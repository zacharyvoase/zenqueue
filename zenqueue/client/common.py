# -*- coding: utf-8 -*-

from zenqueue import json
from zenqueue import log


class AbstractQueueClient(object):
    
    class QueueClientError(Exception): pass
    class ActionError(QueueClientError): pass
    class ClosedClientError(QueueClientError): pass
    class RequestError(QueueClientError): pass
    class Timeout(QueueClientError): pass
    class UnknownError(QueueClientError): pass
    
    actions = ['push', 'push_many', 'pull', 'pull_many']
    log_name = 'zenq.client'
    
    def __init__(self):
        self.log = log.get_logger(self.log_name + ':%x' % (id(self),))
    
    def send(self, data):
        raise NotImplementedError
    
    def action(self, action, args, kwargs):
        raise NotImplementedError
    
    def handle_response(self, data):
        try:
            status, result = json.loads(data)
        except ValueError, exc:
            self.log.error('Invalid response returned: %r', data)
            raise
        
        # This handles the various response statuses the server can return.
        if status == 'success':
            self.log.debug('Request successful')
            return result
        elif status == 'error:action':
            self.log.error('Action error occurred')
            raise self.ActionError(result)
        elif status == 'error:request':
            self.log.error('Request error occurred')
            raise self.RequestError(result)
        elif status == 'error:timeout':
            self.log.debug('Request timed out')
            raise self.Timeout
        elif status == 'error:unknown':
            self.log.error('Unknown error occurred')
            raise self.UnknownError(result)
    
    def __getattr__(self, attribute):
        if attribute in self.actions:
            def wrapper(*args, **kwargs):
                return self.action(attribute, args, kwargs)
            return wrapper
        raise AttributeError(attribute)
