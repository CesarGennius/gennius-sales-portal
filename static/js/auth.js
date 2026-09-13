let destinatariosFinalesChips = [];
let destinatariosBccChips = [];
let editFinalesChips = [];
let editBccChips = [];
let pasoActualEmail = 1;
let pasoActualPass = 1;

document.addEventListener('DOMContentLoaded', () => {
  inicializarChips();
  setupOTPInputs();
  comprobarSesionGuardada();
  setupLiveValidation();
  setupChipsListeners();
});

function setupOTPInputs() {
  const container = document.querySelector('.otp-container');
  if (!container) return;
  const inputs = container.querySelectorAll('.otp-field');
  inputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      const val = e.target.value;
      if (val.length === 1) {
        if (index < inputs.length - 1) {
          inputs[index + 1].focus();
        } else {
          input.blur();
          autoVerificarOTP();
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
        autoVerificarOTP();
      }
    });
  });
}

function obtenerCodigoOTP() {
  const inputs = document.querySelectorAll('.otp-field');
  let code = '';
  inputs.forEach(input => code += input.value.trim());
  return code;
}

function limpiarCasillasOTP() {
  const inputs = document.querySelectorAll('.otp-field');
  inputs.forEach(input => input.value = '');
  if (inputs[0]) inputs[0].focus();
}

async function autoVerificarOTP() {
  const code = obtenerCodigoOTP();
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
        last_2fa: new Date().getTime() // 🔑 Marca temporal de 7 días
      };
      localStorage.setItem('gennius_session', JSON.stringify(session));
      localStorage.setItem('user_email', email);
      inyectarBotonAdminNav(session);
      
      const authOverlay = document.getElementById('auth-overlay');
      if (authOverlay) authOverlay.style.display = 'none';
      if (typeof window.iniciarPrecargaBackground === 'function') {
        window.iniciarPrecargaBackground();
      }
    } else {
      mostrarMensajeUI(res.message || "Código de verificación incorrecto.");
      limpiarCasillasOTP();
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al verificar el código.");
    limpiarCasillasOTP();
  } finally {
    if (statusMsg) statusMsg.style.display = 'none';
  }
}

