# Diseño: PIEDRA · PAPEL · TIJERA (inversión de consigna)

## Intento

Añadir una duelo de piedra, papel o tijera a Konitive donde el reto no es ganar,
sino **obedecer una consigna que a veces pide perder**. El jugador ve la mano del
rival y una consigna (`GANAR` / `PERDER`), y debe tocar la mano propia que cumple
la consigna. Es entrenamiento de flexibilidad: al pedir `PERDER`, la respuesta
correcta es la que en un juego normal sería la perdedora.

Ejemplo de ronda:

```
RIVAL: PAPEL · CONSIGNA: PERDER
PIEDRA   PAPEL   TIJERA
Respuesta correcta: PIEDRA
```

## Objetivos

- Jugarse en INDIVIDUAL y en FIESTA con la misma mecánica, como el resto.
- Que el servidor genere el reto, guarde la respuesta correcta y valide; el
  cliente solo muestra y envía.
- Que en FIESTA la consigna y la mano del rival vivan en la pantalla y los
  mandos reciban solo tres botones, sin la respuesta correcta.
- Conservar la identidad de cuaderno de papel y tinta (sin emoji, esquinas
  rectas, sombras duras, rojo para mandar y verde para confirmar).

## No objetivos

- Empates, serie al mejor de 3 ni marcador propio distinto del de los minijuegos.
- Reconocimiento de gestos ni dibujo: la respuesta son tres botones.
- Cambiar la mecánica de las 11 pruebas existentes.

## Restricciones

- Python + FastAPI/WebSockets, JS sin frameworks, mismo servidor en `:6767`.
- Un generador por juego en `juego/`, un bucle en `arbitro/`, registro en
  `JUEGOS_MINI` / `JUEGOS_FIESTA` y en las listas del cliente.
- Brain Age = `tiempo + 5 s por error` (menor es mejor), igual que los minijuegos.
- Hasta 8 mandos en FIESTA; un mando desconectado no cancela la partida.
- Español en toda la interfaz.

## Enfoques considerados

1. **Duodécimo minijuego integrado (elegido).** Reutiliza `bucle_minijuego`, el
   despacho `TIPOS_RESPUESTA_MINI`, el podio y el informe de INDIVIDUAL. Costo:
   tocar las tablas compartidas del generador y del árbitro.
2. **Modo propio con sala nueva.** Permitiría rondas y reglas propias sin tocar
   las tablas, pero duplicaría sala, bucle, informe y podio para un juego de una
   sola regla.
3. **Juego solo del cliente.** Cero trabajo de servidor, pero la respuesta
   correcta quedaría en el navegador y rompería la regla de que los secretos
   los guarda el servidor.

Se elige el 1: el juego es una variante de regla, no un nuevo modo.

## Diseño

### Identificador y mensajes

- Id interno: `ppt`. Nombre visible: `PIEDRA · PAPEL · TIJERA`.
- Mensajes: `ppt_countdown`, `ppt_show`, `ppt_write`, `ppt_answer`,
  `ppt_feedback`, `ppt_result`, `ppt_over`. Se derivan del id, igual que los
  otros minijuegos; `ppt_answer` se registrará solo al añadir `ppt` a
  `JUEGOS_MINI`.
- `ppt_answer` lleva `{"type", "ronda", "respuesta": "piedra"|"papel"|"tijera"}`.

### Generador (`juego/minijuegos.py`)

`generar_ppt(ronda)` devuelve:

- `rival`: una mano aleatoria de `("piedra", "papel", "tijera")`.
- `objetivo`: `"ganar"` si `ronda % 3 == 1`, si no `"perder"` (2 de cada 3
  rondas piden perder; es el giro del juego y hace que aparezca en cualquier
  tanda de 3).
- `esperado`: mano que cumple la consigna contra `rival`, calculada con la tabla
  `GANAR_CONTRA = {piedra: papel, papel: tijera, tijera: piedra}` y su inversa
  `PERDER_CONTRA`. Nunca es igual a `rival`, así que no hay empate.
