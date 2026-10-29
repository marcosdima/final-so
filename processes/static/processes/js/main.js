const dataEl = document.getElementById('process-data');
const stateEl = document.getElementById('proc-state');
const statusEl = document.getElementById('process-status');
const btnStep = document.getElementById('btn-step');
const btnAuto = document.getElementById('btn-auto');
const btnReset = document.getElementById('btn-reset');

let structure = dataEl ? JSON.parse(dataEl.textContent) : null;
const seed = structure?.meta?.seed ?? null;

// Tokens persistentes por proceso (rectangulos que se mueven)
const tokens = new Map();
let autoTimer = null;

function ensureToken(pid) {
  if (tokens.has(pid)) return tokens.get(pid);
  const el = document.createElement('div');
  el.className = 'proc-token';
  el.id = 'proc-token-' + pid;
  el.textContent = 'P' + pid;
  el.dataset.pid = String(pid);
  tokens.set(pid, el);
  return el;
}

function nodeForState(state) {
  return document.getElementById('list-' + state);
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

  // 5. Panel de texto
  if (stateEl) {
    const lines = [];
    lines.push('Estados:');
    for (const pid of s.pids) lines.push(`  P${pid}: ${s.states[pid]}`);
    lines.push(`Running: ${s.running === null ? 'ninguno' : 'P' + s.running}`);
    lines.push(`Ready: [${s.ready_queue.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Waiting: [${s.waiting_queue.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Terminated: [${s.terminated.map((p) => 'P' + p).join(', ')}]`);
    lines.push(`Paso ${s.event_index}/${s.total_events}`);
    if (s.events && s.event_index < s.events.length) {
      lines.push(`Siguiente: ${s.events[s.event_index].label}`);
    } else {
      lines.push('No hay mas eventos.');
    }
    stateEl.textContent = lines.join('\n');
  }
}

// Stateless: el cliente pide el estado tras aplicar 'step' eventos.
async function requestStep(targetStep) {
  try {
    const res = await fetch('/processes/api/action/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed, action: 'step', payload: { step: targetStep } }),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    structure = data.state;
    render(structure);
    return data.result;
  } catch (e) {
    if (statusEl) statusEl.textContent = 'Error al avanzar.';
    return null;
  }
}

async function step() {
  const next = (structure?.event_index ?? 0) + 1;
  const result = await requestStep(next);
  if (statusEl) {
    if (result && result.event) {
      statusEl.textContent = (result.applied ? '\u2713 ' : '\u2717 ') + result.event.label +
        (result.applied ? '' : ' \u2014 ' + (result.reason || ''));
    } else {
      statusEl.textContent = 'No hay mas eventos.';
    }
  }
}

async function reset() {
  stopAuto();
  await requestStep(0);
  // limpiar tokens (volveran a crearse en NEW)
  tokens.forEach((el) => el.remove());
  tokens.clear();
  render(structure);
  if (statusEl) statusEl.textContent = 'Simulacion reiniciada.';
}

function stopAuto() {
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
    if (btnAuto) btnAuto.innerHTML = '<i data-lucide="timer"></i> Auto';
    if (window.lucide) window.lucide.createIcons();
  }
}

function toggleAuto() {
  if (autoTimer) {
    stopAuto();
    return;
  }
  if (!btnAuto) return;
  btnAuto.innerHTML = '<i data-lucide="pause"></i> Pausa';
  if (window.lucide) window.lucide.createIcons();
  autoTimer = setInterval(async () => {
    if (!structure || structure.event_index >= structure.total_events) {
      stopAuto();
      return;
    }
    await step();
  }, 1100);
}

if (btnStep) btnStep.addEventListener('click', step);
if (btnReset) btnReset.addEventListener('click', reset);
if (btnAuto) btnAuto.addEventListener('click', toggleAuto);

render(structure);
