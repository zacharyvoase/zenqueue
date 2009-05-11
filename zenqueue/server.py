# -*- coding: utf-8 -*-

import errno
import logging
import optparse
import socket
import sys

from eventlet import api
from eventlet import coros

import zenqueue
from zenqueue.queue import Queue

# Try to import the simplejson library from two possible sources.
try:
    import json
except ImportError:
    import simplejson as json


DEFAULT_MAX_CONC_REQUESTS = 1024


# Logging setup

LOG_FORMATTER = logging.Formatter(
    "%(asctime)s :: %(name)-22s :: %(levelname)-7s :: %(message)s",
    datefmt='%a, %d %b %Y %H:%M:%S')

CONSOLE_HANDLER = logging.StreamHandler(sys.stdout)
CONSOLE_HANDLER.setLevel(logging.DEBUG)
CONSOLE_HANDLER.setFormatter(LOG_FORMATTER)

ROOT_LOGGER = logging.getLogger('')
ROOT_LOGGER.setLevel(logging.DEBUG) # Default logging level for library work.
ROOT_LOGGER.addHandler(CONSOLE_HANDLER)

# End logging setup


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
    help='Use log level LEVEL [default %default]', metavar='LEVEL')

# End option parser setup


class Break(Exception): pass


class QueueServer(object):
    
    def __init__(self, queue=None, max_size=DEFAULT_MAX_CONC_REQUESTS):
        self.queue = queue or Queue()
        self.client_pool = coros.CoroutinePool(max_size=max_size)
        self.socket = None
        self.log = logging.getLogger('zenqueue.server:%x' % (id(self),))
    
    def serve(self, interface='0.0.0.0', port=3000):
        
        self.log.info('ZenQueue Server v%s', zenqueue.__version__)
        if interface == '0.0.0.0':
            self.log.info('Serving on %s:%d (all interfaces)', interface, port)
        else:
            self.log.info('Serving on %s:%d', interface, port)
        
        self.socket = api.tcp_listener((interface, port))
        
        try:
            while True:
                
                try:
                    
                    try:
                        client_socket, client_addr = self.socket.accept()
                    except socket.error, exc:
                        if exc[0] not in [errno.EPIPE, errno.EBADF]:
                            raise
                    self.log.info('Client %x connected: %r',
                        id(client_socket), client_addr)
                    self.client_pool.execute_async(self.handle, client_socket)
                    api.sleep(0)
                
                except KeyboardInterrupt:
                    self.log.fatal('Received keyboard interrupt.')
                    api.get_hub().remove_descriptor(self.socket.fileno())
                    break
        finally:
            try:
                self.log.info('Shutting down server.')
                self.socket.close()
            except socket.error, exc:
                if exc[0] != errno.EPIPE:
                    raise
            finally:
                self.socket = None
    
    @staticmethod
    def parse_command(line):
        command = json.loads(line)
        
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
                    output = method(client, *args, **kwargs)
                except Break:
                    break
                except Queue.Timeout:
                    write_json(writer, ['error:timeout', None])
                except Exception, exc:
                    self.log.error('')
                    write_json(writer, ['error:action', repr(exc)])
                else:
                    self.log.debug('Action %r successful for client %x',
                        action, id(client))
                    write_json(writer, ['success', output])
            except Exception, exc:
                self.log.error('Unknown error occurred for client %x: %r',
                    id(client), exc)
                write_json(writer, ['error:unknown', repr(exc)])
        
        self.log.info('Client %x disconnected', id(client))
        client.close()
    
    def do_push(self, client, value):
        self.queue.push(value)
    
    def do_pull(self, client, timeout=None):
        return self.queue.pull(timeout=timeout)
    
    def do_push_many(self, client, *values):
        for value in values:
            self.queue.push(value)
    
    def do_pull_many(self, client, n, timeout=None):
        results = []
        for i in xrange(n):
            try:
                results.append(self.queue.pull(timeout=timeout))
            except self.queue.Timeout:
                break
        return results
    
    def do_quit(self, client):
        client.shutdown(socket.SHUT_RDWR)
        raise Break
    do_exit = do_shutdown = do_quit


def write_json(writer, object):
    writer.write(json.dumps(object) + '\r\n')


def _main():
    options, args = OPTION_PARSER.parse_args()
    
    # Handle log level
    log_level = options.log_level
    if log_level not in 'DEBUG INFO WARNING ERROR FATAL CRITICAL'.split():
        ROOT_LOGGER.warning('Invalid log level supplied, defaulting to INFO')
        ROOT_LOGGER.setLevel(logging.INFO)
    else:
        ROOT_LOGGER.setLevel(getattr(logging, log_level))
    
    # Create and start server.
    server = QueueServer(max_size=options.max_size)
    
    server.serve(interface=options.interface, port=options.port)


if __name__ == '__main__':
    _main()