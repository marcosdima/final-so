// controller.js - Core simulation controller


import { initDoubleAndTripleTables } from "./panels.js";
import * as utils from "./utils.js";
import { getSimData, computeBases } from "./data.js";

let simData = null;
let SIMPLE_BASE = 0,
    DOUBLE_BASE = 0,
    TRIPLE_BASE = 0;

// UI elements (will be set in init)
let posInput,
    presetButtons,
    formalCalcText,
    stepCounterText,
    stepProgressFill,
    carouselTrack,
    carouselDots,
    btnCarouselPrev,
    btnCarouselNext,
    stepProgressLabel,
    btnStepAuto,
    btnStepReset,
    simplePanel,
    doublePanel,
    triplePanel,
    emptyPanel,
    doubleEntriesList,
    tripleEntriesList;

let currentResolution = null;
let currentStepIdx = 0;
let autoTimer = null;
let resolutionRequestId = 0;

/** Initialize controller with DOM references */
export function initController(uiElements) {
  // Assign UI elements
  ({
    posInput,
    presetButtons,
    formalCalcText,
    stepCounterText,
    stepProgressFill,
    carouselTrack,
    carouselDots,
    btnCarouselPrev,
    btnCarouselNext,
    stepProgressLabel,
    btnStepAuto,
    btnStepReset,
    simplePanel,
    doublePanel,
    triplePanel,
    emptyPanel,
    doubleEntriesList,
    tripleEntriesList,
  } = uiElements);

  // Expose panels globally for utils that rely on window references
  window.emptyPanel = emptyPanel;
  window.simplePanel = simplePanel;
  window.doublePanel = doublePanel;
  window.triplePanel = triplePanel;

  // Load simulation data
  simData = getSimData();
  const bases = computeBases(simData);
  SIMPLE_BASE = bases.SIMPLE_BASE;
  DOUBLE_BASE = bases.DOUBLE_BASE;
  TRIPLE_BASE = bases.TRIPLE_BASE;

  // Build panels
  initDoubleAndTripleTables({
    simData,
    doubleEntriesList,
    tripleEntriesList,
    posInput,
    clearActiveStates: utils.clearActiveStates,
    highlightDiskCell: utils.highlightDiskCell,
    scrollDiskIntoView: utils.scrollDiskIntoView,
    resolvePosition,
    getCurrentResolution: () => currentResolution,
    renderStep,
  });

  // Attach UI event listeners
  attachEventListeners();

  // Initial resolve
  resolvePosition(parseInt(posInput?.value, 10) || 10);
}

