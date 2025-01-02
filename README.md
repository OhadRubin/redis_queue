# Distributed Redis Task Queue

A distributed task queue system built with Redis, supporting job dependencies, worker coordination, and real-time monitoring.

## Features

- Distributed task queue with Redis backend
- Job dependency management
- Real-time job monitoring dashboard
- Worker heartbeat tracking
- Automatic job requeuing on worker failure
- Multi-system coordination for distributed workloads

## Prerequisites

- Python 3.9+
- Redis server
- Docker and Docker Compose (for running the complete stack)

## Installation

1. Clone the repository
2. Create a `.env` file with required credentials:
```env
REDIS_PASSWORD=your_redis_password
PORTR_KEY=your_portr_key
GATEWAY_DOMAIN=your_gateway_domain
NGROK_API_KEY=your_ngrok_api_key
```

## Usage

### Starting the Stack

```bash
docker-compose up
```

This starts:
- Redis server
- Redis Commander (web UI)
- Monitoring dashboard
- Portr tunnel service

### Enqueuing Jobs

```python
from src.redis_queue import RedisQueue

# Create a queue
queue = RedisQueue()

# Add a job
job_id = queue.put("echo hello")

# Add a job with dependencies
job_id = queue.put("echo world", depends_on=["previous_job_id"])
```

### Running Workers

```bash
# Start a worker
python3.10 -m src.redis_queue run_queue --worker_name=worker1

# Start a worker with custom settings
python3.10 -m src.redis_queue run_queue \
    --worker_name=worker1 \
    --sleep_time=3 \
    --set_heatbeat=True
```

### Monitoring

Access the monitoring dashboard at `http://localhost:8051`

## Architecture

The system consists of:
1. Redis backend for job storage and queue management
2. Worker processes that execute jobs
3. Monitoring interface built with Streamlit
4. ZMQ-based coordination for multi-system setups

## API Reference

### RedisQueue Class

Core methods:
- `put(item, depends_on=None)`: Add job to queue
- `get(timeout=None, return_job=False)`: Get next job
- `finalize_job(job_id)`: Mark job as complete
- `get_job_status(job_id)`: Check job status
- `get_all_jobs()`: List all jobs
- `get_all_workers()`: List all workers
