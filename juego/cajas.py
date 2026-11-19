"""Generación de pilas isométricas para el minijuego «Cuenta Cajas».

La pila se representa como una matriz de alturas: ``alturas[y][x]`` es el
número de cajas apiladas en esa casilla de la base. Una columna siempre es
sólida (va del suelo hasta su altura), así que nunca aparece una caja
flotando y el total correcto es la suma de todas las alturas.

El dibujo isométrico separa ligeramente cada cubo (del mismo modo que una
maqueta con separadores), de manera que TODAS las cajas quedan a la vista y se
pueden contar. Por eso ``visibles`` es siempre igual al total y no hay cajas
ocultas que el jugador deba adivinar.
"""
from __future__ import annotations

import random

# (nombre, tamaño de la base, total mínimo, total máximo, altura máxima, segundos)
# La base siempre es al menos 5×5: en FÁCIL el total mínimo sube a 5 para que
# pueda haber una columna en cada fila de la cuadrícula.
DIFICULTADES: tuple[tuple[str, int, int, int, int, float], ...] = (
    ("FÁCIL", 5, 5, 10, 3, 3.0),
    ("NORMAL", 5, 7, 14, 4, 2.0),
    ("DIFÍCIL", 5, 12, 22, 5, 1.5),
)


def suma_total(alturas: list[list[int]]) -> int:
    return sum(sum(fila) for fila in alturas)


def contar_visibles(alturas: list[list[int]]) -> int:
    """Todas las cajas se ven: el dibujo separa cada cubo de sus vecinos."""
    return suma_total(alturas)


def _repartir(base: int, total: int, tope: int) -> list[list[int]] | None:
    """Construye una pila compacta y natural sobre la base cuadriculada.

    Se elige un grupo de casillas contiguas (creciendo desde una casilla
    inicial por sus vecinas) y se van apilando cajas hasta llegar al total.
    El resultado es una pila 2D, nunca una diagonal ni casillas aisladas.
    """
    if total < 2 or total > base * base * tope:
        return None
    columnas = random.randint(max(2, base - 2), min(base * base, total))
    sx, sy = random.randrange(base), random.randrange(base)
    celdas = {(sx, sy)}
    while len(celdas) < columnas:
        frontera = [
            (x + dx, y + dy)
            for x, y in celdas
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if 0 <= x + dx < base
            and 0 <= y + dy < base
            and (x + dx, y + dy) not in celdas
        ]
        if not frontera:
            break
        celdas.add(random.choice(frontera))

    alturas = [[0] * base for _ in range(base)]
    for x, y in celdas:
        alturas[y][x] = 1

    restante = total - len(celdas)
    while restante:
        candidatas = [(x, y) for x, y in celdas if alturas[y][x] < tope]
        if not candidatas:
            return None
        x, y = random.choice(candidatas)
        alturas[y][x] += 1
        restante -= 1
    return alturas


def generar_pila(
    indice_dificultad: int, anterior: list[list[int]] | None = None
) -> dict:
    """Genera una pila nueva respetando la dificultad y sin repetir la anterior.

    Devuelve las alturas, el total, las cajas visibles y los datos de fase de la
    dificultad. La respuesta se introduce con el mismo contador que los pájaros.
    """
    indice = max(0, min(len(DIFICULTADES) - 1, indice_dificultad))
    nombre, base, minimo, maximo, tope, segundos = DIFICULTADES[indice]

    for _ in range(120):
        total = random.randint(minimo, maximo)
        alturas = _repartir(base, total, tope)
        if alturas is None:
            continue
        if anterior is not None and alturas == anterior:
            continue
        visibles = contar_visibles(alturas)
        return {
            "alturas": alturas,
            "total": total,
            "visibles": visibles,
            "ocultas": total - visibles,
            "base": base,
            "dificultad": nombre,
            "segundos": segundos,
        }

    # Fallback determinista (no debería alcanzarse): pila 2D pequeña.
    alturas = [[0] * base for _ in range(base)]
    alturas[base - 1][base - 1] = 2
    alturas[base - 1][base - 2] = 2
    alturas[base - 2][base - 1] = 1
    total = suma_total(alturas)
    visibles = contar_visibles(alturas)
    return {
        "alturas": alturas,
        "total": total,
        "visibles": visibles,
        "ocultas": total - visibles,
        "base": base,
        "dificultad": nombre,
        "segundos": segundos,
    }
