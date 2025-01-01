version: '3'
networks:
  redis:
  
services:
  redis:
    image: redis
    command: redis-server --requirepass $REDIS_PASSWORD
    restart: always
    networks:
      - redis
  portr:
    build:
      context: .
      dockerfile: Dockerfile.portr
    environment:
      - PORTR_KEY=${PORTR_KEY}
      - GATEWAY_DOMAIN=${GATEWAY_DOMAIN}
    depends_on:
      - redis
    networks:
      - redis
#   visualizer:
#     image: bla
  #   depends_on:
  #     - redis
    