# -*- coding: utf-8 -*-

__all__ = ['client', 'queue', 'server', 'utils', 'log']
__version__ = '0.5.1'

# Try to import SimpleJSON from a couple of different sources.
try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        raise ImportError('Looks like you need to install SimpleJSON')