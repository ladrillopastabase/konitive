"""Generación de operaciones para el minijuego «Operaciones Matemáticas».

Se muestra una operación durante un instante y hay que escribir el resultado
cifra a cifra en el mismo canvas que las palabras. Los resultados van de 0 a
99 para que el modelo MNIST (10 clases) baste con reconocer una cifra cada vez.

La dificultad sube con la ronda: primero sumas y restas pequeñas, después
operaciones con decenas y por último multiplicaciones y números mayores. Nunca
se repite la misma operación en rondas consecutivas.
"""
from __future__ import annotations

import random

# (etiqueta, ronda mínima)
NIVELES = (("INICIAL", 1), ("INTERMEDIO", 4), ("AVANZADO", 7))


def nivel_para(ronda: int) -> tuple[int, str]:
    indice = 0 if ronda <= 3 else 1 if ronda <= 6 else 2
    return indice, NIVELES[indice][0]


def _operacion_nivel(indice: int) -> tuple[int, str, int, int]:
    """Devuelve (operando A, operador, operando B, resultado), sin negativos."""
    if indice == 0:
        a, b = random.randint(1, 9), random.randint(1, 9)
        if random.choice((True, False)):
            return a, "+", b, a + b
        return max(a, b), "−", min(a, b), abs(a - b)

    if indice == 1:
        a, b = random.randint(10, 49), random.randint(1, 39)
        if random.choice((True, False)):
            return a, "+", b, a + b
        a, b = random.randint(10, 59), random.randint(1, 59)
        return max(a, b), "−", min(a, b), abs(a - b)

    operador = random.choice(("+", "−", "×"))
    if operador == "×":
        a, b = random.randint(2, 9), random.randint(2, 9)
        return a, operador, b, a * b
    if operador == "+":
        a, b = random.randint(10, 59), random.randint(1, 39)
        return a, operador, b, a + b
    a, b = random.randint(10, 89), random.randint(1, 89)
    return max(a, b), operador, min(a, b), abs(a - b)


def generar_operacion(ronda: int, anterior: str | None = None) -> dict:
    """Genera una operación nueva con resultado de 0 a 99.

    Incluye el texto a mostrar y el resultado como cadena de cifras para que
    el servidor pueda crear una casilla por dígito, igual que con las palabras.
    """
    indice, nombre = nivel_para(ronda)
    mejor: dict | None = None
    for _ in range(80):
        a, operador, b, resultado = _operacion_nivel(indice)
        texto = f"{a} {operador} {b}"
        if texto == anterior or not 0 <= resultado <= 99:
            continue
        candidato = {
            "texto": texto,
            "resultado": str(resultado),
            "operador": operador,
            "nivel": indice + 1,
            "dificultad": nombre,
            "ronda": ronda,
        }
        if len(candidato["resultado"]) == 1 and indice > 0:
            if mejor is None:
                mejor = candidato
            continue
        return candidato

    if mejor is not None:
        return mejor
    return {
        "texto": "8 + 1",
        "resultado": "9",
        "operador": "+",
        "nivel": 1,
        "dificultad": NIVELES[0][0],
        "ronda": ronda,
    }
