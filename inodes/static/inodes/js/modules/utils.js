// utils.js - Helper utilities for the inode simulator

/** Refresh Lucide icons if the library is loaded */
export function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

/** Escape HTML to prevent injection */
export function escapeHtml(value) {
  return String(value)
    .replace(/\u0026/g, "&amp;")
    .replace(/\u003c/g, "&lt;")
    .replace(/\u003e/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Clear active entries in index tables */
export function clearIndexEntries() {
  document.querySelectorAll(".simple-entry-item.active-entry").forEach((el) => el.classList.remove("active-entry"));
  document.querySelectorAll(".simple-node-row.active-entry").forEach((el) => el.classList.remove("active-entry"));
  document.querySelectorAll(".double-item-row.active-entry").forEach((el) => el.classList.remove("active-entry"));
  document.querySelectorAll(".triple-item-row.active-entry").forEach((el) => el.classList.remove("active-entry"));
}

/** Focus a specific index panel and highlight a row */
export function focusIndexPanel(panel, blockId, role) {
  if (!panel) return;
  setActiveIndexPanel(panel);
  clearIndexEntries();

  let selectedRow = null;
  if (role === "index_simple" || role === "indirect_simple_data") {
    const row = document.querySelector(`.simple-entry-item[data-target-block="${blockId}"]`) ||
                document.querySelector(`.simple-node-row[data-target-block="${blockId}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
  }
  if (role === "indirect_double_data" || role === "index_double_1" || role === "index_double_2") {
    const row = document.querySelector(`.double-item-row[data-target-block="${blockId}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
  }
  if (role === "indirect_triple_data" || role === "index_triple_1" || role === "index_triple_sub") {
    const row = document.querySelector(`.triple-item-row[data-target-block="${blockId}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
  }

  if (selectedRow) {
    selectedRow.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }
  scrollPanelIntoView(panel);
}

/** Activate a single index panel, hide the others */
export function setActiveIndexPanel(panel) {
  [window.emptyPanel, window.simplePanel, window.doublePanel, window.triplePanel].forEach((p) => {
    if (p) p.classList.remove("active");
  });
  if (panel) panel.classList.add("active");
}

/** Show the appropriate index panel based on route type */
export function updateIndexPanelVisibility(routeType) {
  if (routeType === "INDIRECT_SIMPLE") setActiveIndexPanel(window.simplePanel);
  else if (routeType === "INDIRECT_DOUBLE") setActiveIndexPanel(window.doublePanel);
  else if (routeType === "INDIRECT_TRIPLE") setActiveIndexPanel(window.triplePanel);
  else setActiveIndexPanel(window.emptyPanel);
}

/** Synchronize tables and selection based on the current resolution */
export function syncTablesAndSelection(resolution, currentResolution, currentStepIdx) {
  const pos = resolution.logical_position;
  const step = currentResolution?.steps?.[currentStepIdx];
  const stepBlock = (step && step.disk_block != null) ? step.disk_block : resolution.physical_block;

  let selectedRow = null;
  if (step?.highlight_dom) {
    const domEl = document.getElementById(step.highlight_dom);
    if (
      domEl &&
      (domEl.classList.contains("simple-entry-item") ||
        domEl.classList.contains("simple-node-row") ||
        domEl.classList.contains("double-item-row") ||
        domEl.classList.contains("triple-item-row"))
    ) {
      domEl.classList.add("active-entry");
      selectedRow = domEl;
    }
  }

  if (!selectedRow && resolution.route_type === "INDIRECT_SIMPLE") {
    const row = document.querySelector(`.simple-entry-item[data-target-block="${stepBlock}"]`) ||
                document.querySelector(`.simple-node-row[data-target-block="${stepBlock}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
    else if (resolution.table_index !== undefined) {
      const item = document.getElementById(`simple-entry-${resolution.table_index}`);
      if (item) { item.classList.add("active-entry"); selectedRow = item; }
    }
  } else if (resolution.route_type === "INDIRECT_DOUBLE") {
    const row = document.querySelector(`.double-item-row[data-target-block="${stepBlock}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
    else {
      const item = document.getElementById(`double-entry-${pos}`);
      if (item) { item.classList.add("active-entry"); selectedRow = item; }
    }
  } else if (resolution.route_type === "INDIRECT_TRIPLE") {
    const row = document.querySelector(`.triple-item-row[data-target-block="${stepBlock}"]`);
    if (row) { row.classList.add("active-entry"); selectedRow = row; }
    else {
      const item = document.getElementById(`triple-entry-${pos}`);
      if (item) { item.classList.add("active-entry"); selectedRow = item; }
    }
  }

  if (selectedRow) {
    selectedRow.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }
}

/** Scroll guided step: focus either the highlighted DOM element or the disk cell */
export function scrollGuidedStep(step, blockId) {
  const target = step.highlight_dom
    ? document.getElementById(step.highlight_dom)
    : (blockId != null ? document.getElementById(`disk-cell-${blockId}`) : null);

  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }
}

/** Clear all active UI states */
export function clearActiveStates() {
  document.querySelectorAll('.pointer-item').forEach((el) => el.classList.remove('active-pointer'));
  document.querySelectorAll('.matrix-cell').forEach((el) => el.classList.remove('cell-active-target'));
  clearIndexEntries();
}

/** Highlight a specific disk cell */
export function highlightDiskCell(blockId) {
  document.querySelectorAll('.matrix-cell').forEach((el) => el.classList.remove('cell-active-target'));
  const cell = document.getElementById(`disk-cell-${blockId}`);
  if (cell) cell.classList.add('cell-active-target');
}

/** Update active pointer element */
export function updateActivePointer(pointerDomId) {
  document.querySelectorAll('.pointer-item').forEach((el) => el.classList.remove('active-pointer'));
  if (pointerDomId) {
    const ptr = document.getElementById(pointerDomId);
    if (ptr) ptr.classList.add('active-pointer');
  }
}

/** Scroll a disk cell into view */
export function scrollDiskIntoView(blockId) {
  const diskCell = document.getElementById(`disk-cell-${blockId}`);
  if (diskCell) diskCell.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
}

/** Scroll a generic panel into view */
export function scrollPanelIntoView(panel) {
  if (!panel) return;
  panel.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
}
