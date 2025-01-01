import redis
import os
import json
import requests

NGROK_API_KEY = os.getenv('NGROK_API_KEY')
def get_redis():
    headers = {
        'Authorization': f'Bearer {NGROK_API_KEY}',
        'Ngrok-Version': '2'
    }
    
    response = requests.get('https://api.ngrok.com/endpoints', headers=headers)
    ngrok_url = response.json()["endpoints"][0]["public_url"]
    addr, port = ngrok_url.replace("tcp://","").split(":")
    r = redis.Redis(
        host=addr,
        port=int(port),
        password=os.getenv('REDIS_PASSWORD'),
        # decode_responses=True
    )
    return r

r = get_redis()
