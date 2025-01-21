#!/bin/bash

# it was obtained from:
# wget https://github.com/amalshaji/portr/releases/download/0.0.26-beta/portr_0.0.26-beta_Linux_x86_64.zip
# unzip portr_0.0.26-beta_Linux_x86_64.zip 
./portr auth set --token $PORTR_KEY --remote $GATEWAY_DOMAIN


start_tunnel() {
    local protocol="${1:-tcp}"  # tcp or http
    local port="${2:-6379}"
    local subdomain="${3:-redis}"
    local reconnect_delay="${4:-5}"
    
    while true; do
        if [ "$protocol" = "tcp" ]; then
            ./portr tcp "$port" -s "$subdomain"
        elif [ "$protocol" = "http" ]; then
            ./portr http "$port" -s "$subdomain"
        else
            echo "Invalid protocol. Use 'tcp' or 'http'"
            return 1
        fi
        echo "Connection lost, reconnecting in $reconnect_delay seconds..."
        sleep "$reconnect_delay"
    done
}

# start_tunnel tcp 6379 redis 5 &
start_tunnel http 8081 redis-commander 5 &
start_tunnel http 8051 monitor 5 &
start_tunnel tcp 6379 redis 5 &
wait