from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.usuario import UsuarioCreate, UsuarioOut
from app.crud import crud_usuario
from app.db.session import get_db 

router = APIRouter()

@router.post("/register", response_model=UsuarioOut)
def register_user(user: UsuarioCreate, db: Session = Depends(get_db)):
    db_user = crud_usuario.get_user_by_email(db, correo=user.correo)
    if db_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    return crud_usuario.create_user(db, user)