// 🟢 VERIFICACIÓN DE SESIÓN GUARDADA DE 7 DÍAS CON TARJETA ESTILO FACEBOOK/INSTAGRAM
function comprobarSesionGuardada() {
  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email');
  const now = new Date().getTime();

  if (userEmail && session.last_2fa) {
    const diasTranscurridos = (now - session.last_2fa) / (1000 * 60 * 60 * 24);
    
    // Si la sesión fue iniciada hace menos de 7 días
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
      if (preloggedAvatar) preloggedAvatar.src = session.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(session.nombre || 'User')}&background=0284c7&color=fff`;
      return;
    }
  }
  
  // Si la sesión expiró o no existe, mostrar el formulario de login tradicional
  mostrarLoginForm();
}

// 🟢 INGRESO RÁPIDO DESDE LA TARJETA PRE-LOGUEADA (SIN CÓDIGO NI PASS)
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
        // Actualizar datos de usuario obtenidos del servidor
        if (res.user) {
          session.nombre = res.user.nombre || session.nombre;
          session.es_admin = res.user.es_admin !== undefined ? res.user.es_admin : session.es_admin;
          session.avatar = res.user.avatar || session.avatar;
          session.email = email;
          session.last_2fa = session.last_2fa || new Date().getTime(); // Conservar o actualizar fecha
        }
        
        localStorage.setItem('gennius_session', JSON.stringify(session));
        localStorage.setItem('user_email', email);
        
        inyectarBotonAdminNav(session);
        
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

// 🟢 4. CERRAR SESIÓN LIMPIO
function cerrarSesion() {
  localStorage.removeItem('gennius_session');
  localStorage.removeItem('user_email');
  localStorage.clear();
  sessionStorage.clear();
  
  const navControls = document.getElementById('nav-user-controls');
  if (navControls) navControls.remove();
  
  const authOverlay = document.getElementById('auth-overlay');
  if (authOverlay) authOverlay.style.display = 'flex';
  
  mostrarLoginForm();
}

function mostrarLoginForm() {
  const cardPrelogged = document.getElementById('card-prelogged');
  const cardLogin = document.getElementById('card-login');
  const card2fa = document.getElementById('card-2fa');
  const cardReset = document.getElementById('card-reset-pwd');
  
  if (cardPrelogged) cardPrelogged.style.display = 'none';
  if (card2fa) card2fa.style.display = 'none';
  if (cardReset) cardReset.style.display = 'none';
  if (cardLogin) cardLogin.style.display = 'flex';
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

// 🟢 1. RECUPERACIÓN DE CONTRASEÑA CON SPINNER DE CARGA
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
    if (res.status === 'success') {
      mostrarMensajeUI("¡Listo! Clave temporal enviada al correo.", "success");
      setTimeout(() => mostrarLoginForm(), 3000);
    } else {
      mostrarMensajeUI(res.message || "No se pudo restablecer la contraseña.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de conexión al solicitar restablecimiento.");
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.style.display = 'inline';
    if (btnSpinner) btnSpinner.style.display = 'none';
  }
}

// 🟢 2. SUBMÓDULO DE CAMBIO DE CORREO EN MI PERFIL
async function solicitarCambioEmail() {
  const nuevoEmail = document.getElementById('edit-nuevo-email')?.value.trim();
  const emailActual = localStorage.getItem('user_email');
  const btn = document.getElementById('btn-action-email');
  const wrap2fa = document.getElementById('wrap-step-email-2fa');
  const code2fa = document.getElementById('code-email-2fa')?.value.trim();

  if (!nuevoEmail) {
    mostrarMensajeUI("Ingresa el nuevo correo corporativo.");
    return;
  }

  if (pasoActualEmail === 1) {
    if (btn) btn.disabled = true;
    try {
      const resp = await fetch('/api/auth/request-email-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_actual: emailActual, nuevo_email: nuevoEmail })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        pasoActualEmail = 2;
        if (wrap2fa) wrap2fa.style.display = 'block';
        if (btn) btn.innerText = "Confirmar Código 2FA";
        mostrarMensajeUI("Código 2FA enviado a tu correo actual.", "success");
      } else {
        mostrarMensajeUI(res.message || "Error al solicitar cambio.");
      }
    } catch (e) {
      mostrarMensajeUI("Error de red al solicitar cambio de correo.");
    } finally {
      if (btn) btn.disabled = false;
    }
  } else {
    if (!code2fa || code2fa.length !== 6) {
      mostrarMensajeUI("Ingresa el código 2FA de 6 dígitos.");
      return;
    }
    if (btn) btn.disabled = true;
    try {
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
        
        mostrarMensajeUI("Correo actualizado con éxito.", "success");
        setTimeout(() => location.reload(), 1500);
      } else {
        mostrarMensajeUI(res.message || "Código incorrecto o no válido.");
      }
    } catch (e) {
      mostrarMensajeUI("Error de red al confirmar correo.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }
}

// 🟢 3. SUBMÓDULO DE CAMBIO DE CONTRASEÑA EN MI PERFIL
async function solicitarCambioPassword() {
  const p1 = document.getElementById('edit-new-pass-1')?.value.trim();
  const p2 = document.getElementById('edit-new-pass-2')?.value.trim();
  const emailActual = localStorage.getItem('user_email');
  const btn = document.getElementById('btn-action-pass');
  const wrap2fa = document.getElementById('wrap-step-pass-2fa');
  const code2fa = document.getElementById('code-pass-2fa')?.value.trim();

  if (!p1 || !p2) {
    mostrarMensajeUI("Ingresa y confirma la nueva contraseña.");
    return;
  }
  if (p1 !== p2) {
    mostrarMensajeUI("Las contraseñas no coinciden.");
    return;
  }

  if (pasoActualPass === 1) {
    if (btn) btn.disabled = true;
    try {
      const resp = await fetch('/api/auth/request-password-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailActual })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        pasoActualPass = 2;
        if (wrap2fa) wrap2fa.style.display = 'block';
        if (btn) btn.innerText = "Confirmar Cambio de Contraseña";
        mostrarMensajeUI("Código 2FA enviado a tu correo.", "success");
      } else {
        mostrarMensajeUI(res.message || "Error al solicitar cambio.");
      }
    } catch (e) {
      mostrarMensajeUI("Error de red al solicitar código 2FA.");
    } finally {
      if (btn) btn.disabled = false;
    }
  } else {
    if (!code2fa || code2fa.length !== 6) {
      mostrarMensajeUI("Ingresa el código de 6 dígitos.");
      return;
    }
    if (btn) btn.disabled = true;
    try {
      const resp = await fetch('/api/auth/confirm-password-change', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailActual, new_password: p1, code: code2fa })
      });
      const res = await resp.json();
      if (res.status === 'success') {
        mostrarMensajeUI("Contraseña actualizada correctamente.", "success");
        setTimeout(() => cerrarModal('modal-mi-perfil'), 1500);
      } else {
        mostrarMensajeUI(res.message || "Código 2FA incorrecto.");
      }
    } catch (e) {
      mostrarMensajeUI("Error de red al cambiar contraseña.");
    } finally {
      if (btn) btn.disabled = false;
    }
  }
}

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
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const res = await resp.json();
    if (res.status === 'success') {
      mostrarMensajeRegUI("Cuenta creada. Ingresando...", "success");
      const sessionResp = await fetch('/api/auth/load-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
      });
      const sessionRes = await sessionResp.json();
      if (sessionRes.status === 'success') {
        const session = {
          email,
          nombre: `${payload.nombre} ${payload.apellido}`.trim() || email,
          es_admin: false,
          avatar: `https://ui-avatars.com/api/?name=${encodeURIComponent(payload.nombre || email)}&background=0284c7&color=fff`,
          last_2fa: new Date().getTime()
        };
        localStorage.setItem('gennius_session', JSON.stringify(session));
        localStorage.setItem('user_email', email);
        inyectarBotonAdminNav(session);
        setTimeout(() => {
          const authOverlay = document.getElementById('auth-overlay');
          if (authOverlay) authOverlay.style.display = 'none';
          if (typeof window.iniciarPrecargaBackground === 'function') {
            window.iniciarPrecargaBackground();
          }
        }, 1000);
      } else {
        setTimeout(() => mostrarVistaLogin(), 2000);
      }
    } else {
      mostrarMensajeRegUI(res.message || "No se pudo completar el registro.");
    }
  } catch (e) {
    mostrarMensajeRegUI("Error de red al registrar la cuenta.");
  } finally {
    if (btn) btn.disabled = false;
  }
}

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

