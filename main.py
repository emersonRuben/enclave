from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import asyncio
import logging
import os
from dotenv import load_dotenv
from mqtt_client import manejadorMqtt, TOPICO_COMANDO
from camera_facial import sistema_facial

# Cargar variables de entorno
load_dotenv()

# Configuración
# CAMERA_STREAM_URL ahora apunta al endpoint local de Python, no al ESP32 directo
CAMERA_STREAM_URL = "/video_feed"

# Configurar Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Control Caja Fuerte IoT")

# Montar Archivos Estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def eventoInicio():
    loop = asyncio.get_event_loop()
    # Mqtt se inicia con el loop actual. La gestión de clientes se realiza en /ws.
    manejadorMqtt.iniciar(loop)

@app.on_event("shutdown")
async def eventoCierre():
    manejadorMqtt.detener()
    sistema_facial.detener_escaneo()

@app.get("/", response_class=HTMLResponse)
async def obtenerInicio(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "camera_stream_url": CAMERA_STREAM_URL,
        "system_status": "ESPERA"
    })

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(sistema_facial.generar_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/api/scan/start")
async def iniciar_escaneo():
    return {"estado": "exito", "mensaje": "Escaneo iniciado"}

@app.post("/api/scan-face")
async def verificar_rostro():
    resultado = sistema_facial.verificar_identidad()
    return resultado

class RegistroData(BaseModel):
    nombre: str
    imagen: str | None = None # Base64 opcional

@app.post("/api/register-face")
async def register_face(data: RegistroData):
    """Registra el rostro. Si viene 'imagen', usa esa. Si no, usa el stream."""
    resultado = sistema_facial.registrar_usuario(data.nombre, data.imagen)
    return resultado

@app.post("/api/comando/{accion}")
async def enviarComando(accion: str):
    accion = accion.upper()
    if accion in ["ABRIR", "CERRAR"]:
        manejadorMqtt.publicar(TOPICO_COMANDO, accion)
        return {"estado": "exito", "mensaje": f"Comando {accion} enviado"}
    return {"estado": "error", "mensaje": "Comando inválido"}

@app.websocket("/ws")
async def endpointWebsocket(websocket: WebSocket):
    await websocket.accept()

    async def enviarMensaje(tipo, datos):
        await websocket.send_json({"tipo": tipo, "datos": datos})
    
    # Registrar este cliente para recibir actualizaciones MQTT
    manejadorMqtt.registrar_cliente(enviarMensaje)

    try:
        # 1. Enviar estado actual (cached en manejadorMqtt)
        await enviarMensaje("estado", manejadorMqtt.estadoActual)

        # 2. Enviar historial de logs (en memoria)
        for log in reversed(manejadorMqtt.historialLogs):
            await websocket.send_json(log)
        
        while True:
            # Mantener conexión viva y escuchar comandos desde el Front
            data = await websocket.receive_text()
            # ... Logica de comandos (opcional si se enviaran por WS) ...
    except WebSocketDisconnect:
        manejadorMqtt.deregistrar_cliente(enviarMensaje)
    except Exception as e:
        print(f"Error en WebSocket: {e}")
        manejadorMqtt.deregistrar_cliente(enviarMensaje)
