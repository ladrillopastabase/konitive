# Progresión de dificultad en RASTREO DE HÁMSTERS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la dificultad de RASTREO DE HÁMSTERS suba una vez por ronda hasta experto, tanto en INDIVIDUAL como en FIESTA, y que ese cambio sea visible.

**Architecture:** Una función pura en `juego/rastreo.py` calcula el nivel de cada ronda a partir del nivel base; el árbitro la llama dentro del bucle de rondas y reutiliza los mensajes existentes, que ya llevan `dificultad`. El cliente añade esa etiqueta a la cuenta previa y a la fase de observación. No se tocan tablero, protocolo de secretos ni animación.

**Tech Stack:** Python 3 (asyncio + websockets), JavaScript vainilla (WAAPI), HTML/CSS, tests propios con `python test_rastreo.py`.

**Spec:** `docs/superpowers/specs/2026-11-20-hamsters-rastreo-progresion-dificultad.md`

## Global Constraints

- Secuencia exacta `facil → normal → dificil → experto`, con tope en `experto`.
- INDIVIDUAL empieza en `facil`; FIESTA empieza en el nivel elegido por el anfitrión.
- INDIVIDUAL usa los cuatro niveles: retirar «experto solo en FIESTA» de la documentación.
- `RONDAS_RASTREO == 6`; FIESTA permite `rondas` configurable.
- Sin cambios en ids internos `h1`/`h2`, tablero 3×4, contrato `salida`/`reaparecio` ni secreto de mandos.
- Sin `git add`, `git commit` ni `git push` sin autorización explícita del usuario (hay trabajo previo sin commitear en el árbol).

## Review Focus

- **Ronda 1 no debe desplazarse:** con base `normal`, la ronda 1 sigue siendo `normal`. Test: `probar_nivel_para_ronda_escala_y_top` en Task 1.
- **Tope en rondas largas:** con 10 rondas no se sale del tuple de niveles. Test: `probar_nivel_para_ronda_escala_y_top` en Task 1.
- **Base desconocida o ausente:** cae a `facil` en vez de lanzar `ValueError`. Test: `probar_nivel_para_ronda_escala_y_top` en Task 1.
- **INDIVIDUAL sin ajustes:** debe escalar desde `facil` y los parámetros deben acompañar a la etiqueta. Test: `probar_rastreo_dificultad_sube_por_ronda` en Task 2.
- **Mandos de FIESTA:** siguen sin `tablero`, `final`, `salida` ni ids, aunque suba la dificultad. Test: `probar_rastreo_fiesta_escalera_desde_base` en Task 2.

---

### Task 1: Función pura de progresión

**Files:**
- Modify: `juego/rastreo.py` (junto a `NIVELES`, líneas 105–133)
- Test: `test_rastreo.py` (junto a `probar_cuatro_niveles_con_parametros_independientes`)

**Interfaces:**
- Consumes: `NIVELES` de `juego/rastreo.py`.
- Produces: `nivel_para_ronda(base: str, ronda: int) -> str`; devuelve uno de `facil`, `normal`, `dificil`, `experto`. Task 2 lo importa desde `juego.rastreo`.

- [ ] **Step 1: Write the failing test**

Añadir a `test_rastreo.py` y a la lista de `main()`:

```python
def probar_nivel_para_ronda_escala_y_top():
    from juego.rastreo import nivel_para_ronda
    assert [nivel_para_ronda("facil", r) for r in range(1, 7)] == [
        "facil", "normal", "dificil", "experto", "experto", "experto",
    ]
    assert [nivel_para_ronda("normal", r) for r in range(1, 5)] == [
        "normal", "dificil", "experto", "experto",
    ]
    assert nivel_para_ronda("experto", 10) == "experto"
    assert nivel_para_ronda("desconocido", 3) == "facil"
    assert nivel_para_ronda("facil", 0) == "facil"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_rastreo.py`
Expected: FAIL con `ImportError: cannot import name 'nivel_para_ronda'`.

- [ ] **Step 3: Implement `nivel_para_ronda`**

