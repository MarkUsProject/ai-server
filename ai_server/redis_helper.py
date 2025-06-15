import os

import redis

REDIS_URL = os.environ["REDIS_URL"]

REDIS_CONNECTION = redis.Redis.from_url(REDIS_URL)
