/* ==========================================================================
   GENNIUS SALES PORTAL - AUTENTICACIÓN Y GESTIÓN DE USUARIOS
   Arquitectura Modular: Manejo de Sesiones 7D, 2FA, Perfil y OTP
   ========================================================================== */

// --- VARIABLES GLOBALES DE ESTADO ---
let destinatariosFinalesChips = [];
let destinatariosBccChips = [];
let editFinalesChips = [];
let editBccChips = [];
let pasoActualEmail = 1;
let pasoActualPass = 1;
let avatarSeleccionadoTemp = "";

// --- INICIALIZADOR DE EVENTOS DOM ---
document.addEventListener('DOMContentLoaded', () => {
  inicializarChips();
  setupOTPInputs();
  comprobarSesionGuardada();
  setupLiveValidation();
  setupChipsListeners();

  document.querySelectorAll('input, form').forEach(el => {
    el.setAttribute('autocomplete', 'one-time-code'); // Engaña al autocompletado del navegador
    el.setAttribute('autocorrect', 'off');
    el.setAttribute('spellcheck', 'false');
  });
});

/* ==========================================================================
   1. GESTIÓN DE SESIÓN Y ACCESO RÁPIDO (7 DÍAS)
   ========================================================================== */

/**
 * Comprueba si existe una sesión válida iniciada en los últimos 7 días.
 * Muestra la tarjeta estilo Facebook/Instagram (#card-prelogged) o el Login tradicional.
 */
