# PIEDRA · PAPEL · TIJERA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir PIEDRA · PAPEL · TIJERA como 12ª prueba de Konitive, donde el jugador ve la mano del rival y una consigna GANAR/PERDER y debe tocar la mano propia que la cumple.

**Architecture:** El generador crea `rival`, `objetivo` y `esperado`; el árbitro reutiliza `bucle_minijuego` y su validación de una respuesta por ronda; el cliente muestra la consigna en pantalla y deja tres botones en el mando. No se crea un nuevo modo ni se modifica `servidor.py`, porque `ppt_answer` se registra automáticamente al ampliar `JUEGOS_MINI`.

**Tech Stack:** Python 3.13/3.14, FastAPI + WebSockets, pytest, JavaScript/CSS sin frameworks.

**Spec:** `docs/superpowers/specs/2026-11-19-piedra-papel-tijera-design.md`

## Global Constraints

- Id interno: `ppt`. Nombre visible: `PIEDRA · PAPEL · TIJERA`.
- `MANOS = ("piedra", "papel", "tijera")`; la respuesta siempre es una de esas tres manos, en minúsculas.
- `GANAR` cuando `ronda % 3 == 1`; `PERDER` en las demás rondas.
- 10 rondas por defecto; 4,0 s de respuesta; 3 s de cuenta previa compartida; sin exposición ni `_hide`.
- Brain Age = `tiempo + 5 s por error` (menor es mejor), con el mismo cálculo de puntos que los minijuegos.
- En FIESTA la pantalla ve `rival` y `objetivo`; los mandos reciben `{"mira": True}` y nunca `esperado`.
- Hasta 8 mandos; un mando desconectado no cancela la partida.
- Toda la interfaz en español; sin emoji, esquinas rectas y sombras duras; rojo para `PERDER`, verde para `GANAR`.
- Mensajes: `ppt_countdown`, `ppt_show`, `ppt_write`, `ppt_answer`, `ppt_feedback`, `ppt_result`, `ppt_over`.

## Review Focus

- El jugador toca la misma mano que el rival (empate): no debe contar como acierto — pinned en Task 3, `test_ppt_ignora_respuestas_invalidas_y_empate`.
- Respuesta en mayúsculas, mano inventada o tipo inesperado: se ignora sin cerrar la ronda — pinned en Task 3, `test_ppt_ignora_respuestas_invalidas_y_empate`.
- Ronda vieja o segundo envío del mismo jugador: se ignora — pinned en Task 3, `test_ppt_ignora_respuestas_invalidas_y_empate`.
- En FIESTA, `esperado` no aparece en `ppt_show`, `ppt_write` ni `ppt_result` de los mandos — pinned en Task 5, `test_ppt_fiesta_no_filtra_la_respuesta`.
- Tanda corta de 3 rondas en FIESTA: aparecen ambas consignas y la pantalla no entra al podio — pinned en Task 5, `test_ppt_fiesta_no_filtra_la_respuesta`.

---

### Task 1: Generador y tabla de manos

**Files:**
- Modify: `juego/minijuegos.py`
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: nada.
- Produces: `MANOS = ("piedra", "papel", "tijera")`, `GANAR_CONTRA`, `PERDER_CONTRA` (dicts mano → mano), `mana_para(rival: str, objetivo: str) -> str`, `generar_ppt(ronda: int) -> dict` con claves `rival`, `objetivo`, `esperado`, `dificultad`, `ronda`; `"ppt"` al final de `JUEGOS_MINI`, `NOMBRES_MINI["ppt"] == "PIEDRA · PAPEL · TIJERA"`, `RONDAS_MINI["ppt"] == 10`, y despacho de `generar(ronda, "ppt")`.

- [ ] **Step 1: Write the failing tests**

Crear `test_ppt.py` con:

