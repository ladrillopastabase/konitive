# Minijuego: Hamsters – Memoria y seguimiento

> Especificación funcional aportada por el usuario. La implementación debe
> reutilizar los hámsters existentes del juego `pajaros` (HÁMSTERS) y la
> identidad visual de papel y tinta de `DESIGN.md`, sin crear una identidad
> gráfica nueva.

Desarrollar un minijuego inspirado en la mecánica de Devilish Mice de Dr. Kawashima, adaptado para utilizar los hamsters del otro juego del proyecto.

## 1. Tablero

- Cuadrícula de 3 filas × 4 columnas.
- 10 gatos y 2 hamsters inicialmente.
- Los hamsters deben utilizar exactamente el mismo modelo, apariencia y diseño de personajes del otro juego.
- Todos los hamsters deben tener el mismo color y apariencia. No deben existir diferencias visuales que permitan distinguirlos entre sí.
- Cada hamster debe tener un identificador interno único para poder realizar su seguimiento.

## 2. Mecánica de desplazamiento

Los gatos ingresan automáticamente al tablero desde cualquiera de sus cuatro lados: izquierda, derecha, arriba o abajo.

Cada entrada provoca el desplazamiento de una fila o columna completa.

**Desplazamiento horizontal:**
- Un gato entra por la izquierda o derecha de una fila.
- Todos los elementos de esa fila se desplazan una casilla en la dirección de entrada.
- El gato ocupa la primera casilla de la fila.
- El elemento que sale por el extremo contrario abandona temporalmente el tablero.

**Desplazamiento vertical:**
- Un gato entra por arriba o abajo de una columna.
- Todos los elementos de esa columna se desplazan una casilla en la dirección de entrada.
- El gato ocupa la primera casilla de la columna.
- El elemento del extremo contrario sale del tablero.

## 3. Salida y reaparición de hamsters

Cuando un hamster es desplazado fuera del tablero:

1. Debe desaparecer temporalmente.
2. Debe seleccionarse aleatoriamente una nueva posición disponible.
3. La posición no puede estar ocupada por otro hamster.
4. El hamster reaparece en la nueva posición.

Cada hamster conserva su identificador interno durante todo el proceso, aunque cambie de posición.

## 4. Fases de juego

**Fase de observación**
- Mostrar el tablero completo con gatos y hamsters.
- Permitir que el jugador observe las posiciones iniciales.
- Iniciar una cuenta regresiva.

**Fase de movimiento**
- Ocultar la identidad de los animales mediante casillas de interrogación.
- Los gatos ingresan automáticamente desde diferentes bordes.
- Cada entrada desplaza una fila o columna.
- Los hamsters pueden salir y reaparecer en otras posiciones.
- Mostrar los movimientos mediante animaciones.
- Ejecutar una secuencia de movimientos durante un tiempo determinado.

**Fase de identificación**
- Detener todos los movimientos.
- Mostrar el tablero con las identidades ocultas.
- Permitir que el jugador seleccione las casillas donde cree que están los hamsters.
- El jugador debe seleccionar exactamente dos casillas.

**Fase de resultados**
- Revelar la ubicación real de los hamsters.
- Indicar cuáles fueron identificados correctamente.
- Mostrar la puntuación y precisión del jugador.
- Permitir iniciar otra partida.

## 5. Dificultad

Implementar cuatro niveles configurables:

- Fácil: movimientos lentos y menor cantidad de desplazamientos.
- Normal: velocidad y cantidad moderada de movimientos.
- Difícil: movimientos rápidos y secuencias más largas.
- Experto: movimientos muy rápidos y secuencias complejas.

La dificultad debe controlar independientemente:
- Tiempo de observación.
- Duración de la fase de movimiento.
- Cantidad de entradas de gatos.
- Intervalo entre entradas.
- Velocidad de las animaciones.

La dificultad **progresa una vez por ronda** a lo largo de `facil → normal →
dificil → experto`, con tope en experto. En INDIVIDUAL el punto de partida es
`facil` y se alcanza experto en la cuarta ronda; en FIESTA lo fija el anfitrión.
La etiqueta del nivel se muestra en pantalla.

## 6. Componentes técnicos

Separar la lógica del juego en los siguientes componentes:

- `GameManager`: controla las fases y el estado de la partida.
- `BoardManager`: administra la cuadrícula y sus posiciones.
- `MovementSystem`: procesa las entradas de gatos y los desplazamientos.
- `HamsterManager`: administra los identificadores y posiciones de los hamsters.
- `CatSpawner`: genera las entradas de gatos y determina sus direcciones y líneas.
- `AnimationController`: sincroniza las animaciones con los movimientos.
- `DifficultyManager`: administra los parámetros de dificultad.
- `SelectionManager`: gestiona la selección de casillas del jugador.
- `ScoreManager`: calcula los resultados.

## 7. Requisitos funcionales

- La cuadrícula debe mantener siempre sus dimensiones de 3 × 4.
- Cada movimiento debe actualizar correctamente todos los elementos de la fila o columna afectada.
- Ningún hamster puede duplicarse ni desaparecer definitivamente.
- Los hamsters deben conservar su identidad interna.
- Las posiciones de reaparición deben estar libres de otros hamsters.
- Los movimientos deben ejecutarse secuencialmente, sin modificar simultáneamente el estado del tablero.
- Las animaciones deben representar fielmente los cambios de posición.
- El sistema debe registrar la posición final de cada hamster para comprobar las respuestas.
- La selección final debe permitir identificar exactamente dos hamsters.

## 8. Integración visual

No crear una identidad gráfica nueva para este minijuego.

Reutilizar el diseño visual, componentes, tipografías, colores, interfaz, botones, fondos y estilo de animaciones de los otros juegos del proyecto.

Los hamsters deben utilizar los mismos modelos y recursos gráficos existentes, manteniendo su apariencia original. La única adaptación necesaria es utilizarlos como personajes del sistema de seguimiento.

El tablero, las animaciones de desplazamiento y las pantallas de este minijuego deben integrarse visualmente con el resto del proyecto.

## 9. Alcance del desarrollo

Implementar únicamente las funcionalidades necesarias para que este minijuego sea completamente jugable:

- Tablero interactivo.
- Generación de gatos.
- Desplazamientos horizontales y verticales.
- Gestión de salida y reaparición de hamsters.
- Fases de observación, movimiento e identificación.
- Selección de posiciones.
- Evaluación de respuestas.
- Sistema de dificultad y puntuación.

No modificar los otros minijuegos ni crear sistemas globales nuevos que ya existan en el proyecto. Reutilizar la arquitectura y componentes compartidos siempre que sea posible.
