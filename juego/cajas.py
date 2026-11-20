"""Generación de pilas isométricas para el minijuego «Cuenta Cajas».

La pila se representa como una matriz de alturas: ``alturas[y][x]`` es el
número de cajas apiladas en esa casilla de la base. Una columna siempre es
sólida (va del suelo hasta su altura), así que nunca aparece una caja
flotando y el total correcto es la suma de todas las alturas.

Las cajas se dibujan juntas, como una pila real. Para que el conteo sea justo
el generador descarta las pilas en las que alguna caja quede tapada: dibuja la
pila igual que el cliente (``dibujarPila`` en ``static/app.js``) y mide qué
parte de cada caja se ve. Así ``visibles`` siempre es igual al total.
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw

# Fracción mínima de la silueta de cada caja que debe verse para contarla
# como visible (por debajo es solo una astilla entre otras cajas).
VISIBLE_MINIMO = 0.2
PIXELES_POR_CAJA = 40

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


def fraccion_visible(alturas: list[list[int]]) -> dict[tuple[int, int, int], float]:
    """Qué parte de cada caja (x, y, z) se ve en el dibujo isométrico.

    Replica la proyección, las tres caras visibles y el orden del pintor de
    ``dibujarPila`` (static/app.js): si uno cambia, el otro también.
    """
    s = PIXELES_POR_CAJA
    base = len(alturas)
    tope = max((max(fila) for fila in alturas), default=0)
    ox, oy = base * s / 2 + 2, tope * s / 2 + 2

    def p(x: int, y: int, z: int) -> tuple[float, float]:
        return (ox + (x - y) * s / 2, oy + (x + y) * s / 4 - z * s / 2)

    cajas = [
        (x, y, z) for y in range(base) for x in range(base) for z in range(alturas[y][x])
    ]
    cajas.sort(key=lambda c: (c[0] + c[1], c[2]))
    imagen = Image.new("I", (base * s + 4, int((base + tope) * s / 2) + 4), 0)
    dibujo = ImageDraw.Draw(imagen)
    for i, (x, y, z) in enumerate(cajas, start=1):
        for cara in (
            [p(x, y + 1, z), p(x + 1, y + 1, z), p(x + 1, y + 1, z + 1), p(x, y + 1, z + 1)],
            [p(x + 1, y, z), p(x + 1, y + 1, z), p(x + 1, y + 1, z + 1), p(x + 1, y, z + 1)],
            [p(x, y, z + 1), p(x + 1, y, z + 1), p(x + 1, y + 1, z + 1), p(x, y + 1, z + 1)],
        ):
            dibujo.polygon(cara, fill=i)
    pixeles = np.bincount(np.asarray(imagen).ravel(), minlength=len(cajas) + 1)
    silueta = 3 * s * s / 4  # rombo superior + dos caras laterales
    return {caja: pixeles[i] / silueta for i, caja in enumerate(cajas, start=1)}


def contar_visibles(alturas: list[list[int]]) -> int:
    """Cajas que se ven lo bastante para contarlas."""
    return sum(1 for v in fraccion_visible(alturas).values() if v >= VISIBLE_MINIMO)


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
        if visibles != total:  # alguna caja quedaría tapada: no es justa
            continue
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
