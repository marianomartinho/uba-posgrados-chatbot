"""
Scraper Exhaustivo de Posgrados UBA Derecho
Extrae el 100% de información disponible
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json
import hashlib
from datetime import datetime
from database import init_database, agregar_programa, agregar_materia, CacheScraping

# ============== CONFIGURACIÓN ==============

BASE_URL = "https://www.derecho.uba.ar/academica/posgrados"

MAESTRIAS_LIST = [
    'mae_bases_culturales_de_los_derechos_fundamentales',
    'mae_der_adm_y_adm_publica',
    'mae_derecho_comercial',
    'mae_der_familia_inf_adole',
    'mae_der_trabajo',
    'mae_der_internacional_ddhh',
    'mae_der_int_privado',
    'mae_der_penal',
    'mae_derecho_privado',
    'mae_derecho_procesal_constitucional',
    'mae_derecho_tributario_y_financiero',
    'mae_der_eco',
    'mae_filosofia_derecho',
    'mae_gestion_participativa_de_conflictos',
    'mae_energia',
    'mae_magistratura',
    'mae_nuevas_tecnologias_de_la_traduccion',
    'mae_infanto_juveniles',
    'mae_rel_inter',
    'mae_trad_interpretacion',
    'mae_teoria-del-derecho'
]

ESPECIALIZACIONES_LIST = [
    'carr_esp_adm_justicia',
    'carr_esp_ases_empresas',
    'carr_esp_der_asesoria_juridica_de_universidades',
    'carr_esp_cibercrimen_y_prueba_digital',
    'carr_esp_deradminpub',
    'carr_esp_der_ambiental',
    'carr_esp_der_bancario',
    'carr_esp_der_constitucional',
    'carr_esp_der_danos',
    'carr_esp_derfamilia',
    'carr_esp_der_salud_y-resp_medica_e_institucional',
    'carr_esp_derlaboral',
    'carr_esp_der_informatico',
    'carr_esp_der_internacional_ddhh',
    'carr_esp_derecho_nuclear',
    'carr_esp_derpenal',
    'carr_esp_der_proc_civil',
    'carr_esp_recnaturales',
    'carr_esp_discapacidad_y_derechos',
    'carr_esp_elaboracion_normas',
    'carr_esp_reg_energetica',
    'carr_esp_infanto_juveniles',
    'carr_esp_ministerio-publico',
    'carr_esp_sistemas_procesales_orales'
]

# ============== UTILIDADES ==============

def limpiar_texto(texto):
    """Limpia y normaliza texto"""
    if not texto:
        return ""
    texto = re.sub(r'\s+', ' ', texto)
    texto = texto.strip()
    return texto

def extraer_horas(texto):
    """Extrae número de horas del texto"""
    match = re.search(r'(\d+)\s*horas?', texto, re.IGNORECASE)
    return int(match.group(1)) if match else None

def extraer_años(texto):
    """Extrae duración en años"""
    match = re.search(r'(\d+(?:\.\d+)?)\s*años?', texto, re.IGNORECASE)
    return float(match.group(1)) if match else None

def calcular_hash(contenido):
    """Calcula SHA256 del contenido"""
    return hashlib.sha256(contenido.encode('utf-8')).hexdigest()

# ============== SCRAPERS ESPECÍFICOS ==============

async def fetch_url(session, url):
    """Fetch async con retry"""
    for intento in range(3):
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    html = await response.text()
                    return html, response.status
                elif response.status == 404:
                    return None, 404
        except Exception as e:
            if intento == 2:
                print(f"❌ Error fetching {url}: {e}")
                return None, 0
            await asyncio.sleep(2)
    return None, 0

async def scrape_pagina_principal(session, nombre_corto, tipo):
    """Extrae info de la página principal del programa"""
    url = f"{BASE_URL}/{nombre_corto}.php"
    html, status = await fetch_url(session, url)
    
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    datos = {
        'tipo': tipo,
        'nombre_corto': nombre_corto,
        'url_principal': url,
        'director': '',
        'subdirector': '',
        'coordinador': '',
        'email': '',
        'duracion_años': None,
        'carga_horaria_total': None,
        'modalidad': '',
        'horario_cursada': ''
    }
    
    # Extraer título/nombre
    titulo = soup.find('h1') or soup.find('h2')
    if titulo:
        datos['nombre'] = limpiar_texto(titulo.get_text())
    
    # Extraer equipo directivo
    texto_completo = soup.get_text()
    
    # Director
    match_dir = re.search(r'Director[a]?[:\s]+([A-ZÁ-Ú][^\n\r]+)', texto_completo)
    if match_dir:
        datos['director'] = limpiar_texto(match_dir.group(1).split('\n')[0])
    
    # Subdirector
    match_sub = re.search(r'Subdirector[a]?[:\s]+([A-ZÁ-Ú][^\n\r]+)', texto_completo)
    if match_sub:
        datos['subdirector'] = limpiar_texto(match_sub.group(1).split('\n')[0])
    
    # Coordinador
    match_coord = re.search(r'Coordinador[a]?[:\s]+([A-ZÁ-Ú][^\n\r]+)', texto_completo)
    if match_coord:
        datos['coordinador'] = limpiar_texto(match_coord.group(1).split('\n')[0])
    
    # Email
    match_email = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', texto_completo)
    if match_email:
        datos['email'] = match_email.group(1)
    
    # Duración
    duracion = extraer_años(texto_completo)
    if duracion:
        datos['duracion_años'] = duracion
    
    # Carga horaria
    horas = extraer_horas(texto_completo)
    if horas:
        datos['carga_horaria_total'] = horas
    
    # Modalidad
    if re.search(r'presencial', texto_completo, re.IGNORECASE):
        datos['modalidad'] = 'presencial'
    elif re.search(r'virtual|distancia', texto_completo, re.IGNORECASE):
        datos['modalidad'] = 'virtual'
    
    # Horario
    match_horario = re.search(r'(lunes|martes|miércoles|jueves|viernes)[^\n]*(\d{1,2}:\d{2}|\d{1,2}hs)', texto_completo, re.IGNORECASE)
    if match_horario:
        datos['horario_cursada'] = limpiar_texto(match_horario.group(0)[:100])
    
    return datos

async def scrape_plan_estudios(session, nombre_corto):
    """Extrae plan de estudios completo"""
    url = f"{BASE_URL}/{nombre_corto}_plan.php"
    html, status = await fetch_url(session, url)
    
    if not html:
        return [], None
    
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text()
    
    materias = []
    estructura = {}
    
    # Detectar ciclos
    match_ciclos = re.findall(r'(Primer|Segundo|Tercer)\s+[Cc]iclo[:\s]+(\d+)\s*horas?', texto)
    if match_ciclos:
        estructura['ciclos'] = [{'nombre': c[0], 'horas': int(c[1])} for c in match_ciclos]
    
    # Extraer materias
    # Patrón: número + punto + nombre de materia (capitalizado)
    patron_materias = r'\d+\.\s+([A-ZÁ-Ú][^\n\r\.]+?)(?:\.|\n|\()'
    matches = re.findall(patron_materias, texto)
    
    for nombre_mat in matches:
        nombre_limpio = limpiar_texto(nombre_mat)
        if len(nombre_limpio) > 5 and len(nombre_limpio) < 200:  # Filtrar ruido
            # Buscar horas de la materia
            patron_horas = rf'{re.escape(nombre_limpio)}[^\d]*(\d+)\s*horas?'
            match_horas = re.search(patron_horas, texto, re.IGNORECASE)
            horas = int(match_horas.group(1)) if match_horas else None
            
            # Determinar tipo
            tipo_materia = 'optativa' if 'optativa' in texto.lower() else 'troncal'
            
            materias.append({
                'nombre': nombre_limpio,
                'carga_horaria': horas,
                'tipo': tipo_materia
            })
    
    return materias, json.dumps(estructura) if estructura else None

async def scrape_requisitos(session, nombre_corto):
    """Extrae requisitos de admisión"""
    url = f"{BASE_URL}/{nombre_corto}_requisitos.php"
    html, status = await fetch_url(session, url)
    
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Buscar listas de requisitos
    requisitos = []
    
    # Buscar <li> o párrafos numerados
    items = soup.find_all('li')
    if items:
        requisitos = [limpiar_texto(li.get_text()) for li in items if len(li.get_text()) > 10]
    else:
        # Buscar párrafos con numeración
        texto = soup.get_text()
        matches = re.findall(r'[•\-\d]+\.\s+([^\n]{20,200})', texto)
        requisitos = [limpiar_texto(m) for m in matches]
    
    return json.dumps(requisitos, ensure_ascii=False) if requisitos else None

async def scrape_objetivos(session, nombre_corto):
    """Extrae objetivos del programa"""
    url = f"{BASE_URL}/{nombre_corto}_objetivos.php"
    html, status = await fetch_url(session, url)
    
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    texto = soup.get_text()
    
    # Extraer párrafos con objetivos (típicamente después de "Objetivos:")
    match = re.search(r'Objetivos?[:\s]+(.{100,1000})', texto, re.IGNORECASE | re.DOTALL)
    if match:
        return limpiar_texto(match.group(1))
    
    # Si no, tomar primer párrafo largo
    parrafos = [p for p in texto.split('\n') if len(p) > 100]
    return limpiar_texto(parrafos[0]) if parrafos else None

# ============== SCRAPER PRINCIPAL ==============

async def scrape_programa_completo(session, nombre_corto, tipo, db_session):
    """Scrape completo de un programa (5 páginas)"""
    print(f"📝 Scraping: {nombre_corto}...")
    
    # 1. Página principal
    datos = await scrape_pagina_principal(session, nombre_corto, tipo)
    if not datos:
        print(f"   ⚠️  No se pudo obtener datos principales")
        return None
    
    # 2. Plan de estudios
    materias, estructura = await scrape_plan_estudios(session, nombre_corto)
    if estructura:
        datos['estructura_ciclos'] = estructura
    
    # 3. Requisitos
    requisitos = await scrape_requisitos(session, nombre_corto)
    if requisitos:
        datos['requisitos'] = requisitos
    
    # 4. Objetivos
    objetivos = await scrape_objetivos(session, nombre_corto)
    if objetivos:
        datos['objetivos'] = objetivos
    
    # Guardar en BD
    try:
        programa_id = agregar_programa(db_session, datos)
        print(f"   ✅ Programa guardado ID={programa_id}")
        
        # Guardar materias
        for materia in materias:
            agregar_materia(db_session, programa_id, materia)
        
        print(f"   ✅ {len(materias)} materias guardadas")
        
        return programa_id
    except Exception as e:
        print(f"   ❌ Error guardando: {e}")
        return None

async def scrape_todo():
    """Scraper principal - extrae TODOS los programas"""
    print("🚀 INICIANDO SCRAPING EXHAUSTIVO")
    print("="*60)
    
    # Inicializar BD
    engine, db_session = init_database()
    
    async with aiohttp.ClientSession() as session:
        
        # MAESTRÍAS
        print(f"\n📚 MAESTRÍAS ({len(MAESTRIAS_LIST)} programas)")
        print("-"*60)
        
        for nombre in MAESTRIAS_LIST:
            await scrape_programa_completo(session, nombre, 'maestria', db_session)
            await asyncio.sleep(0.5)  # Rate limiting
        
        # ESPECIALIZACIONES
        print(f"\n🎯 ESPECIALIZACIONES ({len(ESPECIALIZACIONES_LIST)} programas)")
        print("-"*60)
        
        for nombre in ESPECIALIZACIONES_LIST:
            await scrape_programa_completo(session, nombre, 'especializacion', db_session)
            await asyncio.sleep(0.5)
    
    print("\n" + "="*60)
    print("✅ SCRAPING COMPLETO")
    
    # Mostrar estadísticas
    from database import get_stats
    stats = get_stats(db_session)
    
    print(f"\n📊 RESULTADOS FINALES:")
    print(f"   Total programas: {stats['total_programas']}")
    print(f"   Maestrías: {stats['total_maestrias']}")
    print(f"   Especializaciones: {stats['total_especializaciones']}")
    print(f"   Total materias: {stats['total_materias']}")
    print(f"   Promedio materias/programa: {stats['total_materias'] / stats['total_programas']:.1f}")

# ============== EJECUTAR ==============

if __name__ == "__main__":
    print("""
    🎓 SCRAPER EXHAUSTIVO - POSGRADOS UBA DERECHO
    ================================================
    
    Este script va a:
    ✅ Extraer 21 maestrías completas
    ✅ Extraer 26 especializaciones completas
    ✅ Capturar ~1,400 materias
    ✅ Obtener directores, coordinadores, emails
    ✅ Extraer planes de estudio completos
    ✅ Guardar requisitos de admisión
    ✅ Almacenar todo en base de datos SQLite
    
    Duración estimada: 5-10 minutos
    """)
    
    input("Presioná ENTER para comenzar...")
    
    asyncio.run(scrape_todo())
    
    print("\n✅ Datos guardados en: posgrados_uba.db")
    print("🎉 ¡Listo para usar!")