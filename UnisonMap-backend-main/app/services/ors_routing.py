import asyncio
import hashlib
import json
import logging
import re
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx
import polyline
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ubicacion import Ubicacion
from app.services.cache_service import CacheService, CacheServiceFactory

try:
    from prometheus_client import Counter  # type: ignore
except ImportError:  # pragma: no cover - métrica opcional
    Counter = None

DEFAULT_PROFILE = "foot-walking"
MAX_STEP_TEXT_LENGTH = 240
MAX_ROUTE_STEPS = 200

if Counter is not None:
    ORS_ERRORS_COUNTER = Counter(
        "unisonmap_ors_errors_total",
        "Total de errores al llamar a OpenRouteService",
        ["reason"],
    )
else:  # pragma: no cover - métrica opcional
    ORS_ERRORS_COUNTER = None

logger = logging.getLogger(__name__)


def _format_coord_pair(lng: float, lat: float) -> str:
    return f"{lng:.6f},{lat:.6f}"


def _increment_ors_error(reason: str) -> None:
    if ORS_ERRORS_COUNTER is not None:  # pragma: no branch - contador opcional
        try:
            ORS_ERRORS_COUNTER.labels(reason=reason).inc()
        except Exception:  # pragma: no cover - robustez métrica
            logger.debug("No se pudo incrementar métrica ORS para reason=%s", reason)


def _validate_coordinates(coordenadas: List[List[Any]], *, source: str = "payload") -> List[List[float]]:
    context = f" ({source})" if source else ""
    if not isinstance(coordenadas, list) or len(coordenadas) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_payload",
                "message": f"Se requieren al menos dos puntos [lon, lat]{context}",
                "field": "coordinates",
            },
        )

    sanitized: List[List[float]] = []
    for idx, pair in enumerate(coordenadas):
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_payload",
                    "message": f"Coordenada #{idx + 1} inválida; se esperaba [lon, lat]{context}",
                    "field": "coordinates",
                },
            )
        try:
            lon = float(pair[0])
            lat = float(pair[1])
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_payload",
                    "message": f"Coordenada #{idx + 1} contiene valores no numéricos{context}",
                    "field": "coordinates",
                },
            ) from None

        if not (-180.0 <= lon <= 180.0) or not (-90.0 <= lat <= 90.0):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "invalid_payload",
                    "message": f"Coordenada #{idx + 1} fuera de rango lon/lat{context}",
                    "field": "coordinates",
                },
            )
        sanitized.append([lon, lat])

    return sanitized


def _extract_ors_error_detail(response: httpx.Response) -> Dict[str, Any]:
    detail: Dict[str, Any] = {
        "code": "ors_error",
        "message": f"OpenRouteService devolvió estado {response.status_code}",
        "ors_status": response.status_code,
    }

    try:
        payload = response.json()
    except json.JSONDecodeError:
        body_preview = response.text[:200]
        if body_preview:
            detail["raw"] = body_preview
        return detail

    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            message = error_payload.get("message")
            if isinstance(message, str) and message.strip():
                detail["message"] = message.strip()
            code = error_payload.get("code")
            if isinstance(code, (int, str)):
                detail["ors_code"] = code
            details = error_payload.get("details")
            if isinstance(details, (list, dict)):
                detail["details"] = details
        elif isinstance(error_payload, str) and error_payload.strip():
            detail["message"] = error_payload.strip()
        # Guardar payload completo si es útil para depuración
        if "message" not in detail and isinstance(payload.get("message"), str):
            detail["message"] = payload["message"].strip()
        if "details" not in detail and isinstance(payload.get("details"), (list, dict)):
            detail["details"] = payload["details"]

    return detail


