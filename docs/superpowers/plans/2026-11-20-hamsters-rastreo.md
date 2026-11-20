# RASTREO DE HÁMSTERS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir RASTREO DE HÁMSTERS como 13ª prueba de Konitive: observar un tablero 3×4 con dos hámsters idénticos entre diez gatos, seguir sus desplazamientos con las identidades ocultas y señalar las dos casillas finales.

**Architecture:** Toda la lógica pura (tablero, rastreo de identidades, movimientos, dificultad y puntuación) vive en `juego/rastreo.py` con los nueve componentes de la spec. `arbitro/rastreo.py` precalcula la partida con `GameManager.generar()` y emite las cuatro fases por WebSocket. Se registra como **juego dedicado, igual que `cajas` y `operaciones`**: entra en `JUEGOS_FIESTA` y `NOMBRES_JUEGOS`, con su propio handler en `servidor.py` y su propia rama en `arbitro/sesiones.py`. **No entra en `JUEGOS_MINI`**: `test_minijuegos.py:437` itera esa tupla con el protocolo genérico de una respuesta por ronda, que no sirve para la selección de dos casillas; `test_ppt.py:134-135` además exige que `ppt` cierre `JUEGOS_MINI` y `JUEGOS_FIESTA`. El cliente reutiliza `AVE_SVG` y añade casos explícitos en `manejar(msg)`.

**Tech Stack:** Python 3.13, FastAPI + WebSockets, JavaScript y CSS sin frameworks, suites `test_*.py` ejecutables como scripts (no pytest).

**Spec:** `docs/superpowers/specs/2026-11-20-hamsters-rastreo-design.md`

## Global Constraints

- Id interno `rastreo`. Nombre visible exacto `RASTREO DE HÁMSTERS`. Noveno minijuego y 13ª prueba; va justo antes de `ppt` en `JUEGOS_FIESTA` y en el selector.
- Tablero siempre de `FILAS = 3`, `COLUMNAS = 4`, `CELDAS = 12`; índice `fila * 4 + columna`. Siempre lleno: 10 celdas `"G"` y los hamsters `"h1"`, `"h2"`. Nunca se almacena `None`.
- Los dos hamsters comparten sprite y color: reutilizar `AVE_SVG` y fijar `PELAJES[0] = ["#e3a24f", "#fbe6c4"]` en `--pelo`/`--panza` para ambos. Sin emoji, sin clases que los distingan y sin svg nuevo.
- `h1`/`h2` son identificadores internos del servidor: **nunca** viajan al cliente.
- `RONDAS_RASTREO = 6`; 3 s de cuenta previa compartida (`TIEMPO_CUENTA_PREVIA`); 12 s para identificar; pausa de 2,5 s entre rondas y 1,0 s tras la última.
- Brain Age = `tiempo + 5 s por error` (menor es mejor) con `brain_age_y_puntos` (`arbitro/minijuegos.py:108`); `errores = 2 - aciertos`; `precision = 100 * aciertos / 2`.
- Cuatro niveles con parámetros independientes: `facil`, `normal`, `dificil`, `experto`. **`experto` no se añade a `DIFICULTADES_FIESTA`**: `ronda_generador` indexa una tupla de tres saltos y se rompería. En su lugar, `rastreo` es el único juego que ofrece `experto`: el cliente añade esa opción sólo a su fila del lobby, `leer_ajustes_fiesta` la acepta sólo cuando `juego == "rastreo"`, y `bucle_rastreo` lee la base con `ajuste_actual(sala).get("dificultad", "facil")` y calcula `nivel_para_ronda(base, ronda)` (sin `ronda_generador`), de modo que la dificultad sube una vez por ronda hasta experto. Los otros ocho minijuegos conservan sus tres niveles. En INDIVIDUAL la base es `facil` y se alcanza experto en la ronda 4.
- En FIESTA la pantalla ve el tablero y el resultado; los mandos reciben `{"mira": True}`, la dirección/línea/duración de cada entrada y `{"celdas": 12}`, nunca posiciones de hamsters ni `h1`/`h2`. Hasta 8 mandos (`MAX_MANDOS = 8`).
- Mensajes: `rastreo_countdown`, `rastreo_show`, `rastreo_hide`, `rastreo_move`, `rastreo_write`, `rastreo_answer`, `rastreo_feedback`, `rastreo_result`, `rastreo_over`.
- Toda la interfaz en español; papel/tinta, esquinas rectas, sombras duras, sin blur; botones de al menos 44 px y texto de al menos 14 px en celular.
- `test_rastreo.py` sigue el patrón del repo (`test_ppt.py:329-353`): funciones `probar_*`, un `main()` que las llama en orden con un `print` por cada una y `if __name__ == "__main__": asyncio.run(main())`. No existe pytest aquí: sin `main()`, `python test_rastreo.py` no ejecuta nada. El servidor de prueba usa el puerto `8786` (los demás usan 8765–8771 y 8782). Cada tarea añade su función a `main()`.

