// ==========================================================================
// CONFIGURACIÓN E INICIALIZACIÓN
// ==========================================================================
let SHEET_ID = "";  
let GID_HOJA = "0";
let modoEntradaTableau = "img"; // 'img' o 'manual'

async function cargarConfiguracionInicial() {
  try {
    const resp = await fetch('/api/config-sheets');
    const data = await resp.json();
    if (data.sheet_id) {
      SHEET_ID = data.sheet_id;
      GID_HOJA = data.gid_hoja || "0";
    }
  } catch (e) {
    console.error("Error cargando configuración inicial:", e);
  }
}

async function iniciarPrecargaBackground() {
  await cargarConfiguracionInicial();
  fetch('/api/init-background')
    .then(r => r.json())
    .then(bgData => console.log("Precarga completada en segundo plano:", bgData))
    .catch(err => console.warn("Alerta en precarga asíncrona:", err));
}

// Exponer función globalmente
window.iniciarPrecargaBackground = iniciarPrecargaBackground;

// ==========================================================================
// CAMBIO DE MODO DE ENTRADA TABLEAU (CAPTURA VS MANUAL)
// ==========================================================================
function cambiarModoEntrada(modo) {
  modoEntradaTableau = modo;
  const tabImg = document.getElementById('tab-mode-img');
  const tabManual = document.getElementById('tab-mode-manual');
  const panelImg = document.getElementById('panel-input-img');
  const panelManual = document.getElementById('panel-input-manual');

  if (modo === 'img') {
    if (tabImg) tabImg.classList.add('active');
    if (tabManual) tabManual.classList.remove('active');
    if (panelImg) panelImg.style.display = 'block';
    if (panelManual) panelManual.style.display = 'none';
  } else {
    if (tabManual) tabManual.classList.add('active');
    if (tabImg) tabImg.classList.remove('active');
    if (panelManual) panelManual.style.display = 'block';
    if (panelImg) panelImg.style.display = 'none';
  }
}

// MODIFICADO: Envía 'success' para colorear de verde
function copiarPromptIA() {
  const promptText = `Actúa como un extractor de datos OCR de precisión matemática. Tu única tarea es transcribir la tabla de Tableau de la imagen adjunta.

REGLAS CRÍTICAS:
1. IGNORA la columna llamada 'Grand Total' o acumulados de la derecha. Solo extrae la primera columna de valores numéricos de los bancos.
2. Formato estricto de salida: BANCO: VALOR (ejemplo: CIBC FCIB Bank: 1397685), una fila por cada banco.
3. Transcribe las cifras EXACTAMENTE como aparecen. Sin redondeos.
4. Devuelve ÚNICAMENTE la lista formateada, sin introducciones ni bloques markdown (\`\`\`).`;

  navigator.clipboard.writeText(promptText).then(() => {
    showErrorToast("📋 ¡Prompt copiado! Pégalo en ChatGPT o Gemini junto con la imagen.", "success");
  }).catch(() => {
    showErrorToast("Error al copiar el prompt al portapapeles.", "error");
  });
}

// ==========================================================================
// CONTROLADORES DE SPINNER Y NOTIFICACIONES
// ==========================================================================
function setButtonLoading(btnElement, loading) {
  if (!btnElement) return;
  const textSpan = btnElement.querySelector('.btn-text');
  const spinnerSpan = btnElement.querySelector('.btn-spinner');
  if (loading) {
    btnElement.disabled = true;
    if (textSpan) textSpan.style.display = 'none';
    if (spinnerSpan) spinnerSpan.style.display = 'inline-block';
  } else {
    btnElement.disabled = false;
    if (textSpan) textSpan.style.display = 'inline';
    if (spinnerSpan) spinnerSpan.style.display = 'none';
  }
}

// MODIFICADO: Soporta tipo 'success' o 'error'
function showErrorToast(mensajeHumano, tipo = 'error') {
  const toast = document.getElementById('md3-toast');
  const toastText = document.getElementById('md3-toast-text');
  if (toast && toastText) {
    toastText.innerText = mensajeHumano;
    
    if (tipo === 'success') {
      toast.classList.add('success');
    } else {
      toast.classList.remove('success');
    }

    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 6000);
  }
}

