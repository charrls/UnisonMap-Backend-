import asyncio
import gzip
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import uuid4

import aiosqlite

try:
    import redis.asyncio as redis_asyncio  # type: ignore
except ImportError:  # pragma: no cover - redis optional en runtime
    redis_asyncio = None

if TYPE_CHECKING:  # pragma: no cover - solo para type checkers
    from redis.asyncio import Redis as RedisType  # type: ignore
else:
    RedisType = Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_LOCK_KEY_PREFIX = "lock:route:"


def _serialize_payload(payload: Dict[str, Any]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if settings.CACHE_ALWAYS_COMPRESS:
        return gzip.compress(data, compresslevel=5)
    return data


def _deserialize_payload(raw: bytes) -> Dict[str, Any]:
    if settings.CACHE_ALWAYS_COMPRESS:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            logger.warning("No se pudo descomprimir payload en cache, usando datos crudos")
    return json.loads(raw.decode("utf-8"))


class CacheService(ABC):
    """Contrato mínimo para cachés de rutas."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    async def set(self, key: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
        ...

    @abstractmethod
    async def acquire_lock(self, key: str, ttl_seconds: int) -> Optional[str]:
        ...

    @abstractmethod
    async def release_lock(self, key: str, token: str) -> None:
        ...

    async def wait_for_value(self, key: str, attempts: int = 10, delay: float = 0.25) -> Optional[Dict[str, Any]]:
        """Espera activa hasta que exista un valor en cache o se agoten intentos."""

        for _ in range(attempts):
            cached = await self.get(key)
            if cached is not None:
                return cached
            await asyncio.sleep(delay)
        return None

    async def close(self) -> None:  # pragma: no cover - opcional
        return None


class RedisCache(CacheService):
    def __init__(self, url: str) -> None:
        if redis_asyncio is None:
            raise RuntimeError("Paquete redis no disponible")
        self._url = url
        self._client: Optional[RedisType] = None
        self._lock_release_script = None

    async def initialize(self) -> None:
        assert redis_asyncio is not None  # para mypy / type-checkers
        self._client = redis_asyncio.from_url(self._url, encoding=None, decode_responses=False)
        await self._client.ping()
        self._lock_release_script = self._client.register_script(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
        )
        logger.info("CacheService Redis inicializado correctamente")

    @property
    def client(self) -> RedisType:
        if self._client is None:
            raise RuntimeError("RedisCache no inicializado")
        return self._client

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        raw = await self.client.get(key)
        if raw is None:
            return None
        return _deserialize_payload(raw)

    async def set(self, key: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
        data = _serialize_payload(payload)
        await self.client.set(key, data, ex=ttl_seconds)

    async def acquire_lock(self, key: str, ttl_seconds: int) -> Optional[str]:
        lock_key = f"{_LOCK_KEY_PREFIX}{key}"
        token = str(uuid4())
        acquired = await self.client.set(lock_key, token, nx=True, ex=ttl_seconds)
        return token if acquired else None

    async def release_lock(self, key: str, token: str) -> None:
        if self._lock_release_script is None:
            return
        lock_key = f"{_LOCK_KEY_PREFIX}{key}"
        try:
            await self._lock_release_script(keys=[lock_key], args=[token])
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.warning("Error liberando lock Redis %s: %s", lock_key, exc)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


class SQLiteCache(CacheService):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def initialize(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS routes_cache (
                cache_key TEXT PRIMARY KEY,
                payload BLOB NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        await self._conn.commit()
        logger.info("CacheService SQLite inicializado en %s", self._db_path)

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("SQLiteCache no inicializado")
        return self._conn

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT payload, expires_at FROM routes_cache WHERE cache_key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        payload_bytes, expires_at = row
        if expires_at <= int(time.time()):
            async with self.conn.execute("DELETE FROM routes_cache WHERE cache_key = ?", (key,)):
                pass
            await self.conn.commit()
            return None
        return _deserialize_payload(payload_bytes)

    async def set(self, key: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
        expires_at = int(time.time()) + ttl_seconds
        data = _serialize_payload(payload)
        await self.conn.execute(
            """
            INSERT INTO routes_cache(cache_key, payload, expires_at)
            VALUES(?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                payload = excluded.payload,
                expires_at = excluded.expires_at
            """,
            (key, data, expires_at),
        )
        await self.conn.commit()

    async def acquire_lock(self, key: str, ttl_seconds: int) -> Optional[str]:  # noqa: ARG002 - ttl no usado en SQLite
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
        acquired = await lock.acquire()
        return key if acquired else None

    async def release_lock(self, key: str, token: str) -> None:  # noqa: ARG002 - token no usado en SQLite
        lock = self._locks.get(key)
        if lock and lock.locked():
            lock.release()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


class CacheServiceFactory:
    _instance: Optional[CacheService] = None
    _init_lock = asyncio.Lock()

    @classmethod
    async def get_cache(cls) -> Optional[CacheService]:
        if cls._instance is not None:
            return cls._instance

        async with cls._init_lock:
            if cls._instance is not None:
                return cls._instance

            if settings.REDIS_URL:
                try:
                    redis_cache = RedisCache(settings.REDIS_URL)
                    await redis_cache.initialize()
                    cls._instance = redis_cache
                    return cls._instance
                except Exception as exc:
                    logger.warning("Redis no disponible (%s). Usando SQLite fallback.", exc)

            sqlite_cache = SQLiteCache(settings.CACHE_SQLITE_PATH)
            await sqlite_cache.initialize()
            cls._instance = sqlite_cache
            return cls._instance

    @classmethod
    async def reset(cls) -> None:
        if cls._instance is not None:
            try:
                await cls._instance.close()
            finally:
                cls._instance = None
