# -*- coding: utf-8 -*-

from collections import deque
import errno
import socket

import greenlet
from eventlet import api
from eventlet import coros

# Try to import the simplejson library from two possible sources.
try:
    import json
except ImportError:
    import simplejson as json

from zenqueue import log


class QueueClientError(Exception): pass
class Signal(Exception): pass
class ActionError(QueueClientError): pass
class ClosedClientError(QueueClientError): pass
class CloseSignal(Signal): pass
class RequestError(QueueClientError): pass
class SendError(QueueClientError): pass
class TimeoutError(QueueClientError): pass
class UnknownError(QueueClientError): pass

CLOSE_SIGNAL = object()


class QueueClient(object):
    
    actions = ['push', 'push_many', 'pull', 'pull_many']
    
    def __init__(self, host='127.0.0.1', port=3000):
        self.log = log.get_logger('zenq.client:%x' % (id(self),))
        self.socket = self.connect_tcp((host, port))
        self.transfer_queue = deque()
        self.__reader = None
        self.__writer = None
        
        self.loop = api.spawn(self.run)
        api.sleep(0)
    
    def connect_tcp(self, address):
        self.log.info('Connecting to server at address %r', address)
        return api.connect_tcp(address)
    
    # Magic methods for use with the 'with' statement (context management).
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False
    
    def close(self):
        self.transfer_queue.append((CLOSE_SIGNAL, None))
    
    def _close_transfer_queue(self):
        while self.transfer_queue:
            data, event = self.transfer_queue.pop()
            event.send(ClosedClientError())
    
    def _close(self):
        self._close_transfer_queue()
        
        # If it's already been closed, no need to close it.
        if not self.socket:
            return
        
        # Close the connection with the server.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error, exc:
            if exc.errno not in [errno.EBADF, errno.EPIPE]:
                raise
        
        self.socket.close()
        self.socket = None
        
        self.__writer = None
        self.__reader = None
    
    def run(self):
        self.log.info('Beginning main client loop')
        try:
            while True:
                try:
                    data, event = None, None
                    if self.transfer_queue:
                        self.log.debug('Pulling transfer request from queue')
                        data, event = self.transfer_queue.pop()
                        
                        if data is CLOSE_SIGNAL:
                            raise CloseSignal
                        
                        self.log.debug('Sending request data')
                        self.writer.write(data)
                        self.writer.flush()
                        self.log.debug('Reading line from server')
                        result = self.reader.readline().rstrip('\r\n')
                        self.log.debug('Line read from server')
                except CloseSignal:
                    self.log.info(
                        'Close signal received')
                    self._close()
                    return
                except Exception, exc:
                    self.log.error('Exception %r occurred', exc)
                    self._close()
                    event.send(SendError(exc))
                    break
                else:
                    if event:
                        self.log.debug('Response successfully received')
                        event.send(result)
                api.sleep(0)
        except Exception, exc:
            self.log.fatal('Exception %r occurred in main client loop', exc)
        finally:
            self._close()
    
    def send(self, data):
        receive_event = coros.event()
        self.log.debug('Adding transfer request to queue')
        self.transfer_queue.appendleft((data, receive_event))
        try:
            result = receive_event.wait()
        except Exception, exc:
            self.log.error('Error %r occurred', exc)
            api.spawn(lambda:receive_event.wait())
            api.sleep(0)
            raise exc
        
        if isinstance(result, SendError):
            raise result.args[0]
        elif isinstance(result, ClosedClientError):
            raise result
        
        return result
    
    def action(self, action, args, kwargs):
        self.log.debug('Action %r called with %d args', action,
            len(args) + len(kwargs))
        
        status, result = json.loads(
            self.send(json.dumps([action, args, kwargs]) + '\r\n'))
        
        if status == 'success':
            self.log.debug('Request successful')
            return result
        elif status == 'error:action':
            self.log.error('Action error occurred')
            raise ActionError(result)
        elif status == 'error:request':
            self.log.error('Request error occurred')
            raise RequestError(result)
        elif status == 'error:timeout':
            self.log.debug('Request timed out')
            raise TimeoutError
        elif status == 'error:unknown':
            self.log.error('Unknown error occurred')
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
    
    @property
    def running(self):
        return not self.loop.dead
