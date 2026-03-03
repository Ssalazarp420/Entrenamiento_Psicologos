import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv("Conexion_Azure.env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# PERFILES DE PACIENTES SIMULADOS
# Cada perfil tiene: instruccion (system prompt del paciente) y metadatos
# ---------------------------------------------------------------------------

PATIENT_PROFILES = {
    "mateo": {
        "name": "Mateo",
        "age": 22,
        "description": "Joven universitario introvertido, asiste a terapia obligado por sus padres.",
        "specialty_hint": "clinica",  # orientación esperada (informativo)
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

# ---------------------------------------------------------------------------
# INSTRUCCIÓN DE ANÁLISIS OBJETIVO (incluye detección de enfoque terapéutico)
# ---------------------------------------------------------------------------

instruccion_analisis_objetivo = """
Eres un supervisor clínico experto en psicología con conocimiento en múltiples enfoques y corrientes
psicoterapéuticas: humanista, psicoanalítico/psicodinámico, cognitivo-conductual (TCC),
sistémico/familiar, existencial, gestáltico, narrativo, integrativo, entre otros.

Acabas de observar una sesión de práctica entre un psicólogo en formación y un paciente simulado.

Analiza la sesión y entrega un reporte estructurado con los siguientes puntos:

1. **Enfoque terapéutico detectado**: ¿Qué corriente o enfoque psicoterapéutico aplicó predominantemente
   el estudiante durante la sesión? Indica el enfoque principal y, si aplica, uno secundario.
   Justifica brevemente con ejemplos concretos tomados de la conversación (frases, preguntas o
   intervenciones específicas del estudiante).
   Opciones de referencia: Humanista, Psicoanalítico/Psicodinámico, Cognitivo-Conductual (TCC),
   Sistémico/Familiar, Existencial, Gestáltico, Narrativo, Integrativo, Otro (especificar).

2. **Puntuación global** (0-100): Basada en empatía, técnica, manejo del silencio y alianza terapéutica.

3. **Fortalezas** (máx 3): ¿Qué hizo bien el psicólogo?

4. **Áreas de mejora** (máx 3): ¿Qué debe trabajar?

5. **Momento clave**: El instante más importante de la sesión (positivo o negativo).

6. **Coherencia entre enfoque y paciente**: ¿El enfoque utilizado fue adecuado para el perfil de este
   paciente y su motivo de consulta? ¿Las técnicas e intervenciones fueron congruentes con la corriente
   detectada, o hubo mezclas inconsistentes?

7. **Recomendación**: Una sugerencia concreta para la próxima sesión, orientada a profundizar o ajustar
   el enfoque terapéutico empleado.

Sé directo, constructivo y específico. Basa todo en lo que realmente ocurrió en la conversación.
"""

# ---------------------------------------------------------------------------
# ALMACÉN DE SESIONES
# Cada sesión guarda: mensajes + patient_id
# ---------------------------------------------------------------------------

sessions: dict = {}  # { session_id: { "messages": [...], "patient_id": str } }


def get_model():
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )


# ---------------------------------------------------------------------------
# MODELOS PYDANTIC
# ---------------------------------------------------------------------------

class NewSessionRequest(BaseModel):
    patient_id: Optional[str] = "mateo"  # default al perfil original

class MessageRequest(BaseModel):
    session_id: str
    message: str

class SessionResponse(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/patients")
def list_patients():
    """Devuelve la lista de perfiles de pacientes disponibles."""
    return {
        pid: {
            "name": profile["name"],
            "age": profile["age"],
            "description": profile["description"],
        }
        for pid, profile in PATIENT_PROFILES.items()
    }


@app.post("/session/new")
def new_session(req: NewSessionRequest):
    patient_id = req.patient_id or "mateo"

    if patient_id not in PATIENT_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Perfil '{patient_id}' no encontrado. Disponibles: {list(PATIENT_PROFILES.keys())}"
        )

    session_id = str(uuid.uuid4())
    profile = PATIENT_PROFILES[patient_id]

    sessions[session_id] = {
        "messages": [SystemMessage(content=profile["instruccion"])],
        "patient_id": patient_id,
    }

    return {
        "session_id": session_id,
        "patient": {
            "id": patient_id,
            "name": profile["name"],
            "age": profile["age"],
            "description": profile["description"],
        }
    }


@app.post("/chat")
def chat(req: MessageRequest):
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
def end_session(req: SessionResponse):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    model = get_model()
    session = sessions[req.session_id]
    patient_id = session["patient_id"]
    profile = PATIENT_PROFILES[patient_id]
    historial = session["messages"]

    # Construir texto del historial para los evaluadores
    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else profile['name']}: {m.content}"
        for m in historial
        if isinstance(m, (HumanMessage, AIMessage))
    ])

    try:
        # Feedback emocional del paciente simulado
        feedback_msgs = [
            SystemMessage(content=profile["instruccion_feedback"]),
            HumanMessage(content=f"Esta fue nuestra sesión:\n{historial_texto}\n\n¿Cómo te sentiste?")
        ]
        feedback_paciente = model.invoke(feedback_msgs).content

        # Análisis objetivo del supervisor (con detección de enfoque terapéutico)
        analisis_msgs = [
            SystemMessage(content=instruccion_analisis_objetivo),
            HumanMessage(content=(
                f"Paciente simulado: {profile['name']}, {profile['age']} años — {profile['description']}\n\n"
                f"Sesión completa:\n{historial_texto}"
            ))
        ]
        analisis = model.invoke(analisis_msgs).content

        # Limpiar sesión de memoria
        del sessions[req.session_id]

        return {
            "patient_id": patient_id,
            "patient_name": profile["name"],
            "feedback_paciente": feedback_paciente,
            "analisis_objetivo": analisis,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}