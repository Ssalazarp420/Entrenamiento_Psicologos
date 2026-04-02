const API = 'https://psicoia-habaesdshycpafh6.eastus2-01.azurewebsites.net';

let token = null;
let currentUser = null;
let sessionId = null;
let patientName = '';
let patientId = '';
let patientAvatar = '';
let isLoading = false;

// ── PERSISTENCIA DE SESIÓN ────────────────────────────────
// Guarda token y usuario en sessionStorage (persiste al recargar,
// se borra al cerrar el tab — más seguro que localStorage para tokens)
function saveSession() {
  sessionStorage.setItem('simpsi_token', token);
  sessionStorage.setItem('simpsi_user', JSON.stringify(currentUser));
}

function clearSession() {
  sessionStorage.removeItem('simpsi_token');
  sessionStorage.removeItem('simpsi_user');
}

function restoreSession() {
  const savedToken = sessionStorage.getItem('simpsi_token');
  const savedUser = sessionStorage.getItem('simpsi_user');
  if (!savedToken || !savedUser) return false;
  try {
    token = savedToken;
    currentUser = JSON.parse(savedUser);
    return true;
  } catch (e) {
    clearSession();
    return false;
  }
}

// ── Avatares de pacientes disponibles ─────────────────────
const PATIENT_AVATARS = [
  'Hombre_29_1.webp',
  'Mujer_25_1.webp',
  'Hombre_30_1.webp',
  'Mujer_30_1.webp',
  'Hombre_35_1.webp',
  'Mujer_30_2.webp',
  'Mujer_30_3.webp',
  'Hombre_35_2.webp',
  'Mujer_30_4.webp',
  'Hombre_50_1.webp',
  'Hombre_29_2.webp',
  'Mujer_25_2.webp',
  'Mujer_20_1.webp',
  'Mujer_22_1.webp',
  'Mujer_24_1.webp',
  'Mujer_23_1.webp',
  'Mujer_18_1.webp',
  'Mujer_19_1.webp',
  'Mujer_21_1.webp',
  'Mujer_24_2.webp'
];
const AVATAR_BASE = (() => {
  // En local (Live Server) el HTML está en /frontend/public/, raíz es el repo
  // En Azure el HTML está en la raíz del sitio
  const isLocal = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
  return isLocal ? 'public/icons/' : 'public/icons/';
})();

// Al cargar la página, intenta restaurar sesión previa
document.addEventListener('DOMContentLoaded', () => {
  if (restoreSession()) {
    setupHeader();
    routeByRole();
  }
});

window.addEventListener('beforeunload', (e) => {
  if (sessionId) {
    e.preventDefault();
    e.returnValue = 'Tienes una sesión activa. Si cierras ahora, la conversación no guardada se perderá.';
    return e.returnValue;
  }
});

// ── UTILS ─────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  const el = document.getElementById(id);
  el.classList.add('active');
  el.querySelectorAll('.anim').forEach(a => { a.style.animation = 'none'; a.offsetHeight; a.style.animation = ''; });
}

function authHeaders() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDuration(inicio, fin) {
  if (!inicio || !fin) return '—';
  const mins = Math.round((new Date(fin) - new Date(inicio)) / 60000);
  return mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

function scorePill(score) {
  if (score === null || score === undefined) return '<span style="color:var(--muted)">—</span>';
  const cls = score >= 75 ? 'score-high' : score >= 50 ? 'score-mid' : 'score-low';
  return `<span class="score-pill ${cls}">${score}/100</span>`;
}

function setNavActive(screenId) {
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.toggle('active', b.dataset.screen === screenId));
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
}

// ── LOGIN ─────────────────────────────────────────────────
async function doLogin() {
  const email = document.getElementById('login-email').value.trim();
  const pass = document.getElementById('login-password').value;
  const errEl = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');
  errEl.style.display = 'none';

  if (!email || !pass) {
    errEl.textContent = 'Completa todos los campos.';
    errEl.style.display = 'block';
    return;
  }

  btn.disabled = true; btn.textContent = 'Iniciando…';

  try {
    const body = new URLSearchParams({ username: email, password: pass });
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body
    });
    if (!res.ok) throw new Error('Credenciales incorrectas');
    const data = await res.json();

    token = data.access_token;
    currentUser = { email, rol: data.rol, nombre: data.nombre, genero: data.genero || 'otro' };
    saveSession();

    setupHeader();
    routeByRole();
  } catch (e) {
    errEl.textContent = e.message || 'Error al iniciar sesión.';
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false; btn.textContent = 'Iniciar sesión';
  }
}

function setupHeader() {
  document.getElementById('header-guest').style.display = 'none';
  document.getElementById('header-auth').style.display = 'flex';

  document.getElementById('user-initial').textContent = currentUser.nombre.charAt(0).toUpperCase();
  document.getElementById('user-name-label').textContent = currentUser.nombre;
  const rb = document.getElementById('role-badge');
  rb.textContent = currentUser.rol;
  rb.className = `role-badge role-${currentUser.rol}`;

  // Universal branding
  const logoText = document.getElementById('logo-text');
  if (logoText) logoText.innerHTML = 'Psi-<span>IA</span>';

  if (currentUser.rol === 'estudiante') {
    document.body.classList.add('student-mode');
    const greet = document.getElementById('hero-greeting');
    if (greet) greet.textContent = `Hola ${currentUser.nombre} \uD83D\uDC4B`;
    // Imagen hero según género
    const heroImg = document.getElementById('hero-student-img');
    if (heroImg) {
      heroImg.src = (currentUser.genero === 'hombre')
        ? 'https://psicologiaiassets.blob.core.windows.net/assets/Hombre_sentado_2.webp'
        : 'https://psicologiaiassets.blob.core.windows.net/assets/Mujer_sentada_2.webp';
    }
  } else {
    document.body.classList.remove('student-mode');
  }

  const tabs = document.getElementById('nav-tabs');
  tabs.innerHTML = '';

  const allTabs = {
    estudiante: [
      { id: 'screen-selection', label: 'Ir al Inicio', action: () => { resetStudentDashboard(); loadPatients(); } },
      { id: 'screen-historial', label: 'Mi historial', action: () => { showScreen('screen-historial'); loadHistorial(); } },
    ],
    docente: [
      { id: 'screen-docente', label: 'Ir al Inicio', action: () => { showScreen('screen-docente'); loadDocente(); } },
    ],
    admin: [
      { id: 'screen-admin', label: 'Panel Admin', action: () => { showScreen('screen-admin'); loadAdmin(); } },
      { id: 'screen-docente', label: 'Sesiones', action: () => { showScreen('screen-docente'); loadDocente(); } },
    ],
  };

  (allTabs[currentUser.rol] || []).forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'nav-tab';
    btn.textContent = t.label;
    btn.dataset.screen = t.id;
    btn.onclick = () => {
      confirmNavigation(() => {
        document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        t.action();
      });
    };
    tabs.appendChild(btn);
  });
}

/**
 * Intercepta la navegación si hay una sesión activa sin guardar.
 * @param {Function} callback - Acción a realizar si el usuario confirma o no hay sesión.
 */
function confirmNavigation(callback) {
  if (!sessionId) {
    callback();
    return;
  }

  // Si hay sessionId, mostramos el modal estético de advertencia
  const modal = document.getElementById('modal-warning');
  const patientSpan = document.getElementById('warn-patient-name');
  if (patientSpan) patientSpan.textContent = patientName || 'el paciente';

  const confirmBtn = document.getElementById('confirm-leave-btn');
  // Limpiar listeners previos para evitar ejecuciones múltiples
  const newConfirmBtn = confirmBtn.cloneNode(true);
  confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

  newConfirmBtn.onclick = () => {
    const sid = sessionId;
    sessionId = null; // Limpiamos para que no vuelva a saltar la advertencia
    closeAdminModal('modal-warning');
    callback();
    // Opcionalmente podrías limpiar la sesión en el servidor aquí, pero mejor dejarla 
    // para que el usuario pueda retomarla después si no le dio "terminar".
  };

  openAdminModal('modal-warning');
}

function routeByRole() {
  const firstTab = document.querySelector('.nav-tab');
  if (firstTab) firstTab.click();
}

function logout() {
  confirmNavigation(() => {
    token = null; currentUser = null; sessionId = null;
    clearSession();
    document.body.classList.remove('student-mode');
    const logoText = document.getElementById('logo-text');
    if (logoText) logoText.innerHTML = 'Sim<span>Psi</span>';
    document.getElementById('header-auth').style.display = 'none';
    document.getElementById('header-guest').style.display = 'block';
    document.getElementById('login-email').value = '';
    document.getElementById('login-password').value = '';
    showScreen('screen-login');
    // Resetear imagen hero al estado por defecto
    const heroImg = document.getElementById('hero-student-img');
    if (heroImg) heroImg.src = 'https://psicologiaiassets.blob.core.windows.net/assets/Mujer_sentada_chat_no_bubble.png';
  });
}

// ── Student selection flow helpers ────────────────────────
function resetStudentDashboard() {
  showScreen('screen-selection');
  setNavActive('screen-selection');
  const hero = document.getElementById('student-hero-section');
  if (hero) hero.style.display = 'grid';
  // Ocultar todos los contenedores del flujo
  ['step-categorias-wrap', 'step-pacientes-header', 'step-pacientes-wrap']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
}

