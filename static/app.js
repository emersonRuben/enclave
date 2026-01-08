// Estado de Conexión
const indicadorEstado = document.getElementById('connection-status');
const textoEstado = indicadorEstado.querySelector('.text');
const puntoEstado = indicadorEstado.querySelector('.dot'); // Selector del punto

// Elementos
const visualizadorCandado = document.getElementById('lock-display');
const iconoCandado = document.getElementById('lock-icon');
const tituloEstado = document.getElementById('status-text');
const panelEstado = document.querySelector('.status-indicator'); // Selector modificado
const listaAlertas = document.getElementById('alerts-list');
const listaLogs = document.getElementById('logs-list');

// WebSocket
function conectarWebSocket() {
    const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocolo}://${window.location.host}/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        indicadorEstado.classList.add('connected');
        textoEstado.textContent = 'Conectado';
        if (puntoEstado) puntoEstado.style.backgroundColor = 'var(--success)';
        console.log('WebSocket conectado');
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.tipo === 'estado') {
            actualizarEstado(data.datos);
        } else if (data.tipo === 'log') {
            agregarItemLog(listaLogs, data.datos, 'log');
        } else if (data.tipo === 'alerta') {
            agregarItemLog(listaAlertas, data.datos, 'alert');
        } else if (data.tipo === 'facial_status') {
            actualizarEstadoFacial(data.datos);
        }
    };

    socket.onclose = () => {
        indicadorEstado.classList.remove('connected');
        textoEstado.textContent = 'Desconectado';
        if (puntoEstado) puntoEstado.style.backgroundColor = 'var(--danger)';
        setTimeout(conectarWebSocket, 3000);
    };

    socket.onerror = (error) => {
        console.error('Error WebSocket:', error);
    };
}

let estadoActual = 'CERRADO'; // Variable global para estado

function actualizarEstado(estado) {
    estado = estado.toUpperCase();
    estadoActual = estado; // Actualizar estado global

    // Usar el contenedor o elemento específico que style.css apunta con [data-status]
    panelEstado.setAttribute('data-status', estado);

    // Lógica del Icono
    const iconoCandado = document.getElementById('lock-icon');
    const btnOpen = document.querySelector('.btn-action.open');
    const btnClose = document.querySelector('.btn-action.close');

    console.log('Actualizando estado a:', estado); // Depuración

    // Eliminar clases previas
    iconoCandado.classList.remove('fa-lock', 'fa-lock-open', 'fa-shake');

    if (estado === 'ABIERTO') {
        tituloEstado.textContent = 'ABIERTO';
        iconoCandado.classList.add('fa-solid', 'fa-lock-open');

        // Sincronizar widget de reconocimiento facial
        actualizarEstadoFacial('RECONOCIDO');

        // Deshabilitar botón Abrir (ya está abierto)
        if (btnOpen) {
            btnOpen.disabled = true;
            btnOpen.classList.add('disabled');
        }
        if (btnClose) {
            btnClose.disabled = false;
            btnClose.classList.remove('disabled');
        }

    } else {
        tituloEstado.textContent = 'CERRADO';
        iconoCandado.classList.add('fa-solid', 'fa-lock');

        // Habilitar botón Abrir
        if (btnOpen) {
            btnOpen.disabled = false;
            btnOpen.classList.remove('disabled');
        }
        if (btnClose) {
            btnClose.disabled = true; // Opcional: deshabilitar cerrar si ya está cerrado
            btnClose.classList.add('disabled');
        }
    }
}

const MAX_LOGS = 10;

function cargarLogsGuardados() {
    // Cargar Logs Comunes
    const logsGuardados = JSON.parse(localStorage.getItem('logs_historial') || '[]');
    logsGuardados.forEach(log => {
        itemHTML(listaLogs, log.texto, log.tipo, log.tiempo);
    });

    // Cargar Alertas
    const alertasGuardadas = JSON.parse(localStorage.getItem('alertas_historial') || '[]');
    alertasGuardadas.forEach(alerta => {
        itemHTML(listaAlertas, alerta.texto, alerta.tipo, alerta.tiempo);
    });
}

