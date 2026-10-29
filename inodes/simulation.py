"""
Lógica de la simulación de inodos y disco físico fragmentado.

Módulo **puro** (sin Django): implementa el contrato `Simulation` del marco
(`get_state` + `dispatch`) y es determinista dada una semilla. Ver
`docs/sims/inodes/spec.md` para el modelo y las fórmulas.
"""

import random
from dataclasses import dataclass
from typing import Any

from core.exceptions import SimulationError
from core.spec import SimulationSpec


@dataclass
class InodeSimulation:
    """Traduce posiciones lógicas de archivo (base 1) a bloques físicos de disco.

    Determinista dada `seed`: la disposición de bloques se deriva por completo de
    `random.Random(seed)`. Cada petición crea su propia instancia (no hay estado
    compartido entre visitantes).
    """

    seed: int | None = None
    block_size: int = 4096
    ptrs_per_index_block: int = 4
    total_disk_blocks: int = 100
    direct_pointer_count: int = 12
    double_index_count: int = 2

    def __post_init__(self) -> None:
        self.inode_id = 42
        self.mode = "-rw-r--r--"
        self.uid = 1000
        self.gid = 1000

        # Semilla concreta siempre: si no viene, generamos una para poder
        # reportarla en `meta.seed` y que el cliente pueda fijarla.
        if self.seed is None:
            self.seed = random.randrange(2**31)
        self.rng = random.Random(self.seed)

        self._generate_addresses()
        self._refresh_derived_state()
        self._validate_configuration()

    # ------------------------------------------------------------------
    # Generación y validación de la disposición
    # ------------------------------------------------------------------
    def _generate_addresses(self) -> None:
        """Aleatoriza las direcciones físicas sin repeticiones (fragmentación)."""
        n_direct = self.direct_pointer_count
        n_simple = self.ptrs_per_index_block
        n_double_l1 = self.double_index_count
        n_double_data_per_l1 = self.ptrs_per_index_block
        n_triple_data = self.ptrs_per_index_block

        total_needed = (
            n_direct
            + 1  # bloque de índice simple
            + n_simple
            + 1  # bloque de índice doble (N1)
            + n_double_l1  # bloques de índice doble (N2)
            + n_double_l1 * n_double_data_per_l1  # datos dobles
            + 1  # bloque de índice triple (N1)
            + 1  # índice triple N2
            + 1  # índice triple N3
            + n_triple_data  # datos triples
        )

        if total_needed > self.total_disk_blocks:
            raise SimulationError(
                "No hay suficientes bloques de disco para la configuración."
            )

        chosen = self.rng.sample(range(self.total_disk_blocks), total_needed)
        it = iter(chosen)

        self.direct_blocks = [next(it) for _ in range(n_direct)]

        self.indirect_simple_block_id = next(it)
        self.indirect_simple_entries = [next(it) for _ in range(n_simple)]

        self.indirect_double_block_id = next(it)
        self.indirect_double_l1_entries = [next(it) for _ in range(n_double_l1)]
        self.indirect_double_l2_map = {
            entry: [next(it) for _ in range(n_double_data_per_l1)]
            for entry in self.indirect_double_l1_entries
        }

        self.indirect_triple_block_id = next(it)
        self.indirect_triple_l1_entries = [next(it)]
        self.indirect_triple_l2_entries = [next(it)]
        self.indirect_triple_data_blocks = [next(it) for _ in range(n_triple_data)]

    def _refresh_derived_state(self) -> None:
        self.direct_count = len(self.direct_blocks)
        self.simple_count = len(self.indirect_simple_entries)
        self.double_count = sum(len(v) for v in self.indirect_double_l2_map.values())
        self.triple_count = len(self.indirect_triple_data_blocks)
        self.total_logical_positions = (
            self.direct_count
            + self.simple_count
            + self.double_count
            + self.triple_count
        )

    def _validate_configuration(self) -> None:
        all_blocks = (
            list(self.direct_blocks)
            + [self.indirect_simple_block_id]
            + list(self.indirect_simple_entries)
            + [self.indirect_double_block_id]
            + list(self.indirect_double_l1_entries)
            + [blk for vals in self.indirect_double_l2_map.values() for blk in vals]
            + [self.indirect_triple_block_id]
            + list(self.indirect_triple_l1_entries)
            + list(self.indirect_triple_l2_entries)
            + list(self.indirect_triple_data_blocks)
        )
        if len(all_blocks) != len(set(all_blocks)):
            raise SimulationError("Configuración inválida: bloques físicos duplicados.")
        if any(b < 0 or b >= self.total_disk_blocks for b in all_blocks):
            raise SimulationError("Configuración inválida: bloque fuera de rango.")
        if self.ptrs_per_index_block <= 0:
            raise SimulationError("ptrs_per_index_block debe ser > 0.")

    # ------------------------------------------------------------------
    # Contrato Simulation: estado y acciones
    # ------------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        """Estado completo serializable (hidrata la UI y el `json_script`)."""
        return {
            "meta": {"slug": "inodes", "seed": self.seed},
            **self.get_structure(),
        }

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta una acción. Ver `docs/sims/inodes/spec.md` §5."""
        if action == "resolve":
            raw_pos = payload.get("pos")
            if isinstance(raw_pos, bool) or not isinstance(raw_pos, int):
                raise SimulationError("La posición debe ser un número entero válido.")
            return self.resolve_position(raw_pos)

        if action == "randomize":
            new_seed = payload.get("seed")
            self._reseed(new_seed)
            return {"seed": self.seed}

        raise SimulationError(f"Acción desconocida: '{action}'.")

    def _reseed(self, seed: int | None) -> None:
        """Cambiar la disposición a una nueva semilla y regenerar los bloques."""
        if seed is None:
            seed = random.randrange(2**31)
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise SimulationError("La semilla debe ser un entero.")
        self.seed = seed
        self.rng = random.Random(seed)
        self._generate_addresses()
        self._refresh_derived_state()
        self._validate_configuration()

    # ------------------------------------------------------------------
    # Estructura para la plantilla (disco, punteros, índices)
    # ------------------------------------------------------------------
    def get_structure(self) -> dict[str, Any]:
        return {
            "block_size": self.block_size,
            "inode_id": self.inode_id,
            "mode": self.mode,
            "uid": self.uid,
            "gid": self.gid,
            "total_blocks": self.total_disk_blocks,
            "total_logical_positions": self.total_logical_positions,
            "direct_pointers": [
                {"index": i, "position": i + 1, "block": blk}
                for i, blk in enumerate(self.direct_blocks)
            ],
            "indirect_simple": {
                "block_id": self.indirect_simple_block_id,
                "entries": [
                    {"index": i, "position": self.direct_count + 1 + i, "block": blk}
                    for i, blk in enumerate(self.indirect_simple_entries)
                ],
            },
            "indirect_double": {
                "block_id": self.indirect_double_block_id,
                "l1_entries": self.indirect_double_l1_entries,
                "l2_map": self.indirect_double_l2_map,
            },
            "indirect_triple": {
                "block_id": self.indirect_triple_block_id,
                "l1_entries": self.indirect_triple_l1_entries,
                "l2_entries": self.indirect_triple_l2_entries,
                "data_blocks": self.indirect_triple_data_blocks,
            },
            "disk_blocks": self.get_disk_blocks(),
        }

    def get_disk_blocks(self) -> list[dict[str, Any]]:
        role_map: dict[int, tuple[str, str, dict[str, Any]]] = {}

        for idx, blk in enumerate(self.direct_blocks):
            role_map[blk] = (
                "direct",
                f"Bloque #{blk:02d}: Dato Directo [{idx}] (Posición lógica {idx + 1})",
                {"direct_idx": idx},
            )

        role_map[self.indirect_simple_block_id] = (
            "index_simple",
            f"Bloque #{self.indirect_simple_block_id:02d}: Bloque de Índice Simple",
            {},
        )
        for idx, blk in enumerate(self.indirect_simple_entries):
            role_map[blk] = (
                "indirect_simple_data",
                (
                    f"Bloque #{blk:02d}: Dato de Índice Simple (Entrada [{idx}], "
                    f"Posición {self.direct_count + 1 + idx})"
                ),
                {},
            )

        role_map[self.indirect_double_block_id] = (
            "index_double_1",
            f"Bloque #{self.indirect_double_block_id:02d}: Índice Doble Nivel 1",
            {},
        )
        for idx, blk in enumerate(self.indirect_double_l1_entries):
            role_map[blk] = (
                "index_double_2",
                f"Bloque #{blk:02d}: Índice Doble Nivel 2 (Subtabla [{idx}])",
                {},
            )
        for values in self.indirect_double_l2_map.values():
            for blk in values:
                role_map[blk] = (
                    "indirect_double_data",
                    f"Bloque #{blk:02d}: Dato indexado por Indirecto Doble",
                    {},
                )

        role_map[self.indirect_triple_block_id] = (
            "index_triple_1",
            f"Bloque #{self.indirect_triple_block_id:02d}: Índice Triple Nivel 1",
            {},
        )
        for blk in self.indirect_triple_l1_entries + self.indirect_triple_l2_entries:
            role_map[blk] = (
                "index_triple_sub",
                f"Bloque #{blk:02d}: Subíndice Triple (Nivel intermedio)",
                {},
            )
        for blk in self.indirect_triple_data_blocks:
            role_map[blk] = (
                "indirect_triple_data",
                f"Bloque #{blk:02d}: Dato indexado por Indirecto Triple",
                {},
            )

        blocks: list[dict[str, Any]] = []
        for blk in range(self.total_disk_blocks):
            role, desc, extra = role_map.get(
                blk, ("free", f"Bloque #{blk:02d} (Libre / Disponible)", {})
            )
            info: dict[str, Any] = {
                "id": blk,
                "label": f"{blk:02d}",
                "role": role,
                "desc": desc,
            }
            info.update(extra)
            blocks.append(info)
        return blocks

    # ------------------------------------------------------------------
    # Resolución de posiciones lógicas
    # ------------------------------------------------------------------
    def resolve_position(self, logical_position: int) -> dict[str, Any]:
        """Resuelve una posición lógica (base 1) a su bloque físico."""
        if isinstance(logical_position, bool) or not isinstance(logical_position, int):
            raise SimulationError("logical_position debe ser un entero.")
        if logical_position < 1 or logical_position > self.total_logical_positions:
            raise SimulationError(
                f"logical_position fuera de rango: debe estar entre 1 y "
                f"{self.total_logical_positions}."
            )

        n = logical_position - 1
        if n < self.direct_count:
            return self._resolve_direct(n, logical_position)
        if n < self.direct_count + self.simple_count:
            return self._resolve_indirect_simple(n, logical_position)
        if n < self.direct_count + self.simple_count + self.double_count:
            return self._resolve_indirect_double(n, logical_position)
        return self._resolve_triple(n, logical_position)

    def _resolve_direct(self, n: int, logical_position: int) -> dict[str, Any]:
        phys_block = self.direct_blocks[n]
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "DIRECT",
            "physical_block": phys_block,
            "pointer_label": f"Directo [{n}]",
            "pointer_dom_id": f"ptr-direct-{n}",
            "formal_calc": (
                f"N = {logical_position} - 1 = {n} (< {self.direct_count}) "
                "➜ Puntero Directo [{}]".format(n)
            ),
            "substructures": [
                {
                    "role": "inode",
                    "name": f"Inodo #{self.inode_id}",
                    "info": f"Puntero Directo [{n}]",
                    "block": None,
                },
                {
                    "role": "data",
                    "name": f"Bloque Físico #{phys_block:02d}",
                    "info": "Bloque de Datos en Disco",
                    "block": phys_block,
                },
            ],
            "steps": [
                {
                    "step_num": 1,
                    "title": "Mapeo de Posición Lógica",
                    "explanation": (
                        f"Se solicita leer la posición lógica {logical_position} del "
                        f"archivo. En el sistema de archivos (Base 0), esto corresponde "
                        f"al Bloque Lógico N = {logical_position} - 1 = {n}."
                    ),
                    "highlight_dom": f"ptr-direct-{n}",
                    "disk_block": phys_block,
                },
                {
                    "step_num": 2,
                    "title": "Evaluación de Rango Directo",
                    "explanation": (
                        f"Como N = {n} < {self.direct_count}, la dirección está contenida "
                        f"directamente en el inodo. Se consulta el Puntero Directo [{n}]."
                    ),
                    "highlight_dom": f"ptr-direct-{n}",
                    "disk_block": phys_block,
                },
                {
                    "step_num": 3,
                    "title": "Acceso al Bloque Físico en Disco",
                    "explanation": (
                        f"El Puntero Directo [{n}] referencia directamente al Bloque "
                        f"Físico #{phys_block:02d} en disco."
                    ),
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }

    def _resolve_indirect_simple(
        self, n: int, logical_position: int
    ) -> dict[str, Any]:
        rel_idx = n - self.direct_count
        phys_block = self.indirect_simple_entries[rel_idx]
        idx_block = self.indirect_simple_block_id
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "INDIRECT_SIMPLE",
            "physical_block": phys_block,
            "index_block": idx_block,
            "table_index": rel_idx,
            "pointer_label": "Ind. Simple",
            "pointer_dom_id": "ptr-indirect-1",
            "formal_calc": (
                f"N = {logical_position} - 1 = {n} ({self.direct_count} ≤ N < "
                f"{self.direct_count + self.simple_count}) ➜ Entrada = {n} - "
                f"{self.direct_count} = [{rel_idx}] en Bloque #{idx_block:02d}"
            ),
            "substructures": [
                {
                    "role": "inode",
                    "name": f"Inodo #{self.inode_id}",
                    "info": "Puntero Ind. Simple",
                    "block": None,
                },
                {
                    "role": "index",
                    "name": f"Bloque Índice #{idx_block:02d}",
                    "info": f"Entrada [{rel_idx}]",
                    "block": idx_block,
                },
                {
                    "role": "data",
                    "name": f"Bloque Físico #{phys_block:02d}",
                    "info": "Bloque de Datos en Disco",
                    "block": phys_block,
                },
            ],
            "steps": [
                {
                    "step_num": 1,
                    "title": "Cálculo de Bloque Lógico y Desborde Directo",
                    "explanation": (
                        f"Para la posición lógica {logical_position}, el Bloque Lógico es "
                        f"N = {logical_position} - 1 = {n}. Al superar los "
                        f"{self.direct_count} directos (N ≥ {self.direct_count}), el inodo "
                        "delega la búsqueda al Puntero Indirecto Simple."
                    ),
                    "highlight_dom": "ptr-indirect-1",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 2,
                    "title": "Acceso al Bloque de Índice Simple",
                    "explanation": (
                        f"El inodo apunta al Bloque Físico #{idx_block:02d} en disco, el "
                        "cual almacena la tabla de punteros de primer nivel."
                    ),
                    "highlight_dom": f"disk-cell-{idx_block}",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 3,
                    "title": "Indexación Relativa en la Tabla",
                    "explanation": (
                        f"Se calcula la entrada relativa: Entrada = N - "
                        f"{self.direct_count} = {n} - {self.direct_count} = [{rel_idx}]. "
                        f"En el bloque #{idx_block:02d}, la celda [{rel_idx}] contiene la "
                        f"dirección #{phys_block:02d}."
                    ),
                    "highlight_dom": f"simple-entry-{rel_idx}",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 4,
                    "title": "Acceso al Bloque Físico de Datos",
                    "explanation": (
                        f"Se accede al Bloque Físico #{phys_block:02d} en disco para leer "
                        "la información solicitada."
                    ),
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }

    def _resolve_indirect_double(self, n: int, logical_position: int) -> dict[str, Any]:
        rel_double = n - self.direct_count - self.simple_count
        l1_idx = rel_double // self.ptrs_per_index_block
        l2_block_id = self.indirect_double_l1_entries[l1_idx]
        l2_entries = self.indirect_double_l2_map[l2_block_id]
        l2_idx = rel_double % self.ptrs_per_index_block
        phys_block = l2_entries[l2_idx]
        dbl_base = self.direct_count + self.simple_count
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "INDIRECT_DOUBLE",
            "physical_block": phys_block,
            "pointer_label": "Ind. Doble",
            "pointer_dom_id": "ptr-indirect-2",
            "formal_calc": (
                f"N = {logical_position} - 1 = {n} ({dbl_base} ≤ N < "
                f"{dbl_base + self.double_count}) ➜ Rel = {rel_double} | "
                f"L1_idx = {rel_double} // {self.ptrs_per_index_block} = [{l1_idx}] "
                f"(Bloque #{l2_block_id:02d}) | "
                f"L2_idx = {rel_double} % {self.ptrs_per_index_block} = [{l2_idx}]"
            ),
            "substructures": [
                {
                    "role": "inode",
                    "name": f"Inodo #{self.inode_id}",
                    "info": "Puntero Ind. Doble",
                    "block": None,
                },
                {
                    "role": "index",
                    "name": f"Índice N1 #{self.indirect_double_block_id:02d}",
                    "info": f"Entrada [{l1_idx}] ➜ Blk #{l2_block_id:02d}",
                    "block": self.indirect_double_block_id,
                },
                {
                    "role": "index",
                    "name": f"Índice N2 #{l2_block_id:02d}",
                    "info": f"Entrada [{l2_idx}] ➜ Blk #{phys_block:02d}",
                    "block": l2_block_id,
                },
                {
                    "role": "data",
                    "name": f"Bloque Físico #{phys_block:02d}",
                    "info": "Bloque de Datos en Disco",
                    "block": phys_block,
                },
            ],
            "steps": [
                {
                    "step_num": 1,
                    "title": "Desborde de Bloques Directos y Simples",
                    "explanation": (
                        f"La posición lógica {logical_position} supera los bloques "
                        f"directos ({self.direct_count}) y simples ({self.simple_count}), "
                        "por lo que se usa el índice doble."
                    ),
                    "highlight_dom": "ptr-indirect-2",
                    "disk_block": self.indirect_double_block_id,
                },
                {
                    "step_num": 2,
                    "title": "Cálculo del Índice de Nivel 1",
                    "explanation": (
                        f"rel_double = {rel_double}. L1_idx = {rel_double} // "
                        f"{self.ptrs_per_index_block} = {l1_idx}. El bloque N1 es "
                        f"#{self.indirect_double_block_id:02d} que apunta al bloque N2 "
                        f"#{l2_block_id:02d}."
                    ),
                    "highlight_dom": f"double-l1-{l1_idx}",
                    "disk_block": self.indirect_double_block_id,
                },
                {
                    "step_num": 3,
                    "title": "Cálculo del Índice de Nivel 2",
                    "explanation": (
                        f"L2_idx = {rel_double} % {self.ptrs_per_index_block} = {l2_idx}. "
                        f"En el bloque N2 #{l2_block_id:02d} la entrada [{l2_idx}] "
                        f"contiene el bloque de datos #{phys_block:02d}."
                    ),
                    "highlight_dom": f"double-l2-{l2_idx}",
                    "disk_block": l2_block_id,
                },
                {
                    "step_num": 4,
                    "title": "Acceso al Bloque de Datos",
                    "explanation": f"Se lee el bloque de datos físico #{phys_block:02d}.",
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }

    def _resolve_triple(self, n: int, logical_position: int) -> dict[str, Any]:
        rel_triple = n - self.direct_count - self.simple_count - self.double_count
        idx = rel_triple % len(self.indirect_triple_data_blocks)
        phys_block = self.indirect_triple_data_blocks[idx]
        l1_id = self.indirect_triple_block_id
        l2_id = self.indirect_triple_l1_entries[0]
        l3_id = self.indirect_triple_l2_entries[0]
        triple_base = self.direct_count + self.simple_count + self.double_count
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "INDIRECT_TRIPLE",
            "physical_block": phys_block,
            "pointer_label": "Ind. Triple",
            "pointer_dom_id": "ptr-indirect-3",
            "formal_calc": (
                f"N = {logical_position} - 1 = {n} (N ≥ {triple_base}) ➜ Recorrido Triple: "
                f"Blk #{l1_id:02d} ➜ Blk #{l2_id:02d} ➜ Blk #{l3_id:02d} ➜ "
                f"Blk #{phys_block:02d}"
            ),
            "substructures": [
                {
                    "role": "inode",
                    "name": f"Inodo #{self.inode_id}",
                    "info": "Puntero Ind. Triple",
                    "block": None,
                },
                {
                    "role": "index",
                    "name": f"Índice N1 #{l1_id:02d}",
                    "info": f"Apunta a N2 #{l2_id:02d}",
                    "block": l1_id,
                },
                {
                    "role": "index",
                    "name": f"Índice N2 #{l2_id:02d}",
                    "info": f"Apunta a N3 #{l3_id:02d}",
                    "block": l2_id,
                },
                {
                    "role": "index",
                    "name": f"Índice N3 #{l3_id:02d}",
                    "info": f"Apunta a Dato #{phys_block:02d}",
                    "block": l3_id,
                },
                {
                    "role": "data",
                    "name": f"Bloque Físico #{phys_block:02d}",
                    "info": "Bloque de Datos en Disco",
                    "block": phys_block,
                },
            ],
            "steps": [
                {
                    "step_num": 1,
                    "title": "Activación del Indirecto Triple",
                    "explanation": (
                        f"Posición {logical_position} (N = {n} ≥ {triple_base}). La "
                        "dirección desborda el indirecto doble y requiere 3 niveles de "
                        "indirección."
                    ),
                    "highlight_dom": "ptr-indirect-3",
                    "disk_block": None,
                },
                {
                    "step_num": 2,
                    "title": "Acceso a Índice Triple Nivel 1",
                    "explanation": (
                        f"El inodo apunta al Bloque Físico #{l1_id:02d} en disco "
                        f"(Nivel 1). La entrada resuelve al bloque de Nivel 2 #{l2_id:02d}."
                    ),
                    "highlight_dom": f"disk-cell-{l1_id}",
                    "disk_block": l1_id,
                },
                {
                    "step_num": 3,
                    "title": "Acceso a Índice Triple Nivel 2",
                    "explanation": (
                        f"Se accede al Bloque Físico #{l2_id:02d} (Nivel 2), que "
                        f"referencia al bloque de Nivel 3 #{l3_id:02d}."
                    ),
                    "highlight_dom": f"disk-cell-{l2_id}",
                    "disk_block": l2_id,
                },
                {
                    "step_num": 4,
                    "title": "Acceso a Índice Triple Nivel 3",
                    "explanation": (
                        f"Se accede al Bloque Físico #{l3_id:02d} (Nivel 3), donde se "
                        f"encuentra la dirección del bloque de datos #{phys_block:02d}."
                    ),
                    "highlight_dom": f"disk-cell-{l3_id}",
                    "disk_block": l3_id,
                },
                {
                    "step_num": 5,
                    "title": "Acceso al Bloque de Datos",
                    "explanation": (
                        f"Se accede al Bloque Físico de Datos #{phys_block:02d} en disco "
                        "tras resolver la cadena completa de punteros triples."
                    ),
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }


def _initial_context(sim: InodeSimulation, state: dict[str, Any]) -> dict[str, Any]:
    """Contexto de render inicial: posición por defecto 10 y su resolución."""
    initial_pos = 10
    return {
        "initial_pos": initial_pos,
        "initial_resolution": sim.resolve_position(initial_pos),
    }


# Spec pública registrada en el catálogo de `core`.
SPEC = SimulationSpec(
    slug="inodes",
    title="Inodos y disco",
    description="Traducción de posiciones lógicas a bloques físicos fragmentados.",
    icon="hard-drive",
    factory=InodeSimulation,
    context=_initial_context,
)