function comprobarSesionGuardada() {
  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email');
  const now = new Date().getTime();

  if (userEmail && session.last_2fa) {
    const diasTranscurridos = (now - session.last_2fa) / (1000 * 60 * 60 * 24);

    if (diasTranscurridos < 7) {
      const cardLogin = document.getElementById('card-login');
      const cardPrelogged = document.getElementById('card-prelogged');
      const card2fa = document.getElementById('card-2fa');
      const cardReset = document.getElementById('card-reset-pwd');

      if (cardLogin) cardLogin.style.display = 'none';
      if (card2fa) card2fa.style.display = 'none';
      if (cardReset) cardReset.style.display = 'none';
      if (cardPrelogged) cardPrelogged.style.display = 'flex';

      const preloggedName = document.getElementById('prelogged-name');
      const preloggedEmail = document.getElementById('prelogged-email');
      const preloggedDate = document.getElementById('prelogged-date');
      const preloggedAvatar = document.getElementById('prelogged-avatar');

      const fechaAcceso = new Date(session.last_2fa).toLocaleString('es-CO', {
        dateStyle: 'short',
        timeStyle: 'short'
      });

      if (preloggedName) preloggedName.innerText = session.nombre || userEmail;
      if (preloggedEmail) preloggedEmail.innerText = userEmail;
      if (preloggedDate) preloggedDate.innerText = `Último acceso: ${fechaAcceso}`;
      if (preloggedAvatar) {
        preloggedAvatar.src = session.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(session.nombre || 'User')}&background=0284c7&color=fff`;
      }
      return;
    }
  }

  mostrarLoginForm();
}

/**
 * Ingreso directo un solo clic usando las credenciales en caché.
 */
async function ingresarRapidoPrelogueado() {
  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const email = session.email || localStorage.getItem('user_email');

  if (email) {
    try {
      const resp = await fetch('/api/auth/load-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
      });
      const res = await resp.json();

      if (res.status === 'success') {
        if (res.user) {
          session.nombre = res.user.nombre || session.nombre;
          session.es_admin = res.user.es_admin !== undefined ? res.user.es_admin : session.es_admin;
          session.avatar = res.user.avatar || session.avatar;
          session.email = email;
          session.last_2fa = session.last_2fa || new Date().getTime();
        }

        localStorage.setItem('gennius_session', JSON.stringify(session));
        localStorage.setItem('user_email', email);

        inyectarBotonAdminNav(session);

        mostrarToastBienvenida(session);

        const authOverlay = document.getElementById('auth-overlay');
        if (authOverlay) authOverlay.style.display = 'none';

        if (typeof window.iniciarPrecargaBackground === 'function') {
          window.iniciarPrecargaBackground();
        }
      } else {
        mostrarMensajeUI("Sesión expirada. Por favor ingresa tus datos.");
        mostrarLoginForm();
      }
    } catch (e) {
      mostrarMensajeUI("Error reanudando la sesión activa.");
    }
  } else {
    mostrarLoginForm();
  }
}

/**
 * Cierra la sesión activa en pantalla, pero PRESERVA la tarjeta pre-logueada
 * para acceso rápido posterior.
 */
function cerrarSesion() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';

  const navControls = document.getElementById('nav-user-controls');
  if (navControls) navControls.remove();

  localStorage.removeItem('temp_email');
  localStorage.removeItem('temp_pwd');
  localStorage.removeItem('temp_user');

  const alertBox = document.getElementById('auth-ui-alert');
  if (alertBox) alertBox.style.display = 'none';

  const authOverlay = document.getElementById('auth-overlay');
  if (authOverlay) authOverlay.style.display = 'flex';

  comprobarSesionGuardada();
}

/**
 * Conmuta la interfaz hacia el formulario de login tradicional.
 */
function mostrarLoginForm() {
  const alertBox = document.getElementById('auth-ui-alert');
  if (alertBox) alertBox.style.display = 'none';

  const cardPrelogged = document.getElementById('card-prelogged');
  const cardLogin = document.getElementById('card-login');
  const card2fa = document.getElementById('card-2fa');
  const cardReset = document.getElementById('card-reset-pwd');

  if (cardPrelogged) cardPrelogged.style.display = 'none';
  if (card2fa) card2fa.style.display = 'none';
  if (cardReset) cardReset.style.display = 'none';
  if (cardLogin) cardLogin.style.display = 'flex';
}

/* ==========================================================================
   2. FLUJO DE AUTENTICACIÓN, 2FA Y RESETEO DE PASSWORD
   ========================================================================== */

function iniciarSesion() {
  const email = document.getElementById('login-email')?.value || '';
  const password = document.getElementById('login-password')?.value || '';

  if (!email || !password) {
    mostrarMensajeUI("Por favor ingresa tu correo y contraseña.");
    return;
  }

  const btnLogin = document.querySelector('#card-login .btn-gennius-primary');
  const textoOriginal = btnLogin ? btnLogin.innerHTML : 'Iniciar sesión';

  if (btnLogin) {
    btnLogin.disabled = true;
    btnLogin.classList.add('btn-disabled');
    btnLogin.innerHTML = `<span class="btn-spinner"></span> Validando...`;
  }

  fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
  .then(r => r.json())
  .then(res => {
    if (res.status === 'forced_password_change') {
      localStorage.setItem('temp_email', email);
      const cardLogin = document.getElementById('card-login');
      const cardForced = document.getElementById('card-forced-pwd');
      if (cardLogin) cardLogin.style.display = 'none';
      if (cardForced) cardForced.style.display = 'flex';
      mostrarMensajeUI("Debes actualizar tu contraseña temporal.", "success");
    } else if (res.status === '2fa_required') {
      localStorage.setItem('temp_email', email);
      localStorage.setItem('temp_pwd', password);
      localStorage.setItem('temp_user', JSON.stringify(res.user_preview));

      const cardLogin = document.getElementById('card-login');
      const card2fa = document.getElementById('card-2fa');

      if (cardLogin) cardLogin.style.display = 'none';
      if (card2fa) card2fa.style.display = 'flex';

      limpiarCasillasOTP('#card-2fa');

      setTimeout(() => {
        const firstField = document.querySelector('#card-2fa .otp-field');
        if (firstField) firstField.focus();
      }, 100);
    } else if (res.message && res.message.includes('5.7.8')) {
      mostrarMensajeUI("Error SMTP: La contraseña de aplicación de Google es incorrecta.");
    } else {
      mostrarMensajeUI(res.message || "Usuario o contraseña incorrectos.");
    }
  })
  .catch(e => mostrarMensajeUI("Error de conexión con el servidor."))
  .finally(() => {
    if (btnLogin) {
      btnLogin.disabled = false;
      btnLogin.classList.remove('btn-disabled');
      btnLogin.innerHTML = textoOriginal;
    }
  });
}

/**
 * Configura el comportamiento de salto, pegado y borrado para cualquier contenedor OTP.
 */
function setupOTPInputs() {
  const containers = document.querySelectorAll('.otp-container');
  containers.forEach(container => {
    const inputs = container.querySelectorAll('.otp-field');

    inputs.forEach((input, index) => {
      input.addEventListener('input', (e) => {
        const val = e.target.value;
        if (val.length === 1) {
          if (index < inputs.length - 1) {
            inputs[index + 1].focus();
          } else {
            input.blur();
            // 🟢 Detección inteligente del módulo activo para auto-confirmar
            if (container.closest('#card-2fa')) {
              autoVerificarOTP();
            } else if (container.closest('#wrap-step-email-2fa')) {
              solicitarCambioEmail();
            } else if (container.closest('#wrap-step-pass-2fa')) {
              solicitarCambioPassword();
            }
          }
        }
      });

      input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !input.value && index > 0) {
          inputs[index - 1].focus();
        }
      });

      input.addEventListener('paste', (e) => {
        e.preventDefault();
        const pastedData = (e.clipboardData || window.clipboardData).getData('text').trim();
        if (/^\d{6}$/.test(pastedData)) {
          pastedData.split('').forEach((char, i) => {
            if (inputs[i]) inputs[i].value = char;
          });
          inputs[5].focus();
          inputs[5].blur();
          
          if (container.closest('#card-2fa')) {
            autoVerificarOTP();
          } else if (container.closest('#wrap-step-email-2fa')) {
            solicitarCambioEmail();
          } else if (container.closest('#wrap-step-pass-2fa')) {
            solicitarCambioPassword();
          }
        }
      });
    });
  });
}

/**
 * Obtiene el valor unido de 6 dígitos para un contenedor especificado o por defecto #card-2fa.
 */
function obtenerCodigoOTP(containerSelector = '#card-2fa') {
  const inputs = document.querySelectorAll(`${containerSelector} .otp-field`);
  let code = '';
  inputs.forEach(input => code += input.value.trim());
  return code;
}

/**
 * Blanquea las 6 casillas OTP de un contenedor específico.
 */
function limpiarCasillasOTP(containerSelector = '#card-2fa') {
  const inputs = document.querySelectorAll(`${containerSelector} .otp-field`);
  inputs.forEach(input => {
    input.value = '';
    input.classList.remove('field-valid', 'field-invalid');
  });
  if (inputs[0]) inputs[0].focus();
}

async function autoVerificarOTP() {
  const code = obtenerCodigoOTP('#card-2fa');
  if (code.length !== 6) return;

  const email = localStorage.getItem('temp_email');
  const password = localStorage.getItem('temp_pwd');
  const userPreview = JSON.parse(localStorage.getItem('temp_user') || '{}');
  const statusMsg = document.getElementById('otp-loading-status');

  if (statusMsg) statusMsg.style.display = 'block';

  try {
    const resp = await fetch('/api/auth/verify-2fa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, code, password })
    });
    const res = await resp.json();

    if (res.status === 'success') {
      const avatarAuto = userPreview.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(userPreview.nombre || email)}&background=0284c7&color=fff`;

      const session = {
        email: email,
        nombre: userPreview.nombre || email,
        es_admin: userPreview.es_admin || false,
        avatar: avatarAuto,
        last_2fa: new Date().getTime()
      };

      localStorage.setItem('gennius_session', JSON.stringify(session));
      localStorage.setItem('user_email', email);

      inyectarBotonAdminNav(session);

      mostrarToastBienvenida(session);

      const authOverlay = document.getElementById('auth-overlay');
      if (authOverlay) authOverlay.style.display = 'none';

      if (typeof window.iniciarPrecargaBackground === 'function') {
        window.iniciarPrecargaBackground();
      }
    } else {
      mostrarMensajeUI(res.message || "Código de verificación incorrecto.");
      limpiarCasillasOTP('#card-2fa');
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al verificar el código.");
    limpiarCasillasOTP('#card-2fa');
  } finally {
    if (statusMsg) statusMsg.style.display = 'none';
  }
}

function solicitarResetPassword(event) {
  if (event) event.preventDefault();
  const cardLogin = document.getElementById('card-login');
  const cardReset = document.getElementById('card-reset-pwd');
  const cardPrelogged = document.getElementById('card-prelogged');

  if (cardLogin) cardLogin.style.display = 'none';
  if (cardPrelogged) cardPrelogged.style.display = 'none';
  if (cardReset) cardReset.style.display = 'flex';

  const inputEmail = document.getElementById('reset-email-input');
  const loginEmail = document.getElementById('login-email')?.value || '';
  if (inputEmail) inputEmail.value = loginEmail;
}

async function ejecutarResetPassword() {
  const emailInput = document.getElementById('reset-email-input');
  const email = emailInput ? emailInput.value.trim() : '';
  const btn = document.getElementById('btn-do-reset');

  if (!email) {
    mostrarMensajeUI("Por favor ingresa tu correo corporativo.");
    return;
  }

  const btnText = btn ? btn.querySelector('.btn-text') : null;
  const btnSpinner = btn ? btn.querySelector('.btn-spinner') : null;

  if (btn) btn.disabled = true;
  if (btnText) btnText.style.display = 'none';
  if (btnSpinner) btnSpinner.style.display = 'inline-block';

  try {
    const resp = await fetch('/api/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    
    const res = await resp.json();

    if (resp.ok && (res.status === 'success' || res.message)) {
      // 🟢 Inyección de notificación de éxito dentro de la misma tarjeta antes de salir
      const cardReset = document.getElementById('card-reset-pwd');
      let msgBox = document.getElementById('reset-success-msg');
      if (!msgBox) {
        msgBox = document.createElement('div');
        msgBox.id = 'reset-success-msg';
        msgBox.className = 'auth-ui-alert success';
        msgBox.style.marginTop = '12px';
        cardReset.appendChild(msgBox);
      }
      msgBox.innerHTML = `<span class="alert-dot"></span><span>${res.message || 'Se ha enviado la clave temporal a tu correo.'}</span>`;
      msgBox.style.display = 'flex';

      setTimeout(() => {
        if (emailInput) emailInput.value = '';
        if (msgBox) msgBox.style.display = 'none';
        mostrarLoginForm();
      }, 3500);
    } else {
      mostrarMensajeUI(res.message || res.detail || "No se pudo restablecer la contraseña.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de conexión al solicitar restablecimiento.");
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.style.display = 'inline';
    if (btnSpinner) btnSpinner.style.display = 'none';
  }
}

async function guardarNuevaPasswordObligatoria() {
  const email = localStorage.getItem('temp_email');
  const newPasswordInput = document.getElementById('new-forced-password');
  const newPassword = newPasswordInput?.value.trim();

  const btn = document.querySelector('#card-forced-pwd .btn-gennius-primary');
  const textoOriginal = btn ? btn.innerText : 'Guardar Nueva Clave';

  if (!email || !newPassword) {
    mostrarMensajeUI("Por favor ingresa la nueva contraseña.");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.classList.add('btn-disabled');
    btn.innerHTML = `<span class="btn-spinner"></span> Guardando...`;
  }

  try {
    const resp = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, new_password: newPassword })
    });

    const res = await resp.json();

    if (res.status === 'success') {
      mostrarMensajeUI("¡Contraseña actualizada! Ya puedes ingresar.", "success");

      if (newPasswordInput) newPasswordInput.value = '';
      limpiarCasillasOTP('#card-2fa');

      const cardForced = document.getElementById('card-forced-pwd');
      if (cardForced) cardForced.style.display = 'none';
      mostrarLoginForm();
    } else {
      mostrarMensajeUI(res.message || "Error al actualizar la contraseña.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red intentando actualizar la contraseña.");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('btn-disabled');
      btn.innerText = textoOriginal;
    }
  }
}

