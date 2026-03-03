import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Almacén de sesiones en memoria (una por usuario)
sessions: dict = {}

instruccion_paciente = """
Eres 'Mateo', un joven de 22 años que estudia ingeniería. 
Has venido a terapia obligado por tus padres porque dicen que 'no sales de tu cuarto'. 
Te sientes incomprendido y crees que el psicólogo es solo un aliado de tus padres. 
Responde de forma cortante, evita el contacto visual (descríbelo con acciones entre asteriscos) 
y desafía suavemente las preguntas del terapeuta para ver si realmente le importas o solo es su trabajo.
Responde siempre en español.
"""

instruccion_feedback_mateo = """
Acabas de terminar una sesión de terapia como 'Mateo'. 
Basándote en la conversación que tuviste, responde en primera persona cómo te sentiste durante la sesión:
- ¿El psicólogo logró que te sintieras escuchado?
- ¿Hubo algún momento en que bajaste la guardia? ¿Por qué?
- ¿Volverías a una segunda sesión con este psicólogo? ¿Por qué sí o no?
Responde de forma honesta y desde el personaje, con emoción real. Máximo 150 palabras.
"""

instruccion_analisis_objetivo = """
Eres un supervisor clínico experto en psicología. Acabas de observar una sesión de práctica 
entre un psicólogo en formación y un paciente simulado llamado Mateo.

Analiza la sesión y entrega un reporte estructurado con:
1. **Puntuación global** (0-100): Basada en empatía, técnica, manejo del silencio y alianza terapéutica.
2. **Fortalezas** (máx 3): ¿Qué hizo bien el psicólogo?
3. **Áreas de mejora** (máx 3): ¿Qué debe trabajar?
4. **Momento clave**: El instante más importante de la sesión (positivo o negativo).
5. **Recomendación**: Una sugerencia concreta para la próxima sesión.

Sé directo, constructivo y específico. Basa todo en lo que realmente ocurrió en la conversación.
"""

def get_model():
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

class MessageRequest(BaseModel):
    session_id: str
    message: str

class SessionResponse(BaseModel):
    session_id: str

@app.post("/session/new")
def new_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = [SystemMessage(content=instruccion_paciente)]
    return {"session_id": session_id}

@app.post("/chat")
def chat(req: MessageRequest):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    model = get_model()
    sessions[req.session_id].append(HumanMessage(content=req.message))
    
    try:
        response = model.invoke(sessions[req.session_id])
        sessions[req.session_id].append(AIMessage(content=response.content))
        return {"reply": response.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/session/end")
def end_session(req: SessionResponse):
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    
    model = get_model()
    historial = sessions[req.session_id]
    
    # Construimos el texto del historial para los evaluadores
    historial_texto = "\n".join([
        f"{'Psicólogo' if isinstance(m, HumanMessage) else 'Mateo'}: {m.content}"
        for m in historial
        if isinstance(m, (HumanMessage, AIMessage))
    ])

    try:
        # Feedback emocional de Mateo
        feedback_mateo_msgs = [
            SystemMessage(content=instruccion_feedback_mateo),
            HumanMessage(content=f"Esta fue nuestra sesión:\n{historial_texto}\n\n¿Cómo te sentiste?")
        ]
        feedback_mateo = model.invoke(feedback_mateo_msgs).content

        # Análisis objetivo del supervisor
        analisis_msgs = [
            SystemMessage(content=instruccion_analisis_objetivo),
            HumanMessage(content=f"Aquí está la sesión completa:\n{historial_texto}")
        ]
        analisis = model.invoke(analisis_msgs).content

        # Limpiamos la sesión de memoria
        del sessions[req.session_id]

        return {
            "feedback_mateo": feedback_mateo,
            "analisis_objetivo": analisis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}
