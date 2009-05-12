# -*- coding: utf-8 -*-

from collections import deque
from functools import wraps

import threading


def with_lock(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self._lock.acquire()
        try:
            return method(self, *args, **kwargs)
        finally:
            self._lock.release()
    return wrapper


class Event(object):
    
    """An event which allows values to be sent."""
    
    class WaitCancelled(Exception): pass
    class Timeout(Exception): pass
    
    def __init__(self):
        self._lock = threading.Lock()
        self._waiters = {}
        self._result = None
    
    @with_lock
    def send(self, value=True):
        self._result = value
        
        for waiter in self._waiters.keys():
            self._waiters[waiter][1] = True
            self._waiters[waiter][0].set()
    
    @with_lock
    def cancel_all(self):
        for waiter in self._waiters.keys():
            self.cancel(waiter)
    
    @with_lock
    def cancel(self, thread):
        if thread in self._waiters:
            self._waiters[thread][1] = False
            self._waiters[thread][0].set()
    
    def wait(self, timeout=None):
        event = threading.Event()
        self._waiters[threading.currentThread()] = [event, None]
        
        # A timeout of None implies eternal blocking.
        if timeout is not None:
            event.wait(timeout)
        else:
            event.wait()
        
        status = self._waiters.pop(threading.currentThread())[1]
        
        if not event.isSet():
            raise self.Timeout
        
        if status:
            return self._result
        raise self.WaitCancelled


class Semaphore(object):
    
    """A semaphore with queueing which records the threads which acquire it."""
    
    class WaitCancelled(Exception): pass
    class Timeout(Exception): pass
    
    def __init__(self, initial=0):
        self.evt_queue = deque()
        self._lock = threading.Lock()
        self.__count = initial
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, *exc_info):
        self.release()
        return False
    
    def acquire(self, timeout=None):
        
        if self.__count <= 0:
            ready_event = Event()
            self.evt_queue.appendleft(ready_event)
            
            try:
                result = ready_event.wait(timeout=timeout)
            except ready_event.Timeout:
                if ready_event in self.evt_queue:
                    self.evt_queue.remove(ready_event)
                raise self.Timeout
            except ready_event.WaitCancelled:
                if ready_event in self.evt_queue:
                    self.evt_queue.remove(ready_event)
                raise self.WaitCancelled
        
        self.__count -= 1
    
    def release(self):
        self.__count += 1
    
        if self.evt_queue:
            ready_event = self.evt_queue.pop()
            ready_event.send(True)
    
    @with_lock
    def cancel_all(self):
        while self.evt_queue:
            ready_event = self.evt_queue.pop()
            ready_event.cancel_all()
    
    @property
    def count(self):
        return self.__count


class Lock(Semaphore):
    
    def __init__(self):
        super(Lock, self).__init__(initial=1)
    
    @property
    def in_use(self):
        return (self.count == 0)