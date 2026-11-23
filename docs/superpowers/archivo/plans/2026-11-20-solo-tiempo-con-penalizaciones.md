# Solo tiempo con penalizaciones Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el número grande de las 13 pruebas sea el tiempo total con penalizaciones (`brain_age`) y que desaparezca por completo la escala 0–1000.

**Architecture:** Se sustituye la fórmula compartida por una sola función que devuelve segundos; cada ronda, informe, podio y marcador viaja con `brain_age` en lugar de `puntos`, y `decidir_ganador` elige el menor. El cliente lee ese mismo campo en todas las tarjetas y etiqueta todo como `BRAIN AGE · MENOR ES MEJOR`. Los récords locales usan claves nuevas para no mezclar segundos con la escala antigua.

**Tech Stack:** Python 3 (asyncio, websockets, uvicorn), JavaScript vanilla, Chrome para render.

**Spec:** `docs/superpowers/specs/2026-11-20-solo-tiempo-con-penalizaciones.md`

## Global Constraints

- `brain_age = tiempo_total + 5.0 × errores_totales`; menor es mejor. Sin otra fórmula.
- Prohibido `git add`, `git commit` y `git push`: el usuario no ha autorizado nuevos commits para este trabajo. Cada tarea termina con verificación y registro en `.superpowers/sdd/2026-11-20-puntuacion-brain-age-unificada/progress.md`, nunca con commit.
- Identidad visual: papel/tinta, acento rosa `#F7D1D1`, esquinas rectas, sombras duras, sin SVG ni emoji nuevos.
- Sin sprite del hámster.
- Las suites se ejecutan con `python <archivo>.py` desde la raíz del repo (no hay pytest).
- Durante las tareas 1–6 solo debe pasar la suite enfocada de esa tarea; el barrido completo es la tarea 7. Se permite un alias temporal `brain_age_y_puntos` hasta la tarea 7 para no romper importaciones de módulos aún no migrados.

## Review Focus

- Empate exacto de Brain Age entre dos jugadores: `decidir_ganador` debe devolver `None`, nunca elegir el primero por orden de dict. → prueba en Tarea 1.
- Ronda sin respuesta: se cobra el plazo completo y 1 error, por lo que el Brain Age sube 5 s; no debe quedar en 0. → prueba en Tarea 3.
- Mandos de FIESTA: no deben recibir `brain_age_juego` ni el Brain Age de otro jugador. → prueba en Tarea 5.
- Récords locales: un Brain Age mayor no bate récord, y una clave antigua de la escala 0–1000 no debe compararse con segundos. → prueba en Tarea 6.
- Payloads finales: ningún mensaje de resultado debe contener la clave `puntos`. → prueba en Tarea 7.

---

### Task 1: Fórmula compartida y contrato de datos

**Files:**
- Modify: `arbitro/puntuacion.py`
- Test: `test_puntuacion_unificada.py`

**Interfaces:**
- Consumes: nada.
- Produces: `SEGUNDOS_POR_ERROR = 5.0`, `brain_age(tiempo_total: float, errores_totales: int) -> float`, `sumar_brain_age(historial: list[dict], pid: str, tiempo: float, errores: int) -> float`. `fallos_escritura` no cambia. `brain_age_y_puntos` queda como alias temporal.

- [ ] **Step 1: Añadir la prueba que falla**

En `test_puntuacion_unificada.py`, importar `brain_age` y `sumar_brain_age` y añadir:

```python
def probar_formula_solo_tiempo():
    assert brain_age(7.0, 3) == 22.0
    assert brain_age(12.0, 0) == 12.0
    assert sumar_brain_age([{"tiempo": 2.0, "errores": 1}], "yo", 3.0, 0) == 12.0
    modulo = sys.modules["arbitro.puntuacion"]
    assert not hasattr(modulo, "PUNTOS_BASE")
    assert not hasattr(modulo, "PUNTOS_POR_SEGUNDO")
```

Además añadir, en la misma tarea, la prueba de empate del Review Focus:

```python
def probar_empate_brain_age_no_tiene_ganador():
    from arbitro.nucleo import decidir_ganador
    assert decidir_ganador({"a": 12.0, "b": 12.0}) is None
    assert decidir_ganador({"a": 12.0, "b": 17.0}) == "a"
```

- [ ] **Step 2: Verificar que falla**

Run: `python -c "import test_puntuacion_unificada as t; t.probar_formula_solo_tiempo(); t.probar_empate_brain_age_no_tiene_ganador()"`
Expected: FAIL, `brain_age` no existe y `decidir_ganador` devuelve `"a"` en el empate.

- [ ] **Step 3: Implementar la fórmula y cambiar el criterio de ganador**

