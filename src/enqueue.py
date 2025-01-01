import fire
from src.redis_queue import RedisQueue

def enqueue(cmd: str):
    RedisQueue().put(cmd)
    print(f"Enqueued command: {cmd}")
        
# usage: python3.10 -m src.enqueue enqueue "sleep 10"
if __name__ == "__main__":
    fire.Fire(enqueue)