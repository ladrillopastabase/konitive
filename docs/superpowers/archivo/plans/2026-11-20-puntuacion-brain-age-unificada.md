# Puntuación Brain Age unificada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** que las 13 pruebas puntúen solo con `tiempo + 5 s por error`, con el mismo desglose y la misma escala 0–1000.

**Architecture:** se extrae la fórmula actual de los minijuegos a un módulo puro `arbitro/puntuacion.py`; los clásicos dejan de usar base/bono/multiplicador y acumulan tiempo y errores por jugador; `minijuegos.py` y `rastreo.py` consumen la misma función sin cambiar su protocolo. La interfaz cambia solo las etiquetas del desglose.

**Tech Stack:** Python 3 + FastAPI/WebSocket, JavaScript sin bundler, Chrome headless para verificar el render.

**Spec:** `docs/superpowers/specs/2026-11-20-puntuacion-brain-age-unificada.md`

## Global Constraints

- Fórmula exacta: `brain_age = tiempo_total + 5.0 * errores_totales`; `puntos = max(0, round(1000 - brain_age * 10))`.
- Sin respuesta dentro del plazo: tiempo límite completo **y un error**, en las 13 pruebas.
- PALABRAS y OPERACIONES: cada carácter rechazado suma 1 error; si se acepta automáticamente tras 3 intentos fallidos, suma 3 errores.
- Los mandos de FIESTA siguen sin recibir secretos, respuestas correctas ni datos ajenos; `podio_update`/`podium_final` siguen siendo solo pantalla.
- Identidad visual papel/tinta con acento rosa `#F7D1D1`; no introducir `--rojo` salvo STROOP; esquinas rectas y sombras duras.
- Español en toda la interfaz. No ejecutar `git add`, `git commit` ni `git push` sin autorización nueva y explícita.

## Review Focus

- **Sin respuesta**: si el jugador nunca confirma, se consume el límite y se suma 1 error → test de HÁMSTERS y CAJAS en Tasks 2 y 3.
- **Intentos de escritura**: 1, 2 y 3 rechazos en la misma letra → 5 s, 10 s y 15 s → test de PALABRAS/OPERACIONES en Tasks 2 y 4.
- **Acumulación entre rondas**: tiempo y errores no se reinician al pasar de ronda en HÁMSTERS/PALABRAS → test en Task 2.
- **Piso de puntos**: un Brain Age muy alto no produce puntos negativos → test puro en Task 1.
- **Privacidad en FIESTA**: el nuevo desglose no filtra respuestas en los mandos → aserción existente reforzada en `test_fiesta_progreso.py`, Task 6.

---

### Task 1: Fórmula compartida

**Files:**
- Create: `arbitro/puntuacion.py`
- Modify: `arbitro/minijuegos.py:28-42,40-42,108-112,618`
- Modify: `arbitro/rastreo.py:257`
- Test: `test_puntuacion_unificada.py` (nuevo), `test_minijuegos.py:434-435`

**Interfaces:**
- Consumes: ninguna.
- Produces: `SEGUNDOS_POR_ERROR: float`, `PUNTOS_BASE: int`, `PUNTOS_POR_SEGUNDO: int`, `brain_age_y_puntos(tiempo_total: float, errores_totales: int) -> tuple[float, int]`, `sumar_historial(historial: list[dict], pid: str, tiempo: float, errores: int) -> tuple[float, int]`. `minijuegos.py` reexporta `brain_age_y_puntos` para no romper importaciones existentes.

- [ ] **Step 1: Write the failing test**

En `test_puntuacion_unificada.py`, importar desde `arbitro.puntuacion` y afirmar:
`brain_age_y_puntos(10.0, 0) == (10.0, 900)`, `(10.0, 2) == (20.0, 800)`, `(0.0, 0) == (0.0, 1000)`, `(200.0, 0)[1] == 0`; y `sumar_historial([{"tiempo": 2.0, "errores": 1, "puntos": 0}], "yo", 3.0, 0) == (10.0, 900)`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_puntuacion_unificada.py`
Expected: FAIL con `ModuleNotFoundError: No module named 'arbitro.puntuacion'`.

- [ ] **Step 3: Implement `arbitro/puntuacion.py`**

Función pura con las constantes de Global Constraints. `sumar_historial` suma los campos `tiempo` y `errores` de las entradas previas del `pid` y delega en `brain_age_y_puntos`. En `minijuegos.py` y `rastreo.py` sustituir la fórmula local por la importada, manteniendo el nombre público.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_puntuacion_unificada.py && python test_minijuegos.py`
Expected: PASS en ambos; `brain_age_y_puntos(10.0, 2) == (20.0, 800)`.

