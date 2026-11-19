"""Listas de palabras para la prueba de escritura.

EMNIST solo conoce las 26 letras A-Z, así que las palabras en español no
llevan tildes ni ñ (p. ej. ``MANANA``, ``MUSICA``). Se agrupan por longitud
para ir subiendo la dificultad a medida que avanzan las rondas.
"""
from __future__ import annotations

import random

PALABRAS: dict[str, dict[int, tuple[str, ...]]] = {
    "es": {
        3: ("SOL", "MAR", "PAN", "LUZ", "RIO", "DOS", "OJO", "BOL", "AVE", "MES"),
        4: (
            "CASA", "MESA", "AGUA", "NUBE", "LUNA", "FLOR",
            "ROSA", "HOJA", "RAMA", "AZUL", "PATO", "GATO",
        ),
        5: (
            "PERRO", "LIBRO", "NIEVE", "MUNDO", "TIGRE", "PLAYA",
            "CIELO", "FUEGO", "JUEGO", "ARBOL", "ROBLE", "TRIGO",
        ),
        6: (
            "CAMINO", "BOSQUE", "MUSICA", "CIUDAD", "MANANA", "PAJARO",
            "COCINA", "JARDIN", "FUERZA", "PASION",
        ),
        7: (
            "MONTANA", "CORAZON", "AMISTAD", "VENTANA", "ESCUELA",
            "TRABAJO", "FAMILIA", "PAISAJE", "BOSQUES", "CAMPANA",
        ),
        8: (
            "ESTRELLA", "HOSPITAL", "AVENTURA", "CABALLOS", "PELICULA",
            "MAQUINAS", "SERVICIO", "HISTORIA", "LIBRERIA",
        ),
    },
    "en": {
        3: ("SUN", "CAT", "DOG", "SKY", "CUP", "BOX", "KEY", "RUN", "HAT", "PEN"),
        4: ("BOOK", "HOME", "WIND", "FIRE", "TREE", "MOON", "STAR", "BLUE", "FISH", "DOOR"),
        5: (
            "HOUSE", "WATER", "LIGHT", "NIGHT", "RIVER",
            "STONE", "CLOUD", "TRAIN", "BREAD", "SMILE",
        ),
        6: (
            "GARDEN", "SCHOOL", "PAPERS", "WINTER", "SUMMER",
            "PLANET", "CIRCLE", "POCKET", "SILVER", "FOREST",
        ),
        7: (
            "PICTURE", "MORNING", "FRIENDS", "WINDOWS", "PENCILS",
            "BASKETS", "CIRCLES", "GARDENS", "POCKETS", "SUNSETS",
        ),
        8: (
            "SUNLIGHT", "ELEPHANT", "NOTEBOOK", "SANDWICH",
            "AIRPLANE", "MOUNTAIN", "CALENDAR", "FESTIVAL",
        ),
    },
}

# La longitud crece con cada ronda de escritura y se mantiene en 8.
LONGITUDES_POR_NIVEL = (3, 4, 5, 6, 7, 8, 8, 8)


def palabra_para(nivel: int, usadas: set[str] | None = None) -> str:
    """Devuelve una palabra del idioma y longitud adecuados al nivel.

    El nivel empieza en 1. Se evitan las palabras ya usadas en la partida
    mientras queden opciones disponibles.
    """
    usadas = usadas or set()
    largo = LONGITUDES_POR_NIVEL[min(max(nivel, 1), len(LONGITUDES_POR_NIVEL)) - 1]
    idioma = random.choice(("es", "en"))
    opciones = [p for p in PALABRAS[idioma][largo] if p not in usadas]
    if not opciones:
        opciones = list(PALABRAS[idioma][largo])
    return random.choice(opciones)
