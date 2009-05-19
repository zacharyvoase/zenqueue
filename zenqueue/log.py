# -*- coding: utf-8 -*-

# This module contains some defaults for the logging system.

import logging
import sys


LOG_FORMATTER = logging.Formatter(
    "%(asctime)s :: %(name)s :: %(levelname)-7s :: %(message)s",
    datefmt='%a, %d %b %Y %H:%M:%S')

CONSOLE_HANDLER = logging.StreamHandler(sys.stdout)
CONSOLE_HANDLER.setLevel(logging.DEBUG)
CONSOLE_HANDLER.setFormatter(LOG_FORMATTER)

ROOT_LOGGER = logging.getLogger('')
ROOT_LOGGER.setLevel(logging.DEBUG) # Default logging level for library work.
ROOT_LOGGER.addHandler(CONSOLE_HANDLER)

LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL', 'CRITICAL']
for level in LOG_LEVELS:
    vars()[level] = getattr(logging, level)

global get_logger
get_logger = logging.getLogger

def set_level(level):
    ROOT_LOGGER.setLevel(getattr(logging, level))

def silence():
    global get_logger
    get_logger = lambda name: NullLogger()
    ROOT_LOGGER.setLevel(float('inf'))


class NullLogger(object):
    def __getattr__(self, attr):
        if attr.upper() in LOG_LEVELS:
            return lambda *args, **kwargs: None
