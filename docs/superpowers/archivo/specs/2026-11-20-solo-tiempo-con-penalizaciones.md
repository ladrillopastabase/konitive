# Solo tiempo con penalizaciones (sin escala 0–1000)

## Contexto

La puntuación unificada definió `brain_age = tiempo_total + 5 s × errores` pero
además la invirtió a `puntos = max(0, round(1000 - brain_age × 10))` para que el
podio ordenara «mayor es mejor». El usuario aclaró que el número que debe verse
es **el tiempo total incluyendo penalizaciones**, y que la escala 0–1000 se
elimine por completo. La inversión era una decisión propia, no un requisito.

## Decisión

- El número grande de **todas** las tarjetas de resultados es `brain_age`, en
  segundos, con etiqueta `BRAIN AGE · MENOR ES MEJOR`.
- Se eliminan `PUNTOS_BASE`, `PUNTOS_POR_SEGUNDO`, la inversión y todos los
  campos `puntos`/`total` que derivaban de ella.
- `brain_age = tiempo_total + 5.0 × errores_totales` sigue siendo la única
  fórmula. Menor Brain Age gana.

## Alcance

### Servidor

- `arbitro/puntuacion.py`: sustituir `brain_age_y_puntos` por `brain_age` que
  devuelve solo el float. `sumar_historial` devuelve el Brain Age acumulado.
- `arbitro/clasico.py`, `cajas.py`, `operaciones.py`, `rastreo.py`,
  `minijuegos.py`: cada ronda y cada informe llevan `brain_age`, `tiempo_total`
  y `errores`. `mejor` pasa a ser el menor Brain Age de una ronda.
- `decidir_ganador` elige el **menor** Brain Age (antes el mayor de puntos).
- `arbitro/nucleo.py`: `ultimos_puntos`/`fiesta_puntos` pasan a
  `ultimos_brain_age`/`fiesta_brain_age`; `puntos_juego` pasa a
  `brain_age_juego` (también en `CLAVES_SOLO_PANTALLA`); `mis_puntos` pasa a
  `mi_brain_age`. El podio de FIESTA se ordena por menor acumulado.
- `arbitro/sesiones.py`: el total de la sesión suma Brain Age, no puntos.

### Cliente (`static/app.js`)

- Todas las etiquetas `PUNTOS`, `PUNTOS TOTALES`, `RÉCORD`/`NUEVO RÉCORD`
  pasan a `BRAIN AGE`, con `MENOR ES MEJOR`.
- Los números grandes leen `brain_age` (o `tiempo_total` donde aplique) en
  lugar de `puntos`; el desglose existente `textoDesglose` ya muestra tiempo,
  errores y Brain Age y no cambia.
- Los récords locales cambian de clave (`konitive_cajas_record_brain_age`,
  `konitive_operaciones_record_brain_age`) y se comparan con `<`: no tiene
  sentido mezclar valores de la escala antigua con segundos.
- FIESTA: `mi_brain_age` y `brain_age_juego` sustituyen a los campos antiguos.

### Documentación y pruebas

- `README.md` y `PRODUCT.md`: quitar la inversión y describir solo el tiempo
  con penalizaciones.
- Actualizar las 16 suites para que comparen `brain_age` en lugar de `puntos`,
  incluidas las de podio, récords y desgloses. Añadir una prueba que falle si
  aparece cualquier campo `puntos` en los payloads finales.

## Fuera de alcance

- Rediseño visual, nuevos sprites o cambios en las reglas de cada prueba.
- Cambiar cómo se cuentan tiempo y errores (ya corregido en el commit anterior).

## Verificación

- 16 suites en verde con TDD (RED → GREEN) para la eliminación de puntos.
- `node --check static/app.js`, `node --check static/desgloses.js` y
  `git diff --check`.
- Render en Chrome a 1422×844 y 390×844 comprobando que las tarjetas muestran
  segundos y la etiqueta `MENOR ES MEJOR`.
- Sin `add`/`commit`/`push` sin autorización nueva.
