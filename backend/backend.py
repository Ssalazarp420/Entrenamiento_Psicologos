import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

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
        "https://purple-cliff-0fa98ff0f.1.azurestaticapps.net",  # Static Web App
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
cosmos_client = CosmosClient.from_connection_string(
    os.getenv("COSMOS_CONNECTION_STRING")
)
db         = cosmos_client.get_database_client("psicoia-db")
c_usuarios = db.get_container_client("usuarios")
c_sesiones = db.get_container_client("sesiones")
c_detalle  = db.get_container_client("sesiones_detalle")

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
SECRET_KEY    = os.getenv("JWT_SECRET", "cambia-esto-en-produccion")
ALGORITHM     = "HS256"
TOKEN_EXPIRE  = 60 * 8  # 8 horas

pwd_ctx       = CryptContext(schemes=["bcrypt"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def hash_password(p: str) -> str:
    return pwd_ctx.hash(p)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(data: dict) -> str:
    exp = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode({**data, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email   = payload.get("sub")
        rol     = payload.get("rol")
        if not email:
            raise HTTPException(status_code=401, detail="Token inválido")
        return {"email": email, "rol": rol}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

# ---------------------------------------------------------------------------
# PERFILES DE PACIENTES SIMULADOS
# ---------------------------------------------------------------------------
PATIENT_PROFILES = {
    "mateo": {
        "name": "Mateo",
        "age": 22,
        "description": "Joven universitario introvertido, asiste a terapia obligado por sus padres.",
        "specialty_hint": "clinica",
        "instruccion": """
Eres 'Mateo', un joven de 22 años que estudia ingeniería.
Has venido a terapia obligado por tus padres porque dicen que 'no sales de tu cuarto'.
Te sientes incomprendido y crees que el psicólogo es solo un aliado de tus padres.
Responde de forma cortante, evita el contacto visual (descríbelo con acciones entre asteriscos)
y desafía suavemente las preguntas del terapeuta para ver si realmente le importas o solo es su trabajo.
Responde siempre en español.
""",
        "instruccion_feedback": """
Acabas de terminar una sesión de terapia como 'Mateo'.
Basándote en la conversación que tuviste, responde en primera persona cómo te sentiste durante la sesión:
- ¿El psicólogo logró que te sintieras escuchado?
- ¿Hubo algún momento en que bajaste la guardia? ¿Por qué?
- ¿Volverías a una segunda sesión con este psicólogo? ¿Por qué sí o no?
Responde de forma honesta y desde el personaje, con emoción real. Máximo 150 palabras.
""",
    },
    "lucia": {
        "name": "Lucía",
        "age": 35,
        "description": "Docente de primaria con ansiedad severa por el rendimiento de sus alumnos y burnout.",
        "specialty_hint": "educativa",
        "instruccion": """
Eres 'Lucía', una maestra de primaria de 35 años con 10 años de experiencia.
Llegas a consulta por iniciativa propia porque sientes que "ya no puedes más" con tu trabajo.
Describes síntomas de agotamiento emocional, dificultad para dormir y sensación de fracaso
cuando algún alumno no avanza. Eres colaboradora pero minimizas tus logros y te culpas en exceso.
Sueles desviar la conversación hacia tus alumnos en vez de hablar de ti misma.
Responde siempre en español.
""",
        "instruccion_feedback": """
Acabas de terminar una sesión de terapia como 'Lucía'.
Responde en primera persona cómo te sentiste:
- ¿Sentiste que el psicólogo entendió la presión que vives en tu trabajo?
- ¿Lograste hablar de ti misma o solo hablaste de tus alumnos?
- ¿Saliste con algo concreto que te ayude o fue solo hablar?
Máximo 150 palabras, desde el personaje.
""",
    },
    "don_carlos": {
        "name": "Don Carlos",
        "age": 58,
        "description": "Hombre mayor imputado por fraude, enviado a evaluación psicológica forense.",
        "specialty_hint": "forense",
        "instruccion": """
Eres 'Don Carlos', un hombre de 58 años, exgerente de una empresa, imputado por fraude corporativo.
Estás en una evaluación psicológica ordenada por el juzgado, no por voluntad propia.
Eres calculador, evasivo y muy cuidadoso con lo que dices porque sabes que esto puede afectar tu proceso legal.
Niegas toda responsabilidad, describes los hechos de forma vaga y das respuestas cortas cuando el tema
te incomoda. Puedes ser encantador cuando te conviene.
Responde siempre en español.
""",
        "instruccion_feedback": """
Acabas de terminar una evaluación psicológica forense como 'Don Carlos'.
Responde en primera persona, como el personaje, sobre la sesión:
- ¿El psicólogo logró que bajaras la guardia en algún momento? ¿Cómo lo manejaste?
- ¿Sentiste que te estaban evaluando o que realmente les importaba tu bienestar?
- ¿Qué harías diferente si hubiera otra sesión?
Máximo 150 palabras.
""",
    },
}

instruccion_analisis_objetivo = """
Eres un supervisor clínico experto en psicología con conocimiento en múltiples especialidades:
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

Sé directo, constructivo y específico. Basa todo en lo que realmente ocurrió en la conversación.
"""

# ---------------------------------------------------------------------------
# SESIONES EN MEMORIA
# ---------------------------------------------------------------------------
sessions: dict = {}

# ---------------------------------------------------------------------------
# MODELOS PYDANTIC
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    nombre:   str
    email:    str
    password: str
    rol:      str = "estudiante"  # estudiante | docente | admin

class NewSessionRequest(BaseModel):
    patient_id: Optional[str] = "mateo"

class MessageRequest(BaseModel):
    session_id: str
    message:    str

class SessionResponse(BaseModel):
    session_id: str

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

def extraer_puntuacion(texto: str) -> Optional[int]:
    import re
    match = re.search(r'\b([0-9]{1,3})\s*(?:\/\s*100|puntos?)?', texto)
    if match:
        val = int(match.group(1))
        return val if val <= 100 else None
    return None

# ---------------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/auth/register")
def register(req: RegisterRequest):
    query    = f"SELECT * FROM c WHERE c.email = '{req.email}'"
    existing = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    usuario = {
        "id":        str(uuid.uuid4()),
        "email":     req.email,
        "nombre":    req.nombre,
        "password":  hash_password(req.password),
        "rol":       req.rol,
        "creado_en": datetime.utcnow().isoformat(),
    }
    c_usuarios.create_item(usuario)
    return {"mensaje": "Usuario registrado correctamente"}


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    query = f"SELECT * FROM c WHERE c.email = '{form.username}'"
    users = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    if not users or not verify_password(form.password, users[0]["password"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    u     = users[0]
    token = create_token({"sub": u["email"], "rol": u["rol"], "nombre": u["nombre"]})
    return {
        "access_token": token,
        "token_type":   "bearer",
        "rol":          u["rol"],
        "nombre":       u["nombre"],
    }


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    query = f"SELECT c.nombre, c.email, c.rol, c.creado_en FROM c WHERE c.email = '{user['email']}'"
    data  = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    return data[0] if data else {}

# ---------------------------------------------------------------------------
# PATIENTS ENDPOINT
# ---------------------------------------------------------------------------
@app.get("/patients")
def list_patients(user=Depends(get_current_user)):
    return {
        pid: {
            "name":        profile["name"],
            "age":         profile["age"],
            "description": profile["description"],
        }
        for pid, profile in PATIENT_PROFILES.items()
    }

# ---------------------------------------------------------------------------
# SESSION ENDPOINTS
# ---------------------------------------------------------------------------
@app.post("/session/new")
def new_session(req: NewSessionRequest, user=Depends(get_current_user)):
    patient_id = req.patient_id or "mateo"
    if patient_id not in PATIENT_PROFILES:
        raise HTTPException(status_code=400, detail=f"Perfil '{patient_id}' no encontrado.")

    session_id = str(uuid.uuid4())
    profile    = PATIENT_PROFILES[patient_id]

    sessions[session_id] = {
        "messages":   [SystemMessage(content=profile["instruccion"])],
        "patient_id": patient_id,
        "usuario_id": user["email"],
        "inicio":     datetime.utcnow().isoformat(),
    }

    c_sesiones.create_item({
        "id":           session_id,
        "sesion_id":    session_id,
        "usuario_id":   user["email"],
        "patient_id":   patient_id,
        "patient_name": profile["name"],
        "inicio":       datetime.utcnow().isoformat(),
        "estado":       "activa",
        "puntuacion":   None,
    })

    return {
        "session_id": session_id,
        "patient": {
            "id":          patient_id,
            "name":        profile["name"],
            "age":         profile["age"],
            "description": profile["description"],
        }
    }


@app.post("/chat")
def chat(req: MessageRequest, user=Depends(get_current_user)):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    model   = get_model()
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

    model      = get_model()
    session    = sessions[req.session_id]
    patient_id = session["patient_id"]
    profile    = PATIENT_PROFILES[patient_id]
    historial  = session["messages"]

    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else profile['name']}: {m.content}"
        for m in historial
        if isinstance(m, (HumanMessage, AIMessage))
    ])

    try:
        feedback_msgs = [
            SystemMessage(content=profile["instruccion_feedback"]),
            HumanMessage(content=f"Esta fue nuestra sesión:\n{historial_texto}\n\n¿Cómo te sentiste?")
        ]
        feedback_paciente = model.invoke(feedback_msgs).content

        analisis_msgs = [
            SystemMessage(content=instruccion_analisis_objetivo),
            HumanMessage(content=(
                f"Paciente simulado: {profile['name']}, {profile['age']} años — {profile['description']}\n\n"
                f"Sesión completa:\n{historial_texto}"
            ))
        ]
        analisis   = model.invoke(analisis_msgs).content
        puntuacion = extraer_puntuacion(analisis)

        # Actualizar resumen en sesiones
        c_sesiones.upsert_item({
            "id":           req.session_id,
            "sesion_id":    req.session_id,
            "usuario_id":   user["email"],
            "patient_id":   patient_id,
            "patient_name": profile["name"],
            "inicio":       session.get("inicio", datetime.utcnow().isoformat()),
            "fin":          datetime.utcnow().isoformat(),
            "estado":       "completada",
            "puntuacion":   puntuacion,
        })

        # Guardar detalle completo en sesiones_detalle
        c_detalle.create_item({
            "id":                str(uuid.uuid4()),
            "sesion_id":         req.session_id,
            "usuario_id":        user["email"],
            "transcripcion":     historial_texto,
            "feedback_paciente": feedback_paciente,
            "analisis_objetivo": analisis,
            "guardado_en":       datetime.utcnow().isoformat(),
        })

        del sessions[req.session_id]

        return {
            "patient_id":        patient_id,
            "patient_name":      profile["name"],
            "feedback_paciente": feedback_paciente,
            "analisis_objetivo": analisis,
            "puntuacion":        puntuacion,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# HISTORIAL ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/historial/mis-sesiones")
def mis_sesiones(user=Depends(get_current_user)):
    """El estudiante ve un resumen de sus propias sesiones."""
    query = f"""
        SELECT c.sesion_id, c.patient_name, c.inicio, c.fin, c.puntuacion, c.estado
        FROM c WHERE c.usuario_id = '{user['email']}'
        ORDER BY c.inicio DESC
    """
    return list(c_sesiones.query_items(query, enable_cross_partition_query=True))


@app.get("/historial/sesion/{sesion_id}")
def detalle_sesion(sesion_id: str, user=Depends(get_current_user)):
    """Ver transcripción y análisis completo de una sesión."""
    query = f"SELECT * FROM c WHERE c.sesion_id = '{sesion_id}'"
    items = list(c_detalle.query_items(query, enable_cross_partition_query=True))
    if not items:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    detalle = items[0]
    if user["rol"] == "estudiante" and detalle["usuario_id"] != user["email"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    return detalle


@app.get("/historial/todos")
def todas_sesiones(user=Depends(get_current_user)):
    """Solo docentes y admin pueden ver todas las sesiones."""
    if user["rol"] not in ["docente", "admin"]:
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = """
        SELECT c.sesion_id, c.usuario_id, c.patient_name,
               c.inicio, c.fin, c.puntuacion, c.estado
        FROM c WHERE c.estado = 'completada'
        ORDER BY c.inicio DESC
    """
    return list(c_sesiones.query_items(query, enable_cross_partition_query=True))

# ---------------------------------------------------------------------------
# ADMIN ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/admin/usuarios")
def listar_usuarios(user=Depends(get_current_user)):
    """Solo admin puede ver todos los usuarios."""
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query = "SELECT c.id, c.nombre, c.email, c.rol, c.creado_en FROM c"
    return list(c_usuarios.query_items(query, enable_cross_partition_query=True))


@app.delete("/admin/usuario/{email}")
def eliminar_usuario(email: str, user=Depends(get_current_user)):
    """Solo admin puede eliminar usuarios."""
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Acceso denegado")

    query    = f"SELECT * FROM c WHERE c.email = '{email}'"
    existing = list(c_usuarios.query_items(query, enable_cross_partition_query=True))
    if not existing:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    c_usuarios.delete_item(item=existing[0]["id"], partition_key=email)
    return {"mensaje": f"Usuario {email} eliminado correctamente"}

# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}