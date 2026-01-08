@echo off
TITLE ENCLAVE - Servidor IoT
COLOR 0A
echo ===================================================
echo    INICIANDO SISTEMA ENCLAVE (MODO PRODUCCION)
echo ===================================================
echo.
echo [1/3] Activando entorno virtual...
call venv\Scripts\activate.bat

echo [2/3] Iniciando servidor en 0.0.0.0:8000...
echo.
echo  - Acceso Local: http://127.0.0.1:8000
echo  - Acceso Red:   http://[TU_IP]:8000
echo.
echo Presiona CTRL+C para detener el servidor.
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
