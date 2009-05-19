# -*- coding: utf-8 -*-

__all__ = ['client', 'queue', 'server', 'utils', 'log']
__version__ = '0.5'

# Try to import SimpleJSON from a couple of different sources.
try:
    import json
except ImportError:
    import simplejson as json
