// panels.js - Double and Triple tables initialization
export function initDoubleAndTripleTables({
  simData,
  doubleEntriesList,
  tripleEntriesList,
  posInput,
  clearActiveStates,
  highlightDiskCell,
  scrollDiskIntoView,
  resolvePosition,
  getCurrentResolution,
  renderStep,
}) {
  if (!simData) return;

  // Double: nodos N1/N2 y bloques de datos indexados
  if (doubleEntriesList && simData.indirect_double) {
    doubleEntriesList.innerHTML = "";
    const basePos = 17;

    const n1Row = document.createElement("div");
    n1Row.className = "double-item-row index-node-row";
    n1Row.id = "double-node-n1";
    n1Row.setAttribute("data-pos", basePos);
    n1Row.setAttribute("data-target-block", simData.indirect_double.block_id);
    n1Row.innerHTML = `<span>Índice Doble N1</span><strong>➜ Nodos N2</strong>`;
    n1Row.addEventListener("click", (e) => {
      e.stopPropagation();
      const tb = parseInt(n1Row.getAttribute("data-target-block"), 10);
      posInput.value = basePos;
      clearActiveStates();
      n1Row.classList.add("active-entry");
      n1Row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      highlightDiskCell(tb);
      scrollDiskIntoView(tb);
    });
    doubleEntriesList.appendChild(n1Row);

    simData.indirect_double.l1_entries.forEach((l1, l1Idx) => {
      const subBase = basePos + l1Idx * 4;

      const n2Row = document.createElement("div");
      n2Row.className = "double-item-row index-node-row";
      n2Row.id = `double-node-n2-${l1Idx}`;
      n2Row.setAttribute("data-pos", subBase);
      n2Row.setAttribute("data-target-block", l1);
      n2Row.innerHTML = `<span>Índice Doble N2 Subtabla [${l1Idx}]</span><strong>➜ Datos</strong>`;
      n2Row.addEventListener("click", (e) => {
        e.stopPropagation();
        const tb = parseInt(n2Row.getAttribute("data-target-block"), 10);
        posInput.value = subBase;
        clearActiveStates();
        n2Row.classList.add("active-entry");
        n2Row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        highlightDiskCell(tb);
        scrollDiskIntoView(tb);
      });

      const subtable = document.createElement("div");
      subtable.className = "double-subtable-box";
      subtable.innerHTML = `<div class="subtable-title">Subtabla N2 (Bloque #${String(l1).padStart(2, "0")}):</div>`;
      subtable.appendChild(n2Row);

      const l2List = simData.indirect_double.l2_map[l1] || [];
      l2List.forEach((dataBlk, l2Idx) => {
        const row = document.createElement("div");
        row.className = "double-item-row";
        const position = subBase + l2Idx;
        row.id = `double-entry-${position}`;
        row.setAttribute("data-pos", position);
        row.setAttribute("data-target-block", dataBlk);
        row.innerHTML = `
          <span>Entrada [${l1Idx}][${l2Idx}]</span>
          <strong>➜ Bloque #${String(dataBlk).padStart(2, "0")}</strong>
        `;
        row.addEventListener("click", async (e) => {
          e.stopPropagation();
          posInput.value = position;
          clearActiveStates();
          row.classList.add("active-entry");
          row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
          highlightDiskCell(dataBlk);
          scrollDiskIntoView(dataBlk);
          await resolvePosition(position, "ptr-indirect-2");
          const resolution = getCurrentResolution();
          if (resolution?.steps?.length > 0) {
            renderStep(resolution.steps.length - 1);
          }
        });
        subtable.appendChild(row);
      });
      doubleEntriesList.appendChild(subtable);
    });
  }

  // Triple: nodos N1/N2/N3 y bloques de datos
  if (tripleEntriesList && simData.indirect_triple) {
    tripleEntriesList.innerHTML = "";
    const basePos = 25;

    const tN1 = simData.indirect_triple.block_id;
    const n1Row = document.createElement("div");
    n1Row.className = "triple-item-row index-node-row";
    n1Row.id = "triple-node-n1";
    n1Row.setAttribute("data-pos", basePos);
    n1Row.setAttribute("data-target-block", tN1);
    n1Row.innerHTML = `<span>Índice Triple N1</span><strong>➜ Nodo N2</strong>`;
    n1Row.addEventListener("click", (e) => {
      e.stopPropagation();
      const tb = parseInt(n1Row.getAttribute("data-target-block"), 10);
      posInput.value = basePos;
      clearActiveStates();
      n1Row.classList.add("active-entry");
      n1Row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      highlightDiskCell(tb);
      scrollDiskIntoView(tb);
    });
    tripleEntriesList.appendChild(n1Row);

    const tN2 = simData.indirect_triple.l1_entries?.[0];
    if (tN2 !== undefined) {
      const n2Row = document.createElement("div");
      n2Row.className = "triple-item-row index-node-row";
      n2Row.id = "triple-node-n2";
      n2Row.setAttribute("data-pos", basePos);
      n2Row.setAttribute("data-target-block", tN2);
      n2Row.innerHTML = `<span>Índice Triple N2</span><strong>➜ Nodo N3</strong>`;
      n2Row.addEventListener("click", (e) => {
        e.stopPropagation();
        const tb = parseInt(n2Row.getAttribute("data-target-block"), 10);
        posInput.value = basePos;
        clearActiveStates();
        n2Row.classList.add("active-entry");
        n2Row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        highlightDiskCell(tb);
        scrollDiskIntoView(tb);
      });
      tripleEntriesList.appendChild(n2Row);
    }

    const tN3 = simData.indirect_triple.l2_entries?.[0];
    if (tN3 !== undefined) {
      const n3Row = document.createElement("div");
      n3Row.className = "triple-item-row index-node-row";
      n3Row.id = "triple-node-n3";
      n3Row.setAttribute("data-pos", basePos);
      n3Row.setAttribute("data-target-block", tN3);
      n3Row.innerHTML = `<span>Índice Triple N3</span><strong>➜ Datos</strong>`;
      n3Row.addEventListener("click", (e) => {
        e.stopPropagation();
        const tb = parseInt(n3Row.getAttribute("data-target-block"), 10);
        posInput.value = basePos;
        clearActiveStates();
        n3Row.classList.add("active-entry");
        n3Row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        highlightDiskCell(tb);
        scrollDiskIntoView(tb);
      });
      tripleEntriesList.appendChild(n3Row);
    }

    const dataBlks = simData.indirect_triple.data_blocks || [];
    dataBlks.forEach((dataBlk, idx) => {
      const row = document.createElement("div");
      row.className = "triple-item-row";
      const position = basePos + idx;
      row.id = `triple-entry-${position}`;
      row.setAttribute("data-pos", position);
      row.setAttribute("data-target-block", dataBlk);
      row.innerHTML = `
        <span>N3 Entrada [${idx}]</span>
        <strong>➜ Bloque #${String(dataBlk).padStart(2, "0")}</strong>
      `;
      row.addEventListener("click", async (e) => {
        e.stopPropagation();
        posInput.value = position;
        clearActiveStates();
        row.classList.add("active-entry");
        row.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
        highlightDiskCell(dataBlk);
        scrollDiskIntoView(dataBlk);
        await resolvePosition(position, "ptr-indirect-3");
        const resolution = getCurrentResolution();
        if (resolution?.steps?.length > 0) {
          renderStep(resolution.steps.length - 1);
        }
      });
      tripleEntriesList.appendChild(row);
    });
  }
}
