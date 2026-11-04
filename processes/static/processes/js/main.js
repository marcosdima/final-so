const dataEl = document.getElementById('process-data');

// Modos (Demostración vs Manual)
const tabDemo = document.getElementById('tab-demo');
const tabManual = document.getElementById('tab-manual');
const controlsDemo = document.getElementById('controls-demo');
const controlsManual = document.getElementById('controls-manual');

// Controles demo
const btnPlay = document.getElementById('btn-play');
const btnPlayLabel = document.getElementById('btn-play-label');
const btnPrevStep = document.getElementById('btn-prev-step');
const btnStep = document.getElementById('btn-step');
const btnResetDemo = document.getElementById('btn-reset-demo');
const speedButtons = document.querySelectorAll('.btn-speed-pill');

// Controles manual
const btnAddProc = document.getElementById('btn-add-proc');
const btnResetManual = document.getElementById('btn-reset-manual');
const btnTick = document.getElementById('btn-tick');
const clockDisplay = document.getElementById('clock-display');
const actionButtons = document.querySelectorAll('.process-action-buttons .btn-act');

// Selector de algoritmo en el footer
const algoChips = document.querySelectorAll('.btn-algo-chip');

// Modal de Teoría
const btnOpenTheory = document.getElementById('btn-open-theory');
const theoryModal = document.getElementById('theory-modal');
const btnCloseModal = document.getElementById('btn-close-modal');
const modalTabs = document.querySelectorAll('.btn-modal-tab');
const tabContents = document.querySelectorAll('.theory-tab-content');

// Inspector de PCB flotante
const pcbInspector = document.getElementById('pcb-inspector');
const btnClosePcb = document.getElementById('btn-close-pcb');
const pcbPidTitle = document.getElementById('pcb-pid-title');
const pcbStateVal = document.getElementById('pcb-state-val');
const pcbPriorityVal = document.getElementById('pcb-priority-val');
const pcbBurstVal = document.getElementById('pcb-burst-val');
const pcbRemainingVal = document.getElementById('pcb-remaining-val');
const pcbQuantumVal = document.getElementById('pcb-quantum-val');
const pcbStepButtons = document.querySelectorAll('.btn-pcb-step');

// Dialog de alerta del SO
const soDialog = document.getElementById('so-alert-dialog');
const soDialogTitle = document.getElementById('so-dialog-title');
const soDialogMsg = document.getElementById('so-dialog-msg');
const btnCloseSoDialog = document.getElementById('btn-close-so-dialog');

function showSoAlert(title, message) {
  if (soDialog) {
    if (soDialogTitle) soDialogTitle.textContent = title;
    if (soDialogMsg) soDialogMsg.textContent = message;
    if (typeof soDialog.showModal === 'function') {
      soDialog.showModal();
    } else {
      alert(`${title}: ${message}`);
    }
  } else {
    alert(`${title}: ${message}`);
  }
}

if (btnCloseSoDialog && soDialog) {
  btnCloseSoDialog.addEventListener('click', () => soDialog.close());
}

// Narrador / feedback de pasos de la CPU
const narrationTag = document.getElementById('narration-tag');
const narrationText = document.getElementById('narration-text');

// Estado del cliente (event-sourcing)
let structure = dataEl ? JSON.parse(dataEl.textContent) : null;
let log = structure?.events ? [...structure.events] : [];
const seed = structure?.meta?.seed ?? null;
const actionUrl = structure?.meta?.action_url || '/processes/api/action/';

let currentMode = 'demo'; // 'demo' | 'manual'
let currentAlgorithm = 'FCFS'; // 'FCFS' | 'RR' | 'PRIORITY'
let selectedPid = null;
let currentSpeed = 3000;

// Tokens de procesos
const tokens = new Map();

function ensureToken(pid) {
  let el = tokens.get(pid);
  if (!el) {
    el = document.createElement('div');
    el.className = 'proc-token';
    el.id = 'proc-token-' + pid;
    el.dataset.pid = String(pid);
    el.textContent = 'P' + pid;
    el.title = `Proceso P${pid} (Clic para ver PCB)`;
    el.addEventListener('click', () => {
      selectProcess(pid);
    });
    tokens.set(pid, el);
  }
  return el;
}

function syncPcbStepButtons(pcb) {
  const canEdit = currentMode === 'manual' && pcb && pcb.state !== 'TERMINATED';
  pcbStepButtons.forEach((btn) => {
    btn.classList.toggle('is-hidden', !canEdit);
  });
}

function selectProcess(pid) {
  selectedPid = pid;
  tokens.forEach((el, p) => el.classList.toggle('proc-selected', p === pid));
  // Actualizar disponibilidad de botones
  updateActionButtonsAvailability();

  // Habilitar o deshabilitar botón Tick según si hay alguien en CPU
  if (btnTick) {
    btnTick.disabled = (structure?.running === null);
  }

  if (pid != null && structure?.pcbs?.[pid]) {
    const pcb = structure.pcbs[pid];
    if (pcbInspector) {
      pcbInspector.classList.remove('is-hidden');
      if (pcbPidTitle) pcbPidTitle.textContent = `P${pid}`;
      if (pcbStateVal) pcbStateVal.textContent = pcb.state;
      if (pcbPriorityVal) pcbPriorityVal.textContent = String(pcb.priority);
      if (pcbBurstVal) pcbBurstVal.textContent = `${pcb.burst_time} ticks`;
      if (pcbRemainingVal) pcbRemainingVal.textContent = `${pcb.remaining_time} ticks`;
      if (pcbQuantumVal) {
        if (structure?.algorithm === 'RR') {
          pcbQuantumVal.textContent = `${pcb.quantum_used} / ${structure.quantum || 2}`;
        } else {
          pcbQuantumVal.textContent = 'N/A (No aplica)';
        }
      }
      syncPcbStepButtons(pcb);
      // Posicionar inspector cerca del token clickeado
      setTimeout(() => positionInspectorNearToken(pid), 20);
    }
  } else if (pcbInspector) {
    pcbInspector.classList.add('is-hidden');
  }
}