function renderAlertas(alertas = []) {
  let container = document.getElementById('alerts-banner-container');
  if (!container) return;
  container.innerHTML = '';
  if (!alertas || alertas.length === 0) {
    container.style.display = 'none';
    return;
  }
  const htmlAlertas = `
    <div class="card alerts-card">
      <div class="alerts-header">
        <span class="alerts-icon">⚠️</span>
        <div class="card-title text-warning">Novedades y Alertas del Corte</div>
      </div>
      <ul class="alerts-list">
        ${alertas.map(alt => `<li>${alt}</li>`).join('')}
      </ul>
    </div>
  `;
  container.innerHTML = htmlAlertas;
  container.style.display = 'block';
}

// ==========================================================================
// PREVISUALIZACIÓN DE ARCHIVOS DE ENTRADA
// ==========================================================================
function previewImage(event) {
  const input = event.target;
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = function(e) {
      const img = document.getElementById('imgPreview');
      img.src = e.target.result;
      img.style.display = 'block';
      const label = input.closest('.file-input-label');
      document.getElementById('img-label-text').innerText = input.files[0].name;
      label.classList.add('loaded');
    };
    reader.readAsDataURL(input.files[0]);
  }
}

function updateXlsLabel(event) {
  const input = event.target;
  if (input.files && input.files[0]) {
    const label = input.closest('.file-input-label');
    document.getElementById('xls-label-text').innerText = input.files[0].name;
    label.classList.add('loaded');
  }
}

