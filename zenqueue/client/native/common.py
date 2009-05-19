# -*- coding: utf-8 -*-

from collections import deque
import errno
import socket

from zenqueue import json
from zenqueue import log
from zenqueue.client.common import AbstractQueueClient


CLOSE_SIGNAL = object() # A sort of singleton, which you can test with `is`.


class NativeQueueClient(AbstractQueueClient):
    
    log_name = 'zenq.client.native'
    lock_class = NotImplemented
    
    def __init__(self, host='127.0.0.1', port=3000):
        super(NativeQueueClient, self).__init__() # Initializes the log.
        
        self.socket = self.connect_tcp((host, port))
        self.__reader = None
        self.__writer = None
        self.__closed = False
        
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
        self.__closed = True
    
    def send(self, data):
        
        # Acquire the socket lock.
        self.log.debug('Acquiring socket lock')
        self.lock.acquire()
        self.log.debug('Socket lock acquired')
        
        if not self.socket:
            raise self.ClosedClientError
        
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
        received_data = self.send(json.dumps([action, args, kwargs]) + '\r\n')
        return self.handle_response(received_data)
    
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
    
    @property
    def closed(self):
        return self.__closed
