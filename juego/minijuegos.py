"""Generadores de los siete minijuegos de entrenamiento de Konitive.

El host genera aquí cada estímulo y guarda la respuesta correcta. El celular
solo recibe lo que debe mostrar y devuelve una respuesta identificada con el
jugador y el número de ronda.
"""
from __future__ import annotations

import json
import random
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).parent
RUTA_FRASES = BASE / "frases_silabas.json"

# Orden sugerido por la especificación. Se usa tanto en FIESTA como en
# INDIVIDUAL (los botones se renderizan en este orden).
JUEGOS_MINI = (
    "stroop",
    "triangulos",
    "relojes",
    "menor",
    "memoria",
    "vuelto",
    "silabas",
)

NOMBRES_MINI = {
    "stroop": "STROOP",
    "triangulos": "TRIÁNGULOS",
    "relojes": "RELOJES",
    "menor": "MENOR A MAYOR",
    "memoria": "MEMORIA",
    "vuelto": "DAR VUELTO",
    "silabas": "SÍLABAS",
}

RONDAS_MINI = {
    "stroop": 20,
    "triangulos": 10,
    "relojes": 10,
    "menor": 5,
    "memoria": 6,
    "vuelto": 10,
    "silabas": 10,
}

# Juegos que responden dibujando cifras en el componente de escritura ya
# existente. El resto responde tocando botones o casillas.
JUEGOS_ESCRITURA = ("triangulos",)

COLORES = ("rojo", "azul", "verde", "amarillo")
COLOR_HEX = {
    "rojo": "#d33827",
    "azul": "#1d4ed8",
    "verde": "#246b58",
    "amarillo": "#a87300",
}

DENOMINACIONES_CLP = (10000, 5000, 2000, 1000, 500, 100, 50, 10)
PRODUCTOS = (
    ("🍞", "Pan"),
    ("🥤", "Bebida"),
    ("🌭", "Completo"),
    ("🥟", "Empanada"),
    ("📓", "Cuaderno"),
    ("🍎", "Manzana"),
    ("☕", "Café"),
    ("🧃", "Jugo"),
    ("🍫", "Chocolate"),
    ("🧀", "Queso"),
)


def formatear_clp(valor: int) -> str:
    """$3.750, con punto como separador de miles."""
    return f"${valor:,}".replace(",", ".")


# --------------------------------------------------------------------------
# 1. Stroop
# --------------------------------------------------------------------------
def generar_stroop(ronda: int, anterior: tuple[str, str] | None = None) -> dict:
    """Palabra de un color escrita con tinta de otro (o del mismo, a veces)."""
    for _ in range(40):
        palabra = random.choice(COLORES)
        tinta = random.choice(COLORES)
        incongruente = random.random() < (0.5 if ronda <= 4 else 0.75)
        if incongruente and palabra == tinta:
            continue
        if not incongruente:
            tinta = palabra
        if (palabra, tinta) != anterior:
            return {
                "palabra": palabra,
                "tinta": tinta,
                "correcta": tinta,
                "incongruente": incongruente,
                "clave": (palabra, tinta),
                "ronda": ronda,
            }
    return {
        "palabra": "rojo",
        "tinta": "azul",
        "correcta": "azul",
        "incongruente": True,
        "clave": ("rojo", "azul"),
        "ronda": ronda,
    }


# --------------------------------------------------------------------------
# 2. Triángulos de suma
# --------------------------------------------------------------------------
def generar_triangulo(ronda: int) -> dict:
    """Pirámide de tres números; nunca aparece un resultado negativo."""
    if ronda <= 4:
        minimo, maximo, restas = 1, 9, False
    elif ronda <= 7:
        minimo, maximo, restas = 1, 9, True
    else:
        minimo, maximo, restas = 1, 20, True

    for _ in range(300):
        a, b, c = (random.randint(minimo, maximo) for _ in range(3))
        op1 = random.choice(("+", "-")) if restas else "+"
        op2 = random.choice(("+", "-")) if restas else "+"
        op3 = random.choice(("+", "-")) if restas else "+"
        i1 = a + b if op1 == "+" else a - b
        i2 = b + c if op2 == "+" else b - c
        if i1 < 0 or i2 < 0:
            continue
        final = i1 + i2 if op3 == "+" else i1 - i2
        if final < 0:
            continue
        return {
            "top": [a, b, c],
            "ops": [op1, op2],
            "op_final": op3,
            "intermedios": [i1, i2],
            "resultado": final,
            "esperado": f"{final:02d}",
            "dificultad": "FÁCIL" if ronda <= 4 else ("MEDIA" if ronda <= 7 else "DIFÍCIL"),
            "ronda": ronda,
        }

    # Fallback: solo sumas, siempre válido.
    a, b, c = (random.randint(minimo, maximo) for _ in range(3))
    i1, i2 = a + b, b + c
    final = i1 + i2
    return {
        "top": [a, b, c],
        "ops": ["+", "+", "+"][:2],
        "op_final": "+",
        "intermedios": [i1, i2],
        "resultado": final,
        "esperado": f"{final:02d}",
        "dificultad": "FÁCIL",
        "ronda": ronda,
    }