function positionInspectorNearToken(pid) {
  if (!pcbInspector || pid == null) return;
  const token = tokens.get(pid);
  if (!token || !diagramWrap) return;

  const tokenRect = token.getBoundingClientRect();
  const wrapRect = diagramWrap.getBoundingClientRect();

  // Posición relativa al wrap
  let left = tokenRect.right - wrapRect.left + 12;
  let top = tokenRect.top - wrapRect.top - 10;

  // Si se pasa hacia la derecha, poner a la izquierda del token
  if (left + 260 > wrapRect.width) {
    left = tokenRect.left - wrapRect.left - 262;
  }
  // Si se pasa hacia la izquierda (en pantallas chicas), centrar
  if (left < 10) {
    left = Math.max(10, (wrapRect.width - 250) / 2);
    top = tokenRect.bottom - wrapRect.top + 10;
  }
  // Limitar top para no salirse arriba o abajo
  top = Math.max(10, Math.min(top, wrapRect.height - 230));

  pcbInspector.style.left = `${left}px`;
  pcbInspector.style.top = `${top}px`;
}

function updateActionButtonsAvailability() {
  if (currentMode !== 'manual') return;
  const st = selectedPid != null && structure?.states ? structure.states[selectedPid] : null;
  const isRunningAvailable = structure?.running === null;

  actionButtons.forEach((btn) => {
    const act = btn.dataset.action;
    let enabled = false;

    if (act === 'dispatch') {
      if (isRunningAvailable && (structure?.ready_queue?.length > 0 || (selectedPid != null && st === 'READY'))) {
        enabled = true;
      }
    } else if (selectedPid != null && st) {
      if (act === 'admit' && st === 'NEW') enabled = true;
      if (act === 'interrupt' && st === 'RUNNING' && structure?.running === selectedPid) enabled = true;
      if (act === 'io_wait' && st === 'RUNNING' && structure?.running === selectedPid) enabled = true;
      if (act === 'io_complete' && st === 'WAITING') enabled = true;
      if (act === 'exit' && st === 'RUNNING' && structure?.running === selectedPid) enabled = true;
    }
    btn.disabled = !enabled;
  });
}

function nodeForState(state) {
  return document.getElementById('list-' + state);
}

function render(s) {
  if (!s) return;

  if (clockDisplay && s.current_time !== undefined) {
    clockDisplay.textContent = String(s.current_time);
  }

  // Actualizar chips de algoritmo
  if (s.algorithm) {
    currentAlgorithm = s.algorithm;
    algoChips.forEach((chip) => {
      chip.classList.toggle('active', chip.dataset.algo === s.algorithm);
    });
  }

  // 1. Posición actual (FIRST)
  const firstRects = new Map();
  tokens.forEach((el, pid) => {
    firstRects.set(pid, el.getBoundingClientRect());
  });

  // 2. Nodo activo (quién está en CPU)
  for (const st of ['NEW', 'READY', 'RUNNING', 'WAITING', 'TERMINATED']) {
    const node = document.getElementById('node-' + st);
    if (node) {
      node.classList.toggle('active', s.running !== null && s.states[s.running] === st);
    }
  }

  // 3. Mover tokens a su contenedor respetando el orden exacto de cada cola (LAST)
  const orderedGroups = {
    NEW: s.pids.filter((pid) => s.states[pid] === 'NEW'),
    READY: Array.isArray(s.ready_queue) ? s.ready_queue : [],
    RUNNING: s.running != null ? [s.running] : [],
    WAITING: Array.isArray(s.waiting_queue) ? s.waiting_queue : [],
    TERMINATED: Array.isArray(s.terminated) ? s.terminated : [],
  };

  for (const [state, pidList] of Object.entries(orderedGroups)) {
    const container = nodeForState(state);
    if (!container) continue;
    pidList.forEach((pid, idx) => {
      const token = ensureToken(pid);
      token.classList.toggle('proc-running', state === 'RUNNING');
      token.classList.toggle('proc-waiting', state === 'WAITING');
      token.classList.toggle('proc-terminated', state === 'TERMINATED');
      token.classList.toggle('proc-selected', pid === selectedPid);
      token.classList.toggle('proc-next', state === 'READY' && pid === s.next_scheduled);
      if (container.children[idx] !== token) {
        container.insertBefore(token, container.children[idx] || null);
      }
    });
  }

  // 4. Animación FLIP
  requestAnimationFrame(() => {
    tokens.forEach((el, pid) => {
      const last = el.getBoundingClientRect();
      const first = firstRects.get(pid);
      if (!first) {
        el.style.opacity = '0';
        el.style.transform = 'scale(0.7)';
        requestAnimationFrame(() => {
          el.style.transition = 'opacity 0.35s ease, transform 0.35s ease';
          el.style.opacity = '1';
          el.style.transform = '';
        });
        return;
      }
      const dx = first.left - last.left;
      const dy = first.top - last.top;
      if (dx === 0 && dy === 0) return;
      el.style.transition = 'none';
      el.style.transform = `translate(${dx}px, ${dy}px)`;
      void el.offsetWidth;
      el.style.transition = 'transform 0.55s cubic-bezier(0.22, 1, 0.36, 1)';
      el.style.transform = '';
    });
  });

  // Actualizar inspector si el proceso seleccionado cambió
  if (selectedPid != null && s.pcbs?.[selectedPid]) {
    const pcb = s.pcbs[selectedPid];
    if (pcbStateVal) pcbStateVal.textContent = pcb.state;
    if (pcbPriorityVal) pcbPriorityVal.textContent = String(pcb.priority);
    if (pcbBurstVal) pcbBurstVal.textContent = `${pcb.burst_time} ticks`;
    if (pcbRemainingVal) pcbRemainingVal.textContent = `${pcb.remaining_time} ticks`;
    if (pcbQuantumVal) {
      if (s.algorithm === 'RR') {
        pcbQuantumVal.textContent = `${pcb.quantum_used} / ${s.quantum || 2}`;
      } else {
        pcbQuantumVal.textContent = 'N/A (No aplica)';
      }
    }
    syncPcbStepButtons(pcb);
    setTimeout(() => positionInspectorNearToken(selectedPid), 600);
  }

  // Actualizar disponibilidad de botones
  updateActionButtonsAvailability();

  // Habilitar o deshabilitar botón Tick según si hay alguien en CPU
  if (btnTick) {
    btnTick.disabled = (s.running === null);
  }
  drawArrows();
}