## Review Focus

- **Un hamster sale dos veces o reaparece sobre el otro**: debe conservar su id y seguir siendo exactamente dos — pin en Task 1, `probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas`.
- **Entrada por los cuatro lados con el otro hamster en el extremo de salida**: la fila/columna se desplaza entera, la cuadrícula sigue siendo 3×4 y no hay colisión — pin en Task 1, `probar_rastreo_desplazamientos_en_los_cuatro_lados`.
- **Selección inválida** (0, 1 o 3 casillas, repetida, fuera de 0–11, booleano, ronda vieja o segundo envío): se ignora y la ronda sigue abierta — pin en Task 4, dentro de `probar_rastreo_individual_y_seleccion_invalida`.
- **FIESTA filtrando secretos**: `h1`/`h2` y las posiciones finales no aparecen en `_show`, `_move`, `_write` ni `_result` de los mandos — pin en Task 4, `probar_rastreo_fiesta_mandos_sin_posiciones`.
- **Animaciones solapadas**: los movimientos llegan secuencialmente con `intervalo` y un nuevo `_move` o `detenerTimers()` cancela la animación pendiente — pin en Task 4 (`probar_rastreo_movimientos_secuenciales`) y Task 5 (`probar_rastreo_cliente_reutiliza_sprite_y_fases`).
- **No romper los otros juegos**: `rastreo` fuera de `JUEGOS_MINI`, `ppt` último y las aserciones de `test_ppt.py`/`test_minijuegos.py` intactas salvo el reajuste de documentación en Task 6.

---

### Task 1: Tablero, hamsters, movimientos y generador de gatos

**Files:**
- Create: `juego/rastreo.py`
- Test: `test_rastreo.py`

**Interfaces:**
- Consumes: nada.
- Produces: constantes `FILAS = 3`, `COLUMNAS = 4`, `CELDAS = 12`, `HAMSTERS = ("h1", "h2")`, `LADOS = ("izquierda", "derecha", "arriba", "abajo")`; clases `BoardManager`, `HamsterManager`, `MovementSystem`, `CatSpawner` con las firmas de abajo. Todas reciben un `random.Random` inyectado para que los tests sean deterministas.

```python
class BoardManager:
    def __init__(self, rng: random.Random) -> None: ...
    def inicializar(self) -> None: ...          # 10 "G" + "h1" + "h2" revueltos
    def get(self, indice: int) -> str: ...
    def set(self, indice: int, valor: str) -> None: ...
    def instantanea(self) -> list[str]: ...     # copia plana de 12

class HamsterManager:
    def __init__(self, rng: random.Random) -> None: ...
    def posiciones(self, tablero: BoardManager) -> dict[str, int]: ...
    def regenerar(self, tablero: BoardManager) -> int: ...

class MovementSystem:
    def __init__(self, tablero: BoardManager, hamsters: HamsterManager) -> None: ...
    def aplicar(self, lado: str, linea: int) -> dict: ...

class CatSpawner:
    def __init__(self, rng: random.Random) -> None: ...
    def siguiente(self) -> tuple[str, int]: ...
```

- [ ] **Step 1: Write the failing tests**

Crear `test_rastreo.py` con las pruebas puras (sin servidor) y el esqueleto `main()`:

```python
import random
from juego.rastreo import (
    CELDAS, HAMSTERS, LADOS, BoardManager, CatSpawner,
    HamsterManager, MovementSystem,
)

def probar_tablero_arranca_con_10_gatos_y_2_hamsters():
    tablero = BoardManager(random.Random(7))
    tablero.inicializar()
    assert len(tablero.instantanea()) == CELDAS == 12
    assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_desplazamientos_en_los_cuatro_lados():
    for lado in LADOS:
        tablero = BoardManager(random.Random(3))
        hamsters = HamsterManager(random.Random(3))
        tablero.inicializar()
        movimiento = MovementSystem(tablero, hamsters).aplicar(lado, 0)
        assert movimiento["lado"] == lado
        assert len(tablero.instantanea()) == 12
        assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas():
    rng = random.Random(11)
    tablero, hamsters = BoardManager(rng), HamsterManager(rng)
    tablero.inicializar()
    sistema, spawner = MovementSystem(tablero, hamsters), CatSpawner(rng)
    finales = set()
    for _ in range(200):
        lado, linea = spawner.siguiente()
        sistema.aplicar(lado, linea)
        pos = hamsters.posiciones(tablero)
        assert set(pos) == set(HAMSTERS)
        assert len(set(pos.values())) == 2
        finales.update(pos.values())
    assert finales <= set(range(12))

def main():
    probar_tablero_arranca_con_10_gatos_y_2_hamsters()
    probar_desplazamientos_en_los_cuatro_lados()
    probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas()
    print("\nOK - Rastreo de hamsters correcto")

if __name__ == "__main__":
    main()
```