- `dificultad`: `FÁCIL` / `MEDIA` / `DIFÍCIL` según la ronda, como los demás.
- Se añade a `JUEGOS_MINI` (al final), `NOMBRES_MINI` y `RONDAS_MINI` con 10
  rondas por defecto.

### Árbitro (`arbitro/minijuegos.py`)

- `ppt` entra en `MINIJUEGOS_SOLO_PANTALLA` y `VISUAL_MINI["ppt"] =
  ("rival", "objetivo")`. La pantalla ve mano y consigna; el mando recibe
  `mira: True` y solo tres botones. `SECRETOS_MINI["ppt"] = ("esperado",)`.
- `estimulo_para_mando` ya devuelve `{"mira": True}` para ese conjunto: no hay
  que tocarlo.
- Tiempo de respuesta: 4 s por ronda (3 s de cuenta previa compartida). Sin
  exposición ni `_hide`: el estímulo permanece visible mientras se responde.
- Validación: solo se acepta una respuesta por ronda y jugador, con la ronda
  vigente, que sea una de las tres manos; `acepta = respuesta == reto["esperado"]`.
- Cálculo de acierto por ronda y Brain Age: se reutilizan `brain_age_y_puntos`
  y el esqueleto de `bucle_minijuego` sin crear un bucle nuevo.
- `datos_para_resultado["ppt"] = ("rival", "objetivo", "esperado")` para que la
  pantalla Revele la mano correcta; al mando solo le llega `ppt_result` con la
  ronda, como al resto.

### Cliente (`static/`)

- Listas `JUEGOS_MINI`, `NOMBRES_MINI` y botón `data-juego="ppt"` en el selector
  de INDIVIDUAL; `JUGAR TODOS` lo incluye automáticamente.
- `visualMini("ppt", ...)`: ficha con `RIVAL: <mano>` y la consigna en grande,
  con rojo para `PERDER` y verde para `GANAR` (el rojo manda mirar; el verde
  confirma la consigna de ganar).
- Respuesta: tres botones con `data-mano`, reutilizando el patrón de
  `stroop-botones` pero con clase `ppt-opcion` y estilos propios en
  `estilos.css` (papel claro, borde de tinta, sombra dura, sin redondez). En
  FIESTA el mando ve además «MIRA LA PANTALLA».
- `respuestaCorrectaHtml("ppt", reto)` muestra `RIVAL / CONSIGNA / MANO
  CORRECTA` en el informe de la pantalla.
- El `ppt_show` de la pantalla y el `ppt_write` del mando siguen el patrón de
  `difundir_roles` ya existente.

### Pruebas

Nueva suite `test_ppt.py` (una por juego, como el resto):

- Unitarias del generador: las 3 manos posibles, `objetivo` según `ronda % 3`,
  y `esperado` correcto para las 6 combinaciones rival/objetivo.
- INDIVIDUAL: se juega una tanda respondiendo siempre la mano correcta y se
  comprueba el resumen (`aciertos`, `brain_age`, `puntos`).
- FIESTA con dos mandos: la pantalla recibe `rival`/`objetivo`, los mandos no
  reciben `esperado` en `ppt_show`/`ppt_write` y el informe con la respuesta
  correcta solo llega a la pantalla.
- Validación: respuesta con ronda vieja, mano inventada y segundo envío de un
  mismo jugador se ignoran.
- Se añade la suite a la lista de `README.md` y se actualizan los recuentos
  de 11 a 12 pruebas en README y PRODUCT.md.

### Archivos a tocar

- Crear: `test_ppt.py`, este documento.
- Modificar: `juego/minijuegos.py`, `arbitro/nucleo.py`,
  `arbitro/minijuegos.py`, `static/index.html`, `static/app.js`,
  `static/estilos.css`, `README.md`, `PRODUCT.md`.
- Sin cambios: `servidor.py` (el registro de `ppt_answer` es automático).

## Lo que queda al constructor

Elecciones menores ya resueltas aquí: id `ppt`, 10 rondas, 4 s de respuesta,
consigna `GANAR` en 1 de cada 3 rondas. El color exacto del botón y el texto de
la pista se ajustan a la guía `DESIGN.md` sin necesitar nueva decisión.
