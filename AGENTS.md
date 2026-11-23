# Guía para agentes: cómo está hecho Konitive

Juego de entrenamiento cerebral para el navegador: un servidor Python (FastAPI y
WebSocket) que arbitra y un cliente JS sin frameworks. Hay 13 pruebas que se
juegan en INDIVIDUAL o en FIESTA (una PC como pantalla y hasta 8 celulares como
mandos). Todo el código, los nombres y los textos están en español.

Antes de tocar nada: `python tests/correr.py` (18 pruebas, unos 15 s). Después
de cambiar algo, otra vez.

## Mapa

| Dónde | Qué |
|---|---|
| `juego/catalogo.py` | **Única lista de juegos**: id, nombre, descripción, dificultades y orden de portada. |
| `juego/*.py` | Generadores puros (sin red): `minijuegos.py` (8 minijuegos), `cajas.py`, `operaciones.py`, `palabras.py`, `rastreo.py`, `reconocedor.py` (letras y cifras a mano, ONNX). |
| `arbitro/nucleo.py` | `Sala`, `Jugador`, esperas (`pausa`, `esperar`), envíos (`difundir`, `difundir_rol`), podio de FIESTA. |
| `arbitro/sesiones.py` | `BUCLES` (id → bucle del juego) y el encadenado de INDIVIDUAL y FIESTA. |
| `arbitro/<juego>.py` | El bucle de cada juego: `clasico.py` (HÁMSTERS y PALABRAS), `cajas.py`, `operaciones.py`, `rastreo.py`, `minijuegos.py` (un bucle genérico para los 8). |
| `arbitro/puntuacion.py` | `puntuacion(tiempo, errores)` = tiempo + 5 s por error, con 2 decimales. Menor es mejor. Es el **único** resultado. |
| `servidor.py` | Rutas HTTP, `/api/catalogo.js` y el despacho de mensajes WebSocket entrantes (`*_answer`, `*_digit`, etc.). |
| `static/index.html` | Pantallas fijas y los `<script>` **en orden**. |
| `static/nucleo.js` | Estado global, conexión, `MENSAJES`/`registrarMensajes`, `LIMPIEZAS`, y piezas comunes: `mostrarCuentaPrevia`, `iniciarCanvasEscritura`, `STEPPER_HTML`/`stepperConteo`, `panelAmplio`, `barraTiempo`, `mostrarEspera`, `resultadoSoloEnPantalla`. |
| `static/desgloses.js` | `numero()` (máximo 2 decimales) y `textoDesglose()`. |
| `static/juegos/*.js` | Un archivo por juego. `minijuegos.js` tiene el flujo común y `registrarMini`. |
| `static/app.js` | Portada, selector, lobby, podio y el `switch` de mensajes de sala. Se carga el último. |
| `static/estilos.css` | Todo el CSS, con secciones por juego. |
| `tests/` | Un script por área, más `apoyo.py` (servidor de prueba y `Cliente`) y `correr.py`. |

## Cómo fluye una ronda

1. El bucle del juego (en `arbitro/`) genera el reto con `juego/` y guarda lo
   secreto en `sala.datos`.
2. Envía mensajes con el prefijo del juego: `<id>_countdown`, `<id>_show`
   (estímulo), `<id>_hide`/`<id>_write` (fase de respuesta), `<id>_feedback`
   (privado, con `pid`), `<id>_result` (informe), `<id>_over` (fin).
3. El cliente responde con `<id>_answer` (o `<id>_digit` si escribe cifras).
   `servidor.py` lo valida y lo pasa al árbitro.
4. El árbitro mide el tiempo, calcula `puntuacion()` y guarda
   `sala.ultimas_puntuaciones`, que FIESTA suma al podio.

El ritmo vive en el servidor: la cuenta previa es 3-2-1 con un paso de 0,8 s
(`nucleo.TIEMPO_PASO_CUENTA`; el total está en `TIEMPO_CUENTA_PREVIA`,
`cajas.TIEMPO_CUENTA_CAJAS` y `minijuegos.TIEMPO_CUENTA_MINI`) y el informe de
cada ronda se muestra 1,5 s (`nucleo.TIEMPO_RESULTADO`).

En el cliente, `manejar()` (en `app.js`) atiende los mensajes de sala, y el
`default` busca en `MENSAJES[msg.type]`, que llenan los archivos de `juegos/`.

## Reglas que no se rompen

- **Secretos:** en FIESTA, los mandos nunca reciben la respuesta correcta ni los
  datos que hay que memorizar. Usa `difundir_rol(sala, "pantalla" | "mando", msg)`
  y las listas `SECRETOS_MINI` y `estimulo_para_mando` en
  `arbitro/minijuegos.py`. En el cliente, `resultadoSoloEnPantalla()` deja al
  mando esperando durante el informe.
- **Puntuación:** solo con `puntuacion()` o `sumar_puntuacion()`, nunca sumando
  a mano. Todo número que se pinte pasa por `numero()`. Las pruebas fallan si el
  servidor manda una puntuación con más de 2 decimales.
- **Entrada no confiable:** valida tipo y rango de todo lo que llega del
  celular. Mira `manejar_respuesta_mini` (comprueba ronda, jugador y que
  responda una sola vez).
- **Globales del cliente:** los scripts son clásicos y comparten el ámbito
  global. Cada nombre de primer nivel (`function`, `const`, `let`) debe ser
  único en todo `static/`. `registrarMensajes` lanza un error si un tipo de
  mensaje se registra dos veces.
