import paho.mqtt.client as mqtt
import logging
import asyncio
import ssl
import certifi
import json
from typing import Callable, Optional

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración - Credenciales seguras vía variables de entorno
BROKER = os.getenv("HIVEMQ_BROKER", "766bf786657c44d4b1b9079c887442da.s1.eu.hivemq.cloud") 
PUERTO = int(os.getenv("HIVEMQ_PORT", 8883))
USUARIO = os.getenv("HIVEMQ_USERNAME", "ruben")
CONTRASEÑA = os.getenv("HIVEMQ_PASSWORD", "YCCKRD1v$bw4")
PREFIJO_TOPICO = "enclave/caja"

# Tópicos
TOPICO_COMANDO = f"{PREFIJO_TOPICO}/comando"
TOPICO_ESTADO = f"{PREFIJO_TOPICO}/estado"
TOPICO_ALERTA = f"{PREFIJO_TOPICO}/alerta"
TOPICO_LOG = f"{PREFIJO_TOPICO}/log"

class ClienteMqtt:
    def __init__(self):
        # En paho-mqtt 2.0+ callback_api_version por defecto es CallbackAPIVersion.VERSION2
        # Usamos protocolo MQTTv5 o v311. Para simpleza usamos v5 o default.
        self.cliente = mqtt.Client(client_id="FastAPI_Server", protocol=mqtt.MQTTv5)
        
        # Configurar TLS con certificados de Certifi
        self.cliente.tls_set(ca_certs=certifi.where())
        
        # Configuración de Autenticación
        self.cliente.username_pw_set(USUARIO, CONTRASEÑA)

        self.cliente.on_connect = self.alConectar
        self.cliente.on_message = self.alRecibirMensaje
        self.cliente.on_disconnect = self.alDesconectar
        
        # Callback para enviar datos a FastAPI
        self.callbackWebsocket: Optional[Callable[[str, dict], None]] = None
        
        # Modo Simulación (Desactivado si hay dispositivo real)
        self.modoSimulacion = False 
        self.estadoActual = "CERRADO"
        
        # Persistencia de Logs
        self.archivoLogs = "logs.json"
        self.historialLogs = self._cargarLogs()
        self.loop = None

    def _cargarLogs(self):
        try:
            if os.path.exists(self.archivoLogs):
                with open(self.archivoLogs, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error cargando logs: {e}")
        return []

    def _guardarLogs(self):
        try:
            with open(self.archivoLogs, 'w') as f:
                json.dump(self.historialLogs, f)
        except Exception as e:
            print(f"Error guardando logs: {e}")

    def establecerCallback(self, funcionCallback):
        self.callbackWebsocket = funcionCallback

    def _agregarHistorial(self, tipo, mensaje):
        """Guarda los últimos 50 eventos en memoria y archivo."""
        evento = {"tipo": tipo, "datos": mensaje}
        self.historialLogs.insert(0, evento)
        # Limitar a 50
        if len(self.historialLogs) > 50:
            self.historialLogs.pop()
        
        # Guardar en disco
        self._guardarLogs()

    def alConectar(self, cliente, userdata, flags, rc, properties=None):
        if rc == 0:
            logging.info("Conectado exitosamente al Cluster HiveMQ Cloud (RC: Success)")
            # Suscribirse a Tópicos
            cliente.subscribe(f"{PREFIJO_TOPICO}/#")
            logging.info(f"Suscrito a {PREFIJO_TOPICO}/# para simulación")
        else:
            logging.error(f"Fallo en conexión RC: {rc}")

    def alDesconectar(self, cliente, userdata, rc, properties=None):
        logging.warning(f"Desconectado del Broker MQTT (RC: {rc})")

    def alRecibirMensaje(self, cliente, userdata, msg):
        try:
            payload = msg.payload.decode()
            topico = msg.topic
            print(f"MENSAJE RECIBIDO [{topico}]: {payload}") # Requisito: Mostrar por consola

            # Manejar Lógica de Simulación
            if self.modoSimulacion and topico == TOPICO_COMANDO:
                self._manejarComandoSimulado(payload)
                # Continuamos para notificar vía callback si fuera necesario, 
                # aunque el simulador ya publica los cambios de estado.

            # Identificar tipo de mensaje
            tipoMensaje = "desconocido"
            if topico == TOPICO_ESTADO:
                tipoMensaje = "estado"
                # Normalización: Manejar ABIERTA/ABIERTO
                estado_normalizado = payload.upper()
                if "ABIER" in estado_normalizado:
                     self.estadoActual = "ABIERTO"
                else:
                     self.estadoActual = "CERRADO"
                
                # Usar el estado normalizado para el payload que va al WebSocket
                payload = self.estadoActual 
            elif topico == TOPICO_ALERTA:
                tipoMensaje = "alerta"
                self._agregarHistorial("alerta", payload)
            elif topico == TOPICO_LOG:
                tipoMensaje = "log"
                self._agregarHistorial("log", payload)
            
            # Pasar datos al callback (WebSockets)
            if self.callbackWebsocket and tipoMensaje != "desconocido":
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.callbackWebsocket(tipoMensaje, payload),
                        self.loop
                    )

        except Exception as e:
            logging.error(f"Error procesando mensaje: {e}")

    def _manejarComandoSimulado(self, comando):
        """Simula el comportamiento de la caja física."""
        comando = comando.upper()
        if comando == "ABRIR":
            self.estadoActual = "ABIERTO"
            self.publicar(TOPICO_ESTADO, "ABIERTO", retain=True)
            self.publicar(TOPICO_LOG, "Apertura remota ejecutada")
        elif comando == "CERRAR":
            self.estadoActual = "CERRADO"
            self.publicar(TOPICO_ESTADO, "CERRADO", retain=True)
            self.publicar(TOPICO_LOG, "Cierre remoto ejecutado")
        else:
            self.publicar(TOPICO_ALERTA, f"Intento de comando no autorizado: {comando}")

    def iniciar(self, loop):
        self.loop = loop
        try:
            logging.info(f"Conectando a {BROKER}:{PUERTO}...")
            self.cliente.connect(BROKER, PUERTO, 60)
            self.cliente.loop_start()
        except Exception as e:
            logging.error(f"Excepción crítica al conectar MQTT: {e}")

    def detener(self):
        self.cliente.loop_stop()
        self.cliente.disconnect()

    def publicar(self, topico, mensaje, retain=False):
        self.cliente.publish(topico, mensaje, retain=retain)

manejadorMqtt = ClienteMqtt()
