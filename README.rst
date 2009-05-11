===============
ZenQueue v0.3.2
===============

ZenQueue is an incredibly simple message queueing system. It was designed as an experiment, but the author thought it was pretty neat and powerful and decided to release it to the world at large. The latest release of this library includes faster and more stable client and server implementations. The next minor release (version 0.4) will include a client implementation which does not use Eventlet.

Aim and History
===============

At its heart, ZenQueue aims to be a lean, network-available implementation of the queue data structure. After playing around with the concept and realising that it was actually quite cool, I decided to go about implementing this as simply as possible. Experience tells me that the more lines of code your application has, the more prone it is to errors and the slower it's likely to be.

Requirements
============

In order to run ZenQueue, you're going to need the fantastic `Eventlet <http://wiki.secondlife.com/wiki/Eventlet>`_ library, and at least Python 2.4. I tried to write this to be as portable as possible, but there may be some issues (I don't exactly have many systems to test this out on). You'll also need the `simplejson <http://pypi.python.org/pypi/simplejson/>`_ library if you want to run the ZenQueue server. In addition, this library (and client, and server) runs around *six* times faster on Python 2.5 than Python 2.6. The author hasn't a clue as to why, but if you really want to take advantage of ZenQueue's speed, then use Python 2.5.

Using a Queue From Your Code
============================

So it's pretty simple to use ZenQueue; just import it and you're away::
    
    >>> from zenqueue.queue import Queue
    >>> q = Queue()
    >>> q.push('a')
    >>> q.push('b')
    >>> q.push_many('c', 'd')
    >>> q.pull_many(3)
    ['a', 'b', 'c']
    >>> q.pull()
    'd'
    >>> q.pull(timeout=0) # Queue is empty, so this raises a Timeout error.
    Traceback (most recent call last):
        ...
    zenqueue.queue.Timeout

The queue itself is managed not by threads and locks, but by coroutines. If you don't know what they are, or don't understand them, then the introductory material out there is probably far better than what I could ever attempt to reproduce; however, I will tell you that they're awesome, and that they solve a multitude of issues that are difficult to get around with traditional threads. One of the coolest things about them is that coroutines actually *benefit* from having the Global Interpreter Lock (if you don't know what that is then you probably don't need to).

If you want to run things in parallel that use the same queue, rather than using ``threading.Thread``, you should use the helpful functions and classes provided in ``eventlet.api`` and ``eventlet.coros``. Consult the `Eventlet documentation <http://wiki.secondlife.com/wiki/Eventlet/Documentation>`_ for more information on these; I really can't afford to be brief on them here (you need the thorough walkthrough).

Timeouts
--------

Calling ``queue.pull()`` or ``queue.pull_many()`` to retrieve some items from the queue will *yield* until another coroutine adds an item to the queue. If you're operating on the queue within a single coroutine this means the queue will, for all extents and purposes, block. If you wish to retrieve an item without blocking, you can specify a ``timeout`` keyword argument. A timeout of zero will tell the queue the equivalent of "if there's nothing in the queue, just raise an error right now". The ``zenqueue.queue.Queue.Timeout`` exception will be raised (so you can test for that in your ``except`` clauses). An easier way is to test for ``queue.Timeout``, where ``queue`` is the queue instance itself.

The Many Methods
----------------

``queue.push_many()`` and ``queue.pull_many()`` exist as utilities to help when you want to push or pull multiple objects to/from the queue. ``push_many()`` is relatively easy to understand; specify each object as an argument, and it will result in repeated calls to ``push()`` with each of those objects in the order they were supplied. When using a queue from memory, this does not represent a time advantage, but when using the server (see below), it's a good way to save time and bandwidth that would have been spent on multiple networked calls to ``push()``.

