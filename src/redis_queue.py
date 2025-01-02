"""
Redis-based queue implementation supporting:
- Job scheduling with dependencies
- Worker tracking and job status management  
- Job persistence and recovery
- Distributed worker coordination

"""
from typing import Any
import os
import uuid
from datetime import datetime
import pickle
import requests
import socket
from collections import Counter
import fire

import time
from src.logging_utils import init_logger
import tqdm
import uuid
import threading
from src.client import get_client
logger = init_logger()

def get_ip():
    return requests.get('https://checkip.amazonaws.com').text.strip()

# python3.10 -m src.redis_queue run_queue --worker_name=worker_name --process_func=process_func --sleep_time=3 --set_heatbeat=True
# python3.10 -m src.redis_queue run_queue
@logger.catch
def run_queue(worker_name=None,
              process_func=None,
              sleep_time:int=3,
              set_heatbeat:bool = True,
              exit_on_empty:bool = False,
              queue_name:str = "default"
              ):
    logger.info(f"Starting worker")
    if process_func is None:
        process_func = os.system
    if worker_name is None:
        worker_name = str(uuid.uuid4())
    queue = RedisQueue(worker_name=worker_name, name=queue_name)
    while True:
        job = queue.get(timeout=240,return_job=True)
        if job is not None:
            logger.info(f" Starting Job: {job.__dict__}")
            data = job.data
            if set_heatbeat:
                job.last_heartbeat = datetime.utcnow()
            queue.set_job(job)
            if set_heatbeat:
                sentry = threading.Event()
                def heartbeat():
                    while not sentry.is_set():
                        time.sleep(10)  # Update every 60 seconds
                        job.last_heartbeat = datetime.utcnow()
                        queue.set_job(job)
                heartbeat_thread = threading.Thread(target=heartbeat)
                heartbeat_thread.start()
                    
            return_code = process_func(data)
            # Check if the command failed
            if set_heatbeat:
                sentry.set()
                heartbeat_thread.join()
            if return_code != 0:
                logger.error(f"Job {job.id} failed with return code {return_code}")
                queue.update_job_status(job.id, "failed", result=f"Failed with return code {return_code}")
            else:
                queue.finalize_job(job.id)
                try:
                    logger.success(f"Job finished successfully: job: {job.__dict__} ")
                except:
                    
                    logger.success(f"Job finished successfully.")
            
        if exit_on_empty and queue.empty():
            logger.success(f"Queue is empty. Exiting.")
            break
        time.sleep(sleep_time)


import dataclasses


class Job:
    def __init__(self, data: Any):
        self.id = str(uuid.uuid4())
        self.data = data
        self.status = "queued"
        self.result = None
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.finished_at = None
        self.hostname = None
        self.host_ip = None
        self.last_heartbeat = None


class Bookkeeping:
    """Handles worker-job mapping and tracking in Redis"""
    
    def __init__(self, db, mapping_hash):
        # Store Redis client and mapping hash prefix
        self._db = db
        self._mapping_hash = mapping_hash

    def update_mapping(self, job, worker_name):
        # Map both worker name and hostname to job ID
        self._db.set(f"{self._mapping_hash}:{worker_name}", job.id)
        self._db.set(f"{self._mapping_hash}:{job.hostname}", job.id)

    def get_last_job_id(self, worker_name):
        # Get job ID for worker from Redis, decode bytes to string
        job_id_bytes = self._db.get(f"{self._mapping_hash}:{worker_name}")
        if job_id_bytes is not None:
            job_id = job_id_bytes.decode('utf-8')
            return job_id
        else:
            return None
    def get_last_job_id_by_hostname(self, hostname):
        job_id_bytes = self._db.get(f"{self._mapping_hash}:{hostname}")
        if job_id_bytes is not None:
            job_id = job_id_bytes.decode('utf-8')
            return job_id
        else:
            return None
    def clear(self):
        self._db.delete(self._mapping_hash)


