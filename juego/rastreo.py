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


RONDAS_RASTREO = 6

# observación y movimiento en segundos; animación es la duración de cada entrada
NIVELES = {
    "facil": {
        "observacion": 6.0, "movimiento": 6.0, "entradas": 4,
        "intervalo": 1.5, "animacion": 0.45,
    },
    "normal": {
        "observacion": 5.0, "movimiento": 8.0, "entradas": 6,
        "intervalo": 1.3, "animacion": 0.35,
    },
    "dificil": {
        "observacion": 4.0, "movimiento": 10.0, "entradas": 9,
        "intervalo": 1.1, "animacion": 0.25,
    },
    "experto": {
        "observacion": 3.0, "movimiento": 12.0, "entradas": 12,
        "intervalo": 1.0, "animacion": 0.18,
    },
}


class DifficultyManager:
    @staticmethod
    def obtener(nivel: str) -> dict:
        if not isinstance(nivel, str) or nivel not in NIVELES:
            return NIVELES["facil"]
        return NIVELES[nivel]


class SelectionManager:
    def __init__(self) -> None:
        self._casillas: list[int] = []

    def registrar(self, celda: int) -> bool:
        if isinstance(celda, bool) or not isinstance(celda, int):
            return False
        if not 0 <= celda < CELDAS:
            return False
        if celda in self._casillas or len(self._casillas) >= 2:
            return False
        self._casillas.append(celda)
        return True

    def seleccionadas(self) -> tuple[int, ...]:
        return tuple(self._casillas)

    def completa(self) -> bool:
        return len(self._casillas) == 2


class ScoreManager:
    @staticmethod
    def evaluar(seleccion: tuple[int, ...], posiciones: dict[str, int]) -> dict:
        aciertos = len(set(seleccion) & set(posiciones.values()))
        return {
            "aciertos": aciertos,
            "errores": 2 - aciertos,
            "precision": 100 * aciertos / 2,
        }


class GameManager:
    """Plan de una ronda: observación, entradas y posiciones finales."""

    def __init__(self, nivel: str = "normal", semilla: int | None = None) -> None:
        self.parametros = dict(DifficultyManager.obtener(nivel))
        rng = random.Random(semilla)
        self.tablero = BoardManager(rng)
        self.hamsters = HamsterManager(rng)
        self.movimiento = MovementSystem(self.tablero, self.hamsters)
        self.spawner = CatSpawner(rng)
        self.tablero.inicializar()
        self.observacion = self.tablero.instantanea()
        self.movimientos: list[dict] = []
        self.final: dict[str, int] = {}
        self._entradas = 0

    def fase_actual(self) -> str:
        if self.final:
            return "final"
        if self._entradas:
            return "movimientos"
        return "observacion"

    def avanzar(self) -> dict | None:
        if self._entradas >= self.parametros["entradas"]:
            self.final = dict(self.hamsters.posiciones(self.tablero))
            return None
        lado, linea = self.spawner.siguiente()
        self.movimiento.aplicar(lado, linea)
        entrada = {
            "lado": lado,
            "linea": linea,
            "duracion": self.parametros["animacion"],
        }
        self.movimientos.append(entrada)
        self._entradas += 1
        if self._entradas == self.parametros["entradas"]:
            self.final = dict(self.hamsters.posiciones(self.tablero))
        return dict(entrada)

    @classmethod
    def generar(cls, nivel: str = "normal", semilla: int | None = None) -> dict:
        partida = cls(nivel, semilla)
        while partida.fase_actual() != "final":
            partida.avanzar()
        return {
            "observacion": list(partida.observacion),
            "movimientos": [dict(m) for m in partida.movimientos],
            "final": dict(partida.final),
            "parametros": dict(partida.parametros),
        }