// ------------------------------------------------------------------
// Flechas del diagrama
// ------------------------------------------------------------------
const arrowsSvg = document.querySelector('.proc-arrows');
const diagramWrap = document.querySelector('.proc-diagram-wrap');
const SVG_NS = 'http://www.w3.org/2000/svg';

const EDGE_NORMAL = { top: [0, -1], bottom: [0, 1], left: [-1, 0], right: [1, 0] };

const ARROWS = [
  { from: ['NEW', 'bottom'], to: ['READY', 'left'], dist: 70, label: 'admitir', labelOffset: 0 },
  { from: ['READY', 'right'], to: ['RUNNING', 'left'], dist: 60, bow: 26, label: 'despachar', labelOffset: 22 },
  { from: ['RUNNING', 'top'], to: ['READY', 'top'], dist: 95, label: 'interrumpir', labelOffset: 22 },
  { from: ['RUNNING', 'right'], to: ['TERMINATED', 'bottom'], dist: 60, label: 'salir', labelOffset: 0 },
  { from: ['RUNNING', 'bottom'], to: ['WAITING', 'right'], dist: 45, label: 'E/S o evento espera', labelOffset: 0 },
  { from: ['WAITING', 'left'], to: ['READY', 'bottom'], dist: 60, label: 'E/S o evento fin', labelOffset: 0 },
];

function arrowAnchor([state, side]) {
  const node = document.getElementById('node-' + state);
  const svgRect = arrowsSvg.getBoundingClientRect();
  const r = node.getBoundingClientRect();
  const x = r.left - svgRect.left;
  const y = r.top - svgRect.top;
  switch (side) {
    case 'top': return { x: x + r.width / 2, y };
    case 'bottom': return { x: x + r.width / 2, y: y + r.height };
    case 'left': return { x, y: y + r.height / 2 };
    case 'right': return { x: x + r.width, y: y + r.height / 2 };
    default: return { x: x + r.width / 2, y: y + r.height / 2 };
  }
}

function bezierInfo(ctrl, t) {
  const n = ctrl.length - 1;
  const pt = { x: 0, y: 0 };
  for (let i = 0; i <= n; i++) {
    let c = 1;
    for (let j = 1; j <= i; j++) c = (c * (n - i + j)) / j;
    const w = c * Math.pow(1 - t, n - i) * Math.pow(t, i);
    pt.x += ctrl[i].x * w;
    pt.y += ctrl[i].y * w;
  }
  return pt;
}

function bezierTangent(ctrl, t) {
  const e = 0.01;
  const a = bezierInfo(ctrl, Math.max(0, t - e));
  const b = bezierInfo(ctrl, Math.min(1, t + e));
  return { x: b.x - a.x, y: b.y - a.y };
}

function arrowPath(a) {
  const p1 = arrowAnchor(a.from);
  const p2 = arrowAnchor(a.to);
  const n1 = EDGE_NORMAL[a.from[1]];
  const n2 = EDGE_NORMAL[a.to[1]];
  const dist = a.dist ?? 50;

  const c1 = { x: p1.x + n1[0] * dist, y: p1.y + n1[1] * dist };
  const c2 = { x: p2.x + n2[0] * dist, y: p2.y + n2[1] * dist };

  if (a.bow) {
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const len = Math.hypot(dx, dy) || 1;
    const px = -dy / len;
    const py = dx / len;
    c1.x += px * a.bow;
    c1.y += py * a.bow;
    c2.x += px * a.bow;
    c2.y += py * a.bow;
  }

  const ctrl = [p1, c1, c2, p2];
  const d = `M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y} ${p2.x} ${p2.y}`;

  const mid = bezierInfo(ctrl, 0.5);
  const tan = bezierTangent(ctrl, 0.5);
  const len = Math.hypot(tan.x, tan.y) || 1;
  const nx = -tan.y / len;
  const ny = tan.x / len;
  const off = a.labelOffset ?? 16;
  return {
    d,
    label: {
      x: mid.x + nx * off,
      y: mid.y + ny * off,
      anchor: a.labelAnchor || 'middle',
    },
  };
}

