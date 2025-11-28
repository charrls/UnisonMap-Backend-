from fastapi import FastAPI
from app.db.init_db import init_db
from app.api.routes import usuarios
from app.api.routes import ubicaciones
from app.api.routes import edificios
from app.api.routes import conexiones
from app.api.routes import rutas
from app.api.routes import auth
from app.api.routes import importar_ubicaciones
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logging.getLogger("httpx").setLevel(logging.INFO)

app = FastAPI(title="UnisonMap API", version="1.0.0")

@app.on_event("startup")
def startup_event():
    init_db()

app.include_router(usuarios.router, prefix="/api/usuarios", tags=["usuarios"])
app.include_router(ubicaciones.router, prefix="/api", tags=["ubicaciones"])
app.include_router(edificios.router, prefix="/api", tags=["edificios"])
app.include_router(conexiones.router, prefix="/api", tags=["conexiones"])
app.include_router(rutas.router, prefix="/api", tags=["rutas"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(importar_ubicaciones.router, prefix="/api", tags=["importar_ubicaciones"])
