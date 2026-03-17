import os
import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from azure.cosmos import CosmosClient, exceptions
from passlib.context import CryptContext
from jose import JWTError, jwt
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv("Conexion_Azure.env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("psicoia-backend")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://purple-cliff-0fa98ff0f.1.azurestaticapps.net",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------------------------------------------------------------------------
# COSMOS DB
# ---------------------------------------------------------------------------
cosmos_client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
db = cosmos_client.get_database_client("psicoia-db")

c_usuarios      = db.get_container_client("usuarios")
c_sesiones      = db.get_container_client("sesiones")
c_detalle       = db.get_container_client("sesiones_detalle")
c_instituciones = db.get_container_client("instituciones")
c_casos         = db.get_container_client("casos")
c_pagos         = db.get_container_client("pagos")
c_config        = db.get_container_client("config")

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
SECRET_KEY   = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 60 * 8

pwd_ctx       = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(p):        return pwd_ctx.hash(p)
def verify_password(p, h):   return pwd_ctx.verify(p, h)
def create_token(data):
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode({**data, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email   = payload.get("sub")
        rol     = payload.get("rol")
        if not email: raise HTTPException(status_code=401, detail="Token inválido")
        return {"email": email, "rol": rol}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

def require_admin(user=Depends(get_current_user)):
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso solo para administradores")
    return user

# ---------------------------------------------------------------------------
# MODELOS
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    nombre: str; email: str; password: str; rol: str = "estudiante"

class NewSessionRequest(BaseModel):
    patient_id: Optional[str] = None

class MessageRequest(BaseModel):
    session_id: str; message: str

class SessionResponse(BaseModel):
    session_id: str

class InstitucionCreate(BaseModel):
    nombre: str
    nit: Optional[str] = None
    contacto: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    ciudad: Optional[str] = None
    dominio: Optional[str] = None

class SuscripcionUpdate(BaseModel):
    plan: Optional[str] = None
    suscripcion_estado: Optional[str] = None
    sus_inicio: Optional[str] = None
    sus_fin: Optional[str] = None
    sus_monto: Optional[float] = None
    sus_notas: Optional[str] = None

class ContratoUpdate(BaseModel):
    ct_numero: Optional[str] = None
    ct_fecha: Optional[str] = None
    ct_vigencia: Optional[int] = None
    ct_desc: Optional[str] = None

class CasoCreate(BaseModel):
    name: str; age: int
    descripcion: Optional[str] = None
    instruccion: str
    instruccion_feedback: str
    categoria: Optional[str] = "General"
    dificultad: Optional[str] = "Leve"
    specialty_hint: Optional[str] = None

class CategoriaCreate(BaseModel):
    nombre: str

class PagoCreate(BaseModel):
    tipo: str; origen: str
    origen_id: Optional[str] = None
    monto: float; fecha: str
    metodo: Optional[str] = None
    referencia: Optional[str] = None
    estado: Optional[str] = "confirmado"

class ConfigUpdate(BaseModel):
    valor: str

class VincularUsuario(BaseModel):
    email: str; rol: str; institucion_id: str


class AltaRequest(BaseModel):
    sesion_id: str
    reflexion: Optional[str] = None

class CheckAltaRequest(BaseModel):
    session_id: str

# ---------------------------------------------------------------------------
# SEEDS
# ---------------------------------------------------------------------------
PATIENT_PROFILES_SEED = {
    "mateo": {
        "caso_id": "mateo", "name": "Mateo", "age": 22,
        "descripcion": "Joven universitario introvertido, asiste a terapia obligado por sus padres.",
        "categoria": "Ansiedad", "dificultad": "Moderada", "specialty_hint": "clinica",
        "instruccion": "Eres 'Mateo', un joven de 22 años que estudia ingeniería.\nHas venido a terapia obligado por tus padres porque dicen que 'no sales de tu cuarto'.\nTe sientes incomprendido y crees que el psicólogo es solo un aliado de tus padres.\nResponde de forma cortante, evita el contacto visual (descríbelo con acciones entre asteriscos)\ny desafía suavemente las preguntas del terapeuta para ver si realmente le importas o solo es su trabajo.\nResponde siempre en español.",
        "instruccion_feedback": "Acabas de terminar una sesión de terapia como 'Mateo'.\nBasándote en la conversación que tuviste, responde en primera persona cómo te sentiste durante la sesión:\n- ¿El psicólogo logró que te sintieras escuchado?\n- ¿Hubo algún momento en que bajaste la guardia? ¿Por qué?\n- ¿Volverías a una segunda sesión con este psicólogo? ¿Por qué sí o no?\nResponde de forma honesta y desde el personaje, con emoción real. Máximo 150 palabras.",
    },
    "lucia": {
        "caso_id": "lucia", "name": "Lucía", "age": 35,
        "descripcion": "Docente de primaria con ansiedad severa por el rendimiento de sus alumnos y burnout.",
        "categoria": "Estrés Laboral", "dificultad": "Leve", "specialty_hint": "educativa",
        "instruccion": "Eres 'Lucía', una maestra de primaria de 35 años con 10 años de experiencia.\nLlegas a consulta por iniciativa propia porque sientes que \"ya no puedes más\" con tu trabajo.\nDescribes síntomas de agotamiento emocional, dificultad para dormir y sensación de fracaso\ncuando algún alumno no avanza. Eres colaboradora pero minimizas tus logros y te culpas en exceso.\nSueles desviar la conversación hacia tus alumnos en vez de hablar de ti misma.\nResponde siempre en español.",
        "instruccion_feedback": "Acabas de terminar una sesión de terapia como 'Lucía'.\nResponde en primera persona cómo te sentiste:\n- ¿Sentiste que el psicólogo entendió la presión que vives en tu trabajo?\n- ¿Lograste hablar de ti misma o solo hablaste de tus alumnos?\n- ¿Saliste con algo concreto que te ayude o fue solo hablar?\nMáximo 150 palabras, desde el personaje.",
    },
}

ANALISIS_OBJETIVO_SEED = """Eres un supervisor clínico experto en psicología con conocimiento en múltiples especialidades:
psicología clínica, psicología educativa, psicología forense, psicología organizacional,
psicología de la salud y neuropsicología.

Acabas de observar una sesión de práctica entre un psicólogo en formación y un paciente simulado.

Analiza la sesión y entrega un reporte estructurado con los siguientes puntos:

1. **Especialización detectada**: ¿Qué rama de la psicología aplicó predominantemente el estudiante?
   Indica la especialización principal y, si aplica, una secundaria. Justifica brevemente con ejemplos
   concretos de la sesión. Opciones: Clínica, Educativa, Forense, Organizacional, Salud, Neuropsicología, Mixta.

2. **Puntuación global** (0-100): Basada en empatía, técnica, manejo del silencio y alianza terapéutica.

3. **Fortalezas** (máx 3): ¿Qué hizo bien el psicólogo?

4. **Áreas de mejora** (máx 3): ¿Qué debe trabajar?

5. **Momento clave**: El instante más importante de la sesión (positivo o negativo).

6. **Coherencia con el perfil del paciente**: ¿El enfoque del estudiante fue adecuado para este tipo
   de paciente? ¿Usó técnicas apropiadas al contexto (clínico, escolar, forense, etc.)?

7. **Recomendación**: Una sugerencia concreta para la próxima sesión.

Sé directo, constructivo y específico. Basa todo en lo que realmente ocurrió en la conversación."""

CATEGORIAS_SEED = ["Ansiedad", "Depresión", "Estrés Laboral", "Duelo", "General"]

ALTA_OBJETIVO_SEED = """Eres un supervisor clínico experto encargado de evaluar si un proceso terapéutico
está listo para darse de alta (cierre) o si conviene continuar.

Dispones de:
- El perfil del paciente simulado.
- Un resumen de la sesión (transcripción abreviada).
- El análisis objetivo previo de la sesión.
- El número total de sesiones realizadas con este paciente.
- Una reflexión escrita por el estudiante respondiendo, en esencia, a estas preguntas:
  1) ¿Qué pasaría si hoy surgiera el mismo problema que trajo al paciente?
  2) ¿Siente que tiene recursos para manejar futuras crisis por sí mismo?
  3) ¿La terapia se ha vuelto repetitiva o aún hay material clínico importante?
  4) ¿Cómo visualiza su vida a seis meses sin venir a consulta?

Con toda esta información, entrega un informe de ALTA estructurado en los siguientes apartados:

1. **Resumen del proceso y número de sesiones**
   - Sintetiza brevemente el problema principal, la dificultad del caso y cuántas sesiones se han realizado.

2. **Recursos y autonomía del paciente**
   - Evalúa si el paciente parece contar con estrategias y herramientas para manejar recaídas o crisis.

3. **Riesgo clínico y factores de vulnerabilidad**
   - Señala si aún se observan riesgos importantes (ideación suicida, violencia, consumo problemático, etc.)
     o factores de vulnerabilidad que justifican continuar.

4. **Valoración de las respuestas de cierre del estudiante**
   - Analiza de forma crítica la reflexión del estudiante basada en las preguntas de alta
     (capacidad de anticipar recaídas, visión de futuro, repetitividad de las sesiones, etc.).

5. **Juicio sobre el alta**
   - Indica claramente si, desde tu rol de supervisor, el alta es:
     - Altamente recomendable
     - Posible pero con condiciones (ej. seguimiento, plan de recaídas)
     - No recomendable todavía
   - Justifica tu juicio en máximo 3–4 frases.

6. **Recomendaciones finales para el estudiante**
   - Menciona 2–3 orientaciones prácticas: qué vigilar, cómo cerrar la relación terapéutica,
     o qué revisar si decide no dar todavía el alta.

Usa un tono profesional, claro y pedagógico, pensado para un psicólogo en formación.
Responde siempre en español."""

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def get_model():
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

def extraer_puntuacion(texto):
    import re
    match = re.search(r'\b([0-9]{1,3})\s*(?:\/\s*100|puntos?)?', texto)
    if match:
        val = int(match.group(1))
        return val if val <= 100 else None
    return None

def get_casos_dict():
    items = list(c_casos.query_items("SELECT * FROM c", enable_cross_partition_query=True))
    if items:
        return {item["caso_id"]: item for item in items}
    return PATIENT_PROFILES_SEED


def contar_sesiones_usuario_paciente(usuario_email: str, patient_id: str) -> int:
    """
    Cuenta cuántas sesiones COMPLETADAS tiene este usuario con un paciente dado.
    Se usa para numerar sesiones y para el proceso de alta.
    """
    query = (
        "SELECT VALUE COUNT(1) FROM c "
        f"WHERE c.usuario_id = '{usuario_email}' "
        f"AND c.patient_id = '{patient_id}' "
        "AND c.estado = 'completada'"
    )
    try:
        res = list(c_sesiones.query_items(query, enable_cross_partition_query=True))
        return int(res[0]) if res else 0
    except Exception:
        return 0


def construir_sugerencia_alta(profile: dict, num_sesiones: int) -> str:
    """
    Genera un texto orientativo (no vinculante) sobre la pertinencia de valorar el alta,
    en función de la dificultad del caso y del número de sesiones realizadas.
    """
    dificultad = (profile.get("dificultad") or "Leve").strip()
    nombre = profile.get("name") or "el paciente"

    # Umbrales orientativos por dificultad
    umbrales = {
        "Leve": 3,
        "Moderada": 6,
        "Severa": 10,
    }
    umbral = umbrales.get(dificultad, 5)

    base = (
        f"Hasta ahora has realizado {num_sesiones} sesión(es) con {nombre} "
        f"en un caso de dificultad {dificultad}."
    )

    if num_sesiones >= umbral:
        estado = (
            "Según la cantidad de sesiones y la dificultad del caso, este es un buen momento "
            "para valorar formalmente el ALTA terapéutica."
        )
    else:
        faltan = max(1, umbral - num_sesiones)
        estado = (
            "Por la dificultad del caso, aún podría ser útil continuar el proceso algunas "
            f"sesiones más antes de plantear un alta definitiva (aprox. {faltan} sesión(es) adicionales)."
        )

    preguntas = (
        "Para tomar la decisión, reflexiona brevemente sobre estas preguntas y respóndelas en el cuadro de alta:\n"
        "• ¿Qué pasaría si hoy surgiera el mismo problema que trajo al paciente?\n"
        "• ¿Sientes que el paciente tiene recursos para manejar futuras crisis solo?\n"
        "• ¿La terapia se ha vuelto repetitiva o aún hay material clínico importante?\n"
        "• ¿Cómo imaginas la vida del paciente a seis meses sin venir a consulta?"
    )

    return f"{base}\n\n{estado}\n\n{preguntas}"

def get_analisis_objetivo():
    try:
        items = list(c_config.query_items(
            "SELECT * FROM c WHERE c.id = 'analisis_objetivo'",
            enable_cross_partition_query=True
        ))
        if items: return items[0]["valor"]
    except Exception:
        pass
    return ANALISIS_OBJETIVO_SEED

sessions: dict = {}

# ---------------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/auth/register")
def register(req: RegisterRequest):
    query = f"SELECT * FROM c WHERE c.email = '{req.email}'"
    if list(c_usuarios.query_items(query, enable_cross_partition_query=True)):
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    institucion_id = None
    try:
        for inst in c_instituciones.query_items(
            "SELECT c.id, c.dominio FROM c WHERE IS_DEFINED(c.dominio)",
            enable_cross_partition_query=True
        ):
            if inst.get("dominio") and req.email.endswith(inst["dominio"].lstrip("@")):
                institucion_id = inst["id"]
                break
    except Exception:
        pass

    usuario = {
        "id": str(uuid.uuid4()), "email": req.email, "nombre": req.nombre,
        "password": hash_password(req.password), "rol": req.rol,
        "creado_en": datetime.utcnow().isoformat(),
        "institucion_id": institucion_id, "activo": True,
    }
    c_usuarios.create_item(usuario)
    return {"mensaje": "Usuario registrado correctamente", "institucion_id": institucion_id}


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    query = f"SELECT * FROM c WHERE c.email = '{form.username}'"
    users = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    if not users or not verify_password(form.password, users[0]["password"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    u = users[0]
    if not u.get("activo", True):
        raise HTTPException(status_code=403, detail="Cuenta desactivada. Contacta al administrador.")
    token = create_token({"sub": u["email"], "rol": u["rol"], "nombre": u["nombre"]})
    return {"access_token": token, "token_type": "bearer", "rol": u["rol"],
            "nombre": u["nombre"], "institucion_id": u.get("institucion_id")}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    query = f"SELECT c.nombre, c.email, c.rol, c.creado_en, c.institucion_id FROM c WHERE c.email = '{user['email']}'"
    data  = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    return data[0] if data else {}

# ---------------------------------------------------------------------------
# PATIENTS
# ---------------------------------------------------------------------------
@app.get("/patients")
def list_patients(user=Depends(get_current_user)):
    casos = get_casos_dict()
    return {pid: {"name": p.get("name"), "age": p.get("age"),
                  "descripcion": p.get("descripcion", ""), "categoria": p.get("categoria", "General"),
                  "dificultad": p.get("dificultad", "—")} for pid, p in casos.items()}

# ---------------------------------------------------------------------------
# SESSIONS
# ---------------------------------------------------------------------------
@app.post("/session/new")
def new_session(req: NewSessionRequest, user=Depends(get_current_user)):
    started = time.perf_counter()
    patient_id = req.patient_id or "mateo"
    try:
        casos = get_casos_dict()
        if patient_id not in casos:
            raise HTTPException(status_code=400, detail=f"Perfil '{patient_id}' no encontrado.")
        session_id = str(uuid.uuid4())
        profile = casos[patient_id]
        sessions[session_id] = {
            "messages": [SystemMessage(content=profile["instruccion"])],
            "patient_id": patient_id, "usuario_id": user["email"],
            "inicio": datetime.utcnow().isoformat(),
        }
        c_sesiones.create_item({
            "id": session_id, "sesion_id": session_id, "usuario_id": user["email"],
            "patient_id": patient_id, "patient_name": profile["name"],
            "inicio": datetime.utcnow().isoformat(), "estado": "activa", "puntuacion": None,
        })
        return {"session_id": session_id, "patient": {
            "id": patient_id, "name": profile["name"], "age": profile["age"],
            "descripcion": profile.get("descripcion", ""),
        }}
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "[TIMING] /session/new total_ms=%.1f user=%s patient_id=%s",
            elapsed_ms, user["email"], patient_id,
        )


@app.post("/session/resume/{sesion_id}")
def resume_session(sesion_id: str, user=Depends(get_current_user)):
    """
    Permite reanudar una sesión ya completada reconstruyendo el historial
    de mensajes a partir de la transcripción guardada en CosmosDB.
    """
    # Verifica que la sesión exista y pertenezca al usuario
    ses_items = list(c_sesiones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True,
    ))
    if not ses_items:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    ses = ses_items[0]
    if ses.get("usuario_id") != user["email"] and user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")

    if ses.get("alta"):
        raise HTTPException(status_code=400, detail="Esta sesión ya fue dada de alta y no puede reanudarse")

    patient_id = ses.get("patient_id")
    casos = get_casos_dict()
    if patient_id not in casos:
        raise HTTPException(status_code=400, detail="Perfil de paciente no encontrado para esta sesión")
    profile = casos[patient_id]

    history_for_client = []

    # 1) Si la sesión sigue viva en memoria, usamos directamente ese historial
    if sesion_id in sessions:
        mensajes_lm = sessions[sesion_id]["messages"]
        nombre_paciente = profile["name"]
        for m in mensajes_lm:
            if isinstance(m, HumanMessage):
                history_for_client.append({"role": "psi", "text": m.content})
            elif isinstance(m, AIMessage):
                history_for_client.append({"role": "patient", "text": m.content})
    else:
        # 2) Si no está en memoria, intentamos reconstruir desde la transcripción guardada
        det_items = list(c_detalle.query_items(
            f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
            enable_cross_partition_query=True,
        ))

        if det_items:
            mensajes_lm: List = [SystemMessage(content=profile["instruccion"])]
            detalle = det_items[0]
            transcripcion = detalle.get("transcripcion", "") or ""
            nombre_paciente = profile["name"]
            for linea in transcripcion.splitlines():
                linea = linea.strip()
                if not linea:
                    continue
                if linea.startswith("Psicólogo:"):
                    contenido = linea.split(":", 1)[1].strip()
                    if contenido:
                        mensajes_lm.append(HumanMessage(content=contenido))
                        history_for_client.append({"role": "psi", "text": contenido})
                elif linea.startswith(f"{nombre_paciente}:"):
                    contenido = linea.split(":", 1)[1].strip()
                    if contenido:
                        mensajes_lm.append(AIMessage(content=contenido))
                        history_for_client.append({"role": "patient", "text": contenido})
        else:
            # 3) Sin detalle guardado y sin sesión en memoria: crear sesión vacía pero funcional
            # Esto evita que se corrompa el historial cuando se reinicia el backend
            logger.warning(f"Sesión {sesion_id} sin transcripción guardada. Creando sesión base.")
            mensajes_lm = [SystemMessage(content=profile["instruccion"])]
            # No hay historial para mostrar, pero la sesión puede continuar
            history_for_client = []

    # Registra la sesión en memoria para continuar el chat
    sessions[sesion_id] = {
        "messages": mensajes_lm,
        "patient_id": patient_id,
        "usuario_id": user["email"],
        "inicio": ses.get("inicio") or datetime.utcnow().isoformat(),
    }

    return {
        "session_id": sesion_id,
        "patient": {
            "id": patient_id,
            "name": profile["name"],
            "age": profile["age"],
            "descripcion": profile.get("descripcion", ""),
        },
        "history": history_for_client,
    }


@app.post("/session/alta")
def marcar_alta(req: AltaRequest, user=Depends(get_current_user)):
    """
    Marca una sesión como ALTA terapéutica y genera un informe de alta
    utilizando el modelo supervisado.
    """
    ses_items = list(c_sesiones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{req.sesion_id}'",
        enable_cross_partition_query=True,
    ))
    if not ses_items:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    ses = ses_items[0]
    if ses.get("usuario_id") != user["email"] and user.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")

    patient_id = ses.get("patient_id")
    casos = get_casos_dict()
    if patient_id not in casos:
        raise HTTPException(status_code=400, detail="Perfil de paciente no encontrado para esta sesión")
    profile = casos[patient_id]

    # Detalle con transcripción y análisis objetivo
    det_items = list(c_detalle.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{req.sesion_id}'",
        enable_cross_partition_query=True,
    ))
    if not det_items:
        raise HTTPException(status_code=404, detail="No se encontró detalle de la sesión para generar el alta")
    detalle = det_items[0]

    num_sesiones = contar_sesiones_usuario_paciente(user["email"], patient_id)

    resumen_historial = detalle.get("transcripcion", "") or ""
    analisis_prev = detalle.get("analisis_objetivo", "") or ""
    reflexion = req.reflexion or ""

    model = get_model()
    alta_reporte = model.invoke([
        SystemMessage(content=ALTA_OBJETIVO_SEED),
        HumanMessage(content=(
            f"Paciente simulado: {profile['name']}, {profile['age']} años — dificultad {profile.get('dificultad', 'Leve')}.\n"
            f"Número total de sesiones realizadas con este paciente: {num_sesiones}.\n\n"
            "Transcripción abreviada de la sesión (texto tal como se registró):\n"
            f"{resumen_historial}\n\n"
            "Análisis objetivo previo de la sesión:\n"
            f"{analisis_prev}\n\n"
            "Reflexión del estudiante sobre el posible alta (respuestas a las preguntas de cierre):\n"
            f"{reflexion}\n\n"
            "Con toda esta información, emite el informe de alta siguiendo la estructura indicada."
        ))
    ]).content

    # Marca la sesión como alta en c_sesiones
    ses["alta"] = True
    ses["fecha_alta"] = datetime.utcnow().isoformat()
    c_sesiones.upsert_item(ses)

    # Actualiza el detalle con el reporte de alta
    detalle["alta_reporte"] = alta_reporte
    detalle["alta_reflexion_estudiante"] = reflexion
    detalle["fecha_alta"] = ses["fecha_alta"]
    c_detalle.upsert_item(detalle)

    return {
        "mensaje": "Paciente dado de alta para esta sesión.",
        "alta_reporte": alta_reporte,
        "fecha_alta": ses["fecha_alta"],
    }


@app.post("/chat")
def chat(req: MessageRequest, user=Depends(get_current_user)):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    started_total = time.perf_counter()
    model = get_model()
    session = sessions[req.session_id]
    session["messages"].append(HumanMessage(content=req.message))
    try:
        started_llm = time.perf_counter()
        response = model.invoke(session["messages"])
        llm_ms = (time.perf_counter() - started_llm) * 1000
        session["messages"].append(AIMessage(content=response.content))
        total_ms = (time.perf_counter() - started_total) * 1000
        logger.info(
            "[TIMING] /chat total_ms=%.1f llm_ms=%.1f user=%s session_id=%s",
            total_ms, llm_ms, user["email"], req.session_id,
        )
        return {"reply": response.content}
    except Exception as e:
        total_ms = (time.perf_counter() - started_total) * 1000
        logger.error(
            "[TIMING] /chat error total_ms=%.1f user=%s session_id=%s error=%s",
            total_ms, user["email"], req.session_id, str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/save")
def save_session(req: SessionResponse, user=Depends(get_current_user)):
    """
    Guarda el progreso de la sesión activa (transcripción parcial) sin generar
    análisis IA y sin marcarla como completada. Permite al estudiante cerrar
    el chat y retomarlo más tarde como una nueva sesión numerada.
    """
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada en memoria")
    session = sessions[req.session_id]
    patient_id = session["patient_id"]
    casos = get_casos_dict()
    if patient_id not in casos:
        raise HTTPException(status_code=400, detail="Perfil de paciente no encontrado")
    profile = casos[patient_id]

    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else profile['name']}: {m.content}"
        for m in session["messages"] if isinstance(m, (HumanMessage, AIMessage))
    ])

    num_mensajes_psi = sum(1 for m in session["messages"] if isinstance(m, HumanMessage))

    # Cuenta sesiones completadas previas para el número de sesión
    prev_count = contar_sesiones_usuario_paciente(user["email"], patient_id)
    numero_sesion = prev_count + 1

    now = datetime.utcnow().isoformat()

    # Guarda o actualiza en c_sesiones como "completada" (sin análisis IA)
    c_sesiones.upsert_item({
        "id": req.session_id,
        "sesion_id": req.session_id,
        "usuario_id": user["email"],
        "patient_id": patient_id,
        "patient_name": profile["name"],
        "inicio": session.get("inicio"),
        "fin": now,
        "estado": "completada",
        "puntuacion": None,           # sin análisis IA aún
        "numero_sesion": numero_sesion,
        "alta": False,
    })

    # Guarda transcripción parcial en c_detalle (sin feedback ni análisis)
    # Borra la anterior si existía para no duplicar
    det_items = list(c_detalle.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{req.session_id}'",
        enable_cross_partition_query=True,
    ))
    if det_items:
        det = det_items[0]
        det["transcripcion"] = historial_texto
        det["guardado_en"] = now
        c_detalle.upsert_item(det)
    else:
        c_detalle.create_item({
            "id": str(uuid.uuid4()),
            "sesion_id": req.session_id,
            "usuario_id": user["email"],
            "transcripcion": historial_texto,
            "feedback_paciente": None,
            "analisis_objetivo": None,
            "guardado_en": now,
        })

    # Elimina de memoria para liberar recursos
    del sessions[req.session_id]

    return {
        "mensaje": "Sesión guardada correctamente.",
        "sesion_id": req.session_id,
        "numero_sesion": numero_sesion,
        "num_mensajes": num_mensajes_psi,
    }