/* ==========================================================================
   3. REGISTRO DE NUEVOS USUARIOS Y VALIDACIONES
   ========================================================================== */

function limpiarFormularioRegistro() {
  const form = document.getElementById('form-registro-usuario');
  if (form) form.reset();
  destinatariosFinalesChips = [];
  destinatariosBccChips = [];
  renderChips('chips-finales-box', 'input-finales', destinatariosFinalesChips);
  renderChips('chips-bcc-box', 'input-bcc', destinatariosBccChips);
  const alertBox = document.getElementById('auth-reg-alert');
  if (alertBox) alertBox.style.display = 'none';
  const inputs = document.querySelectorAll('#view-register-container .gennius-input');
  inputs.forEach(input => input.classList.remove('field-valid', 'field-invalid'));
}

function mostrarVistaRegistro() {
  limpiarFormularioRegistro();
  const loginView = document.getElementById('view-login-container');
  const regView = document.getElementById('view-register-container');
  if (loginView) loginView.style.display = 'none';
  if (regView) regView.style.display = 'flex';
}

function mostrarVistaLogin() {
  const loginView = document.getElementById('view-login-container');
  const regView = document.getElementById('view-register-container');
  if (regView) regView.style.display = 'none';
  if (loginView) loginView.style.display = 'flex';
  mostrarLoginForm();
}

function esPasswordFuerte(pwd) {
  const regexPwd = /^(?=.*[0-9])(?=.*[@$!%*?&.#_-])[A-Za-z0-9@$!%*?&.#_-]{12,}$/;
  return regexPwd.test(pwd);
}

function setupLiveValidation() {
  const regexEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const campos = [
    { id: 'reg-email', fn: val => regexEmail.test(val) },
    { id: 'reg-password', fn: val => esPasswordFuerte(val) },
    { id: 'reg-gemini-key', fn: val => !val || (val.startsWith('A') && val.length >= 20) },
    { id: 'reg-remitente', fn: val => !val || regexEmail.test(val) },
    { id: 'reg-google-password', fn: val => !val || val.replace(/\s+/g, '').length === 16 },
    { id: 'reg-mi-correo', fn: val => !val || regexEmail.test(val) },
    { id: 'reg-sheet-id', fn: val => !val || val.length >= 20 },
    { id: 'reg-gid-hoja', fn: val => !val || /^\d+$/.test(val) }
  ];

  campos.forEach(c => {
    const el = document.getElementById(c.id);
    if (!el) return;
    el.addEventListener('input', () => {
      if (c.id === 'reg-gid-hoja') el.value = el.value.replace(/\D/g, '');
      const val = el.value.trim();
      if (!val) {
        el.classList.remove('field-valid', 'field-invalid');
      } else if (c.fn(val)) {
        el.classList.add('field-valid');
        el.classList.remove('field-invalid');
      } else {
        el.classList.add('field-invalid');
        el.classList.remove('field-valid');
      }
    });
  });
}

function mostrarMensajeRegUI(mensaje, tipo = 'error') {
  const alertBox = document.getElementById('auth-reg-alert');
  const alertText = document.getElementById('auth-reg-alert-text');
  if (alertBox && alertText) {
    alertText.innerText = mensaje;
    if (tipo === 'success') alertBox.classList.add('success');
    else alertBox.classList.remove('success');
    alertBox.style.display = 'flex';
  }
}

async function completarRegistro() {
  // 🟢 Desactivar autocompletado de navegador de forma forzada
  const inputsRegistro = document.querySelectorAll('#form-registro-usuario input');
  inputsRegistro.forEach(input => {
    input.setAttribute('autocomplete', 'one-time-code');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('autocapitalize', 'none');
    input.setAttribute('spellcheck', 'false');
  });

  const email = document.getElementById('reg-email')?.value.trim();
  const password = document.getElementById('reg-password')?.value.trim();
  const geminiKey = document.getElementById('reg-gemini-key')?.value.trim();
  const remitente = document.getElementById('reg-remitente')?.value.trim();
  const googlePwd = document.getElementById('reg-google-password')?.value.trim().replace(/\s+/g, '');
  const miCorreo = document.getElementById('reg-mi-correo')?.value.trim();
  const sheetId = document.getElementById('reg-sheet-id')?.value.trim();

  const regexEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  if (!email || !regexEmail.test(email)) {
    mostrarMensajeRegUI("Por favor ingresa un correo corporativo válido.");
    return;
  }
  if (!password || !esPasswordFuerte(password)) {
    mostrarMensajeRegUI("La contraseña debe tener mínimo 12 caracteres, al menos un número y un carácter especial.");
    return;
  }

  const payload = {
    nombre: document.getElementById('reg-nombre')?.value.trim() || "",
    apellido: document.getElementById('reg-apellido')?.value.trim() || "",
    email: email,
    password: password,
    gemini_api_key: geminiKey || "",
    remitente: remitente || "",
    google_app_password: googlePwd || "",
    mi_correo: miCorreo || "",
    destinatarios_finales: typeof destinatariosFinalesChips !== 'undefined' ? destinatariosFinalesChips : [],
    destinatarios_bcc: typeof destinatariosBccChips !== 'undefined' ? destinatariosBccChips : [],
    nombre_firma: document.getElementById('reg-firma-nombre')?.value.trim() || "",
    cargo_firma: document.getElementById('reg-firma-cargo')?.value.trim() || "",
    sheet_id: sheetId || "",
    gid_hoja: document.getElementById('reg-gid-hoja')?.value.trim() || "0"
  };

  const btn = document.getElementById('btn-completar-reg');
  const btnText = btn ? btn.querySelector('.btn-text') : null;
  const btnSpinner = btn ? btn.querySelector('.btn-spinner') : null;

  // 🟢 Activar spinner y ocultar texto del botón durante todo el proceso
  if (btn) btn.disabled = true;
  if (btnText) btnText.style.display = 'none';
  if (btnSpinner) btnSpinner.style.display = 'inline-block';

  let esExitoso = false;

  try {
    const resp = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();

    if (resp.ok && (res.status === 'success' || res.message)) {
      esExitoso = true; // Marcar como exitoso para mantener el spinner durante el setTimeout
      const msgExito = res.message || "La cuenta fue registrada correctamente. Aprobación pendiente.";
      mostrarMensajeRegUI(msgExito, "success");

      // 🟢 Mantiene el spinner activo durante los 2.5s antes de la redirección
      setTimeout(() => {
        limpiarFormularioRegistro();
        mostrarVistaLogin();
        mostrarMensajeUI(msgExito, "success");

        // Restablecer botón solo al finalizar la redirección
        if (btn) btn.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnSpinner) btnSpinner.style.display = 'none';
      }, 2500);
    } else {
      mostrarMensajeRegUI(res.message || res.detail || "No se pudo completar el registro.");
    }
  } catch (e) {
    mostrarMensajeRegUI("Error de red al registrar la cuenta.");
  } finally {
    // 🔄 Si ocurrió un error, restaurar el botón de inmediato
    if (!esExitoso) {
      if (btn) btn.disabled = false;
      if (btnText) btnText.style.display = 'inline';
      if (btnSpinner) btnSpinner.style.display = 'none';
    }
  }
}

/* ==========================================================================
   4. COMPONENTES UI Y UTILIDADES (NAVBAR, CHIPS, AVATARES)
   ========================================================================== */

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const eyeOff = btn.querySelector('.eye-off');
  const eyeOn = btn.querySelector('.eye-on');

  if (input.type === 'password') {
    input.type = 'text';
    if (eyeOff) eyeOff.style.display = 'none';
    if (eyeOn) eyeOn.style.display = 'block';
  } else {
    input.type = 'password';
    if (eyeOff) eyeOff.style.display = 'block';
    if (eyeOn) eyeOn.style.display = 'none';
  }
}

