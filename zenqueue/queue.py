# -*- coding: utf-8 -*-

from collections import deque

from eventlet import api
from eventlet import coros


class QueueTimeoutError(Exception): pass

class DummyTimer(object):
    def cancel(self):
        pass


class Queue(object):
    
    class Timeout(QueueTimeoutError):
        pass
    
    def __init__(self, initial=None):
        self.queue = deque(initial or [])
        self.ready_events = deque()
    
    def pull(self, timeout=None):
        # If there are no items in the queue, then we'll need to wait for
        # another coroutine to add something. The following block performs this
        # waiting, with an optional timeout.
        if not self.queue:            
            # Add event to the queue of coroutines waiting to pull().
            ready_event = coros.event()
            self.ready_events.appendleft(ready_event)
            
            # Build a timer, using a dummy if timeout is None.
            timer = DummyTimer()
            if timeout is not None:
                timer = api.exc_after(timeout, self.Timeout())
            
            # Wait for another coroutine to push() to the queue.
            try:
                ready_event.wait()
            # If it timed out, remove this ready event from the queue.
            except self.Timeout:
                if ready_event in self.ready_events:
                    self.ready_events.remove(ready_event)
                raise
            # One way or another, cancel the timer. This has no effect if the
            # timer has already been called.
            finally:
                timer.cancel()
        
        # By this point, self.queue will have something in it.
        return self.queue.pop()
    
    def push(self, value):
        # Add it to the inner queue. appendleft() is used because pop() removes
        # from the right.
        self.queue.appendleft(value)
        
        # If there are coroutines waiting for items to be added:
        if self.ready_events:
            event = self.ready_events.pop()
            
            # Notify the first coroutine that there is an item on the queue.
            # Since coroutines are added in a queue, this will be the first
            # consumer which pull()'d.
            event.send(True)
            
            # Yield control to another coroutine for an amount of time. This
            # might also allow the ready event to notify the pull()ing coro,
            # which will then pop.
            api.sleep(0)