En `arbitro/puntuacion.py`: eliminar `PUNTOS_BASE` y `PUNTOS_POR_SEGUNDO`; definir `brain_age` con `SEGUNDOS_POR_ERROR`; convertir `sumar_historial` en `sumar_brain_age` devolviendo solo el float; dejar `brain_age_y_puntos` como alias temporal que devuelve `(brain_age(t, e), 0)`. Actualizar el docstring del módulo.

En `arbitro/nucleo.py`: `decidir_ganador(valores: dict[str, float]) -> str | None` elige el **mínimo** y sigue devolviendo `None` si hay empate.

- [ ] **Step 4: Verificar que pasa**

Run: `python -c "import test_puntuacion_unificada as t; t.probar_formula_solo_tiempo(); t.probar_empate_brain_age_no_tiene_ganador()"`
Expected: PASS.

- [ ] **Step 5: Registrar el avance**

Añadir una línea al ledger indicando qué contrato cambió y qué prueba lo cubre. No commitear.

### Task 2: Clásicos HÁMSTERS y PALABRAS

**Files:**
- Modify: `arbitro/clasico.py`
- Test: `test_puntuacion_unificada.py`, `test_partida.py`

**Interfaces:**
- Consumes: `brain_age`, `sumar_brain_age` (Tarea 1), `decidir_ganador` por menor.
- Produces: `ronda_pajaros(sala, nivel) -> dict[str, float]`, `ronda_escritura(sala, nivel) -> dict[str, float]`, `resumen_clasico_individual(sala, juego) -> dict`, `enviar_resumen_practica(sala)`. Los mapas devueltos son Brain Age por jugador.

- [ ] **Step 1: Ajustar las pruebas existentes a tiempo**

En `test_puntuacion_unificada.py` cambiar las aserciones de puntos por Brain Age: tres rondas perfectas de 2/4/6 s dan `brain_age == 12.0`, `mejor == 2.0`, y no debe existir la clave `puntos` en el resumen. La prueba de sin respuesta debe seguir dando `correctas == 0`.

- [ ] **Step 2: Verificar que falla**

Run: `python test_puntuacion_unificada.py`
Expected: FAIL en las aserciones de `puntos`/`mejor`.

- [ ] **Step 3: Migrar `clasico.py`**

Sustituir `sumar_historial` por `sumar_brain_age` y `brain_age_y_puntos` por `brain_age`; renombrar los dicts `puntos` a `brain_age_ronda`; `desglose[pid]` lleva `tiempo`, `errores`, `brain_age` y el campo `total` desaparece. `_brain_age_acumulado` devuelve `(tiempo, errores, brain, mejor)` donde `mejor` es el **menor** Brain Age de una ronda (empezando en `inf` y con `0` si no hay historial). `resumen_clasico_individual` y `enviar_resumen_practica` emiten `brain_age` y `mejor`, sin `puntos` ni `total`. El historial guarda `brain_age` en lugar de `puntos`. En FIESTA, `sala.ultimos_brain_age` se calcula con el acumulado. Eliminar `sala.puntos` (solo se inicializaba, nunca se leía).

- [ ] **Step 4: Verificar que pasa**

Run: `python test_puntuacion_unificada.py` y `python test_partida.py`
Expected: ambas PASS.

- [ ] **Step 5: Registrar en el ledger. No commitear.**

### Task 3: Ocho minijuegos y RASTREO DE HÁMSTERS

**Files:**
- Modify: `arbitro/minijuegos.py`, `arbitro/rastreo.py`
- Test: `test_minijuegos.py`, `test_rastreo.py`

**Interfaces:**
- Consumes: `brain_age` (Tarea 1), `nucleo.clasificacion` ordenado por menor.
- Produces: `por_jugador[pid]["brain_age"]`, `resumen["brain_age"]`, `sala.ultimos_brain_age`; mensajes `{juego}_result` y `{juego}_over` sin `puntos`.

- [ ] **Step 1: Ajustar las pruebas**

En `test_minijuegos.py`: la prueba de PPT sin responder debe seguir dando `errores == RONDAS_MINI["ppt"]` y ahora `puntos < brain_age(0, 0)` deja de existir; sustituirla por `assert dato["brain_age"] >= brain_age(dato["tiempo_total"], dato["errores"])`. En el resto de aserciones, `puntos` pasa a `brain_age`. Añadir la comprobación del Review Focus: `assert "puntos" not in resumen`.

- [ ] **Step 2: Verificar que falla**

Run: `python test_minijuegos.py`
Expected: FAIL por las claves antiguas.

- [ ] **Step 3: Migrar los dos módulos**

