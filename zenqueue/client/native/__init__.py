# -*- coding: utf-8 -*-

__all__ = ['async', 'common', 'sync', 'QueueClient']


class QueueClient(object):
    
    def __new__(cls, mode='async', *args, **kwargs):
        if mode == 'async':
            from zenqueue.client.native.async import QueueClient
        elif mode == 'sync':
            from zenqueue.client.native.sync import QueueClient
        else:
            raise ValueError('Invalid client mode: %r' % (mode,))
        return QueueClient(*args, **kwargs)