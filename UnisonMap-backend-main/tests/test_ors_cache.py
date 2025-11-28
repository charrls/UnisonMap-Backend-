import pytest

from app.core.config import settings
from app.services import ors_routing
from app.services.cache_service import CacheServiceFactory, RedisCache, SQLiteCache


class DummyORS:
    calls = 0
    last_profile = None

    def __init__(self) -> None:
        pass

    async def _hacer_peticion_ors(self, coordenadas, profile: str = "foot-walking"):
        DummyORS.calls += 1
        DummyORS.last_profile = profile
        return {}

    def _procesar_respuesta_ors(self, _response):
        return {
            "ruta": [{"lat": 29.0, "lng": -110.0}],
            "distancia_m": 100,
            "duracion_s": 45,
        }


class CacheHitStub:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    async def get(self, key):
        self.requests.append(("get", key))
        return self.payload

    async def set(self, key, payload, ttl_seconds):  # pragma: no cover - cache hit no usa
        raise AssertionError("No debería persistir en cache cuando hay hit")

    async def acquire_lock(self, key, ttl_seconds):
        return None

    async def release_lock(self, key, token):
        return None

    async def wait_for_value(self, key, attempts=10, delay=0.25):
        return None


class CacheMissStub:
    def __init__(self):
        self.set_calls = []
        self.lock_acquired = False
        self.released = False

    async def get(self, key):
        return None

    async def set(self, key, payload, ttl_seconds):
        self.set_calls.append((key, payload, ttl_seconds))

    async def acquire_lock(self, key, ttl_seconds):
        self.lock_acquired = True
        return "token"

    async def release_lock(self, key, token):
        self.released = True

    async def wait_for_value(self, key, attempts=10, delay=0.25):
        return None


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_response(monkeypatch):
    cached_payload = {
        "ruta": [{"lat": 29.0, "lng": -110.0}],
        "distancia_m": 123,
        "duracion_s": 56,
        "origen": {"lat": 29.0, "lng": -110.0},
        "destino": {"lat": 29.1, "lng": -110.1},
        "perfil": "foot-walking",
    }
    cache = CacheHitStub(cached_payload)

    result = await ors_routing.obtener_ruta_ors_por_coordenadas(
        [[-110.0, 29.0], [-110.1, 29.1]],
        cache_service=cache,
    )

    assert result == cached_payload
    assert ("get" in {op for op, _ in cache.requests})


@pytest.mark.asyncio
async def test_cache_miss_calls_ors_and_stores(monkeypatch):
    cache = CacheMissStub()
    DummyORS.calls = 0
    monkeypatch.setattr(ors_routing, "ORSService", DummyORS)

    coords = [[-110.0, 29.0], [-110.1, 29.1]]
    result = await ors_routing.obtener_ruta_ors_por_coordenadas(coords, cache_service=cache)

    assert DummyORS.calls == 1
    assert cache.lock_acquired is True and cache.released is True
    assert cache.set_calls
    stored_key, stored_payload, stored_ttl = cache.set_calls[0]
    assert stored_payload["ruta"]
    assert stored_payload["perfil"] == "foot-walking"
    assert stored_ttl == settings.CACHE_TTL_SECONDS
    assert result["perfil"] == "foot-walking"


@pytest.mark.asyncio
async def test_redis_down_fallback_sqlite(monkeypatch):
    await CacheServiceFactory.reset()

    # Simular redis configurado pero fallo de inicialización
    monkeypatch.setattr(settings, "REDIS_URL", "redis://localhost:6379/0")

    async def failing_init(self):
        raise ConnectionError("redis no disponible")

    monkeypatch.setattr(RedisCache, "initialize", failing_init)

    cache_instance = await CacheServiceFactory.get_cache()

    assert isinstance(cache_instance, SQLiteCache)

    await CacheServiceFactory.reset()


@pytest.mark.asyncio
async def test_cache_ttl_respected(monkeypatch):
    cache = CacheMissStub()
    DummyORS.calls = 0
    monkeypatch.setattr(ors_routing, "ORSService", DummyORS)

    monkeypatch.setattr(settings, "CACHE_MAX_TTL_SECONDS", 60)
    monkeypatch.setattr(settings, "CACHE_TTL_SECONDS", 10)

    await ors_routing.obtener_ruta_ors_por_coordenadas(
        [[-110.0, 29.0], [-110.1, 29.1]],
        cache_service=cache,
        cache_ttl=9999,
    )

    assert cache.set_calls
    _, _, ttl_used = cache.set_calls[0]
    assert ttl_used == 60
