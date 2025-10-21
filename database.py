"""
Base de datos SQLite para Sistema de Posgrados UBA
Schema completo con relaciones
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import json

Base = declarative_base()

class Programa(Base):
    """Tabla principal - Maestrías, Especializaciones, Doctorado"""
    __tablename__ = 'programas'
    
    id = Column(Integer, primary_key=True)
    tipo = Column(String(50))  # maestria, especializacion, doctorado
    nombre = Column(String(300))
    nombre_corto = Column(String(100))  # para URLs
    url_principal = Column(String(500))
    
    # Equipo directivo
    director = Column(String(200))
    subdirector = Column(String(200))
    coordinador = Column(String(200))
    email = Column(String(200))
    telefono = Column(String(50))
    
    # Información académica
    carga_horaria_total = Column(Integer)
    duracion_años = Column(Float)
    modalidad = Column(String(50))  # presencial, virtual, hibrido
    horario_cursada = Column(String(200))
    
    # Estructura del programa
    estructura_ciclos = Column(Text)  # JSON con info de ciclos
    objetivos = Column(Text)  # Objetivos académicos
    requisitos = Column(Text)  # Requisitos de admisión (JSON)
    
    # Metadata
    ultima_actualizacion = Column(DateTime, default=datetime.now)
    activo = Column(Integer, default=1)
    
    # Relaciones
    materias = relationship("Materia", back_populates="programa", cascade="all, delete-orphan")

class Materia(Base):
    """Materias de cada programa"""
    __tablename__ = 'materias'
    
    id = Column(Integer, primary_key=True)
    programa_id = Column(Integer, ForeignKey('programas.id'))
    
    nombre = Column(String(300))
    tipo = Column(String(50))  # troncal, optativa, seminario
    area_tematica = Column(String(200))  # Ej: Parte General, Parte Especial
    carga_horaria = Column(Integer)
    ciclo = Column(String(50))  # primer_ciclo, segundo_ciclo
    descripcion = Column(Text)
    
    # Relación
    programa = relationship("Programa", back_populates="materias")

class Consulta(Base):
    """Registro de consultas del chatbot para analytics"""
    __tablename__ = 'consultas'
    
    id = Column(Integer, primary_key=True)
    pregunta = Column(Text)
    respuesta = Column(Text)
    programa_relacionado = Column(String(200))  # nombre del programa si aplica
    timestamp = Column(DateTime, default=datetime.now)
    tiempo_respuesta_ms = Column(Integer)  # milisegundos
    tokens_usados = Column(Integer)

class CacheScraping(Base):
    """Cache de páginas scrapeadas para detectar cambios"""
    __tablename__ = 'cache_scraping'
    
    id = Column(Integer, primary_key=True)
    url = Column(String(500), unique=True)
    contenido_html = Column(Text)
    hash_contenido = Column(String(64))  # SHA256
    fecha_scraping = Column(DateTime, default=datetime.now)
    status_code = Column(Integer)

# ============== FUNCIONES HELPER ==============

def init_database(db_path="posgrados_uba.db"):
    """Inicializa la base de datos"""
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session()

def get_session(db_path="posgrados_uba.db"):
    """Obtiene una sesión de BD"""
    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    return Session()

def agregar_programa(session, datos):
    """
    Agrega un programa a la BD
    
    datos = {
        'tipo': 'maestria',
        'nombre': 'Derecho Penal',
        'director': 'Edgardo Donna',
        ...
    }
    """
    programa = Programa(**datos)
    session.add(programa)
    session.commit()
    return programa.id

def agregar_materia(session, programa_id, datos):
    """
    Agrega una materia a un programa
    
    datos = {
        'nombre': 'Teoría del Delito',
        'tipo': 'troncal',
        'carga_horaria': 36,
        ...
    }
    """
    datos['programa_id'] = programa_id
    materia = Materia(**datos)
    session.add(materia)
    session.commit()
    return materia.id

def registrar_consulta(session, pregunta, respuesta, programa=None, tiempo_ms=0, tokens=0):
    """Registra una consulta del usuario"""
    consulta = Consulta(
        pregunta=pregunta,
        respuesta=respuesta,
        programa_relacionado=programa,
        tiempo_respuesta_ms=tiempo_ms,
        tokens_usados=tokens
    )
    session.add(consulta)
    session.commit()

def buscar_programas(session, query, tipo=None):
    """
    Búsqueda fuzzy de programas
    
    query: texto a buscar
    tipo: 'maestria', 'especializacion', None (todos)
    """
    q = session.query(Programa)
    
    if tipo:
        q = q.filter(Programa.tipo == tipo)
    
    # Búsqueda en nombre, director, área
    q = q.filter(
        (Programa.nombre.like(f'%{query}%')) |
        (Programa.director.like(f'%{query}%')) |
        (Programa.coordinador.like(f'%{query}%'))
    )
    
    return q.all()

def get_stats(session):
    """Obtiene estadísticas generales"""
    stats = {
        'total_programas': session.query(Programa).count(),
        'total_maestrias': session.query(Programa).filter_by(tipo='maestria').count(),
        'total_especializaciones': session.query(Programa).filter_by(tipo='especializacion').count(),
        'total_materias': session.query(Materia).count(),
        'total_consultas': session.query(Consulta).count(),
    }
    return stats

def get_programas_mas_consultados(session, limit=10):
    """Top N programas más consultados"""
    from sqlalchemy import func
    
    return session.query(
        Consulta.programa_relacionado,
        func.count(Consulta.id).label('count')
    ).filter(
        Consulta.programa_relacionado != None
    ).group_by(
        Consulta.programa_relacionado
    ).order_by(
        func.count(Consulta.id).desc()
    ).limit(limit).all()

# ============== INICIALIZACIÓN ==============

if __name__ == "__main__":
    print("🗄️  Inicializando base de datos...")
    engine, session = init_database()
    print("✅ Base de datos creada: posgrados_uba.db")
    
    stats = get_stats(session)
    print(f"\n📊 Estadísticas:")
    print(f"   Programas: {stats['total_programas']}")
    print(f"   Maestrías: {stats['total_maestrias']}")
    print(f"   Especializaciones: {stats['total_especializaciones']}")
    print(f"   Materias: {stats['total_materias']}")
    print(f"   Consultas: {stats['total_consultas']}")