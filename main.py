"""
🎓 Sistema IA Posgrados UBA Derecho
Production-ready version for Railway deployment
VERSIÓN CORREGIDA - Endpoint /q
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
import logging

# ============================================
# CONFIGURACIÓN
# ============================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI API Key desde variable de entorno
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise ValueError("⚠️ OPENAI_API_KEY no configurada en variables de entorno")

client = OpenAI(api_key=API_KEY)

# URLs a scrapear
URLS_UBA = [
    "https://www.derecho.uba.ar/academica/posgrados/maestrias.php",
    "https://www.derecho.uba.ar/academica/posgrados/carr_especializacion.php",
    "https://www.derecho.uba.ar/academica/posgrados/doctorado.php",
    "https://www.derecho.uba.ar/academica/posgrados/index.php"
]

# Cache del scraping
scraping_cache = {
    "data": "",
    "timestamp": None,
    "ttl_hours": 24  # Re-scrapear cada 24 horas
}

# ============================================
# WEB SCRAPING
# ============================================

async def scrape_uba() -> str:
    """
    Scrapea información de páginas UBA con caché inteligente
    """
    # Verificar si hay cache válido
    if scraping_cache["data"] and scraping_cache["timestamp"]:
        age = datetime.now() - scraping_cache["timestamp"]
        if age < timedelta(hours=scraping_cache["ttl_hours"]):
            logger.info(f"✅ Usando cache (edad: {age.seconds//3600}h)")
            return scraping_cache["data"]
    
    logger.info("🕷️ Iniciando scraping de UBA...")
    datos = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        for url in URLS_UBA:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Remover scripts y styles
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        # Extraer texto limpio
                        texto = soup.get_text(separator='\n', strip=True)
                        
                        # Limpieza básica
                        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
                        texto_limpio = '\n'.join(lineas)
                        
                        # Tomar primeros 8000 caracteres por página
                        datos.append(f"=== {url} ===\n{texto_limpio[:8000]}")
                        logger.info(f"  ✅ {url} - {len(texto_limpio)} chars")
                    else:
                        logger.warning(f"  ⚠️ {url} - Status {response.status}")
            except Exception as e:
                logger.error(f"  ❌ {url} - Error: {str(e)}")
            
            # Rate limiting
            await asyncio.sleep(1)
    
    contexto = "\n\n".join(datos)
    
    # Actualizar cache
    scraping_cache["data"] = contexto
    scraping_cache["timestamp"] = datetime.now()
    
    logger.info(f"✅ Scraping completo: {len(contexto)} caracteres en cache")
    return contexto

# ============================================
# SISTEMA DE IA
# ============================================

async def get_context() -> str:
    """Obtiene contexto (con cache)"""
    if not scraping_cache["data"]:
        await scrape_uba()
    return scraping_cache["data"]

def ask_ai(pregunta: str, contexto: str) -> str:
    """
    Envía pregunta a OpenAI con contexto
    """
    try:
        system_prompt = f"""Eres un asistente experto en posgrados de la Facultad de Derecho de la Universidad de Buenos Aires (UBA).

Tu trabajo es ayudar a estudiantes y profesionales a encontrar información sobre:
- Maestrías
- Especializaciones  
- Doctorados
- Directores de programas
- Requisitos de inscripción
- Contactos

INFORMACIÓN DISPONIBLE:
{contexto[:12000]}

INSTRUCCIONES:
- Responde SOLO con información del contexto proporcionado
- Si no sabes algo, di "No tengo esa información en mi base de datos actual"
- Sé conciso pero completo
- Usa formato legible (bullets, números)
- Si mencionas contactos, incluye emails/teléfonos si los hay
- Siempre sé amable y profesional"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pregunta}
            ],
            temperature=0.3,
            max_tokens=600,
            top_p=0.9
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error OpenAI: {e}")
        return f"⚠️ Error al procesar tu pregunta. Por favor, intenta nuevamente."

# ============================================
# API FASTAPI
# ============================================