`MovementSystem.aplicar` debe devolver `{"lado": str, "linea": int, "entrada": int, "salida": int, "reaparecio": int | None}`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python test_rastreo.py`
Expected: `ModuleNotFoundError: No module named 'juego.rastreo'`.

- [ ] **Step 3: Implement `juego/rastreo.py`**

`BoardManager.inicializar` baraja `["G"]*10 + ["h1","h2"]` con `rng.shuffle`. En `aplicar`, construye la lista ordenada de índices desde la entrada hasta la salida (`"izquierda"` → fila `linea`, columnas `0..3`; `"derecha"` → columnas `3..0`; `"arriba"` → columna `linea`, filas `0..2`; `"abajo"` → filas `2..0`), desplaza cada valor una posición hacia la salida y escribe `"G"` en la entrada. Si el valor expulsado es un hamster, llama a `hamsters.regenerar(tablero)` y devuelve su índice en `reaparecio`. `HamsterManager.regenerar` elige uniformemente entre los 12 índices **excepto** el que ocupa el otro hamster en el tablero ya desplazado, y sobrescribe esa celda (que contendrá un gato) con el hamster que vuelve. `CatSpawner.siguiente` elige `lado = rng.choice(LADOS)` y `linea = rng.randrange(3)` para lados horizontales o `rng.randrange(4)` para verticales.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python test_rastreo.py`
Expected: PASS (3 pruebas).

- [ ] **Step 5: Commit**

```bash
git add juego/rastreo.py test_rastreo.py
git commit -m "feat: tablero y movimientos de rastreo de hamsters"
```

---

### Task 2: Dificultad, selección, puntuación y GameManager

**Files:**
- Modify: `juego/rastreo.py`
- Test: `test_rastreo.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `RONDAS_RASTREO = 6`, `NIVELES` (dict de cuatro niveles), `DifficultyManager.obtener(nivel: str) -> dict`, `SelectionManager` (`registrar(celda: int) -> bool`, `seleccionadas() -> tuple[int, ...]`, `completa() -> bool`), `ScoreManager.evaluar(seleccion: tuple[int, ...], posiciones: dict[str, int]) -> dict`, `GameManager.generar(nivel: str = "normal", semilla: int | None = None) -> dict` con claves `observacion` (lista de 12), `movimientos` (lista de `{"lado","linea","duracion"}`), `final` (dict `h1`/`h2` → índice) y `parametros` (copia del nivel). El dict devuelto es plano y serializable; no contiene instancias de las clases.

- [ ] **Step 1: Write the failing tests**

Añadir a `test_rastreo.py` y a su `main()`:

```python
from juego.rastreo import (
    DifficultyManager, GameManager, NIVELES, RONDAS_RASTREO,
    ScoreManager, SelectionManager,
)

def probar_cuatro_niveles_con_parametros_independientes():
    assert tuple(NIVELES) == ("facil", "normal", "dificil", "experto")
    claves = {"observacion", "movimiento", "entradas", "intervalo", "animacion"}
    for parametros in NIVELES.values():
        assert set(parametros) == claves
    assert NIVELES["facil"]["entradas"] < NIVELES["experto"]["entradas"]
    assert NIVELES["facil"]["animacion"] > NIVELES["experto"]["animacion"]
    for parametros in NIVELES.values():
        assert parametros["entradas"] * parametros["intervalo"] <= parametros["movimiento"]

def probar_seleccion_exige_dos_casillas_distintas():
    seleccion = SelectionManager()
    assert seleccion.registrar(3) is True
    assert seleccion.registrar(3) is False
    assert seleccion.registrar(9) is True
    assert seleccion.registrar(1) is False
    assert seleccion.seleccionadas() == (3, 9)
    assert seleccion.completa() is True

