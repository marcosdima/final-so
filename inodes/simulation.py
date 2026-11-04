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
            pos = idx + 1
            role_map[blk] = (
                "direct",
                f"Bloque #{blk:02d}: Dato Directo [{idx}] (Posición lógica {pos})",
                {"direct_idx": idx, "position": pos},
            )

        simple_base_pos = self.direct_count + 1
        simple_last_pos = self.direct_count + self.simple_count
        role_map[self.indirect_simple_block_id] = (
            "index_simple",
            (
                f"Bloque #{self.indirect_simple_block_id:02d}: Bloque de Índice Simple "
                f"(Posiciones lógicas {simple_base_pos} a {simple_last_pos})"
            ),
            {"position": simple_base_pos},
        )
        for idx, blk in enumerate(self.indirect_simple_entries):
            pos = simple_base_pos + idx
            role_map[blk] = (
                "indirect_simple_data",
                (
                    f"Bloque #{blk:02d}: Dato de Índice Simple (Entrada [{idx}], "
                    f"Posición lógica {pos})"
                ),
                {"position": pos},
            )

        double_base_pos = self.direct_count + self.simple_count + 1
        double_last_pos = double_base_pos + self.double_count - 1
        role_map[self.indirect_double_block_id] = (
            "index_double_1",
            (
                f"Bloque #{self.indirect_double_block_id:02d}: Índice Doble Nivel 1 "
                f"(Posiciones lógicas {double_base_pos} a {double_last_pos})"
            ),
            {"position": double_base_pos},
        )
        for l1_idx, blk in enumerate(self.indirect_double_l1_entries):
            sub_base_pos = double_base_pos + l1_idx * self.ptrs_per_index_block
            sub_last_pos = sub_base_pos + self.ptrs_per_index_block - 1
            role_map[blk] = (
                "index_double_2",
                (
                    f"Bloque #{blk:02d}: Índice Doble Nivel 2 (Subtabla [{l1_idx}], "
                    f"Posiciones lógicas {sub_base_pos} a {sub_last_pos})"
                ),
                {"position": sub_base_pos},
            )
            for l2_idx, data_blk in enumerate(self.indirect_double_l2_map.get(blk, [])):
                pos = sub_base_pos + l2_idx
                role_map[data_blk] = (
                    "indirect_double_data",
                    (
                        f"Bloque #{data_blk:02d}: Dato Indirecto Doble "
                        f"(Entrada [{l1_idx}][{l2_idx}], Posición lógica {pos})"
                    ),
                    {"position": pos},
                )

        triple_base_pos = self.direct_count + self.simple_count + self.double_count + 1
        triple_last_pos = self.total_logical_positions
        role_map[self.indirect_triple_block_id] = (
            "index_triple_1",
            (
                f"Bloque #{self.indirect_triple_block_id:02d}: Índice Triple Nivel 1 "
                f"(Posiciones lógicas {triple_base_pos} a {triple_last_pos})"
            ),
            {"position": triple_base_pos},
        )
        for blk in self.indirect_triple_l1_entries + self.indirect_triple_l2_entries:
            role_map[blk] = (
                "index_triple_sub",
                (
                    f"Bloque #{blk:02d}: Subíndice Triple (Nivel intermedio, "
                    f"Posiciones lógicas {triple_base_pos} a {triple_last_pos})"
                ),
                {"position": triple_base_pos},
            )
        for idx, blk in enumerate(self.indirect_triple_data_blocks):
            pos = triple_base_pos + idx
            role_map[blk] = (
                "indirect_triple_data",
                (
                    f"Bloque #{blk:02d}: Dato Indirecto Triple "
                    f"(Entrada [{idx}], Posición lógica {pos})"
                ),
                {"position": pos},
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
                f"N = {logical_position} − 1 = {n}  │  0 ≤ {n} < {self.direct_count} "
                f"(Directo)  ➜  Inodo.Directo[{n}] = Bloque #{phys_block:02d}"
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
                    "title": "Conversión a Índice de Bloque Lógico",
                    "explanation": (
                        f"Para la posición lógica {logical_position}, se resta 1 porque las "
                        f"tablas internas del sistema operativo comienzan a numerarse desde 0: "
                        f"N = {logical_position} − 1 = {n}."
                    ),
                    "highlight_dom": f"ptr-direct-{n}",
                    "disk_block": phys_block,
                },
                {
                    "step_num": 2,
                    "title": "Verificación de Rango Directo",
                    "explanation": (
                        f"El inodo dispone de {self.direct_count} punteros directos (índices "
                        f"0 al {self.direct_count - 1}). Como N = {n} < {self.direct_count}, "
                        f"se consulta directamente la entrada Directo [{n}] del inodo."
                    ),
                    "highlight_dom": f"ptr-direct-{n}",
                    "disk_block": phys_block,
                },
                {
                    "step_num": 3,
                    "title": "Acceso al Bloque Físico en Disco",
                    "explanation": (
                        f"La entrada Directo [{n}] apunta al Bloque Físico #{phys_block:02d}. "
                        "Se accede a los datos en disco en una única lectura."
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
                f"N = {logical_position} − 1 = {n}  │  d = {n} − {self.direct_count} = {rel_idx}  "
                f"➜  Tabla(#{idx_block:02d})[{rel_idx}] = Bloque #{phys_block:02d}"
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
                    "title": "Conversión a Índice Lógico y Desborde Directo",
                    "explanation": (
                        f"Se resta 1 a la posición {logical_position} porque los índices "
                        f"internos comienzan desde 0: N = {logical_position} − 1 = {n}. Como "
                        f"N = {n} supera los {self.direct_count} punteros directos (0..{self.direct_count - 1}), "
                        "se recurre al Puntero Indirecto Simple."
                    ),
                    "highlight_dom": "ptr-indirect-1",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 2,
                    "title": "Lectura de la Tabla de Índice Simple",
                    "explanation": (
                        f"El Puntero Indirecto Simple del inodo apunta al Bloque Físico "
                        f"#{idx_block:02d} en disco, que almacena una tabla con "
                        f"{self.ptrs_per_index_block} entradas (índices 0 al {self.ptrs_per_index_block - 1})."
                    ),
                    "highlight_dom": "simple-node-parent",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 3,
                    "title": "Cálculo de la Entrada en la Tabla",
                    "explanation": (
                        f"Se restan los {self.direct_count} bloques directos previos para "
                        f"obtener la posición dentro de la tabla: Entrada = {n} − {self.direct_count} "
                        f"= [{rel_idx}]. En el bloque #{idx_block:02d}, la Entrada [{rel_idx}] "
                        f"contiene la dirección #{phys_block:02d}."
                    ),
                    "highlight_dom": f"simple-entry-{rel_idx}",
                    "disk_block": idx_block,
                },
                {
                    "step_num": 4,
                    "title": "Acceso al Bloque Físico de Datos",
                    "explanation": (
                        f"Obtenida la dirección en la tabla de índice simple, se realiza el "
                        f"segundo acceso a disco para leer el Bloque Físico #{phys_block:02d}."
                    ),
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }

    def _resolve_indirect_double(self, n: int, logical_position: int) -> dict[str, Any]:
        k = self.ptrs_per_index_block
        dbl_base = self.direct_count + self.simple_count
        rel_double = n - dbl_base
        l1_idx = rel_double // k
        l2_block_id = self.indirect_double_l1_entries[l1_idx]
        l2_entries = self.indirect_double_l2_map[l2_block_id]
        l2_idx = rel_double % k
        phys_block = l2_entries[l2_idx]
        n1_block_id = self.indirect_double_block_id
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "INDIRECT_DOUBLE",
            "physical_block": phys_block,
            "pointer_label": "Ind. Doble",
            "pointer_dom_id": "ptr-indirect-2",
            "formal_calc": (
                f"N = {n}  │  d = {n} − {dbl_base} = {rel_double}  │  "
                f"i₁ = ⌊{rel_double} ÷ {k}⌋ = [{l1_idx}] (N2 #{l2_block_id:02d})  │  "
                f"i₂ = {rel_double} mod {k} = [{l2_idx}]  ➜  Bloque #{phys_block:02d}"
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
                    "name": f"Índice N1 #{n1_block_id:02d}",
                    "info": f"Entrada [{l1_idx}] ➜ Blk #{l2_block_id:02d}",
                    "block": n1_block_id,
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
                    "title": "Desplazamiento dentro del Indirecto Doble",
                    "explanation": (
                        f"Primero se pasa a numeración desde 0: N = {logical_position} − 1 = {n}. "
                        f"Luego se restan los {self.direct_count} bloques directos y los "
                        f"{self.simple_count} del indirecto simple ({dbl_base} en total): "
                        f"d = {n} − {dbl_base} = {rel_double}."
                    ),
                    "highlight_dom": "double-node-n1",
                    "disk_block": n1_block_id,
                },
                {
                    "step_num": 2,
                    "title": "Selección de Subtabla en Nivel 1 (División Entera)",
                    "explanation": (
                        f"Cada subtabla de Nivel 2 abarca {k} bloques. Dividiendo el "
                        f"desplazamiento d = {rel_double} entre {k}, el cociente entero es "
                        f"{rel_double} ÷ {k} = [{l1_idx}]. En la tabla N1 (#{n1_block_id:02d}), "
                        f"la entrada [{l1_idx}] apunta a la Subtabla N2 en el bloque #{l2_block_id:02d}."
                    ),
                    "highlight_dom": f"double-node-n2-{l1_idx}",
                    "disk_block": l2_block_id,
                },
                {
                    "step_num": 3,
                    "title": "Posición dentro de la Subtabla N2 (Resto)",
                    "explanation": (
                        f"El resto de la división ({rel_double} mod {k} = [{l2_idx}]) indica "
                        f"qué fila leer dentro de la Subtabla N2 (#{l2_block_id:02d}). "
                        f"La Entrada [{l1_idx}][{l2_idx}] contiene el bloque físico #{phys_block:02d}."
                    ),
                    "highlight_dom": f"double-entry-{logical_position}",
                    "disk_block": l2_block_id,
                },
                {
                    "step_num": 4,
                    "title": "Acceso al Bloque Físico de Datos",
                    "explanation": (
                        f"Tras recorrer el bloque N1 (#{n1_block_id:02d}) y la subtabla N2 "
                        f"(#{l2_block_id:02d}), el tercer acceso a disco lee el Bloque Físico "
                        f"de Datos #{phys_block:02d}."
                    ),
                    "highlight_dom": f"disk-cell-{phys_block}",
                    "disk_block": phys_block,
                },
            ],
        }

    def _resolve_triple(self, n: int, logical_position: int) -> dict[str, Any]:
        k = self.ptrs_per_index_block
        k2 = k * k
        triple_base = self.direct_count + self.simple_count + self.double_count
        rel_triple = n - triple_base
        i1 = rel_triple // k2
        i2 = (rel_triple % k2) // k
        idx = rel_triple % len(self.indirect_triple_data_blocks)
        phys_block = self.indirect_triple_data_blocks[idx]
        l1_id = self.indirect_triple_block_id
        l2_id = self.indirect_triple_l1_entries[0]
        l3_id = self.indirect_triple_l2_entries[0]
        return {
            "logical_position": logical_position,
            "logical_block_index": n,
            "route_type": "INDIRECT_TRIPLE",
            "physical_block": phys_block,
            "pointer_label": "Ind. Triple",
            "pointer_dom_id": "ptr-indirect-3",
            "formal_calc": (
                f"N = {n}  │  d = {n} − {triple_base} = {rel_triple}  │  "
                f"(i₁, i₂, i₃) = ([{i1}], [{i2}], [{idx}])  ➜  "
                f"#{l1_id:02d} ➜ #{l2_id:02d} ➜ #{l3_id:02d} ➜ Bloque #{phys_block:02d}"
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
                    "info": f"Entrada [{i1}] ➜ N2 #{l2_id:02d}",
                    "block": l1_id,
                },
                {
                    "role": "index",
                    "name": f"Índice N2 #{l2_id:02d}",
                    "info": f"Entrada [{i2}] ➜ N3 #{l3_id:02d}",
                    "block": l2_id,
                },
                {
                    "role": "index",
                    "name": f"Índice N3 #{l3_id:02d}",
                    "info": f"Entrada [{idx}] ➜ Dato #{phys_block:02d}",
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
                    "title": "Desplazamiento dentro del Indirecto Triple",
                    "explanation": (
                        f"Se pasa a numeración desde 0 (N = {logical_position} − 1 = {n}) y "
                        f"se restan los bloques cubiertos antes del triple ({self.direct_count} "
                        f"directos + {self.simple_count} simples + {self.double_count} dobles = "
                        f"{triple_base}): d = {n} − {triple_base} = {rel_triple}."
                    ),
                    "highlight_dom": "ptr-indirect-3",
                    "disk_block": l1_id,
                },
                {
                    "step_num": 2,
                    "title": "Tabla de Nivel 1 (Bloque N1)",
                    "explanation": (
                        f"Cada entrada de Nivel 1 abarca {k} × {k} = {k2} bloques. El cociente "
                        f"entero {rel_triple} ÷ {k2} = [{i1}] selecciona la entrada [{i1}] del "
                        f"bloque N1 (#{l1_id:02d}), que apunta al bloque N2 #{l2_id:02d}."
                    ),
                    "highlight_dom": "triple-node-n1",
                    "disk_block": l1_id,
                },
                {
                    "step_num": 3,
                    "title": "Tabla de Nivel 2 (Bloque N2)",
                    "explanation": (
                        f"Cada entrada de Nivel 2 abarca {k} bloques. El cociente entero "
                        f"{rel_triple % k2} ÷ {k} = [{i2}] dentro del bloque N2 (#{l2_id:02d}) "
                        f"dirige hacia el bloque de tercer nivel N3 #{l3_id:02d}."
                    ),
                    "highlight_dom": "triple-node-n2",
                    "disk_block": l2_id,
                },
                {
                    "step_num": 4,
                    "title": "Tabla de Nivel 3 (Bloque N3)",
                    "explanation": (
                        f"El resto de la división ({rel_triple} mod {k} = [{idx}]) indica la "
                        f"Entrada [{idx}] en la tabla N3 (#{l3_id:02d}), donde se encuentra "
                        f"la dirección física #{phys_block:02d}."
                    ),
                    "highlight_dom": f"triple-entry-{logical_position}",
                    "disk_block": l3_id,
                },
                {
                    "step_num": 5,
                    "title": "Acceso al Bloque Físico de Datos",
                    "explanation": (
                        f"Recorrida la cadena N1 (#{l1_id:02d}) ➜ N2 (#{l2_id:02d}) ➜ "
                        f"N3 (#{l3_id:02d}), el cuarto acceso a disco lee el Bloque Físico "
                        f"de Datos #{phys_block:02d}."
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
