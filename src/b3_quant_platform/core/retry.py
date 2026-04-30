from __future__ import annotations

from collections.abc import Callable
from typing import ParamSpec, TypeVar

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

P = ParamSpec("P")
R = TypeVar("R")


Retryable = Callable[[Callable[P, R]], Callable[P, R]]


def default_retry() -> Retryable:
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
