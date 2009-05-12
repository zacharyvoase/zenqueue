# -*- coding: utf-8 -*-

import errno
import optparse
import socket
import sys

from eventlet import api
from eventlet import coros

import zenqueue
from zenqueue import log
from zenqueue.queue import Queue

# Try to import the simplejson library from two possible sources.
try:
    import json
except ImportError:
    import simplejson as json


DEFAULT_MAX_CONC_REQUESTS = 1024


# Option parser setup (for command-line usage)

USAGE = 'Usage: %prog [-i IFACE] [-p PORT] [-c NUM] [-l LEVEL]'
OPTION_PARSER = optparse.OptionParser(prog='python -m zenqueue.server',
    usage=USAGE, version=zenqueue.__version__)
OPTION_PARSER.add_option('-i', '--interface', default='0.0.0.0',
    help='Bind to interface IFACE [default %default]', metavar='IFACE')
OPTION_PARSER.add_option('-p', '--port', type='int', default=3000,
    help='Run on port PORT [default %default]', metavar='PORT')
OPTION_PARSER.add_option('-c', '--max-connections', type='int', dest='max_size',
    help='Allow maximum NUM concurrent requests [default %default]',
    metavar='NUM', default=DEFAULT_MAX_CONC_REQUESTS)
OPTION_PARSER.add_option('-l', '--log-level', dest='log_level', default='INFO',
    help='Use log level LEVEL [default %default] (use SILENT for no logging)',
    metavar='LEVEL')

# End option parser setup


# These exception definitions, while empty, allow code higher up the call chain
# to identify the nature of an error. Break, for example, is more of a signal
# than an error.
class ActionError(Exception): pass
class Break(Exception): pass


