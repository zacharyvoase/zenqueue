# -*- coding: utf-8 -*-

from eventlet import api

from zenqueue.client.native.common import AbstractQueueClient
from zenqueue.utils.async import Lock


class QueueClient(AbstractQueueClient):
    
    lock_class = Lock
    
    def connect_tcp(self, address):
        self.log.info('Connecting to server at address %r', address)
        return api.connect_tcp(address)