function attachEventListeners() {
  // Preset buttons
  presetButtons?.forEach((btn) => {
    btn.addEventListener("click", () => {
      presetButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const pos = parseInt(btn.getAttribute("data-pos"), 10);
      posInput.value = pos;
      resolvePosition(pos);
    });
  });

  // Position input
  posInput?.addEventListener("input", () => {
    const val = parseInt(posInput.value, 10);
    if (!isNaN(val) && val >= 1) resolvePosition(val);
  });
  posInput?.addEventListener("change", () => {
    const val = parseInt(posInput.value, 10);
    if (!isNaN(val) && val >= 1) resolvePosition(val);
  });

  // Carousel navigation
  btnCarouselPrev?.addEventListener("click", () => {
    stopAuto();
    prevStep();
  });
  btnCarouselNext?.addEventListener("click", () => {
    stopAuto();
    nextStep();
  });
  carouselTrack?.closest(".carousel")?.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft") { stopAuto(); prevStep(); }
    else if (e.key === "ArrowRight") { stopAuto(); nextStep(); }
  });

  // Step auto & reset
  btnStepAuto?.addEventListener("click", () => {
    toggleAuto();
  });
  btnStepReset?.addEventListener("click", () => {
    stopAuto();
    renderStep(0);
  });

  // Direct pointer items
  document.querySelectorAll(".pointer-item.direct").forEach((ptr) => {
    ptr.addEventListener("click", () => {
      const pos = parseInt(ptr.getAttribute("data-position"), 10);
      const targetBlock = parseInt(ptr.getAttribute("data-target-block"), 10);
      const ptrId = ptr.id;

      posInput.value = pos;
      utils.clearActiveStates();
      ptr.classList.add("active-pointer");
      utils.highlightDiskCell(targetBlock);
      resolvePosition(pos, ptrId);
    });
  });

  // Indirect 1 pointer
  const ptrIndirect1 = document.getElementById("ptr-indirect-1");
  ptrIndirect1?.addEventListener("click", () => {
    posInput.value = SIMPLE_BASE;
    utils.clearActiveStates();
    ptrIndirect1.classList.add("active-pointer");
    resolvePosition(SIMPLE_BASE, "ptr-indirect-1");
  });

  // Simple entry items
  document.querySelectorAll(".simple-entry-item").forEach((entry) => {
    entry.addEventListener("click", async (e) => {
      e.stopPropagation();
      const pos = parseInt(entry.getAttribute("data-position"), 10);
      const targetBlock = parseInt(entry.getAttribute("data-target-block"), 10);
      posInput.value = pos;
      utils.clearActiveStates();
      entry.classList.add("active-entry");
      entry.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      utils.highlightDiskCell(targetBlock);
      utils.scrollDiskIntoView(targetBlock);
      await resolvePosition(pos, "ptr-indirect-1");
      if (currentResolution?.steps?.length > 0) {
        renderStep(currentResolution.steps.length - 1);
      }
    });
  });

  // Simple node rows
  document.querySelectorAll(".simple-node-row").forEach((node) => {
    node.addEventListener("click", (e) => {
      e.stopPropagation();
      const targetBlock = parseInt(node.getAttribute("data-target-block"), 10);
      posInput.value = SIMPLE_BASE;
      utils.clearActiveStates();
      node.classList.add("active-entry");
      node.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      utils.highlightDiskCell(targetBlock);
      utils.scrollDiskIntoView(targetBlock);
    });
  });

  // Indirect 2 pointer
  const ptrIndirect2 = document.getElementById("ptr-indirect-2");
  ptrIndirect2?.addEventListener("click", () => {
    posInput.value = DOUBLE_BASE;
    utils.clearActiveStates();
    ptrIndirect2.classList.add("active-pointer");
    resolvePosition(DOUBLE_BASE, "ptr-indirect-2");
  });

  // Indirect 3 pointer
  const ptrIndirect3 = document.getElementById("ptr-indirect-3");
  ptrIndirect3?.addEventListener("click", () => {
    posInput.value = TRIPLE_BASE;
    utils.clearActiveStates();
    ptrIndirect3.classList.add("active-pointer");
    resolvePosition(TRIPLE_BASE, "ptr-indirect-3");
  });

  // Disk cells
  document.querySelectorAll(".matrix-cell").forEach((cell) => {
    cell.addEventListener("click", () => {
      const blockId = parseInt(cell.getAttribute("data-block-id"), 10);
      const role = cell.dataset.blockRole || "";
      utils.clearActiveStates();
      cell.classList.add("cell-active-target");
      utils.scrollDiskIntoView(blockId);

      if (role === "index_simple" || role === "indirect_simple_data") {
        utils.focusIndexPanel(simplePanel, blockId, role);
      } else if (role === "index_double_1" || role === "index_double_2" || role === "indirect_double_data") {
        utils.focusIndexPanel(doublePanel, blockId, role);
      } else if (role === "index_triple_1" || role === "index_triple_sub" || role === "indirect_triple_data") {
        utils.focusIndexPanel(triplePanel, blockId, role);
      }

      const directPtr = simData?.direct_pointers?.find((p) => p.block === blockId);
      if (directPtr) {
        posInput.value = directPtr.position;
        resolvePosition(directPtr.position, `ptr-direct-${directPtr.index}`);
      }
    });
  });
}