# --------------------------------------------------------------------------
# 3. Lectura de relojes
# --------------------------------------------------------------------------
def generar_reloj(ronda: int) -> dict:
    """Dos relojes analógicos y la diferencia, menor a 12 horas."""
    paso = 15
    minutos_validos = tuple(range(0, 60, paso))
    for _ in range(400):
        hora1 = random.randint(1, 12)
        min1 = random.choice(minutos_validos)
        horas = random.randint(0, 10)
        mins = random.choice(minutos_validos)
        if horas == 0 and mins == 0:
            continue
        if horas * 60 + mins >= 12 * 60:
            continue
        if ronda >= 8:
            pide_prestado = min1 + mins >= 60
            cruza = (hora1 - 1) * 60 + min1 + horas * 60 + mins >= 12 * 60
            if not (pide_prestado or cruza):
                continue
        hora2 = ((hora1 - 1 + horas + (min1 + mins) // 60) % 12) + 1
        min2 = (min1 + mins) % 60
        return {
            "reloj1": [hora1, min1],
            "reloj2": [hora2, min2],
            "horas": horas,
            "minutos": mins,
            "esperado": f"{horas:02d}{mins:02d}",
            "digital1": f"{hora1}:{min1:02d}",
            "digital2": f"{hora2}:{min2:02d}",
            "dificultad": "FÁCIL" if ronda <= 3 else ("MEDIA" if ronda <= 7 else "DIFÍCIL"),
            "ronda": ronda,
        }
    return {
        "reloj1": [2, 15],
        "reloj2": [4, 45],
        "horas": 2,
        "minutos": 30,
        "esperado": "0230",
        "digital1": "2:15",
        "digital2": "4:45",
        "dificultad": "FÁCIL",
        "ronda": ronda,
    }


# --------------------------------------------------------------------------
# 4. De menor a mayor
# --------------------------------------------------------------------------
def generar_menor(ronda: int) -> dict:
    """Números no consecutivos en posiciones normalizadas sin solapamiento."""
    cantidades = (5, 7, 9, 10, 12)
    cantidad = cantidades[min(ronda - 1, len(cantidades) - 1)]
    distancia_minima = 0.17
    for _ in range(200):
        valores = random.sample(range(1, 100), cantidad)
        ordenados = sorted(valores)
        if all(b - a == 1 for a, b in zip(ordenados, ordenados[1:])):
            continue
        puntos: list[tuple[float, float, int]] = []
        for valor in valores:
            for _intento in range(120):
                x = round(random.uniform(0.09, 0.91), 3)
                y = round(random.uniform(0.10, 0.90), 3)
                if all(
                    (x - px) ** 2 + (y - py) ** 2 >= distancia_minima**2
                    for px, py, _ in puntos
                ):
                    puntos.append((x, y, valor))
                    break
            else:
                break
        if len(puntos) == cantidad:
            numeros = [
                {"valor": valor, "x": x, "y": y} for x, y, valor in puntos
            ]
            return {
                "numeros": numeros,
                "orden": [i for i, _ in sorted(enumerate(numeros), key=lambda par: par[1]["valor"])],
                "cantidad": cantidad,
                "ronda": ronda,
                "necesario": RONDAS_MINI["menor"],
            }
    valores = random.sample(range(1, 100), cantidad)
    return {
        "numeros": [
            {"valor": v, "x": 0.1 + 0.8 * i / max(1, cantidad - 1), "y": 0.5}
            for i, v in enumerate(valores)
        ],
        "orden": [i for i, _ in sorted(enumerate(valores), key=lambda par: par[1])],
        "cantidad": cantidad,
        "ronda": ronda,
        "necesario": RONDAS_MINI["menor"],
    }


# --------------------------------------------------------------------------
# 5. Memoria de números
# --------------------------------------------------------------------------
TABLA_MEMORIA = (
    (3, 3, 4),
    (3, 4, 4),
    (4, 5, 4),
    (4, 6, 5),
    (4, 7, 5),
    (5, 8, 6),
)


def generar_memoria(ronda: int) -> dict:
    """Grilla con los números 1..N en casillas aleatorias."""
    grilla, cantidad, segundos = TABLA_MEMORIA[
        min(ronda - 1, len(TABLA_MEMORIA) - 1)
    ]
    celdas = random.sample(range(grilla * grilla), cantidad)
    return {
        "grilla": grilla,
        "celdas": grilla * grilla,
        "cantidad": cantidad,
        "posiciones": {str(numero): celdas[numero - 1] for numero in range(1, cantidad + 1)},
        "segundos": segundos,
        "ronda": ronda,
        "necesario": RONDAS_MINI["memoria"],
    }


# --------------------------------------------------------------------------
# 6. Dar vuelto
# --------------------------------------------------------------------------
def vuelto_optimo(valor: int) -> dict[str, int]:
    """Algoritmo greedy: válido para las denominaciones chilenas actuales."""
    resultado: dict[str, int] = {}
    restante = valor
    for denominacion in DENOMINACIONES_CLP:
        cantidad, restante = divmod(restante, denominacion)
        if cantidad:
            resultado[str(denominacion)] = cantidad
    return resultado


def generar_vuelto(ronda: int) -> dict:
    """Producto, pago realista y vuelto exacto en pesos chilenos."""
    if ronda <= 3:
        precio = random.randint(1, 30) * 100
    elif ronda <= 7:
        precio = random.randint(1, 150) * 10
    else:
        precio = random.randint(100, 900) * 10

    superiores = [d for d in reversed(DENOMINACIONES_CLP) if d > precio]
    if not superiores:
        precio = 100
        superiores = list(DENOMINACIONES_CLP)
    indice = 1 if len(superiores) > 1 and random.random() < 0.2 else 0
    pago = superiores[min(indice, len(superiores) - 1)]
    vuelto = pago - precio
    icono, nombre = random.choice(PRODUCTOS)
    return {
        "producto": {"icono": icono, "nombre": nombre},
        "precio": precio,
        "precio_texto": formatear_clp(precio),
        "pago": pago,
        "pago_texto": formatear_clp(pago),
        "vuelto": vuelto,
        "vuelto_texto": formatear_clp(vuelto),
        "optimo": vuelto_optimo(vuelto),
        "denominaciones": list(DENOMINACIONES_CLP),
        "dificultad": "FÁCIL" if ronda <= 3 else ("MEDIA" if ronda <= 7 else "DIFÍCIL"),
        "ronda": ronda,
        "necesario": RONDAS_MINI["vuelto"],
    }


# --------------------------------------------------------------------------
# 7. Contar sílabas
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def cargar_frases() -> tuple[dict, ...]:
    with RUTA_FRASES.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    return tuple(datos)


def _categoria(frase: dict) -> int:
    palabras = len(frase["frase"].split())
    total = len(frase["silabas"])
    if palabras <= 3 and total <= 8:
        return 0
    if palabras <= 5 and 9 <= total <= 13:
        return 1
    return 2


def generar_silabas(ronda: int, frase_anterior: str | None = None) -> dict:
    """Frase curada, con la separación silábica ya validada en el archivo."""
    categoria = 0 if ronda <= 3 else (1 if ronda <= 7 else 2)
    candidatos = [f for f in cargar_frases() if _categoria(f) == categoria]
    if frase_anterior:
        otros = [f for f in candidatos if f["frase"] != frase_anterior]
        if otros:
            candidatos = otros
    frase = random.choice(candidatos)
    return {
        "frase": frase["frase"],
        "silabas": list(frase["silabas"]),
        "total": len(frase["silabas"]),
        "esperado": f"{len(frase['silabas']):02d}",
        "pista": " · ".join(frase["silabas"]),
        "dificultad": "FÁCIL" if categoria == 0 else ("MEDIA" if categoria == 1 else "DIFÍCIL"),
        "ronda": ronda,
    }


def generar(ronda: int, juego: str, anterior=None) -> dict:
    """Punto de entrada único usado por el bucle del servidor."""
    if juego == "stroop":
        return generar_stroop(ronda, anterior)
    if juego == "triangulos":
        return generar_triangulo(ronda)
    if juego == "relojes":
        return generar_reloj(ronda)
    if juego == "menor":
        return generar_menor(ronda)
    if juego == "memoria":
        return generar_memoria(ronda)
    if juego == "vuelto":
        return generar_vuelto(ronda)
    if juego == "silabas":
        return generar_silabas(ronda, anterior)
    raise ValueError(f"Minijuego desconocido: {juego}")
