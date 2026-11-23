# Konitive · Laboratorio de Atención

Juego de entrenamiento cerebral inspirado en los minijuegos del Dr. Kawashima.
Nombres sencillos: **PÁJAROS**, **PALABRAS**, **CAJAS**, **OPERACIONES**,
**STROOP**, **TRIÁNGULOS**, **RELOJES**, **MENOR A MAYOR**, **MEMORIA**,
**DAR VUELTO**, **SÍLABAS**, **RASTREO DE HÁMSTERS**,
**PIEDRA · PAPEL · TIJERA**, **INDIVIDUAL** y **FIESTA**.

- **ABRIR SALA / UNIRSE**: duelo de dos personas a PÁJAROS y PALABRAS, mejor de
  3 victorias por juego.
- **INDIVIDUAL**: un solo botón para entrenar solo. Elige una, varias o las 13
  pruebas y se juegan unas detrás de otras con un resumen final común.
- **FIESTA**: una pantalla (quien crea la sala) y hasta 8 mandos en celulares,
  con los 13 juegos y un podio que se actualiza entre juegos.

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Los modelos de reconocimiento ya están incluidos, no hay que descargar nada:

- `juego/modelos/emnist_model.onnx` (26 letras, 927 KB) — para **PALABRAS**.
- `juego/modelos/mnist_model.onnx` (10 dígitos) — para **OPERACIONES**.

Para verificarlos:

```bash
python tests/test_reconocedor.py
```

## Jugar en local

```bash
python servidor.py
```

Abre `http://localhost:6767` y elige un modo:

- **ABRIR SALA**: crea una sala para el duelo; abre la misma dirección en otro
  navegador o pestaña y únete con el código de 5 caracteres.
- **INDIVIDUAL**: pulsa **INDIVIDUAL**, marca las pruebas que quieras (o
  **JUGAR TODOS**) y pulsa **EMPEZAR**. Se juega solo, sin sala ni código.
- **FIESTA**: crea la sala pantalla y reparte el QR entre hasta 8 personas.

## Salas, QR y mandos

Al crear una sala, la pantalla de espera muestra:

- el **código de 5 caracteres**;
- un **código QR** con el enlace directo `.../?sala=CODIGO`;
- un botón **COPIAR ENLACE** para compartirlo por cualquier chat;
- la **lista de conectados**, que se actualiza en cuanto alguien entra.

El QR lo dibuja el servidor en `/api/qr` como SVG. Si abres la página desde
`localhost`, el cliente consulta `/api/red` para poner en el QR la IP de la red
local (`http://IP:6767/?sala=CODIGO`) y así el celular pueda escanearlo. Si
abres la página desde un túnel o dominio público, el QR usa ese dominio.

Para unirse, basta con escanear el QR o abrir el enlace: se abre una ficha con el
código ya relleno, se escribe el nombre y se pulsa **UNIRME AL LOBBY**. En una
sala normal caben 2 jugadores; en FIESTA caben 8 mandos además de la pantalla.

> En casa, PC y celular deben estar en la **misma WiFi**. Si no, usa un túnel.

## Jugar desde otra ciudad (Internet)

Necesitas exponer el puerto 6767. Con Cloudflare Tunnel (gratis, sin cuenta):

```bash
cloudflared tunnel --url http://localhost:6767
```

La herramienta muestra una URL pública propia; compártela junto con el código
(o directamente el enlace `/?sala=CODIGO`). El QR se generará apuntando a ese
dominio. Alternativa con ngrok:

```bash
ngrok http 6767
```

> Deja el servidor y el túnel abiertos mientras juegan.

## MODO INDIVIDUAL

En la pantalla inicial, **INDIVIDUAL** sustituye a los antiguos botones de
práctica, cajas y operaciones. Al pulsarlo se abre un selector con las 13
pruebas: los cuatro juegos clásicos y los nueve minijuegos de entrenamiento:

- **JUGAR TODOS** marca las 13 pruebas; **QUITAR TODOS** las desmarca.
- También se puede marcar una sola o cualquier subconjunto. Cada botón se
  ilumina al seleccionarlo y **EMPEZAR** permanece desactivado hasta que haya
  al menos una prueba elegida.