class RedisQueue:
    """Redis-backed queue with job scheduling and worker coordination"""

    def __init__(self, name: str="default", worker_name: str = None):
        # Initialize Redis connection and queue settings
        self._db = get_client()
        self._name = name
        self.bookkeeping_mapping_hash = f"{self._name}:worker_job_mapping"
        if worker_name is not None:
            self.worker_name = worker_name
        self.bookkeeping = Bookkeeping(self._db, self.bookkeeping_mapping_hash)
        
    def get(self, timeout=None, return_job=False,):
        # Pop and deserialize next job from queue
        item = self._db.blpop(self._name, timeout=timeout)
        if item:
            job = pickle.loads(item[1],encoding="utf-8")
            if self.worker_name is not None:
                # Handle previous job completion if needed
                last_job_id = self.bookkeeping.get_last_job_id(self.worker_name)
                if last_job_id and last_job_id != job.id:
                    self.finalize_job(last_job_id)
            self.set_started_job(job)
            if return_job:
                return job
            else:
                return job.data
        else:
            return None

    def put(self, item: Any, depends_on=None):
        # Create and store new job
        job = Job(data=item)
        self.set_job(job)
        
        if depends_on is None:
            # Add job directly to queue if no dependencies
            self._db.rpush(f"{self._name}:queue", pickle.dumps(job))
        else:
            # Track job dependencies
            self._db.incrby(f"{self._name}:deferred_jobs", 1)
            if not isinstance(depends_on, list):
                depends_on = [depends_on]
            for depends_on_id in depends_on:
                self._db.rpush(f"{self._name}:dependents:{depends_on_id}", job.id)
            self._db.incrby(f"{self._name}:dependencies_counter:{job.id}", amount=len(depends_on))
        return job.id
    
    def finalize_job(self, job_id):
        # Mark job as complete and handle dependent jobs
        job = self.get_job(job_id)
        if job and job.status != 'finished':
            job.status = 'finished'
            job.finished_at = datetime.utcnow()
            self.set_job(job)
            
            # Process dependent jobs
            # Iterates over the elements in the Redis list `dependents_{job_id}`.
            for dependent_id in self._db.lrange(f"{self._name}:dependents:{job_id}", 0, -1):
                dependent_id = dependent_id.decode('utf-8')
                dependent_key = f"{self._name}:dependencies_counter:{dependent_id}"
                # Decrements the integer value stored at `dependent_key`.
                self._db.decr(dependent_key)
                
                # Queue dependent job if all dependencies met
                if int(self._db.get(dependent_key))==0:
                    self._db.decr(f"{self._name}:deferred_jobs")
                    dependent_job = self._db.get(f"{self._name}:jobs:{dependent_id}")
                    self._db.rpush(f"{self._name}:queue", dependent_job)

    def put_list(self, items: list):
        for item in items:
            self.put(item)

    def set_job(self, job):
        idx = f"{self._name}:jobs:{job.id}"
        self._db.set(idx, pickle.dumps(job))

    def get_job(self, job_id):
        idx = f"{self._name}:jobs:{job_id}"
        job_str = self._db.get(idx)
        if job_str:
            return pickle.loads(job_str)
        else:
            return None
        

    def set_started_job(self, job):
        job.status = "started"
        job.started_at = datetime.utcnow()
        job.hostname = socket.gethostname()
        job.host_ip = get_ip()
        self.set_job(job)
        if self.bookkeeping is not None:
            self.bookkeeping.update_mapping(job, self.worker_name)
            
    def qsize(self):
        if self._db.get(f"{self._name}:deferred_jobs") is not None:
            return self._db.llen(f"{self._name}:queue")+int(self._db.get(f"{self._name}:deferred_jobs"))
        else:
            return self._db.llen(f"{self._name}:queue")

    def empty(self):
        return self.qsize() == 0

    def update_job_status(self, job_id, status, result=None):
        job = self.get_job(job_id)
        if job:
            job.status = status
            job.result = result
            if status == "finished":
                job.finished_at = datetime.utcnow()
            self.set_job(job)

    def get_job_status(self, job_id):
        job = self.get_job(job_id)
        if job:
            return job.status
        return None

    def get_all_jobs(self):
        all_jobs = []
        
        for key in self._db.keys(f"{self._name}:jobs:*"):
            job_id = key.decode('utf-8').split(":")[-1]
            all_jobs.append(self.get_job(job_id))
        return all_jobs
    
    def get_all_workers(self):
        workers = []
        for key in self._db.keys(f"{self.bookkeeping_mapping_hash}:*"):
            worker_name = key.decode('utf-8').split(":")[-1]
            last_job_id = self._db.get(key).decode('utf-8')
            job = self.get_job(last_job_id)
            workers.append({"name":worker_name, **job.__dict__})
        return workers

    def clear(self):
        for key in self._db.keys(f"{self._name}:*"):
            self._db.delete(key)
            
    def n_jobs(self):
        return len(self._db.keys(f"{self._name}:jobs:*"))
    
    def requeue_job(self, job_id):
        """Reset job state and requeue for retry"""
        job = self.get_job(job_id)
        if job is not None and job.status == "started":
            # Reset job metadata
            job.status = "queued"
            job.started_at = None
            job.finished_at = None
            job.hostname = None
            job.host_ip = None
            job.last_heartbeat = None
            
            # Store updated job and add back to queue
            self.set_job(job)
            self._db.lpush(f"{self._name}:queue", pickle.dumps(job))
            logger.info(f"Requeued job {job.__dict__}")
            return True
        return False