En `juego/rastreo.py`, junto a `NIVELES`, definir `NIVEL_ORDEN = ("facil", "normal", "dificil", "experto")` y la función con la firma anterior. Normalizar `base` desconocida a índice 0; usar `max(0, ronda - 1)` para que la ronda 1 no desplace el nivel base; limitar el índice con `min(len(NIVEL_ORDEN) - 1, ...)`. No duplicar la tabla `NIVELES`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_rastreo.py`
Expected: `OK - Rastreo de hamsters correcto`.

- [ ] **Step 5: Checkpoint**

No ejecutar git add/commit. Pasar a Task 2.

### Task 2: El árbitro aplica la escalera por ronda

**Files:**
- Modify: `arbitro/rastreo.py:130-160` (bucle de rondas)
- Test: `test_rastreo.py` (tests asíncronos, junto a los existentes)

**Interfaces:**
- Consumes: `nivel_para_ronda(base, ronda)` de Task 1; `ajuste_actual(sala)` ya importado.
- Produces: `dificultad` correcta por ronda en `rastreo_countdown`, `rastreo_show`, `rastreo_write` y `rastreo_result` de la pantalla. Sin nuevos campos.

- [ ] **Step 1: Write the failing tests**

Añadir junto a los tests asíncronos y a `main()`:

```python
async def probar_rastreo_dificultad_sube_por_ronda():
    cliente = Cliente(await websockets.connect(URL))
    await cliente.enviar({"type": "individual", "nombre": "SUBE", "juegos": ["rastreo"]})
    await cliente.esperar("rastreo_show")
    while len(cliente.de_tipo("rastreo_result")) < RONDAS_RASTREO:
        await asyncio.sleep(0.01)
    assert [m["dificultad"] for m in cliente.de_tipo("rastreo_countdown")] == [
        "facil", "normal", "dificil", "experto", "experto", "experto",
    ]
    por_ronda = {}
    for m in cliente.de_tipo("rastreo_move"):
        por_ronda.setdefault(m["ronda"], []).append(m)
    assert [len(por_ronda[r]) for r in range(1, RONDAS_RASTREO + 1)] == [
        NIVELES[n]["entradas"] for n in
        ("facil", "normal", "dificil", "experto", "experto", "experto")
    ]
    await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)

async def probar_rastreo_fiesta_escalera_desde_base():
    host = Cliente(await websockets.connect(URL))
    await host.enviar({"type": "fiesta", "nombre": "Pantalla"})
    codigo = (await host.esperar("room_created"))["codigo"]
    mando = Cliente(await websockets.connect(URL))
    await mando.enviar({"type": "join", "nombre": "Ana", "codigo": codigo})
    await mando.esperar("room_joined")
    await host.enviar({
        "type": "start", "juegos": ["rastreo"],
        "ajustes": {"rastreo": {"rondas": 4, "dificultad": "normal"}},
    })
    while len(host.de_tipo("rastreo_result")) < 4:
        await asyncio.sleep(0.01)
    assert [m["dificultad"] for m in host.de_tipo("rastreo_countdown")] == [
        "normal", "dificil", "experto", "experto",
    ]
    for mensaje in mando.recibidos:
        if mensaje["type"].startswith("rastreo_"):
            assert "tablero" not in mensaje and "final" not in mensaje
            assert "salida" not in mensaje and "reaparecio" not in mensaje
            assert "h1" not in mensaje and "h2" not in mensaje
    for cliente in (host, mando):
        await cliente.cerrar()
    while servidor.salas:
        await asyncio.sleep(0.01)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python test_rastreo.py`
Expected: FAIL en `probar_rastreo_dificultad_sube_por_ronda`, primera aserción: todas las rondas son `facil`.

- [ ] **Step 3: Implement the change**

En `arbitro/rastreo.py`: importar `nivel_para_ronda` de `juego.rastreo`; calcular `dificultad_base = ajuste_actual(sala).get("dificultad", "facil")` una vez antes de `for ronda in ...`; dentro del bucle, antes de `GameManager.generar`, hacer `dificultad = nivel_para_ronda(dificultad_base, ronda)`. Dejar intactos los diccionarios de los cuatro mensajes: ya contienen `"dificultad": dificultad`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python test_rastreo.py`
Expected: `OK - Rastreo de hamsters correcto`.

