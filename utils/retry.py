"""
Retry decorator for handling transient failures
"""
import asyncio
import logging
from functools import wraps
from typing import Callable, Type
import asyncpg

logger = logging.getLogger('xp-bot')


def retry_on_db_error(max_attempts: int = 3, delay: float = 0.5, backoff: float = 2.0):
    """
    Decorator to retry database operations on transient failures.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except (
                    asyncpg.ConnectionDoesNotExistError,
                    asyncpg.ConnectionFailureError,
                    asyncpg.InterfaceError,
                    asyncpg.TooManyConnectionsError,
                ) as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
                except asyncpg.PostgresError as e:
                    # Log other postgres errors but don't retry
                    logger.error(f"{func.__name__} database error: {e}")
                    raise

        return wrapper
    return decorator