def enqueue_from_file(filename:str):
    queue = RedisQueue()
    with open(filename, "r") as f:
        lines = f.readlines()
        for line in tqdm.tqdm(lines):
            print(line.strip())
            queue.put(line.strip())



def counter():
    queue = RedisQueue()
    print(Counter(job.status for job in queue.get_all_jobs()))

# python3.10 -m src.redis_queue n_jobs
def n_jobs():
    queue = RedisQueue()
    print(queue.n_jobs())
# python3.10 -m src.redis_queue list_keys
def list_keys():
    queue = RedisQueue()
    print(len(list(queue._db.keys("*"))))

#python3.10 -m src.redis_queue purge
def purge():
    counter()
    queue = RedisQueue()
    queue.clear()
    print("Purged all jobs from Redis queue.")

    
#python3.10 -m src.redis_queue requeue_loop
from datetime import timedelta
def requeue_loop(name:str="default"):
    logger.info(f"Starting requeue loop")
    queue = RedisQueue(name=name)
    while True:
        # iterate over all workers
        # if a worker has not sent a heartbeat in the last minute  requeue the job
        all_workers = list(queue.bookkeeping.get_all_workers())
        now = datetime.utcnow()
        for job_id in all_workers :
            if job_id.last_heartbeat is None: # worker has not started yet
                continue
            if job_id.last_heartbeat < now - timedelta(minutes=1):
                queue.requeue_job(job_id)   
                logger.info(f"Worker {job_id.hostname} has not sent a heartbeat in the last minute. Requeueing.")
            else:
                logger.debug(f"Worker {job_id.hostname} has sent a heartbeat in the last minute. Skipping.")


#python3.10 -m src.redis_queue requeue_subscriber
def requeue_subscriber():
    import zmq
    import json
    logger.info(f"Starting requeuing subscriber")
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://localhost:5559")
    socket.connect(f"tcp://localhost:5560")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")
    queue = RedisQueue()
    while True:
        message = socket.recv().decode()
        inc_tpu_name, old_state, new_state = json.loads(message)
        if new_state in ["SUSPENDING", "SUSPENDED", "PREEMPTED", "FAILED"]:
            job_id = queue.bookkeeping.get_last_job_id_by_hostname(inc_tpu_name)
            queue.requeue_job(job_id)

if __name__ == '__main__':
    fire.Fire()



