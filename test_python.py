import redis
import os
import json

# Connect to Redis
r = redis.Redis(
    host='redis.ohadrubin.com',
    port=6379,
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

# Set a value
r.set('mykey', 'myvalue')

# # Get a value 
value = r.get('mykey')
print(value)
# # Push to a list
# r.lpush('mylist', 'myvalue')

# # Pop from a list
# value = r.rpop('mylist')

# # Test gateway queue
# gateway_data = {
#     'domain': 'test.example.com',
#     'port': 8080
# }
# r.lpush('gateway_queue', json.dumps(gateway_data))
# result = r.rpop('gateway_queue')