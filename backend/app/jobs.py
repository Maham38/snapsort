import json
from functools import lru_cache

from redis import Redis

from app.config import get_settings

MATCHING_QUEUE = "snapsort:matching"
PHOTO_QUEUE = "snapsort:photo-processing"


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def enqueue_matching(job_id: str) -> None:
    try:
        redis_client().rpush(MATCHING_QUEUE, json.dumps({"job_id": job_id}))
    except Exception as error:
        raise RuntimeError("Matching queue is unavailable") from error


def enqueue_photo_processing(photo_id: str) -> None:
    try:
        redis_client().rpush(PHOTO_QUEUE, json.dumps({"photo_id": photo_id}))
    except Exception as error:
        raise RuntimeError("Photo processing queue is unavailable") from error
