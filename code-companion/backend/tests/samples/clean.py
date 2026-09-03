"""A tiny, well-documented module with no known issues."""
from functools import lru_cache


@lru_cache(maxsize=None)
def fibonacci(n: int) -> int:
    """Return the n-th Fibonacci number using memoized recursion."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