function drawArrows() {
  if (!arrowsSvg) return;
  if (getComputedStyle(arrowsSvg).display === 'none') return;
  arrowsSvg.querySelectorAll('.arrow-line, .arrow-label, .arrow-label-bg').forEach((el) => el.remove());
  for (const a of ARROWS) {
    const { d, label } = arrowPath(a);
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('class', 'arrow-line');
    path.setAttribute('d', d);
    path.setAttribute('marker-end', 'url(#proc-arrowhead)');
    path.dataset.label = a.label;
    arrowsSvg.appendChild(path);

    const text = document.createElementNS(SVG_NS, 'text');
    text.setAttribute('class', 'arrow-label');
    text.setAttribute('x', String(label.x));
    text.setAttribute('y', String(label.y));
    text.setAttribute('text-anchor', label.anchor);
    text.textContent = a.label;
    arrowsSvg.appendChild(text);

    const bb = text.getBBox();
    const rect = document.createElementNS(SVG_NS, 'rect');
    rect.setAttribute('class', 'arrow-label-bg');
    rect.setAttribute('x', String(bb.x - 4));
    rect.setAttribute('y', String(bb.y - 2));
    rect.setAttribute('width', String(bb.width + 8));
    rect.setAttribute('height', String(bb.height + 4));
    rect.setAttribute('rx', '4');
    arrowsSvg.insertBefore(rect, text);
  }
}

// ------------------------------------------------------------------
// API Stateless
// ------------------------------------------------------------------
async function applyEvent(event) {
  try {
    const res = await fetch(actionUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'apply', payload: { events: log, event } }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    structure = data.state;
    log = structure.events;
    render(structure);
    return data.result;
  } catch (e) {
    setNarration('Error de comunicación', 'No se pudo aplicar el evento en el servidor.');
    return null;
  }
}

async function rebuildWithEvents(eventsList) {
  try {
    const res = await fetch(actionUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'apply', payload: { events: eventsList } }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    structure = data.state;
    log = structure.events;
    // Remover tokens que ya no existan en el estado reconstruido
    const validPids = new Set(structure.pids);
    tokens.forEach((el, pid) => {
      if (!validPids.has(pid)) {
        el.remove();
        tokens.delete(pid);
      }
    });
    if (selectedPid != null && !validPids.has(selectedPid)) {
      selectedPid = null;
      if (pcbInspector) pcbInspector.classList.add('is-hidden');
    }
    render(structure);
    return true;
  } catch (e) {
    setNarration('Error de comunicación', 'No se pudo reconstruir el estado.');
    return false;
  }
}

async function resetSimulation() {
  try {
    const res = await fetch(actionUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'apply', payload: { events: [] } }),
    });
    const data = await res.json();
    structure = data.state;
    log = [];
    selectedPid = null;
    if (pcbInspector) pcbInspector.classList.add('is-hidden');
    tokens.forEach((el) => el.remove());
    tokens.clear();
    render(structure);
  } catch (e) {
    setNarration('Error de comunicación', 'No se pudo reiniciar la simulación.');
  }
}

// ------------------------------------------------------------------
// GUIONES DIDÁCTICOS ESPECÍFICOS POR ALGORITMO
// ------------------------------------------------------------------

// 1. Guion FCFS: No Preemptivo puro. Sin interrupciones por quantum.
const SCRIPT_FCFS = [
  {
    events: [
      { type: 'set_algorithm', payload: { algorithm: 'FCFS' } },
      { type: 'create', pid: 1, priority: 3, burst_time: 3 },
      { type: 'create', pid: 2, priority: 2, burst_time: 4 },
      { type: 'create', pid: 3, priority: 1, burst_time: 2 },
    ],
    tag: 'FCFS · Creación',
    text: 'Llegan P1, P2 y P3 a NEW. Cada uno recibe su PCB con estado y tiempo de ráfaga estimado.',
  },
  {
    events: [{ type: 'admit', pid: 1 }, { type: 'admit', pid: 2 }, { type: 'admit', pid: 3 }],
    transition: 'admitir',
    tag: 'FCFS · Admisión',
    text: 'El planificador de largo plazo admite los tres procesos a READY. La cola de listos queda en estricto orden de llegada: [P1, P2, P3].',
  },
  {
    events: [{ type: 'dispatch', pid: 1 }],
    transition: 'despachar',
    tag: 'FCFS · Despachar P1',
    text: 'El planificador FCFS elige a P1 por ser el primero en la cola. P1 pasa a RUNNING y obtiene la CPU.',
  },
  {
    events: [{ type: 'io_wait', pid: 1 }],
    transition: 'E/S o evento espera',
    tag: 'FCFS · Bloqueo de P1',
    text: 'P1 realiza una llamada al sistema solicitando E/S. Se bloquea voluntariamente y pasa a WAITING, liberando la CPU.',
  },
  {
    events: [{ type: 'dispatch', pid: 2 }],
    transition: 'despachar',
    tag: 'FCFS · Despachar P2',
    text: 'Con la CPU libre, FCFS despacha al siguiente en la cola de listos: P2.',
  },
  {
    events: [{ type: 'io_complete', pid: 1 }],
    transition: 'E/S o evento fin',
    tag: 'FCFS · E/S completada',
    text: 'La controladora de disco genera una interrupción de E/S: P1 termina su operación y pasa a READY al final de la cola [P3, P1]. P2 sigue en la CPU (FCFS no desaloja).',
  },
  {
    events: [{ type: 'exit', pid: 2 }],
    transition: 'salir',
    tag: 'FCFS · Salida de P2',
    text: 'P2 completa toda su ráfaga sin interrupciones. Pasa a TERMINATED y destruye su PCB.',
  },
  {
    events: [{ type: 'dispatch', pid: 3 }],
    transition: 'despachar',
    tag: 'FCFS · Despachar P3',
    text: 'La CPU queda libre. En la cola de listos estaban [P3, P1], por lo que el planificador despacha a P3.',
  },
  {
    events: [{ type: 'exit', pid: 3 }],
    transition: 'salir',
    tag: 'FCFS · Salida de P3',
    text: 'P3 termina su ejecución y pasa a TERMINATED.',
  },
  {
    events: [{ type: 'dispatch', pid: 1 }],
    transition: 'despachar',
    tag: 'FCFS · Despachar P1',
    text: 'Solo queda P1 en READY: el planificador lo despacha por última vez.',
  },
  {
    events: [{ type: 'exit', pid: 1 }],
    transition: 'salir',
    tag: 'FCFS · Finalizado',
    text: 'P1 termina con éxito. ¡Demostración de FCFS finalizada!',
  },
];

