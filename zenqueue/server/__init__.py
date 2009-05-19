# -*- coding: utf-8 -*-

__all__ = ['http', 'native']


class QueueServer(object):
    
    def __new__(cls, method='native', *args, **kwargs):
        if method == 'native':
            from zenqueue.server.native import NativeQueueServer
            return NativeQueueServer(*args, **kwargs)
        elif method == 'http':
            from zenqueue.server.http import HTTPQueueServer
            return HTTPQueueServer(*args, **kwargs)
        raise ValueError('Invalid server method: %r' % (method,))