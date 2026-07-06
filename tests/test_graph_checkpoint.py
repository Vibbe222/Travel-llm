from langgraph.checkpoint.memory import InMemorySaver

from graph.checkpoint import RedisBackedMemorySaver, build_checkpointer


class FakeRedis:
    def __init__(self):
        self.values = {}

    def ping(self):
        return True

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, _ttl, value):
        self.values[key] = value


def test_build_checkpointer_falls_back_to_memory_when_redis_missing(monkeypatch):
    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr("builtins.__import__", fake_import)

    assert isinstance(build_checkpointer(), InMemorySaver)


def test_redis_backed_memory_saver_restores_snapshot():
    client = FakeRedis()
    first = RedisBackedMemorySaver(client, "checkpoint", 60)
    first.storage["thread-1"][""]["checkpoint-1"] = (
        ("empty", b""),
        ("empty", b""),
        None,
    )
    first._persist_snapshot()

    second = RedisBackedMemorySaver(client, "checkpoint", 60)

    assert "checkpoint-1" in second.storage["thread-1"][""]