// Función auxiliar para renderizar sin guardar (evitar bucle infinito)
function itemHTML(elementoLista, texto, tipo, tiempo) {
    const li = document.createElement('li');
    li.className = `log-item ${tipo}`;
    li.innerHTML = `
        <span class="log-text">${texto}</span>
        <span class="log-time">${tiempo}</span>
    `;
    elementoLista.insertBefore(li, elementoLista.firstChild);
}

function agregarItemLog(elementoLista, texto, tipo) {
    const tiempo = new Date().toLocaleTimeString();

    // 1. Renderizar en HTML
    itemHTML(elementoLista, texto, tipo, tiempo);

    // 2. Guardar en LocalStorage
    // Identificar si es Alerta o Log normal para usar la key correcta
    let key = 'logs_historial';
    if (elementoLista === listaAlertas) key = 'alertas_historial';

    const historial = JSON.parse(localStorage.getItem(key) || '[]');
    historial.unshift({ texto, tipo, tiempo }); // Agregar al inicio

    if (historial.length > MAX_LOGS) {
        historial.pop();
    }

    localStorage.setItem(key, JSON.stringify(historial));

    // Mantener lista manejable en DOM
    if (elementoLista.children.length > MAX_LOGS) {
        elementoLista.removeChild(elementoLista.lastChild);
    }
}

// Iniciar cargando logs viejos
document.addEventListener('DOMContentLoaded', () => {
    cargarLogsGuardados();
    conectarWebSocket();
});

// Funciones Modal PIN
function abrirModalPin() {
    if (estadoActual === 'ABIERTO') return; // Bloquear si ya está abierto

    const modal = document.getElementById('pin-modal');
    const input = document.getElementById('security-pin');
    modal.classList.add('active');
    // Error reset
    document.getElementById('pin-error').textContent = '';
    // Focus input after animation
    setTimeout(() => {
        input.value = '';
        input.focus();
    }, 100);
}

function cerrarModalPin() {
    const modal = document.getElementById('pin-modal');
    modal.classList.remove('active');
}

function verificarPin() {
    const input = document.getElementById('security-pin');
    const errorMsg = document.getElementById('pin-error');
    const pin = input.value;

    // PIN hardcodeado para demostración: 1234
    // En producción esto debería validarse en backend o ser configurable
    if (pin === '1234') {
        cerrarModalPin();
        enviarComando('ABRIR');
    } else {
        errorMsg.textContent = 'PIN Incorrecto';
        input.classList.add('error');
        setTimeout(() => input.classList.remove('error'), 500);
        input.value = '';
        input.focus();
    }
}

// Permitir Enter en el input del PIN
document.getElementById('security-pin')?.addEventListener('keyup', function (event) {
    if (event.key === 'Enter') {
        verificarPin();
    }
});

// Comandos
async function enviarComando(accion) {
    try {
        // Actualización Optimista: Actualizar UI inmediatamente
        const nuevoEstado = (accion === 'ABRIR') ? 'ABIERTO' : 'CERRADO';
        actualizarEstado(nuevoEstado);

        // Opcional: Deshabilitar botones brevemente o mostrar carga
        const btnOpen = document.querySelector('.btn-action.open');
        const btnClose = document.querySelector('.btn-action.close');
        /* btnOpen.disabled = true; btnClose.disabled = true; */

        const respuesta = await fetch(`/api/comando/${accion}`, {
            method: 'POST'
        });
        const resultado = await respuesta.json();

        if (resultado.estado === 'exito') {
            console.log(`Comando ${accion} enviado`);
            // Los logs se actualizarán por WebSocket/MQTT después
        } else {
            // Revertir si hay error
            alert('Error enviando comando');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error de conexión con el backend');
    }
}

// --- RECONOCIMIENTO FACIAL MANUAL ---
const modalFacial = document.getElementById('facial-modal');
const loader = document.getElementById('scan-loader');
const feedbackSuccess = document.getElementById('scan-success');
const feedbackError = document.getElementById('scan-error');

document.getElementById('btn-scan')?.addEventListener('click', verificarRostro);
// --- MANEJO DE VISTAS (SPA) ---
function switchView(viewId) {
    // 1. Ocultar todas las vistas
    const views = ['view-dashboard', 'view-registration'];
    views.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.style.display = 'none';
            el.classList.remove('active');
        }
    });

    // 2. Desactivar todos los links
    const navLinks = ['nav-dashboard', 'nav-registration', 'nav-config'];
    navLinks.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
    });

    // 3. Mostrar nueva vista
    const target = document.getElementById(`view-${viewId}`);
    if (target) {
        target.style.display = 'block';
        setTimeout(() => target.classList.add('active'), 10);
    }

    // 4. Activar nuevo link
    const navTarget = document.getElementById(`nav-${viewId}`);
    if (navTarget) navTarget.classList.add('active');

    // 3. Detener webcam si salimos de registro
    if (viewId !== 'registration') {
        detenerWebcam();
    }
}

