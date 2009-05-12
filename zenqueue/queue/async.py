# -*- coding: utf-8 -*-

from zenqueue.queue.common import AbstractQueue
from zenqueue.utils.async import Semaphore


Queue = AbstractQueue.with_semaphore_class(Semaphore)