async function fetchWithTimeout(resource, options = {}) {
  const { timeout = 90000 } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(resource, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (err) {
    clearTimeout(id);
    throw err;
  }
}

// ==========================================================================
// PROCESAMIENTO PRINCIPAL DE DATOS
// ==========================================================================
async function procesarInsumos() {
  const imgFile = document.getElementById('imgInput')?.files[0];
  const xlsFile = document.getElementById('xlsInput')?.files[0];
  const manualText = document.getElementById('manualTpInput')?.value.trim();
  const btn = document.getElementById('btn-process-main');

  if (!xlsFile) {
    showErrorToast("Falta el archivo de reservas (.xls).");
    return;
  }
  if (modoEntradaTableau === 'img' && !imgFile) {
    showErrorToast("Debes cargar la captura de imagen de Tableau.");
    return;
  }
  if (modoEntradaTableau === 'manual' && !manualText) {
    showErrorToast("Debes ingresar o pegar los datos manuales de TPV.");
    return;
  }

  setButtonLoading(btn, true);
  const formData = new FormData();

  if (modoEntradaTableau === 'img' && imgFile) formData.append("imagen", imgFile);
  if (modoEntradaTableau === 'manual' && manualText) formData.append("texto_manual", manualText);
  formData.append("excel", xlsFile);
  formData.append("email_usuario", localStorage.getItem('user_email') || '');

  try {
    const resp = await fetchWithTimeout('/api/procesar', {
      method: 'POST',
      body: formData,
      timeout: 120000
    });
    let res = await resp.json();

    if (resp.ok && (res.status === 'success' || res.status === 'partial_success' || res.data_total)) {
      document.getElementById('corte-title').innerText = `Resultados - Corte: ${res.label_corte || ''}`;
      
      // 1. Renderizar tabla principal editable
      renderTabla(res.data_total, res.label_corte, res.gemini_error);
      
      // 2. Renderizar minitabla ONED Global
      renderTablaONED(res.oned, res.oned_historico, res.label_corte);
      
      // 3. Mostrar secciones inferiores
      document.getElementById('results-section').style.display = 'flex';
      document.getElementById('bottom-section').style.display = 'flex';
      
      // 4. Mostrar novedades
      renderAlertas(res.alertas || []);
      
      // 5. Cargar visor de Google Sheets
      const iframe = document.getElementById('sheetsIframe');
      if (iframe) iframe.src = obtenerUrlSheetsIframe();

      window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    } else {
      showErrorToast(res.message || "Ocurrió una novedad al procesar los insumos.");
    }
  } catch (e) {
    console.error("Error al procesar:", e);
    showErrorToast("Error de comunicación con el servidor. Intenta nuevamente.");
  } finally {
    setButtonLoading(btn, false);
  }
}

// ==========================================================================
// RENDERIZADO DE TABLAS Y EDICIÓN EN TIEMPO REAL
// ==========================================================================
function renderTabla(dataTotal, labelCorte, errorGemini = false) {
  const tbody = document.querySelector('#tabla-resultados tbody');
  tbody.innerHTML = '';
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const hoy = new Date();
  document.getElementById('fecha-header-dia').innerText = `${String(hoy.getDate()).padStart(2, '0')}-${meses[hoy.getMonth()]}-${String(hoy.getFullYear()).slice(-2)}`;

  const programas = ["VLS", "CIBC", "NCB", "FC", "Cuscatlan", "Scotia", "MilesCare LifeMiles"];
  const cortes = ["630am", "1230pm", "630pm"];
  const cleanLabel = (labelCorte || '').toLowerCase().replace(":", "").replace(/\s+/g, "");

  let idxCorteActual = 2;
  if (cleanLabel.includes("630am")) idxCorteActual = 0;
  else if (cleanLabel.includes("1230pm")) idxCorteActual = 1;

  let totalTPV = { "630am": 0, "1230pm": 0, "630pm": 0 };
  let totalQ = { "630am": 0, "1230pm": 0, "630pm": 0 };

  const formatNum = (num) => (num === "?" || num === null || num === undefined) ? "?" : Math.round(num).toLocaleString('es-CO');

  programas.forEach(prg => {
    let v_tpv = [], v_q = [];
    cortes.forEach((k, idx) => {
      if (idx <= idxCorteActual) {
        const list = dataTotal ? (dataTotal[k] || []) : [];
        const coinc = list.filter(x => x.Programa && x.Programa.toLowerCase().trim().includes(prg.toLowerCase().trim()));
        
        let tpv = 0, q = 0;
        if (coinc.length > 0) {
          tpv = Math.max(...coinc.map(x => parseFloat(x.TPV || 0)));
          q = Math.max(...coinc.map(x => parseInt(x.Q_Juniper || x.Q || 0)));
        }
        
        if (errorGemini && idx === idxCorteActual && tpv === 0) {
          v_tpv.push("?");
        } else {
          v_tpv.push(formatNum(tpv));
          if (typeof tpv === 'number') totalTPV[k] += tpv;
        }
        v_q.push(q);
        totalQ[k] += q;
      } else {
        v_tpv.push(""); v_q.push("");
      }
    });

    let row1 = `
      <tr>
        <td rowspan="${prg === 'MilesCare LifeMiles' ? 1 : 2}" style="font-weight:600; vertical-align:middle; background-color:#1e293b;">${prg}</td>
        <td>TPV puntos</td>
        ${v_tpv.map((v, idx) => {
          const esEditable = (idx === idxCorteActual);
          return `<td ${esEditable ? `contenteditable="true" onblur="guardarEdicionTPV('${prg}', this.innerText, '${labelCorte}')"` : ''} class="${v === '?' ? 'gemini-error-cell' : ''} ${esEditable ? 'tpv-editable' : ''}">${v}</td>`;
        }).join('')}
      </tr>`;
    tbody.innerHTML += row1;

    if (prg !== 'MilesCare LifeMiles') {
      let row2 = `
        <tr>
          <td>Q ventas Juniper</td>
          ${v_q.map(v => `<td>${v}</td>`).join('')}
        </tr>`;
      tbody.innerHTML += row2;
    }
  });

  let rowTotalTPV = `
    <tr style="background-color: #0f172a; font-weight: bold; color: #38bdf8;">
      <td rowspan="2" style="vertical-align:middle;">Total</td>
      <td>TPV</td>
      ${cortes.map((k, idx) => `<td>${idx <= idxCorteActual ? formatNum(totalTPV[k]) : ""}</td>`).join('')}
    </tr>`;
  let rowTotalQ = `
    <tr style="background-color: #0f172a; font-weight: bold; color: #38bdf8;">
      <td>Q ventas Juniper</td>
      ${cortes.map((k, idx) => `<td>${idx <= idxCorteActual ? totalQ[k] : ""}</td>`).join('')}
    </tr>`;
  tbody.innerHTML += rowTotalTPV + rowTotalQ;
}

// GUARDA CUALQUIER EDICIÓN MANUAL HECHA SOBRE LA TABLA
async function guardarEdicionTPV(programa, valorEditado, labelCorte) {
  const valLimpio = valorEditado.replace(/\./g, '').replace(/,/g, '').replace(/\?/g, '').trim();
  const valNum = parseFloat(valLimpio) || 0.0;
  
  const cambios = {};
  cambios[programa] = valNum;

  try {
    await fetch('/api/actualizar-cache-tpv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ label_corte: labelCorte, cambios_tpv: cambios })
    });
  } catch (e) {
    console.error("Error guardando cambios de TPV:", e);
  }
}

