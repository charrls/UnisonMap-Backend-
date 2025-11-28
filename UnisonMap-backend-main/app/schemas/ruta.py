# app/schemas/ruta.py

from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings


class RutaCoordenadasRequest(BaseModel):
    origin: List[float] = Field(
        ...,
        description="[lon, lat]",
        min_length=2,
        max_length=2,
    )
    destination: List[float] = Field(
        ...,
        description="[lon, lat]",
        min_length=2,
        max_length=2,
    )
    profile: Optional[str] = Field(
        default=None,
        description="Perfil de enrutamiento permitido",
        json_schema_extra={"enum": settings.ORS_ALLOWED_PROFILES},
    )

    class Config:
        json_schema_extra = {
            "example": {
                "origin": [-110.962283, 29.082419],
                "destination": [-110.962762, 29.082183],
                "profile": "foot-walking",
            }
        }


class RutaPunto(BaseModel):
    lat: float
    lng: float


class RutaUbicacion(RutaPunto):
    id: Optional[int] = Field(default=None, description="Identificador de la ubicación si aplica")
    nombre: Optional[str] = Field(default=None, description="Nombre descriptivo de la ubicación")


class RutaStep(BaseModel):
    orden: int = Field(..., ge=0)
    texto: str = Field(..., max_length=240)
    distance_m: int = Field(..., ge=0)
    duration_s: int = Field(..., ge=0)
    location: Optional[RutaPunto] = Field(default=None, description="Coordenada aproximada asociada al paso")


class RutaORSResponse(BaseModel):
    ruta: List[RutaPunto]
    distancia_m: int = Field(..., ge=0)
    duracion_s: int = Field(..., ge=0)
    instrucciones: List[RutaStep] = Field(default_factory=list)
    steps_count: int = Field(..., ge=0)
    current_step_index: int = Field(default=0, ge=0)
    origen: RutaUbicacion
    destino: RutaUbicacion
    perfil: str = Field(..., description="Perfil ORS utilizado para la ruta")

    class Config:
        json_schema_extra = {
            "example": {
                "ruta": [
                    {"lat": 29.0824, "lng": -110.9623},
                    {"lat": 29.0825, "lng": -110.9621},
                ],
                "distancia_m": 432,
                "duracion_s": 150,
                "instrucciones": [
                    {
                        "orden": 0,
                        "texto": "Sigue recto en Pasillo A",
                        "distance_m": 120,
                        "duration_s": 45,
                        "location": {"lat": 29.0824, "lng": -110.9623},
                    }
                ],
                "steps_count": 1,
                "current_step_index": 0,
                "origen": {"id": 1, "nombre": "Biblioteca", "lat": 29.0824, "lng": -110.9623},
                "destino": {"id": 2, "nombre": "Cafetería", "lat": 29.0825, "lng": -110.9621},
                "perfil": "foot-walking",
            }
        }
