# -*- coding: utf-8 -*-

__all__ = ['async', 'common', 'sync', 'Queue']


class Queue(object):
    
    def __new__(cls, mode='async', *args, **kwargs):
        if mode == 'async':
            from zenqueue.queue import async
            return async.Queue(*args, **kwargs)
        elif mode == 'sync':
            from zenqueue.queue import sync
            return sync.Queue(*args, **kwargs)
        raise ValueError('Invalid queue mode: %r' % (mode,))