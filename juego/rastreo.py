"""Tablero y movimientos del minijuego «Rastreo de Hámsters».

El tablero es de 3 filas por 4 columnas: diez gatos y dos hámsters. Cada
entrada empuja una línea completa hacia el lado opuesto; si lo expulsado era
un hámster, pasa un turno fuera y vuelve en otra celda en la entrada
siguiente. Al terminar siempre están los dos.
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

    def regenerar(
        self, tablero: BoardManager, hamster: str, vedadas: set[int] | None = None
    ) -> int:
        """Reintroduce un hámster que estaba fuera sin pisar al otro.

        ``vedadas`` incluye las casillas que los hámsters ocupaban antes del
        desplazamiento y la línea que se está moviendo: el sprite que vuelve
        no debe aparecer justo donde el otro acababa de estar.
        """
        excluidas = set(self.posiciones(tablero).values()) | (vedadas or set())
        destino = self.rng.choice([i for i in range(CELDAS) if i not in excluidas])
        tablero.set(destino, hamster)
        return destino


class MovementSystem:
    """Desplaza líneas. Un hámster expulsado queda fuera un turno entero y
    vuelve en la entrada siguiente; en la última vuelve en el mismo turno,
    para que al final siempre estén los dos."""

    def __init__(self, tablero: BoardManager, hamsters: HamsterManager) -> None:
        self.tablero = tablero
        self.hamsters = hamsters
        self.fuera: list[str] = []

    def aplicar(self, lado: str, linea: int, ultimo: bool = False) -> dict:
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
        vedadas = set(self.hamsters.posiciones(self.tablero).values()) | set(indices)
        for i in range(len(indices) - 1, 0, -1):
            self.tablero.set(indices[i], self.tablero.get(indices[i - 1]))
        self.tablero.set(entrada, "G")

        # Vuelven los que salieron el turno anterior (no el recién expulsado).
        vuelven = self.fuera
        self.fuera = []
        if expulsado in HAMSTERS:
            self.fuera.append(expulsado)
        if ultimo:
            vuelven, self.fuera = vuelven + self.fuera, []
        entran = [self.hamsters.regenerar(self.tablero, h, vedadas) for h in vuelven]

        return {
            "lado": lado,
            "linea": linea,
            "entrada": entrada,
            "salida": salida if expulsado in HAMSTERS else None,
            "entran": entran,
        }


class CatSpawner:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def siguiente(self) -> tuple[str, int]:
        lado = self.rng.choice(LADOS)
        linea = self.rng.randrange(FILAS if lado in ("izquierda", "derecha") else COLUMNAS)
        return lado, linea


RONDAS_RASTREO = 6
NIVEL_ORDEN = ("facil", "normal", "dificil", "experto")

# observación y movimiento en segundos; animación es la duración de cada
# entrada. El hámster que sale o vuelve tarda el doble: intervalo >= 2 × animación.
NIVELES = {
    "facil": {
        "observacion": 6.0, "movimiento": 6.0, "entradas": 4,
        "intervalo": 1.5, "animacion": 0.55,
    },
    "normal": {
        "observacion": 5.0, "movimiento": 8.0, "entradas": 6,
        "intervalo": 1.3, "animacion": 0.45,
    },
    "dificil": {
        "observacion": 4.0, "movimiento": 10.0, "entradas": 9,
        "intervalo": 1.1, "animacion": 0.38,
    },
    "experto": {
        "observacion": 3.0, "movimiento": 12.0, "entradas": 12,
        "intervalo": 1.0, "animacion": 0.32,
    },
}
EXTRA_MAXIMO = 4  # rondas más allá de experto que siguen endureciendo


def nivel_para_ronda(base: str, ronda: int) -> str:
    """Nivel de una ronda: escalera desde ``base``, con tope en experto."""
    indice = NIVEL_ORDEN.index(base) if base in NIVEL_ORDEN else 0
    return NIVEL_ORDEN[min(len(NIVEL_ORDEN) - 1, indice + max(0, ronda - 1))]


def extra_para_ronda(base: str, ronda: int) -> int:
    """Rondas jugadas ya en experto: cada una suma entradas y velocidad."""
    indice = NIVEL_ORDEN.index(base) if base in NIVEL_ORDEN else 0
    return min(EXTRA_MAXIMO, max(0, indice + ronda - len(NIVEL_ORDEN)))


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

    def __init__(
        self, nivel: str = "normal", semilla: int | None = None, extra: int = 0
    ) -> None:
        self.parametros = dict(DifficultyManager.obtener(nivel))
        if extra:
            factor = 0.9 ** extra
            self.parametros["entradas"] += 2 * extra
            self.parametros["intervalo"] = round(self.parametros["intervalo"] * factor, 2)
            self.parametros["animacion"] = round(self.parametros["animacion"] * factor, 2)
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
        ultimo = self._entradas + 1 == self.parametros["entradas"]
        resultado = self.movimiento.aplicar(lado, linea, ultimo)
        # La pantalla necesita por dónde se va un hámster y dónde vuelven los
        # que estaban fuera; nunca el id interno, que no cruza la capa de juego.
        entrada = {
            "lado": lado,
            "linea": linea,
            "duracion": self.parametros["animacion"],
            "salida": resultado["salida"],
            "entran": resultado["entran"],
        }
        self.movimientos.append(entrada)
        self._entradas += 1
        if self._entradas == self.parametros["entradas"]:
            self.final = dict(self.hamsters.posiciones(self.tablero))
        return dict(entrada)

    @classmethod
    def generar(
        cls, nivel: str = "normal", semilla: int | None = None, extra: int = 0
    ) -> dict:
        partida = cls(nivel, semilla, extra)
        while partida.fase_actual() != "final":
            partida.avanzar()
        return {
            "observacion": list(partida.observacion),
            "movimientos": [dict(m) for m in partida.movimientos],
            "final": dict(partida.final),
            "parametros": dict(partida.parametros),
        }
