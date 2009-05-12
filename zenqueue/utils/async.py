# -*- coding: utf-8 -*-

from collections import deque

from eventlet import api
from eventlet import coros


class DummyTimer(object):
    def cancel(self):
        pass


class Semaphore(object):
    
    """
    A direct translation of the semaphore to coroutine-based programming.
    
    The Semaphore is a synchronization technique that can be used by a number
    of coroutines at once. The mechanism of its function is that it holds a
    count in memory which is set to an initial value. Every time a coroutine
    acquire()s the semaphore, this count is decreased by one, and every
    release() increases the count. If a coroutine attempts to acquire() a
    semaphore with a count of zero, the coroutine will yield until another
    coroutine release()s it.
    """
    
    class WaitCancelled(Exception): pass
    class Timeout(Exception): pass
    
    def __init__(self, initial=0):
        self.coro_queue = deque()
        self.__count = initial
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, *exc_info):
        self.release()
        return False
    
    def acquire(self, timeout=None):
        
        if self.__count <= 0:
            ready_event = coros.event()
            self.coro_queue.appendleft(ready_event)
            
            timer = DummyTimer()
            if timeout is not None:
                timer = api.exc_after(timeout, self.Timeout)
            
            try:
                result = ready_event.wait()
            except self.Timeout:
                if ready_event in self.coro_queue:
                    self.coro_queue.remove(ready_event)
                raise
            else:
                timer.cancel()
                
            if not result:
                raise self.AcquireCancelled()
        
        self.__count -= 1
    
    def release(self):
        self.__count += 1
    
        if self.coro_queue:
            ready_event = self.coro_queue.pop()
            ready_event.send(True)
            api.sleep(0)
    
    def cancel_all(self):
        while self.coro_queue:
            ready_event = self.coro_queue.pop()
            ready_event.send(False)
        api.sleep(0)
    
    @property
    def count(self):
        return self.__count


class Lock(Semaphore):
    
    def __init__(self):
        super(Lock, self).__init__(initial=1)
    
    @property
    def in_use(self):
        return (self.count == 0)