/** Resolve logical position (network + fallback) */
export async function resolvePosition(pos, forcedPointerDomId = null) {
  if (isNaN(pos) || pos < 1) pos = 1;
  const requestId = ++resolutionRequestId;
  const seed = simData?.meta?.seed;
  const actionUrl = simData?.meta?.action_url || "/inodes/api/action/";

  try {
    const response = await fetch(actionUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed, action: "resolve", payload: { pos } }),
    });
    if (response.ok) {
      const data = await response.json();
      const resolution = data.result || data;
      if (requestId !== resolutionRequestId) return resolution;
      setResolution(resolution, forcedPointerDomId);
      return resolution;
    }
  } catch (err) {
    console.warn("Network fallback error:", err);
  }

  // Local fallback
  const N = pos - 1;
  let physBlock = 14;
  let ptrId = "ptr-direct-0";
  let route = "DIRECT";
  if (N < 12) {
    physBlock = simData?.direct_pointers[N]?.block || 14;
    ptrId = `ptr-direct-${N}`;
    route = "DIRECT";
  } else if (N < 16) {
    const rel = N - 12;
    physBlock = simData?.indirect_simple?.entries[rel]?.block || 11;
    ptrId = "ptr-indirect-1";
    route = "INDIRECT_SIMPLE";
  } else if (N < 24) {
    physBlock = 8;
    ptrId = "ptr-indirect-2";
    route = "INDIRECT_DOUBLE";
  } else {
    physBlock = 29;
    ptrId = "ptr-indirect-3";
    route = "INDIRECT_TRIPLE";
  }

  const fallback = {
    logical_position: pos,
    logical_block_index: N,
    physical_block: physBlock,
    pointer_dom_id: ptrId,
    route_type: route,
    formal_calc: `N = ${pos} - 1 = ${N} ➜ ${route} ➜ Bloque #${physBlock}`,
    substructures: [],
    steps: [
      {
        step_num: 1,
        title: "Mapeo de Posición Lógica",
        explanation: `Lectura de posición lógica ${pos}. Bloque Lógico N = ${pos} - 1 = ${N}.`,
        highlight_dom: ptrId,
        disk_block: physBlock,
      },
      {
        step_num: 2,
        title: "Acceso al Inodo",
        explanation: `Se consulta el puntero en el inodo correspondiente.`,
        highlight_dom: ptrId,
        disk_block: physBlock,
      },
      {
        step_num: 3,
        title: "Localización Física en Disco",
        explanation: `Acceso al Bloque Físico #${physBlock} en disco.`,
        highlight_dom: `disk-cell-${physBlock}`,
        disk_block: physBlock,
      },
    ],
  };
  setResolution(fallback, forcedPointerDomId);
  return fallback;
}

function setResolution(data, keepPointerDomId = null) {
  currentResolution = data;
  if (keepPointerDomId) currentResolution.pointer_dom_id = keepPointerDomId;
  currentStepIdx = 0;
  stopAuto();

  if (formalCalcText) formalCalcText.textContent = data.formal_calc;
  buildStepCards(data);

  // Mostrar la tabla de índices que corresponde a la ruta y marcar el puntero del inodo
  utils.updateIndexPanelVisibility(data.route_type);
  utils.updateActivePointer(data.pointer_dom_id);

  renderStep(0);
}

