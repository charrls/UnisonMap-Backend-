from sqlalchemy import Column, Integer, String, Enum
from app.db.base_class import Base
import enum

class TipoUsuarioEnum(str, enum.Enum):
    estudiante = "estudiante"
    docente = "docente"
    admin = "admin"

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    correo = Column(String, unique=True, nullable=False, index=True)
    nombres = Column(String(50), nullable=False)
    apellidos = Column(String(50), nullable=False)
    tipo_usuario = Column(Enum(TipoUsuarioEnum), nullable=False)
    carrera = Column(String, nullable=True)
    departamento = Column(String, nullable=True)
    contrasena_hash = Column(String, nullable=False)
