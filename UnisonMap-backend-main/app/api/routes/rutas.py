import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.rutas import obtener_ruta
from app.services.ors_routing import (
    normalize_allowed_profiles,
    obtener_ruta_ors,
    obtener_ruta_ors_por_coordenadas,
)
from app.models.ubicacion import Ubicacion
from app.schemas.ruta import RutaCoordenadasRequest, RutaORSResponse
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_cache_ttl(request: Request) -> Optional[int]:
    if not settings.CACHE_ALLOW_HEADER_OVERRIDE:
        return None
    ttl_header = request.headers.get("X-Cache-TTL")
    if ttl_header is None:
        return None
    try:
        ttl_value = int(ttl_header)
    except ValueError:
        logger.warning("Valor inválido para X-Cache-TTL: %s", ttl_header)
        return None
    return ttl_value


def _extract_request_id(request: Request) -> Optional[str]:
    return request.headers.get("X-Request-ID")


def _determine_allowed_profiles(request: Request) -> List[str]:
    override_header = request.headers.get("X-Allowed-Profiles")
    if override_header and settings.DEBUG:
        candidates = [item for item in (segment.strip() for segment in override_header.split(",")) if item]
        if candidates:
            return normalize_allowed_profiles(candidates)
    return normalize_allowed_profiles(None)


@router.get("/rutas/{desde_id}/{hacia_id}")
async def calcular_ruta(
    desde_id: int, 
    hacia_id: int, 
    db: Session = Depends(get_db)
):
    """
    Calcula la ruta óptima entre dos ubicaciones usando algoritmo Dijkstra interno
    Retorna las coordenadas para trazar en el mapa
    """
    try:
        ruta_ubicaciones = obtener_ruta(db, desde_id, hacia_id)
        
        if not ruta_ubicaciones:
            raise HTTPException(status_code=404, detail="No se encontró ruta")
        
        coordenadas = []
        for ubicacion in ruta_ubicaciones:
            coordenadas.append({
                "latitud": ubicacion.latitud,
                "longitud": ubicacion.longitud,
                "nombre": ubicacion.nombre,
                "id": ubicacion.id
            })
        
        distancia_total = len(ruta_ubicaciones) * 50  
        tiempo_estimado = distancia_total / 80  
        
        return {
            "ruta": coordenadas,
            "distancia_metros": distancia_total,
            "tiempo_minutos": round(tiempo_estimado, 1),
            "origen": {
                "id": ruta_ubicaciones[0].id,
                "nombre": ruta_ubicaciones[0].nombre,
                "latitud": ruta_ubicaciones[0].latitud,
                "longitud": ruta_ubicaciones[0].longitud
            },
            "destino": {
                "id": ruta_ubicaciones[-1].id,
                "nombre": ruta_ubicaciones[-1].nombre,
                "latitud": ruta_ubicaciones[-1].latitud,
                "longitud": ruta_ubicaciones[-1].longitud
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando ruta: {str(e)}")

# Endpoint ORS basado en IDs de ubicaciones
@router.get("/rutas/ors/{desde_id}/{hacia_id}", response_model=RutaORSResponse)
async def calcular_ruta_ors(
    desde_id: int,
    hacia_id: int,
    request: Request,
    profile: Optional[str] = Query(
        default=None,
        description="Perfil de enrutamiento ORS permitido",
    ),
    db: Session = Depends(get_db)
):
    """
    Calcula ruta peatonal REAL usando OpenRouteService y datos de OpenStreetMap
    Devuelve coordenadas detalladas del camino real a seguir
    
    Args:
        desde_id: ID de ubicación de origen
        hacia_id: ID de ubicación de destino
        
    Returns:
        {
            "ruta": [{"lat": 29.0721, "lng": -110.9543}, ...],
            "distancia_m": 432,
            "duracion_s": 150,
            "origen": {...},
            "destino": {...}
        }
    """
    cache_ttl = _extract_cache_ttl(request)
    request_id = _extract_request_id(request)
    allowed_profiles = _determine_allowed_profiles(request)
    return await obtener_ruta_ors(
        db,
        desde_id,
        hacia_id,
        profile=profile,
        cache_ttl=cache_ttl,
        request_id=request_id,
        allowed_profiles=allowed_profiles,
    )


# Endpoint ORS basado en coordenadas crudas
@router.post("/rutas/ors/coordenadas", response_model=RutaORSResponse)
async def calcular_ruta_ors_por_coordenadas_endpoint(
    payload: RutaCoordenadasRequest,
    request: Request,
):
    coordenadas = [list(payload.origin), list(payload.destination)]
    profile = payload.profile
    cache_ttl = _extract_cache_ttl(request)
    request_id = _extract_request_id(request)
    allowed_profiles = _determine_allowed_profiles(request)
    return await obtener_ruta_ors_por_coordenadas(
        coordenadas,
        profile=profile,
        cache_ttl=cache_ttl,
        request_id=request_id,
        allowed_profiles=allowed_profiles,
    )