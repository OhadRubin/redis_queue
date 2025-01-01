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





# connects to leader and listens for commands
def follower_loop(leader_ip: str):
    while True:
        try:
            context = zmq.Context()
            socket = context.socket(zmq.SUB)
            socket.connect(f"tcp://{leader_ip}:5554")
            socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
            message = socket.recv_string()
            break
            # we only receive the command once the leader finishes
        except Exception as e:
            time.sleep(1)


# python3.10 -m src.multi_system finish
def finish():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:5554")
    # Give time for subscribers to connect
    time.sleep(1)
    socket.send_string("finish")
    socket.close()
    
# python3.10 -m src.barrier start
# only the leader passes the barrier, the rest wait for the leader to finish
def start(zone: str="us-central2-b"):
    _, leader_ip, my_ip = ip_addr(zone)
    if my_ip != leader_ip:
        follower_loop(leader_ip)
    
    
if __name__ == "__main__":
    fire.Fire()
