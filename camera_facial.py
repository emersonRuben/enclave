import cv2
import face_recognition
import numpy as np
import requests
import time
import os
import logging

# Configurar logger
logger = logging.getLogger(__name__)

# Se debe importar AQUÍ para evitar ciclos, o mejor, importar dentro del método si es estricto.
# Pero dado que systems.py importa mqtt, si mqtt importa systema... 
# mqtt_client NO importa camera_facial. main importa ambos.
# Así que es seguro importar mqtt_client aquí.
from mqtt_client import manejadorMqtt, TOPICO_COMANDO, PREFIJO_TOPICO

TOPICO_FACIAL_STATUS = f"{PREFIJO_TOPICO}/facial_status"

class SistemaFacial:
    def __init__(self):
        # Cargar variables de entorno
        from dotenv import load_dotenv
        load_dotenv()

        self.url_stream = os.getenv("CAMERA_STREAM_URL")
        if not self.url_stream:
             logger.error("CAMERA_STREAM_URL no definido en .env")
             self.url_stream = "" 
        
        self.url_abrir = self.url_stream.replace("/stream", "/abrir") if self.url_stream else ""

        logger.info(f"Configuración Facial: Stream={self.url_stream}")
        
        self.known_face_encodings = []
        self.known_face_names = []
        self.cap = None
        
        self.ultimo_reconocimiento = 0 # Timestamp del último check
        self.ultimo_apertura = 0       # Timestamp de la última apertura enviada
        
        # Variables para feedback visual
        self.last_face_locations = []
        self.last_face_status = None # "AUTHORIZED" | "UNAUTHORIZED"
        self.mostrar_caja_hasta = 0
        
        self.ultimo_frame_bytes = None # Cache para evitar doble request

        # Cargar referencia al iniciar
        self.cargar_referencia()

    def cargar_referencia(self):
        # Reiniciar listas
        self.known_face_encodings = []
        self.known_face_names = []
        
        carpeta = "rostros"
        if not os.path.exists(carpeta):
            os.makedirs(carpeta)
            logger.info(f"Carpeta '{carpeta}' creada.")

        tipos = ('*.jpg', '*.jpeg', '*.png')
        archivos = []
        import glob
        for ext in tipos:
            archivos.extend(glob.glob(os.path.join(carpeta, ext)))
        
        if not archivos:
            logger.warning(f"No hay imágenes en {carpeta}/. El reconocimiento no funcionará.")
            return

        logger.info(f"Cargando {len(archivos)} rostros de referencia...")
        
        for ruta in archivos:
            try:
                nombre = os.path.splitext(os.path.basename(ruta))[0]
                imagen = face_recognition.load_image_file(ruta)
                
                # Redimensionar para velocidad
                h, w = imagen.shape[:2]
                if w > 800 or h > 800: # Permitir un poco más de calidad que antes
                    scale = 800 / max(w, h)
                    imagen = cv2.resize(imagen, (0, 0), fx=scale, fy=scale)
                
                # Buscar cara
                encodings = face_recognition.face_encodings(imagen)
                
                if encodings:
                    self.known_face_encodings.append(encodings[0])
                    self.known_face_names.append(nombre)
                    logger.info(f"Rostro cargado: {nombre}")
                else:
                    logger.warning(f"No se detectó rostro en {nombre}")
                    
            except Exception as e:
                logger.error(f"Error cargando {ruta}: {e}")

    def registrar_usuario(self, nombre, imagen_b64=None):
        """
        Guarda el frame actual como referencia para un nuevo usuario.
        Si imagen_b64 está presente, usa esa imagen (desde webcam laptop).
        """
        datos_imagen = None

        if imagen_b64:
            try:
                # Decodificar Base64 (data:image/jpeg;base64,/9j/...)
                import base64
                if "," in imagen_b64:
                    imagen_b64 = imagen_b64.split(",")[1]
                datos_imagen = base64.b64decode(imagen_b64)
            except Exception as e:
                return {"status": "ERROR", "mensaje": f"Error decodificando imagen: {e}"}
        else:
            # Usar stream ESP32
            if not self.ultimo_frame_bytes:
                return {"status": "ERROR", "mensaje": "No hay video para capturar"}
            datos_imagen = self.ultimo_frame_bytes
        
        # Sanietizar nombre
        nombre_clean = "".join([c for c in nombre if c.isalnum() or c in (' ', '_')]).strip()
        if not nombre_clean:
            return {"status": "ERROR", "mensaje": "Nombre inválido"}

        ruta_destino = os.path.join("rostros", f"{nombre_clean}.jpg")
        
        try:
            with open(ruta_destino, "wb") as f:
                f.write(datos_imagen)
            
            # Recargar referencias para incluir al nuevo
            self.cargar_referencia()
            return {"status": "OK", "mensaje": f"Usuario {nombre_clean} registrado"}
        except Exception as e:
            return {"status": "ERROR", "mensaje": f"Error guardando archivo: {e}"}

    def generar_frames(self):
        """
        Generador robusto que lee el stream HTTP byte a byte (PROXY).
        Evita problemas de OpenCV/FFmpeg con streams remotos.
        """
        while True:
            try:
                if not self.url_stream:
                    yield self._imagen_espera("URL NO DEFINIDA")
                    time.sleep(2)
                    continue

                res = requests.get(self.url_stream, stream=True, timeout=5)

                if res.status_code != 200:
                    yield self._imagen_espera(f"ERROR {res.status_code}")
                    time.sleep(2)
                    continue

                bytes_buffer = b''
                for chunk in res.iter_content(chunk_size=4096):
                    if not chunk: break
                    bytes_buffer += chunk
                    
                    # Buscar inicio (0xFF 0xD8)
                    a = bytes_buffer.find(b'\xff\xd8')
                    if a == -1:
                        # Limpieza si no encontramos inicio tras leer mucho
                        if len(bytes_buffer) > 100000: bytes_buffer = b''
                        continue
                        
                    # Buscar fin (0xFF 0xD9) SIEMPRE DESPUES DEL INICIO
                    b = bytes_buffer.find(b'\xff\xd9', a)
                    
                    if b != -1:
                        jpg = bytes_buffer[a:b+2]
                        
                        # GUARDAR CACHE para uso de verificar_identidad
                        self.ultimo_frame_bytes = jpg
                        
                        # MANTENER SINCRONIZACIÓN:
                        bytes_buffer = bytes_buffer[b+2:]
                        
                        # PREVENIR LAG:
                        if len(bytes_buffer) > 65536: # 64KB safety limit
                            bytes_buffer = b''
                        
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + jpg + b'\r\n')
                else:
                     # Si leemos y leemos y no encontramos fin de frame, quizás estamos desincronizados
                     if len(bytes_buffer) > 100000:
                         bytes_buffer = b''
                         yield self._imagen_espera("RESINCRONIZANDO...")
            
            except requests.exceptions.ReadTimeout:
                logger.warning("Stream pausado (Posiblemente ESP32 ocupado)...")
                yield self._imagen_espera("ESPERANDO... (TIMEOUT)")
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error stream: {e}")
                yield self._imagen_espera("INTENTANDO RECONECTAR...")
                time.sleep(2)
            finally:
                try:
                    res.close()
                except: pass

    def verificar_identidad(self):
        """
        Verifica identidad usando el ÚLTIMO FRAME del stream activo.
        NO abre una nueva conexión para evitar bloquear al ESP32.
        """
        if not self.ultimo_frame_bytes:
             return {"status": "ERROR", "mensaje": "No hay video. Espere..."}

        try:
            jpg_capturado = self.ultimo_frame_bytes

            # 2. Procesar con IA
            frame_bgr = cv2.imdecode(np.frombuffer(jpg_capturado, np.uint8), cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {"status": "ERROR", "mensaje": "Imagen corrupta"}

            # --- MEJORA DE IMAGEN (CLAHE) ---
            # Para corregir imagenes "opacas" o con mala luz
            lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl,a,b))
            frame_enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
            # --------------------------------

            # Reducir y Convertir (Usamos la imagen mejorada)
            small = cv2.resize(frame_enhanced, (0, 0), fx=0.5, fy=0.5) 
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            
            face_locs = face_recognition.face_locations(rgb)
            
            if not face_locs:
                # Intentar una vez mas con la imagen original sin filtro (backup)
                small_raw = cv2.resize(frame_bgr, (0, 0), fx=0.5, fy=0.5)
                rgb_raw = cv2.cvtColor(small_raw, cv2.COLOR_BGR2RGB)
                face_locs = face_recognition.face_locations(rgb_raw)

            if not face_locs:
                 return {"status": "NO_DETECTADO", "mensaje": "No se distingue un rostro claro. Acerquece a la cámara."}

            # Identificar
            face_encs = face_recognition.face_encodings(rgb, face_locs)
            es_propietario = False
            
            for face_encoding in face_encs:
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                if True in matches:
                    es_propietario = True
                    break
            
            if es_propietario:
                logger.info("¡ROSTRO RECONOCIDO EN ESCANEO MANUAL!")
                try:
                    manejadorMqtt.publicar(TOPICO_COMANDO, "ABRIR")
                    manejadorMqtt.publicar(TOPICO_FACIAL_STATUS, "RECONOCIDO")
                except: pass
                return {"status": "RECONOCIDO", "mensaje": "Identidad Verificada. Abriendo..."}
            else:
                try:
                    manejadorMqtt.publicar(TOPICO_FACIAL_STATUS, "DETECTADO")
                except: pass
                return {"status": "NO_AUTORIZADO", "mensaje": "Rostro no autorizado"}

        except Exception as e:
            logger.error(f"Error en verificación manual: {e}")
            return {"status": "ERROR", "mensaje": str(e)}

    def _imagen_espera(self, mensaje):
        # Fondo Gris Azulado para distinguir de "OFF"
        blank = np.full((480, 640, 3), (50, 50, 50), np.uint8) 
        cv2.putText(blank, "SISTEMA DE VIDEO", (180, 200), cv2.FONT_HERSHEY_DUPLEX, 0.8, (200, 200, 200), 1)
        # Centrar texto aprox
        cv2.putText(blank, mensaje, (50, 250), cv2.FONT_HERSHEY_DUPLEX, 0.8, (100, 100, 255), 2)
        ret, buf = cv2.imencode('.jpg', blank)
        return (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

    # Métodos legacy
    def iniciar_escaneo(self, duracion=20): pass
    def detener_escaneo(self, duracion=20): pass

sistema_facial = SistemaFacial()