def probar_puntaje_y_generador_son_deterministas():
    assert ScoreManager.evaluar((3, 9), {"h1": 3, "h2": 7}) == {
        "aciertos": 1, "errores": 1, "precision": 50.0,
    }
    a = GameManager.generar("normal", semilla=42)
    b = GameManager.generar("normal", semilla=42)
    assert a == b
    assert RONDAS_RASTREO == 6
    assert len(a["observacion"]) == 12
    assert len(a["movimientos"]) == NIVELES["normal"]["entradas"]
    assert set(a["final"]) == {"h1", "h2"}
    assert len(set(a["final"].values())) == 2
    assert all(m["lado"] in LADOS for m in a["movimientos"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python test_rastreo.py`
Expected: `ImportError` de `DifficultyManager` / `GameManager`.

- [ ] **Step 3: Implementar los cuatro componentes**

`NIVELES` con estos valores exactos (segundos; `animacion` es la duración de cada desplazamiento):

| nivel | observacion | movimiento | entradas | intervalo | animacion |
|---|---|---|---|---|---|
| facil | 6.0 | 6.0 | 4 | 1.5 | 0.45 |
| normal | 5.0 | 8.0 | 6 | 1.3 | 0.35 |
| dificil | 4.0 | 10.0 | 9 | 1.1 | 0.25 |
| experto | 3.0 | 12.0 | 12 | 1.0 | 0.18 |

`DifficultyManager.obtener` devuelve `NIVELES[nivel]` o `NIVELES["facil"]` si el nivel no existe (entrada no confiable). `SelectionManager.registrar` acepta sólo `int` no booleano en `0..11`, sin repetidos y hasta dos. `ScoreManager.evaluar` cuenta la intersección entre la selección y `posiciones.values()`, con `errores = 2 - aciertos` y `precision = 100 * aciertos / 2`. `GameManager` guarda las cuatro fases internas y `generar` ejecuta los movimientos en orden con `MovementSystem`/`CatSpawner`, usando `duracion = parametros["animacion"]` para cada uno; `observacion` es la instantánea inicial y `final` las posiciones tras la última entrada. `GameManager` también expone `fase_actual()` y `avanzar()` para que el árbitro pueda reproducir el plan, pero `generar` debe ser suficiente para la emisión completa.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python test_rastreo.py`
Expected: PASS (6 pruebas).

- [ ] **Step 5: Commit**

```bash
git add juego/rastreo.py test_rastreo.py
git commit -m "feat: dificultad, seleccion y puntuacion de rastreo"
```

---

### Task 3: Registro del juego y contrato del cliente

**Files:**
- Modify: `arbitro/nucleo.py:26-39,186-204`
- Modify: `static/index.html:82-95`
- Modify: `static/app.js:41-61,378-394,889-905,1789-1799`
- Modify: `static/estilos.css` (selectores vacíos junto a `.ppt-*`)
- Test: `test_rastreo.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `"rastreo"` en `JUEGOS_FIESTA` en penúltima posición (antes de `ppt`), `NOMBRES_JUEGOS["rastreo"] == "RASTREO DE HÁMSTERS"`, `RONDAS_RASTREO == 6`, y **ausencia** en `JUEGOS_MINI`. Botón `<button type="button" class="boton-juego" data-juego="rastreo" aria-pressed="false">RASTREO DE HÁMSTERS</button>` en el selector, entre `silabas` y `ppt`.

- [ ] **Step 1: Write the failing tests**

Añadir a `test_rastreo.py` y a su `main()`:

```python
from juego.minijuegos import JUEGOS_MINI
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS

def probar_rastreo_registrado_como_13a_prueba():
    assert "rastreo" not in JUEGOS_MINI
    assert JUEGOS_FIESTA[-2] == "rastreo"
    assert JUEGOS_FIESTA[-1] == "ppt"
    assert NOMBRES_JUEGOS["rastreo"] == "RASTREO DE HÁMSTERS"

def probar_rastreo_contrato_cliente():
    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert 'data-juego="rastreo"' in html
    assert '"rastreo"' in js
    assert "rastreo_answer" in js
    assert "rastreo_move" in js
    assert ".rastreo-tablero" in css
    assert "@keyframes rastreo-entrada" in css
```

`BASE = Path(__file__).parent`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python test_rastreo.py`
Expected: fallos de aserción de registro y de contrato.

- [ ] **Step 3: Registrar el juego**

En `arbitro/nucleo.py`, extender `JUEGOS_FIESTA` para insertar `rastreo` antes de `ppt` sin alterar el orden de los ocho minijuegos:

```python
JUEGOS_FIESTA = ("pajaros", "escritura", "cajas", "operaciones") + tuple(
    j for j in JUEGOS_MINI if j != "ppt"
) + ("rastreo", "ppt")
```

`NOMBRES_JUEGOS` necesita una entrada explícita `rastreo: "RASTREO DE HÁMSTERS"` porque no está en `NOMBRES_MINI` (`JUEGOS_INDIVIDUAL = JUEGOS_FIESTA` en `servidor.py:240` lo incluye automáticamente en INDIVIDUAL). En `leer_ajustes_fiesta`, ampliar la validación de dificultad para aceptar `experto` sólo en este juego: `dificultad if dificultad in DIFICULTADES_FIESTA or (juego == "rastreo" and dificultad == "experto") else "facil"`.

En `static/app.js`: añadir `rastreo` a `NOMBRES_FIESTA`; definir `JUEGOS_FIESTA` como `["pajaros","escritura","cajas","operaciones", ...JUEGOS_MINI.filter(j => j !== "ppt"), "rastreo", "ppt"]`; en el `map` del `<select>` del lobby usar `(juego === "rastreo" ? [...DIFICULTADES, ["experto","EXPERTO"]] : DIFICULTADES)` para que la cuarta opción aparezca sólo en `rastreo`; en `match_start`, ampliar la condición a `(JUEGOS_MINI.includes(msg.modo) || msg.modo === "rastreo")` y usar `NOMBRES_FIESTA[msg.modo]` como nombre; en `tituloJuego`, añadir `rastreo: "RASTREO DE HÁMSTERS"`. Añadir el botón en `index.html` entre `silabas` y `ppt`. Dejar selectores `.rastreo-tablero`, `.rastreo-casilla` y `@keyframes rastreo-entrada` como placeholders vacíos; el render real llega en Task 5.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python test_rastreo.py`
Expected: PASS (8 pruebas).

- [ ] **Step 5: Commit**

```bash
git add arbitro/nucleo.py static/index.html static/app.js static/estilos.css test_rastreo.py
git commit -m "feat: registrar rastreo de hamsters como 13a prueba"
```

---

### Task 4: Árbitro de fases, validación y FIESTA

**Files:**
- Create: `arbitro/rastreo.py`
- Modify: `arbitro/sesiones.py:9-12,41-48,76-83`
- Modify: `servidor.py:41-49,199-201`
- Test: `test_rastreo.py`

**Interfaces:**
- Consumes: Task 3 (`rastreo` en `JUEGOS_FIESTA`), Tasks 1–2 (`GameManager.generar`, `SelectionManager`, `ScoreManager`, `brain_age_y_puntos`).
- Produces: `async def bucle_rastreo(sala: Sala) -> None`, `async def manejar_respuesta_rastreo(sala: Sala, jugador: Jugador, mensaje: dict) -> None`, `async def resumen_rastreo_individual(sala: Sala) -> dict`. Mensajes listados en Global Constraints. `sala.fase == "rastreo"` durante toda la ronda.

- [ ] **Step 1: Write the failing tests**

Añadir al final de `test_rastreo.py`. Primero los imports y el arranque del servidor, calcados de `test_ppt.py:10-55` (puerto `8786`):

```python
import asyncio, json, threading, time
from pathlib import Path
import uvicorn, websockets
import servidor
from arbitro import nucleo
from juego.rastreo import NIVELES, LADOS

async def pausa_corta(sala, segundos):
    await asyncio.sleep(0.01)

nucleo.pausa = pausa_corta
config = uvicorn.Config(servidor.app, host="127.0.0.1", port=8786, log_level="error")
servidor_uvicorn = uvicorn.Server(config)
threading.Thread(target=servidor_uvicorn.run, daemon=True).start()
while not servidor_uvicorn.started:
    time.sleep(0.02)
URL = "ws://127.0.0.1:8786/ws"
BASE = Path(__file__).parent
```

Después el `Cliente` de `test_ppt.py:58-90` (con `esperar(tipo, timeout=10, desde=0)`) y las tres pruebas:

```python
async def probar_rastreo_individual_y_seleccion_invalida():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "RASTREO", "juegos": ["rastreo"]})
    await cliente.esperar("room_created")
    show = await cliente.esperar("rastreo_show")
    assert len(show["tablero"]) == 12
    assert "final" not in show and "h1" not in show
    await cliente.esperar("rastreo_hide")
    movimientos = cliente.de_tipo("rastreo_move")
    await cliente.esperar("rastreo_write")
    assert len(movimientos) == NIVELES["facil"]["entradas"]
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3]})
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3, 3]})
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [3, 99]})
    assert not cliente.de_tipo("rastreo_feedback")
    await cliente.enviar({"type": "rastreo_answer", "ronda": show["ronda"], "respuesta": [0, 1]})
    assert len(cliente.de_tipo("rastreo_feedback")) == 1
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)

