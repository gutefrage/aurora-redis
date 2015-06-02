#!/usr/bin/env python
"""
redis_elector
- uses Kazoo Election method to find a Redis master and configures the slaves to replicate from it.
"""


from time import sleep
import os
import sys
import signal

import redis
from kazoo.client import KazooClient
from kazoo.client import KazooState


reconnect_time = 10
reconnected = True
master = False

redis_host = os.getenv('redis_host', "127.0.0.1")
redis_port = os.getenv('redis_port', "6639")
redis_address = redis_host + ":" + redis_port

zk_base = os.getenv('zk_base', "/redis")
zk_hosts = os.getenv('zk_hosts', "zookeeper:2181")
zk_path_to_master = zk_base + "/master"

def signal_handler(signal, frame):
    global zk_connection
    print('Processing signal. Shutting down...')
    # Let's try to close the zk connection so that our ephemeral node gets freed faster
    zk_connection.remove_listener(zookeeper_listener)
    zk_connection.stop()
    sys.exit(0)

def zookeeper_listener(state):
    global reconnected

    if state == KazooState.LOST or state == KazooState.SUSPENDED:
        # Register somewhere that the session was lost or being disconnected from Zookeeper
        print "Connection lost, retrying in %d seconds" % reconnect_time
        sys.stdout.flush()
        sleep(reconnect_time)

    else:
        # Handle being connected/reconnected to Zookeeper
        print "Reconnected to Zookeeper!"
        sys.stdout.flush()
        reconnected = True


def zookeeper_watcher(zk_connection):
    @zk_connection.DataWatch(zk_path_to_master)
    def watcher(data, stat, event):
        if data != None and (event == None or event.type == "CHANGED"):
            if data == redis_address:
                # Create Master flag file before running flag file
                touch("isMaster")
                # At this point make sure that the flag file really exists
                touch("running")

                print "Unsetting possible slave config"
                sys.stdout.flush()
                set_redis_slave(None, None)

            else:
                touch("running")
                redis_address_parts = data.split(':')

                if os.path.exists("isMaster"):
                    print "Master flag file found, deleting..."
                    os.remove("isMaster")

                print "Set Master to %s on port %s " % (redis_address_parts[0], redis_address_parts[1])
                set_redis_slave(redis_address_parts[0], redis_address_parts[1])
                sys.stdout.flush()



def start_election_and_take_position():
    global reconnected
    while True:
        if reconnected:
            reconnected = False

            zookeeper_watcher(zk_connection)

            election = zk_connection.Election(zk_base + "/lockpath")

            # Slaves stop at this point, idling the zk connection, waiting for zk.DataWatch.
            # Master continues...
            election.run(set_redis_master)

        sleep(10)


def set_redis_master():
    global master
    master = True

    print "I am taking the crown! (Elected master...) "
    sys.stdout.flush()
    zk_connection.ensure_path(zk_base)

    # Should never be necessary, just to be sure.
    if zk_connection.exists(zk_path_to_master):
        zk_connection.delete(zk_path_to_master)

    zk_connection.create(zk_path_to_master, ephemeral=True)
    zk_connection.set(zk_path_to_master, redis_address)

    # Sleeping forever, idling the zk connection, waiting for zk.DataWatch
    while True:
        if reconnected:
            return

        sleep(10)


def set_redis_slave(tHost, tPort):
    success = False
    timeout = 120
    retry_time = 5

    while success != True:
        try:
            redis_connection.slaveof(host=tHost, port=tPort)
            success = True
        except redis.ConnectionError:
            if timeout <= 0:
                raise OSError, "Timeout reached. Couldn't connect to Redis."
            print "Can't connect to Redis. Sleeping for %d seconds..." % retry_time
            sys.stdout.flush()
            timeout += retry_time
            sleep(retry_time)


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print "Redis %s %s" % (redis_host, redis_port)
sys.stdout.flush()
redis_connection = redis.StrictRedis(host=redis_host, port=redis_port, db=0)

zk_connection = KazooClient(hosts=zk_hosts)
zk_connection.add_listener(zookeeper_listener)
zk_connection.start()

start_election_and_take_position()
