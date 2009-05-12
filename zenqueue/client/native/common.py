# -*- coding: utf-8 -*-

from collections import deque
import errno
import socket

# Try to import the simplejson library from two possible sources.
try:
    import json
except ImportError:
    import simplejson as json

from zenqueue import log


# The following are a bunch of different exceptions and signals that can be
# raised.
class QueueClientError(Exception): pass
class ActionError(QueueClientError): pass
class ClosedClientError(QueueClientError): pass
class RequestError(QueueClientError): pass
class TimeoutError(QueueClientError): pass
class UnknownError(QueueClientError): pass

CLOSE_SIGNAL = object() # A sort of singleton.


class AbstractQueueClient(object):
    
    actions = ['push', 'push_many', 'pull', 'pull_many']
    lock_class = NotImplemented
    
    def __init__(self, host='127.0.0.1', port=3000):
        self.log = log.get_logger('zenq.client:%x' % (id(self),))
        
        self.socket = self.connect_tcp((host, port))
        self.__reader = None
        self.__writer = None
        
        self.lock = self.lock_class()
    
    def connect_tcp(self, address):
        # This is an abstract supermethod.
        raise NotImplementedError
    
    # Magic methods for use with the 'with' statement (context management).
    # Although ZenQueue runs really slowly on Python 2.6 and I don't know why.
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False
    
    def close(self):
        # The following closes the connection by first sending the 'quit'
        # message and then closing the socket via the forced _close() method.
        self.lock.acquire()
        try:
            self.writer.write(json.dumps(['quit']) + '\r\n')
            self._close()
        except Exception, exc:
            self.log.error('Error %r occurred while closing connection', exc)
            raise
        finally:
            self.lock.release()
    
    def _close(self):
        self.lock.cancel_all()
        
        # If it's already been closed, no need to close it.
        if not self.socket:
            return
        
        # Close the connection with the server.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error, exc:
            # If 'broken pipe' or 'bad file descriptor' exceptions are raised
            # then it basically means the server has already been closed.
            if exc[0] not in [errno.EBADF, errno.EPIPE, errno.ENOTCONN]:
                raise
        
        self.socket.close()
        self.socket = None
        
        self.__writer = None
        self.__reader = None
    
    def send(self, data):
        
        # Acquire the socket lock.
        self.log.debug('Acquiring socket lock')
        self.lock.acquire()
        self.log.debug('Socket lock acquired')
        
        if not self.socket:
            raise ClosedClientError
        
        try:
            # Send the request data. It should be a single line,
            # terminated by CR/LF characters, but we won't try to
            # enforce this because we assume the client knows what
            # he/she/it is doing.
            self.log.debug('Sending request data')
            self.writer.write(data)
            # Necessary to ensure the data is sent.
            self.writer.flush()
            
            self.log.debug('Reading line from server')
            # This could block, in which case no other thread would be able to
            # use this client object until it were finished.
            result = self.reader.readline().rstrip('\r\n')
            self.log.debug('Line read from server')
        except Exception, exc:
            self.log.error('Error %r occurred', exc)
            raise
        finally:
            self.log.debug('Releasing socket lock')
            self.lock.release()
        
        return result
    
    def action(self, action, args, kwargs):
        # It's really pathetic, but it's still debugging output.
        self.log.debug('Action %r called with %d args', action,
            len(args) + len(kwargs))
        
        # This method is responsible for the JSON encoding/decoding, not send().
        # This was deliberate because it keeps most of the protocol details
        # separate from the lower-level socket code.
        try:
            received_data = self.send(
                json.dumps([action, args, kwargs]) + '\r\n')
            status, result = json.loads(received_data)
        except ValueError, exc:
            self.log.error('Invalid response returned: %r', received_data)
            raise
        
        # This handles the various response statuses the server can return.
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
        # Caches reader attribute. This wraps the socket, making it work like
        # a file handle (with read() and readline() methods, etc.).
        if (not self.__reader) and self.socket:
            self.__reader = self.socket.makefile('r')
        return self.__reader
    
    @property
    def writer(self):
        # Caches writer attribute. See the comments on the reader property for
        # more information.
        if (not self.__writer) and self.socket:
            self.__writer = self.socket.makefile('w')
        return self.__writer