// 2. Guion Round Robin: Preemptivo por Quantum (q = 2 ticks).
const SCRIPT_RR = [
  {
    events: [
      { type: 'set_algorithm', payload: { algorithm: 'RR', quantum: 2 } },
      { type: 'create', pid: 1, burst_time: 4 },
      { type: 'create', pid: 2, burst_time: 3 },
    ],
    tag: 'Round Robin · Llegada',
    text: 'Llegan P1 (ráfaga de 4) y P2 (ráfaga de 3). Se configura el planificador Round Robin con Quantum = 2 ticks.',
  },
  {
    events: [{ type: 'admit', pid: 1 }, { type: 'admit', pid: 2 }],
    transition: 'admitir',
    tag: 'Round Robin · Admisión',
    text: 'P1 y P2 son admitidos a READY. Cola de listos: [P1, P2].',
  },
  {
    events: [{ type: 'dispatch', pid: 1 }],
    transition: 'despachar',
    tag: 'Round Robin · Despacho P1',
    text: 'El planificador asigna la CPU a P1 e inicia su cuenta regresiva de quantum.',
  },
  {
    events: [{ type: 'interrupt', pid: 1 }],
    transition: 'interrumpir',
    tag: 'Round Robin · Quantum Expirado',
    text: '¡El temporizador expira! P1 agotó su quantum de 2 ticks. El SO lo desaloja con una interrupción de reloj y lo encola al final de READY: [P2, P1].',
  },
  {
    events: [{ type: 'dispatch', pid: 2 }],
    transition: 'despachar',
    tag: 'Round Robin · Despacho P2',
    text: 'La CPU se le asigna equitativamente a P2.',
  },
  {
    events: [{ type: 'interrupt', pid: 2 }],
    transition: 'interrumpir',
    tag: 'Round Robin · Quantum Expirado',
    text: 'P2 consume sus 2 ticks de quantum y es interrumpido, volviendo a READY. La cola queda [P1, P2].',
  },
  {
    events: [{ type: 'dispatch', pid: 1 }],
    transition: 'despachar',
    tag: 'Round Robin · Despacho P1',
    text: 'Le vuelve a tocar el turno a P1 para ejecutar los 2 ticks restantes de su ráfaga.',
  },
  {
    events: [{ type: 'exit', pid: 1 }],
    transition: 'salir',
    tag: 'Round Robin · Salida P1',
    text: 'P1 completa su trabajo dentro del segundo quantum y pasa a TERMINATED.',
  },
  {
    events: [{ type: 'dispatch', pid: 2 }],
    transition: 'despachar',
    tag: 'Round Robin · Despacho P2',
    text: 'P2 toma la CPU para su último tick restante.',
  },
  {
    events: [{ type: 'exit', pid: 2 }],
    transition: 'salir',
    tag: 'Round Robin · Finalizado',
    text: 'P2 finaliza. ¡Demostración de reparto equitativo con Round Robin completada!',
  },
];

// 3. Guion Prioridades: La cola READY se auto-ordena por el nivel de prioridad (1 = Máxima).
const SCRIPT_PRIORITY = [
  {
    events: [
      { type: 'set_algorithm', payload: { algorithm: 'PRIORITY' } },
      { type: 'create', pid: 1, priority: 3, burst_time: 3 },
      { type: 'create', pid: 2, priority: 1, burst_time: 2 },
      { type: 'create', pid: 3, priority: 2, burst_time: 4 },
    ],
    tag: 'Prioridad · Llegada',
    text: 'Llegan P1 (Pri: 3 Baja), P2 (Pri: 1 Crítica) y P3 (Pri: 2 Media). Algoritmo activo: Prioridades.',
  },
  {
    events: [{ type: 'admit', pid: 1 }, { type: 'admit', pid: 2 }, { type: 'admit', pid: 3 }],
    transition: 'admitir',
    tag: 'Prioridad · Reordenamiento',
    text: 'Al admitirlos, el planificador no encola por orden de llegada, sino que reordena READY por prioridad: [P2 (Pri: 1), P3 (Pri: 2), P1 (Pri: 3)].',
  },
  {
    events: [{ type: 'dispatch', pid: 2 }],
    transition: 'despachar',
    tag: 'Prioridad · Despacho P2',
    text: 'P2 tiene la máxima prioridad (1): el planificador lo despacha antes que a P1 a pesar de que P1 llegó primero.',
  },
  {
    events: [{ type: 'exit', pid: 2 }],
    transition: 'salir',
    tag: 'Prioridad · Salida P2',
    text: 'P2 termina rápidamente su tarea crítica y pasa a TERMINATED.',
  },
  {
    events: [{ type: 'dispatch', pid: 3 }],
    transition: 'despachar',
    tag: 'Prioridad · Despacho P3',
    text: 'La cola de listos tiene a P3 (Pri: 2) y P1 (Pri: 3). El planificador elige a P3.',
  },
  {
    events: [{ type: 'exit', pid: 3 }],
    transition: 'salir',
    tag: 'Prioridad · Salida P3',
    text: 'P3 finaliza con éxito.',
  },
  {
    events: [{ type: 'dispatch', pid: 1 }],
    transition: 'despachar',
    tag: 'Prioridad · Despacho P1',
    text: 'Finalmente, sin procesos de mayor prioridad en cola, se despacha a P1.',
  },
  {
    events: [{ type: 'exit', pid: 1 }],
    transition: 'salir',
    tag: 'Prioridad · Finalizado',
    text: 'P1 termina su ciclo. ¡Demostración de planificación por Prioridades completada!',
  },
];

