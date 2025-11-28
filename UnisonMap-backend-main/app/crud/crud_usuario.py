from sqlalchemy.orm import Session
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_email(db: Session, correo: str):
    return db.query(Usuario).filter(Usuario.correo == correo).first()

def create_user(db: Session, user: UsuarioCreate):
    hashed_password = pwd_context.hash(user.contrasena)
    db_user = Usuario(
        correo=user.correo,
        nombres=user.nombres,
        apellidos=user.apellidos,
        tipo_usuario=user.tipo_usuario,
        carrera=user.carrera,
        departamento=user.departamento,
        contrasena_hash=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user