function habilitarCampo(input) {
  if (input.classList.contains('input-lockable')) {
    input.classList.add('unlocked');
    input.removeAttribute('readonly');
    input.focus();
  }
}

function inyectarBotonAdminNav(session) {
  const headerBrand = document.querySelector('.brand-container');
  if (!headerBrand) return;

  const existente = document.getElementById('nav-user-controls');
  if (existente) existente.remove();

  const navDiv = document.createElement('div');
  navDiv.id = 'nav-user-controls';
  navDiv.className = 'user-nav-actions';
  const avatarUrl = session.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(session.nombre || 'User')}&background=0284c7&color=fff`;

  let adminOption = '';
  if (session.es_admin) {
    adminOption = `<button class="dropdown-item-btn" onclick="abrirAdminUsuariosModal()">Gestionar Usuarios</button>`;
  }

  navDiv.innerHTML = `
    <button class="avatar-nav-btn" onclick="toggleUserDropdown(event)">
      <img src="${avatarUrl}" alt="Perfil">
    </button>
    <div id="user-dropdown-menu" class="user-dropdown-menu" style="display: none;">
      <div class="dropdown-user-header">
        <span class="dropdown-user-name">${session.nombre || 'Usuario'}</span>
        <span class="dropdown-user-role">${session.es_admin ? 'Administrador' : 'Usuario'}</span>
      </div>
      <button class="dropdown-item-btn" onclick="abrirMiPerfilModal()">Mi Perfil</button>
      <button class="dropdown-item-btn" onclick="abrirModalModelosIA()">Modelos IA</button>
      ${adminOption}
      <button class="dropdown-item-btn danger" onclick="cerrarSesion()">Cerrar Sesión</button>
    </div>
  `;
  headerBrand.appendChild(navDiv);

  document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('user-dropdown-menu');
    const avatarBtn = document.querySelector('.avatar-nav-btn');
    if (dropdown && !dropdown.contains(e.target) && avatarBtn && !avatarBtn.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });
}

function toggleUserDropdown(event) {
  event.stopPropagation();
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) {
    dropdown.style.display = dropdown.style.display === 'none' ? 'flex' : 'none';
  }
}

function mostrarMensajeUI(mensaje, tipo = 'error') {
  const alertBox = document.getElementById('auth-ui-alert');
  const alertText = document.getElementById('auth-ui-alert-text');
  if (alertBox && alertText) {
    alertText.innerText = mensaje;
    if (tipo === 'success') alertBox.classList.add('success');
    else alertBox.classList.remove('success');
    alertBox.style.display = 'flex';
    setTimeout(() => { alertBox.style.display = 'none'; }, 5000);
  }
}

function cerrarModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = 'none';
}

/* ==========================================================================
   5. MODAL MI PERFIL, SUBMÓDULOS DE EDICIÓN Y AVATAR
   ========================================================================== */

function resetSubmoduloEmail() {
  pasoActualEmail = 1;
  const nuevoEmail = document.getElementById('edit-nuevo-email');
  const wrap2fa = document.getElementById('wrap-step-email-2fa');
  const btn = document.getElementById('btn-action-email');
  const countdownMsg = document.getElementById('email-countdown-msg');

  if (nuevoEmail) nuevoEmail.value = '';
  limpiarCasillasOTP('#wrap-step-email-2fa');
  if (wrap2fa) wrap2fa.style.display = 'none';
  if (countdownMsg) countdownMsg.style.display = 'none';
  if (btn) {
    btn.innerText = "Solicitar Cambio de Correo";
    btn.disabled = false;
    btn.style.display = 'block';
  }
}

function resetSubmoduloPass() {
  pasoActualPass = 1;
  const p1 = document.getElementById('edit-new-pass-1');
  const p2 = document.getElementById('edit-new-pass-2');
  const wrap2fa = document.getElementById('wrap-step-pass-2fa');
  const btn = document.getElementById('btn-action-pass');

  if (p1) p1.value = '';
  if (p2) p2.value = '';
  limpiarCasillasOTP('#wrap-step-pass-2fa');
  if (wrap2fa) wrap2fa.style.display = 'none';
  if (btn) {
    btn.innerText = "Actualizar Contraseña";
    btn.disabled = false;
    btn.style.display = 'block'; // 🟢 Restaurar visibilidad
  }
}

async function abrirMiPerfilModal() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';
  resetSubmoduloEmail();
  resetSubmoduloPass();

  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email') || '';

  document.querySelectorAll('.input-lockable').forEach(inp => {
    inp.classList.remove('unlocked');
    inp.setAttribute('readonly', 'true');
  });

  try {
    const resp = await fetch(`/api/auth/profile?email=${encodeURIComponent(userEmail)}`);
    const res = await resp.json();
    if (res.status === 'success' && res.user) {
      const u = res.user;
      document.getElementById('edit-nombre').value = u.nombre || '';
      document.getElementById('edit-apellido').value = u.apellido || '';
      document.getElementById('edit-gemini-key').value = u.gemini_api_key || '';
      document.getElementById('edit-remitente').value = u.remitente || '';
      document.getElementById('edit-google-password').value = u.google_app_password || '';
      document.getElementById('edit-mi-correo').value = u.mi_correo || '';
      document.getElementById('edit-firma-nombre').value = u.nombre_firma || '';
      document.getElementById('edit-firma-cargo').value = u.cargo_firma || '';
      document.getElementById('edit-sheet-id').value = u.sheet_id || '';
      document.getElementById('edit-gid-hoja').value = u.gid_hoja || '0';

      // 🟢 Carga dinámica limpia de los chips de perfil
      editFinalesChips = Array.isArray(u.destinatarios_finales) 
        ? [...u.destinatarios_finales] 
        : (u.destinatarios_finales || '').split(',').map(s => s.trim()).filter(Boolean);

      editBccChips = Array.isArray(u.destinatarios_bcc) 
        ? [...u.destinatarios_bcc] 
        : (u.destinatarios_bcc || '').split(',').map(s => s.trim()).filter(Boolean);

      renderChips('edit-chips-finales-box', 'edit-input-finales', editFinalesChips);
      renderChips('edit-chips-bcc-box', 'edit-input-bcc', editBccChips);
      renderAvatarPicker(u.avatar || session.avatar);
    }
  } catch (e) {
    console.error("Error cargando datos de perfil:", e);
  }

  const modal = document.getElementById('modal-mi-perfil');
  if (modal) modal.style.display = 'flex';
}

function renderAvatarPicker(selectedAvatar) {
  const currentImg = document.getElementById('profile-current-avatar-img');
  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const avatarActual = selectedAvatar || session.avatar || 'https://api.dicebear.com/7.x/adventurer/svg?seed=rfuusizz&backgroundColor=ff8fab,ffb703,4cc9a7,4d96ff,b57bff';

  if (currentImg) {
    currentImg.src = avatarActual;
  }
}

function abrirModalSelectorAvatar() {
  const grid = document.getElementById('avatar-picker-grid');
  if (!grid) return;

  const bgParams = "backgroundColor[]=ff8fab&backgroundColor[]=ffb703&backgroundColor[]=4cc9a7&backgroundColor[]=4d96ff&backgroundColor[]=b57bff";
  const seeds = [
    "ddqipdl7", "lfkbgep7", "eutgokw0", "n4gzt1qf", "gv5zyxe7", "3dwgx4yv",
    "yt8hczcl", "3x2madpq", "wq11bcoh", "cdq8z35s", "vn8s0j8j", "5ezqvdp4",
    "inqdotov", "ylju0twg", "twrx1uiu", "9dry6dln", "q6ytosiu", "jw6yn7b1",
    "g4pj9bxv", "9c89zir9", "8km027rz", "rfzqawlv", "i5sghjrb", "n4q52nkh",
    "apcg2l9p", "6nb4hr9i", "w3b58s9j", "w5majsyk", "t6f1a3cs", "acgkovvw",
    "b5h6b1pn", "duia0myf", "hh73uz4w", "r8h4rlgo", "hp39fu4p", "8k41w0a8",
    "h3tup8gj", "3ec12zdg", "ahuoiie7", "gt9s62bv", "invgqmw0", "d4xe0d7v"
  ];

  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const currentImg = document.getElementById('profile-current-avatar-img');
  avatarSeleccionadoTemp = currentImg ? currentImg.src : (session.avatar || "");

  const avatares = seeds.map(s => `https://api.dicebear.com/7.x/adventurer/svg?seed=${s.trim()}&${bgParams}`);

  grid.innerHTML = avatares.map(url => `
    <div class="avatar-modal-option ${url === avatarSeleccionadoTemp ? 'selected' : ''}" onclick="seleccionarAvatarModal(this, '${url}')">
      <img src="${url}" alt="Avatar">
    </div>
  `).join('');

  const modal = document.getElementById('modal-selector-avatar');
  if (modal) modal.style.display = 'flex';
}

