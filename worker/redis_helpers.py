from typing import Any, Dict, List, Optional, Union, cast

import redis


def zrangebyscore(
    r: redis.Redis, name: str, min_score: float, max_score: float
) -> List[Union[bytes, str]]:
    """Return a list of members (bytes or str) whose score is between min_score and max_score.

    This wrapper coerces the possibly-ambiguous redis return into a concrete list type for callers.
    """
    # cast the underlying return into a concrete list type for the analyzer
    raw_any = r.zrangebyscore(name, min_score, max_score)
    if isinstance(raw_any, (list, tuple)):
        return cast(List[Union[bytes, str]], list(raw_any))
    return []


def blpop(
    r: redis.Redis, keys: List[str], timeout: int = 0
) -> Optional[List[Union[bytes, str]]]:
    """Blocking left pop. Returns [key, value] or None."""
    # cast blpop return to a concrete list for the analyzer
    raw_any = r.blpop(keys, timeout=timeout)
    if isinstance(raw_any, (list, tuple)):
        return cast(List[Union[bytes, str]], list(raw_any))
    return None


def zrem(r: redis.Redis, name: str, value: Union[bytes, str]) -> int:
    # r.zrem may be typed as returning Awaitable; cast to int for analyzer
    raw_res = r.zrem(name, value)
    return int(cast(int, raw_res))


def rpush(r: redis.Redis, name: str, *values: Union[bytes, str]) -> int:
    raw_res = r.rpush(name, *values)
    return int(cast(int, raw_res))


def zadd(r: redis.Redis, name: str, mapping: Dict[str, float]) -> int:
    # redis-py expects name first then mapping
    raw_res = r.zadd(name, mapping)
    return int(cast(int, raw_res))


def set_(r: redis.Redis, name: str, value: Any) -> bool:
    raw_res = r.set(name, value)
    return bool(cast(bool, raw_res))