- Las pruebas se juegan **una detrás de otra** en este orden fijo: PÁJAROS →
  PALABRAS → CAJAS → OPERACIONES → STROOP → TRIÁNGULOS → RELOJES → MENOR A
  MAYOR → MEMORIA → DAR VUELTO → SÍLABAS → RASTREO DE HÁMSTERS → PIEDRA ·
  PAPEL · TIJERA (solo las marcadas). Antes de cada una se ve una pantalla
  «JUEGO 2 / 13» con su nombre.
- Al terminar la última aparece un **informe final** con una tarjeta por prueba
  (puntuación y desglose), la suma total de puntuación y botones de **REPETIR**
  (misma selección) y **VOLVER AL INICIO**. Durante la secuencia no aparecen los
  informes intermedios de cada juego.

Cada prueba conserva su mecánica de siempre, pero comparte una única forma de
puntuar:

### PUNTUACIÓN DE LAS 13 PRUEBAS

Todas —clásicos, CAJAS, OPERACIONES, RASTREO y los nueve minijuegos— usan el
**puntuación**: `tiempo total + 5 segundos por error`, en segundos y menor es
mejor; no hay escala invertida ni puntos. El podio ordena de menor a mayor
puntuación, que es el tiempo acumulado con penalizaciones. Si no se responde a
tiempo se cuenta el límite completo y **un error**;
en PALABRAS y OPERACIONES cada carácter rechazado cuenta como un error (tres
rechazos seguidos = aceptación automática = 15 s). El desglose siempre muestra
`TIEMPO / ERRORES / PUNTUACIÓN`; no hay base, bonus de rapidez ni multiplicadores.

### PÁJAROS y PALABRAS

Se juega hasta completar 3 victorias en la prueba de turno: pájaros y escritura
se alternan dentro de ella. No hay rival ni desempate: el marcador es solo el
entrenamiento propio. Pájaros muestra de 5 a 18 aves (los dos primeros niveles
quietos y después saltitos aleatorios); se cuenta con **− / +** o flechas y se
confirma con **Enter**. Escritura muestra la palabra apenas 0,8 segundos y
después se escribe de memoria, letra a letra, en el cuaderno de tinta. Cada
letra rechazada suma 5 segundos a la puntuación.

### CAJAS

Tanda de 10 rondas independiente del mejor-de-3 (no toca su marcador ni su
protocolo). Se muestra una pila de cubos en vista isométrica durante unos
instantes y hay que decir cuántas cajas había, contando también las ocultas
detrás de otras columnas. Cada casilla de la base tiene una columna sólida, así
que ninguna caja flota.

- La cuadrícula es siempre **5×5** como mínimo, en las tres dificultades.
- Dificultad: **fácil** (5–10 cajas, 3 s), **normal** (7–14, 2 s) y **difícil**
  (12–22, 1,5 s). Sube automáticamente cada 3 aciertos seguidos.
- Tras la cuenta atrás se ve la pila y después se oculta con un fundido. Se
  responde con el contador de pájaros: **−** y **+**, flechas arriba/abajo (o
  izquierda/derecha) y **CONFIRMAR CUENTA** (tecla **Enter**).
- La racha sigue subiendo la dificultad cada 3 aciertos, pero ya no multiplica
  el resultado. El resultado vuelve a mostrar la pila **tal como se vio**, sin
  transparencias, junto al desglose `TIEMPO / ERRORES / PUNTUACIÓN`.

### OPERACIONES

Tanda de 10 rondas con la misma mecánica de memoria que PALABRAS, pero con
resultados numéricos. Se muestra una operación apenas un instante y hay que
escribir el resultado **cifra a cifra** en el mismo cuaderno de tinta.

- Operaciones de **suma, resta y multiplicación**, sin resultados negativos.
  El resultado va de **0 a 99**, así que basta con reconocer una cifra cada vez.
- Dificultad creciente: **INICIAL** (rondas 1–3), **INTERMEDIO** (4–6) y
  **AVANZADO** (7–10). Nunca se repite la misma operación en rondas seguidas.
- Cuenta atrás de 3 segundos, operación visible 0,9 segundos y después se
  escribe de memoria. El cliente no recibe el enunciado mientras escribe.