function seleccionarAvatarModal(el, url) {
  document.querySelectorAll('.avatar-modal-option').forEach(opt => opt.classList.remove('selected'));
  el.classList.add('selected');
  avatarSeleccionadoTemp = url;
}

async function confirmarSeleccionAvatar() {
  if (!avatarSeleccionadoTemp) {
    cerrarModal('modal-selector-avatar');
    return;
  }

  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email');

  const currentImg = document.getElementById('profile-current-avatar-img');
  if (currentImg) currentImg.src = avatarSeleccionadoTemp;

  session.avatar = avatarSeleccionadoTemp;
  localStorage.setItem('gennius_session', JSON.stringify(session));

  inyectarBotonAdminNav(session);

  try {
    const resp = await fetch('/api/auth/profile/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: userEmail, avatar: avatarSeleccionadoTemp })
    });
    const res = await resp.json();
    if (res.status === 'success') {
      if (typeof showErrorToast === 'function') {
        showErrorToast("Avatar guardado correctamente.", "success");
      }
    } else {
      mostrarMensajeUI(res.message || "No se pudo actualizar el avatar en el servidor.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red guardando el avatar.");
  } finally {
    cerrarModal('modal-selector-avatar');
  }
}

async function guardarCambiosPerfil() {
  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email');

  const payload = {
    email: userEmail,
    nombre: document.getElementById('edit-nombre').value,
    apellido: document.getElementById('edit-apellido').value,
    gemini_api_key: document.getElementById('edit-gemini-key').value,
    remitente: document.getElementById('edit-remitente').value,
    google_app_password: document.getElementById('edit-google-password').value,
    mi_correo: document.getElementById('edit-mi-correo').value,
    destinatarios_finales: editFinalesChips, // 🟢 Envía la lista actualizada de los chips de Perfil
    destinatarios_bcc: editBccChips,           // 🟢 Envía la lista actualizada de los chips de Perfil
    nombre_firma: document.getElementById('edit-firma-nombre').value,
    cargo_firma: document.getElementById('edit-firma-cargo').value,
    sheet_id: document.getElementById('edit-sheet-id').value,
    gid_hoja: document.getElementById('edit-gid-hoja').value
  };

  try {
    const resp = await fetch('/api/auth/profile/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (res.status === 'success') {
      session.nombre = `${payload.nombre} ${payload.apellido}`.trim();
      localStorage.setItem('gennius_session', JSON.stringify(session));
      inyectarBotonAdminNav(session);
      cerrarModal('modal-mi-perfil');
      if (typeof showErrorToast === 'function') {
        showErrorToast("Perfil actualizado con éxito.", "success");
      }
    } else {
      mostrarMensajeUI(res.message || "Error al actualizar perfil.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red actualizando perfil.");
  }
}

async function solicitarCambioEmail() {
  const nuevoEmail = document.getElementById('edit-nuevo-email')?.value.trim();
  let emailActual = localStorage.getItem('user_email');
  if (!emailActual) {
    const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
    emailActual = session.email;
  }

  const btn = document.getElementById('btn-action-email');
  const wrap2fa = document.getElementById('wrap-step-email-2fa');
  const code2fa = obtenerCodigoOTP('#wrap-step-email-2fa');

  if (!nuevoEmail) {
    mostrarMensajeUI("Ingresa el nuevo correo corporativo.");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="btn-spinner"></span> Procesando...`;
  }

  try {
    if (pasoActualEmail === 1) {
      const resp = await fetch('/api/auth/request-email-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_actual: emailActual, nuevo_email: nuevoEmail })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        pasoActualEmail = 2;
        if (wrap2fa) wrap2fa.style.display = 'block';
        if (btn) btn.style.display = 'none'; // 🟢 Ocultar botón en paso 2
        limpiarCasillasOTP('#wrap-step-email-2fa');
        mostrarMensajeUI("Código enviado a tu nuevo correo.", "success");
      } else {
        mostrarMensajeUI(res.message || "Error al solicitar el cambio.");
      }
    } else {
      if (!code2fa || code2fa.length !== 6) {
        mostrarMensajeUI("Ingresa el código 2FA de 6 dígitos.");
        if (btn) {
          btn.disabled = false;
          btn.innerText = "Confirmar Cambio de Correo";
        }
        return;
      }
      const resp = await fetch('/api/auth/confirm-email-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_actual: emailActual, nuevo_email: nuevoEmail, code: code2fa })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        localStorage.setItem('user_email', nuevoEmail);
        let session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
        session.email = nuevoEmail;
        localStorage.setItem('gennius_session', JSON.stringify(session));

        if (typeof showErrorToast === 'function') {
          showErrorToast("Correo actualizado con éxito.", "success");
        }

        // 🟢 CUENTA REGRESIVA DE 5 A 0 SEGUNDOS
        const countdownMsg = document.getElementById('email-countdown-msg');
        const countdownNum = document.getElementById('email-countdown-num');
        
        if (countdownMsg && countdownNum) {
          let segundosRestantes = 5;
          countdownNum.innerText = segundosRestantes;
          countdownMsg.style.display = 'block';

          const intervalo = setInterval(() => {
            segundosRestantes--;
            if (segundosRestantes >= 0) {
              countdownNum.innerText = segundosRestantes;
            }
            
            if (segundosRestantes <= 0) {
              clearInterval(intervalo);
              resetSubmoduloEmail();
              cerrarModal('modal-mi-perfil');
              cerrarSesion();
            }
          }, 1000);
        } else {
          // Respaldo inmediato si no existiera el elemento DOM
          setTimeout(() => {
            resetSubmoduloEmail();
            cerrarModal('modal-mi-perfil');
            cerrarSesion();
          }, 1500);
        }

      } else {
        mostrarMensajeUI(res.message || "Código incorrecto o expirado.");
      }
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al solicitar el cambio de correo.");
  } finally {
    if (btn && pasoActualEmail === 1) {
      btn.disabled = false;
      btn.innerText = "Solicitar Cambio de Correo";
    } else if (btn && pasoActualEmail === 2 && document.getElementById('wrap-step-email-2fa')?.style.display === 'block') {
      btn.disabled = false;
      btn.innerText = "Confirmar Cambio de Correo";
    }
  }
}

function toggleAmbasPasswords(btnPresionado) {
  const input1 = document.getElementById('edit-new-pass-1');
  const input2 = document.getElementById('edit-new-pass-2');
  if (!input1 || !input2) return;

  // Determinar si debemos mostrar u ocultar basándonos en el primer input
  const nuevoTipo = input1.type === 'password' ? 'text' : 'password';

  // Aplicar el nuevo tipo a ambos inputs
  input1.type = nuevoTipo;
  input2.type = nuevoTipo;

  // Actualizar los íconos de los botones de ambos campos
  const botones = [
    input1.closest('.pwd-input-wrap')?.querySelector('.pwd-eye-btn'),
    input2.closest('.pwd-input-wrap')?.querySelector('.pwd-eye-btn')
  ];

  botones.forEach(btn => {
    if (!btn) return;
    const eyeOff = btn.querySelector('.eye-off');
    const eyeOn = btn.querySelector('.eye-on');

    if (nuevoTipo === 'text') {
      if (eyeOff) eyeOff.style.display = 'none';
      if (eyeOn) eyeOn.style.display = 'block';
    } else {
      if (eyeOff) eyeOff.style.display = 'block';
      if (eyeOn) eyeOn.style.display = 'none';
    }
  });
}

async function solicitarCambioPassword() {
  const p1 = document.getElementById('edit-new-pass-1')?.value.trim();
  const p2 = document.getElementById('edit-new-pass-2')?.value.trim();

  let emailActual = localStorage.getItem('user_email');
  if (!emailActual) {
    const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
    emailActual = session.email;
  }

  const btn = document.getElementById('btn-action-pass');
  const wrap2fa = document.getElementById('wrap-step-pass-2fa');
  const code2fa = obtenerCodigoOTP('#wrap-step-pass-2fa');

  if (!emailActual) {
    mostrarMensajeUI("No se detectó una sesión activa. Vuelve a iniciar sesión.");
    return;
  }

  if (!p1 || !p2) {
    mostrarMensajeUI("Ingresa y confirma la nueva contraseña.");
    return;
  }

  if (p1 !== p2) {
    mostrarMensajeUI("Las contraseñas no coinciden.");
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="btn-spinner"></span> Procesando...`;
  }

  try {
    if (pasoActualPass === 1) {
      const resp = await fetch('/api/auth/request-password-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailActual })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        pasoActualPass = 2;
        if (wrap2fa) wrap2fa.style.display = 'block';
        if (btn) btn.style.display = 'none'; // 🟢 Ocultar botón en paso 2
        limpiarCasillasOTP('#wrap-step-pass-2fa');
        mostrarMensajeUI("Código de verificación enviado a tu correo.", "success");
      } else {
        mostrarMensajeUI(res.message || "Error al solicitar el código.");
      }
    } else {
      if (!code2fa || code2fa.length !== 6) {
        mostrarMensajeUI("Ingresa el código de 6 dígitos.");
        if (btn) {
          btn.disabled = false;
          btn.innerText = "Confirmar Cambio de Contraseña";
        }
        return;
      }
      const resp = await fetch('/api/auth/confirm-password-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailActual, new_password: p1, code: code2fa })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        if (typeof showErrorToast === 'function') {
          showErrorToast("Contraseña actualizada correctamente.", "success");
        }
        setTimeout(() => {
          resetSubmoduloPass();
          cerrarModal('modal-mi-perfil');
        }, 1500);
      } else {
        mostrarMensajeUI(res.message || "Código 2FA incorrecto.");
      }
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al procesar el cambio de contraseña.");
  } finally {
    if (btn && pasoActualPass === 1) {
      btn.disabled = false;
      btn.innerText = "Actualizar Contraseña";
    } else if (btn && pasoActualPass === 2 && document.getElementById('wrap-step-pass-2fa')?.style.display === 'block') {
      btn.disabled = false;
      btn.innerText = "Confirmar Cambio de Contraseña";
    }
  }
}

/* ==========================================================================
   6. CONFIGURACIÓN MODELOS IA Y PANEL ADMINISTRADOR
   ========================================================================== */

async function abrirModalModelosIA() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';

  const email = localStorage.getItem('user_email');
  if (!email) return;

  try {
    const resp = await fetch(`/api/auth/get-user-config?email=${encodeURIComponent(email)}`);
    const res = await resp.json();
    if (res.status === 'success' && res.config) {
      const cfg = res.config;
      const elActivo = document.getElementById('ia-modelo-activo');
      const elGemini = document.getElementById('ia-key-gemini');
      const elGroq = document.getElementById('ia-key-groq');
      const elHf = document.getElementById('ia-key-hf');

      if (elActivo) elActivo.value = cfg.MODELO_IA_ACTIVO || 'gemini';
      if (elGemini) elGemini.value = cfg.GEMINI_API_KEY || '';
      if (elGroq) elGroq.value = cfg.GROQ_API_KEY || '';
      if (elHf) elHf.value = cfg.HF_API_KEY || '';
    }
  } catch (e) {
    console.error("Error al obtener llaves IA:", e);
  }

  const modal = document.getElementById('modal-modelos-ia');
  if (modal) modal.style.display = 'flex';
}

