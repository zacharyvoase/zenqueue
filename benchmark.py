#! /usr/bin/env python
# -*- coding: utf-8 -*-
# It's a far cry from 'elegant', but it gets the job done.

import time
from zenqueue import client
from zenqueue import log
log.ROOT_LOGGER.setLevel(log.ERROR)

MESSAGES = 1000000 # 1,000,000 (1 million) messages will be sent in total.
UNIT_SIZE = 10000 # Each request will contain 10,000 (10 thousand) messages.
UNIT = [u'a'] * UNIT_SIZE

# Assumes that the server is running on localhost:3000
c = client.QueueClient()

start_time = time.time()

for i in xrange(MESSAGES / UNIT_SIZE):
    c.push_many(*tuple(UNIT))

for j in xrange(MESSAGES / UNIT_SIZE):
    assert (c.pull_many(UNIT_SIZE, timeout=0) == UNIT)

end_time = time.time()

c.close()

time_taken = end_time - start_time

print '%d Messages transferred' % (MESSAGES,)
print 'Time taken: %0.4f seconds' % (time_taken,)
print 'Average: %0.4f messages/second' % (MESSAGES / time_taken,)
