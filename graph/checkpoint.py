import logging
import pickle
from collections import defaultdict
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from settings import get_settings


logger = logging.getLogger(__name__)


class RedisBackedMemorySaver(InMemorySaver):
    """InMemorySaver-compatible checkpointer that snapshots state to Redis."""

    def __init__(self, client: Any, key: str, ttl_seconds: int) -> None:
        super().__init__()
        self._client = client
        self._key = key
        self._ttl_seconds = ttl_seconds
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        try:
            raw = self._client.get(self._key)
            if not raw:
                return
            snapshot = pickle.loads(raw)
            storage = defaultdict(lambda: defaultdict(dict))
            for thread_id, namespaces in snapshot.get("storage", {}).items():
                for checkpoint_ns, checkpoints in namespaces.items():
                    storage[thread_id][checkpoint_ns].update(checkpoints)
            writes = defaultdict(dict)
            writes.update(snapshot.get("writes", {}))
            self.storage = storage
            self.writes = writes
            self.blobs = snapshot.get("blobs", {})
        except Exception as exc:
            logger.warning("redis checkpoint load failed, starting with empty memory: %s", exc)

    def _snapshot(self) -> dict[str, Any]:
        return {
            "storage": {
                thread_id: {
                    checkpoint_ns: dict(checkpoints)
                    for checkpoint_ns, checkpoints in namespaces.items()
                }
                for thread_id, namespaces in self.storage.items()
            },
            "writes": dict(self.writes),
            "blobs": dict(self.blobs),
        }

    def _persist_snapshot(self) -> None:
        try:
            payload = pickle.dumps(self._snapshot())
            self._client.setex(self._key, self._ttl_seconds, payload)
        except Exception as exc:
            logger.warning("redis checkpoint persist failed, continuing in memory: %s", exc)

    def put(self, config, checkpoint, metadata, new_versions):
        updated_config = super().put(config, checkpoint, metadata, new_versions)
        self._persist_snapshot()
        return updated_config

    def put_writes(self, config, writes, task_id, task_path="") -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist_snapshot()

    def delete_thread(self, thread_id: str) -> None:
        super().delete_thread(thread_id)
        self._persist_snapshot()


def build_checkpointer():
    settings = get_settings()
    if not settings.redis_checkpoint_enabled:
        return InMemorySaver()
    try:
        import redis
    except ImportError:
        logger.warning("redis package is not installed, falling back to InMemorySaver")
        return InMemorySaver()

    try:
        client = redis.from_url(settings.redis_url)
        client.ping()
    except Exception as exc:
        logger.warning("redis unavailable, falling back to InMemorySaver: %s", exc)
        return InMemorySaver()

    key = f"{settings.redis_key_prefix}:checkpoints:v1"
    return RedisBackedMemorySaver(
        client=client,
        key=key,
        ttl_seconds=settings.redis_checkpoint_ttl_seconds,
    )
