===============
ZenQueue v0.1.1
===============

ZenQueue is an incredibly simple message queueing system. It was designed as an experiment, but the author thought it was pretty neat and powerful and decided to release it to the world at large.

Requirements
============

In order to run ZenQueue, you're going to need the fantastic `Eventlet <http://wiki.secondlife.com/wiki/Eventlet>`_ library, and at least Python 2.4. I tried to write this to be as portable as possible, but there may be some issues (I don't exactly have many systems to test this out on). You'll also need the `simplejson <http://pypi.python.org/pypi/simplejson/>`_ library if you want to run the ZenQueue server.

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

The queue itself is managed not by threads and locks, but by coroutines. If you don't know what they are, or don't understand them, then the introductory material out there is probably far better than what I could ever attempt to reproduce; however, I will tell you that they're awesome, and that they solve a multitude of issues that are difficult to get around with traditional threads.

If you want to run things in parallel that use the same queue, rather than using ``threading.Thread``, you should use the helpful functions and classes provided in ``eventlet.api`` and ``eventlet.coros``. Consult the `Eventlet documentation <http://wiki.secondlife.com/wiki/Eventlet/Documentation>`_ for more information on these; I really can't afford to be brief on them here (you need the thorough walkthrough).

Running a Queue Server
======================

ZenQueue can also run remotely via TCP; it's quite fast at doing so, because it uses an incredibly simple JSON-based socket-level protocol. Essentially, this protocol is client-platform-agnostic (although a client only exists for Python right now). To run a server, you can do the following from the command line::
    
    username@host$ python -m zenqueue.server

For some help, type::
    
    username@host$ python -m zenqueue.server --help

I've even made it print some pretty logging information so that you know exactly what it's doing.

Connecting to a Queue Server
============================

Using the client library, you can connect to a ZenQueue server. The client also uses Eventlet for networking, so you can run multiple clients in tandem (using coroutines) and reap the benefits of `asynchronous I/O <http://en.wikipedia.org/wiki/Asynchronous_I/O>`_. To use the client, you can do something like this::
    
    >>> from zenqueue.client import QueueClient
    >>> c = QueueClient(host='127.0.0.1', port=3000)
    >>> c.push('a')
    >>> c.pull()
    u'a'

The reason why that last one came back as a Unicode string is because the simplejson library for Python is Unicode-aware (as such, so is the ZenQueue server). Since JSON is the format of choice for data interchange with the ZenQueue server, content is passed around as Unicode. It's also a rule that you can, over the network, send and receive any Python object that can be serialized to JSON via the simplejson library (without custom decoder hooks).

Benchmarks
==========

In the benchmarks I've run personally, ZenQueue has come out as incredibly fast (using the TCP server). I was able to send, and then receive, one million messages to/from one server at an average rate of 28k (28 thousand) messages per second (calculated as one million divided by the time it took to send and then receive all the messages). From the producer or consumer side, running in parallel, it looks a lot more like 56k messages per second, because each involves only one leg of the process. Although a big **FAT** disclaimer: **Your Mileage May Vary** (**YMMV**). The code I used to do the benchmarking can be found in the benchmark.py file.

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

Author
======

Zachary Voase can be found on `Twitter <http://twitter.com/disturbyte>`_, or at his `personal website <http://disturbyte.github.com>`_.