---

### Task 2: HÁMSTERS y PALABRAS

**Files:**
- Modify: `arbitro/clasico.py:121-195,198-317,320-346,448-456`
- Test: `test_partida.py:92-100`, `test_puntuacion_unificada.py`

**Interfaces:**
- Consumes: `brain_age_y_puntos`, `sumar_historial` de Task 1.
- Produces: entradas de `sala.historial[juego]` con claves nuevas `tiempo`, `errores`, `brain_age`; `round_result.desglose` con `tiempo`, `errores`, `brain_age`, `total`.

- [ ] **Step 1: Write the failing test**

Añadir a `test_puntuacion_unificada.py` dos pruebas sobre `ronda_pajaros` y `ronda_escritura` con `Sala`/`Jugador` reales: una cuenta correcta a 2,0 s sin errores debe dar `(2.0, 980)`; una cuenta errónea debe dar error 1 y `(7.0, 930)`; sin respuesta debe usar `TIEMPO_ESPERA_RESPUESTA` y 1 error. Verificar que una segunda ronda correcta acumula el tiempo de la primera.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_puntuacion_unificada.py`
Expected: FAIL porque `ronda_pajaros` todavía devuelve `100 + bono`.

- [ ] **Step 3: Implement el cambio en `clasico.py`**

En `ronda_pajaros`: `tiempo = instante - momento` si hubo confirmación, si no `TIEMPO_ESPERA_RESPUESTA`; `errores = 0` si el conteo es correcto y hubo confirmación, si no 1. En `ronda_escritura`: `tiempo = progreso["fin"] - progreso["inicio"]` si terminó, si no `TIEMPO_ESPERA_ESCRITURA`; `errores = suma de caracteres rechazados + (0 si terminó else 1)`. En ambos usar `sumar_historial(sala.historial[juego], pid, tiempo, errores)` — las entradas se escriben después, así que la primera ronda parte de cero. Guardar `tiempo`/`errores`/`brain_age` en la entrada del historial y en el desglose.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_puntuacion_unificada.py && python test_partida.py && python test_individual.py`
Expected: PASS; actualizar `test_partida.py:96` para comparar `desglose["total"] == brain_age_y_puntos(...)[1]` en vez de `letras + bono`.

---

### Task 3: CAJAS

**Files:**
- Modify: `arbitro/cajas.py:25-30,87-190,209-229`
- Test: `test_cajas.py:118-133,259-264`

**Interfaces:**
- Consumes: `brain_age_y_puntos` de Task 1.
- Produces: `cajas_result` con `tiempo`, `errores`, `brain_age` por jugador; sin `bono` ni `multiplicador`.

- [ ] **Step 1: Write the failing test**

En `test_cajas.py`, reemplazar las aserciones de `(100 + bono) * multiplicador` por: `puntos == brain_age_y_puntos(tiempo_acumulado, errores_acumulados)[1]`, `0 <= brain_age`, y `errores == 1` tras una respuesta equivocada o sin respuesta. Añadir el caso sin respuesta al test de fiesta.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_cajas.py`
Expected: FAIL con `KeyError: 'tiempo'` en el mensaje `cajas_result`.

- [ ] **Step 3: Implement el cambio en `cajas.py`**

Mantener `rachas` solo para la dificultad. Acumular `tiempos[pid]` y `errores[pid]` en el bucle de 10 rondas: tiempo = `respuesta[1] - momento_respuesta` o `TIEMPO_RESPUESTA_CAJAS` si no hay respuesta; error = 1 si la cuenta es errónea o no hubo respuesta. Calcular puntos con la función compartida sobre el acumulado. Eliminar `PUNTOS_BASE_CAJAS`, `BONO_MAXIMO_CAJAS`, `BONO_POR_SEGUNDO_CAJAS` y el campo `bono`/`multiplicador` de los mensajes.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_cajas.py && python test_salas.py`
Expected: PASS; el total sigue siendo la suma de los 10 puntos parciales.

---

### Task 4: OPERACIONES

**Files:**
- Modify: `arbitro/operaciones.py:25-30,130-182,186-200`
- Test: `test_operaciones.py:158-162`

**Interfaces:**
- Consumes: `brain_age_y_puntos` de Task 1.
- Produces: `operacion_result.desglose` con `tiempo`, `errores`, `brain_age`, `total`; sin `digitos` ni `bono`.

