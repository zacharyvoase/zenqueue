# -*- coding: utf-8 -*-

from collections import deque


class AbstractQueue(object):
    
    semaphore_class = None
    
    class Timeout(Exception):
        pass
    
    def __init__(self, initial=None):
        self.queue = deque(initial or [])
        self.semaphore = self.semaphore_class(initial=0)
    
    def pull(self, timeout=None):
        try:
            self.semaphore.acquire(timeout=timeout)
        except self.semaphore.Timeout:
            raise self.Timeout
        return self.queue.pop()
    
    def pull_many(self, n, timeout=None):
        
        # Shortcut for null consumers.
        if n is None and timeout is None:
            while True:
                self.pull()
        
        # If n is None, iterate indefinitely, otherwise n times.
        if n is None:
            gen = eternal(True)
        else:
            gen = xrange(n)
        
        # Pull either n or infinity items from the queue until timeout.
        results = []
        
        for i in gen:
            try:
                results.append(self.pull(timeout=timeout))
            except self.Timeout:
                if not results:
                    raise
        
        return results
    
    def push(self, value):
        # Add it to the inner queue. appendleft() is used because pop() removes
        # from the right.
        self.queue.appendleft(value)
        
        # If coroutines are waiting for items to be available, then this will
        # notify the first of these that there is at least one item on the
        # queue.
        self.semaphore.release()
    
    def push_many(self, *values):
        for value in values:
            self.push(value)
    
    @classmethod
    def with_semaphore_class(cls, semaphore_class):
        return type('Queue', (cls,), {'semaphore_class': semaphore_class})


def eternal(item):
    while True:
        yield item