- **Limpieza:** si tu juego anima o deja timers propios, añade una función a
  `LIMPIEZAS` (como `juegos/rastreo.js`). Las comunes (`animacion`,
  `cuentaTimer`, `teclaConteo`) ya las limpia `detenerTimers()`.

## Receta: añadir un minijuego (el caso más rápido)

Un minijuego reutiliza el bucle genérico: cuenta previa, estímulo, respuesta,
informe, N rondas. Ejemplo con id `colores`:

1. **Catálogo:** `juego/catalogo.py` → nueva entrada
   `{"id": "colores", "nombre": "COLORES", "descripcion": "... Conita."}`, en
   la posición de portada que quieras.
2. **Generador:** `juego/minijuegos.py` → añádelo a `JUEGOS_MINI` y a
   `RONDAS_MINI`, escribe `generar_colores(ronda) -> dict` y añade el caso en
   `generar()`.
3. **Árbitro:** `arbitro/minijuegos.py` →
   - `TIEMPO_RESPUESTA_MINI["colores"]` (segundos para responder).
   - `SECRETOS_MINI["colores"]` (claves que nunca viajan en el estímulo).
   - `datos_para_resultado`: las claves que se revelan en el informe.
   - Si el dibujo solo va en la PC: añádelo a `MINIJUEGOS_SOLO_PANTALLA` y a
     `VISUAL_MINI`.
   - En `manejar_respuesta_mini`: un `elif juego == "colores":` que valide la
     `respuesta`, decida `acepta`, sume `progreso["fallos"]` si falla y llame a
     `_feedback_privado`.
   - `TIPOS_RESPUESTA_MINI` en `servidor.py` y `BUCLES` en `sesiones.py` se
     generan solos desde `JUEGOS_MINI`.
4. **Cliente:** `static/juegos/colores.js` (copia el más parecido; `stroop.js`
   y `ppt.js` son los más cortos):
   ```js
   registrarMini("colores", {
     visual: (datos) => (datos.algo ? `<div>…</div>` : ""), // dibujo; "" si no hay datos
     estimulo(msg) { return [this.visual(msg), '<p class="pista">…</p>']; },
     respuesta(msg, mando) { /* pinta controles y envía colores_answer */ },
     correcta: (reto) => `<div class="mini-respuesta">…</div>`,
     // feedback(msg) opcional; por defecto el panel destella verde o rojo
   });
   ```
   Para botones de opción única existe `opcionesUnicas("colores", "atributo", msg.ronda)`.
   Para un número, `STEPPER_HTML` + `stepperConteo(enviarFn)`. Para escribir
   cifras a mano, `iniciarCanvasEscritura` (mira `triangulos.js`).
5. **`index.html`:** `<script src="/static/juegos/colores.js"></script>` antes de `app.js`.
6. **CSS:** clases propias en `estilos.css`, en una sección `/* Colores */`.
7. **Pruebas:** `python tests/test_catalogo.py` dice qué pieza falta. Para el
   flujo completo, sigue el patrón de `tests/test_ppt.py` (generador más una
   partida INDIVIDUAL con `Cliente`).

## Receta: añadir un juego con bucle propio

Para cuando el flujo genérico no alcanza (animaciones por fases, como RASTREO, o
una sola respuesta compleja, como CAJAS):

1. Entrada en `juego/catalogo.py` y generador en `juego/<id>.py`.
2. `arbitro/<id>.py` con `async def bucle_<id>(sala)`. Copia la estructura de
   `arbitro/cajas.py`: rondas con `rondas_para`, pausas con `nucleo.pausa`,
   puntuación con `puntuacion()`, `sala.ultimas_puntuaciones` al final, y
   `sala.resultados_individual[id] = ...` para el resumen de INDIVIDUAL.
3. Regístralo en `BUCLES` (`arbitro/sesiones.py`).
4. En `servidor.py`, dentro del despacho de mensajes: `elif tipo == "<id>_answer": ...`.
5. `static/juegos/<id>.js` con sus funciones y un
   `registrarMensajes({ "<id>_countdown": …, "<id>_show": …, … })`, más su `<script>`.

## Pruebas

- `python tests/correr.py [filtro]` las corre en paralelo. Cada prueba es un
  script con `main()`, sin pytest.
- `tests/apoyo.py`: `levantar_servidor()` (puerto libre), `Cliente`
  (`esperar(tipo, desde=n)`, `de_tipo`, `enviar`), `conectar(mensaje)` y
  `cliente_js()` (todo el JS en el orden de `index.html`, para pruebas que
  revisan el código fuente).
- Las pruebas acortan las esperas con `nucleo.pausa = pausa_corta`, y sustituyen
  los reconocedores con falsos (`nucleo.reconocedor`,
  `nucleo.reconocedor_digitos`).
- `test_descripciones_individuales.py` abre la portada real en Chrome headless.
  Si no encuentra Chrome, se salta.

## Trampas conocidas

- Después de cambiar el JS o el servidor, reinicia `python servidor.py` y
  recarga con **Ctrl+F5**. Si no, el navegador sigue usando el JS viejo de su
  caché.
- En Windows, los heredocs de bash con tildes se corrompen al pasar por stdin.
  Escribe los scripts de edición en un archivo.
- `docs/superpowers/archivo/` y `.superpowers/` son notas históricas de
  planificación, no documentación vigente (allí todavía se habla de "Brain
  Age"). Para el estado actual, `README.md` y este archivo.
- La puntuación tiene 2 decimales tanto en el servidor como en `numero()`. Si
  cambias la precisión, cambia los dos y `revisar_decimales` en `tests/apoyo.py`.
