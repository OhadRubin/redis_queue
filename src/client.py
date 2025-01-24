import redis
import os
import json
import requests



def get_redis_url():
    headers = {
        'Authorization': f'Bearer {os.getenv("NGROK_API_KEY")}',
        'Ngrok-Version': '2'
    }
    
    response = requests.get('https://api.ngrok.com/endpoints', headers=headers)
    ngrok_url = response.json()["endpoints"][0]["public_url"]
    addr, port = ngrok_url.replace("tcp://","").split(":")
    password = os.getenv('REDIS_PASSWORD')
    return f"redis://:{password}@{addr}:{port}"


def get_client(**kwargs):
    url = get_redis_url()
    # host=addr,
    # port=int(port),
    # password=os.getenv('REDIS_PASSWORD'),
    r = redis.Redis.from_url(url,
        **kwargs
        # decode_responses=True
    )
    # redis.Redis.from_url(f"redis://{addr}:{port}", password=os.getenv('REDIS_PASSWORD'), **kwargs)
    return r

if __name__ == "__main__":
    r = get_client()
    print(r.get('mykey'))