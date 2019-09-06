import serial
import struct

from hydrabus_framework.modules.AModule import AModule
from hydrabus_framework.utils.hb_generic_cmd import hb_connect_bbio, hb_reset, hb_close
from hydrabus_framework.utils.protocols.spi import hb_switch_spi, hb_configure_spi_port, set_spi_speed
from hydrabus_framework.utils.logger import Logger


class SpiDump(AModule):
    def __init__(self, hbf_config):
        super(SpiDump, self).__init__(hbf_config)
        self.meta.update({
            'name': 'dump SPI EEPROM',
            'version': '0.0.1',
            'description': 'Module to dump SPI EEPROM',
            'author': 'Jordan Ovrè'
        })
        self.serial = serial.Serial()
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
            {"Name": "spi_device", "Value": "", "Required": True, "Type": "string",
             "Description": "The hydrabus SPI device (SPI1 or SPI2)", "Default": "SPI1"},
            {"Name": "spi_speed", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI speed (fast = 10.5MHz, slow = 320kHz)", "Default": "slow"},
            {"Name": "spi_polarity", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI polarity (high or low)", "Default": "low"},
            {"Name": "spi_phase", "Value": "", "Required": True, "Type": "string",
             "Description": "set SPI phase (high or low)", "Default": "low"}
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

    def connect(self):
        """
        Connect to hydrabus and switch into BBIO mode
        :return: Bool
        """
        try:
            device = self.get_option_value("hydrabus")
            self.serial = hb_connect_bbio(device=device, baudrate=115200, timeout=1)
            if not self.serial:
                raise UserWarning("Unable to connect to hydrabus device")
            return True
        except UserWarning as err:
            self.logger.handle("{}".format(err), Logger.ERROR)
            return False

    def init_hydrabus(self):
        """
        Manage connection and init of the hydrabus into BBIO spi mode
        :return: Bool
        """
        if self.connect():
            if hb_switch_spi(self.serial):
                return True
            else:
                self.logger.handle("Unable to switch hydrabus in spi mode, please reset it", Logger.ERROR)
                return False
        else:
            self.logger.handle("Unable to connect to hydrabus", Logger.ERROR)
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
            while start_sector < size:
                # write-then-read: write 4 bytes (1 read cmd + 3 read addr), read sector_size bytes
                self.serial.write(b'\x04\x00\x04' + struct.pack('>L', sector_size)[2:])
                # read command (\x03) and address
                self.serial.write(b'\x03' + struct.pack('>L', start_sector)[1:])
                # Hydrabus will send \x01 in case of success...
                ret = self.serial.read(1)
                if not ret:
                    raise UserWarning("Error reading data... Abort")
                buff += self.serial.read(sector_size)
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
            result = hb_configure_spi_port(self.serial,
                                           polarity=self.get_option_value("spi_polarity"),
                                           phase=self.get_option_value("spi_phase"),
                                           spi_device=self.get_option_value("spi_device"))
            if result:
                spi_device = self.get_option_value("spi_device")
                spi_speed_string = self.get_option_value("spi_speed")
                if spi_speed_string.upper() == "FAST":
                    if not set_spi_speed(self.serial, spi_speed="10.5MHZ", spi_device=spi_device):
                        return
                elif spi_speed_string.upper() == "SLOW":
                    if not set_spi_speed(self.serial, spi_speed="320KHZ", spi_device=spi_device):
                        return
                else:
                    self.logger.handle("Invalid spi_speed value ('slow' or 'fast' expected)", Logger.ERROR)
                    return
                self.logger.handle("Starting to read chip...", Logger.INFO)
                self.logger.handle("Reading {} sectors".format(self.get_option_value("sectors")))
                self.dump_spi()
            self.logger.handle("Reset hydrabus to console mode", Logger.INFO)
            hb_reset(self.serial)
            hb_close(self.serial)