async function guardarConfiguracionIA() {
  const email = localStorage.getItem('user_email');
  const btn = document.getElementById('btn-save-ia-config');
  if (btn) btn.disabled = true;

  const payload = {
    email: email,
    config_env: {
      MODELO_IA_ACTIVO: document.getElementById('ia-modelo-activo')?.value || 'gemini',
      GEMINI_API_KEY: document.getElementById('ia-key-gemini')?.value.trim() || '',
      GROQ_API_KEY: document.getElementById('ia-key-groq')?.value.trim() || '',
      HF_API_KEY: document.getElementById('ia-key-hf')?.value.trim() || ''
    }
  };

  try {
    const resp = await fetch('/api/auth/update-user-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (res.status === 'success') {
      cerrarModal('modal-modelos-ia');
      if (typeof showErrorToast === 'function') {
        showErrorToast("Configuración de IA guardada con éxito.", "success");
      }
    } else {
      mostrarMensajeUI(res.message || "Error al guardar la configuración.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al actualizar IA.");
  } finally {
    if (btn) btn.disabled = false;
  }
}

let listaUsuariosCache = [];

async function abrirAdminUsuariosModal() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';

  const container = document.getElementById('admin-users-cards-container');
  if (container) container.innerHTML = '<div style="text-align:center; padding: 20px; color: #94a3b8;">Cargando lista de usuarios...</div>';

  document.getElementById('modal-admin-usuarios').style.display = 'flex';

  try {
    const resp = await fetch('/api/auth/admin/users');
    const data = await resp.json();
    listaUsuariosCache = Array.isArray(data) ? data : (data.users || []);
    
    // Renderizar por defecto 'todos'
    renderizarListaUsuariosAdmin(listaUsuariosCache);
  } catch (e) {
    if (container) container.innerHTML = '<div style="text-align:center; color:#f87171; padding: 20px;">Error al cargar las cuentas.</div>';
  }
}