function renderTablaONED(dataOned, onedHistorico = {}, labelCorte = "") {
  const cortes = ["630am", "1230pm", "630pm"];
  const cleanLabel = (labelCorte || '').toLowerCase().replace(":", "").replace(/\s+/g, "");
  let idxCorteActual = 2;
  if (cleanLabel.includes("630am")) idxCorteActual = 0;
  else if (cleanLabel.includes("1230pm")) idxCorteActual = 1;

  cortes.forEach((k, idx) => {
    const elTok = document.getElementById(`oned-tok-${k}`);
    const elTx = document.getElementById(`oned-tx-${k}`);
    if (!elTok || !elTx) return;

    if (idx < idxCorteActual) {
      const hist = onedHistorico[k] || {};
      elTok.innerText = hist.tokenized ? Math.round(hist.tokenized).toLocaleString('es-CO') : "--";
      elTx.innerText = hist.transaction ? Math.round(hist.transaction).toLocaleString('es-CO') : "--";
    } else if (idx === idxCorteActual) {
      const tokVal = dataOned ? dataOned.tokenized : 0;
      const txVal = dataOned ? dataOned.transaction : 0;
      elTok.innerText = tokVal > 0 ? Math.round(tokVal).toLocaleString('es-CO') : "0";
      elTx.innerText = txVal > 0 ? Math.round(txVal).toLocaleString('es-CO') : "0";
    } else {
      elTok.innerText = "";
      elTx.innerText = "";
    }
  });
}

// ==========================================================================
// GOOGLE SHEETS IFRAME
// ==========================================================================
function obtenerUrlSheetsIframe() {
  return SHEET_ID ? `https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit?rm=minimal&gid=${GID_HOJA}#gid=${GID_HOJA}` : "";
}

function refreshSheetsIframe() {
  const iframe = document.getElementById('sheetsIframe');
  if (iframe) {
    const baseUrl = obtenerUrlSheetsIframe();
    if (baseUrl) iframe.src = `${baseUrl}&_t=${new Date().getTime()}`;
  }
}

async function ejecutarAccion(endpoint, nombre, btnElement) {
  setButtonLoading(btnElement, true);
  try {
    const resp = await fetchWithTimeout(endpoint, { method: 'POST', timeout: 60000 });
    const res = await resp.json();
    if (res.status === 'error') {
      showErrorToast(res.message || "Error ejecutando acción.");
      return;
    }
    if (endpoint.includes('google-sheets')) {
      const iframe = document.getElementById('sheetsIframe');
      if (iframe) refreshSheetsIframe();
    }
  } catch (e) {
    showErrorToast("Error en la solicitud.");
  } finally {
    setButtonLoading(btnElement, false);
  }
}

async function ejecutarAccionEmail(modoFinal, btnElement) {
  setButtonLoading(btnElement, true);
  const formData = new FormData();
  formData.append("modo_final", modoFinal);
  try {
    const resp = await fetchWithTimeout('/api/enviar-email', { method: 'POST', body: formData, timeout: 60000 });
    const res = await resp.json();
    if (res.status === 'error') {
      showErrorToast(res.message || "Error al enviar el correo.");
      return;
    }
    if (res.status === 'success' && res.whatsapp_url) {
      window.open(res.whatsapp_url, '_blank');
    }
  } catch (e) {
    showErrorToast("Error de red al intentar enviar el correo.");
  } finally {
    setButtonLoading(btnElement, false);
  }
}

// EXPOSICIÓN GLOBAL DE FUNCIONES
window.cambiarModoEntrada = cambiarModoEntrada;
window.copiarPromptIA = copiarPromptIA;
window.guardarEdicionTPV = guardarEdicionTPV;
window.procesarInsumos = procesarInsumos;
window.ejecutarAccion = ejecutarAccion;
window.ejecutarAccionEmail = ejecutarAccionEmail;
window.refreshSheetsIframe = refreshSheetsIframe;
window.previewImage = previewImage;
window.updateXlsLabel = updateXlsLabel;