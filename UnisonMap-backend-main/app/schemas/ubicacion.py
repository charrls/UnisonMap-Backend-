from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class TipoUbicacionEnum(str, Enum):
    aula = "aula"
    oficina = "oficina"
    baño = "baño"
    cafeteria = "cafeteria"
    entrada = "entrada"
    pasillo = "pasillo"
    laboratorio = "laboratorio"
    edificio = "edificio"
    otro = "otro"
 

class UbicacionCreate(BaseModel):
    nombre: str
    tipo: TipoUbicacionEnum
    edificio_id: Optional[int] = None
    latitud: float = Field(..., ge=-90.0, le=90.0)
    longitud: float = Field(..., ge=-180.0, le=180.0)
    piso: int = 1


class UbicacionOut(BaseModel):
    id: int
    nombre: str
    tipo: TipoUbicacionEnum
    edificio_id: Optional[int]
    latitud: float
    longitud: float
    piso: int
    
    class Config:
        from_attributes = True
