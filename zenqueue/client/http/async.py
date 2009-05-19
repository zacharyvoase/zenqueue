# -*- coding: utf-8 -*-

from eventlet import httpc

from zenqueue.client.http.common import HTTPQueueClient


class QueueClient(HTTPQueueClient):
    
    def send(self, url, data=''):
        # Catch non-successful HTTP requests and treat them as if they were.
        try:
            result = httpc.post(url, data=data,
                content_type='application/json; charset=utf-8')
        except httpc.ConnectionError, exc:
            result = exc.params.response_body
        
        return result