async function abrirMiPerfilModal() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';
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
      editFinalesChips = Array.isArray(u.destinatarios_finales) ? u.destinatarios_finales : [];
      editBccChips = Array.isArray(u.destinatarios_bcc) ? u.destinatarios_bcc : [];
      renderChips('edit-chips-finales-box', 'edit-input-finales', editFinalesChips);
      renderChips('edit-chips-bcc-box', 'edit-input-bcc', editBccChips);
      renderAvatarPicker(u.avatar || session.avatar);
    }
  } catch (e) {
    console.error("Error perfil:", e);
  }
  const modal = document.getElementById('modal-mi-perfil');
  if (modal) modal.style.display = 'flex';
}

// Variable global temporal para la selección en la modal
let avatarSeleccionadoTemp = "";

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

  // 🎨 Paleta de colores idéntica a la configuración de Python
  const bgParams = "backgroundColor[]=ff8fab&backgroundColor[]=ffb703&backgroundColor[]=4cc9a7&backgroundColor[]=4d96ff&backgroundColor[]=b57bff";
  
  // 🎭 Colección completa con tus 42 Seeds escogidas
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

  // Mapeo seguro limpiando espacios con .trim()
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

// 🟢 GUARDADO DIRECTO E INMEDIATO EN BASE DE DATOS Y NAVBAR
async function confirmarSeleccionAvatar() {
  if (!avatarSeleccionadoTemp) {
    cerrarModal('modal-selector-avatar');
    return;
  }

  const session = JSON.parse(localStorage.getItem('gennius_session') || '{}');
  const userEmail = session.email || localStorage.getItem('user_email');

  // 1. Actualizar vista previa local en la modal
  const currentImg = document.getElementById('profile-current-avatar-img');
  if (currentImg) currentImg.src = avatarSeleccionadoTemp;

  // 2. Guardar en localStorage
  session.avatar = avatarSeleccionadoTemp;
  localStorage.setItem('gennius_session', JSON.stringify(session));

  // 3. Actualizar la foto en el botón del menú superior (Navbar)
  inyectarBotonAdminNav(session);

  // 4. Enviar actualización directa a la base de datos (users_db.json)
  try {
    const resp = await fetch('/api/auth/profile/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: userEmail, avatar: avatarSeleccionadoTemp })
    });
    const res = await resp.json();
    if (res.status === 'success') {
      mostrarMensajeUI("Avatar guardado correctamente.", "success");
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
  
  // 🟢 Se quitó 'avatar' del payload para evitar sobreescrituras no deseadas
  const payload = {
    email: session.email,
    nombre: document.getElementById('edit-nombre').value,
    apellido: document.getElementById('edit-apellido').value,
    gemini_api_key: document.getElementById('edit-gemini-key').value,
    remitente: document.getElementById('edit-remitente').value,
    google_app_password: document.getElementById('edit-google-password').value,
    mi_correo: document.getElementById('edit-mi-correo').value,
    destinatarios_finales: editFinalesChips,
    destinatarios_bcc: editBccChips,
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
      mostrarMensajeUI("Perfil actualizado con éxito.", "success");
    } else {
      mostrarMensajeUI(res.message || "Error al actualizar perfil.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red actualizando perfil.");
  }
}

async function abrirModalModelosIA() {
  // 🟢 OCULTAR EL MENÚ DESPLEGABLE DEL AVATAR
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
      mostrarMensajeUI("Configuración de IA guardada con éxito.", "success");
    } else {
      mostrarMensajeUI(res.message || "Error al guardar la configuración.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red al actualizar IA.");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function abrirAdminUsuariosModal() {
  const dropdown = document.getElementById('user-dropdown-menu');
  if (dropdown) dropdown.style.display = 'none';
  const container = document.getElementById('admin-users-cards-container');
  if (container) container.innerHTML = '<div style="text-align:center; padding: 20px; color: #94a3b8;">Cargando lista de usuarios...</div>';
  document.getElementById('modal-admin-usuarios').style.display = 'flex';
  try {
    const resp = await fetch('/api/auth/admin/users');
    const data = await resp.json();
    const usuarios = Array.isArray(data) ? data : (data.users || []);
    if (container && usuarios.length > 0) {
      container.innerHTML = usuarios.map(u => `
        <div class="user-admin-card">
          <div class="user-admin-avatar">
            <img src="${u.avatar || `https://ui-avatars.com/api/?name=${encodeURIComponent(u.nombre || u.email)}&background=0284c7&color=fff`}" alt="Avatar">
          </div>
          <div class="user-admin-details">
            <span class="user-admin-name">${u.nombre || 'Sin Nombre'} ${u.apellido || ''}</span>
            <span class="user-admin-email">${u.email}</span>
            <span class="user-admin-badge ${u.es_admin ? 'admin' : 'user'}">${u.es_admin ? 'Administrador' : 'Usuario'}</span>
          </div>
          <div class="user-admin-actions">
            <button class="btn-delete-user" onclick="eliminarUsuarioAdmin('${u.email}')">Eliminar</button>
          </div>
        </div>
      `).join('');
    } else if (container) {
      container.innerHTML = '<div style="text-align:center; padding: 20px; color: #94a3b8;">No hay otras cuentas registradas.</div>';
    }
  } catch (e) {
    if (container) container.innerHTML = '<div style="text-align:center; color:#f87171; padding: 20px;">Error al cargar las cuentas.</div>';
  }
}

async function eliminarUsuarioAdmin(email) {
  if (!confirm(`¿Estás seguro de que deseas eliminar la cuenta de ${email}?`)) return;
  try {
    const resp = await fetch(`/api/auth/admin/users/${encodeURIComponent(email)}`, { method: 'DELETE' });
    const res = await resp.json();
    if (res.status === 'success') {
      mostrarMensajeUI(`Usuario ${email} eliminado.`, 'success');
      abrirAdminUsuariosModal();
    } else {
      mostrarMensajeUI(res.message || "No se pudo eliminar.");
    }
  } catch (e) {
    mostrarMensajeUI("Error de red intentando eliminar.");
  }
}

function cerrarModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.style.display = 'none';
}

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
      setTimeout(() => {
        const firstField = document.querySelector('.otp-field');
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

function guardarNuevaPasswordObligatoria() {
  const email = localStorage.getItem('temp_email');
  const newPassword = document.getElementById('new-forced-password')?.value.trim();
  if (!email || !newPassword) {
    mostrarMensajeUI("Por favor ingresa la nueva contraseña.");
    return;
  }
  fetch('/api/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, new_password: newPassword })
  })
  .then(r => r.json())
  .then(res => {
    if (res.status === 'success') {
      mostrarMensajeUI("¡Contraseña actualizada! Ya puedes ingresar.", "success");
      setTimeout(() => {
        const cardForced = document.getElementById('card-forced-pwd');
        if (cardForced) cardForced.style.display = 'none';
        mostrarLoginForm();
      }, 2000);
    } else {
      mostrarMensajeUI(res.message || "Error al actualizar.");
    }
  })
  .catch(e => mostrarMensajeUI("Error de red intentando actualizar."));
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

function inicializarChips() {
  setupChipInput('input-finales', 'chips-finales-box', destinatariosFinalesChips);
  setupChipInput('input-bcc', 'chips-bcc-box', destinatariosBccChips);
}

function setupChipInput(inputId, containerId, targetArray) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const val = input.value.replace(',', '').trim();
      if (val && !targetArray.includes(val)) {
        targetArray.push(val);
        renderChips(containerId, inputId, targetArray);
      }
      input.value = '';
    }
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

// Asegurar exposición global
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
window.togglePasswordVisibility = togglePasswordVisibility;
window.solicitarResetPassword = solicitarResetPassword;
window.ejecutarResetPassword = ejecutarResetPassword;
window.guardarNuevaPasswordObligatoria = guardarNuevaPasswordObligatoria;