En `arbitro/minijuegos.py` y `arbitro/rastreo.py`: quitar la importación de `PUNTOS_BASE`; `brain` deja de desempaquetarse en tupla; eliminar el dict `puntos` y usar directamente el Brain Age de cada jugador para `marcador_mini`, `por_jugador`, `resumen`, `clasificacion` y `ultimos_brain_age`. `nucleo.clasificacion` ordena por `brain_age` ascendente. Los mensajes conservan `tiempo_total` y `errores` y pierden `puntos`.

- [ ] **Step 4: Verificar que pasa**

Run: `python test_minijuegos.py` y `python test_rastreo.py`
Expected: ambas PASS, incluida la partida sin respuesta.

- [ ] **Step 5: Registrar en el ledger. No commitear.**

### Task 4: CAJAS y OPERACIONES

**Files:**
- Modify: `arbitro/cajas.py`, `arbitro/operaciones.py`
- Test: `test_cajas.py`, `test_operaciones.py`

**Interfaces:**
- Consumes: `brain_age` (Tarea 1).
- Produces: `marcador_cajas`/`marcador_operaciones` con `brain_age` por jugador; `cajas_over`/`operacion_over` con `brain_age` y sin `puntos`.

- [ ] **Step 1: Ajustar las pruebas**

En `test_cajas.py` y `test_operaciones.py`, cambiar `msg["puntos"] == brain_age_y_puntos(...)[1]` por `msg["brain_age"] == brain_age(...)`; el podio compara Brain Ages y comprueba que el ganador tiene el menor.

- [ ] **Step 2: Verificar que falla**

Run: `python test_cajas.py` y `python test_operaciones.py`
Expected: FAIL por claves ausentes.

- [ ] **Step 3: Migrar los módulos**

Sustituir los dicts `puntos` por `brain_age_ronda` en los marcadores y en el cálculo final; `sala.ultimos_puntos` pasa a `sala.ultimos_brain_age`; los mensajes `cajas_over`/`operacion_over` y `registrar_resultado_individual` llevan `brain_age`, `tiempo_total`, `errores` y ningún `puntos`. La racha de CAJAS sigue sirviendo solo para dificultad.

- [ ] **Step 4: Verificar que pasa**

Run: `python test_cajas.py` y `python test_operaciones.py`
Expected: ambas PASS.

- [ ] **Step 5: Registrar en el ledger. No commitear.**

### Task 5: FIESTA, podio y sesiones

**Files:**
- Modify: `arbitro/nucleo.py`, `arbitro/sesiones.py`, `arbitro/clasico.py` (únicamente el bloque de FIESTA)
- Test: `test_fiesta_progreso.py`, `test_salas.py`

**Interfaces:**
- Consumes: `sala.ultimos_brain_age` de las tareas 2–4.
- Produces: `Sala.fiesta_brain_age`, `Sala.ultimos_brain_age`; mensajes `mi_brain_age`, `podio_update`/`podio_final` con `despues[].brain_age` y `brain_age_juego`.

- [ ] **Step 1: Ajustar las pruebas de privacidad y podio**

En `test_fiesta_progreso.py`: `mis_puntos` pasa a `mi_brain_age`, sus aserciones leen `brain_age`, y el mensaje del mando no debe contener `despues`, `brain_age_juego` ni Brain Age ajeno. En `test_salas.py`, `podio["puntos_juego"]` pasa a `podio["brain_age_juego"]` y el orden es ascendente.

- [ ] **Step 2: Verificar que falla**

Run: `python test_fiesta_progreso.py` y `python test_salas.py`
Expected: FAIL, los mensajes antiguos siguen llegando.

- [ ] **Step 3: Migrar el núcleo**

Renombrar los campos de `Sala` y `CLAVES_SOLO_PANTALLA` a `brain_age_juego`; `clasificacion` devuelve `brain_age` y ordena ascendente; `enviar_puntos_propios` pasa a `enviar_brain_age_propio` con tipo `mi_brain_age`; `emitir_podium` acumula Brain Age y emite `brain_age_juego`. `sesiones.py` suma `brain_age` de los resultados individuales. El podio del celular sigue recibiendo solo su propia fila.

- [ ] **Step 4: Verificar que pasa**

Run: `python test_fiesta_progreso.py`, `python test_salas.py` y `python test_individual.py`
Expected: las tres PASS.

- [ ] **Step 5: Registrar en el ledger. No commitear.**

### Task 6: Cliente: tarjetas, etiquetas y récords

**Files:**
- Modify: `static/app.js`
- Test: `test_desgloses.py`, `test_feedback_individual.py`

**Interfaces:**
- Consumes: mensajes con `brain_age`, `mi_brain_age`, `brain_age_juego` (Tareas 1–5).
- Produces: mismo contrato de mensajes, sin cambios en `textoDesglose`.