async def probar_rastreo_movimientos_secuenciales():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "SEC", "juegos": ["rastreo"]})
    await cliente.esperar("rastreo_show")
    await cliente.esperar("rastreo_write")
    movimientos = cliente.de_tipo("rastreo_move")
    assert [m["indice"] for m in movimientos] == list(range(1, len(movimientos) + 1))
    assert all(m["duracion"] > 0 and m["lado"] in LADOS for m in movimientos)
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)

async def probar_rastreo_fiesta_mandos_sin_posiciones():
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mando = Cliente(await websockets.connect(URL))
    await mando.enviar({"type": "join", "nombre": "Ana", "codigo": codigo})
    await mando.esperar("room_joined")
    await host.enviar({
        "type": "start", "juegos": ["rastreo"],
        "ajustes": {"rastreo": {"rondas": 1, "dificultad": "experto"}},
    })
    await host.esperar("rastreo_show")
    await mando.esperar("rastreo_show")
    await mando.esperar("rastreo_write")
    for mensaje in mando.recibidos:
        if mensaje["type"].startswith("rastreo_"):
            assert "tablero" not in mensaje and "final" not in mensaje
            assert "h1" not in mensaje and "h2" not in mensaje
    for cliente in (host, mando):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
```

`main()` pasa a ser `async def main()` con `asyncio.run(main())` al final y llama a las tres pruebas async tras las ocho síncronas.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python test_rastreo.py`
Expected: timeout esperando `rastreo_show`.