- Cada cifra rechazada suma 5 segundos a la puntuación; tres rechazos seguidos
  bastan para que se acepte sola. El informe de cada ronda muestra
  `TIEMPO / ERRORES / PUNTUACIÓN`.

## LOS NUEVE MINIJUEGOS

Disponibles en INDIVIDUAL y FIESTA. El servidor genera cada estímulo, guarda la
respuesta correcta, cronometra y valida; el celular solo muestra y envía. El
feedback es **verde** al acertar y **rosa** al fallar, tanto en la pantalla como
en el mando.

Igual que el resto de pruebas, se miden con la **puntuación** descrita arriba.
El informe final muestra además la **precisión** y el **tiempo promedio por
ronda**. En el podio de FIESTA gana quien acumula la menor puntuación, y cada
mando ve solo su propio tiempo.

### STROOP

20 rondas. Aparece un color escrito con tinta de otro color; hay que tocar el
**color de la tinta**, no lo que dice la palabra. La palabra se ve solo un
instante —de **1,2 s** en la primera ronda a **0,5 s** en la última— y después
se borra: queda un aviso neutro y hay que responder de memoria en **3 s**.
A partir de la quinta ronda predominan los estímulos incongruentes.

### TRIÁNGULOS

10 rondas. Fila superior de tres números, dos casillas intermedias con `?` y los
operadores entre ellos. Hay que calcular mentalmente el resultado final y
**escribirlo a mano** en el cuaderno de tinta (dos cifras). Nunca aparece un
resultado negativo. Dificultad creciente: números del 1–9 con solo sumas,
después con restas y por fin hasta el 20.

### RELOJES

10 rondas. Dos relojes analógicos: hay que calcular cuánto tiempo pasó del
primero al segundo y escribir **horas y minutos con dos cifras cada uno**
(por ejemplo `0230` = 2 h 30 min). Los minutos van de 15 en 15 al principio y
de 5 en 5 después; las últimas rondas cruzan la hora.

### MENOR A MAYOR

5 rondas. Números no consecutivos repartidos por una cuadrícula sin solaparse.
Hay que tocarlos **en orden ascendente**. La cantidad crece de 5 a 12 números.

### MEMORIA

6 rondas. Se muestra una grilla con los números 1..N en casillas aleatorias
durante unos segundos; después se oculta y hay que **tocar las casillas en
orden (1, 2, 3…)**. Mientras se memoriza, el celular en FIESTA muestra solo
«**¡MIRA LA PANTALLA!**»: la grilla nunca se envía a los mandos. Un error cierra
la ronda como fallida. Grillas de 3×3 a 5×5.

### DAR VUELTO

10 rondas. Un producto con su precio y el billete con el que paga el cliente.
Hay que armar el **vuelto exacto** sumando denominaciones chilenas
(`$10, $50, $100, $500, $1.000, $2.000, $5.000, $10.000, $20.000`), con formato
`$3.750`. El total del vuelto permanece oculto en modo normal: en la pantalla
solo se ve el precio y el pago; el resultado revela el vuelto y la combinación
mínima de billetes y monedas (algoritmo greedy).

### SÍLABAS

10 rondas. Una frase curada y hay que escribir de mano el **número total de
sílabas gramaticales**. El archivo `juego/frases_silabas.json` tiene 63 frases
con su separación silábica validada: al unir las sílabas se reconstruye la frase
ignorando espacios y mayúsculas. Dificultad creciente por longitud de frase y
número de sílabas.

### RASTREO DE HÁMSTERS

6 rondas. Un tablero de **3×4** siempre lleno con diez gatos y dos hámsters
idénticos, en cuatro fases: **observación** (memorizas sus casillas),
**movimiento** (sigues filas y columnas completas que entran por los cuatro
lados, con las identidades ocultas tras `?`), **identificación** (señalas las
dos casillas finales) y **resultados** (aciertos, precisión y puntuación). Cuatro
niveles: **fácil**, **normal**, **difícil** y **experto**. La dificultad sube un
nivel por ronda: en INDIVIDUAL las 6 rondas van fácil → normal → difícil →
experto (y se mantiene experto); en FIESTA el nivel elegido es el punto de
partida. La etiqueta del nivel se muestra en pantalla. Es un juego dedicado con
protocolo propio: la pantalla ve el tablero y el resultado, y los mandos nunca
reciben las posiciones de los hámsters.

