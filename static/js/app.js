const inputField = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const messagesContainer = document.getElementById('chat-messages');
const loaderOverlay = document.getElementById('loader-overlay');

// Generate or retrieve session ID
function getSessionId() {
    let sessionId = localStorage.getItem('chat_session_id');
    if (!sessionId) {
        // Simple UUID generation backup if crypto.randomUUID isn't available
        if (crypto.randomUUID) {
            sessionId = crypto.randomUUID();
        } else {
            sessionId = 'session-' + Date.now() + '-' + Math.random().toString(36).substring(2);
        }
        localStorage.setItem('chat_session_id', sessionId);
    }
    return sessionId;
}

function addMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    if (sender === 'bot') {
        // Create icon element
        const iconImg = document.createElement('img');
        iconImg.src = '/static/assets/icon.png';
        iconImg.alt = 'Bot';
        iconImg.classList.add('message-icon');

        // Append icon
        messageDiv.appendChild(iconImg);

        // Create container for formatted text
        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');

        // Use marked.parse to convert Markdown to HTML
        // SECURITY NOTE: In a real app, sanitize this input to prevent XSS. 
        // For this demo with trusted n8n output, direct parsing is okay.
        contentDiv.innerHTML = marked.parse(text);

        messageDiv.appendChild(contentDiv);
    } else {
        messageDiv.textContent = text;
    }

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

async function sendMessage() {
    // Check login/expiration before sending
    if (!checkLogin()) {
        return;
    }

    const text = inputField.value.trim();
    if (!text) return;

    // Display user message
    addMessage(text, 'user');
    inputField.value = '';

    // Show loader
    if (loaderOverlay) {
        loaderOverlay.style.display = 'flex';
    }

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: text,
                session_id: getSessionId(),
                user_context: localStorage.getItem('chat_user_data') ? JSON.parse(localStorage.getItem('chat_user_data')) : null
            })
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        // Display bot response
        addMessage(data.answer, 'bot');

    } catch (error) {
        console.error('Error:', error);
        addMessage('Error al conectar con el servidor.', 'bot');
    } finally {
        if (loaderOverlay) {
            loaderOverlay.style.display = 'none';
        }
    }
}

sendButton.addEventListener('click', sendMessage);

// Login Logic within DOMContentLoaded to share scope or separate?
// Separating out to avoid scope issues, but needs elements.
// Let's attach listeners here since elements are defined above.
const loginModal = document.getElementById('login-modal');
const cedulaInput = document.getElementById('cedula-input');
const noCedulaCheckbox = document.getElementById('no-cedula-checkbox');
const loginButton = document.getElementById('login-button');
const loginError = document.getElementById('login-error');

function updateUserInfo(userData) {
    const panel = document.getElementById('user-info-panel');
    // If guest or no data, hide panel
    if (!userData || !userData.tse_data) {
        panel.style.display = 'none';
        return;
    }

    // Normalize data source
    let data = userData.tse_data.d || userData.tse_data;
    console.log("Processing User Info Data:", data);
    if (data.lista) data = data.lista;

    const cedula = data.cedula || userData.cedula || 'N/A';
    const nombre = data.nombreCompleto || 'Ciudadano';
    const provincia = data.descripcionProvincia || 'N/A';
    const canton = data.descripcionCanton || 'N/A';
    const distrito = data.descripcionDistrito || 'N/A';
    const escuela = data.nombreCentroVotacion || 'N/A';
    const junta = data.junta || 'N/A';

    panel.innerHTML = `
        <div>
        <strong>Tu centro de votación es:</strong><br>
        <strong>Nombre:</strong> ${nombre} <br><strong>Cédula:</strong> ${cedula}</div>
        <div style="margin-top: 4px;">
            <strong>Provincia:</strong> ${provincia} <strong>Cantón:</strong> ${canton} <br><strong>Distrito:</strong> ${distrito}<br>
            <strong>Centro:</strong> ${escuela} - <strong>Junta:</strong> ${junta}
        </div>
    `;
    panel.style.display = 'block';
}

function checkLogin() {
    // ... (existing timeout logic) ...
    const userData = localStorage.getItem('chat_user_data');
    const loginTime = localStorage.getItem('chat_login_time');
    const MAX_SESSION_TIME = 30 * 60 * 1000;

    if (userData && loginTime) {
        if (Date.now() - parseInt(loginTime) > MAX_SESSION_TIME) {
            localStorage.removeItem('chat_user_data');
            localStorage.removeItem('chat_login_time');
            // Reload to clear all memory and reset state cleanly
            location.reload();
            return false;
        }

        loginModal.style.display = 'none';
        // Only update info if NOT a guest
        const parsedData = JSON.parse(userData);
        if (!parsedData.is_guest) {
            updateUserInfo(parsedData);
        } else {
            document.getElementById('user-info-panel').style.display = 'none'; // Ensure hidden for guest
        }
        return true;
    }

    loginModal.style.display = 'flex';
    document.getElementById('user-info-panel').style.display = 'none'; // Hide if no session
    return false;
}

async function handleLogin() {
    const isGuest = noCedulaCheckbox.checked;
    const cedula = cedulaInput.value.trim();

    if (isGuest) {
        // Guest Login
        localStorage.setItem('chat_user_data', JSON.stringify({ is_guest: true }));
        localStorage.setItem('chat_login_time', Date.now().toString());
        loginModal.style.display = 'none';
        document.getElementById('user-info-panel').style.display = 'none'; // Hide panel for guest
        return;
    }

    if (!cedula) {
        loginError.textContent = 'Por favor ingrese su cédula.';
        return;
    }

    const originalBtnText = loginButton.textContent;
    loginButton.textContent = 'Verificando...';
    loginButton.disabled = true;
    loginError.textContent = '';

    try {
        const response = await fetch('/api/validate-cedula', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cedula: cedula })
        });

        if (!response.ok) {
            throw new Error('Error validando cédula');
        }

        const data = await response.json();
        console.log("Datos TSE:", data);

        if (data && (data.d || data.nombre || typeof data === 'object')) {
            localStorage.setItem('chat_user_data', JSON.stringify({
                cedula: cedula,
                tse_data: data
            }));
            localStorage.setItem('chat_login_time', Date.now().toString());
            localStorage.setItem('chat_session_id', '');
            loginModal.style.display = 'none';
            updateUserInfo({ cedula: cedula, tse_data: data });
        } else {
            loginError.textContent = 'Cédula no encontrada.';
        }
    } catch (error) {
        console.error(error);
        loginError.textContent = 'Error de conexión.';
    } finally {
        loginButton.textContent = originalBtnText;
        loginButton.disabled = false;
    }
}

// Initial check
checkLogin();

if (loginButton) loginButton.addEventListener('click', handleLogin);
if (cedulaInput) cedulaInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleLogin();
});

// Toggle input based on checkbox
if (noCedulaCheckbox) {
    noCedulaCheckbox.addEventListener('change', (e) => {
        cedulaInput.disabled = e.target.checked;
        if (e.target.checked) {
            cedulaInput.value = '';
            cedulaInput.placeholder = 'Modo invitado';
            loginError.textContent = '';
        } else {
            cedulaInput.placeholder = 'Ej: 206440798';
        }
    });
}

// Quick Replies Logic
document.querySelectorAll('.quick-reply-btn').forEach(button => {
    button.addEventListener('click', () => {
        const text = button.textContent;
        // Optionally update input, but user said "just click or tap" implies sending.
        // We can simulate sending:
        if (inputField) inputField.value = text;
        sendMessage();
    });
});
