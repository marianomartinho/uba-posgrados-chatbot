"""
Backend completo - Sistema de Posgrados UBA
FastAPI + SQLite + OpenAI + RAG
"""

import os
import time
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Imports locales
from database import (
    get_session, 
    get_stats, 
    get_programas_mas_consultados,
    registrar_consulta,
    Programa,
    Materia
)
from ai_engine import generar_respuesta, buscar_programas_avanzado

# ============== CONFIGURACIÓN ==============

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Validar API Key
if not os.getenv('OPENAI_API_KEY'):
    logger.error("⚠️  OPENAI_API_KEY no configurada")
    raise ValueError("OPENAI_API_KEY requerida")

# ============== LIFESPAN ==============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup y shutdown events"""
    logger.info("🚀 Iniciando servidor...")
    
    # Verificar que existe la BD
    if not os.path.exists('posgrados_uba.db'):
        logger.warning("⚠️  Base de datos no encontrada. Ejecutá scraper_complete.py primero.")
    else:
        session = get_session()
        stats = get_stats(session)
        logger.info(f"✅ BD cargada: {stats['total_programas']} programas, {stats['total_materias']} materias")
    
    yield
    
    logger.info("👋 Cerrando servidor...")

app = FastAPI(
    title="Posgrados UBA Derecho",
    description="Sistema de consultas con IA",
    version="2.0.0",
    lifespan=lifespan
)

# ============== MODELS ==============

class Pregunta(BaseModel):
    pregunta: str

class BusquedaAvanzada(BaseModel):
    query: str
    tipo: str | None = None
    modalidad: str | None = None

# ============== ENDPOINTS ==============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Sirve index.html"""
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("""
            <html>
                <body>
                    <h1>Sistema de Posgrados UBA</h1>
                    <p>Error: index.html no encontrado</p>
                </body>
            </html>
        """)

@app.get("/dashboard.html", response_class=HTMLResponse)
async def dashboard():
    """Sirve dashboard.html"""
    try:
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>Dashboard no disponible</h1>")

@app.get("/health")
async def health():
    """Health check"""
    session = get_session()
    stats = get_stats(session)
    
    return {
        "status": "ok",
        "database": "connected",
        "programas": stats['total_programas'],
        "materias": stats['total_materias']
    }

@app.post("/q")
async def consultar(pregunta: Pregunta, request: Request):
    """
    Endpoint principal - Consulta con IA + RAG
    """
    inicio = time.time()
    
    if not pregunta.pregunta or len(pregunta.pregunta.strip()) < 3:
        raise HTTPException(status_code=400, detail="Pregunta muy corta")
    
    try:
        # Generar respuesta usando RAG + OpenAI
        respuesta, programa_relacionado, tokens = await generar_respuesta(
            pregunta.pregunta
        )
        
        tiempo_ms = int((time.time() - inicio) * 1000)
        
        # Registrar consulta para analytics
        session = get_session()
        registrar_consulta(
            session,
            pregunta=pregunta.pregunta,
            respuesta=respuesta,
            programa=programa_relacionado,
            tiempo_ms=tiempo_ms,
            tokens=tokens
        )
        
        logger.info(f"Consulta procesada en {tiempo_ms}ms - {tokens} tokens")
        
        return {
            "respuesta": respuesta,
            "programa_relacionado": programa_relacionado,
            "tiempo_ms": tiempo_ms
        }
        
    except Exception as e:
        logger.error(f"Error procesando consulta: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/programas")
async def listar_programas(tipo: str | None = None, limit: int = 50):
    """
    Lista todos los programas
    Query params: ?tipo=maestria&limit=20
    """
    session = get_session()
    
    query = session.query(Programa)
    
    if tipo:
        query = query.filter(Programa.tipo == tipo)
    
    programas = query.limit(limit).all()
    
    return [
        {
            "id": p.id,
            "tipo": p.tipo,
            "nombre": p.nombre,
            "director": p.director,
            "email": p.email,
            "duracion": p.duracion_años,
            "carga_horaria": p.carga_horaria_total,
            "modalidad": p.modalidad
        }
        for p in programas
    ]

@app.get("/api/programas/{programa_id}")
async def detalle_programa(programa_id: int):
    """
    Detalle completo de un programa con materias
    """
    session = get_session()
    
    programa = session.query(Programa).filter_by(id=programa_id).first()
    
    if not programa:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    
    materias = session.query(Materia).filter_by(programa_id=programa_id).all()
    
    return {
        "programa": {
            "id": programa.id,
            "tipo": programa.tipo,
            "nombre": programa.nombre,
            "director": programa.director,
            "subdirector": programa.subdirector,
            "coordinador": programa.coordinador,
            "email": programa.email,
            "duracion": programa.duracion_años,
            "carga_horaria": programa.carga_horaria_total,
            "modalidad": programa.modalidad,
            "horario": programa.horario_cursada,
            "objetivos": programa.objetivos,
            "requisitos": programa.requisitos
        },
        "materias": [
            {
                "nombre": m.nombre,
                "tipo": m.tipo,
                "horas": m.carga_horaria,
                "area": m.area_tematica
            }
            for m in materias
        ],
        "total_materias": len(materias)
    }

@app.post("/api/buscar")
async def buscar(busqueda: BusquedaAvanzada):
    """
    Búsqueda avanzada de programas
    Body: {"query": "penal", "tipo": "maestria", "modalidad": "presencial"}
    """
    session = get_session()
    
    filtros = {}
    if busqueda.tipo:
        filtros['tipo'] = busqueda.tipo
    if busqueda.modalidad:
        filtros['modalidad'] = busqueda.modalidad
    
    resultados = buscar_programas_avanzado(session, busqueda.query, filtros)
    
    return [
        {
            "id": p.id,
            "tipo": p.tipo,
            "nombre": p.nombre,
            "director": p.director,
            "email": p.email
        }
        for p in resultados
    ]

@app.get("/api/estadisticas")
async def estadisticas():
    """
    Estadísticas generales del sistema
    """
    session = get_session()
    
    stats = get_stats(session)
    top_programas = get_programas_mas_consultados(session, limit=10)
    
    return {
        "general": stats,
        "programas_mas_consultados": [
            {"programa": p[0], "consultas": p[1]}
            for p in top_programas
        ]
    }

@app.get("/api/materias")
async def buscar_materias(q: str, limit: int = 20):
    """
    Búsqueda de materias por nombre
    """
    session = get_session()
    
    materias = session.query(Materia).filter(
        Materia.nombre.ilike(f'%{q}%')
    ).limit(limit).all()
    
    return [
        {
            "nombre": m.nombre,
            "programa": m.programa.nombre,
            "tipo": m.tipo,
            "horas": m.carga_horaria
        }
        for m in materias
    ]

# ============== ERROR HANDLERS ==============

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"error": "Recurso no encontrado"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(f"Error interno: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor"}
    )

# ============== MAIN ==============

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
