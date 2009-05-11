# -*- coding: utf-8 -*-

import logging
import sys


LOG_FORMATTER = logging.Formatter(
    "%(asctime)s :: %(name)-18s :: %(levelname)-7s :: %(message)s",
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

get_logger = logging.getLogger