- [ ] **Step 3: Implementar el bucle**

En `arbitro/rastreo.py`: constantes `TIEMPO_IDENTIFICACION = 12.0` y `PAUSA_ENTRE_RONDAS = 2.5`. `bucle_rastreo` sigue la forma de `bucle_minijuego`: anuncia `match_start` con `modo="rastreo"`, y por ronda (a) difunde `rastreo_countdown` con `segundos = TIEMPO_CUENTA_PREVIA` y espera con `nucleo.pausa`, (b) lee la base `ajuste_actual(sala).get("dificultad", "facil")` (puede valer `experto`, porque `rastreo` no pasa por `ronda_generador`) y calcula `dificultad = nivel_para_ronda(base, ronda)` antes de `plan = GameManager.generar(dificultad)`; envía `rastreo_show` con `tablero = plan["observacion"]` **sólo a la pantalla** (`difundir_roles` con versión `{"mira": True}` para mandos), (c) espera `parametros["observacion"]`, (d) envía `rastreo_hide` y un `rastreo_move` por entrada con `{"indice","total","lado","linea","duracion"}`, esperando `intervalo` entre ellos con `nucleo.pausa` (comprobar `sala.cancelada` tras cada espera), (e) envía `rastreo_write` con `celdas: 12` y fija `momento_respuesta`, (f) espera `sala.evento_respuestas` con `TIEMPO_IDENTIFICACION`, y (g) envía `rastreo_result` con `reto` = posiciones finales y aciertos **sólo a la pantalla** y `{"type","ronda"}` a mandos. Acumula tiempos/errores por jugador con `brain_age_y_puntos` y cierra con `rastreo_over` (`brain_age`, `precision`, `tiempo_promedio`, `clasificacion`) y `registrar_resultado_individual`. En FIESTA emite `progreso_vivo` con cuántos mandos ya respondieron, nunca sus selecciones.