def _normalize_step_text(instruction: Any, name: Any, step_index: int) -> str:
    raw_instruction = str(instruction).strip() if isinstance(instruction, str) else ""
    step_name = str(name).strip() if isinstance(name, str) else ""

    if not raw_instruction:
        raw_instruction = f"Paso {step_index}" if step_name else f"Paso {step_index}"  # fallback genérico

    if step_name and step_name.lower() not in raw_instruction.lower():
        raw_instruction = f"{raw_instruction} en {step_name}" if raw_instruction else f"Continúa en {step_name}"

    normalized = re.sub(r"\s+", " ", raw_instruction).strip()
    if len(normalized) > MAX_STEP_TEXT_LENGTH:
        normalized = normalized[: MAX_STEP_TEXT_LENGTH - 3].rstrip() + "..."
    return normalized


def _extract_step_location(step: Dict[str, Any], ruta_coordenadas: List[Dict[str, float]]) -> Optional[Dict[str, float]]:
    way_points = step.get("way_points")
    if isinstance(way_points, (list, tuple)) and way_points:
        candidate = way_points[0]
        if isinstance(candidate, int) and 0 <= candidate < len(ruta_coordenadas):
            coord = ruta_coordenadas[candidate]
            lat = coord.get("lat")
            lng = coord.get("lng")
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                return {"lat": float(lat), "lng": float(lng)}

    coordinate = step.get("coordinate")
    if isinstance(coordinate, (list, tuple)) and len(coordinate) >= 2:
        try:
            lng = float(coordinate[0])
            lat = float(coordinate[1])
        except (TypeError, ValueError):
            return None
        return {"lat": lat, "lng": lng}

    return None


def _parse_steps(raw_steps: Any, ruta_coordenadas: List[Dict[str, float]]) -> List[Dict[str, Any]]:
    if not isinstance(raw_steps, list):
        return []

    parsed_steps: List[Dict[str, Any]] = []
    for idx, step in enumerate(raw_steps):
        if not isinstance(step, dict):
            continue

        texto = _normalize_step_text(step.get("instruction"), step.get("name"), idx + 1)
        try:
            distance = int(round(float(step.get("distance", 0) or 0)))
        except (TypeError, ValueError):
            distance = 0
        try:
            duration = int(round(float(step.get("duration", 0) or 0)))
        except (TypeError, ValueError):
            duration = 0

        location = _extract_step_location(step, ruta_coordenadas)

        parsed_steps.append(
            {
                "orden": idx,
                "texto": texto,
                "distance_m": max(0, distance),
                "duration_s": max(0, duration),
                "location": location,
            }
        )

        if len(parsed_steps) >= MAX_ROUTE_STEPS:
            logger.info("Se truncaron las instrucciones de ruta a %s pasos", MAX_ROUTE_STEPS)
            break

    return parsed_steps


def normalize_allowed_profiles(allowed_profiles: Optional[List[str]]) -> List[str]:
    profiles = allowed_profiles if allowed_profiles is not None else settings.ORS_ALLOWED_PROFILES
    normalized = [profile.strip().lower() for profile in profiles if isinstance(profile, str) and profile.strip()]
    if not normalized:
        normalized = [DEFAULT_PROFILE]
    return normalized


def normalize_profile(profile: Optional[str], allowed_profiles: Optional[List[str]] = None) -> str:
    normalized_allowed = normalize_allowed_profiles(allowed_profiles)
    candidate = profile.strip().lower() if isinstance(profile, str) and profile.strip() else normalized_allowed[0]
    if candidate not in normalized_allowed:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_profile",
                "allowed": normalized_allowed,
                "received": candidate,
            },
        )
    return candidate


def _build_cache_key(profile: str, coordenadas: List[List[float]], variant: str = "coords") -> str:
    if not coordenadas or len(coordenadas[0]) < 2 or len(coordenadas[-1]) < 2:
        raise ValueError("Coordenadas inválidas para cache")
    origen = coordenadas[0]
    destino = coordenadas[-1]
    raw_key = f"{variant}|{profile}|{_format_coord_pair(origen[0], origen[1])}|{_format_coord_pair(destino[0], destino[1])}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"route:{digest}"


