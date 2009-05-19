# -*- coding: utf-8 -*-

import urllib2

from zenqueue.client.http.common import HTTPQueueClient


class QueueClient(HTTPQueueClient):
    
    def send(self, url, data=''):
        request = urllib2.Request(url, data=data)
        request.add_header('Content-Type', 'application/json; charset=utf-8')
        
        # Catch non-successful HTTP requests and treat them as if they were.
        try:
            conn = urllib2.urlopen(request)
        except urllib2.HTTPError, exc:
            conn = exc
        
        # Both `urllib2.HTTPError` and normal response objects have the same
        # methods and behavior.
        try:
            result = conn.read()
        finally:
            conn.close()
        
        return result