// --- WEBCAM LAPTOP ---
let mediaStream = null;

async function iniciarWebcam() {
    const video = document.getElementById('webcam-preview');
    const statusMsg = document.getElementById('reg-status');
    statusMsg.textContent = "Solicitando acceso a cámara...";

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = mediaStream;
        statusMsg.textContent = "Cámara activa. Encuadre su rostro.";
        statusMsg.style.color = "lime";
        video.style.transform = "scaleX(-1)";
    } catch (err) {
        console.error("Error acceso camara:", err);
        statusMsg.textContent = "Error: No se pudo acceder a la cámara.";
        statusMsg.style.color = "red";
    }
}

function detenerWebcam() {
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
}

async function capturarYRegistrar() {
    const nombreInput = document.getElementById('reg-name');
    const statusMsg = document.getElementById('reg-status');
    const nombre = nombreInput.value.trim();

    if (!nombre) {
        statusMsg.textContent = "Ingrese un nombre válido.";
        statusMsg.style.color = "orange";
        nombreInput.focus();
        return;
    }

    if (!mediaStream) {
        statusMsg.textContent = "Primero active la cámara.";
        statusMsg.style.color = "orange";
        return;
    }

    // 1. Capturar Frame
    const video = document.getElementById('webcam-preview');
    const canvas = document.getElementById('webcam-canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const imagenBase64 = canvas.toDataURL('image/jpeg', 0.8);

    statusMsg.textContent = "Enviando...";
    statusMsg.style.color = "cyan";

    try {
        // 2. Enviar al Backend
        const respuesta = await fetch('/api/register-face', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nombre, imagen: imagenBase64 })
        });
        const resultado = await respuesta.json();

        if (resultado.status === 'OK') {
            statusMsg.textContent = `¡Usuario ${nombre} REGISTRADO!`;
            statusMsg.style.color = "lime";
            nombreInput.value = "";

            const camContainer = document.querySelector('.camera-container');
            camContainer.style.border = "2px solid lime";
            setTimeout(() => {
                camContainer.style.border = "none";
                detenerWebcam();
                switchView('dashboard');
                statusMsg.textContent = "";
            }, 1500);

        } else {
            statusMsg.textContent = `Error: ${resultado.mensaje}`;
            statusMsg.style.color = "red";
        }
    } catch (error) {
        console.error(error);
        statusMsg.textContent = "Error de conexión.";
        statusMsg.style.color = "red";
    }
}