### PIEDRA · PAPEL · TIJERA

10 rondas. Se muestran la mano del rival y una consigna: **GANAR** o **PERDER**.
Hay que responder con una mano que gane o que pierda a propósito contra la del
rival; tocar la mano del rival empataría y cuenta como error, así que nunca es
la mano correcta. La consigna **PERDER** aparece 2 de cada 3 rondas, así que hay
que leerla antes de tocar. Se responde en **4 s**, con la misma puntuación de los
demás minijuegos (`tiempo total + 5 segundos por error`).

## FIESTA

Una persona crea la sala y es la **pantalla**; las demás entran desde el QR con
su celular y son **mandos** (hasta 8). El anfitrión elige el juego en el lobby:
los cuatro clásicos y los nueve minijuegos anteriores.

- La pantalla muestra lo que hay que ver o memorizar; los mandos ven solo sus
  propios controles y pistas. La pantalla **no es participante**: aparece como
  «PANTALLA» aparte en la lista, no puntúa y no entra en el podio.
- Los secretos **no se envían a los mandos**: ni las aves, ni la palabra, ni la
  pila de cajas, ni el texto de la operación, ni la grilla de MEMORIA. Tampoco
  viaja nunca la respuesta correcta de ningún minijuego. En los demás minijuegos
  el mando ve el estímulo (o la pantalla, según corresponda) y responde desde su
  celular; la pantalla es solo espectadora mientras responden. En PIEDRA · PAPEL ·
  TIJERA la mano del rival y la consigna se ven solo en la pantalla; el mando
  recibe únicamente el aviso de mirar. En **RASTREO DE HÁMSTERS** la pantalla ve
  el tablero y el resultado; los mandos reciben solo la dirección, la línea y la
  duración de cada entrada, nunca las posiciones de los hámsters.
- Cada mando puntúa por separado. Si un mando se desconecta, la partida sigue y
  solo se actualiza la lista de conectados; si se va la pantalla, la partida se
  cancela.
- Después de cada juego se muestra un **podio animado**: las filas se reordenan
  con una transición y se indica cuántos puestos sube o baja cada jugador y el
  puntuación de ese juego. El podio acumula la puntuación de toda la fiesta.
- Tras el podio se vuelve al selector y el anfitrión elige el siguiente juego.
  **TERMINAR FIESTA** muestra el **podio final** con los campeones.

## Cómo funciona

- **Servidor** (`servidor.py`): FastAPI + WebSockets. Crea salas, reparte roles
  y despacha cada mensaje al árbitro. Admite hasta 200 salas abiertas a la vez.
- **Árbitro** (`arbitro/`): sincroniza las fases, valida las respuestas, lleva
  el marcador y decide el podio, también en FIESTA. `nucleo.py` tiene las salas,
  los jugadores y las esperas; hay un módulo por juego (`clasico.py` para
  PÁJAROS y PALABRAS, `cajas.py`, `operaciones.py`, `minijuegos.py`,
  `rastreo.py`) y `sesiones.py` encadena los juegos de INDIVIDUAL y FIESTA. El
  reconocimiento de trazos corre en un hilo aparte para no frenar al resto de
  jugadores.
- **Reconocedores** (`juego/reconocedor.py`): rasterizan los trazos del navegador
  a 28×28, aplican el preprocesado EMNIST (incluido el *transpose*) y usan el
  modelo de letras o el de dígitos según el juego.
- **Cliente** (`static/`): HTML/CSS/JS sin frameworks, en scripts clásicos que
  comparten el ámbito global. `/api/catalogo.js` trae el catálogo; `nucleo.js`
  tiene el estado, la conexión y las piezas comunes (cuenta previa, lienzo de
  escritura, stepper); `sonido.js` los sonidos; `static/juegos/` un archivo por
  juego, que se registra con `registrarMensajes` o `registrarMini`; y `app.js`
  la portada, el lobby, el podio y el despacho de mensajes. Cuaderno de papel y
  tinta, canvas para dibujar y para la vista isométrica de cajas, hámsters en
  SVG, QR, mandos y podio animado con WAAPI.
