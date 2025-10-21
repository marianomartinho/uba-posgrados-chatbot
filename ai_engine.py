"""
Motor de IA con RAG (Retrieval-Augmented Generation)
Búsqueda inteligente + OpenAI para respuestas precisas
"""

import os
import re
from openai import AsyncOpenAI
from database import get_session, buscar_programas, Programa, Materia
from sqlalchemy import or_, func
import logging

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ============== RAG - BÚSQUEDA INTELIGENTE ==============

def buscar_programa_relevante(query: str, session) -> dict:
    """
    Búsqueda semántica en BD antes de preguntar a IA
    Retorna datos estructurados del programa más relevante
    """
    
    # Limpiar query
    query_lower = query.lower()
    
    # Palabras clave para identificar área
    areas = {
        'penal': ['penal', 'criminal', 'delito', 'pena'],
        'civil': ['civil', 'contratos', 'obligaciones'],
        'laboral': ['trabajo', 'laboral', 'empleado', 'sindicato'],
        'familia': ['familia', 'divorcio', 'adopción', 'alimentos'],
        'tributario': ['tributario', 'impuesto', 'fiscal', 'afip'],
        'internacional': ['internacional', 'tratados', 'extranjero'],
        'administrativo': ['administrativo', 'estado', 'público'],
        'procesal': ['procesal', 'proceso', 'juicio'],
        'ambiental': ['ambiental', 'ambiente', 'ecología'],
    }
    
    # Detectar área
    area_detectada = None
    for area, keywords in areas.items():
        if any(kw in query_lower for kw in keywords):
            area_detectada = area
            break
    
    # Buscar en BD
    programas = session.query(Programa).filter(
        or_(
            Programa.nombre.ilike(f'%{query}%'),
            Programa.director.ilike(f'%{query}%'),
            Programa.coordinador.ilike(f'%{query}%')
        )
    ).all()
    
    # Si no encuentra nada, buscar por área detectada
    if not programas and area_detectada:
        programas = session.query(Programa).filter(
            Programa.nombre.ilike(f'%{area_detectada}%')
        ).all()
    
    if not programas:
        return None
    
    # Tomar el primer resultado (más relevante)
    programa = programas[0]
    
    # Obtener materias del programa
    materias = session.query(Materia).filter_by(programa_id=programa.id).all()
    
    # Construir contexto estructurado
    contexto = {
        'nombre': programa.nombre,
        'tipo': programa.tipo,
        'director': programa.director,
        'subdirector': programa.subdirector,
        'coordinador': programa.coordinador,
        'email': programa.email,
        'duracion': f"{programa.duracion_años} años" if programa.duracion_años else "No especificada",
        'carga_horaria': f"{programa.carga_horaria_total} horas" if programa.carga_horaria_total else "No especificada",
        'modalidad': programa.modalidad or "No especificada",
        'horario': programa.horario_cursada or "No especificado",
        'objetivos': programa.objetivos or "No especificados",
        'requisitos': programa.requisitos or "[]",
        'materias': [
            {
                'nombre': m.nombre,
                'tipo': m.tipo,
                'horas': m.carga_horaria,
                'area': m.area_tematica
            }
            for m in materias[:30]  # Limitar a 30 para no sobrecargar
        ],
        'total_materias': len(materias)
    }
    
    return contexto

