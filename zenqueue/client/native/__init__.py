# -*- coding: utf-8 -*-

__all__ = ['async', 'common', 'sync', 'QueueClient']


class QueueClient(object):
    
    def __new__(cls, mode='async', *args, **kwargs):
        if mode == 'async':
            from zenqueue.client.native import async
            return async.QueueClient(*args, **kwargs)
        elif mode == 'sync':
            from zenqueue.client.native import sync
            return async.QueueClient(*args, **kwargs)
        raise ValueError('Invalid client mode: %r' % (mode,))