function getActiveScript() {
  if (currentAlgorithm === 'RR') return SCRIPT_RR;
  if (currentAlgorithm === 'PRIORITY') return SCRIPT_PRIORITY;
  return SCRIPT_FCFS;
}

let stepIndex = 0;
let playing = false;
let timer = null;

function setNarration(tag, text, isError = false) {
  if (narrationTag) {
    narrationTag.textContent = tag;
    narrationTag.style.color = isError ? '#f87171' : 'var(--active-blue)';
  }
  if (narrationText) {
    narrationText.textContent = text;
    narrationText.classList.remove('anim');
    void narrationText.offsetWidth;
    narrationText.classList.add('anim');
  }
}

function highlightArrow(label) {
  if (!arrowsSvg) return;
  arrowsSvg.classList.toggle('has-highlight', Boolean(label));
  arrowsSvg.querySelectorAll('.arrow-line').forEach((p) => {
    p.classList.toggle('arrow-active', Boolean(label) && p.dataset.label === label);
  });
}

function setPlaying(on) {
  playing = on;
  if (btnPlay) {
    btnPlay.classList.toggle('is-playing', on);
    btnPlay.classList.toggle('is-paused', !on);
    btnPlay.setAttribute('aria-pressed', String(on));
  }
  if (btnPlayLabel) btnPlayLabel.textContent = on ? 'Pausar' : 'Reproducir';
}

function updateDemoStepButtons() {
  const script = getActiveScript();
  if (btnPrevStep) {
    btnPrevStep.disabled = stepIndex <= 0;
  }
  if (btnStep) {
    btnStep.disabled = stepIndex >= script.length;
  }
}

async function runStep() {
  const script = getActiveScript();
  if (stepIndex >= script.length) {
    finishDemo();
    updateDemoStepButtons();
    return false;
  }
  const step = script[stepIndex++];
  for (const ev of step.events) {
    const result = await applyEvent(ev);
    if (result && !result.applied) {
      setNarration('Error en el guion', `El evento ${ev.type} no se aplicó: ${result.reason}`, true);
      updateDemoStepButtons();
      return false;
    }
  }
  highlightArrow(step.transition || null);
  setNarration(step.tag, step.text);
  updateDemoStepButtons();

  if (stepIndex >= script.length) {
    setPlaying(false);
  }
  return true;
}

async function runPrevStep() {
  if (stepIndex <= 0) return false;
  setPlaying(false);
  clearTimeout(timer);
  stepIndex -= 1;

  if (stepIndex === 0) {
    await resetDemo();
    return true;
  }

  const script = getActiveScript();
  const accumulatedEvents = [];
  for (let i = 0; i < stepIndex; i++) {
    accumulatedEvents.push(...script[i].events);
  }
  await rebuildWithEvents(accumulatedEvents);
  const currentStep = script[stepIndex - 1];
  highlightArrow(currentStep.transition || null);
  setNarration(currentStep.tag, currentStep.text);
  updateDemoStepButtons();
  return true;
}

function scheduleNext() {
  clearTimeout(timer);
  if (!playing) return;
  timer = setTimeout(async () => {
    const ok = await runStep();
    if (ok && playing) scheduleNext();
    else setPlaying(false);
  }, currentSpeed);
}

async function playFromHere() {
  setPlaying(true);
  const ok = await runStep();
  if (ok && playing) scheduleNext();
  else setPlaying(false);
}

function finishDemo() {
  setPlaying(false);
  highlightArrow(null);
  setNarration('Fin del guion', `Demostración de ${currentAlgorithm} completada. Pulsa «Reiniciar» para repetirla o cambia de algoritmo.`);
}

async function resetDemo() {
  clearTimeout(timer);
  setPlaying(false);
  highlightArrow(null);
  stepIndex = 0;
  updateDemoStepButtons();
  await resetSimulation();
  setNarration(
    `${currentAlgorithm} · Inicio`,
    `Simulación reiniciada para ${currentAlgorithm}. Pulsa «Paso a paso» para avanzar o «Reproducir» para animación automática.`
  );
}

// ------------------------------------------------------------------
// Modo Manual: Eventos interactivos del usuario
// ------------------------------------------------------------------
async function addManualProcess() {
  const nextPid = (structure?.pids?.length ? Math.max(...structure.pids) : 0) + 1;
  const priority = Math.floor(Math.random() * 3) + 1;
  const burst = Math.floor(Math.random() * 4) + 2;

  const result = await applyEvent({
    type: 'create',
    pid: nextPid,
    priority,
    burst_time: burst,
  });

  if (result && result.applied) {
    selectProcess(nextPid);
    setNarration(
      `P${nextPid} creado (NEW)`,
      `Asignado PCB con Prioridad ${priority} y ráfaga de ${burst} ticks. Clic en "Admitir" para moverlo a READY.`
    );
  } else {
    showSoAlert('Error al Crear Proceso', result?.reason || 'No se pudo crear el proceso.');
  }
}