function renderizarListaUsuariosAdmin(usuarios) {
  const container = document.getElementById('admin-users-cards-container');
  if (!container) return;

  if (usuarios.length === 0) {
    container.innerHTML = '<div style="text-align:center; padding: 20px; color: #94a3b8;">No se encontraron cuentas en esta categoría.</div>';
    return;
  }

  container.innerHTML = usuarios.map(u => {
    const esPendiente = u.estado === 'pendiente';
    const badgeEstado = esPendiente 
      ? `<span class="user-admin-badge status-pending">Pendiente</span>` 
      : `<span class="user-admin-badge status-active">Activo</span>`;
    
    // Dentro del .map() que renderiza las tarjetas de los usuarios:
    const btnAprobar = esPendiente ? `
      <button class="btn-approve-user" onclick="aprobarUsuarioAdmin('${u.email}', this)" title="Aprobar cuenta">
        <svg class="action-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      </button>` : '';

    return `
      <div class="user-admin-card">
        <div class="user-admin-avatar">
          <img src="${u.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(u.nombre || u.email)}&background=0284c7&color=fff`}" alt="Avatar">
        </div>
        <div class="user-admin-details">
          <span class="user-admin-name">${u.nombre || 'Sin Nombre'} ${u.apellido || ''}</span>
          <span class="user-admin-email">${u.email}</span>
          <div style="display: flex; gap: 6px; margin-top: 4px; align-items: center;">
            <span class="user-admin-badge ${u.es_admin ? 'admin' : 'user'}">${u.es_admin ? 'Administrador' : 'Usuario'}</span>
            ${badgeEstado}
          </div>
        </div>
        
        <div class="user-admin-actions">
          ${btnAprobar}
          <button class="btn-delete-user" onclick="eliminarUsuarioAdmin('${u.email}', this)" title="Eliminar cuenta">
            <span class="btn-delete-text">Eliminar</span>
            <svg class="trash-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              <line x1="10" y1="11" x2="10" y2="17"></line>
              <line x1="14" y1="11" x2="14" y2="17"></line>
            </svg>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function filtrarUsuariosAdmin(filtro, btnEl) {
  document.querySelectorAll('.admin-tab-btn').forEach(btn => btn.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');

  if (filtro === 'todos') {
    renderizarListaUsuariosAdmin(listaUsuariosCache);
  } else {
    const filtrados = listaUsuariosCache.filter(u => u.estado === filtro);
    renderizarListaUsuariosAdmin(filtrados);
  }
}

// 🟢 Función para aprobar usuario con spinner individual en el botón
async function aprobarUsuarioAdmin(email, btnEl) {
  if (!btnEl) btnEl = event.currentTarget;
  
  // Guardar el icono original y desactivar el botón
  const contenidoOriginal = btnEl.innerHTML;
  btnEl.disabled = true;
  btnEl.style.opacity = '0.7';
  btnEl.style.pointerEvents = 'none';
  
  // Inyectar spinner del mismo tamaño (20px)
  btnEl.innerHTML = `<span class="btn-spinner" style="width: 18px; height: 18px; border-width: 2px; margin: 0;"></span>`;

  try {
    const resp = await fetch('/api/auth/admin/users/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const res = await resp.json();

    if (resp.ok && res.status === 'success') {
      if (typeof showErrorToast === 'function') {
        showErrorToast(`Cuenta de ${email} aprobada y notificada por correo.`, "success");
      }
      // Recargar la lista para reflejar el cambio de estado
      abrirAdminUsuariosModal();
    } else {
      mostrarMensajeUI(res.message || "No se pudo aprobar la cuenta.");
      btnEl.disabled = false;
      btnEl.style.opacity = '1';
      btnEl.style.pointerEvents = 'auto';
      btnEl.innerHTML = contenidoOriginal;
    }
  } catch (e) {
    mostrarMensajeUI("Error de red intentando aprobar usuario.");
    btnEl.disabled = false;
    btnEl.style.opacity = '1';
    btnEl.style.pointerEvents = 'auto';
    btnEl.innerHTML = contenidoOriginal;
  }
}

// 🟢 Modal de Confirmación Personalizado para Eliminar
function eliminarUsuarioAdmin(email, btnEl) {
  if (!btnEl) btnEl = event.currentTarget;

  // Crear la modal de confirmación en la UI si no existe
  let confirmModal = document.getElementById('modal-confirm-delete');
  if (!confirmModal) {
    confirmModal = document.createElement('div');
    confirmModal.id = 'modal-confirm-delete';
    confirmModal.className = 'gennius-modal-backdrop';
    confirmModal.style.zIndex = '10020';
    document.body.appendChild(confirmModal);
  }

  confirmModal.innerHTML = `
    <div class="gennius-modal-content responsive-modal" style="max-width: 420px; text-align: center; padding: 24px;">
      <div style="font-size: 2.5rem; margin-bottom: 10px;">⚠️</div>
      <h3 class="auth-sub-title" style="margin-bottom: 8px; color: #f8fafc;">¿Eliminar usuario?</h3>
      <p class="auth-desc" style="margin-bottom: 20px; color: #94a3b8;">
        ¿Estás seguro de que deseas eliminar la cuenta <b style="color: #38bdf8;">${email}</b>? Esta acción no se puede deshacer.
      </p>
      <div style="display: flex; gap: 12px; justify-content: center;">
        <button class="btn-gennius-secondary" style="flex: 1; height: 42px;" onclick="cerrarModal('modal-confirm-delete')">
          Cancelar
        </button>
        <button id="btn-confirm-delete-action" class="btn-gennius-primary" style="flex: 1; height: 42px; background-color: #ef4444;" onclick="ejecutarEliminacionUsuario('${email}', this)">
          <span class="btn-text">Sí, Eliminar</span>
          <span class="btn-spinner" style="display: none; width: 18px; height: 18px; border-width: 2px;"></span>
        </button>
      </div>
    </div>
  `;

  confirmModal.style.display = 'flex';
}

// 🟢 Procesa la eliminación con spinner en el botón del modal y respuesta del servidor
async function ejecutarEliminacionUsuario(email, btnConfirm) {
  const btnText = btnConfirm.querySelector('.btn-text');
  const btnSpinner = btnConfirm.querySelector('.btn-spinner');

  btnConfirm.disabled = true;
  if (btnText) btnText.style.display = 'none';
  if (btnSpinner) btnSpinner.style.display = 'inline-block';

  try {
    const resp = await fetch(`/api/auth/admin/users/${encodeURIComponent(email)}`, { method: 'DELETE' });
    const res = await resp.json();

    if (resp.ok && res.status === 'success') {
      cerrarModal('modal-confirm-delete');
      if (typeof showErrorToast === 'function') {
        showErrorToast(`Usuario ${email} eliminado.`, "success");
      }
      abrirAdminUsuariosModal();
    } else {
      mostrarMensajeUI(res.message || "No se pudo eliminar el usuario.");
      cerrarModal('modal-confirm-delete');
    }
  } catch (e) {
    mostrarMensajeUI("Error de red intentando eliminar.");
    cerrarModal('modal-confirm-delete');
  }
}

/* ==========================================================================
   7. MANEJO DE CHIPS E INPUTS DINÁMICOS (UNIFICADO PERFIL + REGISTRO)
   ========================================================================== */
function inicializarChips() {
  setupChipInput('input-finales', 'chips-finales-box', destinatariosFinalesChips);
  setupChipInput('input-bcc', 'chips-bcc-box', destinatariosBccChips);
  setupChipInput('edit-input-finales', 'edit-chips-finales-box', editFinalesChips);
  setupChipInput('edit-input-bcc', 'edit-chips-bcc-box', editBccChips);
}

function setupChipInput(inputId, containerId, targetArray) {
  const input = document.getElementById(inputId);
  if (!input) return;

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      e.preventDefault();
      procesarEntradaChips(input.value, targetArray, containerId, inputId);
    }
  });

  input.addEventListener('blur', () => {
    if (input.value.trim()) {
      procesarEntradaChips(input.value, targetArray, containerId, inputId);
    }
  });

  input.addEventListener('paste', (e) => {
    e.preventDefault();
    const pastedData = (e.clipboardData || window.clipboardData).getData('text');
    procesarEntradaChips(pastedData, targetArray, containerId, inputId);
  });
}

function renderChips(boxId, inputId, targetArray) {
  const container = document.getElementById(boxId);
  const inputEl = document.getElementById(inputId);
  if (!container || !inputEl) return;

  const chipsExistentes = container.querySelectorAll('.chip-item');
  chipsExistentes.forEach(chip => chip.remove());

  targetArray.forEach((email, index) => {
    const chipNode = document.createElement('div');
    chipNode.className = 'chip-item';
    
    const labelSpan = document.createElement('span');
    labelSpan.textContent = email;

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'chip-remove-btn';
    btnRemove.innerHTML = '&times;';
    btnRemove.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      removerChip(boxId, inputId, index);
    });

    chipNode.appendChild(labelSpan);
    chipNode.appendChild(btnRemove);
    container.insertBefore(chipNode, inputEl);
  });
  inputEl.value = '';
}

