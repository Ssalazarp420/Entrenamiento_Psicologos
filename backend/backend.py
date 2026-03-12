import os
import uuid
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
    patient_id = req.patient_id or "mateo"
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

    # Busca el detalle con la transcripción previa
    det_items = list(c_detalle.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True,
    ))
    if not det_items:
        raise HTTPException(status_code=404, detail="La sesión no tiene historial para reanudar")

    detalle = det_items[0]
    patient_id = ses.get("patient_id")
    casos = get_casos_dict()
    if patient_id not in casos:
        raise HTTPException(status_code=400, detail="Perfil de paciente no encontrado para esta sesión")
    profile = casos[patient_id]

    # Reconstruye los mensajes para el modelo a partir de la transcripción
    transcripcion = detalle.get("transcripcion", "") or ""
    mensajes_lm: List = [SystemMessage(content=profile["instruccion"])]
    history_for_client = []

    nombre_paciente = profile["name"]
    for linea in transcripcion.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        # Espera formato "Psicólogo: ..." o "<NombrePaciente>: ..."
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

    if len(mensajes_lm) == 1:
        # No se pudo reconstruir nada útil
        raise HTTPException(status_code=400, detail="No se pudo reconstruir el historial de la sesión")

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


@app.post("/chat")
def chat(req: MessageRequest, user=Depends(get_current_user)):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    model = get_model()
    session = sessions[req.session_id]
    session["messages"].append(HumanMessage(content=req.message))
    try:
        response = model.invoke(session["messages"])
        session["messages"].append(AIMessage(content=response.content))
        return {"reply": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/session/end")
def end_session(req: SessionResponse, user=Depends(get_current_user)):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    model = get_model()
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
        feedback_paciente = model.invoke([
            SystemMessage(content=profile["instruccion_feedback"]),
            HumanMessage(content=f"Esta fue nuestra sesión:\n{historial_texto}\n\n¿Cómo te sentiste?")
        ]).content
        analisis = model.invoke([
            SystemMessage(content=analisis_objetivo),
            HumanMessage(content=f"Paciente simulado: {profile['name']}, {profile['age']} años — {profile.get('descripcion', '')}\n\nSesión completa:\n{historial_texto}")
        ]).content
        puntuacion = extraer_puntuacion(analisis)
        c_sesiones.upsert_item({
            "id": req.session_id, "sesion_id": req.session_id, "usuario_id": user["email"],
            "patient_id": patient_id, "patient_name": profile["name"],
            "inicio": session.get("inicio"), "fin": datetime.utcnow().isoformat(),
            "estado": "completada", "puntuacion": puntuacion,
        })
        c_detalle.create_item({
            "id": str(uuid.uuid4()), "sesion_id": req.session_id, "usuario_id": user["email"],
            "transcripcion": historial_texto, "feedback_paciente": feedback_paciente,
            "analisis_objetivo": analisis, "guardado_en": datetime.utcnow().isoformat(),
        })
        del sessions[req.session_id]
        return {"patient_id": patient_id, "patient_name": profile["name"],
                "feedback_paciente": feedback_paciente, "analisis_objetivo": analisis, "puntuacion": puntuacion}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# HISTORIAL
# ---------------------------------------------------------------------------
@app.get("/historial/mis-sesiones")
def mis_sesiones(user=Depends(get_current_user)):
    query = f"SELECT c.sesion_id, c.patient_name, c.inicio, c.fin, c.puntuacion, c.estado FROM c WHERE c.usuario_id = '{user['email']}' ORDER BY c.inicio DESC"
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

    # Elimina de sesiones
    try: c_sesiones.delete_item(item=ses_items[0]["id"], partition_key=ses_items[0]["sesion_id"])
    except Exception: pass

    # Elimina detalle
    det_items = list(c_detalle.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    for d in det_items:
        try: c_detalle.delete_item(item=d["id"], partition_key=d["sesion_id"])
        except Exception: pass

    # Elimina retroalimentaciones asociadas
    retro_items = list(c_retroalimentaciones.query_items(
        f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'",
        enable_cross_partition_query=True))
    for r in retro_items:
        try: c_retroalimentaciones.delete_item(item=r["id"], partition_key=r["sesion_id"])
        except Exception: pass

    return {"mensaje": "Sesión eliminada completamente"}

# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}