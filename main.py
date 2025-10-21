"""
Sistema IA Posgrados UBA Derecho
Backend minimalista
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("OPENAI_API_KEY no configurada")

client = OpenAI(api_key=API_KEY)

URLS_UBA = [
    "https://www.derecho.uba.ar/academica/posgrados/maestrias.php",
    "https://www.derecho.uba.ar/academica/posgrados/carr_especializacion.php",
    "https://www.derecho.uba.ar/academica/posgrados/doctorado.php",
    "https://www.derecho.uba.ar/academica/posgrados/index.php"
]

scraping_cache = {"data": "", "timestamp": None, "ttl_hours": 24}

async def scrape_uba():
    if scraping_cache["data"] and scraping_cache["timestamp"]:
        age = datetime.now() - scraping_cache["timestamp"]
        if age < timedelta(hours=scraping_cache["ttl_hours"]):
            logger.info(f"Usando cache")
            return scraping_cache["data"]
    
    logger.info("Iniciando scraping...")
    datos = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for url in URLS_UBA:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        for script in soup(["script", "style"]):
                            script.decompose()
                        texto = soup.get_text(separator='\n', strip=True)
                        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
                        texto_limpio = '\n'.join(lineas)
                        datos.append(texto_limpio[:8000])
                        logger.info(f"OK {url}")
            except Exception as e:
                logger.error(f"Error {url}: {e}")
            await asyncio.sleep(1)
    
    contexto = "\n\n".join(datos)
    scraping_cache["data"] = contexto
    scraping_cache["timestamp"] = datetime.now()
    logger.info(f"Scraping completo: {len(contexto)} chars")
    return contexto

async def get_context():
    if not scraping_cache["data"]:
        await scrape_uba()
    return scraping_cache["data"]

def ask_ai(pregunta, contexto):
    try:
        system_prompt = f"""Eres un asistente experto en posgrados de la Facultad de Derecho UBA.

Informacion disponible:
{contexto[:12000]}

Instrucciones:
- Responde solo con info del contexto
- Si no sabes, di "No tengo esa informacion"
- Se conciso y claro
- Usa bullets cuando sea util
- Se amable"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.3,
            max_tokens=600
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error OpenAI: {e}")
        return "Error al procesar tu pregunta."

app = FastAPI(title="UBA Posgrados AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class Pregunta(BaseModel):
    pregunta: str

@app.on_event("startup")
async def startup_event():
    logger.info("Iniciando servidor...")
    try:
        await scrape_uba()
        logger.info("Cache inicializado")
    except Exception as e:
        logger.error(f"Error init: {e}")

@app.get("/")
async def home():
    index_path = Path(__file__).parent / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"error": "index.html no encontrado"}

@app.post("/q")
async def consultar(pregunta: Pregunta):
    if not pregunta.pregunta or len(pregunta.pregunta.strip()) < 3:
        raise HTTPException(status_code=400, detail="Pregunta muy corta")
    try:
        contexto = await get_context()
        respuesta = ask_ai(pregunta.pregunta, contexto)
        logger.info(f"Pregunta: {pregunta.pregunta[:50]}")
        return {"respuesta": respuesta}
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
