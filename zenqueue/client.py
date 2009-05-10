# -*- coding: utf-8 -*-

import socket

from eventlet import api

# Try to import the simplejson library from two possible sources.
try:
    import json
except ImportError:
    import simplejson as json


class QueueClientError(Exception): pass
class ActionError(QueueClientError): pass
class ClosedClientError(QueueClientError): pass
class RequestError(QueueClientError): pass
class TimeoutError(QueueClientError): pass
class UnknownError(QueueClientError): pass


class QueueClient(object):
    
    actions = ['push', 'push_many', 'pull', 'pull_many']
    
    def __init__(self, host='127.0.0.1', port=3000):
        # Connection on initialization was something I felt funny about, but
        # by the same token
        self.socket = api.connect_tcp((host, port))
        self.__reader = None
        self.__writer = None
    
    # Magic methods for use with the 'with' statement (context management).
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False
    
    def close(self):
        # Close the connection with the server. By sending 'quit' this will
        # happen automatically on their end.
        self.writer.write(json.dumps(['quit', [], {}]) + '\r\n')
        
        self.socket.close()
        self.socket = None
        
        self.__writer = None
        self.__reader = None
    
    def action(self, action, args, kwargs):
        if not self.socket:
            raise ClosedClientError
        self.writer.write(json.dumps([action, args, kwargs]) + '\r\n')
        
        status, result = json.loads(self.reader.readline())
        
        if status == 'success':
            return result
        elif status == 'error:action':
            raise ActionError(result)
        elif status == 'error:request':
            raise RequestError(result)
        elif status == 'error:timeout':
            raise TimeoutError
        elif status == 'error:unknown':
            raise UnknownError(result)
    
    def __getattr__(self, attribute):
        if attribute in self.actions:
            def wrapper(*args, **kwargs):
                return self.action(attribute, args, kwargs)
            return wrapper
        raise AttributeError(attribute)
    
    @property
    def reader(self):
        if (not self.__reader) and self.socket:
            self.__reader = self.socket.makefile('r')
        return self.__reader
    
    @property
    def writer(self):
        if (not self.__writer) and self.socket:
            self.__writer = self.socket.makefile('w')
        return self.__writer