class QueueServer(object):
    
    def __init__(self, queue=None, max_size=DEFAULT_MAX_CONC_REQUESTS):
        
        self.log = log.get_logger('zenq.server:%x' % (id(self),))
        
        # An initial queue may be provided; this might help with durable queues
        # (i.e. those that save their state to disk and can restore it on load).
        self.queue = queue or Queue()
        
        # The client pool is a pool of coroutines which doesn't allow more than
        # max_size coroutines to be running 'at the same time' (although
        # strictly speaking they never do anyway). In this case it represents
        # the maximum number of clients that may be connected at once.
        self.client_pool = coros.CoroutinePool(max_size=max_size)
        
        self.socket = None
    
    def serve(self, interface='0.0.0.0', port=3000):
        
        self.log.info('ZenQueue Server v%s', zenqueue.__version__)
        if interface == '0.0.0.0':
            self.log.info('Serving on %s:%d (all interfaces)', interface, port)
        else:
            self.log.info('Serving on %s:%d', interface, port)
        
        self.socket = api.tcp_listener((interface, port))
        
        # A lot of the code below was copied or adapted from eventlet's
        # implementation of an asynchronous WSGI server.
        try:
            while True:
                try:
                    try:
                        client_socket, client_addr = self.socket.accept()
                    except socket.error, exc:
                        # EPIPE (Broken Pipe) and EBADF (Bad File Descriptor)
                        # errors are common for clients that suddenly quit. We
                        # shouldn't worry so much about them.
                        if exc[0] not in [errno.EPIPE, errno.EBADF]:
                            raise
                    # Throughout the logging output, we use the client's ID in
                    # hexadecimal to identify a particular client in the logs.
                    self.log.info('Client %x connected: %r',
                        id(client_socket), client_addr)
                    # Handle this client on the pool, sleeping for 0 time to
                    # allow the handler (or other coroutines) to run.
                    self.client_pool.execute_async(self.handle, client_socket)
                    api.sleep(0)
                
                except KeyboardInterrupt:
                    # It's a fatal error because it kills the program.
                    self.log.fatal('Received keyboard interrupt.')
                    # This removes the socket from the current hub's list of
                    # sockets to check for clients (i.e. the select() call).
                    # select() is a key component of asynchronous networking.
                    api.get_hub().remove_descriptor(self.socket.fileno())
                    break
        finally:
            try:
                self.log.info('Shutting down server.')
                self.socket.close()
            except socket.error, exc:
                # See above for why we shouldn't worry about Broken Pipe or Bad
                # File Descriptor errors.
                if exc[0] not in [errno.EPIPE, errno.EBADF]:
                    raise
            finally:
                self.socket = None
    
    @staticmethod
    def parse_command(line):
        command = json.loads(line)
        
        # The specification for commands is really simple. Essentially they
        # consist of lists:
        #     ['action_name', ['arg1', 'arg2'], {'key': 'value'}]
        # The protocol is surprisingly close to Remote Procedure Call (RPC).
        action, args, kwargs = command[0], (), {}
        if len(command) > 1:
            args = command[1]
        if len(command) > 2:
            kwargs = command[2]
        
        # Convert unicode strings to byte strings.
        for key in kwargs.keys():
            kwargs[str(key)] = kwargs.pop(key)
        
        return action, args, kwargs
    
    def handle(self, client):
        reader, writer = client.makefile('r'), client.makefile('w')
        
        try:
            while True:
                try:
                    # If the client sends an empty line, ignore it.
                    line = reader.readline()
                    stripped_line = line.rstrip('\r\n')
                    if not line:
                        break
                    elif not stripped_line:
                        api.sleep(0)
                        continue
                
                    # Try to parse the request, failing if it is invalid.
                    try:
                        action, args, kwargs = self.parse_command(stripped_line)
                    except ValueError:
                        # Request was malformed. ValueError is raised by
                        # simplejson when the passed string is not valid JSON.
                        self.log.error('Received malformed request from client %x',
                            id(client))
                        write_json(writer, ['error:request', 'malformed request'])
                        continue
                
                    # Find the method corresponding to the requested action.
                    try:
                        method = getattr(self, 'do_' + action)
                    except AttributeError:
                        self.log.error('Missing action requested by client %x',
                            id(client))
                        write_json(writer, ['error:request', 'action not found'])
                        continue
                
                    # Run the method, dealing with exceptions or success.
                    try:
                        self.log.debug('Action %r requested by client %x',
                            action, id(client))
                        # All actions get the client socket as an additional
                        # argument. This means they can do cool things with the
                        # client object that might not be possible otherwise.
                        output = method(client, *args, **kwargs)
                    except Break:
                        # The Break error propagates up the call chain and
                        # causes the server to disconnect the client.
                        break
                    except self.queue.Timeout:
                        # The client will pick this up. It's not so much a
                        # serious error, which is why we don't log it: timeouts
                        # are more often than not specified for very useful
                        # reasons.
                        write_json(writer, ['error:timeout', None])
                    except Exception, exc:
                        self.log.error(
                            'Action %r raised error %r for client %x',
                            action, exc, id(client))
                        write_json(writer, ['error:action', repr(exc)])
                        # Chances are that if an error occurred, we'll need to
                        # raise it properly. This will trigger the closing of
                        # the client socket via the finally clause below.
                        raise ActionError(exc)
                    else:
                        # I guess debug is overkill.
                        self.log.debug('Action %r successful for client %x',
                            action, id(client))
                        write_json(writer, ['success', output])
                except ActionError, exc:
                    # Raise the inner action error. This will prevent the
                    # catch-all except statement below from logging action
                    # errors as 'unknown' errors. The exception has already been
                    # written to the client.
                    raise ActionError.args[0]
                except Exception, exc:
                    self.log.error('Unknown error occurred for client %x: %r',
                        id(client), exc)
                    # If we really don't know what happened, then
                    write_json(writer, ['error:unknown', repr(exc)])
                    raise # Raises the last exception, in this case exc.
        except:
            # If any exception has been raised at this point, it will show up as
            # an error in the logging output.
            self.log.error('Forcing disconnection of client %x', id(client))
        finally:
            # If code reaches this point simply by non-error means (i.e. an
            # actual call to the quit, exit or shutdown actions), then it will
            # not include an error-level logging event.
            self.log.info('Client %x disconnected', id(client))
            client.close()
    
    # Most of these methods are pure wrappers around the underlying queue
    # object.
    
    def do_push(self, client, value):
        self.queue.push(value)
    
    def do_pull(self, client, timeout=None):
        # Timeouts will propagate upwards to the client loop and be handled
        # accordingly.
        return self.queue.pull(timeout=timeout)
    
    def do_push_many(self, client, *values):
        self.queue.push_many(*values)
    
    def do_pull_many(self, client, n, timeout=None):
        # Timeouts will propagate upwards to the client loop and be handled
        # accordingly.
        return self.queue.pull_many(n, timeout=timeout)
    
    def do_quit(self, client):
        client.shutdown(socket.SHUT_RDWR)
        # This will be caught and cause the client loop to break, essentially
        # closing the client's connection.
        raise Break
    # exit and shutdown are synonyms for quit.
    do_exit = do_shutdown = do_quit


def write_json(writer, object):
    # A simple utility method.
    writer.write(json.dumps(object) + '\r\n')


def _main():
    options, args = OPTION_PARSER.parse_args()
    
    # Handle log level.
    log_level = options.log_level
    if log_level.upper() == 'SILENT':
        # Completely disables logging output.
        log.silence()
    elif log_level.upper() not in log.LOG_LEVELS:
        log.ROOT_LOGGER.warning(
            'Invalid log level supplied, defaulting to INFO')
        log.ROOT_LOGGER.setLevel(log.INFO)
    else:
        log.ROOT_LOGGER.setLevel(getattr(log, log_level.upper()))
    
    # Instantiate and start server.
    server = QueueServer(max_size=options.max_size)
    server.serve(interface=options.interface, port=options.port)


if __name__ == '__main__':
    _main()