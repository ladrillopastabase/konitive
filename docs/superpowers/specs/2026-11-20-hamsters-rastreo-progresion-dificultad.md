# Progresión de dificultad en RASTREO DE HÁMSTERS — diseño

## Problema

El nivel se calcula una sola vez por partida y se reutiliza en todas las
rondas. En INDIVIDUAL `ajuste_actual()` devuelve `{}` y siempre cae en `facil`.
En FIESTA el anfitrión elige un nivel y se mantiene fijo. La cuenta previa
tampoco muestra la etiqueta, así que el cambio es invisible. No es una
regresión de la animación de salida/reingreso.

## Decisión

**Escalera por ronda hasta experto.** Cada ronda avanza un nivel dentro de
`facil → normal → dificil → experto`, con tope en `experto`. En FIESTA el nivel
elegido es el punto de partida; en INDIVIDUAL el punto de partida es `facil`.
INDIVIDUAL pasa a usar los cuatro niveles, así que se retira la restricción
documental «experto solo en FIESTA».

## Cambios

1. `juego/rastreo.py`: añadir `NIVEL_ORDEN` y la función pura
   `nivel_para_ronda(base, ronda)` = `NIVEL_ORDEN[min(3, indice(base) + ronda - 1)]`.
   Reutilizar `DifficultyManager.obtener` para los parámetros; no duplicar la
   tabla `NIVELES`.
2. `arbitro/rastreo.py`: leer `base` una vez fuera del bucle y calcular
   `dificultad = nivel_para_ronda(base, ronda)` dentro; pasar ese nivel a
   `GameManager.generar`. Los mensajes `rastreo_countdown`, `rastreo_show`,
   `rastreo_write` y `rastreo_result` ya llevan `dificultad`: **sin cambiar el
   protocolo**.
3. `static/app.js`: mostrar la etiqueta del nivel en la cuenta previa y en la
   fase de observación, para que el aumento sea visible. Sin secretos nuevos:
   el nivel ya viaja en esos mensajes.
4. Documentación: README (§ RASTREO y reglas) y spec/plan del juego: retirar
   «experto solo en FIESTA» y describir la escalera y el tope.

## No cambia

- Tablero 3×4, ids internos `h1`/`h2`, contrato `salida`/`reaparecio`,
  animación del sprite y secreto de los mandos.
- `ronda_generador` y `DIFICULTADES_FIESTA`: `rastreo` no los usa; el selector
  de FIESTA sigue ofreciendo `experto` sólo para este juego.
- FIESTA con base `experto`: se queda en `experto` desde la ronda 1.

## Verificación

- Test puro de `nivel_para_ronda` para las cuatro bases y 6 rondas.
- Test end-to-end INDIVIDUAL: secuencia `facil, normal, dificil, experto,
  experto, experto`, con entradas/duraciones coherentes con cada etiqueta.
- Test FIESTA con base `normal`: `normal, dificil, experto, experto`; los mandos
  siguen sin `tablero`, `salida` ni `reaparecio`.
- Barrido de las 12 suites, `node --check static/app.js` y `git diff --check`.
