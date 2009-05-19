# -*- coding: utf-8 -*-

import urllib

from urlobject import URLObject

from zenqueue import json
from zenqueue.client.common import AbstractQueueClient


class HTTPQueueClient(AbstractQueueClient):
    
    log_name = 'zenq.client.http'
    
    def __init__(self, host='127.0.0.1', port=3080):
        super(HTTPQueueClient, self).__init__() # Initializes logging.
        
        self.host = host
        self.port = port
    
    def send(self, url, data=''):
        raise NotImplementedError
    
    def action(self, action, args, kwargs):
        # It's really pathetic, but it's still debugging output.
        self.log.debug('Action %r called with %d args', action,
            len(args) + len(kwargs))
        
        path = '/' + urllib.quote(action) + '/'        
        url = URLObject(host=self.host).with_port(self.port).with_path(path)
        received_data = self.send(url, data=json.dumps([args, kwargs]))
        
        return self.handle_response(received_data)