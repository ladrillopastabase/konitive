# Archivo histórico de planificación

> **No es documentación vigente.** Aquí viven las especificaciones y los planes
> de implementación que se escribieron el 19 y el 20 de noviembre, antes del
> rediseño. Se conservan como registro de las decisiones de aquellos días, no
> como contrato del producto actual.

## Qué leer en su lugar

| Documento | Qué cuenta |
| --- | --- |
| `README.md` | Modos, las 13 pruebas, reglas, instalación y suites de prueba. |
| `AGENTS.md` | Arquitectura, flujo de una ronda y recetas para añadir juegos. |
| `PRODUCT.md` | Usuarios, propósito, posicionamiento y límites del producto. |
| `DESIGN.md` | Sistema visual: papel, tinta y rosa. |

## Por qué están desfasados

- Hablan de 11 y 12 pruebas; hoy son **13**.
- Llaman «Brain Age» al resultado; hoy se llama **puntuación** y se mide en
  segundos (`tiempo + 5 s por error`, menor es mejor).
- Varios describen la escala invertida 0–1000, que ya se eliminó.

## Organización

`specs/` guarda el qué y el porqué de cada cambio. `plans/` guarda el paso a
paso con el que se implementó.

### Specs

| Fecha | Documento | Tema |
| --- | --- | --- |
| 2026-11-19 | `specs/2026-11-19-piedra-papel-tijera-design.md` | Diseño de PIEDRA · PAPEL · TIJERA (consigna invertida). |
| 2026-11-20 | `specs/2026-11-20-hamsters-rastreo-design.md` | Diseño de RASTREO DE HÁMSTERS. |
| 2026-11-20 | `specs/2026-11-20-hamsters-rastreo-progresion-dificultad.md` | Progresión de dificultad de RASTREO DE HÁMSTERS. |
| 2026-11-20 | `specs/2026-11-20-puntuacion-brain-age-unificada.md` | Puntuación unificada para las 13 pruebas (incluida la escala 0–1000). |
| 2026-11-20 | `specs/2026-11-20-solo-tiempo-con-penalizaciones.md` | Eliminar la escala 0–1000 y quedarse con el tiempo penalizado. |

### Plans

| Fecha | Documento | Tema |
| --- | --- | --- |
| 2026-11-19 | `plans/2026-11-19-piedra-papel-tijera.md` | Implementación de PIEDRA · PAPEL · TIJERA. |
| 2026-11-20 | `plans/2026-11-20-hamsters-rastreo.md` | Implementación de RASTREO DE HÁMSTERS. |
| 2026-11-20 | `plans/2026-11-20-hamsters-rastreo-progresion-dificultad.md` | Implementación de la progresión de dificultad de RASTREO. |
| 2026-11-20 | `plans/2026-11-20-puntuacion-brain-age-unificada.md` | Implementación de la puntuación unificada. |
| 2026-11-20 | `plans/2026-11-20-solo-tiempo-con-penalizaciones.md` | Implementación de la puntuación sin escala invertida. |

## Nota sobre las rutas

Los documentos conservan las rutas tal como se escribieron
(`docs/superpowers/specs/...` y `docs/superpowers/plans/...`). Hoy equivalen a
`docs/superpowers/archivo/specs/...` y `docs/superpowers/archivo/plans/...`.
No se reescribieron para no alterar el registro.
