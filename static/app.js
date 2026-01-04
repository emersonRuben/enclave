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

function agregarItemLog(elementoLista, texto, tipo) {
    const li = document.createElement('li');
    li.className = `log-item ${tipo}`;

    const tiempo = new Date().toLocaleTimeString();

    li.innerHTML = `
        <span class="log-text">${texto}</span>
        <span class="log-time">${tiempo}</span>
    `;

    elementoLista.insertBefore(li, elementoLista.firstChild);

    // Mantener lista manejable
    if (elementoLista.children.length > 50) {
        elementoLista.removeChild(elementoLista.lastChild);
    }
}

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

// Inicializar
document.addEventListener('DOMContentLoaded', () => {
    conectarWebSocket();
});