/* 
Legacy code removed:
document.getElementById('btn-register')?.addEventListener('click', registrarRostro);
*/
async function registrarRostro_Legacy() { // Renamed to avoid usage
    const nombre = prompt("Ingrese el nombre para el nuevo usuario:");
    if (!nombre) return;

    // 1. Mostrar Modal y Loader
    modalFacial.classList.add('active');
    loader.classList.remove('hidden');
    feedbackSuccess.classList.add('hidden');
    feedbackError.classList.add('hidden');

    // Texto temporal loader
    const subtitulo = loader.querySelector('p');
    if (subtitulo) subtitulo.textContent = "Registrando...";

    try {
        // 2. Llamar API Backend
        const respuesta = await fetch('/api/register-face', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nombre: nombre })
        });
        const resultado = await respuesta.json();

        // Ocultar loader
        loader.classList.add('hidden');
        if (subtitulo) subtitulo.textContent = "Escaneando..."; // Reset

        if (resultado.status === 'OK') {
            // ÉXITO
            feedbackSuccess.classList.remove('hidden');
            const h3 = feedbackSuccess.querySelector('h3');
            const p = feedbackSuccess.querySelector('p');
            h3.textContent = "REGISTRO COMPLETADO";
            p.textContent = resultado.mensaje;

            setTimeout(() => {
                modalFacial.classList.remove('active');
            }, 2000);
        } else {
            // ERROR
            feedbackError.classList.remove('hidden');
            const titulo = feedbackError.querySelector('h3');
            const desc = feedbackError.querySelector('p');
            titulo.textContent = 'ERROR DE REGISTRO';
            desc.textContent = resultado.mensaje;

            setTimeout(() => {
                modalFacial.classList.remove('active');
            }, 3000);
        }

    } catch (error) {
        console.error('Error register:', error);
        loader.classList.add('hidden');
        feedbackError.classList.remove('hidden');
        setTimeout(() => modalFacial.classList.remove('active'), 3000);
    }
}

async function verificarRostro() {
    // 1. Mostrar Modal y Loader
    modalFacial.classList.add('active');
    loader.classList.remove('hidden');
    feedbackSuccess.classList.add('hidden');
    feedbackError.classList.add('hidden');

    try {
        // 2. Llamar API Backend
        const respuesta = await fetch('/api/scan-face', { method: 'POST' });
        const resultado = await respuesta.json();

        // Ocultar loader
        loader.classList.add('hidden');

        if (resultado.status === 'RECONOCIDO') {
            // ÉXITO
            feedbackSuccess.classList.remove('hidden');
            // Cerrar automáticamente tras 2s
            setTimeout(() => {
                modalFacial.classList.remove('active');
                actualizarEstado('ABIERTO'); // Optimista
            }, 2000);
        } else {
            // FALLO (No autorizado o error)
            feedbackError.classList.remove('hidden');
            const titulo = feedbackError.querySelector('h3');
            const desc = feedbackError.querySelector('p');

            if (resultado.status === 'NO_AUTORIZADO') {
                titulo.textContent = 'ACCESO DENEGADO';
            } else if (resultado.status === 'NO_DETECTADO') {
                titulo.textContent = 'ROSTRO NO DETECTADO';
            } else {
                titulo.textContent = 'ERROR DE LECTURA';
            }
            desc.textContent = resultado.mensaje || 'Intente nuevamente';

            // Cerrar tras 3s
            setTimeout(() => {
                modalFacial.classList.remove('active');
            }, 3000);
        }
    } catch (error) {
        console.error('Error scan:', error);
        loader.classList.add('hidden');
        feedbackError.classList.remove('hidden');
        setTimeout(() => modalFacial.classList.remove('active'), 3000);
    }
}

// Permitir cerrar modal con click afuera
modalFacial?.addEventListener('click', (e) => {
    if (e.target === modalFacial) {
        modalFacial.classList.remove('active');
    }
});
// Actualizar Estado Facial
function actualizarEstadoFacial(estado) {
    const display = document.getElementById('facial-status-display');
    const icon = document.getElementById('facial-icon');
    const title = document.getElementById('facial-title');
    const desc = document.getElementById('facial-desc');

    if (!display) return;

    display.setAttribute('data-state', estado);

    // Reset animations
    display.classList.remove('pulse-red', 'pulse-green');

    if (estado === 'RECONOCIDO') {
        icon.className = 'fa-solid fa-user-check';
        title.textContent = 'ACCESO AUTORIZADO';
        desc.textContent = 'Identidad Confirmada';
        display.classList.add('pulse-green');
    } else if (estado === 'DETECTADO') {
        icon.className = 'fa-solid fa-user-lock';
        title.textContent = 'ROSTRO DETECTADO';
        desc.textContent = 'Analizando biometría...';
    } else { // NO_DETECTADO
        icon.className = 'fa-solid fa-user-slash';
        title.textContent = 'VIGILANCIA ACTIVA';
        desc.textContent = 'Sin presencia detectada';
        display.classList.add('pulse-red');
    }
}

