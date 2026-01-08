import requests
import cv2
import os
from dotenv import load_dotenv
import time

load_dotenv()

URL = os.getenv("CAMERA_STREAM_URL")

print(f"Probando conexión a {URL}...")

print("1. TEST DE RED (REQUESTS)...")
try:
    start_t = time.time()
    r = requests.get(URL, stream=True, timeout=15)
    elapsed = time.time() - start_t
    print(f"   [TIEMPO] Respuesta en {elapsed:.2f} segundos")
    if r.status_code == 200:
        print("   [EXITO] Python puede ver la cámara (Status 200).")
    else:
        print(f"   [FALLO] Código de estado: {r.status_code}")
except Exception as e:
    print(f"   [FALLO] No se pudo conectar: {e}")

print("\n2. TEST DE OPENCV...")
cap = cv2.VideoCapture(URL)
if cap.isOpened():
    print("   [EXITO] OpenCV abrió el stream.")
    ret, frame = cap.read()
    if ret:
        print(f"   [EXITO] Se leyó un cuadro de video: {frame.shape}")
    else:
        print("   [FALLO] OpenCV abrió pero no lee cuadros.")
else:
    print("   [FALLO] OpenCV no pudo abrir el stream.")

cap.release()
print("\nPrueba terminada.")