```python
from juego.minijuegos import (
    JUEGOS_MINI, NOMBRES_MINI, RONDAS_MINI, generar, generar_ppt, mana_para,
)

def test_manos_ganan_y_pierden_contra_cada_rival():
    assert mana_para("piedra", "ganar") == "papel"
    assert mana_para("papel", "ganar") == "tijera"
    assert mana_para("tijera", "ganar") == "piedra"
    assert mana_para("piedra", "perder") == "tijera"
    assert mana_para("papel", "perder") == "piedra"
    assert mana_para("tijera", "perder") == "papel"

def test_generar_ppt_cumple_la_consigna_y_nunca_empata():
    for ronda in range(1, 31):
        reto = generar_ppt(ronda)
        assert reto["rival"] in ("piedra", "papel", "tijera")
        assert reto["objetivo"] == ("ganar" if ronda % 3 == 1 else "perder")
        assert reto["esperado"] == mana_para(reto["rival"], reto["objetivo"])
        assert reto["esperado"] != reto["rival"]
        assert reto["ronda"] == ronda

def test_generar_ppt_registrado():
    assert JUEGOS_MINI[-1] == "ppt"
    assert NOMBRES_MINI["ppt"] == "PIEDRA · PAPEL · TIJERA"
    assert RONDAS_MINI["ppt"] == 10
    assert generar(5, "ppt")["objetivo"] == generar_ppt(5)["objetivo"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py -v`
Expected: FAIL con `ImportError` de `mana_para` / `generar_ppt`.

- [ ] **Step 3: Implement the generator in `juego/minijuegos.py`**

Definir `MANOS` y las dos tablas inversas (`GANAR_CONTRA` y `PERDER_CONTRA`); `mana_para` devuelve `GANAR_CONTRA[rival]` o `PERDER_CONTRA[rival]` según el objetivo. `generar_ppt` elige `rival` con `random.choice(MANOS)`, calcula `objetivo` con `ronda % 3`, usa `mana_para` para `esperado`, y pone `dificultad` con los mismos umbrales que los otros generadores (`FÁCIL` ≤ 3, `MEDIA` ≤ 7, `DIFÍCIL` después). Añadir `"ppt"` al final de `JUEGOS_MINI`, las entradas en `NOMBRES_MINI` y `RONDAS_MINI`, y la rama `if juego == "ppt": return generar_ppt(ronda)` en `generar`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_ppt.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add juego/minijuegos.py test_ppt.py
git commit -m "feat: generador de piedra papel tijera con consigna invertida"
```

---

### Task 2: Registro en núcleo y secretos del árbitro

**Files:**
- Modify: `arbitro/nucleo.py:28`
- Modify: `arbitro/minijuegos.py`
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: Task 1 (`generar_ppt`, id `ppt`, `MANOS`).
- Produces: `JUEGOS_FIESTA` termina en `"ppt"`; `NOMBRES_JUEGOS["ppt"]`; `TIEMPO_RESPUESTA_MINI["ppt"] == 4.0`; `MINIJUEGOS_SOLO_PANTALLA` contiene `"ppt"`; `SECRETOS_MINI["ppt"] == ("esperado",)`; `VISUAL_MINI["ppt"] == ("rival", "objetivo")`; `visual_mini("ppt", reto) -> dict`; `estimulo_para_mando("ppt", reto) == {"mira": True}`; `datos_para_resultado("ppt", reto)` con exactamente `rival`, `objetivo`, `esperado`.

- [ ] **Step 1: Write the failing tests**

Añadir a `test_ppt.py`:

```python
from arbitro.nucleo import JUEGOS_FIESTA, NOMBRES_JUEGOS
from arbitro.minijuegos import (
    MINIJUEGOS_SOLO_PANTALLA, SECRETOS_MINI, TIEMPO_RESPUESTA_MINI,
    VISUAL_MINI, datos_para_resultado, estimulo_para_mando, visual_mini,
)

def test_ppt_registrado_en_nucleo_y_arbitro():
    assert JUEGOS_FIESTA[-1] == "ppt"
    assert NOMBRES_JUEGOS["ppt"] == "PIEDRA · PAPEL · TIJERA"
    assert "ppt" in MINIJUEGOS_SOLO_PANTALLA
    assert SECRETOS_MINI["ppt"] == ("esperado",)
    assert VISUAL_MINI["ppt"] == ("rival", "objetivo")
    assert TIEMPO_RESPUESTA_MINI["ppt"] == 4.0

def test_ppt_no_filtra_la_respuesta_en_el_estimulo():
    reto = generar_ppt(4)
    visual = visual_mini("ppt", reto)
    mando = estimulo_para_mando("ppt", reto)
    assert visual == {"rival": reto["rival"], "objetivo": reto["objetivo"]}
    assert mando == {"mira": True}
    for secreto in SECRETOS_MINI["ppt"]:
        assert secreto not in visual
        assert secreto not in mando