async function changeSchedulerAlgorithm(algo) {
  currentAlgorithm = algo;
  clearTimeout(timer);
  setPlaying(false);
  highlightArrow(null);

  // Reiniciar estado y cargar nuevo algoritmo
  await resetSimulation();
  stepIndex = 0;
  updateDemoStepButtons();

  const result = await applyEvent({
    type: 'set_algorithm',
    payload: { algorithm: algo, quantum: 2 },
  });

  if (result && result.applied) {
    const desc = algo === 'FCFS'
      ? 'FCFS activo (sin desalojo). Pulsa «Paso a paso» para ver la demo de FCFS.'
      : algo === 'RR'
      ? 'Round Robin activo con Quantum = 2. Pulsa «Paso a paso» para ver la demo de Round Robin.'
      : 'Prioridades activo (1 es máxima). Pulsa «Paso a paso» para ver la demo por Prioridades.';
    setNarration(`Planificador: ${algo}`, desc);
  }
}

async function tickCpu() {
  const prevRunning = structure?.running ?? null;
  if (prevRunning === null) {
    showSoAlert('CPU Inactiva (IDLE)', 'No hay ningún proceso en estado RUNNING. Despacha un proceso a la CPU antes de ejecutar ciclos de reloj.');
    return;
  }
  const result = await applyEvent({ type: 'tick' });
  if (result && result.applied) {
    if (structure?.running !== null) {
      const pcb = structure.pcbs?.[structure.running];
      const qInfo = structure.algorithm === 'RR' ? `, Quantum: ${pcb?.quantum_used ?? '?'}/${structure.quantum || 2}` : '';
      setNarration(
        'Tick CPU ejecutado',
        `P${structure.running} consumió 1 ciclo. Tiempo restante: ${pcb?.remaining_time ?? '?'}${qInfo}.`
      );
    } else if (prevRunning !== null) {
      const newState = structure?.states?.[prevRunning];
      if (newState === 'TERMINATED') {
        highlightArrow('salir');
        setTimeout(() => highlightArrow(null), 1200);
        setNarration(
          `P${prevRunning} Finalizado (TERMINATED)`,
          `P${prevRunning} agotó su tiempo restante de ráfaga en este tick y liberó la CPU.`
        );
      } else if (newState === 'READY') {
        highlightArrow('interrumpir');
        setTimeout(() => highlightArrow(null), 1200);
        setNarration(
          `Quantum Expirado · P${prevRunning}`,
          `P${prevRunning} alcanzó el límite de quantum (${structure?.quantum || 2} ticks) en Round Robin y fue desalojado hacia READY.`
        );
      }
    }
  } else if (result && !result.applied) {
    showSoAlert('Ciclo de CPU Rechazado', result.reason || 'No se pudo avanzar el ciclo de reloj.');
  }
}

const ACTION_DESCRIPTIONS = {
  admit: 'NEW → READY: Proceso admitido en memoria principal.',
  dispatch: 'READY → RUNNING: Asignada la CPU al proceso.',
  interrupt: 'RUNNING → READY: Fin de quantum / interrupción de temporizador.',
  io_wait: 'RUNNING → WAITING: El proceso se bloquea esperando operación de E/S.',
  io_complete: 'WAITING → READY: Fin de E/S. El proceso vuelve a competir por la CPU.',
  exit: 'RUNNING → TERMINATED: Proceso finalizado. Recursos liberados.',
};

const ACTION_TRANSITION_MAP = {
  admit: 'admitir',
  dispatch: 'despachar',
  interrupt: 'interrumpir',
  io_wait: 'E/S o evento espera',
  io_complete: 'E/S o evento fin',
  exit: 'salir',
};

async function runManualAction(type) {
  let targetPid = selectedPid;

  if (type === 'dispatch' && (targetPid == null || structure?.states?.[targetPid] !== 'READY')) {
    targetPid = structure?.next_scheduled ?? null;
  }

  if (targetPid == null && type !== 'dispatch') {
    showSoAlert('Selección Requerida', 'Selecciona primero un proceso haciendo clic sobre su token para aplicar esta transición.');
    return;
  }

  const result = await applyEvent({ type, pid: targetPid });
  if (result && result.applied) {
    highlightArrow(ACTION_TRANSITION_MAP[type] || null);
    setTimeout(() => highlightArrow(null), 1200);
    setNarration(`${type.toUpperCase()} aplicado con éxito`, ACTION_DESCRIPTIONS[type] || '');
  } else {
    showSoAlert('Transición Inválida', result?.reason || 'El Sistema Operativo no permite esta transición desde el estado actual.');
  }
}

// ------------------------------------------------------------------
// Cambio de Modo (Demo <-> Manual)
// ------------------------------------------------------------------
function setMode(mode) {
  currentMode = mode;
  tabDemo.classList.toggle('active', mode === 'demo');
  tabManual.classList.toggle('active', mode === 'manual');
  controlsDemo.classList.toggle('is-hidden', mode !== 'demo');
  controlsManual.classList.toggle('is-hidden', mode !== 'manual');

  if (selectedPid != null && structure?.pcbs?.[selectedPid]) {
    syncPcbStepButtons(structure.pcbs[selectedPid]);
  }

  if (mode === 'manual') {
    clearTimeout(timer);
    setPlaying(false);
    highlightArrow(null);
    updateActionButtonsAvailability();

    if (btnTick) {
      btnTick.disabled = (structure?.running === null);
    }
    setNarration('Modo Manual Activado', 'Crea procesos, haz clic en ellos para ver o editar su PCB y aplica las transiciones.');
  } else {
    updateDemoStepButtons();
    setNarration('Modo Demostración', `Demostración de ${currentAlgorithm} lista. Pulsa «Paso a paso» para continuar.`);
  }
}

