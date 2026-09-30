# Psi-IA — Entrenamiento de Psicólogos

Plataforma de entrenamiento clínico con inteligencia artificial para estudiantes de psicología. Permite practicar sesiones con pacientes simulados, recibir análisis automático del desempeño y consultar retroalimentación docente.

## Funcionalidades

- Simulación de conversaciones terapéuticas con pacientes generados mediante IA.
- Casos clínicos organizados por categoría y dificultad.
- Historial y reanudación de sesiones.
- Análisis IA del desempeño del estudiante.
- Puntuación, fortalezas, áreas de mejora y recomendaciones.
- Evaluación orientativa para alta terapéutica.
- Panel docente para administrar grupos, revisar sesiones y dejar retroalimentación.
- Panel administrador para gestionar usuarios, instituciones, casos, categorías, pagos y configuraciones.
- Autenticación mediante JWT y control de acceso por roles.

## Roles

- **Estudiante:** practica sesiones y consulta sus resultados.
- **Docente:** administra grupos, revisa sesiones y entrega retroalimentación.
- **Encargado:** gestiona usuarios y datos de su institución.
- **Administrador:** administra la plataforma completa.

## Arquitectura

```text
Entrenamiento_Psicologos/
├── backend/
│   ├── backend.py
│   ├── requirements.txt
│   └── startup.txt
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── scripts/
│   ├── Entrenamiento_gpt_4o.py
│   └── upload_assets.py
├── package.json
└── .gitignore
```

## Tecnologías

### Frontend

- HTML5
- CSS3
- JavaScript
- Azure Static Web Apps

### Backend

- Python 3
- FastAPI
- Uvicorn / Gunicorn
- Pydantic
- Azure Cosmos DB
- Azure OpenAI mediante LangChain
- JWT
- Passlib y bcrypt

## Requisitos

- Python 3.9 o superior.
- Node.js y npm, si se requieren tareas relacionadas con los assets.
- Una cuenta y configuración de Azure OpenAI.
- Una instancia de Azure Cosmos DB.
- Variables de entorno configuradas.

## Instalación del backend

```bash
git clone https://github.com/Ssalazarp420/Entrenamiento_Psicologos.git
cd Entrenamiento_Psicologos/backend
python -m venv .venv
```

Activar el entorno virtual:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Variables de entorno

El backend utiliza credenciales para Azure OpenAI, Azure Cosmos DB y JWT. Configúralas como variables de entorno o mediante un archivo local no versionado:

```env
AZURE_OPENAI_API_KEY=tu_clave
AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=tu_deployment
AZURE_OPENAI_API_VERSION=tu_version
COSMOS_CONNECTION_STRING=tu_cadena_de_conexion
JWT_SECRET=una_clave_segura
```

No publiques claves, cadenas de conexión ni archivos `.env` en el repositorio. Si alguna credencial fue expuesta, revócala y genera una nueva.

## Ejecutar localmente

Desde `backend/`:

```bash
uvicorn backend:app --reload
```

La API estará disponible normalmente en:

```text
http://127.0.0.1:8000
```

Documentación interactiva de FastAPI:

```text
http://127.0.0.1:8000/docs
```

Para un despliegue con Gunicorn se puede utilizar:

```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker backend:app
```

Abre `frontend/index.html` mediante un servidor web local y verifica que la URL de la API y la configuración de CORS coincidan con tu entorno.

## API principal

Algunos endpoints disponibles son:

- `POST /auth/register`: registrar usuarios.
- `POST /auth/login`: iniciar sesión.
- `GET /auth/me`: consultar el usuario autenticado.
- `GET /patients`: listar pacientes simulados.
- `POST /session/new`: crear o reanudar una sesión.
- `POST /chat`: enviar una intervención al paciente simulado.
- `POST /session/end`: finalizar y analizar una sesión.
- `GET /historial/mis-sesiones`: consultar el historial propio.
- `GET /health`: comprobar el estado del backend.

También existen endpoints protegidos para administración, grupos, instituciones, casos IA, pagos y retroalimentación docente.

## Pacientes simulados

El backend incluye perfiles iniciales, entre ellos:

- **Mateo:** estudiante universitario de 22 años, caso de ansiedad y dificultad moderada.
- **Lucía:** docente de primaria de 35 años, caso relacionado con estrés laboral y burnout.

Los administradores pueden crear y editar casos, categorías, instrucciones de personalidad y prompts de análisis.

## Uso responsable

Esta plataforma es una herramienta educativa para practicar habilidades de entrevista y razonamiento clínico. Sus respuestas y análisis son generados por IA y no sustituyen la supervisión profesional, una evaluación clínica real ni la atención psicológica a pacientes.

## Estado del proyecto

Proyecto en desarrollo. La configuración de Azure, las credenciales y los recursos externos deben adaptarse al entorno de despliegue utilizado.

## Licencia

El repositorio no especifica actualmente una licencia de uso.

## Enlace

[Repositorio Entrenamiento_Psicologos](https://github.com/Ssalazarp420/Entrenamiento_Psicologos)