`manejar_respuesta_rastreo` valida `sala.fase == "rastreo"`, rol `mando` en fiesta, ronda vigente, `respuesta` lista/tupla de exactamente 2 `int` no booleanos distintos en `0..11`, y un solo envío por jugador; guarda `(seleccion, time.monotonic())`, envía `rastreo_feedback` privado con los aciertos de ese jugador y marca `sala.evento_respuestas` cuando respondieron todos. En `servidor.py`, importar el handler y añadir `elif tipo == "rastreo_answer": await manejar_respuesta_rastreo(sala, jugador, mensaje)` **antes** del despacho genérico `TIPOS_RESPUESTA_MINI`. En `arbitro/sesiones.py`, importar `bucle_rastreo` y añadir `elif juego == "rastreo": await bucle_rastreo(sala)` antes de `elif juego in JUEGOS_MINI` en `bucle_individual` y `bucle_fiesta`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python test_rastreo.py`
Expected: PASS (11 pruebas).

- [ ] **Step 5: Commit**

```bash
git add arbitro/rastreo.py arbitro/sesiones.py servidor.py test_rastreo.py
git commit -m "feat: arbitro de fases de rastreo con fiesta sin secretos"
```

---

### Task 5: Cliente — tablero, animación, selección y resultado

**Files:**
- Modify: `static/app.js:212-222,799-1120,1755-1787` (y ayudas nuevas)
- Modify: `static/estilos.css` (bloque `.rastreo-*` junto a `.ppt-*`)

**Interfaces:**
- Consumes: Task 3 (registro y contrato base), Task 4 (mensajes y payloads).
- Produces: `AnimationController` (objeto con `animar(movimiento)` y `detener()`), `mostrarRastreo(msg, fase)`, `configurarSeleccionRastreo(msg)`, `mostrarResultadoRastreo(msg)`. Casos explícitos en `manejar(msg)` para `rastreo_countdown`, `_show`, `_hide`, `_move`, `_write`, `_feedback`, `_result` y `_over` (ante el `default:` que llama a `identificarMini`, que no reconoce `rastreo` al no estar en `JUEGOS_MINI`).

- [ ] **Step 1: Write the failing tests**

Añadir a `test_rastreo.py` y a su `main()`:

```python
def probar_rastreo_cliente_reutiliza_sprite_y_fases():
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert "HAMSTER_PIXELES" in js and "AVE_SVG" in js
    assert "PELAJES[0]" in js
    assert "rastreo_hide" in js and "rastreo_result" in js
    assert "AnimationController" in js
    assert ".rastreo-casilla" in css
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python test_rastreo.py`
Expected: fallo de aserción.

- [ ] **Step 3: Implementar el render**

En `detenerTimers()`, llamar a `AnimationController.detener()`. Crear `AnimationController` con un `setTimeout` que aplica a las casillas de la fila/columna una animación de un solo disparo y limpia la clase al terminar `duracion * 1000`; un nuevo `animar()` cancela el temporizador anterior. En `estilos.css`, cuatro `@keyframes rastreo-entrada-{izquierda,derecha,arriba,abajo}` que desplazan la fila/columna exactamente una casilla (`calc(100% / 4 + var(--v-1))` en horizontal, `calc(100% / 3 + var(--v-1))` en vertical) con `steps(1, end)`, sin blur y respetando `prefers-reduced-motion`.

`mostrarRastreo` construye un `panelAmplio` con clase `respuesta-rastreo`: arriba `FASE 01 · OBSERVA` / `FASE 02 · SIGUE LAS CASILLAS` / `FASE 03 · SEÑALA DOS HÁMSTERS`, visual con `.rastreo-tablero` (grid de 3×4, `.rastreo-casilla` con borde y sombra dura), y abajo la barra de tiempo con `actualizarBarraCajas`. En observación, cada casilla contiene `AVE_SVG` si el valor no es `"G"`, con `--pelo`/`--panza` fijos a `PELAJES[0]` para ambos hamsters. En movimiento e identificación, todas las casillas muestran `?` en mono; el tablero del anfitrión no es interactivo. En `_write`, INDIVIDUAL permite tocar las casillas del propio tablero; FIESTA muestra el tablero en pantalla y los mandos reciben 12 botones numerados del 1 al 12. `configurarSeleccionRastreo` acumula hasta dos índices distintos, marca la selección con `outline: 3px solid var(--rojo)` y envía `{type:"rastreo_answer", ronda, respuesta:[i,j]}` al completar la segunda. `mostrarResultadoRastreo` revela los dos `AVE_SVG` en `reto.final`, marca cada selección en verde (acierto) o rojo (fallo) y muestra aciertos, precisión y Brain Age. En FIESTA el resultado detallado sólo se dibuja en la pantalla (`resultadoSoloEnPantalla()`), igual que los otros juegos. Para PC, la regla existente de `.panel-amplio` (`estilos.css:1629-1649`) ya reserva la columna grande; añadir `.panel-amplio .rastreo-tablero { height:auto; flex:1 1 auto; min-height:280px; }`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python test_rastreo.py`
Expected: PASS (12 pruebas).

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/estilos.css test_rastreo.py
git commit -m "feat: tablero y animaciones de rastreo en el cliente"
```

---

### Task 6: Documentación y verificación completa

**Files:**
- Modify: `README.md:11-14,46,91-105,155,229,254,296-310`
- Modify: `PRODUCT.md:20,27,39-41,47,61`
- Modify: `test_ppt.py:173-174`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: documentación con 13 pruebas y 9 minijuegos, sección nueva de RASTREO DE HÁMSTERS, orden fijo con `RASTREO DE HÁMSTERS` antes de `PIEDRA · PAPEL · TIJERA`, y `python test_rastreo.py` en la lista de suites.

- [ ] **Step 1: Write the failing test**

Añadir a `test_rastreo.py` y a su `main()`:

```python
def probar_documentacion_incluye_rastreo():
    readme = (BASE / "README.md").read_text(encoding="utf-8")
    producto = (BASE / "PRODUCT.md").read_text(encoding="utf-8")
    assert "RASTREO DE HÁMSTERS" in readme
    assert "13 pruebas" in readme or "las 13" in readme
    assert "nueve minijuegos" in readme
    assert "python test_rastreo.py" in readme
    assert "RASTREO DE HÁMSTERS" in producto
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python test_rastreo.py`
Expected: fallo de aserción de documentación.

- [ ] **Step 3: Actualizar documentación**

Sustituir «12 pruebas»/«ocho minijuegos» por «13 pruebas»/«nueve minijuegos» donde corresponda, añadir `RASTREO DE HÁMSTERS` en penúltimo lugar de la lista de orden fijo (`… → SÍLABAS → RASTREO DE HÁMSTERS → PIEDRA · PAPEL · TIJERA`), en el encabezado `## LOS OCHO MINIJUEGOS`, en el apartado de FIESTA y en la descripción de `juego/minijuegos.py`, añadir un párrafo corto con las cuatro fases y los cuatro niveles, y sumar `python test_rastreo.py` a los comandos de verificación. En `PRODUCT.md`, añadir el nombre a la terminología fija y a la lista de suites. **Actualizar también `test_ppt.py:173-174`** de `assert "12 pruebas" in readme/product` a `assert "13 pruebas" in readme/product`, y su `print` de la línea 345; es la única aserción existente que quedaría obsoleta. No tocar `DESIGN.md`: la identidad no cambia.

