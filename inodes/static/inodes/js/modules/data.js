export function getSimData() {
  const simDataScript = document.getElementById("simulation-data");
  return simDataScript ? JSON.parse(simDataScript.textContent) : null;
}

export function computeBases(simData) {
  const SIMPLE_BASE = (simData?.direct_pointers?.length || 12) + 1;
  const DOUBLE_BASE = SIMPLE_BASE + (simData?.indirect_simple?.entries?.length || 4);
  const TRIPLE_BASE = DOUBLE_BASE + 8;
  return { SIMPLE_BASE, DOUBLE_BASE, TRIPLE_BASE };
}
