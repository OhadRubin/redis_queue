import redis
import os
import json
import requests


# def get_redis_url():
#     headers = {
#         'Authorization': 'Bearer 2r1YIzNo0KpPmyZSpKQFhcDtrpO_7SCPzbMxakXt53jryGikf',
#         'Ngrok-Version': '2'
#     }
#     response = requests.get('https://api.ngrok.com/endpoints', headers=headers)
#     return response.json()["endpoints"][0]["public_url"]
# # Connect to Redis
# r = redis.from_url(get_redis_url(),
#                    )
r = redis.Redis(
    host="4.tcp.eu.ngrok.io",
    port=12954,
    # ohadrubin.com:
    password=os.getenv('REDIS_PASSWORD'),
    decode_responses=True
)

# Set a value
r.set('mykey', 'myvaadasdlue')

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