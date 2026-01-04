from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import asyncio
import logging
import os
from dotenv import load_dotenv
from mqtt_client import manejadorMqtt, TOPICO_COMANDO

# Cargar variables de entorno
load_dotenv()

# Configuración
CAMERA_STREAM_URL = os.getenv("CAMERA_STREAM_URL", "http://10.93.36.6:81/stream")

# Configurar Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Control Caja Fuerte IoT")

# Montar Archivos Estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Gestor de WebSockets
class GestorConexiones:
    def __init__(self):
        self.conexionesActivas: list[WebSocket] = []

    async def conectar(self, websocket: WebSocket):
        await websocket.accept()
        self.conexionesActivas.append(websocket)

    def desconectar(self, websocket: WebSocket):
        self.conexionesActivas.remove(websocket)

    async def transmitir(self, mensaje: dict):
        for conexion in self.conexionesActivas:
            await conexion.send_json(mensaje)

gestor = GestorConexiones()

# Callback MQTT para enviar a WebSockets
async def mqttAWebsocket(tipoMensaje: str, payload: str):
    await gestor.transmitir({
        "tipo": tipoMensaje,
        "datos": payload
    })

@app.on_event("startup")
async def eventoInicio():
    loop = asyncio.get_event_loop()
    manejadorMqtt.establecerCallback(mqttAWebsocket)
    manejadorMqtt.iniciar(loop)

@app.on_event("shutdown")
async def eventoCierre():
    manejadorMqtt.detener()

@app.get("/", response_class=HTMLResponse)
async def obtenerInicio(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "camera_stream_url": CAMERA_STREAM_URL
    })

@app.post("/api/comando/{accion}")
async def enviarComando(accion: str):
    accion = accion.upper()
    if accion in ["ABRIR", "CERRAR"]:
        manejadorMqtt.publicar(TOPICO_COMANDO, accion)
        return {"estado": "exito", "mensaje": f"Comando {accion} enviado"}
    return {"estado": "error", "mensaje": "Comando inválido"}

@app.websocket("/ws")
async def endpointWebsocket(websocket: WebSocket):
    await gestor.conectar(websocket)
    try:
        # 1. Enviar estado actual inmediato
        await websocket.send_json({
            "tipo": "estado", 
            "datos": manejadorMqtt.estadoActual
        })

        # 2. Enviar historial de logs
        for log in reversed(manejadorMqtt.historialLogs):
            await websocket.send_json(log)

        while True:
            await websocket.receive_text() # Mantener conexión abierta
    except WebSocketDisconnect:
        gestor.desconectar(websocket)
