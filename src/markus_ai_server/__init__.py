import secrets

from .redis_helper import REDIS_CONNECTION


def generate_api_key(value: str) -> str:
    """Generate a new API key"""
    api_key = secrets.token_hex(32)
    REDIS_CONNECTION.set(f"api-key:{api_key}", value)
    print(api_key)  # Just for testing purposes
    return api_key