function removerChip(boxId, inputId, index) {
  if (boxId === 'chips-finales-box') {
    destinatariosFinalesChips.splice(index, 1);
    renderChips(boxId, inputId, destinatariosFinalesChips);
  } else if (boxId === 'chips-bcc-box') {
    destinatariosBccChips.splice(index, 1);
    renderChips(boxId, inputId, destinatariosBccChips);
  } else if (boxId === 'edit-chips-finales-box') {
    editFinalesChips.splice(index, 1);
    renderChips(boxId, inputId, editFinalesChips);
  } else if (boxId === 'edit-chips-bcc-box') {
    editBccChips.splice(index, 1);
    renderChips(boxId, inputId, editBccChips);
  }
}

function procesarEntradaChips(inputText, targetArray, boxId, inputId) {
  const regexEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  const candidatos = inputText.split(/[\s,\n\r]+/);
  let seAgregoNuevo = false;

  candidatos.forEach(item => {
    const emailLimpio = item.trim().toLowerCase();
    if (emailLimpio && regexEmail.test(emailLimpio) && !targetArray.includes(emailLimpio)) {
      targetArray.push(emailLimpio);
      seAgregoNuevo = true;
    }
  });

  if (seAgregoNuevo) {
    renderChips(boxId, inputId, targetArray);
  }
}

function setupChipsListeners() {
  const configuraciones = [
    { boxId: 'chips-finales-box', inputId: 'input-finales', getArray: () => destinatariosFinalesChips },
    { boxId: 'chips-bcc-box', inputId: 'input-bcc', getArray: () => destinatariosBccChips }
  ];

  configuraciones.forEach(config => {
    const inputEl = document.getElementById(config.inputId);
    if (!inputEl) return;

    inputEl.addEventListener('paste', (e) => {
      e.preventDefault();
      const pastedData = (e.clipboardData || window.clipboardData).getData('text');
      procesarEntradaChips(pastedData, config.getArray(), config.boxId, config.inputId);
    });

    inputEl.addEventListener('keydown', (e) => {
      if (['Enter', ',', ' '].includes(e.key)) {
        e.preventDefault();
        procesarEntradaChips(inputEl.value, config.getArray(), config.boxId, config.inputId);
      }
    });

    inputEl.addEventListener('blur', () => {
      if (inputEl.value.trim()) {
        procesarEntradaChips(inputEl.value, config.getArray(), config.boxId, config.inputId);
      }
    });
  });
}

function mostrarToastBienvenida(session) {
  let toast = document.getElementById('welcome-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'welcome-toast';
    toast.className = 'welcome-toast-container';
    document.body.appendChild(toast);
  }

  const avatarUrl = session.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(session.nombre || 'User')}&background=0284c7&color=fff`;
  const primerNombre = (session.nombre || 'Usuario').split(' ')[0];

  toast.innerHTML = `
    <img src="${avatarUrl}" alt="Avatar" class="welcome-avatar">
    <div class="welcome-text-wrap">
      <span class="welcome-title">¡Bienvenido de vuelta, ${primerNombre}! 👋</span>
      <span class="welcome-sub">Sesión sincronizada correctamente</span>
    </div>
  `;

  setTimeout(() => toast.classList.add('show'), 300);
  setTimeout(() => toast.classList.remove('show'), 4500);
}

/* ==========================================================================
   8. EXPOSICIÓN GLOBAL DE FUNCIONES (WINDOW)
   ========================================================================== */
window.abrirModalSelectorAvatar = abrirModalSelectorAvatar;
window.seleccionarAvatarModal = seleccionarAvatarModal;
window.confirmarSeleccionAvatar = confirmarSeleccionAvatar;
window.solicitarCambioEmail = solicitarCambioEmail;
window.solicitarCambioPassword = solicitarCambioPassword;
window.abrirModalModelosIA = abrirModalModelosIA;
window.guardarConfiguracionIA = guardarConfiguracionIA;
window.iniciarSesion = iniciarSesion;
window.ingresarRapidoPrelogueado = ingresarRapidoPrelogueado;
window.mostrarLoginForm = mostrarLoginForm;
window.cerrarSesion = cerrarSesion;
window.habilitarCampo = habilitarCampo;
window.toggleUserDropdown = toggleUserDropdown;
window.abrirMiPerfilModal = abrirMiPerfilModal;
window.abrirAdminUsuariosModal = abrirAdminUsuariosModal;
window.eliminarUsuarioAdmin = eliminarUsuarioAdmin;
window.cerrarModal = cerrarModal;
window.guardarCambiosPerfil = guardarCambiosPerfil;
window.removerChip = removerChip;
window.mostrarVistaRegistro = mostrarVistaRegistro;
window.mostrarVistaLogin = mostrarVistaLogin;
window.completarRegistro = completarRegistro;
window.filtrarUsuariosAdmin = filtrarUsuariosAdmin;
window.aprobarUsuarioAdmin = aprobarUsuarioAdmin;
window.ejecutarEliminacionUsuario = ejecutarEliminacionUsuario;
window.togglePasswordVisibility = togglePasswordVisibility;
window.solicitarResetPassword = solicitarResetPassword;
window.toggleAmbasPasswords = toggleAmbasPasswords;
window.ejecutarResetPassword = ejecutarResetPassword;
window.guardarNuevaPasswordObligatoria = guardarNuevaPasswordObligatoria;