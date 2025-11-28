from pydantic import BaseModel, EmailStr
from enum import Enum

class TipoUsuarioEnum(str, Enum):
    estudiante = "estudiante"
    docente = "docente"
    admin = "admin"

class UsuarioBase(BaseModel):
    correo: EmailStr
    nombres: str
    apellidos: str
    tipo_usuario: TipoUsuarioEnum
    carrera: str | None = None
    departamento: str | None = None

class UsuarioCreate(UsuarioBase):
    contrasena: str

class UsuarioOut(UsuarioBase):
    id: int

    class Config:
        from_attributes = True
