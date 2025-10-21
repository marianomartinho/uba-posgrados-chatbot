"""
Sistema IA Posgrados UBA Derecho
Version FINAL - Sin errores
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
            logger.info(f"Usando cache ({age.seconds//3600}h)")
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
                        datos.append(f"=== {url} ===\n{texto_limpio[:8000]}")
                        logger.info(f"OK {url}")
                    else:
                        logger.warning(f"Status {response.status}: {url}")
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
- Se amable y profesional"""

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
        return "Error al procesar tu pregunta. Intenta nuevamente."

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

@app.get("/", response_class=HTMLResponse)
async def home():
    html = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Posgrados UBA Derecho</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.container{width:100%;max-width:900px;height:90vh;max-height:800px;background:#fff;border-radius:24px;box-shadow:0 25px 50px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:24px;text-align:center}
.header h1{font-size:24px;font-weight:700;margin-bottom:8px}
.header p{opacity:.9;font-size:14px}
.messages{flex:1;overflow-y:auto;padding:24px;background:#f8f9fa;display:flex;flex-direction:column;gap:16px}
.message{display:flex;gap:12px;animation:fadeIn .3s}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.message.user{flex-direction:row-reverse}
.avatar{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.message.bot .avatar{background:linear-gradient(135deg,#667eea,#764ba2)}
.message.user .avatar{background:linear-gradient(135deg,#11998e,#38ef7d)}
.bubble{max-width:70%;padding:14px 18px;border-radius:18px;line-height:1.5;font-size:15px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.message.bot .bubble{background:#fff;border:1px solid #e0e0e0;color:#333}
.message.user .bubble{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.suggestions{padding:16px 24px;background:#fff;border-top:1px solid #e0e0e0;display:flex;gap:8px;overflow-x:auto;flex-wrap:wrap}
.suggestion-btn{padding:8px 16px;background:#f0f0f0;border:1px solid #ddd;border-radius:20px;font-size:13px;cursor:pointer;transition:all .2s;white-space:nowrap}
.suggestion-btn:hover{background:#667eea;color:#fff;border-color:#667eea}
.loading{display:none;text-align:center;padding:12px;color:#667eea;font-style:italic}
.input-area{padding:20px 24px;background:#fff;border-top:2px solid #e0e0e0;display:flex;gap:12px;align-items:center}
#userInput{flex:1;padding:12px 20px;border:2px solid #e0e0e0;border-radius:24px;font-size:15px;outline:none;transition:border-color .2s}
#userInput:focus{border-color:#667eea}
#sendBtn{padding:12px 28px;background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border:none;border-radius:24px;font-weight:600;cursor:pointer;transition:transform .2s;font-size:15px}
#sendBtn:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 4px 12px rgba(102,126,234,.4)}
#sendBtn:disabled{opacity:.6;cursor:not-allowed}
@media (max-width:768px){
.container{height:100vh;border-radius:0}
.bubble{max-width:85%}
.header h1{font-size:20px}
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
<div class="bubble">¡Hola! Soy tu asistente virtual de posgrados UBA Derecho.<br><br>Puedo ayudarte con:<br>• Maestrías y especializaciones<br>• Requisitos de inscripción<br>• Directores y contactos<br>• Planes de estudio<br><br>¿En qué puedo ayudarte?</div>
</div>
</div>
<div class="suggestions">
<button class="suggestion-btn" onclick="sendSuggestion('Que maestrias hay disponibles')">📚 Maestrías</button>
<button class="suggestion-btn" onclick="sendSuggestion('Que especializaciones ofrecen')">🎯 Especializaciones</button>
<button class="suggestion-btn" onclick="sendSuggestion('Requisitos para el doctorado')">🎓 Doctorado</button>
<button class="suggestion-btn" onclick="sendSuggestion('Como me inscribo')">✍️ Inscripción</button>
</div>
<div class="loading" id="loading">Pensando...</div>
<div class="input-area">
<input type="text" id="userInput" placeholder="Escribe tu pregunta aqui..." autocomplete="off"/>
<button id="sendBtn">Enviar</button>
</div>
</div>
<script>
const m=document.getElementById('messages');
const inp=document.getElementById('userInput');
const btn=document.getElementById('sendBtn');
const load=document.getElementById('loading');
function addMsg(txt,isUser){
const div=document.createElement('div');
div.className='message '+(isUser?'user':'bot');
const av=document.createElement('div');
av.className='avatar';
av.textContent=isUser?'👤':'🤖';
const bub=document.createElement('div');
bub.className='bubble';
bub.innerHTML=txt.replace(/\\n/g,'<br>');
div.appendChild(av);
div.appendChild(bub);
m.appendChild(div);
m.scrollTop=m.scrollHeight;
}
async function send(){
const q=inp.value.trim();
if(!q)return;
addMsg(q,true);
inp.value='';
btn.disabled=true;
load.style.display='block';
try{
const r=await fetch('/q',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({pregunta:q})
});
const d=await r.json();
if(r.ok){
addMsg(d.respuesta,false);
}else{
addMsg('Error: '+(d.detail||'No se pudo procesar'),false);
}
}catch(e){
addMsg('Error de conexion. Intenta nuevamente.',false);
}finally{
btn.disabled=false;
load.style.display='none';
}
}
function sendSuggestion(txt){
inp.value=txt;
send();
}
btn.onclick=send;
inp.onkeypress=e=>{if(e.key==='Enter')send()};
inp.focus();
</script>
</body>
</html>"""
    return html

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
    cache_age = None
    if scraping_cache["timestamp"]:
        age = datetime.now() - scraping_cache["timestamp"]
        cache_age = f"{age.seconds//3600}h {(age.seconds%3600)//60}m"
    return {
        "status": "healthy",
        "cache_size": len(scraping_cache["data"]),
        "cache_age": cache_age,
        "openai_configured": bool(API_KEY)
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
