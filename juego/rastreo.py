"""Tablero y movimientos del minijuego «Rastreo de Hámsters».

El tablero es fijo de 3 filas por 4 columnas y siempre está lleno: diez gatos
y dos hámsters. Cada entrada empuja una línea completa hacia el lado opuesto;
si el gato expulsado era un hámster, este reaparece en otra celda que no sea
la del otro hámster.
"""
from __future__ import annotations

import random

FILAS = 3
COLUMNAS = 4
CELDAS = 12
HAMSTERS = ("h1", "h2")
LADOS = ("izquierda", "derecha", "arriba", "abajo")


class BoardManager:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.celdas: list[str] = []

    def inicializar(self) -> None:
        self.celdas = ["G"] * 10 + list(HAMSTERS)
        self.rng.shuffle(self.celdas)

    def get(self, indice: int) -> str:
        return self.celdas[indice]

    def set(self, indice: int, valor: str) -> None:
        self.celdas[indice] = valor

    def instantanea(self) -> list[str]:
        return list(self.celdas)


class HamsterManager:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def posiciones(self, tablero: BoardManager) -> dict[str, int]:
        halladas = {}
        for indice in range(CELDAS):
            valor = tablero.get(indice)
            if valor in HAMSTERS:
                halladas[valor] = indice
        return halladas

    def regenerar(self, tablero: BoardManager) -> int:
        posiciones = self.posiciones(tablero)
        vuelve = next(h for h in HAMSTERS if h not in posiciones)
        otro = next(h for h in HAMSTERS if h != vuelve)
        destino = self.rng.choice([i for i in range(CELDAS) if i != posiciones[otro]])
        tablero.set(destino, vuelve)
        return destino


class MovementSystem:
    def __init__(self, tablero: BoardManager, hamsters: HamsterManager) -> None:
        self.tablero = tablero
        self.hamsters = hamsters

    def aplicar(self, lado: str, linea: int) -> dict:
        if lado == "izquierda":
            indices = [linea * COLUMNAS + c for c in range(COLUMNAS)]
        elif lado == "derecha":
            indices = [linea * COLUMNAS + c for c in range(COLUMNAS - 1, -1, -1)]
        elif lado == "arriba":
            indices = [f * COLUMNAS + linea for f in range(FILAS)]
        elif lado == "abajo":
            indices = [f * COLUMNAS + linea for f in range(FILAS - 1, -1, -1)]
        else:
            raise ValueError(f"Lado desconocido: {lado}")

        entrada, salida = indices[0], indices[-1]
        expulsado = self.tablero.get(salida)
        for i in range(len(indices) - 1, 0, -1):
            self.tablero.set(indices[i], self.tablero.get(indices[i - 1]))
        self.tablero.set(entrada, "G")

        reaparecio = None
        if expulsado in HAMSTERS:
            reaparecio = self.hamsters.regenerar(self.tablero)

        return {
            "lado": lado,
            "linea": linea,
            "entrada": entrada,
            "salida": salida,
            "reaparecio": reaparecio,
        }


class CatSpawner:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def siguiente(self) -> tuple[str, int]:
        lado = self.rng.choice(LADOS)
        linea = self.rng.randrange(FILAS if lado in ("izquierda", "derecha") else COLUMNAS)
        return lado, linea
