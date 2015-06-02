Aurora Redis lets you set up a redis cluster that consists of one master and several slaves.
If the master goes down, another nodes get elected as master, and the other slaves are pointed to the new master.
Every time Redis does a database dump, this dump gets copied to HDFS. Also, if there's no available Master / you're bootstrapping the Cluster, the dump is copied over from HDFS and the cluster is started from that.
For writing clients can fetch the current redis master via zookeeper. For reading you could either use the normal serverset that's done by aurora, or you could use a proxy (e.g. HAProxy) that get's populated by the serverset.

## What it does
- The Job consists of 4 processes: copy,run,backup,election
- Copy is run first, it fetches the redis binary and the python helper script to the sandbox
- Run, Backup & Election are run in parallel after that
- Election: is trying to get the current state of the cluster. If it has a state, the flag file "running" is created. If the current instance is going to be the Master one, also the flag file "isMaster" is created
- Run: is waiting for the flag file "running" before it starts the redis server. If the flag file "isMaster" is found, it tried to fetch the latest redis dump from HDFS before starting the server
- Backup: this is only active when the flag file "isMaster" is found, it then watches if there's a new "dump.rdb". If there is one, copy it to HDFS


## Before you start
- There are a lot of hardcoded "hdfs://hdfscluster/path/to/redis" values in the .aurora file, you should change them before you use it
- You need to copy a redis-server binary to the HDFS path mentioned above
- You need to define the zookeeper cluster you're going to use. You can either edit it in the redis_electory.py file, or you can set the "zk_hosts" ENV in the .aurora file

## ToDo
- It's rather crude right now, a lot of hardcoded values and usage of flag files seem to be bad as well
- Right now the zookeeper entry is in the form of "ip:port", it probably makes sense to switch to the serverset format that aurora is already using
- The local ip address is fetched via $(ifconfig bond0 |  grep "inet addr" | awk -F: '{print $2}' | awk '{print $1}') ... there has to be a better way :)