``queue.pull_many()`` has slightly different semantics. ``pull_many()`` accepts a single positional argument (let's call it ``n``) with the number of items to ``pull()``, and an optional ``timeout`` keyword argument. By default, this timeout is ``None``, which means the method will block until at least ``n`` objects are ready to be returned. However, if you specify another timeout (such as a zero timeout), then the method will attempt to retrieve as many items as possible, up to ``n``, with that timeout for each individual ``pull()``. If the very first call to ``pull()`` times out, then a ``Queue.Timeout`` exception is raised from the method. If, however, it manages to retrieve only a few items (i.e. less than ``n`` items), it will return everything it could ``pull()``. 

This was a deliberate design decision; it allows you to do things like ``pull_many(1024, timeout=0)``, which will retrieve a maximum of 1024 items. Since you might also want to retrieve the entire contents of the queue, you can provide ``None`` as the number of items to fetch, and the method will just return everything it can ``pull()`` without a timeout. For example, ``pull_many(None, timeout=0)`` will grab the entire contents of the queue, emptying the queue at the same time. Another trick is to specify ``None`` with no timeout; this causes the coroutine which called ``pull_many()`` to act as a 'null consumer' (much like the special ``/dev/null`` file on UNIX systems). Every message sent to the queue will be consumed by the calling coroutine, but since it will always block and never return, it acts as a 'black hole'. Because this will attempt to accrue a large number of items in a temporary list in memory, ZenQueue implements a shortcut for these null consumers.

Running a Queue Server
======================

ZenQueue can also run remotely via TCP; it's quite fast at doing so, because it uses an incredibly simple JSON-based socket-level protocol. Essentially, this protocol is client-platform-agnostic (although a client only exists for Python right now). To run a server, you can do the following from the command line::
    
    username@host$ python -m zenqueue.server

For some help, type::
    
    username@host$ python -m zenqueue.server --help

I've even made it print some pretty logging information so that you know exactly what it's doing. The server itself uses `asynchronous IO <http://en.wikipedia.org/wiki/Asynchronous_I/O>`_, facilitated by the Eventlet library and coroutine-based implementation. This means that there are no issues raised by having multiple clients connected in parallel, because coroutines provide inherent mutual exclusion (as would be obtained by threads) coupled with relatively huge improvements in performance when under concurrent load.

Connecting to a Queue Server
============================

Using the client library, you can connect to a ZenQueue server. The client also uses Eventlet for networking, so you can run multiple clients in tandem (using coroutines) and reap the benefits of asynchronous IO. You'll get a fair amount of logging output, too. To use the client, you can do something like this::
    
    >>> from zenqueue.client import QueueClient
    >>> c = QueueClient(host='127.0.0.1', port=3000)
    >>> c.push('a')
    >>> c.pull()
    u'a'
    >>> c.push_many('a', 'b', 'c')
    >>> c.pull_many(3)
    [u'a', u'b', u'c']

The reason why the messages came back as a Unicode strings is because the simplejson library for Python is Unicode-aware (as such, so is the ZenQueue server). Since JSON is the format of choice for data interchange with the ZenQueue server, content is passed around as Unicode. A rule of thumb is that you can send and receive any Python object over the network that can be serialized to JSON (via the simplejson library, and without custom decoder hooks).

The Protocol
------------

The protocol itself is an ad-hoc form of Remote Procedure Call, with the client sending a request for an action to be performed (and, optionally, some positional and keyword arguments) and the server either returning a value (indicating success) or an error (which will be raised on the client side). A lot of the concept behind it originally stems from HTTP's 'send request with method, get response with status' architecture. This is because I was originally planning on implementing the server using WSGI (but then decided against it when I realised what an impact it would have on performance). I'm sure it would be possible, if not easy, to build a HTTP front-end to ZenQueue.

Benchmarks
==========

In the benchmarks I've run personally, ZenQueue has come out as incredibly fast (using the TCP server). I was able to send, and then receive, one million messages to/from one server at an average rate of 300k (300 thousand) messages per second (calculated as one million divided by the time it took to send and then receive all the messages). From the producer or consumer side, running in parallel, it looks a lot more like 600k messages per second, because each involves only one leg of the process. Although a big **FAT** disclaimer: **Your Mileage May Vary** (**YMMV**). The code I used to do the benchmarking can be found in the benchmark.py file. I was grouping the messages together into single requests; this multiplexing might not be feasible in every scenario, but it does increase the speed greatly.

Managing Multiple Queues, and Other Sophisticated Activities
============================================================

At the moment, ZenQueue doesn't support running multiple queues from the same server, and I doubt it ever will. If you need to run several queues at once, you can just run multiple server instances on different ports. If you want it to support things like routing keys, durability, fanout and direct exchanges and binding, et cetera, then you're also out of luck. There's a reason why I chose to focus on simplicity with this library; if you need a fully-fledged message queueing server with bells and whistles, I suggest you go with an `AMQP <http://www.amqp.org/>`_-based solution like `RabbitMQ <http://www.rabbitmq.com/>`_ (which I use myself and heartily recommend).

Downloading and Installation
============================

You can download and install this library in a few ways:

    1. Clone a copy of this repo from github and just run ``python setup.py install`` from the root directory.
    2. Run ``easy_install ZenQueue`` from the command line; this will automatically fetch and install the latest version.
    3. Download the tarball `here <http://github.com/disturbyte/zenqueue/tarball/master>`_, extract it and run ``python setup.py install`` from the root directory.

License
=======

This software is licensed under the following MIT-style license:

    Copyright (c) 2009 Zachary Voase

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.

Plans for the Future
====================

My primary priority right now is to keep this library working fully in its current state, optimizing performance in certain areas perhaps, but for the most part maintaining stability. I also plan on building a couple of variations of ZenQueue; most notably a 'ZenStack' (I'm sure you can probably guess what that'll do) and a 'ZenDeque' (a dual queue/stack). I'm also planning on building a synchronous, single-socket client library.

Author
======

Zachary Voase can be found on `Twitter <http://twitter.com/disturbyte>`_, or at his `personal website <http://disturbyte.github.com>`_.