- **Generadores** (`juego/palabras.py`, `juego/cajas.py`, `juego/operaciones.py`,
  `juego/minijuegos.py`): palabras, mapas de altura de cajas, operaciones de 0 a
  99 y los estímulos de los ocho minijuegos genéricos; el noveno, RASTREO DE
  HÁMSTERS, genera su tablero y sus movimientos en `juego/rastreo.py`. El corpus
  de sílabas vive en `juego/frases_silabas.json`.

## Reglas de PÁJAROS y PALABRAS

- **Pájaros**: 5 → 18 aves. Los dos primeros niveles van quietos; después
  algunos pájaros dan saltitos cortos y aleatorios, con un desplazamiento
  mínimo (nunca saltan todos). El número se elige con los botones **− / +** o
  con las **flechas arriba/abajo**; no hay campo de texto. Durante la respuesta
  se ve en vivo la cuenta de ambos jugadores y quién ya confirmó. El resultado
  muestra el total en grande; la puntuación suma el tiempo de la ronda y 5 s si
  el conteo es erróneo o no se confirmó a tiempo.
- **Escritura**: cuenta atrás de 3 segundos; después la palabra **aparece apenas
  0,8 segundos** y desaparece. Recién entonces se escribe de memoria. El cliente
  no recibe la palabra ni cuántas letras faltan: solo muestra las letras ya
  confirmadas, sin casillas vacías. Misma palabra para ambos (español sin
  tildes/ñ e inglés), con longitud creciente 3 → 8. Cada letra rechazada suma
  5 segundos a la puntuación; tres rechazos seguidos la aceptan automáticamente.
  Sin respuesta se cuenta el plazo completo y un error. El informe de cada
  ronda muestra el desglose `TIEMPO / ERRORES / PUNTUACIÓN`.
- Empate en una ronda → se juega otra con la dificultad subida un nivel.
- 1–1 en los minijuegos → ronda de desempate de un juego elegido al azar.

## Pruebas

Viven en `tests/`. Todas a la vez, en paralelo (cada una levanta su servidor en
un puerto libre):

```bash
python tests/correr.py           # todas, con resumen y código de salida
python tests/correr.py rastreo   # solo las que contienen "rastreo"
```

O una sola:

```bash
python tests/test_catalogo.py      # catálogo único: bucles, archivos de cliente y <script>
python tests/test_reconocedor.py   # modelos de letras y dígitos
python tests/test_partida.py       # palabras, conteo en vivo, desglose, desempate y práctica
python tests/test_cajas.py         # pilas isométricas, puntuación y mandos en fiesta
python tests/test_operaciones.py   # generación, cifras manuscritas y fiesta sin enunciado
python tests/test_salas.py         # QR, unión por código, roles, aforo y podio
python tests/test_individual.py    # uno/varios/todos, orden, resumen y repetición
python tests/test_silabas.py       # corpus de 63 frases y separación silábica válida
python tests/test_minijuegos.py    # los ocho minijuegos genéricos en individual y fiesta
python tests/test_ppt.py           # piedra papel tijera: generador, individual y fiesta
python tests/test_revision.py      # memoria, vuelto con trampas, envío doble y tope de salas
python tests/test_rastreo.py       # tablero, fases y fiesta de rastreo de hamsters
python tests/test_descripciones_individuales.py  # portada real en Chrome headless
```

`tests/apoyo.py` reúne lo común: el servidor de prueba, el jugador simulado
(`Cliente`) y `cliente_js()`, que junta el JavaScript del cliente en el orden de
`index.html`.

## Añadir un juego

Guía detallada (estructura, reglas y recetas, pensada también para agentes de IA): `AGENTS.md`.

1. Una entrada en `juego/catalogo.py` (id, nombre, descripción y dificultades).
   De ahí salen el selector INDIVIDUAL, la lista de FIESTA y los nombres.
2. Su generador en `juego/` y su bucle en `arbitro/`, registrado en
   `arbitro.sesiones.BUCLES`. Un minijuego genérico solo necesita su generador
   en `juego/minijuegos.py`.
3. Su archivo en `static/juegos/` con su `<script>` en `index.html` (antes de
   `app.js`). Un minijuego llama a `registrarMini(id, {...})`; otro juego, a
   `registrarMensajes({...})` con sus tipos de mensaje.
4. `python tests/test_catalogo.py` dice qué pieza falta.
