#! /usr/bin/env python
# -*- coding: utf-8 -*-

import optparse
import time

from zenqueue.client.native import QueueClient
from zenqueue import log


option_parser = optparse.OptionParser(
    usage='%prog [options]', version='0.1')

option_parser.add_option('-a', '--address', metavar='ADDR',
    default='127.0.0.1:3000',
    help='Contact server on address ADDR [default %default]')

option_parser.add_option('-l', '--log-level', metavar='LEVEL', default='SILENT',
    help='Set logging level to LEVEL [default %default]')

option_parser.add_option('-n', '--num-messages', metavar='COUNT',
    default=1000000, type='int',
    help='Send/receive COUNT messages in total [default %default]')

option_parser.add_option('-u', '--unit-size', metavar='SIZE', default=10000,
    type='int',
    help='Send/receive messages in batches of SIZE [default %default]')

option_parser.add_option('-m', '--message', metavar='MESSAGE', default='a',
    help='Send/receive message MSG [default "%default"]')

option_parser.add_option('-s', '--synchronous', action='store_true',
    default=False,
    help='Use synchronous transfer mode [default asynchronous]')


def main():
    options, args = option_parser.parse_args()

    # Set logging level
    if options.log_level.upper() == 'SILENT':
        log.silence()
    else:
        log.set_level(options.log_level.upper())

    # Build address
    split_addr = options.address.split(':')
    if len(split_addr) == 1:
        host, port = split_addr[0], 3000
    elif len(split_addr) == 2:
        host, port = split_addr[0], int(split_addr[1])
    else:
        print 'Invalid address specified; defaulting to 127.0.0.1:3000'
        host, port = '127.0.0.1', 3000
    
    # Build message unit
    message = options.message.decode('utf-8')
    unit = [message] * options.unit_size
    message_count = options.num_messages
    
    # Configure mode (sync/async).
    mode = 'async'
    if options.synchronous:
        mode = 'sync'
    
    client = QueueClient(mode=mode, host=host, port=port)

    start_time = time.time()

    while message_count > 0:
        client.push_many(*tuple(unit))
        assert (client.pull_many(options.unit_size, timeout=0) == unit)
        message_count -= options.unit_size

    end_time = time.time()
    
    client.close()
    
    time_taken = end_time - start_time
    
    print '%d messages transferred in chunks of %s' % (options.num_messages,
                                                       options.unit_size)
    print 'Time taken: %0.4f seconds' % (time_taken,)
    print 'Average speed: %0.4f messages/second' % (
        options.num_messages / time_taken,)


if __name__ == '__main__':
    main()