function scrollToSelectionFlow() {
  const hero = document.getElementById('student-hero-section');
  if (hero) hero.style.display = 'none';
  // Mostrar Vista A: libro de categorías
  const b = document.getElementById('step-categorias-wrap');
  if (b) { b.style.display = 'block'; b.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  // Asegurar que Vista B esté oculta
  ['step-pacientes-header', 'step-pacientes-wrap']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
}

function closeSelectionFlow() {
  resetStudentDashboard();
}

// ═══════════════════════════════════════════════════════════
// SELECCIÓN DE PACIENTE — flujo categoría → dificultad → pacientes
// ═══════════════════════════════════════════════════════════
let allPatients = {};   // cache: { pid: {...} }
let allCategories = [];
let selectedCategoria = null;
let selectedDificultad = null;
let currentCatPage = 0;
let currentBookPatients = [];

const categoryEmojis = {
  'ansiedad': '😟', 'depresión': '😞', 'depresion': '😞', 'duelo': '🕯️',
  'estrés': '💼', 'estres': '💼', 'general': '🧠', 'autoestima': '🌱',
  'pareja': '💔', 'infantil': '🧸', 'adicciones': '🍷', 'trauma': '💔'
};

function getCategoryEmoji(cat) {
  const c = (cat || '').trim().toLowerCase();
  for (let [k, emoji] of Object.entries(categoryEmojis)) {
    if (c.includes(k)) return emoji;
  }
  return '🧠'; // Default
}

// ── Tips aleatorios (móvil del dashboard) ────────────────────────
const CLINICAL_TIPS = [
  'Escucha lo que el paciente ‘no dice’. Los silencios y pausas también son información clínica.',
  'Valida primero, interviene después. El paciente necesita sentirse comprendido antes de recibir orientación.',
  'Evita dar consejos prematuros. Explora más con preguntas abiertas antes de proponer una hipótesis.',
  'El lenguaje no verbal del paciente cuenta tanto como sus palabras. No lo ignores.',
  'Mantener una postura neutral y abierta transmite seguridad y acogida al paciente.',
  'Un buen reflejo empatítico puede cambiar el rumbo de una sesión en segundos.',
  'Recuerda diferenciar entre empatía y simpatía. La empatía conecta; la simpatía puede distanciar.',
  'Las preguntas circulares ayudan al paciente a ver sus problemáticas desde distintos ángulos.',
  'Nombra las emociones que observas: «Parece que eso te causa mucha tristeza…».',
  'No tengas prisa por llenar los silencios. A veces el paciente los necesita para procesar.',
  'Una buena alian za terapéutica es el predictor más sólido de éxito en terapia.',
  'Cuida tu propio estado emocional: el autocuidado del terapeuta impacta directamente al paciente.',
];

function refreshPhoneTip() {
  const el = document.getElementById('phone-tip-bubble');
  if (!el) return;
  const tip = CLINICAL_TIPS[Math.floor(Math.random() * CLINICAL_TIPS.length)];
  el.textContent = tip;
}

async function loadPatients() {
  selectedCategoria = null;
  selectedDificultad = null;
  document.getElementById('step-pacientes-wrap').style.display = 'none';

  //const cw = document.getElementById('step-categorias-wrap');
  //if (cw) cw.style.display = 'block';


  // In student mode, hide the flow panel until user clicks "Nuevo caso"
  const flowPanel = document.getElementById('selection-flow-panel');
  if (flowPanel) {
    if (document.body.classList.contains('student-mode')) {
      flowPanel.style.display = 'none';
    } else {
      flowPanel.style.display = 'block';
    }
  }

  loadRecentSessions(); // carga el panel lateral en paralelo
  if (document.body.classList.contains('student-mode')) {
    refreshPhoneTip();
  }

  try {
    // Carga pacientes y categorías en paralelo
    // /categorias es público para todos los roles — /admin/categorias solo admin
    const [resPat, resCats] = await Promise.all([
      fetch(`${API}/patients`, { headers: authHeaders() }),
      fetch(`${API}/categorias`, { headers: authHeaders() }),
    ]);
    const rawPatients = await resPat.json();
    // Normaliza: asegura que allPatients sea un objeto {pid: {...}}
    if (Array.isArray(rawPatients)) {
      allPatients = {};
      rawPatients.forEach(p => { allPatients[p.caso_id || p.id || p.name] = p; });
    } else {
      allPatients = rawPatients || {};
    }
    const cats = await resCats.json();
    allCategories = Array.isArray(cats) ? cats : [];
    currentCatPage = 0;
    renderCategoriesBook();
  } catch (e) {
    document.getElementById('categories-empty-state').innerHTML =
      '<span style="color:var(--red);font-size:.85rem;">⚠ Error cargando categorías</span>';
    document.getElementById('categories-empty-state').style.display = 'block';
  }
}

function renderCategoriesBook() {
  const bc = document.getElementById('categories-book');
  const bes = document.getElementById('categories-empty-state');
  if (!bc || !bes) return;

  if (!allCategories.length) {
    bc.style.display = 'none';
    bes.style.display = 'block';
    return;
  }

  bes.style.display = 'none';
  bc.style.display = 'flex';

  const ITEMS_PER_PAGE = 6;
  const totalPages = Math.ceil(allCategories.length / ITEMS_PER_PAGE);
  const startIdx = currentCatPage * ITEMS_PER_PAGE;
  const paginated = allCategories.slice(startIdx, startIdx + ITEMS_PER_PAGE);

  const leftItems = paginated.slice(0, 3);
  const rightItems = paginated.slice(3, 6);

  const generateCardHTML = (cat) => {
    const emoji = getCategoryEmoji(cat);
    const safeCat = cat.replace(/'/g, "\\'");
    return `
          <div class="book-patient-card patient-case-leve" style="border-left-color: var(--teal); cursor:pointer;" onclick="selectCategoria('${safeCat}')">
            <div class="bp-icon" style="background:var(--card); font-size:1.5rem;">${emoji}</div>
            <div class="bp-info">
              <h3>${cat}</h3>
            </div>
            <div class="bp-start">Seleccionar →</div>
          </div>`;
  };

  document.getElementById('categories-page-left').innerHTML = leftItems.map(generateCardHTML).join('');

  const rightPageHTML = rightItems.map(generateCardHTML).join('');
  const navNode = document.getElementById('categories-book-nav');
  document.getElementById('categories-page-right').innerHTML = rightPageHTML;
  if (navNode) document.getElementById('categories-page-right').appendChild(navNode);

  const prevBtn = document.getElementById('btn-cat-prev');
  const nextBtn = document.getElementById('btn-cat-next');
  const indicator = document.getElementById('cat-page-indicator');

  if (totalPages > 1) {
    navNode.style.display = 'flex';
    prevBtn.style.visibility = currentCatPage > 0 ? 'visible' : 'hidden';
    nextBtn.style.visibility = currentCatPage < totalPages - 1 ? 'visible' : 'hidden';
    indicator.textContent = `${currentCatPage + 1} / ${totalPages}`;
  } else {
    navNode.style.display = 'none';
  }
}

function changeCatPage(dir) {
  currentCatPage += dir;
  const bc = document.getElementById('categories-book');
  if (bc) {
    bc.classList.remove('book-flip');
    void bc.offsetWidth;
    bc.classList.add('book-flip');
  }
  renderCategoriesBook();
}

function selectCategoria(cat) {
  selectedCategoria = cat;
  selectedDificultad = null;
  // Ocultar Vista A
  ['step-categorias-wrap']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
  // Actualizar título de la categoría seleccionada
  const sttl = document.getElementById('selected-cat-title');
  if (sttl) {
    const emoji = getCategoryEmoji(cat);
    sttl.innerHTML = `${emoji} ${cat}`;
  }

  // Mostrar Vista B
  const h = document.getElementById('step-pacientes-header');
  const p = document.getElementById('step-pacientes-wrap');
  if (h) h.style.display = 'block';
  if (p) { p.style.display = 'block'; p.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  // Resetea botones de dificultad
  document.querySelectorAll('.filter-dif-btn').forEach(b => b.classList.remove('active'));
  const grid = document.getElementById('patients-grid-container');
  const bes = document.getElementById('patients-empty-state');
  if (grid) grid.innerHTML = '';
  if (bes) {
    bes.style.display = 'block';
    bes.innerHTML = '<div style="font-size:2rem;margin-bottom:8px">👆</div><div>Selecciona una dificultad arriba para ver los casos de <strong>' + cat + '</strong>.</div>';
  }
}

function selectDificultad(dif) {
  selectedDificultad = dif;

  document.querySelectorAll('.filter-dif-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.dif === dif));

  renderPatientCards();
}

function volverALibroCategorias() {
  // Ocultar Vista B
  ['step-pacientes-header', 'step-pacientes-wrap']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
  // Mostrar Vista A
  const b = document.getElementById('step-categorias-wrap');
  if (b) b.style.display = 'block';
}

function renderPatientCards() {
  const catNorm = (selectedCategoria || '').trim().toLowerCase();
  const difNorm = (selectedDificultad || '').trim().toLowerCase();

  currentBookPatients = Object.entries(allPatients).filter(([, p]) => {
    const pCat = (p.categoria || '').trim().toLowerCase();
    const pDif = (p.dificultad || '').trim().toLowerCase();
    if (catNorm === 'general') return pDif === difNorm;
    return pCat === catNorm && pDif === difNorm;
  });

  const grid = document.getElementById('patients-grid-container');
  const bes = document.getElementById('patients-empty-state');
  if (!grid || !bes) return;

  if (!currentBookPatients.length) {
    grid.style.display = 'none';
    bes.innerHTML = `
          <div style="font-size:2rem;margin-bottom:8px">🔍</div>
          <div>No hay casos para <strong>${selectedCategoria}</strong> — <strong>${selectedDificultad}</strong></div>
          <div style="font-size:.8rem;margin-top:6px">El administrador puede agregar casos desde el panel.</div>`;
    bes.style.display = 'block';
    return;
  }

  bes.style.display = 'none';
  grid.style.display = 'grid';

  const catColorClass = 'patient-case-' + difNorm;

  const generateGridCardHTML = ([pid, p]) => {
    const safeName = String(p.name || '').replace(/'/g, "\\'");
    const initial = safeName ? safeName.charAt(0).toUpperCase() : '?';
    const description = p.descripcion || 'Sin descripción disponible.';

    return `
          <div class="flip-card" onclick="selectPatient('${pid}','${safeName}',${p.age},this)">
            <div class="flip-card-inner">
              <div class="flip-card-front book-patient-card ${catColorClass}" style="margin:0; width:100%;">
                <div class="bp-icon" style="padding:0; overflow:hidden;">
                  ${p.avatar
        ? `<img src="${AVATAR_BASE}${p.avatar}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.style.display='none'" />`
        : initial}
                </div>
                <div class="bp-info">
                  <h3>${p.name}</h3>
                  <span class="bp-age">${p.age} años</span>
                </div>
                <div class="bp-start">→</div>
              </div>
              <div class="flip-card-back ${catColorClass}">
                <div class="back-content">
                  <h4>Descripción</h4>
                  <p>${description}</p>
                  <div class="bp-start" style="opacity:1; transform:none; margin-top:10px;">Seleccionar →</div>
                </div>
              </div>
            </div>
          </div>`;
  };

  grid.innerHTML = currentBookPatients.map(generateGridCardHTML).join('');
}

// cardEl se pasa directamente desde onclick — event.currentTarget se pierde tras el primer await
async function selectPatient(pid, name, age, cardEl) {
  if (!token) { showToast('Sesión expirada. Inicia sesión nuevamente.', true); logout(); return; }
  // Limpiar estado previo (por si venía de un chat abandonado)
  sessionId = null; isLoading = false;
  if (isLoading) return;
  isLoading = true;

  const orig = cardEl ? cardEl.innerHTML : null;
  if (cardEl) {
    cardEl.style.opacity = '0.6'; cardEl.style.pointerEvents = 'none';
    cardEl.innerHTML = `<div class="spinner" style="width:24px;height:24px;border:2px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin:20px auto;"></div><div style="color:var(--muted);font-size:.8rem;margin-top:6px;">Cargando…</div>`;
  }
  patientId = pid; patientName = name;
  patientAvatar = allPatients[pid]?.avatar || '';

  try {
    const res = await fetch(`${API}/session/new`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify({ patient_id: pid }),
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    const data = await res.json();
    if (!data.session_id) throw new Error('Sin session_id en respuesta');
    sessionId = data.session_id;

    // ── Configurar header del chat ──
    document.getElementById('card-name').textContent = `${name}, ${age} años`;
    const chatAvatarEl = document.getElementById('chat-patient-avatar');
    if (chatAvatarEl) {
      if (patientAvatar) {
        const img = document.createElement('img');
        img.src = AVATAR_BASE + patientAvatar;
        img.alt = patientName;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;';
        img.onerror = () => { chatAvatarEl.textContent = patientName.charAt(0).toUpperCase(); };
        chatAvatarEl.innerHTML = '';
        chatAvatarEl.appendChild(img);
      } else {
        chatAvatarEl.textContent = patientName.charAt(0).toUpperCase();
      }
    }

    const chatBox = document.getElementById('chat-box');

    if (data.resumed) {
      // ── Sesión previa activa: cargar historial existente ──
      chatBox.innerHTML = '';
      const history = data.history || [];
      if (history.length === 0) {
        chatBox.innerHTML = `<div class="empty-state" id="empty-msg"><div class="icon">🛋️</div><span>Continúa tu sesión con ${name}. Escribe tu siguiente intervención.</span></div>`;
      } else {
        history.forEach(m => { if (m && m.text && m.role) appendMsg(m.role, m.text); });
      }
      // Mostrar botón "Ver análisis" si ya hay transcripción
      const ab = document.getElementById('analyze-btn'); if (ab) ab.style.display = history.length ? '' : 'none';
      showToast(`↩ Retomando sesión previa con ${name}`);
    } else {
      // ── Sesión nueva ──
      chatBox.innerHTML = `<div class="empty-state" id="empty-msg"><div class="icon">🛋️</div><span>Escribe tu primera intervención para iniciar la sesión con ${name}.</span></div>`;
      const ab = document.getElementById('analyze-btn'); if (ab) { ab.style.display = 'none'; }
    }

    // Ocultar/resetear botón alta
    const hb = document.getElementById('alta-btn'); if (hb) { hb.style.display = 'none'; delete hb.dataset.shown; }
    _checkAltaCount = 0;
    showScreen('screen-chat'); setNavActive('screen-selection');
    document.getElementById('user-input').disabled = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('end-btn').disabled = false;
    document.getElementById('user-input').focus();
  } catch (e) {
    if (cardEl && orig !== null) { cardEl.style.opacity = '1'; cardEl.style.pointerEvents = 'auto'; cardEl.innerHTML = orig; }
    let msg = 'Error al conectar. Intenta de nuevo.';
    if (e.name === 'TimeoutError' || e.name === 'AbortError') msg = 'El servidor tardó demasiado.';
    else if (e.message.includes('401')) { showToast('Sesión expirada.', true); logout(); return; }
    showToast(msg, true);
  } finally { isLoading = false; }
}

// \u2500\u2500 Retroalimentaciones del docente (vista estudiante) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
async function openRetroModal() {
  const overlay = document.getElementById('modal-retro');
  if (overlay) overlay.style.display = 'flex';
  const list = document.getElementById('retro-list');
  if (!list) return;
  list.innerHTML = '<div class="spinner" style="margin:32px auto;"></div>';
  try {
    const res = await fetch(`${API}/estudiante/retroalimentaciones`, { headers: authHeaders() });
    const items = await res.json();
    if (!items.length) {
      list.innerHTML = '<div class="ov-empty" style="padding:32px">Aún no tienes retroalimentaciones de ningún docente.</div>';
      return;
    }
    list.innerHTML = items.map(r => `
      <div class="retro-item">
        <div class="retro-sesion">Sesión: ${r.sesion_id?.slice(0, 8)}… · ${formatDate(r.creado_en)}</div>
        <div class="retro-comentario">${r.comentario}</div>
        <div class="retro-docente">— ${r.docente_email}</div>
      </div>`).join('');
  } catch (e) {
    list.innerHTML = '<div class="ov-empty" style="color:var(--red)">Error cargando retroalimentaciones.</div>';
  }
}

function closeRetroModal() {
  const overlay = document.getElementById('modal-retro');
  if (overlay) overlay.style.display = 'none';
}

// \u2500\u2500 Panel de sesiones recientes \u2014 dual mode (student light / dark) \u2500\u2500\u2500\u2500
async function loadRecentSessions() {
  // Student mode renders into hero-right panel; other roles use old dark panel
  const heroContainer = document.getElementById('recent-sessions-hero');
  const oldContainer = document.getElementById('recent-sessions-list');
  const isStudent = document.body.classList.contains('student-mode');
  const container = isStudent ? heroContainer : oldContainer;
  if (!container) return;

  try {
    const [resSes, resPat] = await Promise.all([
      fetch(`${API}/historial/mis-sesiones`, { headers: authHeaders() }),
      fetch(`${API}/patients`, { headers: authHeaders() }),
    ]);
    const sesiones = await resSes.json();
    const rawPat = await resPat.json();
    const pats = Array.isArray(rawPat) ? Object.fromEntries(rawPat.map(p => [p.caso_id || p.id, p])) : rawPat;

    const recent = (Array.isArray(sesiones) ? sesiones : [])
      .filter(s => !s.alta)
      /* === LIMITE DE CHATS VISIBLES === 
         Cambia el 3 por 2 o 4 para ver mas o menos sesiones en el panel lateral */
      .slice(0, 3);

    if (!recent.length) {
      container.innerHTML = isStudent
        ? '<div class="rcn-empty">Aún no tienes sesiones<br>guardadas aquí.</div>'
        : '<div class="recent-empty">Aún no tienes sesiones guardadas.</div>';
      return;
    }

    if (isStudent) {
      // ── New colorful light cards ────────────────────────────────────────
      const colorClasses = ['color-0', 'color-1', 'color-2'];
      container.innerHTML = recent.map((s, idx) => {
        const p = pats[s.patient_id] || {};
        const cat = p.categoria || '—';
        const dif = (p.dificultad || '').toLowerCase();
        const difCls = dif === 'leve' ? 'rcn-tag-leve' : dif === 'moderada' ? 'rcn-tag-mod' : dif === 'severa' ? 'rcn-tag-sev' : '';
        const colorCls = colorClasses[idx % colorClasses.length];
        const initial = (s.patient_name || '?').charAt(0).toUpperCase();
        const safeName = (s.patient_name || '').replace(/'/g, "\\'");
        return `
          <div class="recent-card-new ${colorCls}" onclick="reanudarSesion('${s.sesion_id}','${safeName}')">
            <div class="rcn-header">
              <div class="rcn-avatar" style="padding:0;overflow:hidden;">${p.avatar
            ? `<img src="${AVATAR_BASE}${p.avatar}" alt="${s.patient_name}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.parentElement.textContent='${initial}'" />`
            : initial}</div>
              <span class="rcn-name">${s.patient_name || '—'}</span>
            </div>
            <div class="rcn-date">${formatDate(s.inicio)}</div>
            <div class="rcn-tags">
              <span class="rcn-tag rcn-tag-cat">${cat}</span>
              ${dif ? `<span class="rcn-tag ${difCls}">${p.dificultad || dif}</span>` : ''}
              ${s.puntuacion == null
            ? '<span class="rcn-tag" style="background:rgba(251,191,36,.15);color:#b45309;">Sin analizar</span>'
            : `<span class="rcn-tag" style="background:rgba(5,150,105,.15);color:#059669;">${s.puntuacion}/100</span>`}
            </div>
          </div>`;
      }).join('');
    } else {
      // ── Original dark cards (unchanged for admin/docente) ───────────────
      container.innerHTML = recent.map(s => {
        const p = pats[s.patient_id] || {};
        const cat = p.categoria || '—';
        const dif = (p.dificultad || '').toLowerCase();
        const nSes = s.numero_sesion ? `Sesión #${s.numero_sesion}` : '';
        const difCls = dif === 'leve' ? 'rc-tag-leve' : dif === 'moderada' ? 'rc-tag-moderada' : dif === 'severa' ? 'rc-tag-severa' : '';
        const safeName = (s.patient_name || '').replace(/'/g, "\\'");
        return `
          <div class="recent-card" onclick="reanudarSesion('${s.sesion_id}','${safeName}')">
            <div class="recent-card-name"><span style="font-size:1.1rem;">👤</span>${s.patient_name || '—'}</div>
            <div class="recent-card-meta">${formatDate(s.inicio)}</div>
            <div class="recent-card-tags">
              <span class="rc-tag rc-tag-cat">${cat}</span>
              ${dif ? `<span class="rc-tag ${difCls}">${p.dificultad || dif}</span>` : ''}
              ${nSes ? `<span class="rc-tag rc-tag-sesion">${nSes}</span>` : ''}
              ${s.puntuacion == null ? '<span class="rc-tag" style="background:rgba(251,191,36,.1);color:#d97706;">Sin analizar</span>' : `<span class="rc-tag" style="background:rgba(52,211,153,.1);color:var(--green);">${s.puntuacion}/100</span>`}
            </div>
          </div>`;
      }).join('');
    }
  } catch (e) {
    if (container) container.innerHTML = isStudent
      ? '<div class="rcn-empty">No se pudieron cargar las sesiones.</div>'
      : '<div class="recent-empty">No se pudieron cargar.</div>';
  }
}

// ═══════════════════════════════════════════════════════════
// HISTORIAL — con botón eliminar
// ═══════════════════════════════════════════════════════════
let historialSeleccionadas = new Set();

async function loadHistorial() {
  const tbody = document.getElementById('historial-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="empty-table"><div class="spinner" style="margin:0 auto;"></div></td></tr>';
  try {
    const res = await fetch(`${API}/historial/mis-sesiones`, { headers: authHeaders() });
    const data = await res.json();
    historialSeleccionadas = new Set();
    const selectAll = document.getElementById('hist-select-all');
    if (selectAll) selectAll.checked = false;
    actualizarBotonEliminarSeleccionadas();
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-table">No tienes sesiones completadas aún.</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(s => {
      const p = allPatients[s.patient_id] || {};
      const initial = (s.patient_name || '?').charAt(0).toUpperCase();
      const patientAvatar = p.avatar ? `${AVATAR_BASE}${p.avatar}` : null;
      const safePatientName = (s.patient_name || '').replace(/'/g, "\\'");
      const scoreClass = s.puntuacion != null ? 'hist-score' : 'hist-score-empty';
      const scoreText = s.puntuacion != null ? s.puntuacion : '—';
      const status = (s.estado || 'activa').toLowerCase();

      return `
      <tr data-sid="${s.sesion_id}">
        <td style="text-align:center;">
          <input type="checkbox" class="hist-check" data-sid="${s.sesion_id}"
            onclick="toggleHistSelect(this,'${s.sesion_id}')">
        </td>
        <td>
          <div class="hist-patient-cell">
            <div class="hist-avatar">
              ${patientAvatar
          ? `<img src="${patientAvatar}" alt="${s.patient_name}" onerror="this.parentElement.innerHTML='${initial}'" />`
          : initial}
            </div>
            <strong>${s.patient_name || '—'}</strong>
          </div>
        </td>
        <td>
          <div class="hist-date-box">
            <span class="hist-date-main">${formatDate(s.inicio)}</span>
          </div>
        </td>
        <td style="color:var(--muted); font-size:.85rem;">${formatDuration(s.inicio, s.fin)}</td>
        <td>
          <div class="${scoreClass}">${scoreText}${s.puntuacion != null ? '<small>/100</small>' : ''}</div>
        </td>
        <td>
          <span class="status-pill status-${status}">${status}</span>
        </td>
        <td>
          <div class="hist-actions">
            <button class="btn-accent" style="padding:6px 12px; font-size:.78rem;"
              onclick="reanudarSesion('${s.sesion_id}','${safePatientName}')">
              ↩ Retomar
            </button>
            <button class="btn-ghost" style="padding:6px 12px; font-size:.78rem;"
              onclick="loadDetalle('${s.sesion_id}')">Detalles</button>
            <button class="btn-ghost-danger" style="padding:4px 8px; font-size:1rem; min-width:36px; display:flex; align-items:center; justify-content:center;"
              onclick="eliminarSesion('${s.sesion_id}', this)">🗑</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-table" style="color:var(--red)">Error cargando historial.</td></tr>';
  }
}

async function eliminarSesion(sesionId, btn) {
  showConfirmModal({
    title: '¿Eliminar sesión?',
    msg: 'Se borrará completamente incluyendo el análisis y las retroalimentaciones. Esta acción <strong>no se puede deshacer</strong>.',
    icon: '🗑️',
    confirmText: 'Sí, eliminar',
    onConfirm: async () => {
      btn.disabled = true; btn.textContent = '…';
      try {
        const res = await fetch(`${API}/historial/sesion/${sesionId}`, {
          method: 'DELETE', headers: authHeaders()
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        showToast('Sesión eliminada');
        if (historialSeleccionadas.has(sesionId)) {
          historialSeleccionadas.delete(sesionId);
          actualizarBotonEliminarSeleccionadas();
        }
        loadHistorial();
      } catch (e) {
        showToast('Error al eliminar: ' + e.message, true);
        btn.disabled = false; btn.textContent = '🗑';
      }
    }
  });
}

function toggleHistSelect(checkbox, sesionId) {
  if (checkbox.checked) historialSeleccionadas.add(sesionId);
  else historialSeleccionadas.delete(sesionId);
  actualizarBotonEliminarSeleccionadas();
}

function toggleHistSelectAll(master) {
  const checks = document.querySelectorAll('#historial-tbody .hist-check');
  historialSeleccionadas = new Set();
  checks.forEach(ch => {
    ch.checked = master.checked;
    if (master.checked && ch.dataset.sid) historialSeleccionadas.add(ch.dataset.sid);
  });
  actualizarBotonEliminarSeleccionadas();
}

function actualizarBotonEliminarSeleccionadas() {
  const btn = document.getElementById('btn-delete-selected');
  if (!btn) return;
  const count = historialSeleccionadas.size;
  btn.disabled = count === 0;
  btn.textContent = count > 0 ? `Eliminar seleccionadas (${count})` : 'Eliminar seleccionadas';
}

async function eliminarSesionesSeleccionadas() {
  const ids = Array.from(historialSeleccionadas);
  if (!ids.length) return;

  showConfirmModal({
    title: `¿Eliminar ${ids.length} sesiones?`,
    msg: `Se borrarán completamente ${ids.length} sesiones incluyendo sus análisis y retroalimentaciones. <strong>Esta acción no se puede deshacer</strong>.`,
    icon: '🗑️',
    confirmText: `Eliminar ${ids.length} sesiones`,
    onConfirm: async () => {
      let ok = 0, fail = 0;
      for (const sid of ids) {
        try {
          const res = await fetch(`${API}/historial/sesion/${sid}`, {
            method: 'DELETE', headers: authHeaders()
          });
          if (res.ok) ok++;
          else fail++;
        } catch (e) {
          fail++;
        }
      }
      showToast(`Sesiones eliminadas: ${ok}${fail ? ` · Errores: ${fail}` : ''}`);
      historialSeleccionadas = new Set();
      const selectAll = document.getElementById('hist-select-all');
      if (selectAll) selectAll.checked = false;
      actualizarBotonEliminarSeleccionadas();
      loadHistorial();
    }
  });
}

async function reanudarSesion(sesionId, patientNameFromList) {
  try {
    const res = await fetch(`${API}/session/resume/${sesionId}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = data.detail || `Error ${res.status}`;
      showToast('No se pudo reanudar la sesión: ' + msg, true);
      return;
    }

    sessionId = data.session_id;
    patientId = data.patient.id;
    patientName = data.patient.name || patientNameFromList || 'Paciente';
    patientAvatar = allPatients[patientId]?.avatar || '';
    const chatAvatarEl = document.getElementById('chat-patient-avatar');
    if (chatAvatarEl) {
      if (patientAvatar) {
        const img = document.createElement('img');
        img.src = AVATAR_BASE + patientAvatar;
        img.alt = patientName;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;border-radius:50%;';
        img.onerror = () => { chatAvatarEl.textContent = patientName.charAt(0).toUpperCase(); };
        chatAvatarEl.innerHTML = '';
        chatAvatarEl.appendChild(img);
      } else {
        chatAvatarEl.textContent = patientName.charAt(0).toUpperCase();
      }
    }

    const cardTitle = document.getElementById('card-name');
    if (cardTitle) cardTitle.textContent = `${patientName}, ${data.patient.age} años`;
    const emptyLabel = document.getElementById('empty-label');
    if (emptyLabel) emptyLabel.textContent = `Continúa la sesión con ${patientName}.`;

    const chatBox = document.getElementById('chat-box');
    if (chatBox) {
      chatBox.innerHTML = '';
      (data.history || []).forEach(m => {
        if (m && m.text && m.role) appendMsg(m.role, m.text);
      });
    }

    showScreen('screen-chat');
    setNavActive('screen-selection');
    document.getElementById('user-input').disabled = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('end-btn').disabled = false;
    // Mostrar "Ver análisis IA" porque la sesión tiene transcripción guardada
    const ab = document.getElementById('analyze-btn'); if (ab) ab.style.display = '';
    _checkAltaCount = 0;
    document.getElementById('user-input').focus();
  } catch (e) {
    showToast('No se pudo reanudar la sesión', true);
  }
}

// ═══════════════════════════════════════════════════════════
// PANEL DOCENTE — grupos, estudiantes, retroalimentaciones
// ═══════════════════════════════════════════════════════════
let docenteGrupoActual = null;  // { id, nombre, estudiantes[] }

async function loadDocente() {
  document.getElementById('docente-grupo-detail').style.display = 'none';
  document.getElementById('docente-grupos-wrap').style.display = 'grid';
  const wrap = document.getElementById('docente-grupos-wrap');
  wrap.innerHTML = '<div style="grid-column:1/-1"><div class="spinner" style="margin:0 auto;"></div></div>';
  try {
    const res = await fetch(`${API}/docente/mis-grupos`, { headers: authHeaders() });
    const grupos = await res.json();
    if (!grupos.length) {
      wrap.innerHTML = `<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--muted);
        background:var(--card);border:1px dashed var(--border);border-radius:14px;">
        <div style="font-size:2rem;margin-bottom:8px">👥</div>
        <div>No tienes grupos creados aún.</div>
        <div style="font-size:.8rem;margin-top:6px">Haz clic en "+ Nuevo grupo" para comenzar.</div>
      </div>`;
      return;
    }
    wrap.innerHTML = grupos.map(g => `
      <div class="grupo-card">
        <div class="grupo-card-nombre" style="cursor:pointer" onclick="abrirGrupoDocente('${g.id}')">👥 ${g.nombre}</div>
        <div class="grupo-card-meta" style="cursor:pointer" onclick="abrirGrupoDocente('${g.id}')">${(g.estudiantes || []).length} estudiantes · Creado ${formatDate(g.creado_en)}</div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:4px;">
          <span class="inst-pill inst-pill-plan">${g.institucion_id ? 'Institucional' : 'Independiente'}</span>
          <button class="btn-danger" style="padding:4px 10px;font-size:.75rem;"
            onclick="eliminarGrupoDocente('${g.id}','${g.nombre.replace(/'/g, "&apos;")}')">
            🗑 Eliminar
          </button>
        </div>
      </div>`).join('');
  } catch (e) {
    wrap.innerHTML = '<div style="grid-column:1/-1" class="ov-empty" style="color:var(--red)">Error cargando grupos.</div>';
  }
}

async function abrirGrupoDocente(grupoId) {
  // Carga el grupo fresco desde el backend — evita problemas con JSON inline
  try {
    const res = await fetch(`${API}/docente/mis-grupos`, { headers: authHeaders() });
    const todos = await res.json();
    const grupo = todos.find(g => g.id === grupoId);
    if (!grupo) { showToast('Grupo no encontrado', true); return; }

    docenteGrupoActual = { id: grupo.id, nombre: grupo.nombre, estudiantes: grupo.estudiantes || [] };
    document.getElementById('docente-grupos-wrap').style.display = 'none';
    document.getElementById('docente-grupo-detail').style.display = 'block';
    document.getElementById('dg-nombre').textContent = grupo.nombre;
    document.getElementById('dg-sub').textContent = `${docenteGrupoActual.estudiantes.length} estudiantes en este grupo`;
    await cargarEstudiantesGrupo(grupo.id, docenteGrupoActual.estudiantes);
  } catch (e) {
    showToast('Error al abrir el grupo: ' + e.message, true);
  }
}

async function eliminarGrupoDocente(grupoId, nombre) {
  showConfirmModal({
    title: '¿Eliminar grupo?',
    msg: `¿Estás seguro de eliminar el grupo "<strong>${nombre}</strong>"? Los estudiantes no se borrarán, solo la asociación al grupo.`,
    icon: '📂',
    confirmText: 'Sí, eliminar grupo',
    onConfirm: async () => {
      try {
        const res = await fetch(`${API}/docente/grupos/${grupoId}`, {
          method: 'DELETE', headers: authHeaders(),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `Error ${res.status}`);
        }
        showToast(`Grupo "${nombre}" eliminado`);
        await loadDocente();
      } catch (e) { showToast('Error: ' + e.message, true); }
    }
  });
}

function cerrarGrupoDetail() {
  document.getElementById('docente-grupo-detail').style.display = 'none';
  document.getElementById('docente-grupos-wrap').style.display = 'grid';
  docenteGrupoActual = null;
}

async function cargarEstudiantesGrupo(grupoId, emails) {
  const tbody = document.getElementById('dg-estudiantes-tbody');
  if (!emails.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-table">Sin estudiantes aún. Agrégalos por email arriba.</td></tr>';
    return;
  }
  tbody.innerHTML = '<tr><td colspan="5" class="empty-table"><div class="spinner" style="margin:0 auto;"></div></td></tr>';
  try {
    const res = await fetch(`${API}/docente/grupo/${grupoId}/sesiones`, { headers: authHeaders() });
    const sesiones = await res.json();

    // Agrupa sesiones por estudiante
    const porEst = {};
    sesiones.forEach(s => {
      if (!porEst[s.usuario_id]) porEst[s.usuario_id] = [];
      porEst[s.usuario_id].push(s);
    });

    tbody.innerHTML = emails.map(email => {
      const ses = porEst[email] || [];
      const ultima = ses[0];
      const name = email.split('@')[0];
      const initial = name.charAt(0).toUpperCase();

      return `<tr>
        <td>
          <div class="hist-patient-cell">
            <div class="hist-avatar">${initial}</div>
            <strong>${name}</strong>
          </div>
        </td>
        <td style="font-size:.8rem;color:var(--muted)">${email}</td>
        <td style="text-align:center; font-weight:600;">${ses.length}</td>
        <td>
          ${ultima?.puntuacion != null
          ? `<div class="hist-score">${ultima.puntuacion}<small>/100</small></div>`
          : '<span class="hist-score-empty">—</span>'}
        </td>
        <td>
          <div class="hist-actions">
            <button class="btn-ghost" style="padding:6px 12px; font-size:.78rem;"
              onclick="verSesionesEstudiante('${email}', '${name}')">Ver sesiones</button>
            <button class="btn-ghost-danger" style="padding:4px 8px; font-size:1rem; min-width:36px; display:flex; align-items:center; justify-content:center;"
              onclick="quitarEstudianteGrupo('${email}')">🗑</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-table" style="color:var(--red)">Error cargando sesiones.</td></tr>';
  }
}

async function docenteAgregarEstudiante() {
  if (!docenteGrupoActual) return;
  const email = document.getElementById('dg-add-email').value.trim();
  if (!email) return;
  try {
    const res = await fetch(`${API}/docente/grupos/${docenteGrupoActual.id}/agregar-estudiante`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${res.status}`);
    }
    document.getElementById('dg-add-email').value = '';
    if (!docenteGrupoActual.estudiantes.includes(email))
      docenteGrupoActual.estudiantes.push(email);
    document.getElementById('dg-sub').textContent = `${docenteGrupoActual.estudiantes.length} estudiantes en este grupo`;
    await cargarEstudiantesGrupo(docenteGrupoActual.id, docenteGrupoActual.estudiantes);
    showToast(`${email} agregado al grupo ✓`);
  } catch (e) { showToast('Error: ' + e.message, true); }
}

async function quitarEstudianteGrupo(email) {
  if (!docenteGrupoActual) return;
  showConfirmModal({
    title: '¿Quitar estudiante?',
    msg: `¿Estás seguro de quitar a <strong>${email}</strong> de este grupo?`,
    icon: '👤',
    confirmText: 'Quitar del grupo',
    onConfirm: async () => {
      try {
        const res = await fetch(`${API}/docente/grupos/${docenteGrupoActual.id}/quitar-estudiante`, {
          method: 'POST', headers: authHeaders(), body: JSON.stringify({ email }),
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        docenteGrupoActual.estudiantes = docenteGrupoActual.estudiantes.filter(e => e !== email);
        document.getElementById('dg-sub').textContent = `${docenteGrupoActual.estudiantes.length} estudiantes en este grupo`;
        await cargarEstudiantesGrupo(docenteGrupoActual.id, docenteGrupoActual.estudiantes);
        showToast('Estudiante quitado del grupo');
      } catch (e) { showToast('Error: ' + e.message, true); }
    }
  });
}

// ── Ver sesiones de un estudiante (modal) ────────────────
let retroSesionActual = null;
let retroEstudianteActual = null;

async function verSesionesEstudiante(email, nombre) {
  retroEstudianteActual = { email, nombre };
  document.getElementById('modal-ses-nombre').textContent = nombre;
  openAdminModal('modal-docente-sesiones');
  const list = document.getElementById('modal-ses-list');
  list.innerHTML = '<div class="spinner" style="margin:32px auto;"></div>';
  try {
    const res = await fetch(`${API}/docente/grupo/${docenteGrupoActual.id}/sesiones`, { headers: authHeaders() });
    const all = await res.json();
    const ses = all.filter(s => s.usuario_id === email);
    if (!ses.length) {
      list.innerHTML = '<div class="ov-empty">Este estudiante no tiene sesiones completadas.</div>';
      return;
    }
    list.innerHTML = `<div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Paciente</th>
          <th>Fecha</th>
          <th>Duración</th>
          <th style="text-align:center;">Puntuación</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${ses.map(s => `<tr>
          <td>
            <div class="hist-patient-cell">
              <strong>${s.patient_name || '—'}</strong>
            </div>
          </td>
          <td style="font-size:.85rem;color:var(--muted);">${formatDate(s.inicio)}</td>
          <td style="font-size:.8rem;color:var(--muted);">${formatDuration(s.inicio, s.fin)}</td>
          <td>
            <div style="display:flex; justify-content:center;">
              ${s.puntuacion != null
        ? `<div class="hist-score">${s.puntuacion}<small>/100</small></div>`
        : '<span class="hist-score-empty">—</span>'}
            </div>
          </td>
          <td>
            <div class="hist-actions">
              <button class="btn-accent" style="padding:6px 12px; font-size:.78rem;"
                onclick="abrirEscribirRetro('${s.sesion_id}','${(s.patient_name || '').replace(/'/g, "\\'")}')">
                ✏️ Comentar
              </button>
            </div>
          </td>
        </tr>`).join('')}
      </tbody>
    </table></div>`;
  } catch (e) {
    list.innerHTML = '<div class="ov-empty" style="color:var(--red)">Error cargando sesiones.</div>';
  }
}

function abrirEscribirRetro(sesionId, pacienteNombre) {
  retroSesionActual = sesionId;
  document.getElementById('retro-est-nombre').textContent =
    `${retroEstudianteActual?.nombre || '—'} (${pacienteNombre})`;
  document.getElementById('retro-comentario').value = '';
  openAdminModal('modal-escribir-retro');
}

async function guardarRetroalimentacion() {
  const comentario = document.getElementById('retro-comentario').value.trim();
  if (!comentario) { showToast('Escribe un comentario antes de enviar', true); return; }
  const btn = document.querySelector('#modal-escribir-retro .btn-accent');
  if (btn) { btn.disabled = true; btn.textContent = 'Enviando…'; }
  try {
    const res = await fetch(`${API}/docente/retroalimentacion`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({
        sesion_id: retroSesionActual,
        estudiante_email: retroEstudianteActual.email,
        comentario,
      }),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    closeAdminModal('modal-escribir-retro');
    showToast('Retroalimentación enviada ✓');
  } catch (e) {
    showToast('Error: ' + e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Enviar retroalimentación'; }
  }
}

function openCrearGrupoModal() {
  document.getElementById('ng-nombre').value = '';
  openAdminModal('modal-crear-grupo');
}

async function docenteCrearGrupo() {
  const nombre = document.getElementById('ng-nombre').value.trim();
  if (!nombre) { showToast('El nombre es requerido', true); return; }
  try {
    const res = await fetch(`${API}/docente/grupos`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ nombre }),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    closeAdminModal('modal-crear-grupo');
    showToast(`Grupo "${nombre}" creado ✓`);
    await loadDocente();
  } catch (e) { showToast('Error: ' + e.message, true); }
}

// ── CHAT ──────────────────────────────────────────────────

function appendMsg(role, text) {
  const empty = document.getElementById('empty-msg');
  if (empty) empty.remove();
  const chatBox = document.getElementById('chat-box');
  const msg = document.createElement('div');
  msg.className = `msg ${role === 'patient' ? 'patient' : role}`;
  const formatted = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  if (role === 'sistema') {
    msg.innerHTML = `<div style="width:100%;text-align:center;font-size:.78rem;color:var(--muted);padding:4px 0;">${formatted}</div>`;
  } else {
    const isPatient = role === 'patient';
    msg.innerHTML = `
      <div class="msg-avatar">${isPatient && patientAvatar
        ? `<img src="${AVATAR_BASE}${patientAvatar}" alt="${patientName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.outerHTML='${patientName.charAt(0)}'" />`
        : isPatient ? patientName.charAt(0) : currentUser.nombre.charAt(0).toUpperCase()}</div>
      <div>
        <div class="msg-name">${isPatient ? patientName : currentUser.nombre}</div>
        <div class="msg-bubble">${formatted}</div>
      </div>`;
  }
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping() {
  const chatBox = document.getElementById('chat-box');
  const t = document.createElement('div');
  t.className = 'msg patient'; t.id = 'typing-indicator';
  t.innerHTML = `
    <div class="msg-avatar">${patientAvatar
      ? `<img src="${AVATAR_BASE}${patientAvatar}" alt="${patientName}" style="width:100%;height:100%;object-fit:cover;border-radius:50%;" onerror="this.outerHTML='${patientName.charAt(0)}'" />`
      : patientName.charAt(0)}</div>
    <div>
      <div class="msg-name">${patientName}</div>
      <div class="msg-bubble typing">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
      </div>
    </div>`;
  chatBox.appendChild(t);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
  const t = document.getElementById('typing-indicator');
  if (t) t.remove();
}

async function sendMessage() {
  if (!sessionId || isLoading) return;
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text) return;

  isLoading = true;
  document.getElementById('send-btn').disabled = true;
  document.getElementById('end-btn').disabled = true;
  input.value = '';
  appendMsg('psi', text);
  showTyping();

  try {
    const res = await fetch(`${API}/chat`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ session_id: sessionId, message: text }),
      signal: AbortSignal.timeout(30000),
    });
    const data = await res.json();
    removeTyping();
    appendMsg('patient', data.reply);
    maybeCheckAlta();
  } catch (e) {
    removeTyping();
    appendMsg('sistema', (e.name === 'TimeoutError' || e.name === 'AbortError')
      ? '⚠ El paciente tardó demasiado. Intenta de nuevo.'
      : '⚠ Error al contactar el servidor.');
  } finally {
    isLoading = false;
    document.getElementById('send-btn').disabled = false;
    document.getElementById('end-btn').disabled = false;
    input.focus();
  }
}

// ── check-alta counter ────────────────────────────────────
let _checkAltaCount = 0;

async function maybeCheckAlta() {
  if (!sessionId) return;
  _checkAltaCount++;
  if (_checkAltaCount % 3 !== 0) return;
  try {
    const res = await fetch(`${API}/session/check-alta`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ session_id: sessionId }),
      signal: AbortSignal.timeout(20000),
    });
    if (!res.ok) return;
    const data = await res.json();
    const hb = document.getElementById('alta-btn');
    if (data.sugerir_alta && hb) {
      hb.style.display = '';
      if (hb.dataset.shown !== '1') {
        hb.dataset.shown = '1';
        appendMsg('sistema', `🎯 ${data.mensaje}`);
      }
    }
  } catch (_) { }
}

/**
 * Muestra un modal de confirmación estético personalizado.
 * @param {Object} options - { title, msg, icon, onConfirm, onCancel, confirmText }
 */
function showConfirmModal(options) {
  const modal = document.getElementById('modal-confirm');
  if (!modal) return;

  document.getElementById('confirm-title').textContent = options.title || '¿Estás seguro?';
  document.getElementById('confirm-msg').innerHTML = options.msg || '';
  document.getElementById('confirm-icon').textContent = options.icon || '❓';

  const yesBtn = document.getElementById('confirm-yes-btn');
  const noBtn = document.getElementById('confirm-no-btn');

  yesBtn.textContent = options.confirmText || 'Sí, continuar';

  // Limpiar listeners antiguos usando clonación
  const newYes = yesBtn.cloneNode(true);
  const newNo = noBtn.cloneNode(true);
  yesBtn.parentNode.replaceChild(newYes, yesBtn);
  noBtn.parentNode.replaceChild(newNo, noBtn);

  newYes.onclick = () => {
    closeAdminModal('modal-confirm');
    if (options.onConfirm) options.onConfirm();
  };

  newNo.onclick = () => {
    closeAdminModal('modal-confirm');
    if (options.onCancel) options.onCancel();
  };

  openAdminModal('modal-confirm');
}

async function endSession() {
  if (!sessionId || isLoading) return;

  showConfirmModal({
    title: '¿Guardar y cerrar?',
    msg: `Tu progreso con <strong>${patientName || 'el paciente'}</strong> quedará guardado para que puedas retomarlo después en tu historial.`,
    icon: '💾',
    confirmText: 'Guardar sesión',
    onConfirm: async () => {
      isLoading = true;
      const eb = document.getElementById('end-btn');
      const sb = document.getElementById('send-btn');
      if (eb) { eb.disabled = true; eb.textContent = 'Guardando…'; }
      if (sb) sb.disabled = true;
      document.getElementById('user-input').disabled = true;

      try {
        const res = await fetch(`${API}/session/save`, {
          method: 'POST', headers: authHeaders(),
          body: JSON.stringify({ session_id: sessionId }),
          signal: AbortSignal.timeout(20000),
        });
        if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Error ${res.status}`); }
        const data = await res.json();
        showToast(`Sesión #${data.numero_sesion} guardada ✓`);
        _closeAndReset();
      } catch (e) {
        showToast('Error al guardar: ' + e.message, true);
        isLoading = false;
        if (eb) { eb.disabled = false; eb.textContent = 'Guardar y cerrar'; }
        if (sb) sb.disabled = false;
        document.getElementById('user-input').disabled = false;
      }
    }
  });
}

// "Ver análisis IA" — llama a /session/end para generar el reporte completo
async function analyzeSession() {
  if (!sessionId || isLoading) return;

  showConfirmModal({
    title: '¿Generar análisis?',
    msg: 'La IA supervisora evaluará tu desempeño clínico. Esto cerrará la sesión actual y tardará unos segundos.',
    icon: '📊',
    confirmText: 'Analizar ahora',
    onConfirm: async () => {
      const overlay = document.getElementById('modal-overlay');
      const mc = document.getElementById('modal-content');
      overlay.classList.add('active');
      mc.innerHTML = `<div class="modal-title">Analizando sesión…</div><div class="modal-subtitle">La IA supervisora está generando tu reporte clínico</div><div class="spinner"></div>`;
      try {
        const res = await fetch(`${API}/session/end`, {
          method: 'POST', headers: authHeaders(),
          body: JSON.stringify({ session_id: sessionId }),
          signal: AbortSignal.timeout(120000),
        });
        if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Error ${res.status}`); }
        const data = await res.json();
        _renderReport(data, mc);
        _closeAndReset();
      } catch (e) {
        overlay.classList.remove('active');
        showToast('Error en el análisis: ' + e.message, true);
      }
    }
  });
}

function _renderReport(data, mc) {
  const score = data.puntuacion;
  const deg = score ? Math.round(score * 3.6) : 0;
  const specMatch = (data.analisis_objetivo || '').match(/especializaci[oó]n[^:]*[:]\s*\*{0,2}([^*]+)\*{0,2}/i);
  const specialty = specMatch ? specMatch[1].trim() : null;
  mc.innerHTML = `
    <div class="modal-title">Reporte · Sesión #${data.numero_sesion || 1}</div>
    <div class="modal-subtitle">Con ${data.patient_name} · Análisis generado por IA supervisora</div>
    ${score != null ? `<div class="score-ring" style="background:conic-gradient(var(--accent) ${deg}deg,var(--border) ${deg}deg);"><span class="score-value">${score}</span></div>` : ''}
    ${specialty ? `<div style="text-align:center;margin-bottom:20px;"><div class="specialty-badge">🎓 ${specialty}</div></div>` : ''}
    <div class="section-label">Perspectiva de ${data.patient_name}</div>
    <div class="feedback-block">${data.feedback_paciente || '—'}</div>
    <div class="section-label">Análisis clínico objetivo</div>
    <div class="feedback-block">${data.analisis_objetivo || '—'}</div>
    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:16px;">
      <button class="modal-close" onclick="closeSessionModal()">Cerrar</button>
    </div>`;
}

function closeSessionModal() { closeModal(); _closeAndReset(); }

function _closeAndReset() {
  isLoading = false; sessionId = null; patientId = ''; patientName = '';
  _checkAltaCount = 0;
  const eb = document.getElementById('end-btn');
  const ab = document.getElementById('analyze-btn');
  const hb = document.getElementById('alta-btn');
  const ui = document.getElementById('user-input');
  if (eb) { eb.disabled = false; eb.textContent = 'Guardar y cerrar'; }
  if (ab) { ab.style.display = 'none'; ab.disabled = false; }
  if (hb) { hb.style.display = 'none'; hb.disabled = false; delete hb.dataset.shown; }
  if (ui) { ui.disabled = false; ui.value = ''; }
  const ti = document.getElementById('typing-indicator'); if (ti) ti.remove();
  document.getElementById('chat-box').innerHTML = `<div class="empty-state" id="empty-msg"><div class="icon">🛋️</div><span>Selecciona un paciente para comenzar una nueva sesión.</span></div>`;
  document.getElementById('card-name').textContent = '—';
  resetStudentDashboard(); loadPatients();
}

// "Proponer alta" — abre formulario de alta
function proposeAlta() {
  if (!sessionId) return;
  const overlay = document.getElementById('modal-overlay');
  const mc = document.getElementById('modal-content');
  overlay.classList.add('active');
  mc.innerHTML = `
    <div class="modal-title">Alta terapéutica</div>
    <div class="modal-subtitle">Responde las siguientes preguntas para fundamentar el alta. El supervisor IA evaluará tu criterio clínico.</div>
    <div class="section-label">Preguntas de cierre</div>
    <div style="font-size:.82rem;color:var(--muted);line-height:1.8;margin-bottom:14px;">
      • ¿Qué pasaría si hoy surgiera el mismo problema que trajo al paciente?<br>
      • ¿Sientes que el paciente tiene recursos para manejar futuras crisis solo?<br>
      • ¿La terapia se ha vuelto repetitiva o aún hay material clínico importante?<br>
      • ¿Cómo imaginas la vida del paciente a seis meses sin venir a consulta?
    </div>
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;">Tu reflexión:</label>
    <textarea id="alta-reflexion" style="width:100%;min-height:110px;border-radius:10px;border:1px solid var(--border);background:var(--surface);color:var(--text);padding:10px;font-size:.85rem;resize:vertical;" placeholder="Escribe aquí tu análisis sobre el alta…"></textarea>
    <div style="display:flex;justify-content:space-between;gap:10px;margin-top:16px;">
      <button class="btn-ghost" style="padding:10px 18px;" onclick="closeModal()">Cancelar</button>
      <button class="btn-primary" style="width:auto;padding:10px 22px;" onclick="darAltaSesion()">Enviar y generar informe</button>
    </div>`;
}

async function darAltaSesion() {
  const reflexion = (document.getElementById('alta-reflexion')?.value || '').trim();
  if (!reflexion) { showToast('Escribe tu reflexión antes de enviar.', true); return; }
  if (!sessionId) { closeSessionModal(); return; }
  const overlay = document.getElementById('modal-overlay');
  const mc = document.getElementById('modal-content');
  overlay.classList.add('active');
  mc.innerHTML = `<div class="modal-title">Generando informe de alta…</div><div class="modal-subtitle">El supervisor IA está evaluando el cierre del proceso.</div><div class="spinner"></div>`;
  try {
    const res = await fetch(`${API}/session/alta`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ sesion_id: sessionId, reflexion }),
      signal: AbortSignal.timeout(120000),
    });
    const data = await res.json();
    if (!res.ok) { mc.innerHTML = `<div class="modal-title">Error</div><div class="modal-subtitle">${data.detail || 'Error desconocido'}</div><button class="modal-close" onclick="closeSessionModal()">Cerrar</button>`; return; }
    mc.innerHTML = `
      <div class="modal-title">✅ Alta terapéutica registrada</div>
      <div class="modal-subtitle">El proceso con este paciente ha sido cerrado formalmente.</div>
      <div class="section-label">Informe del supervisor IA</div>
      <div class="feedback-block">${data.alta_reporte}</div>
      <button class="modal-close" style="margin-top:12px;" onclick="closeSessionModal()">Cerrar</button>`;
  } catch (e) {
    mc.innerHTML = `<div class="modal-title">Error</div><div class="modal-subtitle">${e.message}</div><button class="modal-close" onclick="closeSessionModal()">Cerrar</button>`;
  }
}


// ── HISTORIAL — ver detalle (modal) ──────────────────────

async function loadDetalle(sesionId) {
  const overlay = document.getElementById('modal-overlay');
  const mc = document.getElementById('modal-content');
  overlay.classList.add('active');
  mc.innerHTML = '<div class="spinner"></div>';

  try {
    const res = await fetch(`${API}/historial/sesion/${sesionId}`, { headers: authHeaders() });
    const data = await res.json();
    mc.innerHTML = `
      <div class="modal-title">Detalle de sesión</div>
      <div class="modal-subtitle">Guardado el ${formatDate(data.guardado_en)}</div>
      <div class="section-label">Perspectiva del paciente</div>
      <div class="feedback-block">${data.feedback_paciente}</div>
      <div class="section-label">Análisis clínico objetivo</div>
      <div class="feedback-block">${data.analisis_objetivo}</div>
      <div class="section-label">Transcripción</div>
      <div class="feedback-block" style="font-size:.8rem;color:var(--muted);">${data.transcripcion}</div>
      <button class="modal-close" onclick="closeModal()">Cerrar</button>`;
  } catch (e) {
    mc.innerHTML = `
      <div class="modal-title">Error</div>
      <div class="modal-subtitle">No se pudo cargar el detalle.</div>
      <button class="modal-close" onclick="closeModal()">Cerrar</button>`;
  }
}


// ── DOCENTE (old simple view — replaced by new panel above) ──
// kept as stub to avoid reference errors from old nav calls
// ── ADMIN PANEL ───────────────────────────────────────────

// ---- State ----
let adminData = { usuarios: [], instituciones: [], pagos: [], casos: {}, categorias: [] };
let selectedInstId = null;
let selectedCasoId = null;
let selectedCatIndex = null;

// ---- Navigation ----
function adminNav(btn, panelId) {
  document.querySelectorAll('.sidebar-item').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.admin-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(panelId).classList.add('active');
}

// ---- Load overview (called on admin screen open) ----
async function loadAdmin() {
  // Update nav tabs for admin role
  try {
    const res = await fetch(`${API}/admin/usuarios`, { headers: authHeaders() });
    const data = await res.json();
    adminData.usuarios = data;

    // KPIs
    document.getElementById('kpi-users').textContent = data.length;
    document.getElementById('kpi-students').textContent = data.filter(u => u.rol === 'estudiante').length;

    // Overview: users
    const ovUsers = document.getElementById('ov-users-list');
    ovUsers.innerHTML = data.slice(0, 5).map(u => `
      <div class="ov-row">
        <span>${u.nombre} <span style="color:var(--muted);font-size:.75rem;">(${u.rol})</span></span>
        <span style="font-size:.75rem;color:var(--muted)">${formatDate(u.creado_en)}</span>
      </div>`).join('') || '<div class="ov-empty">Sin usuarios</div>';

  } catch (e) {
    document.getElementById('ov-users-list').innerHTML = '<div class="ov-empty" style="color:var(--red)">Error cargando usuarios</div>';
  }

  // Overview: instituciones (local for now)
  loadInstitOverview();
  // Overview: sesiones
  loadSesionesOverview();
  // Cases KPI
  document.getElementById('kpi-cases').textContent = Object.keys(adminData.casos || {}).length || 3;
  document.getElementById('kpi-inst').textContent = adminData.instituciones.length || '—';
  loadContabilidadKpis();
}

function loadInstitOverview() {
  const el = document.getElementById('ov-inst-list');
  if (!adminData.instituciones.length) {
    el.innerHTML = '<div class="ov-empty">Sin instituciones registradas aún.<br><small>Ve a Instituciones → + Nueva institución</small></div>';
    return;
  }
  el.innerHTML = adminData.instituciones.slice(0, 4).map(i => `
    <div class="ov-row">
      <span>${i.nombre}</span>
      <span class="inst-pill inst-pill-active" style="font-size:.7rem">${i.suscripcion_estado || 'activa'}</span>
    </div>`).join('');
  document.getElementById('kpi-inst').textContent = adminData.instituciones.length;
}

async function loadSesionesOverview() {
  try {
    const res = await fetch(`${API}/historial/todos`, { headers: authHeaders() });
    const data = await res.json();
    const el = document.getElementById('ov-sesiones-list');
    el.innerHTML = data.slice(0, 5).map(s => `
      <div class="ov-row">
        <span style="font-size:.82rem">${s.usuario_id?.split('@')[0] || '—'} → ${s.patient_name || '—'}</span>
        <span class="score-pill ${scoreCls(s.puntuacion)}">${s.puntuacion != null ? s.puntuacion + 'pts' : '—'}</span>
      </div>`).join('') || '<div class="ov-empty">Sin sesiones aún</div>';
    adminData.sesiones = data;
  } catch (e) { }
}

// ---- INSTITUCIONES ----
// ═══════════════════════════════════════════════════════════
// INSTITUCIONES — Conectado al backend real
// ═══════════════════════════════════════════════════════════

async function loadInstituciones() {
  const list = document.getElementById('inst-list');
  list.innerHTML = '<div style="grid-column:1/-1;padding:32px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';
  try {
    const res = await fetch(`${API}/admin/instituciones`, { headers: authHeaders() });
    const data = await res.json();
    adminData.instituciones = Array.isArray(data) ? data : [];
    renderInstCards();
    loadInstitOverview();
    document.getElementById('kpi-inst').textContent = adminData.instituciones.length;
  } catch (e) {
    list.innerHTML = '<div style="grid-column:1/-1" class="ov-empty" style="color:var(--red)">Error cargando instituciones</div>';
  }
}

function renderInstCards() {
  const list = document.getElementById('inst-list');
  if (!adminData.instituciones.length) {
    list.innerHTML = `<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--muted);background:var(--card);border:1px dashed var(--border);border-radius:14px">
      <div style="font-size:2rem;margin-bottom:8px">🏫</div>
      <div>No hay instituciones registradas</div>
      <div style="font-size:.8rem;margin-top:6px">Haz clic en "+ Nueva institución" para comenzar</div>
    </div>`;
    return;
  }
  list.innerHTML = adminData.instituciones.map((inst, i) => `
    <div class="inst-card" onclick="abrirInstitucion(${i})">
      <div class="inst-card-name">${inst.nombre}</div>
      <div class="inst-card-meta">${inst.ciudad || ''} ${inst.ciudad && inst.email ? '·' : ''} ${inst.email || ''}</div>
      <div class="inst-card-pills">
        <span class="inst-pill inst-pill-active">${inst.suscripcion_estado || 'prueba'}</span>
        <span class="inst-pill inst-pill-plan">${inst.plan || 'Sin plan'}</span>
      </div>
    </div>`).join('');
}

async function abrirInstitucion(idx) {
  selectedInstId = idx;
  const inst = adminData.instituciones[idx];
  document.getElementById('inst-list').style.display = 'none';
  document.getElementById('inst-detail').style.display = 'block';

  // Info básica
  document.getElementById('di-nombre').value = inst.nombre || '';
  document.getElementById('di-nit').value = inst.nit || '';
  document.getElementById('di-contacto').value = inst.contacto || '';
  document.getElementById('di-email').value = inst.email || '';
  document.getElementById('di-telefono').value = inst.telefono || '';
  document.getElementById('di-ciudad').value = inst.ciudad || '';
  document.getElementById('di-dominio').value = inst.dominio || '';

  // Suscripción — estado visual
  document.getElementById('sus-plan-name').textContent = inst.plan || 'Sin plan';
  document.getElementById('sus-inicio').textContent = inst.sus_inicio ? formatDate(inst.sus_inicio) : '—';
  document.getElementById('sus-vence').textContent = inst.sus_fin ? formatDate(inst.sus_fin) : '—';
  document.getElementById('sus-monto').textContent = inst.sus_monto ? '$' + Number(inst.sus_monto).toLocaleString() : '—';
  const badge = document.getElementById('sus-badge-estado');
  if (badge) { badge.textContent = inst.suscripcion_estado || 'prueba'; }

  // Suscripción — formulario
  document.getElementById('sus-plan-sel').value = inst.plan || '';
  document.getElementById('sus-fecha-inicio').value = inst.sus_inicio || '';
  document.getElementById('sus-fecha-fin').value = inst.sus_fin || '';
  document.getElementById('sus-monto-input').value = inst.sus_monto || '';
  document.getElementById('sus-estado-sel').value = inst.suscripcion_estado || 'prueba';
  document.getElementById('sus-notas').value = inst.sus_notas || '';

  // Contrato
  document.getElementById('ct-numero').value = inst.ct_numero || '';
  document.getElementById('ct-fecha').value = inst.ct_fecha || '';
  document.getElementById('ct-vigencia').value = inst.ct_vigencia || '';
  document.getElementById('ct-desc').value = inst.ct_desc || '';

  // Reset tabs
  document.querySelectorAll('#inst-detail .dtab').forEach((t, i) => t.classList.toggle('active', i === 0));
  document.querySelectorAll('#inst-detail .dtab-panel').forEach((p, i) => p.classList.toggle('active', i === 0));

  // Cargar usuarios de la institución desde backend
  await loadInstUsuarios(inst.id);
  // Cargar pagos de la institución
  renderInstPagos(inst.nombre);
}

async function loadInstUsuarios(instId) {
  document.getElementById('inst-docentes-tbody').innerHTML = '<tr><td colspan="5" class="empty-table"><div class="spinner" style="margin:0 auto"></div></td></tr>';
  document.getElementById('inst-estudiantes-tbody').innerHTML = '<tr><td colspan="5" class="empty-table"></td></tr>';
  try {
    const res = await fetch(`${API}/admin/instituciones/${instId}/usuarios`, { headers: authHeaders() });
    const data = await res.json();
    const docentes = data.filter(u => u.rol === 'docente');
    const estudiantes = data.filter(u => u.rol === 'estudiante');

    document.getElementById('inst-docentes-tbody').innerHTML = docentes.length
      ? docentes.map(u => {
        const initial = (u.nombre || '?').charAt(0).toUpperCase();
        return `<tr>
          <td>
            <div class="hist-patient-cell">
              <div class="hist-avatar">${initial}</div>
              <strong>${u.nombre}</strong>
            </div>
          </td>
          <td style="font-size:.8rem;color:var(--muted)">${u.email}</td>
          <td style="text-align:center;color:var(--muted)">—</td>
          <td>
            <span class="status-pill ${u.activo !== false ? 'status-completada' : 'status-activa'}">
              ${u.activo !== false ? 'Activo' : 'Inactivo'}
            </span>
          </td>
          <td>
            <div class="hist-actions">
              <button class="btn-ghost-danger" style="padding:4px 8px; font-size:1rem; min-width:36px; display:flex; align-items:center; justify-content:center;"
                onclick="desvincularUsuario('${u.email}','${instId}')">🗑</button>
            </div>
          </td>
        </tr>`}).join('')
      : '<tr><td colspan="5" class="empty-table">Sin docentes vinculados</td></tr>';

    document.getElementById('inst-estudiantes-tbody').innerHTML = estudiantes.length
      ? estudiantes.map(u => {
        const initial = (u.nombre || '?').charAt(0).toUpperCase();
        return `<tr>
          <td>
            <div class="hist-patient-cell">
              <div class="hist-avatar">${initial}</div>
              <strong>${u.nombre}</strong>
            </div>
          </td>
          <td style="font-size:.8rem;color:var(--muted)">${u.email}</td>
          <td style="text-align:center;color:var(--muted)">—</td>
          <td style="font-size:.78rem;color:var(--muted)">${formatDate(u.creado_en)}</td>
          <td>
            <div class="hist-actions">
              <button class="btn-ghost-danger" style="padding:4px 8px; font-size:1rem; min-width:36px; display:flex; align-items:center; justify-content:center;"
                onclick="desvincularUsuario('${u.email}','${instId}')">🗑</button>
            </div>
          </td>
        </tr>`}).join('')
      : '<tr><td colspan="5" class="empty-table">Sin estudiantes vinculados</td></tr>';
  } catch (e) {
    document.getElementById('inst-docentes-tbody').innerHTML = '<tr><td colspan="5" class="empty-table" style="color:var(--red)">Error cargando usuarios</td></tr>';
  }
}

function renderInstPagos(nombreInst) {
  const pagos = (adminData.pagos || []).filter(p => p.origen === nombreInst);
  document.getElementById('inst-pagos-tbody').innerHTML = pagos.length
    ? pagos.map(p => {
      const status = (p.estado || 'pendiente').toLowerCase();
      return `<tr>
        <td>
          <div class="hist-date-box">
            <span class="hist-date-main">${formatDate(p.fecha)}</span>
          </div>
        </td>
        <td><strong style="color:var(--teal-deep);font-size:1.05rem;">$${Number(p.monto || 0).toLocaleString()}</strong></td>
        <td style="font-size:.8rem;color:var(--muted)">${p.metodo || '—'}</td>
        <td style="font-size:.78rem;color:var(--muted);font-family:monospace;">${p.referencia || '—'}</td>
        <td><span class="status-pill status-${status === 'confirmado' ? 'completada' : 'activa'}">${status}</span></td>
        <td></td>
      </tr>`}).join('')
    : '<tr><td colspan="6" class="empty-table">Sin pagos registrados</td></tr>';
}

function closeInstDetail() {
  document.getElementById('inst-detail').style.display = 'none';
  document.getElementById('inst-list').style.display = 'grid';
}

async function guardarInstitucion() {
  if (selectedInstId === null) return;
  const inst = adminData.instituciones[selectedInstId];
  const payload = {
    nombre: document.getElementById('di-nombre').value.trim(),
    nit: document.getElementById('di-nit').value.trim(),
    contacto: document.getElementById('di-contacto').value.trim(),
    email: document.getElementById('di-email').value.trim(),
    telefono: document.getElementById('di-telefono').value.trim(),
    ciudad: document.getElementById('di-ciudad').value.trim(),
    dominio: document.getElementById('di-dominio').value.trim(),
  };
  if (!payload.nombre) { showToast('El nombre es requerido', true); return; }
  try {
    const res = await fetch(`${API}/admin/instituciones/${inst.id}`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    Object.assign(adminData.instituciones[selectedInstId], payload);
    showToast('Institución guardada ✓');
  } catch (e) { showToast('Error al guardar: ' + e.message, true); }
}

async function guardarSuscripcion() {
  if (selectedInstId === null) return;
  const inst = adminData.instituciones[selectedInstId];
  const payload = {
    plan: document.getElementById('sus-plan-sel').value,
    sus_inicio: document.getElementById('sus-fecha-inicio').value,
    sus_fin: document.getElementById('sus-fecha-fin').value,
    sus_monto: Number(document.getElementById('sus-monto-input').value) || null,
    suscripcion_estado: document.getElementById('sus-estado-sel').value,
    sus_notas: document.getElementById('sus-notas').value,
  };
  try {
    const res = await fetch(`${API}/admin/instituciones/${inst.id}/suscripcion`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    Object.assign(adminData.instituciones[selectedInstId], payload);
    document.getElementById('sus-plan-name').textContent = payload.plan || 'Sin plan';
    document.getElementById('sus-inicio').textContent = payload.sus_inicio ? formatDate(payload.sus_inicio) : '—';
    document.getElementById('sus-vence').textContent = payload.sus_fin ? formatDate(payload.sus_fin) : '—';
    document.getElementById('sus-monto').textContent = payload.sus_monto ? '$' + payload.sus_monto.toLocaleString() : '—';
    showToast('Suscripción actualizada ✓');
  } catch (e) { showToast('Error al guardar: ' + e.message, true); }
}

async function guardarContrato() {
  if (selectedInstId === null) return;
  const inst = adminData.instituciones[selectedInstId];
  const payload = {
    ct_numero: document.getElementById('ct-numero').value.trim(),
    ct_fecha: document.getElementById('ct-fecha').value,
    ct_vigencia: Number(document.getElementById('ct-vigencia').value) || null,
    ct_desc: document.getElementById('ct-desc').value.trim(),
  };
  try {
    const res = await fetch(`${API}/admin/instituciones/${inst.id}/contrato`, {
      method: 'PUT', headers: authHeaders(), body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    Object.assign(adminData.instituciones[selectedInstId], payload);
    showToast('Contrato guardado ✓');
  } catch (e) { showToast('Error al guardar: ' + e.message, true); }
}

async function crearInstitucion() {
  const nombre = document.getElementById('ni-nombre').value.trim();
  if (!nombre) { showToast('El nombre es requerido', true); return; }
  const payload = {
    nombre,
    nit: document.getElementById('ni-nit').value.trim(),
    contacto: document.getElementById('ni-contacto').value.trim(),
    email: document.getElementById('ni-email').value.trim(),
    ciudad: document.getElementById('ni-ciudad').value.trim(),
    dominio: document.getElementById('ni-dominio').value.trim(),
  };
  try {
    const res = await fetch(`${API}/admin/instituciones`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    closeAdminModal('modal-nueva-inst');
    // Limpiar campos
    ['ni-nombre', 'ni-nit', 'ni-contacto', 'ni-email', 'ni-ciudad', 'ni-dominio'].forEach(id => {
      document.getElementById(id).value = '';
    });
    await loadInstituciones();
    showToast(`"${nombre}" creada ✓`);
  } catch (e) { showToast('Error al crear: ' + e.message, true); }
}

async function invitarUsuario() {
  if (selectedInstId === null) return;
  const inst = adminData.instituciones[selectedInstId];
  const email = document.getElementById('inv-email').value.trim();
  const rol = document.getElementById('inv-rol').value;
  if (!email) { showToast('Ingresa un correo', true); return; }
  try {
    const res = await fetch(`${API}/admin/instituciones/${inst.id}/vincular`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ email, rol, genero: document.getElementById('inv-genero').value, institucion_id: inst.id }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${res.status}`);
    }
    closeAdminModal('modal-invitar-usuario');
    document.getElementById('inv-email').value = '';
    await loadInstUsuarios(inst.id);
    showToast('Usuario vinculado ✓');
  } catch (e) { showToast('Error: ' + e.message, true); }
}

async function desvincularUsuario(email, instId) {
  showConfirmModal({
    title: '¿Desvincular usuario?',
    msg: `¿Estás seguro de desvincular a <strong>${email}</strong> de esta institución?`,
    icon: '🔗',
    confirmText: 'Desvincular ahora',
    onConfirm: async () => {
      try {
        const res = await fetch(`${API}/admin/instituciones/${instId}/desvincular/${encodeURIComponent(email)}`, {
          method: 'POST', headers: authHeaders(),
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);
        await loadInstUsuarios(instId);
        showToast('Usuario desvinculado');
      } catch (e) { showToast('Error: ' + e.message, true); }
    }
  });
}

// ═══════════════════════════════════════════════════════════
// PAGOS — Conectado al backend real
// ═══════════════════════════════════════════════════════════

async function loadContabilidad() {
  const tbody = document.getElementById('cont-tbody');
  tbody.innerHTML = '<tr><td colspan="7" class="empty-table"><div class="spinner" style="margin:0 auto"></div></td></tr>';
  try {
    const res = await fetch(`${API}/admin/pagos`, { headers: authHeaders() });
    const data = await res.json();
    adminData.pagos = Array.isArray(data) ? data : [];
    loadContabilidadKpis();
    filtrarPagos();
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty-table" style="color:var(--red)">Error cargando pagos</td></tr>';
  }
}

// ---- PARTICULARES ----
function loadParticulares() {
  filtrarParticulares();
}

function filtrarParticulares() {
  const q = (document.getElementById('part-search')?.value || '').toLowerCase();
  const estado = document.getElementById('part-filter-estado')?.value || '';
  // Only users with no institución
  const vinculados = new Set(adminData.instituciones.flatMap(i => (i.usuarios || []).map(u => u.email)));
  let users = adminData.usuarios.filter(u => !vinculados.has(u.email) && u.rol !== 'admin');
  if (q) users = users.filter(u => u.nombre?.toLowerCase().includes(q) || u.email?.toLowerCase().includes(q));
  const tbody = document.getElementById('part-tbody');
  tbody.innerHTML = users.length
    ? users.map(u => {
      const initial = (u.nombre || '?').charAt(0).toUpperCase();
      return `<tr>
        <td>
          <div class="hist-patient-cell">
            <div class="hist-avatar">${initial}</div>
            <strong>${u.nombre}</strong>
          </div>
        </td>
        <td style="font-size:.8rem;color:var(--muted)">${u.email}</td>
        <td><span class="status-pill status-activa" style="text-transform:uppercase; font-size:10px;">${u.rol}</span></td>
        <td style="font-size:.78rem;color:var(--muted)">—</td>
        <td style="font-size:.78rem;color:var(--muted)">—</td>
        <td><strong style="color:var(--teal-deep)">$0</strong></td>
        <td>
          <div class="hist-actions">
            <button class="btn-ghost" style="padding:6px 12px; font-size:.78rem;" onclick="verParticular('${u.email}')">Ver</button>
            ${u.email !== currentUser?.email
          ? `<button class="btn-ghost-danger" style="padding:4px 8px; font-size:1rem; min-width:36px; display:flex; align-items:center; justify-content:center;" onclick="deleteUser('${u.email}')">🗑</button>`
          : ''}
          </div>
        </td>
      </tr>`}).join('')
    : '<tr><td colspan="7" class="empty-table">Sin usuarios particulares</td></tr>';
}

function crearParticular() {
  const nombre = document.getElementById('np-nombre').value.trim();
  const email = document.getElementById('np-email').value.trim();
  const password = document.getElementById('np-password').value;
  const rol = document.getElementById('np-rol').value;
  const genero = document.getElementById('np-genero').value;
  if (!nombre || !email || !password) { alert('Completa todos los campos.'); return; }
  fetch(`${API}/auth/register`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre, email, password, rol, genero })
  }).then(r => r.json()).then(d => {
    closeAdminModal('modal-nuevo-particular');
    loadAdmin();
    showToast('Usuario creado ✓');
  }).catch(() => alert('Error creando el usuario.'));
}

function verParticular(email) {
  const u = adminData.usuarios.find(u => u.email === email);
  if (!u) return;
  alert(`Usuario: ${u.nombre}\nCorreo: ${u.email}\nRol: ${u.rol}\nRegistrado: ${formatDate(u.creado_en)}`);
}

// ---- CASOS IA ----
// ═══════════════════════════════════════════════════════════
// CASOS IA — Conectado al backend real
// ═══════════════════════════════════════════════════════════

async function loadCasosAdmin() {
  setCasosLoading(true);
  try {
    // Carga casos y categorías en paralelo
    const [resCasos, resCats] = await Promise.all([
      fetch(`${API}/admin/casos`, { headers: authHeaders() }),
      fetch(`${API}/admin/categorias`, { headers: authHeaders() }),
    ]);
    const casos = await resCasos.json();
    const cats = await resCats.json();

    // Guarda en adminData como dict keyed por caso_id
    adminData.casos = {};
    (Array.isArray(casos) ? casos : []).forEach(c => {
      adminData.casos[c.caso_id || c.name?.toLowerCase().replace(/\s+/g, '_')] = c;
    });
    adminData.categorias = Array.isArray(cats) ? cats : [];

    document.getElementById('kpi-cases').textContent = Object.keys(adminData.casos).length;
    renderCategorias();

    // Si no hay categoría seleccionada y hay categorías, selecciona la primera
    if (selectedCatIndex === null && adminData.categorias.length) {
      seleccionarCategoria(0, adminData.categorias[0]);
    } else if (selectedCatIndex !== null) {
      seleccionarCategoria(selectedCatIndex, adminData.categorias[selectedCatIndex]);
    }
  } catch (e) {
    document.getElementById('casos-cat-list').innerHTML =
      '<div class="ov-empty" style="color:var(--red)">Error cargando casos.<br>Verifica la conexión al backend.</div>';
  } finally {
    setCasosLoading(false);
  }
}

function setCasosLoading(on) {
  const wrap = document.getElementById('casos-list-wrap');
  if (on) wrap.innerHTML = '<div class="ov-empty"><div class="spinner" style="margin:12px auto"></div></div>';
}

function renderCategorias() {
  const list = document.getElementById('casos-cat-list');
  if (!adminData.categorias.length) {
    list.innerHTML = '<div class="ov-empty" style="font-size:.78rem">Sin categorías</div>';
    return;
  }
  list.innerHTML = adminData.categorias.map((cat, i) => {
    const count = Object.values(adminData.casos).filter(c => c.categoria === cat).length;
    return `<div class="cat-item${i === selectedCatIndex ? ' active' : ''}"
      onclick="seleccionarCategoria(${i},'${cat.replace(/'/g, "\\'")}')">
      <span>${cat}</span><span class="cat-count">${count}</span>
    </div>`;
  }).join('');
}

function seleccionarCategoria(idx, cat) {
  selectedCatIndex = idx;
  renderCategorias();
  const casos = Object.entries(adminData.casos).filter(([, c]) => c.categoria === cat);
  const wrap = document.getElementById('casos-list-wrap');
  wrap.innerHTML = casos.length
    ? casos.map(([id, c]) => `
        <div class="caso-item" onclick="abrirCasoEditor('${id}', event)">
          <div class="caso-item-name">${c.name}
            <span style="font-size:.72rem;color:var(--muted)">(${c.age} años)</span>
            <span class="inst-pill inst-pill-plan" style="float:right;font-size:.65rem">${c.dificultad || '—'}</span>
          </div>
          <div class="caso-item-meta">${(c.descripcion || '').slice(0, 55)}${c.descripcion?.length > 55 ? '…' : ''}</div>
        </div>`).join('')
    : '<div class="ov-empty">Sin casos en esta categoría.<br><small>Crea uno con "+ Nuevo caso"</small></div>';
}

function renderAvatarGrid(selectedFile = '') {
  const grid = document.getElementById('ce-avatar-grid');
  if (!grid) return;
  const wasOpen = grid.style.display === 'grid'; // preservar estado abierto/cerrado

  grid.innerHTML = PATIENT_AVATARS.map(file => {
    const isSelected = file === selectedFile;
    return `
      <div onclick="selectAvatar('${file}')" title="${file.replace('.webp', '')}" style="
        cursor:pointer;
        border-radius:10px;
        padding:4px;
        border:2.5px solid ${isSelected ? 'var(--teal)' : 'transparent'};
        background:${isSelected ? 'rgba(108,193,206,.15)' : 'transparent'};
        transition:all .18s;
        display:flex; flex-direction:column; align-items:center; gap:4px;">
        <img src="${AVATAR_BASE}${file}" alt="${file}"
          style="width:52px; height:52px; border-radius:50%; object-fit:cover;
                 border:1px solid var(--border);"
          onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
        <div style="display:none; width:52px; height:52px; border-radius:50%;
                    background:var(--surface); border:1px solid var(--border);
                    align-items:center; justify-content:center; font-size:1.4rem;">👤</div>
        <span style="font-size:.6rem; color:var(--muted); text-align:center; line-height:1.2; word-break:break-word; max-width:60px;">
          ${file.replace('.webp', '').replace(/_/g, ' ')}
        </span>
      </div>`;
  }).join('');
  if (!wasOpen) grid.style.display = 'none'; // re-ocultar si estaba cerrado
}

function selectAvatar(file) {
  document.getElementById('ce-avatar').value = file;
  // Actualizar preview
  const img = document.getElementById('ce-avatar-img');
  const placeholder = document.getElementById('ce-avatar-placeholder');
  const label = document.getElementById('ce-avatar-label');
  if (img && placeholder) {
    img.src = AVATAR_BASE + file;
    img.style.display = 'block';
    placeholder.style.display = 'none';
  }
  if (label) label.textContent = file.replace('.webp', '').replace(/_/g, ' ');
  // Re-render grid para actualizar borde seleccionado
  renderAvatarGrid(file);
  // Cerrar el desplegable al seleccionar
  const grid = document.getElementById('ce-avatar-grid');
  const chevron = document.getElementById('ce-avatar-chevron');
  const trigger = document.getElementById('ce-avatar-trigger');
  if (grid) grid.style.display = 'none';
  if (chevron) chevron.style.transform = 'rotate(0deg)';
  if (trigger) trigger.style.borderColor = 'var(--border)';
}

function toggleAvatarDropdown() {
  const grid = document.getElementById('ce-avatar-grid');
  const chevron = document.getElementById('ce-avatar-chevron');
  const trigger = document.getElementById('ce-avatar-trigger');
  const isOpen = grid.style.display === 'grid';

  if (isOpen) {
    grid.style.display = 'none';
    chevron.style.transform = 'rotate(0deg)';
    trigger.style.borderColor = 'var(--border)';
  } else {
    grid.style.display = 'grid';
    chevron.style.transform = 'rotate(180deg)';
    trigger.style.borderColor = 'var(--teal)';
  }
}

function abrirNuevoCaso() {
  selectedCasoId = null;
  document.getElementById('editor-caso-title').textContent = 'Nuevo caso';
  document.getElementById('ce-nombre').value = '';
  document.getElementById('ce-edad').value = '';
  document.getElementById('ce-dificultad').value = 'Leve';
  document.getElementById('ce-desc').value = '';
  document.getElementById('ce-instruccion').value = '';
  document.getElementById('ce-feedback').value = '';
  document.getElementById('btn-eliminar-caso').style.display = 'none';
  document.getElementById('caso-editor').style.display = 'flex';
  document.getElementById('caso-editor').style.flexDirection = 'column';
  // Resetear avatar
  document.getElementById('ce-avatar').value = '';
  document.getElementById('ce-avatar-img').style.display = 'none';
  document.getElementById('ce-avatar-placeholder').style.display = 'block';
  document.getElementById('ce-avatar-label').textContent = 'Sin avatar seleccionado';
  renderAvatarGrid('');
}

function abrirCasoEditor(id, evt) {
  selectedCasoId = id;
  const c = adminData.casos[id];
  document.getElementById('editor-caso-title').textContent = 'Editando: ' + c.name;
  document.getElementById('ce-nombre').value = c.name || '';
  document.getElementById('ce-edad').value = c.age || '';
  document.getElementById('ce-dificultad').value = c.dificultad || 'Leve';
  document.getElementById('ce-desc').value = c.descripcion || '';
  document.getElementById('ce-instruccion').value = c.instruccion || '';
  document.getElementById('ce-feedback').value = c.instruccion_feedback || '';
  // Cargar avatar existente
  const avatarFile = c.avatar || '';
  document.getElementById('ce-avatar').value = avatarFile;
  if (avatarFile) {
    document.getElementById('ce-avatar-img').src = AVATAR_BASE + avatarFile;
    document.getElementById('ce-avatar-img').style.display = 'block';
    document.getElementById('ce-avatar-placeholder').style.display = 'none';
    document.getElementById('ce-avatar-label').textContent = avatarFile.replace('.webp', '').replace(/_/g, ' ');
  } else {
    document.getElementById('ce-avatar-img').style.display = 'none';
    document.getElementById('ce-avatar-placeholder').style.display = 'block';
    document.getElementById('ce-avatar-label').textContent = 'Sin avatar seleccionado';
  }
  renderAvatarGrid(avatarFile);
  document.getElementById('btn-eliminar-caso').style.display = 'inline-block';
  document.getElementById('caso-editor').style.display = 'flex';
  document.getElementById('caso-editor').style.flexDirection = 'column';
  document.querySelectorAll('.caso-item').forEach(el => el.classList.remove('active'));
  evt?.currentTarget?.classList.add('active');
}

async function guardarCaso() {
  const nombre = document.getElementById('ce-nombre').value.trim();
  if (!nombre) { showToast('El nombre del paciente es requerido', true); return; }

  const payload = {
    name: nombre,
    age: Number(document.getElementById('ce-edad').value) || 0,
    dificultad: document.getElementById('ce-dificultad').value,
    descripcion: document.getElementById('ce-desc').value.trim(),
    instruccion: document.getElementById('ce-instruccion').value.trim(),
    instruccion_feedback: document.getElementById('ce-feedback').value.trim(),
    avatar: document.getElementById('ce-avatar').value || '',
    categoria: adminData.categorias[selectedCatIndex] || adminData.categorias[0] || 'General',
  };

  if (!payload.instruccion) { showToast('Las instrucciones de comportamiento son requeridas', true); return; }
  if (!payload.instruccion_feedback) { showToast('Las instrucciones de feedback son requeridas', true); return; }

  // Deshabilitar botón mientras guarda
  const btn = document.querySelector('#caso-editor .btn-accent');
  if (btn) { btn.disabled = true; btn.textContent = 'Guardando…'; }

  try {
    let res;
    if (selectedCasoId) {
      // PUT — actualizar existente
      res = await fetch(`${API}/admin/casos/${selectedCasoId}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
    } else {
      // POST — crear nuevo
      res = await fetch(`${API}/admin/casos`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${res.status}`);
    }

    document.getElementById('caso-editor').style.display = 'none';
    showToast(selectedCasoId ? `"${nombre}" actualizado ✓` : `"${nombre}" creado ✓`);
    selectedCasoId = null;
    await loadCasosAdmin(); // Recarga desde el backend
  } catch (e) {
    showToast('Error: ' + e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Guardar'; }
  }
}

async function eliminarCaso() {
  if (!selectedCasoId) return;
  const nombre = adminData.casos[selectedCasoId]?.name || selectedCasoId;

  showConfirmModal({
    title: '¿Eliminar caso?',
    msg: `¿Seguro que deseas eliminar el caso "<strong>${nombre}</strong>"? Esta acción es permanente.`,
    icon: '📝',
    confirmText: 'Eliminar caso',
    onConfirm: async () => {
      const btn = document.getElementById('btn-eliminar-caso');
      if (btn) { btn.disabled = true; btn.textContent = 'Eliminando…'; }

      try {
        const res = await fetch(`${API}/admin/casos/${selectedCasoId}`, {
          method: 'DELETE',
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error(`Error ${res.status}`);

        document.getElementById('caso-editor').style.display = 'none';
        selectedCasoId = null;
        showToast(`"${nombre}" eliminado`);
        await loadCasosAdmin();
      } catch (e) {
        showToast('Error al eliminar: ' + e.message, true);
        if (btn) { btn.disabled = false; btn.textContent = 'Eliminar'; }
      }
    }
  });
}

async function crearCategoria() {
  const nombre = document.getElementById('nc-nombre').value.trim();
  if (!nombre) return;

  try {
    const res = await fetch(`${API}/admin/categorias`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ nombre }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Error ${res.status}`);
    }
    const data = await res.json();
    adminData.categorias = data.categorias || [...adminData.categorias, nombre];
    closeAdminModal('modal-nueva-categoria');
    document.getElementById('nc-nombre').value = '';
    renderCategorias();
    showToast(`Categoría "${nombre}" creada ✓`);
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

// ── Análisis objetivo global ──────────────────────────────
async function openAdminModal_analisisObjetivo() {
  openAdminModal('modal-analisis-objetivo');
  const textarea = document.getElementById('ao-instruccion');
  textarea.value = 'Cargando…';
  textarea.disabled = true;

  try {
    const res = await fetch(`${API}/admin/config/analisis_objetivo`, { headers: authHeaders() });
    const data = await res.json();
    textarea.value = data.valor || '';
  } catch (e) {
    textarea.value = '';
    showToast('No se pudo cargar el análisis objetivo', true);
  } finally {
    textarea.disabled = false;
  }
}

async function guardarAnalisisObjetivo() {
  const valor = document.getElementById('ao-instruccion').value.trim();
  if (!valor) { showToast('El texto no puede estar vacío', true); return; }

  const btn = document.querySelector('#modal-analisis-objetivo .btn-accent');
  if (btn) { btn.disabled = true; btn.textContent = 'Guardando…'; }

  try {
    const res = await fetch(`${API}/admin/config/analisis_objetivo`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ valor }),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    closeAdminModal('modal-analisis-objetivo');
    showToast('Análisis objetivo actualizado ✓');
  } catch (e) {
    showToast('Error al guardar: ' + e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Guardar cambios'; }
  }
}

// ---- SESIONES ADMIN ----
let adminSesMode = 'estudiantes';
let adminSesEstudiantes = [];
let adminSesDocentes = [];
let adminSesDocenteDetalle = [];

async function loadAdminSesiones() {
  await setSesionesMode(adminSesMode || 'estudiantes');
}

async function setSesionesMode(mode) {
  adminSesMode = mode;
  const tbody = document.getElementById('admin-ses-tbody');
  const headRow = document.getElementById('admin-ses-head-row');
  if (!tbody || !headRow) return;
  tbody.innerHTML = '<tr><td colspan="6" class="empty-table"><div class="spinner" style="margin:0 auto"></div></td></tr>';

  const btnEst = document.getElementById('ses-mode-est');
  const btnDoc = document.getElementById('ses-mode-doc');
  if (btnEst && btnDoc) {
    if (mode === 'estudiantes') {
      btnEst.style.borderColor = 'var(--accent)';
      btnEst.style.background = 'rgba(59,130,246,.15)';
      btnEst.style.color = 'var(--accent)';
      btnDoc.style.borderColor = 'var(--border)';
      btnDoc.style.background = 'transparent';
      btnDoc.style.color = 'var(--muted)';
    } else {
      btnDoc.style.borderColor = 'var(--accent)';
      btnDoc.style.background = 'rgba(59,130,246,.15)';
      btnDoc.style.color = 'var(--accent)';
      btnEst.style.borderColor = 'var(--border)';
      btnEst.style.background = 'transparent';
      btnEst.style.color = 'var(--muted)';
    }
  }

  if (mode === 'estudiantes') {
    headRow.innerHTML = `
      <th>Estudiante</th>
      <th>Total sesiones</th>
      <th>Minutos de práctica</th>
      <th>Promedio puntuación</th>
      <th>Última sesión</th>
      <th></th>`;
    try {
      const res = await fetch(`${API}/admin/sesiones/estudiantes`, { headers: authHeaders() });
      const data = await res.json();
      adminSesEstudiantes = Array.isArray(data) ? data : [];
      renderSesionesAdminEstudiantes(adminSesEstudiantes);
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-table" style="color:var(--red)">Error cargando sesiones de estudiantes</td></tr>';
    }
  } else {
    headRow.innerHTML = `
      <th>Docente</th>
      <th>Total comentarios</th>
      <th>Estudiantes</th>
      <th>Última retroalimentación</th>
      <th></th>
      <th></th>`;
    try {
      const res = await fetch(`${API}/admin/sesiones/docentes`, { headers: authHeaders() });
      const data = await res.json();
      adminSesDocentes = Array.isArray(data) ? data : [];
      renderSesionesAdminDocentes(adminSesDocentes);
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-table" style="color:var(--red)">Error cargando sesiones de docentes</td></tr>';
    }
  }
}

function renderSesionesAdminEstudiantes(data) {
  const tbody = document.getElementById('admin-ses-tbody');
  if (!tbody) return;
  tbody.innerHTML = data.length
    ? data.map(s => {
      const name = s.nombre || (s.usuario_id || '—').split('@')[0];
      const initial = name.charAt(0).toUpperCase();
      return `<tr>
        <td>
          <div class="hist-patient-cell">
            <div class="hist-avatar">${initial}</div>
            <div style="display:flex; flex-direction:column;">
              <strong>${name}</strong>
              <small style="color:var(--muted); font-size:11px;">${s.usuario_id || '—'}</small>
            </div>
          </div>
        </td>
        <td style="text-align:center; font-weight:600;">${s.total_sesiones || 0}</td>
        <td style="color:var(--muted); font-size:.85rem;">${s.minutos_totales != null ? s.minutos_totales + ' min' : '—'}</td>
        <td style="text-align:center;">
          ${s.puntuacion_promedio != null
          ? `<div class="hist-score">${s.puntuacion_promedio}<small>/100</small></div>`
          : '<span class="hist-score-empty">—</span>'}
        </td>
        <td style="font-size:.85rem;color:var(--muted);">${s.ultima_sesion ? formatDate(s.ultima_sesion) : '—'}</td>
        <td>
          <div class="hist-actions">
            <button class="btn-ghost" style="padding:6px 12px; font-size:.78rem;"
              onclick="verSesionesEstudianteAdmin('${s.usuario_id}')">Ver detalle</button>
          </div>
        </td>
      </tr>`}).join('')
    : '<tr><td colspan="6" class="empty-table">Sin sesiones registradas</td></tr>';
}

function renderSesionesAdminDocentes(data) {
  const tbody = document.getElementById('admin-ses-tbody');
  if (!tbody) return;
  tbody.innerHTML = data.length
    ? data.map(d => {
      const name = d.docente_nombre || (d.docente_email || '—').split('@')[0];
      const initial = name.charAt(0).toUpperCase();
      return `<tr>
        <td>
          <div class="hist-patient-cell">
            <div class="hist-avatar">${initial}</div>
            <div style="display:flex; flex-direction:column;">
              <strong>${name}</strong>
              <small style="color:var(--muted); font-size:11px;">${d.docente_email || '—'}</small>
            </div>
          </div>
        </td>
        <td style="text-align:center; font-weight:600;">${d.total_retro || 0}</td>
        <td style="text-align:center; font-weight:600;">${d.total_estudiantes || 0}</td>
        <td style="font-size:.85rem;color:var(--muted);">${d.ultima_retro ? formatDate(d.ultima_retro) : '—'}</td>
        <td>
          <div class="hist-actions">
            <button class="btn-ghost" style="padding:6px 12px; font-size:.78rem;"
              onclick="verDocenteEstudiantesAdmin('${d.docente_email}')">Ver estudiantes</button>
          </div>
        </td>
        <td></td>
      </tr>`}).join('')
    : '<tr><td colspan="6" class="empty-table">Sin retroalimentaciones registradas</td></tr>';
}

function filtrarSesiones() {
  const q = (document.getElementById('ses-search')?.value || '').toLowerCase();
  const estado = document.getElementById('ses-filter-estado')?.value || '';

  if (adminSesMode === 'estudiantes') {
    let data = adminSesEstudiantes || [];
    if (q) {
      data = data.filter(s =>
        (s.nombre || '').toLowerCase().includes(q) ||
        (s.usuario_id || '').toLowerCase().includes(q)
      );
    }
    if (estado === 'completada') {
      data = data.filter(s => (s.total_sesiones || 0) > 0);
    }
    renderSesionesAdminEstudiantes(data);
  } else {
    let data = adminSesDocentes || [];
    if (q) {
      data = data.filter(d =>
        (d.docente_nombre || '').toLowerCase().includes(q) ||
        (d.docente_email || '').toLowerCase().includes(q)
      );
    }
    renderSesionesAdminDocentes(data);
  }
}

async function verSesionesEstudianteAdmin(email) {
  openModal();
  const mc = document.getElementById('modal-content');
  if (!mc) return;
  mc.innerHTML = '<div class="spinner" style="margin:40px auto;"></div>';
  try {
    const res = await fetch(`${API}/admin/sesiones/estudiante/${encodeURIComponent(email)}`, { headers: authHeaders() });
    const data = await res.json();
    const nombre = (adminSesEstudiantes.find(s => s.usuario_id === email)?.nombre) || email.split('@')[0];
    mc.innerHTML = `
      <div class="modal-title">Sesiones de ${nombre}</div>
      <div class="modal-subtitle" style="margin-bottom:12px;">Historial completo de práctica con pacientes simulados</div>
      <div style="max-height:70vh;overflow-y:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:.85rem;">
          <thead>
            <tr style="background:rgba(255,255,255,.03);">
              <th style="padding:8px 10px;text-align:left;">Paciente</th>
              <th style="padding:8px 10px;text-align:left;">Fecha</th>
              <th style="padding:8px 10px;text-align:left;">Duración</th>
              <th style="padding:8px 10px;text-align:left;"># Sesión</th>
              <th style="padding:8px 10px;text-align:left;">Puntuación</th>
              <th style="padding:8px 10px;text-align:left;">Estado</th>
            </tr>
          </thead>
          <tbody>
            ${data.length ? data.map(s => `
              <tr style="border-top:1px solid var(--border);">
                <td style="padding:8px 10px;">${s.patient_name || '—'}</td>
                <td style="padding:8px 10px;color:var(--muted);">${s.inicio ? formatDate(s.inicio) : '—'}</td>
                <td style="padding:8px 10px;">${s.minutos != null ? s.minutos + ' min' : '—'}</td>
                <td style="padding:8px 10px;">${s.numero_sesion || '—'}</td>
                <td style="padding:8px 10px;">${s.puntuacion != null ? `<strong>${s.puntuacion}</strong>/100` : '—'}</td>
                <td style="padding:8px 10px;">
                  <span class="status-pill status-${s.alta ? 'completada' : (s.estado || 'activa')}">
                    ${s.alta ? 'Alta' : (s.estado || 'activa')}
                  </span>
                </td>
              </tr>`).join('') :
        `<tr><td colspan="6" style="padding:20px;text-align:center;color:var(--muted);">Este estudiante aún no tiene sesiones registradas.</td></tr>`}
          </tbody>
        </table>
      </div>
      <button class="modal-close" onclick="closeModal()" style="margin-top:16px;">Cerrar</button>`;
  } catch (e) {
    mc.innerHTML = '<div style="padding:20px;color:var(--red);">Error cargando las sesiones del estudiante.</div>';
  }
}

async function verDocenteEstudiantesAdmin(docenteEmail) {
  openModal();
  const mc = document.getElementById('modal-content');
  if (!mc) return;
  mc.innerHTML = '<div class="spinner" style="margin:40px auto;"></div>';
  try {
    const res = await fetch(`${API}/admin/sesiones/docente/${encodeURIComponent(docenteEmail)}`, { headers: authHeaders() });
    const data = await res.json();
    adminSesDocenteDetalle = Array.isArray(data) ? data : [];
    const docenteNombre = (adminSesDocentes.find(d => d.docente_email === docenteEmail)?.docente_nombre) || docenteEmail.split('@')[0];
    mc.innerHTML = `
      <div class="modal-title">Retroalimentaciones de ${docenteNombre}</div>
      <div class="modal-subtitle" style="margin-bottom:12px;">Estudiantes que han recibido comentarios de este docente</div>
      <div style="max-height:70vh;overflow-y:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:.85rem;">
          <thead>
            <tr style="background:rgba(255,255,255,.03);">
              <th style="padding:8px 10px;text-align:left;">Estudiante</th>
              <th style="padding:8px 10px;text-align:left;">Correo</th>
              <th style="padding:8px 10px;text-align:left;">Comentarios</th>
              <th style="padding:8px 10px;text-align:left;">Última retro</th>
              <th style="padding:8px 10px;text-align:left;"></th>
            </tr>
          </thead>
          <tbody>
            ${adminSesDocenteDetalle.length ? adminSesDocenteDetalle.map((e, idx) => `
              <tr style="border-top:1px solid var(--border);">
                <td style="padding:8px 10px;">${e.estudiante_nombre || e.estudiante_email.split('@')[0]}</td>
                <td style="padding:8px 10px;color:var(--muted);">${e.estudiante_email}</td>
                <td style="padding:8px 10px;">${e.total_comentarios || 0}</td>
                <td style="padding:8px 10px;color:var(--muted);">${e.ultima_fecha ? formatDate(e.ultima_fecha) : '—'}</td>
                <td style="padding:8px 10px;">
                  <button class="btn-detail" onclick="verComentariosDocenteEstudiante(${idx})">Ver comentarios</button>
                </td>
              </tr>`).join('') :
        `<tr><td colspan="5" style="padding:20px;text-align:center;color:var(--muted);">Este docente aún no ha dejado retroalimentaciones.</td></tr>`}
          </tbody>
        </table>
      </div>
      <button class="modal-close" onclick="closeModal()" style="margin-top:16px;">Cerrar</button>`;
  } catch (e) {
    mc.innerHTML = '<div style="padding:20px;color:var(--red);">Error cargando la información del docente.</div>';
  }
}

function verComentariosDocenteEstudiante(index) {
  const mc = document.getElementById('modal-content');
  if (!mc) return;
  const est = adminSesDocenteDetalle[index];
  if (!est) return;
  mc.innerHTML = `
    <div class="modal-title">Comentarios para ${est.estudiante_nombre || est.estudiante_email.split('@')[0]}</div>
    <div class="modal-subtitle" style="margin-bottom:12px;">Detalle de retroalimentaciones por sesión</div>
    <div style="max-height:70vh;overflow-y:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:.85rem;">
        <thead>
          <tr style="background:rgba(255,255,255,.03);">
            <th style="padding:8px 10px;text-align:left;">Fecha</th>
            <th style="padding:8px 10px;text-align:left;">Paciente</th>
            <th style="padding:8px 10px;text-align:left;">Sesión</th>
            <th style="padding:8px 10px;text-align:left;">Puntuación</th>
            <th style="padding:8px 10px;text-align:left;">Comentario</th>
          </tr>
        </thead>
        <tbody>
          ${est.comentarios && est.comentarios.length ? est.comentarios.map(c => `
            <tr style="border-top:1px solid var(--border);">
              <td style="padding:8px 10px;color:var(--muted);">${c.creado_en ? formatDate(c.creado_en) : '—'}</td>
              <td style="padding:8px 10px;">${c.patient_name || '—'}</td>
              <td style="padding:8px 10px;font-size:.78rem;color:var(--muted);">${c.sesion_id ? c.sesion_id.slice(0, 8) + '…' : '—'}</td>
              <td style="padding:8px 10px;">${c.puntuacion != null ? `<strong>${c.puntuacion}</strong>/100` : '—'}</td>
              <td style="padding:8px 10px;">${c.comentario || ''}</td>
            </tr>`).join('') :
      `<tr><td colspan="5" style="padding:20px;text-align:center;color:var(--muted);">No hay comentarios registrados para este estudiante.</td></tr>`}
        </tbody>
      </table>
    </div>
    <button class="modal-close" onclick="closeModal()" style="margin-top:16px;">Cerrar</button>`;
}

// ---- CONTABILIDAD ----
function loadContabilidadKpis() {
  const pagos = adminData.pagos || [];
  const total = pagos.reduce((s, p) => s + Number(p.monto || 0), 0);
  const inst = pagos.filter(p => p.tipo === 'institucional').reduce((s, p) => s + Number(p.monto || 0), 0);
  const part = pagos.filter(p => p.tipo === 'particular').reduce((s, p) => s + Number(p.monto || 0), 0);
  const ahora = new Date();
  const mes = pagos.filter(p => {
    if (!p.fecha) return false;
    const d = new Date(p.fecha);
    return d.getMonth() === ahora.getMonth() && d.getFullYear() === ahora.getFullYear();
  }).reduce((s, p) => s + Number(p.monto || 0), 0);

  document.getElementById('kpi-revenue').textContent = total ? '$' + total.toLocaleString() : '$0';
  document.getElementById('ck-total').textContent = '$' + total.toLocaleString();
  document.getElementById('ck-inst').textContent = '$' + inst.toLocaleString();
  document.getElementById('ck-part').textContent = '$' + part.toLocaleString();
  document.getElementById('ck-mes').textContent = '$' + mes.toLocaleString();
}

function filtrarPagos() {
  const tipo = document.getElementById('cont-filter-tipo')?.value || '';
  const mes = document.getElementById('cont-filter-mes')?.value || '';
  let pagos = adminData.pagos || [];
  if (tipo) pagos = pagos.filter(p => p.tipo === tipo);
  if (mes) pagos = pagos.filter(p => p.fecha?.startsWith(mes));
  const tbody = document.getElementById('cont-tbody');
  tbody.innerHTML = pagos.length
    ? pagos.map(p => {
      const status = (p.estado || 'pendiente').toLowerCase();
      return `<tr>
        <td>
          <div class="hist-date-box">
            <span class="hist-date-main">${formatDate(p.fecha)}</span>
          </div>
        </td>
        <td><strong>${p.origen || '—'}</strong></td>
        <td><span class="status-pill status-alta" style="font-size:10px;">${p.tipo || '—'}</span></td>
        <td><strong style="color:var(--teal-deep);font-size:1.05rem;">$${Number(p.monto || 0).toLocaleString()}</strong></td>
        <td style="font-size:.8rem;color:var(--muted)">${p.metodo || '—'}</td>
        <td style="font-size:.78rem;color:var(--muted);font-family:monospace;">${p.referencia || '—'}</td>
        <td><span class="status-pill status-${status === 'confirmado' ? 'completada' : 'activa'}">${status === 'confirmado' ? 'Confirmado' : 'Pendiente'}</span></td>
      </tr>`}).join('')
    : '<tr><td colspan="7" class="empty-table">Sin registros de pago</td></tr>';
}

async function registrarPago() {
  const pago = {
    tipo: document.getElementById('pago-tipo').value,
    origen: document.getElementById('pago-origen').value.trim(),
    monto: Number(document.getElementById('pago-monto').value) || 0,
    fecha: document.getElementById('pago-fecha').value,
    metodo: document.getElementById('pago-metodo').value,
    referencia: document.getElementById('pago-ref').value.trim(),
    estado: document.getElementById('pago-estado').value,
  };
  if (!pago.origen || !pago.monto) { showToast('Completa al menos el origen y el monto', true); return; }
  if (!pago.fecha) { showToast('La fecha es requerida', true); return; }

  const btn = document.querySelector('#modal-registro-pago .btn-accent');
  if (btn) { btn.disabled = true; btn.textContent = 'Guardando…'; }

  try {
    const res = await fetch(`${API}/admin/pagos`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(pago),
    });
    if (!res.ok) throw new Error(`Error ${res.status}`);
    closeAdminModal('modal-registro-pago');
    // Limpiar campos
    ['pago-origen', 'pago-monto', 'pago-fecha', 'pago-ref'].forEach(id => {
      document.getElementById(id).value = '';
    });
    await loadContabilidad();
    // Si hay institución abierta, refresca sus pagos también
    if (selectedInstId !== null) {
      renderInstPagos(adminData.instituciones[selectedInstId]?.nombre);
    }
    showToast('Pago registrado ✓');
  } catch (e) {
    showToast('Error al registrar: ' + e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Guardar pago'; }
  }
}

// ---- ADMIN MODAL HELPERS ----
function openAdminModal(id) {
  const el = document.getElementById(id);
  if (!el) return;
  // Use .open class for .modal-overlay elements (gives proper backdrop-filter)
  if (el.classList.contains('modal-overlay') || el.classList.contains('admin-modal-overlay')) {
    el.style.display = 'flex';
  } else {
    el.style.display = 'flex';
  }
  if (id === 'modal-analisis-objetivo' && !document.getElementById('ao-instruccion').value) {
    document.getElementById('ao-instruccion').value = 'Eres un supervisor clínico experto en psicología con conocimiento en múltiples especialidades...\n\n[Edita aquí el prompt completo del análisis objetivo global]';
  }
}

function openModal(id) {
  if (id) { openAdminModal(id); return; }
  document.getElementById('modal-overlay').classList.add('active');
  document.getElementById('modal-content').innerHTML = '<div class="spinner"></div>';
}

function closeAdminModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

// ---- DETAIL TABS ----
function detailTab(btn, panelId) {
  btn.closest('.admin-panel, #inst-detail').querySelectorAll('.dtab').forEach(b => b.classList.remove('active'));
  btn.closest('.admin-panel, #inst-detail').querySelectorAll('.dtab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(panelId).classList.add('active');
}

function subTab(btn, panelId) {
  btn.closest('.dtab-panel').querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
  btn.closest('.dtab-panel').querySelectorAll('.stab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(panelId).classList.add('active');
}

function handleContratoFile(input) {
  const fname = input.files[0]?.name || '';
  document.getElementById('contrato-file-name').textContent = fname || 'Haz clic para cargar el contrato PDF';
}

// ---- TOAST PREMIUM ----
function showToast(msg, isError = false) {
  let t = document.getElementById('premium-toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'premium-toast';
    t.className = 'toast-premium';
    t.innerHTML = `
      <div class="toast-icon"></div>
      <div class="toast-msg"></div>
    `;
    document.body.appendChild(t);
  }

  t.className = 'toast-premium' + (isError ? ' error' : '');
  t.querySelector('.toast-icon').textContent = isError ? '✕' : '✓';
  t.querySelector('.toast-msg').textContent = msg;

  // Forzar reflow para reiniciar la animación
  t.classList.remove('visible');
  void t.offsetWidth;
  t.classList.add('visible');

  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove('visible'), isError ? 5000 : 3500);
}

// Keep deleteUser from old admin
async function deleteUser(email) {
  showConfirmModal({
    title: '¿Eliminar usuario?',
    msg: `¿Estás seguro de eliminar al usuario <strong>${email}</strong>? Esta acción es irreversible.`,
    icon: '🚫',
    confirmText: 'Sí, eliminar',
    onConfirm: async () => {
      try {
        await fetch(`${API}/admin/usuario/${encodeURIComponent(email)}`, { method: 'DELETE', headers: authHeaders() });
        loadAdmin();
        loadParticulares();
        showToast('Usuario eliminado');
      } catch (e) { alert('Error al eliminar el usuario.'); }
    }
  });
}

function scoreCls(s) {
  if (s == null) return '';
  if (s >= 75) return 'score-high';
  if (s >= 50) return 'score-mid';
  return 'score-low';
}

// ── KEYBOARD ─────────────────────────────────────────────
document.addEventListener('keydown', e => {
  const onLogin = document.getElementById('screen-login').classList.contains('active');
  const onChat = document.getElementById('screen-chat').classList.contains('active');
  if (e.key === 'Enter' && !e.shiftKey) {
    if (onLogin && (document.activeElement.id === 'login-email' || document.activeElement.id === 'login-password')) doLogin();
    if (onChat && document.activeElement.id === 'user-input') { e.preventDefault(); sendMessage(); }
  }
});