import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.api.routes import rutas
from app.core.config import settings


@pytest.mark.asyncio
async def test_default_profile_is_foot_walking(monkeypatch):
    called = {}

    async def fake_service(coordenadas, profile=None, **kwargs):
        called["profile"] = profile
        called["allowed"] = kwargs.get("allowed_profiles")
        return {
            "perfil": profile,
            "ruta": [],
            "distancia_m": 0,
            "duracion_s": 0,
            "origen": {"lat": coordenadas[0][1], "lng": coordenadas[0][0]},
            "destino": {"lat": coordenadas[-1][1], "lng": coordenadas[-1][0]},
        }

    monkeypatch.setattr(rutas, "obtener_ruta_ors_por_coordenadas", fake_service)

    app = FastAPI()
    app.include_router(rutas.router, prefix="/api")

    payload = {
        "origin": [-110.0, 29.0],
        "destination": [-110.1, 29.1],
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/rutas/ors/coordenadas", json=payload)

    assert response.status_code == 200
    assert called["profile"] == "foot-walking"
    assert called["allowed"] == settings.ORS_ALLOWED_PROFILES


@pytest.mark.asyncio
async def test_invalid_profile_returns_400(monkeypatch):
    async def forbidden_service(*args, **kwargs):  # pragma: no cover - no debería ejecutarse
        raise AssertionError("No se debe invocar el servicio con perfil inválido")

    monkeypatch.setattr(rutas, "obtener_ruta_ors_por_coordenadas", forbidden_service)

    app = FastAPI()
    app.include_router(rutas.router, prefix="/api")

    payload = {
        "origin": [-110.0, 29.0],
        "destination": [-110.1, 29.1],
        "profile": "rocket",
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/rutas/ors/coordenadas", json=payload)

    assert response.status_code == 400
    detail = response.json().get("detail")
    assert detail == {
        "code": "invalid_profile",
        "allowed": settings.ORS_ALLOWED_PROFILES,
        "received": "rocket",
    }


@pytest.mark.asyncio
async def test_valid_profiles_pass_through(monkeypatch):
    captured = {}

    async def fake_service(coordenadas, profile=None, **kwargs):
        captured["profile"] = profile
        return {
            "perfil": profile,
            "ruta": [],
            "distancia_m": 0,
            "duracion_s": 0,
            "origen": {"lat": coordenadas[0][1], "lng": coordenadas[0][0]},
            "destino": {"lat": coordenadas[-1][1], "lng": coordenadas[-1][0]},
        }

    monkeypatch.setattr(rutas, "obtener_ruta_ors_por_coordenadas", fake_service)

    app = FastAPI()
    app.include_router(rutas.router, prefix="/api")

    payload = {
        "origin": [-110.0, 29.0],
        "destination": [-110.1, 29.1],
        "profile": "DRIVING-CAR",
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/rutas/ors/coordenadas", json=payload)

    assert response.status_code == 200
    assert captured["profile"] == "driving-car"
