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


# The following are a bunch of different exceptions and signals that can be
# raised.
class QueueClientError(Exception): pass
class Signal(Exception): pass
class ActionError(QueueClientError): pass
class ClosedClientError(QueueClientError): pass
class CloseSignal(Signal): pass
class RequestError(QueueClientError): pass
class SendError(QueueClientError): pass
class TimeoutError(QueueClientError): pass
class UnknownError(QueueClientError): pass

CLOSE_SIGNAL = object() # A sort of singleton.


class QueueClient(object):
    
    actions = ['push', 'push_many', 'pull', 'pull_many']
    
    def __init__(self, host='127.0.0.1', port=3000):
        self.log = log.get_logger('zenq.client:%x' % (id(self),))
        self.socket = self.connect_tcp((host, port))
        self.transfer_queue = deque()
        self.__reader = None
        self.__writer = None
        
        # The loop is the backbone of the client object. Having a loop means
        # multiple coroutines may use the same client object without any issues
        # like locking, etc.
        self.loop = api.spawn(self.run)
        api.sleep(0)
    
    def connect_tcp(self, address):
        # This has been made into its own method so that when I extend the
        # client object in the future, I can do dependency injection.
        self.log.info('Connecting to server at address %r', address)
        return api.connect_tcp(address)
    
    # Magic methods for use with the 'with' statement (context management).
    # Although ZenQueue runs really slowly on Python 2.6 and I don't know why.
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()
        return False
    
    def close(self):
        # Shuts the client down gracefully. _close() can be called for a forced
        # shutdown, but this is bad practice.
        self.transfer_queue.append((CLOSE_SIGNAL, None))
    
    def _close_transfer_queue(self):
        # The events on the transfer queue will recognise the ClosedClientError
        # instance and raise it in their respective coroutines.
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
            # If 'broken pipe' or 'bad file descriptor' exceptions are raised
            # then it basically means the server has already been closed.
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
                        # Pull transfer request from queue
                        self.log.debug('Pulling transfer request from queue')
                        data, event = self.transfer_queue.pop()
                        
                        if data is CLOSE_SIGNAL:
                            raise CloseSignal
                        
                        # Send the request data. It should be a single line,
                        # terminated by CR/LF characters, but we won't try to
                        # enforce this because we assume the client knows what
                        # he/she/it is doing.
                        self.log.debug('Sending request data')
                        self.writer.write(data)
                        # Necessary to ensure the data is sent.
                        self.writer.flush()
                        
                        self.log.debug('Reading line from server')
                        # This could return (almost) immediately or it could
                        # yield; either way, no other requests will get to try
                        # and read from this socket because of the mutual
                        # exclusion inherent in coroutines.
                        result = self.reader.readline().rstrip('\r\n')
                        self.log.debug('Line read from server')
                        
                except CloseSignal:
                    self.log.info(
                        'Close signal received')
                    # At least we're sure that no requests are running.
                    self._close()
                    return
                except Exception, exc:
                    self.log.error('Exception %r occurred', exc)
                    # If an error occurs, we need to close this connection,
                    # simply because we don't know what might have happened. The
                    # coroutine which receives the SendError() exception will
                    # know to extract the inner exception and raise it.
                    self._close()
                    event.send(SendError(exc))
                    break # Stop the client loop.
                else:
                    if event:
                        # If there was nothing in the transfer queue, the event
                        # will still be None.
                        self.log.debug('Response successfully received')
                        event.send(result)
                # Hand control to another coroutine, if others are running.
                api.sleep(0)
        except Exception, exc:
            # Log this exception but still raise it.
            self.log.fatal('Exception %r occurred in main client loop', exc)
            raise exc
        finally:
            # One way or another, when the main loop finishes executing, we
            # have to close the socket. We don't use the graceful close()
            # because that uses the transfer queue, which itself only works
            # when the main loop is running.
            self._close()
    
    def send(self, data):
        # Events are the way for one coroutine to communicate with one or more
        # coroutines. Eventlet is cool in that this coroutine will yield when
        # waiting for the result of the request.
        receive_event = coros.event()
        self.log.debug('Adding transfer request to queue')
        self.transfer_queue.appendleft((data, receive_event))
        
        try:
            result = receive_event.wait() # Yields control.
        except Exception, exc:
            self.log.error('Error %r occurred', exc)
            # An error occurred between wait()ing and actually receiving. What
            # we need to do is spawn a 'null consumer' to receive the event, so
            # that we don't get dangling events hanging around the transfer
            # queue and in memory.
            api.spawn(lambda:receive_event.wait())
            # Yield again so that the null consumer has a chance to consume.
            api.sleep(0)
            raise exc
        
        if isinstance(result, SendError):
            # Sometimes, a SendError instance can be sent which will cause this
            # function to raise the first argument provided (which should
            # itself be an exception).
            raise result.args[0]
        elif isinstance(result, ClosedClientError):
            # Sometimes, the client can close before we receive the output. This
            # will occurr if you call close() before all transfers in the
            # transfer queue have executed.
            raise result
        
        return result
    
    def action(self, action, args, kwargs):
        # It's really pathetic, but it's still debugging output.
        self.log.debug('Action %r called with %d args', action,
            len(args) + len(kwargs))
        
        # This method is responsible for the JSON encoding/decoding, not send().
        # This was deliberate because it keeps most of the protocol details
        # separate from the lower-level socket code.
        status, result = json.loads(
            self.send(json.dumps([action, args, kwargs]) + '\r\n'))
        
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
    
    @property
    def running(self):
        # Just a simple utility shortcut.
        return not self.loop.dead
