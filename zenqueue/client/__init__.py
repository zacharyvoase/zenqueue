# -*- coding: utf-8 -*-

__all__ = ['common', 'http', 'native', 'QueueClient']


class QueueClient(object):
    
    def __new__(cls, method='native', *args, **kwargs):
        if method == 'native':
            from zenqueue.client.native import QueueClient
        elif method == 'http':
            from zenqueue.client.http import QueueClient
        else:
            raise ValueError('Invalid client method: %r' % (method,))
        return QueueClient(*args, **kwargs)
