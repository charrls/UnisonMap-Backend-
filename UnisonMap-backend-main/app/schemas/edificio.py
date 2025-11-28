from pydantic import BaseModel
from typing import Optional

class EdificioCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class EdificioOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str]

    class Config:
        from_attributes = True