def construir_prompt_con_contexto(pregunta: str, contexto: dict = None) -> str:
    """
    Construye prompt optimizado con contexto de BD
    """
    
    if not contexto:
        # Sin contexto específico - respuesta general
        return f"""Sos un asistente especializado en los posgrados de la Facultad de Derecho de la UBA.

Pregunta del usuario: {pregunta}

Respondé de forma clara y precisa. Si no tenés información específica sobre lo que pregunta, indicalo claramente y sugiere contactar a la Dirección de Posgrado.

Email general de Posgrado: inscripcionesposgrado@derecho.uba.ar
"""
    
    # Con contexto - respuesta específica
    materias_texto = "\n".join([
        f"   - {m['nombre']}" + (f" ({m['horas']}hs)" if m['horas'] else "") + (f" [{m['tipo']}]" if m['tipo'] else "")
        for m in contexto['materias'][:20]  # Top 20 materias
    ])
    
    prompt = f"""Sos un asistente especializado en los posgrados de la Facultad de Derecho de la UBA.

INFORMACIÓN DEL PROGRAMA CONSULTADO:

**{contexto['nombre']}** ({contexto['tipo'].upper()})

📋 DATOS GENERALES:
- Director: {contexto['director']}
- Subdirector: {contexto['subdirector']}
- Coordinador: {contexto['coordinador']}
- Email de contacto: {contexto['email']}
- Duración: {contexto['duracion']}
- Carga horaria total: {contexto['carga_horaria']}
- Modalidad: {contexto['modalidad']}
- Horario de cursada: {contexto['horario']}

📚 PLAN DE ESTUDIOS ({contexto['total_materias']} materias en total):
{materias_texto}

🎯 OBJETIVOS:
{contexto['objetivos'][:500] if contexto['objetivos'] else 'No especificados'}

✅ REQUISITOS DE ADMISIÓN:
{contexto['requisitos'][:500] if contexto['requisitos'] else 'No especificados'}

---

PREGUNTA DEL USUARIO: {pregunta}

INSTRUCCIONES:
1. Respondé usando SOLO la información que te proporcioné arriba
2. Sé específico: cita carga horaria, nombres de materias, contactos
3. Si el usuario pregunta algo que NO está en los datos, decilo claramente
4. Formato: claro, estructurado, bullets cuando corresponda
5. Incluí siempre el email de contacto relevante al final

Respondé ahora de forma directa y útil:"""
    
    return prompt

# ============== MOTOR DE IA ==============

async def generar_respuesta(pregunta: str, max_tokens: int = 800) -> tuple:
    """
    Genera respuesta usando RAG + OpenAI
    Retorna: (respuesta, programa_relacionado, tokens_usados)
    """
    
    try:
        # 1. RAG - Buscar en BD
        session = get_session()
        contexto = buscar_programa_relevante(pregunta, session)
        
        programa_relacionado = contexto['nombre'] if contexto else None
        
        # 2. Construir prompt con contexto
        prompt = construir_prompt_con_contexto(pregunta, contexto)
        
        # 3. Llamar a OpenAI
        logger.info(f"Generando respuesta para: {pregunta[:50]}...")
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Sos un asistente experto en posgrados de la UBA. Respondés de forma clara, precisa y estructurada."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_tokens,
            temperature=0.3  # Más determinista para respuestas precisas
        )
        
        respuesta = response.choices[0].message.content
        tokens_usados = response.usage.total_tokens
        
        logger.info(f"Respuesta generada. Tokens: {tokens_usados}")
        
        return respuesta, programa_relacionado, tokens_usados
        
    except Exception as e:
        logger.error(f"Error generando respuesta: {e}")
        return f"Error al procesar tu pregunta: {str(e)}", None, 0

# ============== BÚSQUEDA AVANZADA ==============

def buscar_programas_avanzado(session, query: str, filtros: dict = None):
    """
    Búsqueda avanzada con filtros
    
    filtros = {
        'tipo': 'maestria',  # o 'especializacion'
        'modalidad': 'presencial',
        'area': 'penal'
    }
    """
    
    q = session.query(Programa)
    
    # Búsqueda por texto
    if query:
        q = q.filter(
            or_(
                Programa.nombre.ilike(f'%{query}%'),
                Programa.director.ilike(f'%{query}%'),
                Programa.coordinador.ilike(f'%{query}%')
            )
        )
    
    # Aplicar filtros
    if filtros:
        if filtros.get('tipo'):
            q = q.filter(Programa.tipo == filtros['tipo'])
        
        if filtros.get('modalidad'):
            q = q.filter(Programa.modalidad == filtros['modalidad'])
        
        if filtros.get('area'):
            q = q.filter(Programa.nombre.ilike(f"%{filtros['area']}%"))
    
    return q.all()

def obtener_preguntas_frecuentes(session, limit=10):
    """
    Obtiene las preguntas más frecuentes del sistema
    """
    from sqlalchemy import func
    from database import Consulta
    
    resultado = session.query(
        Consulta.pregunta,
        func.count(Consulta.id).label('count')
    ).group_by(
        Consulta.pregunta
    ).order_by(
        func.count(Consulta.id).desc()
    ).limit(limit).all()
    
    return [{'pregunta': r[0], 'veces': r[1]} for r in resultado]