# Spec — Simulación de Inodos y Disco Físico

> Spec de la simulación `inodes` (SDD · Fase 0). Satisface el contrato de
> [spec.md §6](../spec.md).

## 1. Descripción

Traduce una **posición lógica de un archivo (base 1)** al **bloque físico de disco** que la
contiene, mostrando la cadena de indirección recorrida y una explicación paso a paso.
Modela el esquema de inodos con punteros directos e indirectos simple/doble/triple sobre
un disco fragmentado de 100 bloques.

## 2. Parámetros del modelo

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| `block_size` | 4096 | Informativo |
| `total_disk_blocks` | 100 | Bloques `#00`–`#99` |
| `direct_pointer_count` | 12 | Punteros directos en el inodo |
| `ptrs_per_index_block` | 4 | Punteros por bloque de índice |
| `double_index_count` | 2 | Subtablas N2 del indirecto doble |
| `seed` | entero o `None` | Determina la disposición aleatoria |

### Capacidad por nivel

| Nivel | Bloques de datos | Rango de N (base 0) | Rango de posición (base 1) |
|-------|------------------|---------------------|----------------------------|
| Directo | 12 | 0–11 | 1–12 |
| Indirecto simple | 4 | 12–15 | 13–16 |
| Indirecto doble | 2 × 4 = 8 | 16–23 | 17–24 |
| Indirecto triple | 4 | 24–27 | 25–28 |
| **Total** | **28** | 0–27 | **1–28** |

> El indirecto triple se modela con una cadena fija N1 ➜ N2 ➜ N3 ➜ 4 bloques de datos
> (didáctico, no extensión real de capacidad).

## 3. Bloques del disco

El disco se rellena con `rng.sample(range(100), total_needed)` — sin repeticiones — de
forma que los bloques de datos e índices quedan **dispersos** (fragmentación realista).
Roles asignados:

| Rol (`role`) | Descripción |
|--------------|-------------|
| `direct` | Dato apuntado por un puntero directo |
| `index_simple` | Bloque de índice del indirecto simple |
| `indirect_simple_data` | Dato apuntado por el índice simple |
| `index_double_1` / `index_double_2` | Índice doble N1 / subtabla N2 |
| `indirect_double_data` | Dato del indirecto doble |
| `index_triple_1` / `index_triple_sub` | Índice triple N1 / niveles intermedios |
| `indirect_triple_data` | Dato del indirecto triple |
| `free` | Bloque no usado |

## 4. Fórmulas de resolución

- `N = posición - 1` (paso de base 1 a base 0).
- Directo: si `N < 12` ⇒ `direct_blocks[N]`.
- Simple: si `12 ≤ N < 16` ⇒ entrada `N - 12` del bloque de índice simple.
- Doble: si `16 ≤ N < 24` ⇒ `rel = N - 16`; `L1 = rel // 4`; `L2 = rel % 4` ⇒
  `l2_map[l1_entries[L1]][L2]`.
- Triple: si `N ≥ 24` ⇒ `rel = N - 24`; recorrido `N1 ➜ N2 ➜ N3 ➜ data[rel % 4]`.

## 5. API

### Estado (`get_state()`)

Clave: misma salida que hoy expone `get_structure()` (el JS y las plantillas la consumen):

```json
{
  "meta": { "slug": "inodes", "seed": 42 },
  "block_size": 4096, "inode_id": 42, "mode": "-rw-r--r--", "uid": 1000, "gid": 1000,
  "total_blocks": 100, "total_logical_positions": 28,
  "direct_pointers": [ { "index": 0, "position": 1, "block": 14 }, … ],
  "indirect_simple": { "block_id": 22, "entries": [ … ] },
  "indirect_double": { "block_id": 53, "l1_entries": [ … ], "l2_map": { … } },
  "indirect_triple": { "block_id": 71, "l1_entries": [ … ], "l2_entries": [ … ], "data_blocks": [ … ] },
  "disk_blocks": [ { "id": 0, "label": "00", "role": "free", "desc": "…" }, … ]
}
```

### Acciones (`dispatch`)

| Acción | Payload | Resultado |
|--------|---------|-----------|
| `resolve` | `{"pos": 18}` | Resolución completa: `route_type`, `physical_block`, `formal_calc`, `substructures[]`, `steps[]` |
| `randomize` | `{}` (usa `payload.seed` si se pasa) | Devuelve el estado con una disposición nueva. Equivale a cambiar de semilla |

> `randomize` no muta estado del servidor: el cliente recibe la nueva semilla en
> `state.meta.seed` y puede recargar con ella (`/?seed=nuevo`).

### Errores de dominio (`SimulationError` ⇒ 400)

- `pos` no entero, `< 1` o `> total_logical_positions`.
- Configuración inválida (bloques duplicados / fuera de rango) al construir.

## 6. Contrato de determinismo

`InodeSimulation(seed=k)` produce **siempre** las mismas direcciones. Los tests usan seeds
fijos. `seed=None` usa el generador por defecto (para renders "aleatorios" de arranque).

## 7. Criterios de aceptación

- CA1 · `resolve(10)` ⇒ `route_type="DIRECT"`, `physical_block == direct_blocks[9]`.
- CA2 · `resolve(14)` ⇒ `INDIRECT_SIMPLE`, `table_index == 1`.
- CA3 · `resolve(18)` ⇒ `INDIRECT_DOUBLE`; `resolve(26)` ⇒ `INDIRECT_TRIPLE`.
- CA4 · `resolve(0)` y `resolve(29)` ⇒ `SimulationError`.
- CA5 · `randomize(seed=x)` ⇒ mismo estado que `InodeSimulation(seed=x).get_state()`.
- CA6 · Ningún bloque físico repetido en toda la disposición.
- CA7 · La página inicial carga con 200 y el estado embebido es coherente.

## 8. UI asociada

- Plantilla: `inodes/templates/inodes/index.html` (extiende `base.html`).
- JS: `static/inodes/js/simulator.js` + `modules/{controller,data,panels,utils}.js`.
- Interacciones: input de posición, chips de ejemplo, clic en punteros/índices/celdas,
  carrusel de pasos con autoplay, botón de aleatorizar.