- [ ] **Step 5: Checkpoint**

No ejecutar git add/commit. Pasar a Task 3.

### Task 3: Hacer visible el nivel en el cliente

**Files:**
- Modify: `static/app.js:1199-1205` (case `rastreo_countdown`) y `static/app.js:1994-1997` (`mostrarRastreo`)
- Test: `test_rastreo.py` (test de contrato de cliente)

**Interfaces:**
- Consumes: `msg.dificultad`, ya presente en `rastreo_countdown` y `rastreo_show`.
- Produces: etiqueta del nivel en la cuenta previa y en las fases de la pantalla. Sin mensajes nuevos.

- [ ] **Step 1: Write the failing test**

```python
def probar_rastreo_cliente_muestra_nivel():
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    inicio = js.index('case "rastreo_countdown"')
    bloque = js[inicio:js.index("break;", inicio)]
    assert "msg.dificultad" in bloque
    inicio = js.index("function mostrarRastreo(msg, fase)")
    bloque = js[inicio:js.index("function configurarSeleccionRastreo", inicio)]
    assert "msg.dificultad" in bloque
    assert "FASES_RASTREO[fase]" in bloque
```

Añadir el test a `main()`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_rastreo.py`
Expected: FAIL en la primera aserción de `probar_rastreo_cliente_muestra_nivel`.

- [ ] **Step 3: Implement the change**

En el case `rastreo_countdown`, construir el `kicker` con la etiqueta en mayúsculas, p. ej. `` `FASE 01 · PREPARA LA VISTA · ${String(msg.dificultad || "facil").toUpperCase()}` ``. En `mostrarRastreo`, calcular `const nivel = msg.dificultad ? \` · ${String(msg.dificultad).toUpperCase()}\` : "";` y concatenarlo a `FASES_RASTREO[fase] || FASES_RASTREO.movimiento`: algunos mensajes (`rastreo_hide`, mensajes de mando) no traen `dificultad` y no deben dejar un separador colgando. No añadir recursos ni cambiar `mostrarEspera`.

- [ ] **Step 4: Run tests to verify it passes**

Run: `python test_rastreo.py`
Expected: `OK - Rastreo de hamsters correcto`.

- [ ] **Step 5: Checkpoint y verificación visual**

Run: `node --check static/app.js`
Expected: sin salida de error.
No ejecutar git add/commit. Pasar a Task 4.

### Task 4: Documentación y verificación final

**Files:**
- Modify: `README.md` (§ RASTREO DE HÁMSTERS, líneas 221–230)
- Modify: `docs/superpowers/specs/2026-11-20-hamsters-rastreo-design.md` (§ 5)
- Modify: `docs/superpowers/plans/2026-11-20-hamsters-rastreo.md` (línea 21 y lista de enmiendas)

**Interfaces:**
- Consumes: comportamiento de Tasks 1–3.
- Produces: documentación coherente con INDIVIDUAL hasta experto.

- [ ] **Step 1: Update documentation**

En README, sustituir «este último solo en FIESTA» por la escalera: en INDIVIDUAL las 6 rondas van `fácil → normal → difícil → experto` (y se mantiene experto); en FIESTA el nivel elegido es el punto de partida. Añadir que la etiqueta del nivel se muestra en pantalla. En la spec § 5 y en el plan (línea 21 y la lista de enmiendas), retirar la restricción y registrar la enmienda con el nombre del test `probar_rastreo_dificultad_sube_por_ronda`.

- [ ] **Step 2: Run the full verification**

Run:

```bash
python test_rastreo.py
for t in test_reconocedor.py test_partida.py test_cajas.py test_operaciones.py test_salas.py test_individual.py test_silabas.py test_minijuegos.py test_ppt.py test_revision.py test_fiesta_progreso.py test_rastreo.py; do python "$t" || exit 1; done
node --check static/app.js
git diff --check
```

Expected: 12 suites en verde, `node --check` sin errores y `git diff --check` sin avisos de whitespace (los avisos de LF→CRLF son informativos).

- [ ] **Step 3: Report and ask before committing**

Informar del diff y de los resultados. No ejecutar git add/commit/push sin autorización explícita.