def test_ppt_revela_respuesta_solo_en_el_resultado():
    reto = generar_ppt(5)
    datos = datos_para_resultado("ppt", reto)
    assert set(datos) == {"rival", "objetivo", "esperado"}
    assert datos["esperado"] == reto["esperado"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py -v`
Expected: FAIL en `JUEGOS_FIESTA[-1]` y `KeyError: "ppt"`.

- [ ] **Step 3: Register the game and its secret fields**

En `arbitro/nucleo.py`, añadir `"ppt"` al final de `JUEGOS_FIESTA`. `NOMBRES_JUEGOS` ya incorpora `NOMBRES_MINI` con `**`, así que no necesita cambio. En `arbitro/minijuegos.py`, añadir `ppt` a `MINIJUEGOS_SOLO_PANTALLA`, `VISUAL_MINI`, `SECRETOS_MINI` y `TIEMPO_RESPUESTA_MINI` con los valores exactos del bloque Interfaces, y la clave `"ppt": ("rival", "objetivo", "esperado")` en el mapa de `datos_para_resultado`. No tocar `estimulo_para_mando`: su rama de `MINIJUEGOS_SOLO_PANTALLA` ya devuelve `{"mira": True}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_ppt.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add arbitro/nucleo.py arbitro/minijuegos.py test_ppt.py
git commit -m "feat: registrar ppt en fiesta y proteger su respuesta"
```

---

### Task 3: Validación de respuestas y partida INDIVIDUAL

**Files:**
- Modify: `arbitro/minijuegos.py`
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: Task 1 (`MANOS`, `mana_para`), Task 2 (tablas y registro).
- Produces: `ppt_answer` aceptado por `TIPOS_RESPUESTA_MINI` sin tocar `servidor.py`; mensajes `ppt_feedback`, `ppt_result` y `ppt_over`; `sala.resultados_individual["ppt"]` con `rondas`, `aciertos`, `errores`, `brain_age`, `precision`, `tiempo_promedio`, `tiempo_total`, `puntos`.

- [ ] **Step 1: Write the failing integration tests**

Añadir al inicio de `test_ppt.py` el andamiaje de `test_minijuegos.py:43-96` (uvicorn sobre `servidor.app` en el puerto 8782, `nucleo.pausa` acortada, clase `Cliente` con `enviar`, `de_tipo`, `esperar`, `cerrar`) y las funciones:

```python
async def abrir_individual_ppt() -> Cliente:
    # conecta, envía {"type": "individual", "nombre": "PPT", "juegos": ["ppt"]}
    # y devuelve el Cliente ya abierto
```

```python
async def responder_ronda(cliente: Cliente, mensaje_show: dict, mano: str | None = None) -> None:
    # mano por defecto: mana_para(mensaje_show["rival"], mensaje_show["objetivo"])
    # envía {"type": "ppt_answer", "ronda": mensaje_show["ronda"], "respuesta": mano}
```

```python
def test_ppt_individual_responde_bien_y_resume():
    # 10 rondas: en cada ppt_show responder con responder_ronda(...)
    # esperar individual_summary
    datos = resumen["resumen"]["ppt"]
    assert datos["rondas"] == 10
    assert datos["aciertos"] == 10
    assert datos["errores"] == 0
    assert datos["precision"] == 100.0
    assert datos["brain_age"] >= 0 and datos["puntos"] >= 0
    assert len(cliente.de_tipo("ppt_show")) == 10
```

```python
def test_ppt_ignora_respuestas_invalidas_y_empate():
    # ronda 1: enviar "PIEDRA" (mayúsculas) y después la correcta
    # ronda 2: enviar la misma mano del rival, y después la correcta (se ignora)
    # ronda 3: enviar respuesta con ronda - 1 y después la correcta
    # resto: responder siempre bien; esperar individual_summary
    datos = resumen["resumen"]["ppt"]
    assert datos["aciertos"] == 9
    assert datos["errores"] == 1
    assert datos["precision"] == 90.0
    assert len(cliente.de_tipo("ppt_feedback")) == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py -v`
Expected: FAIL en los `assert` de `aciertos` y `ppt_feedback` (la ronda se cierra sin respuesta válida porque aún no existe la rama `ppt` en la validación).

- [ ] **Step 3: Validate answers and score the round**

En `arbitro/minijuegos.py`, importar `MANOS` de `juego.minijuegos`. En `manejar_respuesta_mini`, añadir una rama `elif juego == "ppt":` junto a `stroop`/`silabas`/`relojes` que devuelva sin hacer nada si `respuesta not in MANOS`, y si no: `acepta = respuesta == reto["esperado"]`, sumar un fallo a `progreso["fallos"]` cuando no acepte, enviar `_feedback_privado(...)` y dejar que el código común cierre la ronda. En `bucle_minijuego`, añadir `elif juego == "ppt": acierto = bool(respuesta) and respuesta[0] == reto["esperado"]` en la cadena que calcula `acierto` por jugador, antes de la rama `else` de `vuelto`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_ppt.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add arbitro/minijuegos.py test_ppt.py
git commit -m "feat: validar respuestas de ppt y puntuar la partida"
```

---

### Task 4: Interfaz del juego en el cliente

**Files:**
- Modify: `static/index.html:93`
- Modify: `static/app.js`
- Modify: `static/estilos.css`
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: Tasks 1–3 (id `ppt`, mensajes `ppt_show`/`ppt_write`/`ppt_answer`/`ppt_result`, campos `rival`, `objetivo`, `esperado`).
- Produces: botón `data-juego="ppt"` en el selector; respuesta enviada como `{type:"ppt_answer", ronda:number, respuesta:"piedra"|"papel"|"tijera"}`; clases CSS `.ppt-consigna`, `.ppt-rival`, `.ppt-ganar`, `.ppt-perder`, `.ppt-botones`, `.ppt-opcion`.

- [ ] **Step 1: Write the failing contract test**

Añadir a `test_ppt.py`:

```python
from pathlib import Path
BASE = Path(__file__).parent

def test_cliente_incluye_ppt_en_selector_y_mensajes():
    html = (BASE / "static/index.html").read_text(encoding="utf-8")
    js = (BASE / "static/app.js").read_text(encoding="utf-8")
    css = (BASE / "static/estilos.css").read_text(encoding="utf-8")
    assert 'data-juego="ppt"' in html
    assert '"ppt"' in js
    assert "ppt_answer" in js
    assert ".ppt-opcion" in css
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py -v`
Expected: FAIL en `test_cliente_incluye_ppt_en_selector_y_mensajes`.

- [ ] **Step 3: Render the game in the client**

En `static/index.html`, añadir tras el botón de SÍLABAS: `<button type="button" class="boton-juego" data-juego="ppt" aria-pressed="false">PIEDRA · PAPEL · TIJERA</button>`. En `static/app.js`: añadir `"ppt"` al final de `JUEGOS_MINI` y `ppt: "PIEDRA · PAPEL · TIJERA"` a `NOMBRES_MINI` (las listas de FIESTA y `JUGAR TODOS` se derivan de ahí); añadir un caso `ppt` en `visualMini` que muestre `RIVAL · <mano>` y la consigna en grande con clase `ppt-ganar` o `ppt-perder`; añadir la rama de `mostrarEstimuloMini` que use ese visual y una pista «Elige la mano que cumpla la consigna contra el rival»; añadir en `prepararRespuestaMini` un panel con tres botones `data-mano` que envíen `ppt_answer` con `msg.ronda` y desactiven las opciones: en INDIVIDUAL el panel muestra `msg.rival` y `msg.objetivo` del `ppt_write`, y en FIESTA muestra `miraPantallaHtml("MIRA LA PANTALLA · ELIGE TU MANO")` porque el mando solo recibe `mira: True`; ampliar `desactivarOpciones` con `juego === "ppt" ? "[data-mano]"`; añadir el caso `ppt` en `respuestaCorrectaHtml` mostrando rival, consigna y mano correcta. En `static/estilos.css`, añadir los estilos de las clases del bloque Interfaces siguiendo `DESIGN.md`: papel claro, borde de 2 px de tinta, sombra dura sin blur, sin redondez, mínimo 44 px de alto táctil, rojo para `PERDER` y verde para `GANAR`; sin emoji.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_ppt.py -v` y `node --check static/app.js`
Expected: PASS (9 tests) y sintaxis JS correcta.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/app.js static/estilos.css test_ppt.py
git commit -m "feat: interfaz de piedra papel tijera con consigna invertida"
```

---

### Task 5: FIESTA sin filtrar secretos

**Files:**
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: none. Verifica el contrato de FIESTA de `ppt_show`, `ppt_write`, `ppt_result` y `podium_update` con dos mandos.

- [ ] **Step 1: Write the failing test**

Añadir a `test_ppt.py`:

```python
def test_ppt_fiesta_no_filtra_la_respuesta():
    # host crea "fiesta"; dos mandos hacen join; host envía start con
    # {"juegos": ["ppt"], "ajustes": {"ppt": {"rondas": 3, "dificultad": "facil"}}}
    # en cada una de las 3 rondas:
    #   show_pantalla = pantalla.esperar("ppt_show", desde=i)
    #   show_mando = mando.esperar("ppt_show", desde=i)
    #   assert {"rival", "objetivo"} <= show_pantalla.keys()
    #   assert "esperado" not in show_pantalla
    #   assert not ({"rival", "objetivo", "esperado"} & show_mando.keys())
    #   write_mando = mando.esperar("ppt_write", desde=i)
    #   assert "esperado" not in write_mando
    #   ambos mandos responden con mana_para(show_pantalla["rival"], show_pantalla["objetivo"])
    #   result_pantalla = pantalla.esperar("ppt_result", desde=i)
    #   result_mando = mando.esperar("ppt_result", desde=i)
    #   assert result_pantalla["reto"]["esperado"] == show_pantalla  # ver nota abajo
    #   assert set(result_mando) <= {"type", "ronda"}
    consignas = {show_pantalla["objetivo"] for show_pantalla en shows}
    assert consignas == {"ganar", "perder"}
    podio = pantalla.esperar("podium_update")
    assert {fila["id"] for fila in podio["despues"]} == {id_mando_1, id_mando_2}
```

Nota: la aserción del resultado debe comparar `result_pantalla["reto"]["esperado"]` con `mana_para(show_pantalla["rival"], show_pantalla["objetivo"])` de esa misma ronda, no con el mensaje completo.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py::test_ppt_fiesta_no_filtra_la_respuesta -v`
Expected: FAIL por timeout esperando mensajes o por `AssertionError` en las claves del mando.

- [ ] **Step 3: Fix any leak the test exposes**

Si el test falla, corregir solo `arbitro/minijuegos.py`: la pantalla debe recibir `rival` y `objetivo` en `ppt_show`/`ppt_write` y `esperado` únicamente dentro de `ppt_result`; los mandos deben recibir `{"mira": True}` en `ppt_show` y solo `type` y `ronda` en `ppt_result`. No añadir campos nuevos ni cambiar `difundir_roles`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_ppt.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add test_ppt.py arbitro/minijuegos.py
git commit -m "test: verificar secretos y consignas de ppt en fiesta"
```

---

### Task 6: Documentación y verificación final

**Files:**
- Modify: `README.md`
- Modify: `PRODUCT.md`
- Test: `test_ppt.py`

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: documentación con 12 pruebas y la suite `test_ppt.py` listada.

- [ ] **Step 1: Write the failing test**

Añadir a `test_ppt.py`:

```python
def test_documentacion_incluye_ppt():
    readme = (BASE / "README.md").read_text(encoding="utf-8")
    product = (BASE / "PRODUCT.md").read_text(encoding="utf-8")
    assert "PIEDRA · PAPEL · TIJERA" in readme
    assert "test_ppt.py" in readme
    assert "12 pruebas" in readme
    assert "12 pruebas" in product
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_ppt.py::test_documentacion_incluye_ppt -v`
Expected: FAIL.

- [ ] **Step 3: Update the docs**

En `README.md`: incluir `PIEDRA · PAPEL · TIJERA` en la lista de nombres y en el recuento de pruebas (11 → 12) de la cabecera, INDIVIDUAL y FIESTA; añadir una sección corta con la regla (rival + consigna, `PERDER` 2 de cada 3 rondas, 10 rondas, 4 s, mismo Brain Age) y una línea `python test_ppt.py  # piedra papel tijera: generador, individual y fiesta` en Pruebas. En `PRODUCT.md`: cambiar los recuentos de 11 a 12 y añadir el juego a la lista de minijuegos. No tocar `DESIGN.md`.

- [ ] **Step 4: Run the full verification**

Run: `python -m pytest test_ppt.py -v`, `python -m pytest -q`, `node --check static/app.js`
Expected: PASS en las tres; las suites existentes siguen pasando.

- [ ] **Step 5: Commit**

```bash
git add README.md PRODUCT.md test_ppt.py
git commit -m "docs: documentar piedra papel tijera como prueba 12"
```
