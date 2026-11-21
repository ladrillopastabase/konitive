# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Público mixto, confirmado por el usuario:

- Una persona entrenando sola en INDIVIDUAL, en su computador o celular.
- Grupos que juegan juntos en FIESTA: una persona lleva la pantalla (TV) y hasta 8 personas participan con su celular como mando.

No hay un único público asignado; ambos usos son parte del producto.

## Product Purpose

Juego de entrenamiento cerebral inspirado en los minijuegos del Dr. Kawashima. Reúne 13 pruebas de atención, memoria, escritura y cálculo. El éxito es completar las pruebas elegidas y ver el propio progreso: resumen final con el Brain Age de cada prueba en INDIVIDUAL, podio acumulado entre juegos y podio final en FIESTA.

## Positioning

El usuario confirmó que la identidad está en la combinación de tres mecanismos, no en uno solo:

- **FIESTA de pantalla y mandos**: el servidor nunca envía secretos ni respuestas correctas a los celulares; hay que mirar la pantalla para jugar. La pantalla no puntúa.
- **Las 13 pruebas en un solo lugar**: clásicos y minijuegos comparten selección, puntuación y resumen.
- **Escritura a mano reconocida localmente**: modelos incluidos en el repositorio, sin descargas ni servicios externos.

## Operating Context

- Servidor local FastAPI + WebSockets en `http://localhost:6767`. La sala se comparte con un código de 5 caracteres o un QR que apunta a `/?sala=CODIGO`.
- En casa, computador y celular deben estar en la misma WiFi; para jugar a distancia se expone el puerto 6767 con un túnel (Cloudflare Tunnel o ngrok).
- Quien crea la sala es la **pantalla** (TV, espectadora, no puntúa); los celulares son **mandos** (hasta 8, cada uno puntúa por separado).
- INDIVIDUAL no usa sala ni código.

## Capabilities and Constraints

- Modos: duelo **ABRIR SALA / UNIRSE** (PÁJAROS y PALABRAS, mejor de 3 victorias por juego), **INDIVIDUAL** (de 1 a 13 pruebas en orden fijo con informe final) y **FIESTA** (los 13 juegos, podio entre juegos y podio final).
- Juegos clásicos: **PÁJAROS**, **PALABRAS**, **CAJAS** (tanda de 10 rondas) y **OPERACIONES** (tanda de 10 rondas).
- Nueve minijuegos: **STROOP**, **TRIÁNGULOS**, **RELOJES**, **MENOR A MAYOR**, **MEMORIA**, **DAR VUELTO**, **SÍLABAS**, **RASTREO DE HÁMSTERS** y **PIEDRA · PAPEL · TIJERA**.
- Puntuación de las 13 pruebas: Brain Age = `tiempo total + 5 s por error`, en segundos y menor es mejor; cada intento fallido cuenta, y sin respuesta se suma el límite de tiempo y un error. Es el único número de resultados e informes, también en el podio, que ordena de menor a mayor; no hay escala 0–1000, base, bonus ni multiplicadores. El desglose muestra `tiempo / errores / brain_age`.
- En FIESTA la pantalla no entra al podio. No se envían a los mandos las aves, la palabra, la pila de cajas, el enunciado de la operación, la grilla de MEMORIA ni ninguna respuesta correcta. El informe de cada ronda se muestra solo en la pantalla; el mando solo espera la siguiente.
- Si un mando se desconecta, la partida sigue; si se desconecta la pantalla, la partida se cancela.
- Reconocedores EMNIST (26 letras) y MNIST (10 dígitos) incluidos en `juego/modelos/`. No requieren descarga.
- Hasta 200 salas abiertas a la vez.
- Terminología fija del producto: «PÁJAROS» / «HÁMSTERS», «RASTREO DE HÁMSTERS», «PALABRAS», «CAJAS», «OPERACIONES», «DAR VUELTO», «pantalla», «mando», «podio», «Brain Age».

## Brand Commitments

- Nombre: **Konitive · Laboratorio de Atención**.
- Voz íntegramente en español; pesos chilenos y formato `$3.750` en DAR VUELTO; corpus de palabras sin tildes ni ñ.
- Compromiso explícito del usuario: debe ser «bonito, con diseño y componentes reutilizables y escalables». La calidad visual y la reutilización forman parte del producto, no son un extra.
- Identidad ya instalada en el código y el README: cuaderno de laboratorio de papel y tinta con un solo acento rosa (`#F7D1D1`). Tratar como identidad existente a preservar; no reemplazarla sin que se pida un rediseño.

## Evidence on Hand

- `README.md`: fuente de verdad de modos, juegos, reglas, instalación, arquitectura y pruebas.
- `juego/frases_silabas.json`: 63 frases con separación silábica validada.
- `juego/modelos/emnist_model.onnx` (26 letras) y `juego/modelos/mnist_model.onnx` (10 dígitos).
- Doce suites ejecutables: `test_reconocedor.py`, `test_partida.py`, `test_cajas.py`, `test_operaciones.py`, `test_salas.py`, `test_individual.py`, `test_silabas.py`, `test_minijuegos.py`, `test_ppt.py`, `test_revision.py`, `test_fiesta_progreso.py`, `test_rastreo.py`.
- No hay testimonios, clientes, métricas de uso ni evidencia de mercado. No inventarlos.

## Product Principles

- Lo que hay que memorizar vive solo en la pantalla: los mandos reciben controles y pistas, nunca secretos ni respuestas.
- Un mismo conjunto de 13 pruebas sirve para la rutina individual y para la fiesta; la mecánica de cada prueba no cambia entre modos.
- La generación de estímulos y el reconocimiento ocurren en el servidor o localmente, sin servicios externos ni descargas.
- Debe funcionar bien en celulares pequeños y equipos con pocos recursos, y mantenerse en español.
- El cuidado visual y los componentes reutilizables y escalables son requisitos del producto.

## Accessibility & Inclusion

- Compromiso confirmado por el usuario: funcionar bien en celulares pequeños y en hardware modesto.
- No se ha establecido ningún requisito concreto de accesibilidad (lectores de pantalla, contraste normado, navegación por teclado). No inventarlo.