def _resolve_cache_ttl(override_ttl: Optional[int]) -> int:
    ttl = settings.CACHE_TTL_SECONDS
    if override_ttl is not None:
        try:
            override_value = max(0, int(override_ttl))
        except (TypeError, ValueError):
            override_value = ttl
        else:
            ttl = override_value
    if ttl == 0:
        return 0
    return min(ttl, settings.CACHE_MAX_TTL_SECONDS)


def _log_prefix(request_id: Optional[str]) -> str:
    return f"[req:{request_id}] " if request_id else ""

class ORSService:
    """
    Servicio para integración con OpenRouteService API
    Calcula rutas peatonales reales usando datos de OpenStreetMap
    """
    
    def __init__(self):
        if not settings.ORS_API_KEY:
            raise ValueError("ORS_API_KEY no está configurada en las variables de entorno")
        if not settings.ORS_BASE_URL:
            raise ValueError("ORS_BASE_URL no está configurada en las variables de entorno")
    
    def _build_profile_url(self, profile: str) -> str:
        base_url = settings.ORS_BASE_URL.rstrip("/")
        if "/directions/" in base_url:
            root, current_profile = base_url.rsplit("/", 1)
            if current_profile:
                return f"{root}/{profile}"
        return f"{base_url}/{profile}" if not base_url.endswith(profile) else base_url

    async def _hacer_peticion_ors(
        self,
        coordenadas: List[List[float]],
        profile: str = DEFAULT_PROFILE,
        *,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Realiza la petición HTTP hacia ORS con reintentos y manejo de errores enriquecido."""

        normalized_coords = _validate_coordinates(coordenadas, source="internal")
        headers = {
            "Authorization": settings.ORS_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"coordinates": normalized_coords}
        url = self._build_profile_url(profile)

        attempts = max(1, settings.ORS_MAX_RETRIES + 1)
        backoff_factor = max(0.0, settings.ORS_BACKOFF_FACTOR)
        prefix = _log_prefix(request_id)

        logger.info("%sEnviando petición a ORS (perfil=%s): %s", prefix, profile, normalized_coords)
        logger.debug("%sURL ORS: %s", prefix, url)

        async with httpx.AsyncClient(timeout=settings.ORS_TIMEOUT) as client:
            for attempt in range(1, attempts + 1):
                attempt_label = f"{attempt}/{attempts}"
                start_ts = time.perf_counter()
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    elapsed_ms = (time.perf_counter() - start_ts) * 1000
                    logger.info(
                        "%sRespuesta ORS intento %s: status=%s en %.0fms",
                        prefix,
                        attempt_label,
                        response.status_code,
                        elapsed_ms,
                    )
                except httpx.TimeoutException:
                    elapsed_ms = (time.perf_counter() - start_ts) * 1000
                    logger.warning(
                        "%sTimeout ORS tras %.0fms (intento %s, perfil=%s)",
                        prefix,
                        elapsed_ms,
                        attempt_label,
                        profile,
                    )
                    _increment_ors_error("timeout")
                    if attempt < attempts:
                        sleep_seconds = backoff_factor * (2 ** (attempt - 1))
                        if sleep_seconds > 0:
                            await asyncio.sleep(sleep_seconds)
                        continue
                    raise HTTPException(
                        status_code=504,
                        detail={
                            "code": "ors_timeout",
                            "message": "Timeout al conectar con OpenRouteService",
                            "attempts": attempt,
                        },
                    )
                except httpx.RequestError as exc:
                    elapsed_ms = (time.perf_counter() - start_ts) * 1000
                    logger.warning(
                        "%sError de conexión ORS tras %.0fms (intento %s, perfil=%s): %s",
                        prefix,
                        elapsed_ms,
                        attempt_label,
                        profile,
                        exc,
                    )
                    _increment_ors_error("connection_error")
                    if attempt < attempts:
                        sleep_seconds = backoff_factor * (2 ** (attempt - 1))
                        if sleep_seconds > 0:
                            await asyncio.sleep(sleep_seconds)
                        continue
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "code": "ors_connection_error",
                            "message": "Error de conexión con OpenRouteService",
                            "attempts": attempt,
                        },
                    )

                if response.status_code == 200:
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        _increment_ors_error("invalid_json")
                        logger.error(
                            "%sRespuesta ORS inválida (JSON) intento %s: %s",
                            prefix,
                            attempt_label,
                            response.text[:200],
                        )
                        raise HTTPException(
                            status_code=502,
                            detail={
                                "code": "ors_invalid_json",
                                "message": "Respuesta inválida de OpenRouteService",
                            },
                        )

                ors_detail = _extract_ors_error_detail(response)

                if response.status_code == 400:
                    _increment_ors_error("bad_request")
                    ors_detail.update(
                        {
                            "code": "ors_invalid_request",
                            "message": ors_detail.get(
                                "message",
                                "Parámetros inválidos en petición a OpenRouteService",
                            ),
                        }
                    )
                    logger.error("%sPetición ORS inválida: %s", prefix, ors_detail)
                    raise HTTPException(status_code=400, detail=ors_detail)

                if response.status_code == 401:
                    _increment_ors_error("unauthorized")
                    ors_detail.update(
                        {
                            "code": "ors_invalid_key",
                            "message": ors_detail.get(
                                "message",
                                "API Key de OpenRouteService inválida o expirada",
                            ),
                        }
                    )
                    logger.error("%sAPI Key ORS inválida: %s", prefix, ors_detail)
                    raise HTTPException(status_code=500, detail=ors_detail)

                if response.status_code == 403:
                    _increment_ors_error("forbidden")
                    ors_detail.update(
                        {
                            "code": "ors_forbidden",
                            "message": ors_detail.get(
                                "message",
                                "OpenRouteService rechazó la petición (forbidden)",
                            ),
                        }
                    )
                    logger.error("%sAcceso ORS denegado/cuota excedida: %s", prefix, ors_detail)
                    raise HTTPException(status_code=503, detail=ors_detail)

                if response.status_code == 429:
                    _increment_ors_error("rate_limited")
                    ors_detail.update(
                        {
                            "code": "ors_rate_limited",
                            "message": ors_detail.get(
                                "message",
                                "Límite de solicitudes a OpenRouteService excedido",
                            ),
                        }
                    )
                    logger.warning("%sRate limit ORS detectado: %s", prefix, ors_detail)
                    if attempt < attempts:
                        sleep_seconds = backoff_factor * (2 ** (attempt - 1)) or 1.0
                        await asyncio.sleep(sleep_seconds)
                        continue
                    raise HTTPException(status_code=503, detail=ors_detail)

                if response.status_code == 404:
                    _increment_ors_error("not_found")
                    ors_detail.update(
                        {
                            "code": "ors_not_found",
                            "message": ors_detail.get(
                                "message",
                                "OpenRouteService no encontró ruta para las coordenadas dadas",
                            ),
                        }
                    )
                    logger.warning("%sORS no encontró ruta: %s", prefix, ors_detail)
                    raise HTTPException(status_code=404, detail=ors_detail)

                if 500 <= response.status_code < 600 or response.status_code in {502, 503, 504}:
                    _increment_ors_error("server_error")
                    ors_detail.update(
                        {
                            "code": "ors_unavailable",
                            "message": ors_detail.get(
                                "message",
                                "OpenRouteService no está disponible",
                            ),
                        }
                    )
                    logger.warning(
                        "%sORS respondió con error %s: %s",
                        prefix,
                        response.status_code,
                        ors_detail,
                    )
                    if attempt < attempts:
                        sleep_seconds = backoff_factor * (2 ** (attempt - 1)) or 1.0
                        await asyncio.sleep(sleep_seconds)
                        continue
                    raise HTTPException(status_code=502, detail=ors_detail)

                _increment_ors_error("unexpected_status")
                logger.error(
                    "%sEstado ORS inesperado %s: %s",
                    prefix,
                    response.status_code,
                    ors_detail,
                )
                raise HTTPException(status_code=502, detail=ors_detail)

    def _decodificar_polyline(self, encoded_polyline: str) -> List[Dict[str, float]]:
        """
        Decodifica una polyline string a coordenadas
        
        Args:
            encoded_polyline: String codificada en formato Polyline
            
        Returns:
            Lista de coordenadas [{"lat": lat, "lng": lng}, ...]
        """
        try:
            # La librería polyline devuelve [(lat, lng), (lat, lng), ...]
            coordinates = polyline.decode(encoded_polyline)
            
            # Convertir a formato [{"lat": lat, "lng": lng}, ...]
            result = []
            for lat, lng in coordinates:
                result.append({
                    "lat": lat,
                    "lng": lng
                })
            
            logger.info(f"Polyline decodificada: {len(result)} puntos")
            return result
            
        except Exception as e:
            logger.error(f"Error decodificando polyline: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error decodificando geometría de ruta"
            )
    
    def _procesar_respuesta_ors(self, ors_response: Dict) -> Dict:
        """
        Procesa la respuesta de ORS y extrae la información necesaria
        
        Args:
            ors_response: Respuesta JSON de OpenRouteService
            
        Returns:
            Dict con ruta, distancia y duración procesados
        """
        try:
            logger.info(f"Procesando respuesta ORS...")
            
            # Debug: mostrar la estructura de la respuesta
            if isinstance(ors_response, dict):
                logger.info(f"Claves disponibles en respuesta: {list(ors_response.keys())}")
            else:
                logger.error(f"Respuesta no es un diccionario: {type(ors_response)}")
                raise HTTPException(
                    status_code=500,
                    detail="Formato de respuesta inesperado de OpenRouteService"
                )
            
            # Verificar que existe la clave 'routes'
            if "routes" not in ors_response:
                logger.error(f"No se encontró 'routes' en la respuesta. Claves: {list(ors_response.keys())}")
                raise HTTPException(
                    status_code=500,
                    detail="Estructura de respuesta inválida de OpenRouteService"
                )
            
            routes = ors_response["routes"]
            if not routes or len(routes) == 0:
                logger.error("No se encontraron rutas en la respuesta")
                raise HTTPException(
                    status_code=404,
                    detail="No se pudo calcular ruta entre las ubicaciones"
                )
            
            # Extraer la primera ruta
            route = routes[0]
            logger.info(f"Claves en route: {list(route.keys()) if isinstance(route, dict) else type(route)}")
            
            # Extraer coordenadas de la geometría (siempre viene como Polyline string)
            if "geometry" not in route:
                logger.error("No se encontró 'geometry' en la ruta")
                raise HTTPException(
                    status_code=500,
                    detail="Geometría de ruta no disponible"
                )
            
            geometry = route["geometry"]
            logger.info(f"Tipo de geometry: {type(geometry)}")
            
            if isinstance(geometry, str):
                logger.info("Decodificando geometría Polyline")
                ruta_coordenadas = self._decodificar_polyline(geometry)
            else:
                logger.debug("Procesando geometría ORS como %s", type(geometry))
                if isinstance(geometry, dict) and "coordinates" in geometry:
                    logger.info("Procesando geometría como objeto GeoJSON")
                    coordinates = geometry["coordinates"]
                    ruta_coordenadas = []
                    for coord in coordinates:
                        if len(coord) >= 2:
                            lng, lat = coord[0], coord[1]
                            ruta_coordenadas.append({
                                "lat": lat,
                                "lng": lng
                            })
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Formato de geometría no soportado"
                    )
            
            # Extraer distancia (en metros) y duración (en segundos)
            if "summary" not in route:
                logger.error("No se encontró 'summary' en la ruta")
                raise HTTPException(
                    status_code=500,
                    detail="Resumen de ruta no disponible"
                )
            
            summary = route["summary"]
            logger.info(f"Claves en summary: {list(summary.keys()) if isinstance(summary, dict) else type(summary)}")
            
            distancia_m = int(summary.get("distance", 0))
            duracion_s = int(summary.get("duration", 0))

            steps: List[Dict[str, Any]] = []
            segments = route.get("segments")
            if isinstance(segments, list) and segments:
                raw_steps = segments[0].get("steps") if isinstance(segments[0], dict) else None
                steps = _parse_steps(raw_steps, ruta_coordenadas)
            else:
                logger.debug("Respuesta ORS sin segmentos/steps disponibles")
            
            logger.info(f"Ruta procesada: {len(ruta_coordenadas)} puntos, {distancia_m}m, {duracion_s}s")
            
            return {
                "ruta": ruta_coordenadas,
                "distancia_m": distancia_m,
                "duracion_s": duracion_s,
                "instrucciones": steps,
                "steps_count": len(steps),
                "current_step_index": 0,
            }
            
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.error(f"Error procesando respuesta ORS: {str(e)}")
            logger.error(f"Respuesta completa: {ors_response}")
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando respuesta de OpenRouteService: {str(e)}"
            )


async def obtener_ruta_ors(
    db: Session,
    desde_id: int,
    hacia_id: int,
    profile: Optional[str] = None,
    *,
    cache_service: Optional[CacheService] = None,
    cache_ttl: Optional[int] = None,
    request_id: Optional[str] = None,
    allowed_profiles: Optional[List[str]] = None,
) -> Dict:
    """
    Función principal para obtener ruta usando OpenRouteService
    
    Args:
        db: Sesión de base de datos
        desde_id: ID de ubicación de origen
        hacia_id: ID de ubicación de destino
        
    Returns:
        Dict con ruta, distancia, duración y detalles de origen/destino
    """
    prefix = _log_prefix(request_id)
    logger.info(f"{prefix}Calculando ruta ORS desde {desde_id} hacia {hacia_id}")
    
    # Obtener ubicaciones desde la base de datos
    origen = db.query(Ubicacion).filter(Ubicacion.id == desde_id).first()
    if not origen:
        logger.error(f"Ubicación origen {desde_id} no encontrada")
        raise HTTPException(status_code=404, detail=f"Ubicación origen {desde_id} no encontrada")
    
    destino = db.query(Ubicacion).filter(Ubicacion.id == hacia_id).first()
    if not destino:
        logger.error(f"Ubicación destino {hacia_id} no encontrada")
        raise HTTPException(status_code=404, detail=f"Ubicación destino {hacia_id} no encontrada")
    
    logger.info(f"{prefix}Origen: {origen.nombre} ({origen.latitud}, {origen.longitud})")
    logger.info(f"{prefix}Destino: {destino.nombre} ({destino.latitud}, {destino.longitud})")

    # Preparar coordenadas para ORS (formato [lng, lat])
    coordenadas = [
        [origen.longitud, origen.latitud],
        [destino.longitud, destino.latitud]
    ]

    base_resultado = await obtener_ruta_ors_por_coordenadas(
        coordenadas,
        profile=profile,
        cache_service=cache_service,
        cache_ttl=cache_ttl,
        request_id=request_id,
        allowed_profiles=allowed_profiles,
    )

    resultado = deepcopy(base_resultado)
    resultado.setdefault("origen", {}).update(
        {
            "id": origen.id,
            "nombre": origen.nombre,
            "lat": origen.latitud,
            "lng": origen.longitud,
        }
    )
    resultado.setdefault("destino", {}).update(
        {
            "id": destino.id,
            "nombre": destino.nombre,
            "lat": destino.latitud,
            "lng": destino.longitud,
        }
    )

    logger.info(f"{prefix}Ruta ORS calculada exitosamente")
    return resultado


async def obtener_ruta_ors_por_coordenadas(
    coordenadas: List[List[float]],
    profile: Optional[str] = None,
    *,
    cache_service: Optional[CacheService] = None,
    cache_ttl: Optional[int] = None,
    request_id: Optional[str] = None,
    allowed_profiles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calcula una ruta usando coordenadas crudas en formato [[lng, lat], [lng, lat]]."""

    sanitized_coords = _validate_coordinates(coordenadas, source="payload")

    prefix = _log_prefix(request_id)
    ttl_seconds = _resolve_cache_ttl(cache_ttl)
    normalized_profile = normalize_profile(profile, allowed_profiles)
    cache = cache_service

    if cache is None:
        try:
            cache = await CacheServiceFactory.get_cache()
        except Exception as exc:  # pragma: no cover - fallback defensivo
            logger.warning("%sNo se pudo inicializar cache de rutas: %s", prefix, exc)
            cache = None

    cache_key = None
    cached_payload: Optional[Dict[str, Any]] = None
    lock_token: Optional[str] = None

    if cache is not None and ttl_seconds > 0:
        try:
            cache_key = _build_cache_key(normalized_profile, sanitized_coords, variant="coords")
            cached_payload = await cache.get(cache_key)
            if cached_payload is not None:
                logger.info("%sCache hit para ruta ORS (%s)", prefix, cache_key)
                return deepcopy(cached_payload)
        except Exception as exc:
            logger.warning("%sError leyendo cache de rutas: %s", prefix, exc)
            cache_key = None

    if cache is not None and ttl_seconds > 0 and cache_key is None:
        cache_key = _build_cache_key(normalized_profile, sanitized_coords, variant="coords")

    if cache is not None and ttl_seconds > 0 and cache_key is not None:
        try:
            lock_token = await cache.acquire_lock(cache_key, settings.CACHE_LOCK_TIMEOUT_SECONDS)
            if lock_token is None:
                logger.info("%sLock no disponible para %s; esperando valor existente", prefix, cache_key)
                cached_payload = await cache.wait_for_value(cache_key)
                if cached_payload is not None:
                    logger.info("%sCache llenado por otra petición para %s", prefix, cache_key)
                    return deepcopy(cached_payload)
        except Exception as exc:
            logger.warning("%sError adquiriendo lock de cache: %s", prefix, exc)
            lock_token = None

    try:
        ors_service = ORSService()
    except ValueError as e:
        logger.error(f"{prefix}Error configuración ORS: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    ors_response = await ors_service._hacer_peticion_ors(
        sanitized_coords,
        profile=normalized_profile,
        request_id=request_id,
    )
    resultado = ors_service._procesar_respuesta_ors(ors_response)
    resultado["origen"] = {
        "lat": sanitized_coords[0][1],
        "lng": sanitized_coords[0][0],
    }
    resultado["destino"] = {
        "lat": sanitized_coords[-1][1],
        "lng": sanitized_coords[-1][0],
    }
    resultado["perfil"] = normalized_profile

    if cache is not None and ttl_seconds > 0 and cache_key is not None:
        try:
            await cache.set(cache_key, resultado, ttl_seconds)
            logger.info("%sRuta ORS guardada en cache (%s) por %s s", prefix, cache_key, ttl_seconds)
        except Exception as exc:
            logger.warning("%sNo se pudo guardar ruta en cache: %s", prefix, exc)
        finally:
            if lock_token is not None:
                try:
                    await cache.release_lock(cache_key, lock_token)
                except Exception as exc:
                    logger.warning("%sNo se pudo liberar lock %s: %s", prefix, cache_key, exc)
    elif cache is not None and lock_token is not None and cache_key is not None:
        # Si ttl <= 0, liberar el lock igualmente
        try:
            await cache.release_lock(cache_key, lock_token)
        except Exception as exc:
            logger.warning("%sNo se pudo liberar lock %s: %s", prefix, cache_key, exc)

    logger.info("%sRuta ORS por coordenadas calculada exitosamente", prefix)
    return deepcopy(resultado)
