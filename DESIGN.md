---
name: Konitive · Laboratorio de Atención
description: Cuaderno de laboratorio de papel y tinta con un solo acento rojo para entrenamiento cerebral.
colors:
  papel: "#efe9dc"
  papel-claro: "#f9f5ea"
  papel-oscuro: "#ded4c1"
  tinta: "#1c1a17"
  tinta-suave: "#5f594e"
  rojo: "#d33827"
  verde: "#246b58"
  blanco: "#ffffff"
typography:
  display:
    fontFamily: '"Arial Black", "Helvetica Neue", Impact, sans-serif'
    fontSize: "clamp(20px, min(4vw, 5vh), 30px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.02em"
  title:
    fontFamily: '"Arial Black", "Helvetica Neue", Impact, sans-serif'
    fontSize: "clamp(13px, 2.6vw, 18px)"
    fontWeight: 800
  body:
    fontFamily: '"Trebuchet MS", "Segoe UI", system-ui, sans-serif'
    fontSize: "15px"
    lineHeight: 1.55
  label:
    fontFamily: '"Courier New", Courier, monospace'
    fontSize: "10px"
    fontWeight: 700
    letterSpacing: "0.2em"
rounded:
  none: "0px"
spacing:
  v-1: "clamp(6px, 1dvh, 10px)"
  v-2: "clamp(12px, 2dvh, 20px)"
  v-3: "clamp(18px, 3dvh, 30px)"
  v-4: "clamp(26px, 5dvh, 48px)"
components:
  boton-rojo:
    backgroundColor: "{colors.rojo}"
    textColor: "{colors.blanco}"
    rounded: "{rounded.none}"
    padding: "clamp(11px, 1.8vh, 14px) 18px"
  boton-oscuro:
    backgroundColor: "{colors.tinta}"
    textColor: "{colors.papel-claro}"
    rounded: "{rounded.none}"
    padding: "clamp(11px, 1.8vh, 14px) 18px"
  boton-contorno:
    backgroundColor: "transparent"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "clamp(11px, 1.8vh, 14px) 18px"
  boton-juego:
    backgroundColor: "{colors.papel-claro}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "clamp(16px, 2.5vh, 24px) 14px"
  panel:
    backgroundColor: "{colors.papel-claro}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "clamp(14px, 2.6vh, 30px) clamp(16px, 3vw, 34px)"
  ticket:
    backgroundColor: "{colors.papel-claro}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "clamp(14px, 2.6vh, 24px)"
  campo-input:
    backgroundColor: "{colors.blanco}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "clamp(10px, 1.8vh, 13px) 14px"
  barra:
    backgroundColor: "{colors.tinta}"
    textColor: "{colors.papel-claro}"
    rounded: "{rounded.none}"
    padding: "6px 16px"
  progreso-vivo:
    backgroundColor: "{colors.papel-claro}"
    textColor: "{colors.tinta}"
    rounded: "{rounded.none}"
    padding: "6px 10px 8px"
---

# Design System: Konitive · Laboratorio de Atención

## Overview

**Creative North Star: "El Cuaderno de Laboratorio"**

Konitive se lee como una ficha de laboratorio impresa en papel rayado: tinta negra, márgenes estrechos, etiquetas en mayúsculas y un único acento rojo que reserva para lo que manda atender. La voz es precisa, táctil y con un humor seco: no explica de más, no adorna y confía en que el número grande y el sello inclinado digan lo suficiente. Cada pantalla parece una hoja recién sacada del cuaderno, con sus perforaciones, sus rayas y su sello.

El sistema es deliberadamente plano. No hay degradados, desenfoques ni transparencias decorativas: la profundidad se construye apilando papel con sombras duras de desplazamiento y cero desenfoque, y la interacción se siente física porque el botón se hunde y su sombra desaparece al presionarlo. La densidad es alta (11 pruebas, podios, marcadores) pero el ritmo vertical único (`--v-1` a `--v-4`, en `dvh`) mantiene la composición estable entre un teléfono de 320px y una TV de 1080p.

