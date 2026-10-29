const dataEl = document.getElementById('process-data');
const stateEl = document.getElementById('proc-state');
const statusEl = document.getElementById('process-status');
const btnAdd = document.getElementById('btn-add');
const btnReset = document.getElementById('btn-reset');
const selectEl = document.getElementById('proc-select');
const actionButtons = document.querySelectorAll('.process-action-buttons .btn-act');

// Estado del cliente: log de eventos (event-sourcing) + proceso seleccionado.
let structure = dataEl ? JSON.parse(dataEl.textContent) : null;
let log = structure?.events ? [...structure.events] : [];
const seed = structure?.meta?.seed ?? null;
let selectedPid = null;

// Tokens persistentes por proceso (rectangulos que se mueven)
const tokens = new Map();

function ensureToken(pid) {
  if (tokens.has(pid)) return tokens.get(pid);
  const el = document.createElement('div');
  el.className = 'proc-token';
  el.id = 'proc-token-' + pid;
  el.textContent = 'P' + pid;
  el.dataset.pid = String(pid);
  el.addEventListener('click', () => selectProcess(pid));
  tokens.set(pid, el);
  return el;
}

function nodeForState(state) {
  return document.getElementById('list-' + state);
}

function selectProcess(pid) {
  selectedPid = pid;
  if (selectEl) selectEl.value = pid == null ? '' : String(pid);
  // resaltar el token seleccionado
  tokens.forEach((el, p) => el.classList.toggle('proc-selected', p === pid));
}

function render(s) {
  if (!s) return;

  // 1. Recordar posicion actual de cada token (FIRST)
  const firstRects = new Map();
  tokens.forEach((el, pid) => {
    firstRects.set(pid, el.getBoundingClientRect());
  });

  // 2. Marcar nodo activo (quien esta en CPU)
  for (const st of ['NEW', 'READY', 'RUNNING', 'WAITING', 'TERMINATED']) {
    const node = document.getElementById('node-' + st);
    if (node) {
      node.classList.toggle('active', s.running !== null && s.states[s.running] === st);
    }
  }

  // 3. Mover cada token a su nuevo contenedor (LAST)
  for (const pid of s.pids) {
    const state = s.states[pid];
    const token = ensureToken(pid);
    token.classList.toggle('proc-running', state === 'RUNNING');
    token.classList.toggle('proc-waiting', state === 'WAITING');
    token.classList.toggle('proc-terminated', state === 'TERMINATED');
    token.classList.toggle('proc-selected', pid === selectedPid);
    const container = nodeForState(state);
    if (container && token.parentElement !== container) {
      container.appendChild(token);
    }
  }

  // 4. FLIP: animar el desplazamiento entre contenedores
  requestAnimationFrame(() => {
    tokens.forEach((el, pid) => {
      const last = el.getBoundingClientRect();
      const first = firstRects.get(pid);
      if (!first) {
        // token nuevo: aparece con fade
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
      // forzar reflow
      void el.offsetWidth;
      el.style.transition = 'transform 0.55s cubic-bezier(0.22, 1, 0.36, 1)';
      el.style.transform = '';
    });
  });

  refreshSelect(s);

  // 5. Panel de texto
  if (stateEl) {
    const lines = [];
    lines.push('Estados:');
    for (const pid of s.pids) lines.push(`  P${pid}: ${s.states[pid]}`);
    lines.push(`Running: ${s.running === null ? 'ninguno' : 'P' + s.running}`);
    lines.push(`Ready: [${s.ready_queue.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Waiting: [${s.waiting_queue.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Terminated: [${s.terminated.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Eventos aplicados: ${s.events.length}`);
    stateEl.textContent = lines.join('\n');
  }
}

function refreshSelect(s) {
  if (!selectEl) return;
  const current = selectedPid;
  selectEl.innerHTML = '<option value="">— selecciona —</option>';
  for (const pid of s.pids) {
    const opt = document.createElement('option');
    opt.value = String(pid);
    opt.textContent = `P${pid} (${s.states[pid]})`;
    selectEl.appendChild(opt);
  }
  // conservar la selección si sigue existiendo
  if (current != null && s.pids.includes(current)) {
    selectEl.value = String(current);
  } else {
    selectedPid = null;
    selectEl.value = '';
  }
}

// Estado Stateless: el cliente envia el log completo + el evento nuevo.
async function applyEvent(event) {
  try {
    const res = await fetch('/processes/api/action/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'apply', payload: { events: log, event } }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    structure = data.state;
    log = structure.events; // el servidor devuelve el log efectivo
    render(structure);
    return data.result;
  } catch (e) {
    if (statusEl) statusEl.textContent = 'Error al aplicar el evento.';
    return null;
  }
}

function setStatusFromResult(result) {
  if (!statusEl) return;
  if (result && result.event) {
    const label = `${result.event.type.toUpperCase()} P${result.event.pid}`;
    statusEl.textContent = (result.applied ? '\u2713 ' : '\u2717 ') + label +
      (result.applied ? '' : ' \u2014 ' + (result.reason || ''));
    statusEl.classList.toggle('status-error', !result.applied);
  } else {
    statusEl.textContent = '';
  }
}

async function addProcess() {
  const nextPid = (structure?.pids?.length ? Math.max(...structure.pids) : 0) + 1;
  const result = await applyEvent({ type: 'create', pid: nextPid });
  if (result && result.applied) selectProcess(nextPid);
  setStatusFromResult(result);
}

async function runAction(type) {
  if (selectedPid == null) {
    if (statusEl) {
      statusEl.textContent = 'Selecciona primero un proceso (haz clic en uno o usa el desplegable).';
      statusEl.classList.add('status-error');
    }
    return;
  }
  const result = await applyEvent({ type, pid: selectedPid });
  setStatusFromResult(result);
}

async function reset() {
  try {
    const res = await fetch('/processes/api/action/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'apply', payload: { events: [] } }),
    });
    const data = await res.json();
    structure = data.state;
    log = [];
    selectedPid = null;
    // limpiar tokens
    tokens.forEach((el) => el.remove());
    tokens.clear();
    render(structure);
    if (statusEl) {
      statusEl.textContent = 'Simulacion reiniciada.';
      statusEl.classList.remove('status-error');
    }
  } catch (e) {
    if (statusEl) statusEl.textContent = 'Error al reiniciar.';
  }
}

if (btnAdd) btnAdd.addEventListener('click', addProcess);
if (btnReset) btnReset.addEventListener('click', reset);
if (selectEl) {
  selectEl.addEventListener('change', () => {
    const v = selectEl.value;
    selectProcess(v === '' ? null : parseInt(v, 10));
  });
}
actionButtons.forEach((btn) => {
  btn.addEventListener('click', () => runAction(btn.dataset.action));
});

render(structure);
