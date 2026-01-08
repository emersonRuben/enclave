import cv2
import requests
import face_recognition
import numpy as np
import time

import os
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
CAMERA_STREAM_URL = os.getenv("CAMERA_STREAM_URL")

if not CAMERA_STREAM_URL:
    print("ERROR: CAMERA_STREAM_URL no está definido en el archivo .env")
    exit()

URL_VIDEO = CAMERA_STREAM_URL
# Asumimos que la URL del stream termina en /stream y la del servo es /abrir
# Si la URL es la raíz, ajustamos según sea necesario.
# Estrategia: Reemplazar '/stream' por '/abrir' directo.
URL_ABRIR = CAMERA_STREAM_URL.replace("/stream", "/abrir")

print(f"Configuración cargada:")
print(f" - Stream: {URL_VIDEO}")
print(f" - Abrir:  {URL_ABRIR}")

# --- CARGAR FOTO (VERSIÓN ROBUSTA) ---
print("Cargando referencia facial...")
mi_imagen = face_recognition.load_image_file("yo.jpg")

# 1. Redimensionar si es muy grande (evita crash)
h, w = mi_imagen.shape[:2]
if w > 600 or h > 600:
    print(f"La imagen es muy grande ({w}x{h}). Redimensionando a 600px...")
    scale = 600 / max(w, h)
    mi_imagen = cv2.resize(mi_imagen, (0, 0), fx=scale, fy=scale)

# 2. Buscar cara en 4 rotaciones (evita error de foto movida)
print("Buscando cara en diferentes rotaciones...")
encodings = []
for i in range(4):
    try:
        encodings = face_recognition.face_encodings(mi_imagen)
    except Exception:
        pass
    
    if encodings:
        print(f"¡Cara encontrada tras rotar {i * 90} grados!")
        break
    
    mi_imagen = np.rot90(mi_imagen)
    mi_imagen = np.ascontiguousarray(mi_imagen) # Fix memoria para C++

if not encodings:
    print("ERROR: No se detectó ninguna cara en 'yo.jpg' (ni rotándola).")
    print("Usa una foto más clara y de frente.")
    exit()

mi_encoding = encodings[0]

known_face_encodings = [mi_encoding]
known_face_names = ["PROPIETARIO"]

print(f"Probando conexión a {URL_VIDEO}...")
try:
    # Test rápido de conexión antes de usar OpenCV (para no esperar 30s)
    # Aumentamos a 10s porque a veces el ESP32 tarda en empezar a mandar datos
    requests.get(URL_VIDEO, stream=True, timeout=10)
    print("Conexión exitosa. Iniciando captura de video...")
except Exception as e:
    print(f"ERROR: No se pudo conectar a {URL_VIDEO}")
    print("Verifica que el ESP32 esté encendido y en la misma red.")
    print(f"Detalle: {e}")
    exit()

cap = cv2.VideoCapture(URL_VIDEO)
# Buffer pequeño para reducir lag (solo 1 frame en cola)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

ultimo_intento = 0

while True:
    ret, frame = cap.read()
    
    # Si falla el video, intentamos reconectar
    if not ret:
        print("Perdida de señal. Reintentando...")
        time.sleep(2)
        try:
             # Verificar si sigue viva la conexión
             requests.get(URL_VIDEO, stream=True, timeout=2)
             cap = cv2.VideoCapture(URL_VIDEO)
             cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except:
             pass
        continue

    # Reducimos imagen para que el reconocimiento sea RAPIDÍSIMO
    # Usamos 0.25 (1/4 del tamaño original)
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Buscamos caras
    face_locations = face_recognition.face_locations(rgb_small_frame)
    if face_locations: # Solo si hay caras procesamos lo demás
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for face_encoding, face_location in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Desconocido"
            color = (0, 0, 255)

            if True in matches:
                name = "ABRIENDO..."
                color = (0, 255, 0)
                
                # --- LA SOLUCIÓN AL BLOQUEO ---
                if time.time() - ultimo_intento > 8:
                    print("¡Rostro reconocido! Enviando orden...")
                    
                    # 1. SOLTAMOS LA CÁMARA para liberar al ESP32
                    cap.release() 
                    
                    try:
                        # 2. Enviamos la orden (ahora el ESP32 sí escuchará)
                        requests.get(URL_ABRIR, timeout=2)
                        print(">> ORDEN ENVIADA CON ÉXITO <<")
                    except Exception as e:
                        print(f"Error enviando orden: {e}")
                    
                    # 3. Guardamos tiempo y RECONECTAMOS el video
                    ultimo_intento = time.time()
                    cap = cv2.VideoCapture(URL_VIDEO) 
                    # Saltamos al siguiente ciclo para que cargue la cámara
                    continue 

            # Dibujar recuadro (Visualización)
            top, right, bottom, left = face_location
            top *= 4; right *= 4; bottom *= 4; left *= 4
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            cv2.putText(frame, name, (left, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)

    # Mostrar video
    cv2.imshow('Caja Fuerte AI', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()