#!/usr/bin/env python

from setuptools import setup, find_packages

__author__ = ""

description = ''
name = 'hbfmodules.<category>.<module_name>'
setup(
    name=name,
    version='0.0.1',
    packages=find_packages(),
    license='GPLv3',
    description=description,
    author=__author__,
    url='https://github.com/hydrabus-framework/' + name,
    install_requires=[],
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Development Status :: 3 - Alpha'
    ],
    keywords=['hydrabus', 'framework', 'hardware', 'security']
)
