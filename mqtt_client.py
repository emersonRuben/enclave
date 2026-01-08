import paho.mqtt.client as mqtt
import logging
import asyncio
import ssl
import certifi
import json
import random
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
        # Generar ID aleatorio para evitar conflictos de "Session taken over" al reiniciar
        client_id = f"FastAPI_Server_{random.randint(1000, 9999)}"
        self.cliente = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv5)
        
        # Configurar TLS con certificados de Certifi
        self.cliente.tls_set(ca_certs=certifi.where())
        
        # Configuración de Autenticación
        self.cliente.username_pw_set(USUARIO, CONTRASEÑA)

        self.cliente.on_connect = self.alConectar
        self.cliente.on_message = self.alRecibirMensaje
        self.cliente.on_disconnect = self.alDesconectar
        
        # Callbacks para enviar datos a FastAPI (Soporte Multi-Cliente)
        self.clientes_conectados = set()
        
        # Modo Simulación (Desactivado si hay dispositivo real)
        self.modoSimulacion = False 
        
        # Persistencia de Estado
        self.archivoEstado = "state.txt"
        # self.estadoActual = self._cargarEstado() # Desactivado: Siempre iniciar CERRADO por seguridad
        self.estadoActual = "CERRADO"
        self._guardarEstado() # Actualizar archivo para reflejar el inicio cerrado
        
        self.historialLogs = []
        self.loop = None

    def _cargarEstado(self):
        try:
            if os.path.exists(self.archivoEstado):
                with open(self.archivoEstado, 'r') as f:
                    estado = f.read().strip()
                    # print(f"DEBUG: Estado recuperado: {estado}")
                    return estado
        except Exception as e:
            print(f"Error cargando estado: {e}")
        return "CERRADO"

    def _guardarEstado(self):
        try:
            with open(self.archivoEstado, 'w') as f:
                f.write(self.estadoActual)
        except Exception as e:
            print(f"Error guardando estado: {e}")

    def registrar_cliente(self, callback):
        self.clientes_conectados.add(callback)

    def deregistrar_cliente(self, callback):
        self.clientes_conectados.discard(callback)

    def _agregarHistorial(self, tipo, mensaje):
        """Guarda los últimos 50 eventos en memoria RAM."""
        evento = {"tipo": tipo, "datos": mensaje}
        self.historialLogs.insert(0, evento)
        if len(self.historialLogs) > 50:
            self.historialLogs.pop()

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
            print(f"MENSAJE RECIBIDO [{topico}]: {payload}") 

            # Manejar Lógica de Simulación
            if self.modoSimulacion and topico == TOPICO_COMANDO:
                self._manejarComandoSimulado(payload)

            # Identificar tipo de mensaje
            tipoMensaje = "desconocido"
            if topico == TOPICO_ESTADO:
                tipoMensaje = "estado"
                # Normalización: Manejar ABIERTA/ABIERTO
                estado_normalizado = payload.upper()
                
                # Detectar cambio de estado
                nuevo_estado = "CERRADO"
                if "ABIER" in estado_normalizado:
                     nuevo_estado = "ABIERTO"
                
                # Regla de Log: Si cambia el estado O si es un mensaje en vivo (retain=0)
                # msg.retain suele ser 0 en mensajes nuevos y 1 en históricos
                deberia_loguear = (nuevo_estado != self.estadoActual) or (msg.retain == 0)

                self.estadoActual = nuevo_estado
                self._guardarEstado() # Guardar siempre para asegurar consistencia
                
                if deberia_loguear:
                     mensaje_log = f"Estado cambiado a: {self.estadoActual}"
                     self._agregarHistorial("log", mensaje_log)
                     
                     # Enviar 'log' a todos los clientes
                     self._notificar_clientes("log", mensaje_log)
                
                payload = self.estadoActual 

            elif topico == TOPICO_ALERTA:
                tipoMensaje = "alerta"
                self._agregarHistorial("alerta", payload)
            elif topico == TOPICO_LOG:
                tipoMensaje = "log"
                self._agregarHistorial("log", payload)
            elif "facial_status" in topico:
                tipoMensaje = "facial_status"
                # No guardamos historial para esto, es transitorio
            
            # Enviar el mensaje original (tipo 'estado', 'alerta', etc.) a todos
            if tipoMensaje != "desconocido":
                 self._notificar_clientes(tipoMensaje, payload)

        except Exception as e:
            logging.error(f"Error procesando mensaje: {e}")

    def _notificar_clientes(self, tipo, datos):
        if self.loop and self.clientes_conectados:
            for callback in list(self.clientes_conectados):
                asyncio.run_coroutine_threadsafe(callback(tipo, datos), self.loop)

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
