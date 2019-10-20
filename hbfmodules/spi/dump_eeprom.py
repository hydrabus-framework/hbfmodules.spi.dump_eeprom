import serial
import struct

from hydrabus_framework.modules.AModule import AModule
from hydrabus_framework.utils.logger import Logger
from hydrabus_framework.utils.pyHydrabus.spi import SPI


class SpiDump(AModule):
    def __init__(self, hbf_config):
        super(SpiDump, self).__init__(hbf_config)
        self.meta.update({
            'name': 'dump SPI EEPROM',
            'version': '0.0.2',
            'description': 'Module to dump SPI EEPROM',
            'author': 'Jordan Ovrè'
        })
        self.hb_serial = None
        self.options = [
            {"Name": "hydrabus", "Value": "", "Required": True, "Type": "string",
             "Description": "Hydrabus device", "Default": self.config["HYDRABUS"]["port"]},
            {"Name": "timeout", "Value": "", "Required": True, "Type": "int",
             "Description": "Hydrabus read timeout", "Default": self.config["HYDRABUS"]["read_timeout"]},
            {"Name": "dumpfile", "Value": "", "Required": True, "Type": "string",
             "Description": "The dump filename", "Default": ""},
            {"Name": "sectors", "Value": "", "Required": True, "Type": "int",
             "Description": "The number of sector (4096) to read. For example 1024 sector * 4096 = 4MiB",
             "Default": "1024"},
            {"Name": "start_sector", "Value": "", "Required": True, "Type": "int",
             "Description": "The starting sector (1 sector = 4096 bytes)", "Default": "0"},
            {"Name": "spi_device", "Value": "", "Required": True, "Type": "int",
             "Description": "The hydrabus SPI device (1=SPI1 or 0=SPI2)", "Default": 1},
            {"Name": "spi_speed", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI speed (fast = 10.5MHz, slow = 320kHz, medium = 5MHz)", "Default": "slow"},
            {"Name": "spi_polarity", "Value": "", "Required": True, "Type": "int",
             "Description": "set SPI polarity (1=high or 0=low)", "Default": 0},
            {"Name": "spi_phase", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI phase (1=high or 0=low)", "Default": 0}
        ]

    def hex_to_bin(self, num, padding):
        """
        Convert hexadecimal to binary
        :param num: hexadecimal representation
        :param padding: padding
        :return: converted hexadecimal value
        """
        return num.to_bytes(padding, byteorder='big')

    def calc_hex_addr(self, addr, add):
        """
        Calculate an addr and return its hexadecimal representation
        :param addr: based address
        :param add: length to add
        :return:
        """
        addr_int = int(addr, 16)
        addr_int += add
        byte_arr = self.hex_to_bin(addr_int, 3)
        return byte_arr

    def init_hydrabus(self):
        """
        Manage connection and init of the hydrabus into BBIO spi mode
        :return: Bool
        """
        try:
            device = self.get_option_value("hydrabus")
            timeout = int(self.get_option_value("timeout"))
            self.hb_serial = SPI(device)
            self.hb_serial.timeout = timeout
            self.hb_serial.device = self.get_option_value("spi_device")
            self.hb_serial.polarity = self.get_option_value("spi_polarity")
            self.hb_serial.phase = self.get_option_value("spi_phase")
            spi_speed_string = self.get_option_value("spi_speed")
            if spi_speed_string.upper() not in ["SLOW", "FAST", "MEDIUM"]:
                self.logger.handle("Invalid spi_speed value ('slow' or 'fast' expected)", Logger.ERROR)
                return False
            if self.get_option_value("spi_speed").upper() == "FAST":
                if self.get_option_value("spi_device") == 1:
                    self.hb_serial.set_speed(SPI.SPI1_SPEED_10M)
                else:
                    self.hb_serial.set_speed(SPI.SPI2_SPEED_10M)
            if self.get_option_value("spi_speed").upper() == "MEDIUM":
                if self.get_option_value("spi_device") == 1:
                    self.hb_serial.set_speed(SPI.SPI1_SPEED_5M)
                else:
                    self.hb_serial.set_speed(SPI.SPI2_SPEED_5M)
            return True
        except serial.SerialException as err:
            self.logger.handle("{}".format(err), self.logger.ERROR)
            return False

    @staticmethod
    def _sizeof_fmt(num, suffix='B'):
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
            if abs(num) < 1024.0:
                return "%3.1f%s%s" % (num, unit, suffix)
            num /= 1024.0
        return "%.1f%s%s" % (num, 'Yi', suffix)

    def dump_spi(self):
        sectors = self.get_option_value("sectors")
        start_sector = self.get_option_value("start_sector")
        dump_file = self.get_option_value("dumpfile")
        sector_size = 0x1000
        buff = bytearray()
        size = sector_size * sectors

        self.logger.handle("Dump {}".format(self._sizeof_fmt(size)))
        try:
            line_length = 0
            # Ensure to empty the input buffer
            self.hb_serial.read(self.hb_serial.hydrabus.in_waiting)
            while start_sector < size:
                # write-then-read: write 4 bytes (1 read cmd + 3 read addr), read sector_size bytes
                # data = struct.pack('>L', sector_size)[2:] + b'\x03' + struct.pack('>L', start_sector)[1:]
                data = b'\x03' + struct.pack('>L', start_sector)[1:]
                ret = self.hb_serial.write_read(data=data, read_len=sector_size)
                if not ret:
                    raise UserWarning("Error reading data... Abort")
                buff += ret
                # TODO: implement this in framework logger
                print(" "*line_length, end="\r", flush=True)
                print("Readed: {}".format(self._sizeof_fmt(start_sector)), end="\r", flush=True)
                line_length = len("Readed: {}".format(self._sizeof_fmt(start_sector)))
                start_sector += sector_size
            self.logger.handle("Readed: {}".format(self._sizeof_fmt(start_sector)))
            with open(dump_file, 'wb') as f:
                f.write(buff)
            self.logger.handle("Finished dumping to {}".format(dump_file), Logger.RESULT)
        except UserWarning as err:
            self.logger.handle(err, Logger.ERROR)

    def run(self):
        """
        Main function.
        The aim of this module is to dump an spi eeprom
        :return: Nothing
        """
        if self.init_hydrabus():
                self.logger.handle("Starting to read chip...", Logger.INFO)
                self.logger.handle("Reading {} sectors".format(self.get_option_value("sectors")))
                self.dump_spi()
        self.logger.handle("Reset hydrabus to console mode", Logger.INFO)
        if self.hb_serial:
            self.hb_serial.close()

