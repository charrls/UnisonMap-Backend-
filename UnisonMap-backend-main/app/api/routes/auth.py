from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from app.dependencies.auth import get_current_user
from app.schemas.usuario import UsuarioOut
from app.db.session import get_db 
from app.models.usuario import Usuario
from app.core.security import verificar_password, crear_token_acceso, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()

@router.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.correo == form_data.username).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    
    if not form_data.username.endswith("@unison.mx"):
        raise HTTPException(status_code=400, detail="Solo se permiten correos @unison.mx")

    if not verificar_password(form_data.password, usuario.contrasena_hash):
        raise HTTPException(status_code=400, detail="Contraseña incorrecta")

    token = crear_token_acceso(
        data={"sub": usuario.correo, "id": usuario.id, "tipo": usuario.tipo_usuario},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {"access_token": token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UsuarioOut)
def obtener_usuario_actual(usuario: Usuario = Depends(get_current_user)):
    return usuario
