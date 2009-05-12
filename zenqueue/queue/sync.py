# -*- coding: utf-8 -*-

from zenqueue.queue.common import AbstractQueue
from zenqueue.utils.sync import Semaphore


Queue = AbstractQueue.with_semaphore_class(Semaphore)