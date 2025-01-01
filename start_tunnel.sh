#!/bin/bash

# it was obtained from:
# wget https://github.com/amalshaji/portr/releases/download/0.0.26-beta/portr_0.0.26-beta_Linux_x86_64.zip
# unzip portr_0.0.26-beta_Linux_x86_64.zip 
./portr auth set --token $PORTR_KEY --remote $GATEWAY_DOMAIN

while true; do
    ./portr tcp 6379 -s redis
    echo "Connection lost, reconnecting in 5 seconds..."
    sleep 5
done