app = FastAPI(
    title="UBA Posgrados AI Assistant",
    description="Chatbot inteligente para consultas sobre posgrados UBA Derecho",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Pregunta(BaseModel):
    pregunta: str

# ============================================
# ENDPOINTS
# ============================================

@app.on_event("startup")
async def startup_event():
    """Inicializar cache al arrancar"""
    logger.info("🚀 Iniciando servidor...")
    try:
        await scrape_uba()
        logger.info("✅ Cache inicializado correctamente")
    except Exception as e:
        logger.error(f"⚠️ Error inicializando cache: {e}")

@app.get("/", response_class=HTMLResponse)
async def home():
    """Frontend del chatbot"""
    return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎓 Posgrados UBA Derecho - Asistente IA</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            width: 100%;
            max-width: 900px;
            height: 90vh;
            max-height: 800px;
            background: white;
            border-radius: 24px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.25);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px;
            text-align: center;
            border-bottom: 3px solid rgba(255,255,255,0.2);
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 8px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            background: #f8f9fa;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .message {
            display: flex;
            gap: 12px;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .message.user {
            flex-direction: row-reverse;
        }
        
        .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .message.bot .avatar {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        
        .message.user .avatar {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        
        .bubble {
            max-width: 70%;
            padding: 14px 18px;
            border-radius: 18px;
            line-height: 1.5;
            font-size: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        
        .message.bot .bubble {
            background: white;
            border: 1px solid #e0e0e0;
            color: #333;
        }
        
        .message.user .bubble {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .suggestions {
            padding: 16px 24px;
            background: white;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 8px;
            overflow-x: auto;
            flex-wrap: wrap;
        }
        
        .suggestion-btn {
            padding: 8px 16px;
            background: #f0f0f0;
            border: 1px solid #ddd;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .suggestion-btn:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 12px;
            color: #667eea;
            font-style: italic;
        }
        
        .input-area {
            padding: 20px 24px;
            background: white;
            border-top: 2px solid #e0e0e0;
            display: flex;
            gap: 12px;
            align-items: center;
        }
        
        #userInput {
            flex: 1;
            padding: 12px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 24px;
            font-size: 15px;
            outline: none;
            transition: border-color 0.2s;
        }
        
        #userInput:focus {
            border-color: #667eea;
        }
        
        #sendBtn {
            padding: 12px 28px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 24px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            font-size: 15px;
        }
        
        #sendBtn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        #sendBtn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        @media (max-width: 768px) {
            .container {
                height: 100vh;
                max-height: none;
                border-radius: 0;
            }
            
            .bubble {
                max-width: 85%;
            }
            
            .header h1 {
                font-size: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 Asistente de Posgrados UBA Derecho</h1>
            <p>Pregúntame sobre maestrías, especializaciones y doctorados</p>
        </div>
        
        <div class="messages" id="messages">
            <div class="message bot">
                <div class="avatar">🤖</div>
                <div class="bubble">
                    ¡Hola! Soy tu asistente virtual de posgrados de la Facultad de Derecho UBA.<br><br>
                    Puedo ayudarte con información sobre:<br>
                    • Maestrías y especializaciones disponibles<br>
                    • Requisitos de inscripción<br>
                    • Directores y contactos<br>
                    • Planes de estudio<br><br>
                    ¿En qué puedo ayudarte?
                </div>
            </div>
        </div>
        
        <div class="suggestions">
            <button class="suggestion-btn" onclick="sendSuggestion('¿Qué maestrías hay disponibles?')">📚 Maestrías</button>
            <button class="suggestion-btn" onclick="sendSuggestion('¿Qué especializaciones ofrecen?')">🎯 Especializaciones</button>
            <button class="suggestion-btn" onclick="sendSuggestion('Requisitos para el doctorado')">🎓 Doctorado</button>
            <button class="suggestion-btn" onclick="sendSuggestion('¿Cómo me inscribo?')">✍️ Inscripción</button>
        </div>
        
        <div class="loading" id="loading">Pensando...</div>
        
        <div class="input-area">
            <input 
                type="text" 
                id="userInput" 
                placeholder="Escribe tu pregunta aquí..."
                autocomplete="off"
            />
            <button id="sendBtn">Enviar</button>
        </div>
    </div>

    <script>
        const messagesDiv = document.getElementById('messages');
        const userInput = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        const loading = document.getElementById('loading');

        function addMessage(text, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'bot'}`;
            
            const avatar = document.createElement('div');
            avatar.className = 'avatar';
            avatar.textContent = isUser ? '👤' : '🤖';
            
            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.innerHTML = text.replace(/\n/g, '<br>');
            
            messageDiv.appendChild(avatar);
            messageDiv.appendChild(bubble);
            messagesDiv.appendChild(messageDiv);
            
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        async function sendMessage() {
            const pregunta = userInput.value.trim();
            if (!pregunta) return;

            addMessage(pregunta, true);
            userInput.value = '';
            sendBtn.disabled = true;
            loading.style.display = 'block';

            try {
                const response = await fetch('/q', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ pregunta })
                });

                const data = await response.json();
                
                if (response.ok) {
                    addMessage(data.respuesta, false);
                } else {
                    addMessage('❌ Error: ' + (data.detail || 'No se pudo procesar tu pregunta'), false);
                }
            } catch (error) {
                addMessage('❌ Error de conexión. Por favor, intenta nuevamente.', false);
            } finally {
                sendBtn.disabled = false;
                loading.style.display = 'none';
            }
        }

        function sendSuggestion(text) {
            userInput.value = text;
            sendMessage();
        }

        sendBtn.onclick = sendMessage;
        userInput.onkeypress = (e) => {
            if (e.key === 'Enter') sendMessage();
        };

        // Focus en input al cargar
        userInput.focus();
    </script>
</body>
</html>"""

@app.post("/q")
async def consultar(pregunta: Pregunta):
    """
    Endpoint principal para consultas
    """
    if not pregunta.pregunta or len(pregunta.pregunta.strip()) < 3:
        raise HTTPException(status_code=400, detail="Pregunta muy corta")
    
    try:
        contexto = await get_context()
        respuesta = ask_ai(pregunta.pregunta, contexto)
        
        logger.info(f"✅ Pregunta procesada: {pregunta.pregunta[:50]}...")
        
        return {"respuesta": respuesta}
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/health")
async def health():
    """Health check para monitoring"""
    cache_age = None
    if scraping_cache["timestamp"]:
        age = datetime.now() - scraping_cache["timestamp"]
        cache_age = f"{age.seconds // 3600}h {(age.seconds % 3600) // 60}m"
    
    return {
        "status": "healthy",
        "cache_size": len(scraping_cache["data"]),
        "cache_age": cache_age,
        "openai_configured": bool(API_KEY)
    }

@app.post("/refresh-cache")
async def refresh_cache():
    """Forzar actualización del cache"""
    try:
        await scrape_uba()
        return {"status": "success", "message": "Cache actualizado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENTRY POINT
# ============================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