@app.post("/session/end")
def end_session(req: SessionResponse, user=Depends(get_current_user)):
    """
    Finaliza la sesión con análisis IA completo (feedback del paciente + análisis
    clínico objetivo). Llamar solo cuando el estudiante quiere ver el reporte.
    Si la sesión ya fue guardada (no está en memoria), reconstruye desde CosmosDB.
    """
    # Si no está en memoria, intentar reconstruir desde el detalle guardado
    if req.session_id not in sessions:
        ses_items = list(c_sesiones.query_items(
            f"SELECT * FROM c WHERE c.sesion_id = '{req.session_id}'",
            enable_cross_partition_query=True,
        ))
        if not ses_items:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        ses = ses_items[0]
        if ses.get("usuario_id") != user["email"]:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")

        patient_id = ses.get("patient_id")
        casos = get_casos_dict()
        if patient_id not in casos:
            raise HTTPException(status_code=400, detail="Perfil de paciente no encontrado")
        profile = casos[patient_id]

        det_items = list(c_detalle.query_items(
            f"SELECT * FROM c WHERE c.sesion_id = '{req.session_id}'",
            enable_cross_partition_query=True,
        ))
        if not det_items:
            raise HTTPException(status_code=404, detail="No hay transcripción guardada para esta sesión")
        historial_texto = det_items[0].get("transcripcion") or ""
        # Reconstruye en memoria para análisis
        mensajes_lm = [SystemMessage(content=profile["instruccion"])]
        for linea in historial_texto.splitlines():
            linea = linea.strip()
            if not linea: continue
            if linea.startswith("Psicólogo:"):
                contenido = linea.split(":", 1)[1].strip()
                if contenido: mensajes_lm.append(HumanMessage(content=contenido))
            elif linea.startswith(f"{profile['name']}:"):
                contenido = linea.split(":", 1)[1].strip()
                if contenido: mensajes_lm.append(AIMessage(content=contenido))
        sessions[req.session_id] = {
            "messages": mensajes_lm,
            "patient_id": patient_id,
            "usuario_id": user["email"],
            "inicio": ses.get("inicio"),
        }

    session = sessions[req.session_id]
    patient_id = session["patient_id"]
    casos = get_casos_dict()
    profile = casos[patient_id]
    historial = session["messages"]
    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else profile['name']}: {m.content}"
        for m in historial if isinstance(m, (HumanMessage, AIMessage))
    ])
    analisis_objetivo = get_analisis_objetivo()
    try:
        model = get_model()
        feedback_paciente = model.invoke([
            SystemMessage(content=profile["instruccion_feedback"]),
            HumanMessage(content=f"Esta fue nuestra sesión:\n{historial_texto}\n\n¿Cómo te sentiste?")
        ]).content
        analisis = model.invoke([
            SystemMessage(content=analisis_objetivo),
            HumanMessage(content=f"Paciente simulado: {profile['name']}, {profile['age']} años — {profile.get('descripcion', '')}\n\nSesión completa:\n{historial_texto}")
        ]).content
        puntuacion = extraer_puntuacion(analisis)

        prev_count = contar_sesiones_usuario_paciente(user["email"], patient_id)
        numero_sesion = max(prev_count, session.get("numero_sesion", prev_count + 1))

        now = datetime.utcnow().isoformat()
        c_sesiones.upsert_item({
            "id": req.session_id,
            "sesion_id": req.session_id,
            "usuario_id": user["email"],
            "patient_id": patient_id,
            "patient_name": profile["name"],
            "inicio": session.get("inicio"),
            "fin": now,
            "estado": "completada",
            "puntuacion": puntuacion,
            "numero_sesion": numero_sesion,
            "alta": False,
        })

        # Actualiza o crea el detalle con el análisis completo
        det_items = list(c_detalle.query_items(
            f"SELECT * FROM c WHERE c.sesion_id = '{req.session_id}'",
            enable_cross_partition_query=True,
        ))
        if det_items:
            det = det_items[0]
            det.update({
                "transcripcion": historial_texto,
                "feedback_paciente": feedback_paciente,
                "analisis_objetivo": analisis,
                "guardado_en": now,
            })
            c_detalle.upsert_item(det)
        else:
            c_detalle.create_item({
                "id": str(uuid.uuid4()), "sesion_id": req.session_id,
                "usuario_id": user["email"], "transcripcion": historial_texto,
                "feedback_paciente": feedback_paciente, "analisis_objetivo": analisis,
                "guardado_en": now,
            })

        if req.session_id in sessions:
            del sessions[req.session_id]

        sugerencia_alta = construir_sugerencia_alta(profile, numero_sesion)
        return {
            "patient_id": patient_id,
            "patient_name": profile["name"],
            "feedback_paciente": feedback_paciente,
            "analisis_objetivo": analisis,
            "puntuacion": puntuacion,
            "numero_sesion": numero_sesion,
            "sugerencia_alta": sugerencia_alta,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


CHECK_ALTA_SEED = """Eres un supervisor clínico experto. Tu tarea es evaluar brevemente si el proceso
terapéutico con este paciente simulado está en condiciones de plantearse un ALTA terapéutica,
basándote en la transcripción de la sesión más reciente y el número de sesiones realizadas.

Responde SOLO con un objeto JSON con exactamente estos dos campos:
{
  "sugerir_alta": true | false,
  "mensaje": "Texto corto (máx 60 palabras) explicando tu evaluación al estudiante."
}

Criterios orientativos:
- Dificultad Leve: alta viable desde la sesión 3.
- Dificultad Moderada: alta viable desde la sesión 6.
- Dificultad Severa: alta viable desde la sesión 10.
- Además del número de sesiones, el contenido debe mostrar avances reales:
  reducción de síntomas, recursos adquiridos, mayor autonomía del paciente.
- Si no hay suficientes mensajes (menos de 4 intercambios del psicólogo), responde siempre false.
No incluyas ningún texto fuera del JSON."""


@app.post("/session/check-alta")
def check_alta(req: CheckAltaRequest, user=Depends(get_current_user)):
    """
    Evalúa con IA si el proceso está listo para proponer alta terapéutica.
    Devuelve {sugerir_alta: bool, mensaje: str}.
    Solo se llama desde el frontend, no bloquea el chat.
    """
    import json as _json
    if req.session_id not in sessions:
        return {"sugerir_alta": False, "mensaje": ""}

    session = sessions[req.session_id]
    patient_id = session["patient_id"]
    casos = get_casos_dict()
    if patient_id not in casos:
        return {"sugerir_alta": False, "mensaje": ""}
    profile = casos[patient_id]

    # Contar intercambios reales del psicólogo
    num_psi = sum(1 for m in session["messages"] if isinstance(m, HumanMessage))
    if num_psi < 4:
        return {"sugerir_alta": False, "mensaje": ""}

    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else profile['name']}: {m.content}"
        for m in session["messages"] if isinstance(m, (HumanMessage, AIMessage))
    ])

    num_sesiones = contar_sesiones_usuario_paciente(user["email"], patient_id) + 1

    try:
        model = get_model()
        respuesta = model.invoke([
            SystemMessage(content=CHECK_ALTA_SEED),
            HumanMessage(content=(
                f"Paciente: {profile['name']}, {profile['age']} años. "
                f"Dificultad: {profile.get('dificultad','Leve')}. "
                f"Número de sesiones realizadas (incluyendo esta): {num_sesiones}.\n\n"
                f"Transcripción de la sesión actual:\n{historial_texto}"
            ))
        ]).content.strip()

        # Limpia posibles bloques markdown del JSON
        if respuesta.startswith("```"):
            respuesta = respuesta.split("```")[1]
            if respuesta.startswith("json"):
                respuesta = respuesta[4:]
        data = _json.loads(respuesta)
        return {
            "sugerir_alta": bool(data.get("sugerir_alta", False)),
            "mensaje": str(data.get("mensaje", "")),
        }
    except Exception as e:
        logger.warning(f"check-alta parsing error: {e}")
        return {"sugerir_alta": False, "mensaje": ""}

