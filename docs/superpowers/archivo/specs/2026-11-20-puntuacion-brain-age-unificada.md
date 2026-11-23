# Especificación: puntuación Brain Age unificada

## Decisión del usuario

- Aplica a **las 13 pruebas**, en INDIVIDUAL y en FIESTA.
- La puntuación depende **solo del tiempo y de los errores**.
- Cada error suma **5 segundos** al tiempo.
- En PALABRAS y OPERACIONES cuenta como error **cada intento fallido** de un carácter.

## Fórmula única

```
brain_age = tiempo_total + 5.0 * errores_totales
puntos    = max(0, round(1000 - brain_age * 10))
```

Menor Brain Age es mejor; el podio y los resúmenes siguen ordenando de mayor a
menor `puntos` para no cambiar la dirección visual. Un jugador perfecto e
instantáneo parte de 1000; cada segundo resta 10 puntos y cada error resta 50.

## Medición por juego

| Juego | Inicio del cronómetro | Fin | Error |
| --- | --- | --- | --- |
| HÁMSTERS | `birds_show` | confirmación de la cuenta | cuenta distinta de la correcta |
| PALABRAS | fin del flash de la palabra | última letra aceptada | cada letra rechazada (incluida la aceptada automáticamente tras 3 fallos) |
| CAJAS | `cajas_hide` | confirmación de la cuenta | cuenta distinta de la correcta |
| OPERACIONES | fin del flash de la operación | última cifra aceptada | cada cifra rechazada (incluida la automática) |
| RASTREO | fin de los movimientos | confirmación de las posiciones | ya implementado: 2 − aciertos |
| 8 minijuegos | desaparición del estímulo | respuesta | ya implementado: respuesta inválida |

Sin respuesta dentro del plazo: se cuenta el **tiempo límite completo** y **un
error**, igual en las 13 pruebas. Esto sustituye el comportamiento actual de
HÁMSTERS (usaba el último conteo con tiempo de relleno) y de los minijuegos
(tiempo límite sin error).

## Lo que se elimina

- HÁMSTERS: base 100 y bono de 10 puntos/segundo.
- PALABRAS y OPERACIONES: 30/20/10 puntos por carácter y bono de 50 puntos.
- CAJAS: base 100, bono de 50 y multiplicador por racha. La racha sigue
  existiendo solo para subir la dificultad cada 3 aciertos; deja de multiplicar
  puntos y de mostrarse en el desglose.
- Constantes y desgloses que solo servían a esas fórmulas (`bono`, `letras`,
  `digitos`) se sustituyen por `tiempo`, `errores`, `brain_age`, `puntos`.

## Lo que se conserva

- Protocolos WebSocket y nombres de mensajes; cambian los campos del desglose,
  no el tipo. Los mandos siguen sin recibir secretos ni respuestas correctas.
- Orden de juegos, dificultad progresiva, cantidades de rondas, límites de
  tiempo, feedback privado y podios.
- La función `brain_age_y_puntos` de `arbitro/minijuegos.py` pasa a ser la
  implementación compartida; se mueve a un módulo común sin cambiar su formula.

## Interfaz

- Los paneles de resultado muestran `TIEMPO`, `ERRORES` y `BRAIN AGE` con el
  mismo estilo papel/tinta; desaparecen las líneas de `BASE + RAPIDEZ` y `×N`.
- El informe final de INDIVIDUAL y el podio de FIESTA siguen mostrando puntos
  altos, ahora con escala común 0–1000.

## Verificación

- Prueba nueva RED→GREEN que compruebe la fórmula compartida y el +5 s/error
  en cada una de las 13 pruebas, incluido el caso sin respuesta.
- Actualizar las aserciones de `test_partida.py`, `test_cajas.py`,
  `test_operaciones.py`, `test_minijuegos.py`, `test_rastreo.py`,
  `test_individual.py`, `test_salas.py` y `test_fiesta_progreso.py` que hoy
  esperan base/bono/multiplicador.
- Barrido completo de suites, `node --check static/app.js` y render en Chrome
  a 390×844 y 1440×900.

## Fuera de alcance

- Cambiar la dificultad progresiva, el orden de las pruebas o la privacidad de
  mandos.
- Commit y push: requieren autorización nueva y explícita.
