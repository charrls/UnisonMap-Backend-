from pydantic import BaseModel
from typing import Optional

class ConexionCreate(BaseModel):
    origen_id: int
    destino_id: int
    peso: float

class ConexionOut(BaseModel):
    id: int
    origen_id: int
    destino_id: int
    peso: float

    class Config:
        from_attributes = True