- [ ] **Step 1: Añadir pruebas de récord y de ausencia de puntos**

En `test_feedback_individual.py` (o un helper JS del propio test), comprobar con `node -e` sobre `static/app.js`: las cadenas `"PUNTOS TOTALES"`, `"<b>${msg.puntos} PUNTOS</b>"` y `case "mis_puntos"` no aparecen; `konitive_cajas_record_brain_age` sí; la comparación de récord usa `<`. Añadir el caso del Review Focus: un valor guardado de la escala antigua (`980`) no supera un Brain Age nuevo de `22`.

- [ ] **Step 2: Verificar que falla**

Run: `python test_feedback_individual.py`
Expected: FAIL por las cadenas antiguas.

- [ ] **Step 3: Migrar la interfaz**

Sustituir en todas las tarjetas el número grande por `brain_age` (o `tiempo_total` donde ya se usa) y las etiquetas por `BRAIN AGE · MENOR ES MEJOR`. Los marcadores en vivo de CAJAS/OPERACIONES leen `brain_age`. `mi_brain_age` y `brain_age_juego` sustituyen a los campos antiguos. Los récords usan claves nuevas y `nuevoRecord = brainAge < anterior`, con `anterior = Infinity` si no hay valor o si la clave antigua existe. Mantener `textoDesglose` tal cual.

- [ ] **Step 4: Verificar que pasa**

Run: `python test_feedback_individual.py`, `python test_desgloses.py` y `node --check static/app.js`
Expected: todo PASS.

- [ ] **Step 5: Registrar en el ledger. No commitear.**

### Task 7: Retirar la API antigua, documentación y barrido final

**Files:**
- Modify: `arbitro/puntuacion.py`, `README.md`, `PRODUCT.md`
- Test: las 16 suites; spec y ledger

**Interfaces:**
- Consumes: todas las tareas anteriores.
- Produces: contrato final sin rastro de `puntos`, `brain_age_y_puntos` ni inversión 0–1000.

- [ ] **Step 1: Añadir la prueba del Review Focus**

En `test_puntuacion_unificada.py`, recorrer los payloads de los mensajes finales y afirmar que ninguno contiene la clave `puntos` ni `total` derivado de puntos. En `test_desgloses.py`, verificar que el texto sigue siendo `TIEMPO 12 s · ERRORES 2 · BRAIN AGE 22`.

- [ ] **Step 2: Verificar que falla**

Run: `python test_puntuacion_unificada.py`
Expected: FAIL mientras exista el alias o alguna clave antigua.

- [ ] **Step 3: Eliminar el alias y actualizar la documentación**

Borrar `brain_age_y_puntos` de `arbitro/puntuacion.py` y cualquier importación residual. En `README.md` y `PRODUCT.md` sustituir la descripción de la inversión por `tiempo + 5 s por error; menor es mejor`.

- [ ] **Step 4: Barrido completo**

Run: las 16 suites (`test_reconocedor.py`, `test_partida.py`, `test_cajas.py`, `test_operaciones.py`, `test_salas.py`, `test_individual.py`, `test_silabas.py`, `test_minijuegos.py`, `test_ppt.py`, `test_revision.py`, `test_fiesta_progreso.py`, `test_rastreo.py`, `test_feedback_individual.py`, `test_descripciones_individuales.py`, `test_puntuacion_unificada.py`, `test_desgloses.py`), `node --check static/app.js`, `node --check static/desgloses.js` y `git diff --check`.
Expected: 16/16 PASS, sin errores de sintaxis ni de diff.

- [ ] **Step 5: Verificación visual**

Run: `python C:\Users\ferna\AppData\Local\Temp\opencode\verificar-ficha.py` y revisar en Chrome a 1422×844 y 390×844.
Expected: las tarjetas muestran segundos y `MENOR ES MEJOR`; la ficha lateral y EMPEZAR siguen visibles.

- [ ] **Step 6: Cerrar el ledger sin commitear.**

## Self-review

- Spec coverage: fórmula (T1), 13 pruebas (T2–T4), eliminación de puntos y podio (T1, T5), cliente y récords (T6), docs (T7), verificación (T7). Sin huecos.
- Tipos: `brain_age` es `float` de principio a fin; `decidir_ganador` recibe `dict[str, float]`; `mejor` es `float`. Los nombres de mensaje coinciden entre servidor y cliente.
- Variables sin dueño: `sala.puntos` se elimina en T2; `ultimos_puntos`/`fiesta_puntos`/`puntos_juego`/`mis_puntos` se eliminan en T5.
- Diferencia deliberada: `mejor` pasa de «mejor ronda por puntos» a «menor Brain Age de una ronda», coherente con menor-es-mejor.
