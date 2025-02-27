"""
Multi-system coordination module for distributed TPU VM operations.

This module provides functionality for coordinating commands across multiple TPU VM instances
using ZeroMQ for communication. It handles leader-follower topology setup, command distribution,
and synchronization between nodes.

Key functions:
- ip_addr(): Gets IP addresses and determines leader node
- get_leader_ip(): Returns the leader node's IP address  
- init(): Initializes node as leader or follower
- send_cmd(): Sends commands to be executed across nodes
- follower_loop(): Runs command listener loop on follower nodes

Usage:
    # Initialize nodes:
    python3.10 -m src.multi_system init
    
    # Send command to all nodes:
    python3.10 -m src.multi_system send_cmd --cmd="echo hello"
"""

import zmq
import os
import subprocess
import json
from src.redis_queue import run_queue
import fire
import time

def ip_addr(zone: str):
    hostname = os.uname().nodename
    DESCRIBE = "gcloud alpha compute tpus tpu-vm describe {hostname}  --zone {zone} --format json"
    res = subprocess.getoutput(DESCRIBE.format(hostname=hostname, zone=zone))
    addr_list = []
    for endpoint in json.loads(res)['networkEndpoints']:
        ip_address = endpoint["accessConfig"]['externalIp']
        addr_list.append(ip_address)
    my_ip =  subprocess.getoutput("curl https://checkip.amazonaws.com").split("\n")[-1]
    sorted_addr_list = sorted(addr_list)
    leader_ip = sorted_addr_list[0]
    return sorted_addr_list, leader_ip, my_ip




# python3.10 -m src.multi_system send_cmd --cmd="echo hello"
def send_cmd(cmd: str):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:5555")
    # Give time for subscribers to connect
    time.sleep(1)
    
    socket.send_string(cmd)
    return_value = os.system(cmd)
    os.system("python3.10 -c \"import jax; from jax.experimental.multihost_utils import sync_global_devices; sync_global_devices('bla'); print(jax.process_index())\" ")
    socket.close()
    return return_value
    
# connects to leader and listens for commands
def follower_loop(leader_ip: str):
    print(f"Follower connected to leader at {leader_ip}")
    
    while True:
        try:
            context = zmq.Context()
            socket = context.socket(zmq.SUB)
            socket.connect(f"tcp://{leader_ip}:5555")
            socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
            message = socket.recv_string()
            print(f"Received command: {message}")
            os.system(message)
            os.system("python3.10 -c \"import jax; from jax.experimental.multihost_utils import sync_global_devices; sync_global_devices('bla'); print(jax.process_index())\" ")
            # print("Synced devices, waiting for next command")
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)


# python3.10 -m src.multi_system init
def init(zone: str="us-central2-b"):
    other_ips, leader_ip, my_ip = ip_addr(zone)
    if my_ip != leader_ip:
        while True:
            follower_loop(leader_ip)
    else:
        queue_name = f"v4-{str(8*len(other_ips))}"
        run_queue(process_func=send_cmd, queue_name=queue_name)
    
    
if __name__ == "__main__":
    fire.Fire()