// ------------------------------------------------------------------
// Modal de Teoría
// ------------------------------------------------------------------
function openTheoryModal(tab = 'fcfs') {
  if (!theoryModal) return;
  theoryModal.classList.remove('is-hidden');
  switchTheoryTab(tab);
}

function closeTheoryModal() {
  if (theoryModal) theoryModal.classList.add('is-hidden');
}

function switchTheoryTab(tabKey) {
  modalTabs.forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === tabKey));
  tabContents.forEach((content) => {
    content.classList.toggle('is-hidden', content.id !== `tab-content-${tabKey}`);
    content.classList.toggle('active', content.id === `tab-content-${tabKey}`);
  });
}

// Event Listeners
tabDemo?.addEventListener('click', () => setMode('demo'));
tabManual?.addEventListener('click', () => setMode('manual'));

if (btnPlay) {
  btnPlay.addEventListener('click', () => {
    if (playing) {
      setPlaying(false);
      clearTimeout(timer);
      return;
    }
    const script = getActiveScript();
    if (stepIndex >= script.length) {
      resetDemo();
      return;
    }
    playFromHere();
  });
}

if (btnPrevStep) {
  btnPrevStep.addEventListener('click', async () => {
    await runPrevStep();
  });
}

if (btnStep) {
  btnStep.addEventListener('click', async () => {
    setPlaying(false);
    clearTimeout(timer);
    const script = getActiveScript();
    if (stepIndex >= script.length) {
      finishDemo();
      return;
    }
    await runStep();
  });
}

if (btnResetDemo) btnResetDemo.addEventListener('click', resetDemo);

// Selector de velocidad por pills
speedButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    speedButtons.forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    currentSpeed = parseInt(btn.dataset.speed, 10);
    if (playing) scheduleNext();
  });
});

// Selector de algoritmo en el footer
algoChips.forEach((chip) => {
  chip.addEventListener('click', () => {
    const algo = chip.dataset.algo;
    if (algo !== currentAlgorithm) {
      changeSchedulerAlgorithm(algo);
    }
  });
});

// Modal de teoría
btnOpenTheory?.addEventListener('click', () => {
  const activeAlgo = currentAlgorithm.toLowerCase();
  openTheoryModal(activeAlgo === 'priority' ? 'priority' : activeAlgo);
});
btnCloseModal?.addEventListener('click', closeTheoryModal);
theoryModal?.addEventListener('click', (e) => {
  if (e.target === theoryModal) closeTheoryModal();
});
modalTabs.forEach((btn) => {
  btn.addEventListener('click', () => switchTheoryTab(btn.dataset.tab));
});

// Inspector de PCB
btnClosePcb?.addEventListener('click', () => {
  if (pcbInspector) pcbInspector.classList.add('is-hidden');
  selectedPid = null;
  tokens.forEach((el) => el.classList.remove('proc-selected'));
  updateActionButtonsAvailability();

  if (btnTick) {
    btnTick.disabled = (structure?.running === null);
  }
});

pcbStepButtons.forEach((btn) => {
  btn.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (selectedPid == null || !structure?.pcbs?.[selectedPid]) return;
    const pcb = structure.pcbs[selectedPid];
    const field = btn.dataset.pcbField;
    const delta = parseInt(btn.dataset.delta, 10) || 0;
    if (field === 'priority') {
      const nextPrio = Math.max(1, Math.min(5, pcb.priority + delta));
      if (nextPrio === pcb.priority) return;
      const res = await applyEvent({ type: 'update_pcb', pid: selectedPid, priority: nextPrio });
      if (res && !res.applied) showSoAlert('No se pudo actualizar PCB', res.reason);
    } else if (field === 'burst_time') {
      const nextBurst = Math.max(1, Math.min(20, pcb.burst_time + delta));
      if (nextBurst === pcb.burst_time) return;
      const res = await applyEvent({ type: 'update_pcb', pid: selectedPid, burst_time: nextBurst });
      if (res && !res.applied) showSoAlert('No se pudo actualizar PCB', res.reason);
    }
  });
});

// Controles manuales
if (btnAddProc) btnAddProc.addEventListener('click', addManualProcess);
if (btnTick) btnTick.addEventListener('click', tickCpu);
if (btnResetManual) {
  btnResetManual.addEventListener('click', async () => {
    await resetSimulation();
    setNarration('Simulación limpia', 'Se han eliminado todos los procesos de memoria y CPU.');
  });
}

actionButtons.forEach((btn) => {
  btn.addEventListener('click', () => runManualAction(btn.dataset.action));
});

// Tecla Escape cierra modal o inspector; flechas ← / → avanzan o retroceden en modo Demo
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeTheoryModal();
    if (pcbInspector && !pcbInspector.classList.contains('is-hidden')) {
      btnClosePcb?.click();
    }
    return;
  }
  if (currentMode === 'demo' && theoryModal?.classList.contains('is-hidden') && !soDialog?.open) {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      btnStep?.click();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      btnPrevStep?.click();
    }
  }
});

// Inicialización: render inicial sin autoplay
updateDemoStepButtons();
render(structure);

if (diagramWrap && typeof ResizeObserver !== 'undefined') {
  const ro = new ResizeObserver(() => drawArrows());
  ro.observe(diagramWrap);
}

if (window.lucide) {
  window.lucide.createIcons();
}
// NOTA: Se eliminó el setTimeout(playFromHere, 900) automático.
// Ahora la simulación espera que el usuario pulse "Paso a paso" o "Reproducir".
