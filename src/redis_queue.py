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

@logger.catch
def run_queue(worker_name=None,
              process_func=None,
              sleep_time:int=3,
              set_heatbeat:bool = True
              ):
    logger.info(f"Starting worker")
    if process_func is None:
        process_func = os.system
    if worker_name is None:
        worker_name = str(uuid.uuid4())
    queue = RedisQueue(worker_name=worker_name)
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
            
        if queue.empty():
            logger.success(f"Queue is empty. Exiting.")
            break
        time.sleep(sleep_time)



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
    def __init__(self, db, mapping_hash):
        self._db = db
        self._mapping_hash = mapping_hash

    def update_mapping(self, job, worker_name):
        self._db.set(f"{self._mapping_hash}_{worker_name}", job.id)
        self._db.set(f"{self._mapping_hash}_{job.hostname}", job.id)
        # self._db.set(f"{self._mapping_hash}_{worker_name}", job_id)

    def get_last_job_id(self, worker_name):
        job_id_bytes = self._db.get(f"{self._mapping_hash}_{worker_name}")
        if job_id_bytes is not None:
            job_id = job_id_bytes.decode('utf-8')
            return job_id
        else:
            return None
    def get_last_job_id_by_hostname(self, hostname):
        job_id_bytes = self._db.get(f"{self._mapping_hash}_{hostname}")
        if job_id_bytes is not None:
            job_id = job_id_bytes.decode('utf-8')
            return job_id
        else:
            return None
    def clear(self):
        self._db.delete(self._mapping_hash)


class RedisQueue:
    def __init__(self, name: str="default", worker_name: str = None):
        url = os.environ.get("REDIS_URL", None)
        if url is None:
            raise ValueError("REDIS_URL is not set")
        self._db = get_client()
        # self._db = redis.Redis.from_url(url)
        self._name = name
        self.bookkeeping_mapping_hash = f"{name}_worker_job_mapping"
        if worker_name is not None:
            self.worker_name = worker_name
        self.bookkeeping = Bookkeeping(self._db, self.bookkeeping_mapping_hash)
        
    def get(self, timeout=None, return_job=False,):
        item = self._db.blpop(self._name, timeout=timeout)
        if item:
            job = pickle.loads(item[1],encoding="utf-8")
            if self.worker_name is not None:
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
        job = Job(data=item)
        self.set_job(job)
        if depends_on is None:
            self._db.rpush(self._name, pickle.dumps(job))
        else:
            self._db.incrby("deferred_jobs", 1)  
            if not isinstance(depends_on, list):
                depends_on = [depends_on]
            for depends_on_id in depends_on:
                self._db.rpush(f"dependents_{depends_on_id}", job.id)
            self._db.incrby(f"dependencies_counter_{job.id}", amount=len(depends_on))
        return job.id
    
    def finalize_job(self, job_id):
        job = self.get_job(job_id)
        if job and job.status != 'finished':
            job.status = 'finished'
            job.finished_at = datetime.utcnow()
            self.set_job(job)
            for dependent_id in self._db.lrange(f"dependents_{job_id}", 0, -1):
                dependent_id = dependent_id.decode('utf-8')
                dependent_key = f"dependencies_counter_{dependent_id}"
                self._db.decr(dependent_key)
                if int(self._db.get(dependent_key))==0:
                    self._db.decr("deferred_jobs")
                    dependent_job = self._db.get(f"jobs_{dependent_id}")
                    self._db.rpush(self._name, dependent_job)        

    def put_list(self, items: list):
        for item in items:
            self.put(item)

    def set_job(self, job):
        idx = f"jobs_{job.id}"
        self._db.set(idx, pickle.dumps(job))

    def get_job(self, job_id):
        idx = f"jobs_{job_id}"
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
        if self._db.get("deferred_jobs") is not None:
            return self._db.llen(self._name)+int(self._db.get("deferred_jobs"))
        else:
            return self._db.llen(self._name)

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
        
        for key in self._db.keys(f"jobs_*"):
            job_id = key.decode('utf-8').split("_")[1]
            all_jobs.append(self.get_job(job_id))
        return all_jobs
    
    def get_all_workers(self):
        workers = []
        for key in self._db.keys(f"{self.bookkeeping_mapping_hash}_*"):
            worker_name = key.decode('utf-8').split("_")[-1]
            last_job_id = self._db.get(key).decode('utf-8')
            job = self.get_job(last_job_id)
            workers.append({"name":worker_name, **job.__dict__})
        return workers

    def clear(self):
        for key in self._db.keys(f"*"):
            self._db.delete(key)
            
    def n_jobs(self):
        return len(self._db.keys(f"jobs_*"))
    
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

def n_jobs():
    queue = RedisQueue()
    print(queue.n_jobs())
def list_keys():
    queue = RedisQueue()
    print(len(list(queue._db.keys("*"))))

#python3.10 -m src.redis_queue purge
def purge():
    counter()
    queue = RedisQueue()
    queue.clear()
    print("Purged all jobs from Redis queue.")
    
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
        if new_state == "SUSPENDING" or new_state == "SUSPENDED" or new_state=="PREEMPTED" or new_state == "FAILED":
            job_id = queue.bookkeeping.get_last_job_id_by_hostname(inc_tpu_name)
            job = queue.get_job(job_id)
            if job is not None and job.status == "started":
                job.status="queued"
                job.started_at = None
                job.finished_at = None
                job.hostname = None
                job.host_ip = None
                job.last_heartbeat = None
                queue.set_job(job)
                queue._db.lpush(queue._name, pickle.dumps(job))
                logger.info(f"Requeued job {job.__dict__}")

if __name__ == '__main__':
    fire.Fire()



