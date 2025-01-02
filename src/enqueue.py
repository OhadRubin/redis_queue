import fire
from src.redis_queue import RedisQueue

def enqueue(cmd: str, name: str="default"):
    RedisQueue(name=name).put(cmd)
    print(f"Enqueued command: {cmd}")
        
# usage: python3.10 -m src.enqueue enqueue "sleep 10"
# python3.10 -m src.enqueue --cmd "gsutil cat gs://meliad2_us2_backup/scripts/script.sh | bash" --name v4-16
if __name__ == "__main__":
    fire.Fire(enqueue)