- [ ] **Step 1: Write the failing test**

En `test_operaciones.py:160`, cambiar `total == digitos + bono` por `total == brain_age_y_puntos(tiempo, errores)[1]`. Añadir un caso de tres rechazos seguidos en una cifra: `errores == 3` y `brain_age == tiempo + 15.0`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_operaciones.py`
Expected: FAIL con `KeyError: 'tiempo'`.

- [ ] **Step 3: Implement el cambio en `operaciones.py`**

Errores por cifra = número de reconocimientos fallidos (`intentos` cuando `motivo == "automatica"`, `intentos - 1` en caso contrario); si la operación no se completó, sumar 1 error adicional. Tiempo = fin parcial o `TIEMPO_ESPERA_OPERACIONES` si no terminó. Acumular tiempo y errores entre rondas y usar la función compartida. Eliminar constantes y campos de bono.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_operaciones.py`
Expected: PASS.

---

### Task 5: Paneles del cliente

**Files:**
- Create: `static/desgloses.js`, `test_desgloses.py`
- Modify: `static/index.html:210`, `static/app.js:2890-2922,3020-3045,3225-3250,3274-3300,3314-3330`
- Verify with Chrome headless.

**Interfaces:**
- Consumes: campos `tiempo`, `errores`, `brain_age`, `total` de Tasks 2–4.
- Produces: `textoDesglose(dato: {tiempo: number, errores: number, brain_age: number}) -> string`, con el formato exacto `TIEMPO {n} s · ERRORES {n} · BRAIN AGE {n}`. Se expone en `globalThis` para que funcione igual en el navegador y en Node.

- [ ] **Step 1: Write the failing test**

En `test_desgloses.py`, ejecutar el contenido de `static/desgloses.js` con `node -e` (sin DOM: `globalThis.window = globalThis`) y afirmar:
`textoDesglose({tiempo: 2, errores: 1, brain_age: 7}) == "TIEMPO 2 s · ERRORES 1 · BRAIN AGE 7"` y `textoDesglose({}) == "TIEMPO 0 s · ERRORES 0 · BRAIN AGE 0"`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python test_desgloses.py`
Expected: FAIL con `textoDesglose is not defined`.

- [ ] **Step 3: Implement el formateador y cablearlo**

Crear `static/desgloses.js` con esa única función y cargarlo en `index.html` antes de `app.js`. En `mostrarResultadoCajas`, `mostrarResultadoOperaciones`, `mostrarResultadoRonda`, `mostrarResumenPractica` y `mostrarResumenIndividual`, sustituir las cadenas `BASE 100 + RAPIDEZ`, `CIFRAS +… RAPIDEZ +…` y `LETRAS … RAPIDEZ …` por `textoDesglose(propio)` (o el dato equivalente). Los paneles de minijuegos y RASTREO ya muestran Brain Age: no tocarlos.

- [ ] **Step 4: Run test to verify it passes**

Run: `python test_desgloses.py && python test_descripciones_individuales.py && node --check static/app.js && node --check static/desgloses.js`
Expected: PASS en los tests y `node --check` limpio. Comprobar además en Chrome headless a 390×844 y 1440×900 que la pantalla individual sigue sin desbordamiento horizontal.

---

### Task 6: Documentación y barrido final

**Files:**
- Modify: `README.md:110-166`, `PRODUCT.md:29-31`
- Test: todas las suites.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: documentación y protocolo alineados.

- [ ] **Step 1: Update docs**

En `README.md`, sustituir las secciones de bonus/base/multiplicador por la fórmula única y el desglose `tiempo / errores / brain_age`. En `PRODUCT.md`, cambiar «Puntuación de los minijuegos» por «Puntuación de las 13 pruebas».

- [ ] **Step 2: Run the full sweep**

Run: `python test_reconocedor.py`, `test_partida.py`, `test_cajas.py`, `test_operaciones.py`, `test_salas.py`, `test_individual.py`, `test_silabas.py`, `test_minijuegos.py`, `test_ppt.py`, `test_revision.py`, `test_fiesta_progreso.py`, `test_rastreo.py`, `test_feedback_individual.py`, `test_descripciones_individuales.py`, `test_puntuacion_unificada.py`.
Expected: 15/15 OK; reforzar en `test_fiesta_progreso.py` que el desglose nuevo no incluye claves privadas en los mandos.

- [ ] **Step 3: Verify the working tree**

Run: `git diff --check && git status --short`
Expected: sin errores de whitespace; los cambios siguen sin commitear.