La identidad es patrimonio del código existente: este documento la describe, no la sustituye. Lo que se conserva es el papel, la tinta, el rojo de sello y la ausencia de redondez. Lo que se evita es cualquier superficie que parezca una app genérica de tarjetas flotantes.

**Key Characteristics:**

- Papel rayado de fondo y superficies de ficha, siempre en tonos crema.
- Un solo acento cálido: rojo de sello para acciones, números que mandan y errores.
- Verde reservado a la confirmación: acierto, conectado, listo.
- Sombras duras sin desenfoque; presionar elimina la sombra.
- Esquinas rectas por defecto; círculos solo para sellos, perforaciones y puntos de estado.
- Tres voces tipográficas: display condensada en negrita, cuerpo legible y mono para datos.
- El avance en vivo de la fiesta se proyecta como una ficha apilada sobre la escena: datos ajenos solo en la pantalla del anfitrión.

## Colors

La paleta es papel, tinta y un sello rojo; el verde aparece únicamente cuando algo está bien.

### Primary

- **Rojo de Sello** (#d33827): tinta de estampilla. Vive en el botón principal, la barra inferior de la cabecera, el número del vuelto y del conteo final, el flash de PALABRAS, los sellos inclinados y el borde del primer puesto del podio. Es el color que manda mirar.

### Secondary

- **Verde de Aprobado** (#246b58): la única confirmación. Subraya las letras acertadas, el punto de conexión, el estado «listo» de un mando y las subidas del podio.

### Neutral

- **Papel de Cuaderno** (#efe9dc): fondo del cuerpo, con rayado horizontal de tinta al 5,5% cada 32px.
- **Hoja de Ficha** (#f9f5ea): superficie de paneles, tickets, fichas, marcadores y botones de juego.
- **Papel de Recorte** (#ded4c1): sombras de contorno, franjas de datos, relleno del stepper y fondo de la barra de tiempo.
- **Tinta de Bolígrafo** (#1c1a17): texto, bordes de 2px, sombras duras y la barra superior.
- **Tinta Suave** (#5f594e): etiquetas, pistas y desgloses que acompañan sin competir.
- **Blanco de Lienzo** (#ffffff): fondo de inputs, del área de dibujo y del valor del stepper.

**The One Accent Rule.** El rojo es el único acento cálido y se usa para mandar, no para decorar: si una pantalla tiene varios rojos, ninguno manda. El verde confirma y no compite con él.

**The Ink-and-Paper Rule.** Toda superficie es papel y toda línea es tinta. No se introducen degradados ni transparencias decorativas; el único patrón es el rayado del cuaderno.

## Typography

**Display Font:** Arial Black (con Helvetica Neue, Impact y sans-serif como respaldo)
**Body Font:** Trebuchet MS (con Segoe UI y system-ui como respaldo)
**Label/Mono Font:** Courier New (con Courier y monospace como respaldo)

**Character:** La display grita como un titular de cuaderno: compacta, pesada, con tracking negativo en los titulares grandes. El mono es la voz de la ficha clínica: espaciada, uppercase, para códigos, etiquetas y datos. El cuerpo solo se usa para texto que se lee de verdad.

### Hierarchy

- **Display** (800, `clamp(52px, min(9vw, 12vh), 104px)`, line-height .82): el logotipo de la portada y los números protagonistas; tracking negativo.
- **Headline** (800, `clamp(20px, min(4vw, 5vh), 30px)`, line-height 1): títulos de panel, podio y resultados.
- **Title** (800, `clamp(13px, 2.6vw, 18px)`): nombre del juego en la cabecera de ronda.
- **Body** (400, `clamp(14px, 1.8vh, 16px)`, line-height 1.55): descripciones y pistas; nunca baja de 14px en celular.
- **Label** (700, 10px, letter-spacing .2em, uppercase): kicker, etiquetas de campo, ticket y separadores.

**The Shouted Labels Rule.** Las etiquetas gritan en mayúsculas mono y espaciadas (`.1em`–`.2em`); el texto que hay que leer se escribe en minúsculas y conserva al menos 14px en pantallas de hasta 600px.

## Layout

La página no hace scroll: `body` mide `100dvh` y reparte altura entre la barra superior (~38px) y `#app`. `#app` centra el contenido con padding `calc(var(--v-2) + env(safe-area-inset-*, 0px))` horizontal `clamp(14px, 3vw, 32px)`. Cada pantalla tiene su propio ancho máximo: 1060px para juego y lobby con selector, 760px para el selector individual, 620px para el podio, 560px para el lobby simple.

El ritmo vertical es una sola escala de cuatro pasos, definida dos veces para `vh` y `dvh` y con la segunda como definitiva: `--v-1` 6–10px, `--v-2` 12–20px, `--v-3` 18–30px, `--v-4` 26–48px. En pantallas de hasta 560px de alto se reduce a 4/8/14/22px para que el escenario siga cabiendo.

El lobby con selector pasa a dos columnas desde 900px de ancho: acceso a la izquierda (260–340px) y juegos/podio a la derecha, cada columna con scroll propio. El panel de juego usa el mismo corte desde 900px y 520px de alto: visual a la izquierda, título y controles a la derecha en una columna de 260–320px; los tamaños del visual se miden en `cqi`/`cqh` dentro de su contenedor.

En celular el selector individual pasa de 4 a 3 columnas por debajo de 560px, la cabecera de partida se apila con la ronda arriba, y las pantallas de inicio e individual scrollean dentro de sí mismas para que ningún botón quede fuera de alcance. `#contenido` y los paneles usan `justify-content: safe center`: centran si cabe y alinean arriba si no.

## Elevation & Depth

El sistema es plano por defecto y construye profundidad exclusivamente con sombras duras de desplazamiento, sin `blur`, como hojas recortadas apiladas. No hay sombras ambientales ni luz difusa: una sombra es la huella de una capa de papel.

### Shadow Vocabulary

- **Sombra de ficha** (`box-shadow: 6px 6px 0 var(--tinta)`): paneles, fichas de inscripción, ticket y contenedores principales.
- **Sombra de botón rojo** (`4px 4px 0 var(--tinta)`): acción principal.
- **Sombra de botón oscuro** (`4px 4px 0 var(--rojo)`): acción secundaria sobre papel.
- **Sombra de contorno** (`4px 4px 0 var(--papel-oscuro)`): acción terciaria y tiles de juego.
- **Sombra de foco** (`3px 3px 0 var(--rojo)`): input enfocado.
- **Sombra de sello** (`4px 4px 0 var(--rojo)`): retrato, QR y avisos.
- **Sombra de resultado** (`5px 5px 0 var(--rojo)`): el conteo final.

**The Cut-Paper Rule.** Toda sombra es un desplazamiento duro sin desenfoque. Si un elemento no tiene sombra, está en reposo, desactivado o siendo presionado; nunca se inventa una sombra suave para dar profundidad.

## Shapes

Las esquinas son rectas (`border-radius: 0`) en botones, inputs, paneles, tickets, fichas y tableros. El borde normativo es de 2px de tinta; los separadores usan `3px double` y la cabecera de ronda lleva 3px de rojo a cada lado. Las únicas formas redondas son funcionales: las perforaciones del ticket (círculos de 16px), el punto de conexión (8px), el sello grande del diploma (84px doble borde) y el único heredado `border-radius: 12px` del cartel de pago de DAR VUELTO. Los sellos se rotan entre -4° y -9° para parecer estampados a mano.

## Components

### Buttons

- **Shape:** esquinas rectas (0px), borde de 2px de tinta, ancho completo salvo la variante `chico`.
- **Primary:** rojo de sello sobre blanco con sombra `4px 4px 0` de tinta; padding `clamp(11px, 1.8vh, 14px) 18px`; display uppercase 13px.
- **Dark:** tinta sobre papel claro con sombra roja. **Outline:** transparente sobre papel, sombra de papel oscuro, y al hover el fondo pasa a papel oscuro.
- **Hover / Focus:** el hover levanta 1px y aumenta la sombra a 5px; el foco visible marca `outline: 3px solid var(--rojo)` con `outline-offset: 2px`.
- **Pressed:** `translate(3px, 3px)` y `box-shadow: none`. Es el gesto táctil canónico.

### Chips y fichas

- **Ficha de jugador:** papel claro, borde de tinta, padding `10px 14px`, número y rol en mono; el rol va en rojo. Vacía es borde discontinuo y sin fondo.
- **Ficha de pantalla:** borde discontinuo, fondo transparente, texto de tinta suave: la pantalla está presente pero no puntúa.
- **Sellos:** borde de 3px en rojo o verde, texto display en minúsculas rotado, para «GANADOR», rachas o resultados.

### Cards / Containers

- **Corner Style:** recto (0px).
- **Background:** hoja de ficha sobre papel de cuaderno.
- **Shadow Strategy:** sombra de ficha (`6px 6px 0 var(--tinta)`), salvo el panel de espectadora, que prescinde de controles.
- **Border:** 2px de tinta; el ticket añade dos círculos laterales recortados.
- **Internal Padding:** `clamp(14px, 2.6vh, 30px) clamp(16px, 3vw, 34px)` para paneles, `clamp(14px, 2.6vh, 24px)` para tickets.

### Inputs / Fields

- **Style:** fondo blanco, borde de 2px de tinta, radio 0, 16px mínimo para evitar zoom en iOS.
- **Focus:** `box-shadow: 3px 3px 0 var(--rojo)` y `outline: none`.
- **Placeholder:** tinta suave; el error va en rojo debajo del campo.

### Navigation

- **Barra superior:** fondo de tinta, texto de papel claro en mono de 11px con tracking `.13em`, borde inferior de 3px rojo, sello «K» rojo de 24px a la izquierda. El subtexto se oculta por debajo de 780px. Los botones SALIR y SONIDO van en contorno de 1px.

### Stepper de conteo

- Botones laterales de papel oscuro con display de 28–40px, valor central blanco de 32–52px, todos con 2px de borde y mínimo 58px de alto.
- Hover del botón: fondo rojo y texto blanco; deshabilitado al 40% de opacidad.
- Aparece solo en los mandos: la pantalla de la fiesta es espectadora y no cuenta.

### Fila de podio

- Papel claro, borde de 2px, sombra `3px 3px 0` de papel oscuro; el primer puesto sube a borde y sombra rojos de 3px y 4px.
- Puesto en display de 24px, nombre en negrita, puntos en display de 22px, movimiento en mono verde si sube y rojo si baja.

## Do's and Don'ts

### Do:

- **Do** mantener las sombras duras sin desenfoque: `6px 6px 0 var(--tinta)` para fichas y `4px 4px 0` para botones.
- **Do** alimentar el ritmo desde `--v-1` a `--v-4` en `dvh`, con su copia en `vh` como respaldo.
- **Do** dejar que la pantalla del anfitrión en FIESTA proyecte hámsters pero no muestre stepper ni conteos: en HÁMSTERS los mandos cuentan.
- **Do** mantener como mínimo 44px de alto táctil y 14px de texto leído en celular, con `env(safe-area-inset-*)` en los bordes.
- **Do** usar `cqi`/`cqh` para escalar el visual dentro de `.panel-amplio` en pantallas grandes.

### Don't:

- **Don't** introducir blur, degradados, tarjetas flotantes ni esquinas redondeadas en superficies nuevas: el carácter es papel recortado.
- **Don't** añadir emoji ni glifos de producto a DAR VUELTO: la escena muestra nombre, precio y pago como texto.
- **Don't** bajar las etiquetas mono de 12px ni el texto de lectura de 14px por debajo de 600px.
- **Don't** dejar un control fuera del viewport en celular: las pantallas largas scrollean dentro de sí mismas.
- **Don't** usar verde como acento decorativo: está reservado a acierto, conexión y subida.