- [ ] **Step 4: Run all tests to verify everything passes**

Run: `python test_rastreo.py`
Expected: PASS (13 pruebas).

Run (barrido completo, en orden):

```powershell
$tests = @('test_reconocedor.py','test_partida.py','test_cajas.py','test_operaciones.py','test_salas.py','test_individual.py','test_silabas.py','test_minijuegos.py','test_ppt.py','test_revision.py','test_fiesta_progreso.py','test_rastreo.py'); foreach ($t in $tests) { python $t; if ($LASTEXITCODE -ne 0) { throw "Fallo: $t" } }
```

Expected: las 12 suites con código de salida 0.

Run: `node --check static/app.js`
Expected: sin salida, código 0.

- [ ] **Step 5: Commit y push**

```bash
git add README.md PRODUCT.md test_ppt.py
git commit -m "docs: documentar rastreo de hamsters como 13a prueba"
git push origin main
```

---

## Notas de ejecución

- Las suites se ejecutan como scripts: `python test_rastreo.py`. `python -m pytest` no recolecta pruebas en este repositorio.
- Cada tarea termina con commit; el push se hace al final de Task 6. No crear rama nueva: el flujo acordado es trabajar directamente en `main`.
- Verificación visual: con Chrome headless y un fixture HTML que cargue `static/estilos.css`, comprobar a 1440×900 y 390×844 que el tablero mantiene 3×4, que los dos hámsters son idénticos, que las casillas ocultas muestran `?` y que la selección de dos casillas cabe sin scroll.
- Enmienda posterior (petición del usuario): el `steps(1, end)` fijado en Task 5 hacía que la fila/columna saltara sin movimiento visible. Se sustituye por un deslizamiento continuo con `cubic-bezier(0.16, 1, 0.3, 1)` y se resalta con contorno rojo la línea en movimiento; `prefers-reduced-motion` conserva el contorno y cambia el fondo en lugar de trasladar. El nuevo contrato se fija en `probar_rastreo_deslizamiento_suave_de_linea`.
- Enmienda 2 (petición del usuario): animar también la salida y el regreso del hámster expulsado. `GameManager.avanzar` incorpora `salida` y `reaparecio` (índices, nunca `h1`/`h2`); `rastreo_move` usa `difundir_roles` para que la pantalla reciba esos índices y los mandos sigan sin secretos. El cliente reutiliza `AVE_SVG` y `PELAJES[0]` en un sprite superpuesto que cruza el borde y vuelve a entrar por el borde más cercano a su nueva casilla; `prefers-reduced-motion` sustituye el traslado por un fundido en el mismo sitio. Contratos en `probar_rastreo_salida_y_reaparicion_en_el_plan`, `probar_rastreo_cliente_animacion_salida_y_reaparicion` y `probar_rastreo_fiesta_mandos_sin_posiciones`.
- Enmienda 3 (petición del usuario): la dificultad estaba fija durante toda la partida (y en INDIVIDUAL siempre era `facil`). `nivel_para_ronda(base, ronda)` sube un nivel por ronda hasta `experto`; `bucle_rastreo` la aplica sin cambiar el protocolo y el cliente muestra la etiqueta. INDIVIDUAL pasa a usar los cuatro niveles. Contratos en `probar_nivel_para_ronda_escala_y_top`, `probar_rastreo_dificultad_sube_por_ronda`, `probar_rastreo_fiesta_escalera_desde_base` y `probar_rastreo_cliente_muestra_nivel`.
