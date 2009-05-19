# -*- coding: utf-8 -*-

import optparse
import random
import re

from eventlet import api
from eventlet import wsgi

from werkzeug import Request, Response
from werkzeug import exceptions
from werkzeug.routing import Map, Rule

from zenqueue import json
from zenqueue import log
from zenqueue.queue import Queue
import zenqueue


DEFAULT_MAX_CONC_REQUESTS = 1024


# Option parser setup (for command-line usage)

USAGE = 'Usage: %prog [-i IFACE] [-p PORT] [-c NUM] [-l LEVEL]'
OPTION_PARSER = optparse.OptionParser(prog='python -m zenqueue.server.http',
    usage=USAGE, version=zenqueue.__version__)
OPTION_PARSER.add_option('-i', '--interface', default='0.0.0.0',
    help='Bind to interface IFACE [default %default]', metavar='IFACE')
OPTION_PARSER.add_option('-p', '--port', type='int', default=3080,
    help='Run on port PORT [default %default]', metavar='PORT')
OPTION_PARSER.add_option('-c', '--max-connections', type='int', dest='max_size',
    help='Allow maximum NUM concurrent requests [default %default]',
    metavar='NUM', default=DEFAULT_MAX_CONC_REQUESTS)
OPTION_PARSER.add_option('-l', '--log-level', dest='log_level', default='INFO',
    help='Use log level LEVEL [default %default] (use SILENT for no logging)',
    metavar='LEVEL')

# End option parser setup


URL_MAP = Map([
    Rule('/push/', endpoint='push'),
    Rule('/pull/', endpoint='pull'),
    Rule('/push_many/', endpoint='push_many'),
    Rule('/pull_many/', endpoint='pull_many'),
])


class JSONResponse(Response):
    
    def __new__(cls, obj, status=200):
        return Response(response=json.dumps(obj), mimetype='application/json',
            status=status)


class HTTPQueueServer(object):
    
    def __init__(self, queue=None):
        self.log = log.get_logger('zenq.server.http:%x' % (id(self),))
        self.queue = queue or Queue()
    
    def unpack_args(self, data):
        self.log.debug('Data received: %r', data)
        
        args, kwargs = (), {}
        if data:
            parsed = json.loads(data)
            if len(parsed) > 0:
                args = parsed[0]
            if len(parsed) > 1:
                kwargs = parsed[1]
        
        # Convert unicode strings to byte strings.
        for key in kwargs.keys():
            kwargs[str(key)] = kwargs.pop(key)
        
        return args, kwargs
    
    def __call__(self, request):
        
        adapter = URL_MAP.bind_to_environ(request.environ)
        client_id = '%0.6x' % (random.randint(1, 16777215),)
        
        try:
            endpoint, values = adapter.match()
            action = 'do_' + endpoint
            
            # Parse arguments and keyword arguments from request data.
            try:
                args, kwargs = self.unpack_args(request.data)
            except ValueError:
                self.log.error('Received malformed request from client %s',
                    client_id)
                return JSONResponse(['error:request', 'malformed request'],
                    status=400) # Bad Request
        
            # Find the method corresponding to the requested action.
            try:
                method = getattr(self, action)
            except AttributeError:
                self.log.error('Missing action requested by client %s',
                    client_id)
                return JSONResponse(['error:request', 'action not found'],
                    status=404) # Not Found
            
            # Run the method, dealing with exceptions or success.
            try:
                self.log.debug('Action %r requested by client %s',
                    action, client_id)
                output = method(*args, **kwargs)
            except self.queue.Timeout:
                # The client will pick this up. It's not so much a
                # serious error, which is why we don't log it: timeouts
                # are more often than not specified for very useful
                # reasons.
                return JSONResponse(['error:timeout', None])
            except Exception, exc:
                self.log.error(
                    'Action %r raised error %r for client %s',
                    action, exc, client_id)
                return JSONResponse(['error:action', repr(exc)], status=500)
            else:
                # I guess debug is overkill.
                self.log.debug('Action %r successful for client %s',
                    action, client_id)
                return JSONResponse(['success', output])
        except Exception, exc:
            self.log.error('Unknown error occurred for client %s: %r',
                client_id, exc)
            # If we really don't know what happened, return a generic 500.
            return JSONResponse(['error:unknown', repr(exc)], status=500)
        except exceptions.HTTPException, exc:
            return exc
    
    def serve(self, interface='0.0.0.0', port=3080,
        max_size=DEFAULT_MAX_CONC_REQUESTS):
        
        self.log.info('ZenQueue HTTP Server v%s', zenqueue.__version__)
        if interface == '0.0.0.0':
            self.log.info('Serving on %s:%d (all interfaces)', interface, port)
        else:
            self.log.info('Serving on %s:%d', interface, port)
        
        self.sock = api.tcp_listener((interface, port))
        
        try:
            # Wrap `self` with `Request.application` so that we get a request as
            # an argument instead of the usual `environ, start_response`.
            wsgi.server(self.sock, Request.application(self), max_size=max_size)
        finally:
            self.sock = None
    
    def do_push(self, value):
        self.queue.push(value)
    
    def do_pull(self, timeout=None):
        return self.queue.pull(timeout=timeout)
    
    def do_push_many(self, *values):
        self.queue.push_many(*values)
    
    def do_pull_many(self, n, timeout=None):
        return self.queue.pull_many(n, timeout=timeout)


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
    server = HTTPQueueServer()
    server.serve(interface=options.interface, port=options.port,
                 max_size=options.max_size)


if __name__ == '__main__':
    _main()