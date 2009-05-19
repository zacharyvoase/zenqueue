# -*- coding: utf-8 -*-

import socket
import threading

from zenqueue.client.native.common import NativeQueueClient
from zenqueue.utils.sync import Lock


class QueueClient(NativeQueueClient):
    
    lock_class = Lock
    
    def connect_tcp(self, address):
        self.log.info('Connecting to server at address %r', address)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(address)
        return sock