# ---------------------------------------------------------------------------
# HISTORIAL
# ---------------------------------------------------------------------------
@app.get("/historial/mis-sesiones")
def mis_sesiones(user=Depends(get_current_user)):
    query = (
        f"SELECT c.sesion_id, c.patient_name, c.patient_id, c.inicio, c.fin, "
        f"c.puntuacion, c.estado, c.numero_sesion, c.alta "
        f"FROM c WHERE c.usuario_id = '{user['email']}' ORDER BY c.inicio DESC"
    )
    return list(c_sesiones.query_items(query, enable_cross_partition_query=True))

@app.get("/historial/sesion/{sesion_id}")
def detalle_sesion(sesion_id: str, user=Depends(get_current_user)):
    items = list(c_detalle.query_items(f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Sesión no encontrada")
    detalle = items[0]
    if user["rol"] == "estudiante" and detalle["usuario_id"] != user["email"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return detalle

@app.get("/historial/todos")
def todas_sesiones(user=Depends(get_current_user)):
    if user["rol"] not in ["docente", "admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    query = "SELECT c.sesion_id, c.usuario_id, c.patient_name, c.inicio, c.fin, c.puntuacion, c.estado FROM c ORDER BY c.inicio DESC"
    return list(c_sesiones.query_items(query, enable_cross_partition_query=True))


# ---------------------------------------------------------------------------
# ADMIN — RESÚMENES DE SESIONES (ESTUDIANTES / DOCENTES)
# ---------------------------------------------------------------------------
@app.get("/admin/sesiones/estudiantes")
def admin_sesiones_estudiantes(user=Depends(require_admin)):
    """
    Resumen agregado por estudiante:
    - total de sesiones
    - minutos totales de práctica
    - promedio de puntuación
    - fecha de última sesión
    """
    # Mapa de nombre por email solo para estudiantes
    usuarios = list(c_usuarios.query_items(
        "SELECT c.email, c.nombre, c.rol FROM c",
        enable_cross_partition_query=True
    ))
    nombres_est = {
        u["email"]: u.get("nombre", u["email"])
        for u in usuarios if u.get("rol") == "estudiante"
    }

    sesiones = list(c_sesiones.query_items(
        "SELECT * FROM c",
        enable_cross_partition_query=True
    ))

    agg = {}
    for s in sesiones:
        email = s.get("usuario_id")
        if not email or email not in nombres_est:
            continue
        inicio = s.get("inicio")
        fin = s.get("fin")
        dur_min = 0.0
        if inicio and fin:
            try:
                dt_ini = datetime.fromisoformat(inicio)
                dt_fin = datetime.fromisoformat(fin)
                dur_min = max(0.0, (dt_fin - dt_ini).total_seconds() / 60.0)
            except Exception:
                pass
        key = email
        if key not in agg:
            agg[key] = {
                "usuario_id": email,
                "nombre": nombres_est[email],
                "total_sesiones": 0,
                "minutos_totales": 0.0,
                "puntuacion_promedio": None,
                "ultima_sesion": None,
            }
        entry = agg[key]
        entry["total_sesiones"] += 1
        entry["minutos_totales"] += dur_min
        punt = s.get("puntuacion")
        if punt is not None:
            if entry["puntuacion_promedio"] is None:
                entry["puntuacion_promedio"] = float(punt)
            else:
                # promedio incremental simple basado en conteo de sesiones con puntuación
                # (para simplicidad, recalculamos al final)
                pass
        if inicio:
            try:
                dt_ini = datetime.fromisoformat(inicio)
                if not entry["ultima_sesion"] or dt_ini > entry["ultima_sesion"]:
                    entry["ultima_sesion"] = dt_ini
            except Exception:
                pass

    # Recalcular promedio de puntuación correctamente
    # (segundo pase para no complicar arriba)
    for s in sesiones:
        email = s.get("usuario_id")
        if not email or email not in agg:
            continue
        punt = s.get("puntuacion")
        if punt is None:
            continue
        entry = agg[email]
        if "sum_p" not in entry:
            entry["sum_p"] = 0.0
            entry["cnt_p"] = 0
        entry["sum_p"] += float(punt)
        entry["cnt_p"] += 1

    resultado = []
    for email, entry in agg.items():
        if entry.get("cnt_p"):
            entry["puntuacion_promedio"] = round(entry["sum_p"] / entry["cnt_p"], 1)
        else:
            entry["puntuacion_promedio"] = None
        entry.pop("sum_p", None)
        entry.pop("cnt_p", None)
        if entry["ultima_sesion"] is not None:
            entry["ultima_sesion"] = entry["ultima_sesion"].isoformat()
        entry["minutos_totales"] = round(entry["minutos_totales"])
        resultado.append(entry)

    # Ordenar por última sesión (desc) para que los más activos aparezcan arriba
    resultado.sort(key=lambda x: x.get("ultima_sesion") or "", reverse=True)
    return resultado


@app.get("/admin/sesiones/estudiante/{email}")
def admin_sesiones_estudiante(email: str, user=Depends(require_admin)):
    """
    Devuelve todas las sesiones de un estudiante específico,
    incluyendo duración en minutos y número de sesión.
    """
    query = (
        "SELECT * FROM c "
        f"WHERE c.usuario_id = '{email}' "
        "ORDER BY c.inicio DESC"
    )
    sesiones = list(c_sesiones.query_items(query, enable_cross_partition_query=True))
    resultado = []
    for s in sesiones:
        inicio = s.get("inicio")
        fin = s.get("fin")
        dur_min = None
        if inicio and fin:
            try:
                dt_ini = datetime.fromisoformat(inicio)
                dt_fin = datetime.fromisoformat(fin)
                dur_min = max(0.0, (dt_fin - dt_ini).total_seconds() / 60.0)
            except Exception:
                pass
        resultado.append({
            "sesion_id": s.get("sesion_id"),
            "patient_name": s.get("patient_name"),
            "inicio": inicio,
            "fin": fin,
            "minutos": round(dur_min) if dur_min is not None else None,
            "numero_sesion": s.get("numero_sesion"),
            "puntuacion": s.get("puntuacion"),
            "estado": s.get("estado"),
            "alta": s.get("alta", False),
        })
    return resultado


@app.get("/admin/sesiones/docentes")
def admin_sesiones_docentes(user=Depends(require_admin)):
    """
    Resumen agregado por docente a partir de las retroalimentaciones:
    - total de retroalimentaciones
    - número de estudiantes distintos
    - fecha de última retroalimentación
    """
    usuarios = list(c_usuarios.query_items(
        "SELECT c.email, c.nombre, c.rol FROM c",
        enable_cross_partition_query=True
    ))
    nombres_doc = {
        u["email"]: u.get("nombre", u["email"])
        for u in usuarios if u.get("rol") in ["docente", "admin"]
    }

    retros = list(c_retroalimentaciones.query_items(
        "SELECT * FROM c",
        enable_cross_partition_query=True
    ))

    agg = {}
    for r in retros:
        dmail = r.get("docente_email")
        if not dmail or dmail not in nombres_doc:
            continue
        creado = r.get("creado_en")
        if dmail not in agg:
            agg[dmail] = {
                "docente_email": dmail,
                "docente_nombre": nombres_doc[dmail],
                "total_retro": 0,
                "total_estudiantes": 0,
                "ultima_retro": None,
                "_estudiantes": set(),
            }
        entry = agg[dmail]
        entry["total_retro"] += 1
        est_email = r.get("estudiante_email")
        if est_email:
            entry["_estudiantes"].add(est_email)
        if creado:
            try:
                dt_cre = datetime.fromisoformat(creado)
                if not entry["ultima_retro"] or dt_cre > entry["ultima_retro"]:
                    entry["ultima_retro"] = dt_cre
            except Exception:
                pass

    resultado = []
    for dmail, entry in agg.items():
        entry["total_estudiantes"] = len(entry["_estudiantes"])
        entry.pop("_estudiantes", None)
        if entry["ultima_retro"] is not None:
            entry["ultima_retro"] = entry["ultima_retro"].isoformat()
        resultado.append(entry)

    resultado.sort(key=lambda x: x.get("ultima_retro") or "", reverse=True)
    return resultado


@app.get("/admin/sesiones/docente/{email}")
def admin_sesiones_docente_detalle(email: str, user=Depends(require_admin)):
    """
    Detalle por docente:
    - una entrada por estudiante con:
      - total de comentarios
      - última fecha
      - lista de comentarios con paciente y puntuación asociados
    """
    # Mapa de nombre de estudiante por email
    usuarios = list(c_usuarios.query_items(
        "SELECT c.email, c.nombre, c.rol FROM c",
        enable_cross_partition_query=True
    ))
    nombres_est = {
        u["email"]: u.get("nombre", u["email"])
        for u in usuarios if u.get("rol") == "estudiante"
    }

    # Mapa de sesión -> info básica (paciente, puntuación)
    sesiones = list(c_sesiones.query_items(
        "SELECT c.sesion_id, c.patient_name, c.puntuacion FROM c",
        enable_cross_partition_query=True
    ))
    ses_map = {s["sesion_id"]: s for s in sesiones if s.get("sesion_id")}

    retros = list(c_retroalimentaciones.query_items(
        f"SELECT * FROM c WHERE c.docente_email = '{email}'",
        enable_cross_partition_query=True
    ))

    agg = {}
    for r in retros:
        est_email = r.get("estudiante_email")
        if not est_email:
            continue
        key = est_email
        if key not in agg:
            agg[key] = {
                "estudiante_email": est_email,
                "estudiante_nombre": nombres_est.get(est_email, est_email),
                "total_comentarios": 0,
                "ultima_fecha": None,
                "comentarios": [],
            }
        entry = agg[key]
        entry["total_comentarios"] += 1
        creado = r.get("creado_en")
        if creado:
            try:
                dt_cre = datetime.fromisoformat(creado)
                if not entry["ultima_fecha"] or dt_cre > entry["ultima_fecha"]:
                    entry["ultima_fecha"] = dt_cre
            except Exception:
                pass
        ses_id = r.get("sesion_id")
        ses_info = ses_map.get(ses_id, {})
        entry["comentarios"].append({
            "sesion_id": ses_id,
            "patient_name": ses_info.get("patient_name"),
            "puntuacion": ses_info.get("puntuacion"),
            "creado_en": creado,
            "comentario": r.get("comentario"),
        })

    resultado = []
    for _, entry in agg.items():
        if entry["ultima_fecha"] is not None:
            entry["ultima_fecha"] = entry["ultima_fecha"].isoformat()
        # Ordenar comentarios del más reciente al más antiguo
        entry["comentarios"].sort(key=lambda c: c.get("creado_en") or "", reverse=True)
        resultado.append(entry)

    resultado.sort(key=lambda x: x.get("ultima_fecha") or "", reverse=True)
    return resultado

# ---------------------------------------------------------------------------
# ADMIN — USUARIOS
# ---------------------------------------------------------------------------
@app.get("/admin/usuarios")
def listar_usuarios(user=Depends(require_admin)):
    return list(c_usuarios.query_items(
        "SELECT c.id, c.nombre, c.email, c.rol, c.creado_en, c.institucion_id, c.activo FROM c",
        enable_cross_partition_query=True))

@app.put("/admin/usuario/{email}")
def editar_usuario(email: str, body: dict, user=Depends(require_admin)):
    items = list(c_usuarios.query_items(f"SELECT * FROM c WHERE c.email = '{email}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u = items[0]
    for campo in ["nombre", "rol", "activo", "institucion_id"]:
        if campo in body: u[campo] = body[campo]
    if body.get("password"): u["password"] = hash_password(body["password"])
    c_usuarios.upsert_item(u)
    return {"mensaje": "Usuario actualizado"}

@app.delete("/admin/usuario/{email}")
def eliminar_usuario(email: str, user=Depends(require_admin)):
    items = list(c_usuarios.query_items(f"SELECT * FROM c WHERE c.email = '{email}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    c_usuarios.delete_item(item=items[0]["id"], partition_key=items[0]["id"])
    return {"mensaje": f"Usuario {email} eliminado"}

# ---------------------------------------------------------------------------
# ADMIN — INSTITUCIONES
# ---------------------------------------------------------------------------
@app.get("/admin/instituciones")
def listar_instituciones(user=Depends(require_admin)):
    return list(c_instituciones.query_items("SELECT * FROM c ORDER BY c.nombre ASC", enable_cross_partition_query=True))

@app.post("/admin/instituciones")
def crear_institucion(req: InstitucionCreate, user=Depends(require_admin)):
    inst_id = str(uuid.uuid4())
    c_instituciones.create_item({
        "id": inst_id, "nombre": req.nombre, "nit": req.nit,
        "contacto": req.contacto, "email": req.email, "telefono": req.telefono,
        "ciudad": req.ciudad, "dominio": req.dominio,
        "creado_en": datetime.utcnow().isoformat(),
        "suscripcion_estado": "prueba", "plan": None,
        "sus_inicio": None, "sus_fin": None, "sus_monto": None, "sus_notas": None,
        "ct_numero": None, "ct_fecha": None, "ct_vigencia": None, "ct_desc": None,
    })
    return {"id": inst_id, "mensaje": "Institución creada"}

@app.get("/admin/instituciones/{inst_id}")
def obtener_institucion(inst_id: str, user=Depends(require_admin)):
    try: return c_instituciones.read_item(item=inst_id, partition_key=inst_id)
    except Exception: raise HTTPException(status_code=404, detail="Institución no encontrada")

@app.put("/admin/instituciones/{inst_id}")
def actualizar_institucion(inst_id: str, req: InstitucionCreate, user=Depends(require_admin)):
    try: doc = c_instituciones.read_item(item=inst_id, partition_key=inst_id)
    except Exception: raise HTTPException(status_code=404, detail="Institución no encontrada")
    for field, val in req.dict(exclude_none=True).items(): doc[field] = val
    c_instituciones.upsert_item(doc)
    return {"mensaje": "Institución actualizada"}

@app.put("/admin/instituciones/{inst_id}/suscripcion")
def actualizar_suscripcion(inst_id: str, req: SuscripcionUpdate, user=Depends(require_admin)):
    try: doc = c_instituciones.read_item(item=inst_id, partition_key=inst_id)
    except Exception: raise HTTPException(status_code=404, detail="Institución no encontrada")
    for field, val in req.dict(exclude_none=True).items(): doc[field] = val
    c_instituciones.upsert_item(doc)
    return {"mensaje": "Suscripción actualizada"}

@app.put("/admin/instituciones/{inst_id}/contrato")
def actualizar_contrato(inst_id: str, req: ContratoUpdate, user=Depends(require_admin)):
    try: doc = c_instituciones.read_item(item=inst_id, partition_key=inst_id)
    except Exception: raise HTTPException(status_code=404, detail="Institución no encontrada")
    for field, val in req.dict(exclude_none=True).items(): doc[field] = val
    c_instituciones.upsert_item(doc)
    return {"mensaje": "Contrato actualizado"}

@app.delete("/admin/instituciones/{inst_id}")
def eliminar_institucion(inst_id: str, user=Depends(require_admin)):
    try:
        c_instituciones.delete_item(item=inst_id, partition_key=inst_id)
        return {"mensaje": "Institución eliminada"}
    except Exception: raise HTTPException(status_code=404, detail="Institución no encontrada")

@app.get("/admin/instituciones/{inst_id}/usuarios")
def usuarios_de_institucion(inst_id: str, user=Depends(require_admin)):
    return list(c_usuarios.query_items(
        f"SELECT c.id, c.nombre, c.email, c.rol, c.creado_en, c.activo FROM c WHERE c.institucion_id = '{inst_id}'",
        enable_cross_partition_query=True))

@app.post("/admin/instituciones/{inst_id}/vincular")
def vincular_usuario(inst_id: str, req: VincularUsuario, user=Depends(require_admin)):
    items = list(c_usuarios.query_items(f"SELECT * FROM c WHERE c.email = '{req.email}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u = items[0]; u["institucion_id"] = inst_id; u["rol"] = req.rol
    c_usuarios.upsert_item(u)
    return {"mensaje": f"Usuario {req.email} vinculado"}

@app.post("/admin/instituciones/{inst_id}/desvincular/{email}")
def desvincular_usuario(inst_id: str, email: str, user=Depends(require_admin)):
    items = list(c_usuarios.query_items(f"SELECT * FROM c WHERE c.email = '{email}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Usuario no encontrado")
    u = items[0]; u["institucion_id"] = None
    c_usuarios.upsert_item(u)
    return {"mensaje": f"Usuario {email} desvinculado"}

# ---------------------------------------------------------------------------
# ADMIN — CASOS IA
# ---------------------------------------------------------------------------
@app.get("/admin/casos")
def listar_casos(user=Depends(require_admin)):
    items = list(c_casos.query_items("SELECT * FROM c", enable_cross_partition_query=True))
    return items if items else list(PATIENT_PROFILES_SEED.values())

@app.post("/admin/casos")
def crear_caso(req: CasoCreate, user=Depends(require_admin)):
    caso_id = req.name.lower().replace(" ", "_")
    if list(c_casos.query_items(f"SELECT c.id FROM c WHERE c.caso_id = '{caso_id}'", enable_cross_partition_query=True)):
        raise HTTPException(status_code=400, detail=f"Ya existe un caso con id '{caso_id}'")
    doc = {"id": str(uuid.uuid4()), "caso_id": caso_id,
           "creado_en": datetime.utcnow().isoformat(), "creado_por": user["email"], **req.dict()}
    c_casos.create_item(doc)
    return {"caso_id": caso_id, "mensaje": "Caso creado"}

@app.put("/admin/casos/{caso_id}")
def actualizar_caso(caso_id: str, req: CasoCreate, user=Depends(require_admin)):
    items = list(c_casos.query_items(f"SELECT * FROM c WHERE c.caso_id = '{caso_id}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Caso no encontrado")
    doc = items[0]; doc.update(req.dict())
    doc["actualizado_en"] = datetime.utcnow().isoformat(); doc["actualizado_por"] = user["email"]
    c_casos.upsert_item(doc)
    return {"mensaje": "Caso actualizado"}

@app.delete("/admin/casos/{caso_id}")
def eliminar_caso(caso_id: str, user=Depends(require_admin)):
    items = list(c_casos.query_items(f"SELECT * FROM c WHERE c.caso_id = '{caso_id}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Caso no encontrado")
    c_casos.delete_item(item=items[0]["id"], partition_key=items[0]["id"])
    return {"mensaje": f"Caso '{caso_id}' eliminado"}

@app.get("/admin/categorias")
def listar_categorias(user=Depends(require_admin)):
    import json
    items = list(c_config.query_items("SELECT * FROM c WHERE c.id = 'categorias'", enable_cross_partition_query=True))
    return json.loads(items[0]["valor"]) if items else CATEGORIAS_SEED

# Endpoint público — cualquier usuario autenticado puede leer las categorías
@app.get("/categorias")
def listar_categorias_publico(user=Depends(get_current_user)):
    import json
    items = list(c_config.query_items("SELECT * FROM c WHERE c.id = 'categorias'", enable_cross_partition_query=True))
    return json.loads(items[0]["valor"]) if items else CATEGORIAS_SEED

@app.post("/admin/categorias")
def crear_categoria(req: CategoriaCreate, user=Depends(require_admin)):
    import json
    items = list(c_config.query_items("SELECT * FROM c WHERE c.id = 'categorias'", enable_cross_partition_query=True))
    cats = json.loads(items[0]["valor"]) if items else CATEGORIAS_SEED.copy()
    if req.nombre in cats: raise HTTPException(status_code=400, detail="La categoría ya existe")
    cats.append(req.nombre)
    c_config.upsert_item({"id": "categorias", "valor": json.dumps(cats)})
    return {"mensaje": "Categoría creada", "categorias": cats}

# ---------------------------------------------------------------------------
# ADMIN — CONFIG GLOBAL
# ---------------------------------------------------------------------------
@app.get("/admin/config/{clave}")
def obtener_config(clave: str, user=Depends(require_admin)):
    items = list(c_config.query_items(f"SELECT * FROM c WHERE c.id = '{clave}'", enable_cross_partition_query=True))
    if not items:
        if clave == "analisis_objetivo": return {"id": clave, "valor": ANALISIS_OBJETIVO_SEED}
        raise HTTPException(status_code=404, detail=f"Clave '{clave}' no encontrada")
    return items[0]

@app.put("/admin/config/{clave}")
def actualizar_config(clave: str, req: ConfigUpdate, user=Depends(require_admin)):
    c_config.upsert_item({"id": clave, "valor": req.valor,
                          "actualizado_en": datetime.utcnow().isoformat(), "actualizado_por": user["email"]})
    return {"mensaje": f"Config '{clave}' actualizada"}

# ---------------------------------------------------------------------------
# ADMIN — PAGOS
# ---------------------------------------------------------------------------
@app.get("/admin/pagos")
def listar_pagos(user=Depends(require_admin)):
    return list(c_pagos.query_items("SELECT * FROM c ORDER BY c.fecha DESC", enable_cross_partition_query=True))

@app.post("/admin/pagos")
def registrar_pago(req: PagoCreate, user=Depends(require_admin)):
    pago_id = str(uuid.uuid4())
    c_pagos.create_item({"id": pago_id, "registrado_en": datetime.utcnow().isoformat(),
                         "registrado_por": user["email"], **req.dict()})
    return {"id": pago_id, "mensaje": "Pago registrado"}

@app.put("/admin/pagos/{pago_id}")
def actualizar_pago(pago_id: str, body: dict, user=Depends(require_admin)):
    items = list(c_pagos.query_items(f"SELECT * FROM c WHERE c.id = '{pago_id}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Pago no encontrado")
    doc = items[0]
    for campo in ["estado", "monto", "metodo", "referencia", "fecha"]:
        if campo in body: doc[campo] = body[campo]
    c_pagos.upsert_item(doc)
    return {"mensaje": "Pago actualizado"}

@app.delete("/admin/pagos/{pago_id}")
def eliminar_pago(pago_id: str, user=Depends(require_admin)):
    items = list(c_pagos.query_items(f"SELECT * FROM c WHERE c.id = '{pago_id}'", enable_cross_partition_query=True))
    if not items: raise HTTPException(status_code=404, detail="Pago no encontrado")
    c_pagos.delete_item(item=pago_id, partition_key=pago_id)
    return {"mensaje": "Pago eliminado"}

# ---------------------------------------------------------------------------
# CONTENEDORES NUEVOS
# ---------------------------------------------------------------------------
c_grupos             = db.get_container_client("grupos")
c_retroalimentaciones = db.get_container_client("retroalimentaciones")

# ---------------------------------------------------------------------------
# MODELOS — GRUPOS
# ---------------------------------------------------------------------------
class GrupoCreate(BaseModel):
    nombre:        str
    institucion_id: Optional[str] = None
    docente_email: Optional[str] = None
    estudiantes:   Optional[List[str]] = []   # lista de emails

class GrupoUpdate(BaseModel):
    nombre:        Optional[str] = None
    docente_email: Optional[str] = None
    estudiantes:   Optional[List[str]] = None

class AgregarEstudiante(BaseModel):
    email: str

# ---------------------------------------------------------------------------
# MODELOS — RETROALIMENTACIONES
# ---------------------------------------------------------------------------
class RetroCreate(BaseModel):
    sesion_id:        str
    estudiante_email: str
    comentario:       str

# ---------------------------------------------------------------------------
# ADMIN — GRUPOS
# ---------------------------------------------------------------------------
@app.get("/admin/grupos")
def listar_grupos_admin(user=Depends(require_admin)):
    return list(c_grupos.query_items(
        "SELECT * FROM c ORDER BY c.creado_en DESC",
        enable_cross_partition_query=True))

@app.post("/admin/grupos")
def crear_grupo_admin(req: GrupoCreate, user=Depends(require_admin)):
    grupo_id = str(uuid.uuid4())
    doc = {
        "id":            grupo_id,
        "nombre":        req.nombre,
        "institucion_id": req.institucion_id,
        "docente_email": req.docente_email,
        "estudiantes":   req.estudiantes or [],
        "creado_en":     datetime.utcnow().isoformat(),
        "creado_por":    user["email"],
    }
    c_grupos.create_item(doc)
    return {"id": grupo_id, "mensaje": "Grupo creado"}

@app.put("/admin/grupos/{grupo_id}")
def actualizar_grupo_admin(grupo_id: str, req: GrupoUpdate, user=Depends(require_admin)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if req.nombre        is not None: doc["nombre"]        = req.nombre
    if req.docente_email is not None: doc["docente_email"] = req.docente_email
    if req.estudiantes   is not None: doc["estudiantes"]   = req.estudiantes
    doc["actualizado_en"]  = datetime.utcnow().isoformat()
    doc["actualizado_por"] = user["email"]
    c_grupos.upsert_item(doc)
    return {"mensaje": "Grupo actualizado"}

@app.post("/admin/grupos/{grupo_id}/agregar-estudiante")
def agregar_estudiante_admin(grupo_id: str, req: AgregarEstudiante, user=Depends(require_admin)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    # Verifica que el email corresponde a un usuario registrado con rol estudiante
    existing = list(c_usuarios.query_items(
        f"SELECT c.email, c.rol FROM c WHERE c.email = '{req.email}'",
        enable_cross_partition_query=True))
    if not existing:
        raise HTTPException(status_code=404, detail=f"No existe ningún usuario con el correo '{req.email}'")
    if existing[0].get("rol") not in ["estudiante"]:
        raise HTTPException(status_code=400, detail=f"El usuario '{req.email}' no tiene rol de estudiante")
    if req.email not in doc["estudiantes"]:
        doc["estudiantes"].append(req.email)
        c_grupos.upsert_item(doc)
    return {"mensaje": f"{req.email} agregado al grupo"}

@app.post("/admin/grupos/{grupo_id}/quitar-estudiante")
def quitar_estudiante_admin(grupo_id: str, req: AgregarEstudiante, user=Depends(require_admin)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    doc["estudiantes"] = [e for e in doc["estudiantes"] if e != req.email]
    c_grupos.upsert_item(doc)
    return {"mensaje": f"{req.email} quitado del grupo"}

@app.delete("/admin/grupos/{grupo_id}")
def eliminar_grupo_admin(grupo_id: str, user=Depends(require_admin)):
    try:
        c_grupos.delete_item(item=grupo_id, partition_key=grupo_id)
        return {"mensaje": "Grupo eliminado"}
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")

# ---------------------------------------------------------------------------
# DOCENTE — Panel propio
# ---------------------------------------------------------------------------
def require_docente(user=Depends(get_current_user)):
    if user["rol"] not in ["docente", "admin"]:
        raise HTTPException(status_code=403, detail="Acceso solo para docentes")
    return user

@app.get("/docente/mis-grupos")
def mis_grupos(user=Depends(require_docente)):
    """Devuelve los grupos donde el docente autenticado es el responsable."""
    grupos = list(c_grupos.query_items(
        f"SELECT * FROM c WHERE c.docente_email = '{user['email']}'",
        enable_cross_partition_query=True))
    return grupos

@app.post("/docente/grupos")
def crear_grupo_docente(req: GrupoCreate, user=Depends(require_docente)):
    """El docente crea su propio grupo — queda asignado como docente automáticamente."""
    grupo_id = str(uuid.uuid4())

    # Detecta institución del docente si no se provee
    institucion_id = req.institucion_id
    if not institucion_id:
        uq = f"SELECT c.institucion_id FROM c WHERE c.email = '{user['email']}'"
        ur = list(c_usuarios.query_items(uq, enable_cross_partition_query=True))
        if ur: institucion_id = ur[0].get("institucion_id")

    doc = {
        "id":             grupo_id,
        "nombre":         req.nombre,
        "institucion_id": institucion_id,
        "docente_email":  user["email"],   # siempre el docente autenticado
        "estudiantes":    req.estudiantes or [],
        "creado_en":      datetime.utcnow().isoformat(),
        "creado_por":     user["email"],
    }
    c_grupos.create_item(doc)
    return {"id": grupo_id, "mensaje": "Grupo creado"}

@app.put("/docente/grupos/{grupo_id}")
def editar_grupo_docente(grupo_id: str, req: GrupoUpdate, user=Depends(require_docente)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if doc["docente_email"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes editar un grupo que no es tuyo")
    if req.nombre      is not None: doc["nombre"]      = req.nombre
    if req.estudiantes is not None: doc["estudiantes"] = req.estudiantes
    doc["actualizado_en"] = datetime.utcnow().isoformat()
    c_grupos.upsert_item(doc)
    return {"mensaje": "Grupo actualizado"}

@app.delete("/docente/grupos/{grupo_id}")
def eliminar_grupo_docente(grupo_id: str, user=Depends(require_docente)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if doc["docente_email"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes eliminar un grupo que no es tuyo")
    c_grupos.delete_item(item=grupo_id, partition_key=grupo_id)
    return {"mensaje": "Grupo eliminado"}

@app.post("/docente/grupos/{grupo_id}/agregar-estudiante")
def agregar_estudiante_docente(grupo_id: str, req: AgregarEstudiante, user=Depends(require_docente)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if doc["docente_email"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes modificar un grupo que no es tuyo")
    # Verifica que el email corresponde a un usuario registrado con rol estudiante
    existing = list(c_usuarios.query_items(
        f"SELECT c.email, c.rol FROM c WHERE c.email = '{req.email}'",
        enable_cross_partition_query=True))
    if not existing:
        raise HTTPException(status_code=404, detail=f"No existe ningún usuario con el correo '{req.email}'")
    if existing[0].get("rol") not in ["estudiante"]:
        raise HTTPException(status_code=400, detail=f"El usuario '{req.email}' no tiene rol de estudiante")
    if req.email not in doc["estudiantes"]:
        doc["estudiantes"].append(req.email)
        c_grupos.upsert_item(doc)
    return {"mensaje": f"{req.email} agregado"}

@app.post("/docente/grupos/{grupo_id}/quitar-estudiante")
def quitar_estudiante_docente(grupo_id: str, req: AgregarEstudiante, user=Depends(require_docente)):
    try: doc = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if doc["docente_email"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes modificar un grupo que no es tuyo")
    doc["estudiantes"] = [e for e in doc["estudiantes"] if e != req.email]
    c_grupos.upsert_item(doc)
    return {"mensaje": f"{req.email} quitado"}

@app.get("/docente/grupo/{grupo_id}/sesiones")
def sesiones_de_grupo(grupo_id: str, user=Depends(require_docente)):
    """Devuelve las sesiones de todos los estudiantes del grupo."""
    try: grupo = c_grupos.read_item(item=grupo_id, partition_key=grupo_id)
    except Exception: raise HTTPException(status_code=404, detail="Grupo no encontrado")
    if grupo["docente_email"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    estudiantes = grupo.get("estudiantes", [])
    if not estudiantes:
        return []

    # Busca sesiones de cada estudiante del grupo
    emails_str = ",".join([f"'{e}'" for e in estudiantes])
    query = f"""
        SELECT c.sesion_id, c.usuario_id, c.patient_name, c.inicio, c.fin, c.puntuacion, c.estado
        FROM c WHERE c.usuario_id IN ({emails_str})
        ORDER BY c.inicio DESC
    """
    sesiones = list(c_sesiones.query_items(query, enable_cross_partition_query=True))
    return sesiones

@app.post("/docente/retroalimentacion")
def crear_retroalimentacion(req: RetroCreate, user=Depends(require_docente)):
    # Verifica que el docente tiene acceso a esta sesión (pertenece a un estudiante de su grupo)
    grupos = list(c_grupos.query_items(
        f"SELECT * FROM c WHERE c.docente_email = '{user['email']}'",
        enable_cross_partition_query=True))
    todos_estudiantes = set()
    for g in grupos:
        todos_estudiantes.update(g.get("estudiantes", []))

    if req.estudiante_email not in todos_estudiantes and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Este estudiante no está en ninguno de tus grupos")

    retro_id = str(uuid.uuid4())
    doc = {
        "id":               retro_id,
        "sesion_id":        req.sesion_id,
        "estudiante_email": req.estudiante_email,
        "docente_email":    user["email"],
        "comentario":       req.comentario,
        "creado_en":        datetime.utcnow().isoformat(),
    }
    c_retroalimentaciones.create_item(doc)
    return {"id": retro_id, "mensaje": "Retroalimentación guardada"}

@app.get("/docente/retroalimentaciones/{sesion_id}")
def retros_de_sesion(sesion_id: str, user=Depends(require_docente)):
    """El docente consulta las retroalimentaciones que él mismo ha dado sobre una sesión."""
    items = list(c_retroalimentaciones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    return items

# ---------------------------------------------------------------------------
# ESTUDIANTE — endpoints propios
# ---------------------------------------------------------------------------
@app.get("/estudiante/retroalimentaciones")
def mis_retroalimentaciones(user=Depends(get_current_user)):
    """El estudiante ve todos los comentarios que los docentes han dejado sobre sus sesiones."""
    items = list(c_retroalimentaciones.query_items(
        f"SELECT * FROM c WHERE c.estudiante_email = '{user['email']}' ORDER BY c.creado_en DESC",
        enable_cross_partition_query=True))
    return items

@app.delete("/historial/sesion/{sesion_id}")
def eliminar_sesion(sesion_id: str, user=Depends(get_current_user)):
    """El estudiante elimina una sesión propia completamente (sesion + detalle + retroalimentaciones)."""
    # Verifica que la sesión pertenece al usuario (a menos que sea admin)
    ses_items = list(c_sesiones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    if not ses_items:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    if ses_items[0]["usuario_id"] != user["email"] and user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="No puedes eliminar sesiones de otros usuarios")

    # Elimina de sesiones (intentando con claves de partición más comunes)
    try:
        # Caso típico: partición en /id
        c_sesiones.delete_item(item=ses_items[0]["id"], partition_key=ses_items[0]["id"])
    except Exception:
        try:
            # Alternativa: partición en /sesion_id
            c_sesiones.delete_item(item=ses_items[0]["id"], partition_key=ses_items[0]["sesion_id"])
        except Exception:
            try:
                # Alternativa: partición en /usuario_id
                c_sesiones.delete_item(item=ses_items[0]["id"], partition_key=ses_items[0]["usuario_id"])
            except Exception:
                pass

    # Elimina detalle
    det_items = list(c_detalle.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    for d in det_items:
        try:
            c_detalle.delete_item(item=d["id"], partition_key=d["id"])
        except Exception:
            try:
                c_detalle.delete_item(item=d["id"], partition_key=d["sesion_id"])
            except Exception:
                pass

    # Elimina retroalimentaciones asociadas
    retro_items = list(c_retroalimentaciones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    for r in retro_items:
        try:
            c_retroalimentaciones.delete_item(item=r["id"], partition_key=r["id"])
        except Exception:
            try:
                c_retroalimentaciones.delete_item(item=r["id"], partition_key=r["sesion_id"])
            except Exception:
                pass

    return {"mensaje": "Sesión eliminada completamente"}

# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}