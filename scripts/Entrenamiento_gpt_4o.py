import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# 1. Cargamos las variables de entorno desde el archivo .env
load_dotenv("Conexion_Azure.env")

if not os.getenv("AZURE_OPENAI_API_KEY"):
    print("Error: No se cargaron las variables de Conexion_Azure.env")
else:
    model = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    )

    # 2. Personalidad del paciente simulado
    instruccion_paciente = """
    Eres 'Mateo', un joven de 22 años que estudia ingeniería. 
    Has venido a terapia obligado por tus padres porque dicen que 'no sales de tu cuarto'. 
    Te sientes incomprendido y crees que el psicólogo es solo un aliado de tus padres. 
    Responde de forma cortante, evita el contacto visual (descríbelo con acciones entre asteriscos) 
    y desafía suavemente las preguntas del terapeuta para ver si realmente le importas o solo es su trabajo.
    """

    # 3. Inicializamos el historial con la instrucción del sistema
    mensajes = [SystemMessage(content=instruccion_paciente)]

    print("=" * 50)
    print("   Simulador de Consulta Psicológica")
    print("   Paciente: Mateo (22 años)")
    print("=" * 50)
    print("Escribe 'salir' para terminar la sesión.\n")

    # 4. Loop de conversación con historial acumulado
    while True:
        entrada = input("Psicólogo: ").strip()

        if not entrada:
            continue

        if entrada.lower() == "salir":
            print("\n--- Sesión terminada ---")
            break

        # Agregamos el mensaje del psicólogo al historial
        mensajes.append(HumanMessage(content=entrada))

        try:
            # Enviamos todo el historial al modelo
            response = model.invoke(mensajes)
            print(f"\nMateo: {response.content}\n")

            # Guardamos la respuesta de Mateo en el historial
            mensajes.append(AIMessage(content=response.content))

        except Exception as e:
            print(f"Error técnico: {e}")
            break