function buildStepCards(resolution) {
  if (!carouselTrack || !resolution?.steps) return;
  carouselTrack.innerHTML = "";
  if (carouselDots) carouselDots.innerHTML = "";

  resolution.steps.forEach((step, i) => {
    const card = document.createElement("article");
    card.className = "carousel-card";
    card.dataset.index = String(i);
    const formulaHtml = step.formula
      ? `<div class="step-formula-box"><code>${utils.escapeHtml(step.formula)}</code></div>`
      : "";
    card.innerHTML = `
      <div class="step-header-row">
        <span class="step-badge-tag">PASO ${i + 1}</span>
        <h3 class="step-card-title">${utils.escapeHtml(step.title)}</h3>
      </div>
      ${formulaHtml}
      <p class="step-body-text">${utils.escapeHtml(step.explanation)}</p>
    `;
    carouselTrack.appendChild(card);

    if (carouselDots) {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = "dot";
      dot.dataset.index = String(i);
      dot.setAttribute("role", "tab");
      dot.setAttribute("aria-label", `Ir al paso ${i + 1}`);
      dot.addEventListener("click", () => {
        stopAuto();
        renderStep(i);
      });
      carouselDots.appendChild(dot);
    }
  });
  utils.refreshIcons();
}

export function renderStep(idx) {
  if (!currentResolution || !currentResolution.steps || currentResolution.steps.length === 0) return;
  if (idx < 0) idx = 0;
  if (idx >= currentResolution.steps.length) idx = currentResolution.steps.length - 1;
  currentStepIdx = idx;

  const step = currentResolution.steps[idx];
  const total = currentResolution.steps.length;

  // Update UI counters
  if (stepCounterText) stepCounterText.textContent = `Paso ${idx + 1} de ${total}`;
  if (stepProgressFill) stepProgressFill.style.width = `${((idx + 1) / total) * 100}%`;
  if (stepProgressLabel) stepProgressLabel.textContent = step.title;

  // Slide the carousel to the current card
  if (carouselTrack) {
    carouselTrack.style.transform = `translateX(-${idx * 100}%)`;
    carouselTrack.querySelectorAll(".carousel-card").forEach((c, i) => {
      c.classList.toggle("active", i === idx);
      c.setAttribute("aria-hidden", i === idx ? "false" : "true");
    });
  }
  carouselDots?.querySelectorAll(".dot").forEach((d, i) => {
    d.classList.toggle("active", i === idx);
    d.classList.toggle("done", i < idx);
    d.setAttribute("aria-selected", i === idx ? "true" : "false");
  });
  if (btnCarouselPrev) btnCarouselPrev.disabled = idx === 0;
  if (btnCarouselNext) btnCarouselNext.disabled = idx === total - 1;

  // Resaltar la fila de la tabla de índices correspondiente al paso
  utils.clearIndexEntries();
  utils.syncTablesAndSelection(currentResolution, currentResolution, idx);

  // Highlight disk cell
  if (step.disk_block != null) {
    utils.highlightDiskCell(step.disk_block);
    utils.scrollDiskIntoView(step.disk_block);
  }
}

export function nextStep() {
  if (!currentResolution) return;
  if (currentStepIdx < currentResolution.steps.length - 1) {
    renderStep(currentStepIdx + 1);
  } else {
    stopAuto();
  }
}

export function prevStep() {
  if (!currentResolution) return;
  if (currentStepIdx > 0) {
    renderStep(currentStepIdx - 1);
  }
}

export function toggleAuto() {
  if (autoTimer) stopAuto();
  else startAuto();
}

export function startAuto() {
  if (currentStepIdx >= (currentResolution?.steps?.length || 4) - 1) currentStepIdx = -1;
  if (btnStepAuto) {
    btnStepAuto.classList.add("btn-play");
    btnStepAuto.setAttribute("aria-pressed", "true");
  }
  nextStep();
  autoTimer = setInterval(() => {
    if (currentStepIdx >= (currentResolution?.steps?.length || 4) - 1) {
      stopAuto();
    } else {
      nextStep();
    }
  }, 2400);
}

export function stopAuto() {
  if (autoTimer) {
    clearInterval(autoTimer);
    autoTimer = null;
  }
  if (btnStepAuto) {
    btnStepAuto.classList.remove("btn-play");
    btnStepAuto.setAttribute("aria-pressed", "false");
  }
}



