import asyncio
from typing import Any, Awaitable, Callable, Tuple, Type


async def with_retries(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    retries: int = 3,
    base_delay: float = 0.5,
    retry_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except retry_exceptions:
            attempt += 1
            if attempt > retries:
                raise
            await asyncio.sleep(base_delay * (2 ** (attempt - 1)))
