"""Prueba rápida del modelo EMNIST antes de integrarlo al juego.

Uso:
    pip install -r requirements.txt
    python test_reconocedor.py
"""
from __future__ import annotations

import string
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from juego.reconocedor import LADO_IMAGEN, Reconocedor

FUENTES = (
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for ruta in FUENTES:
        if ruta.exists():
            return ImageFont.truetype(str(ruta), tamano)
    return ImageFont.load_default()


def glyph(letra: str) -> np.ndarray:
    """Renderiza una letra con una fuente y la devuelve como tinta 28x28."""
    pixeles = 200
    imagen = Image.new("L", (pixeles, pixeles), 255)
    dibujo = ImageDraw.Draw(imagen)
    fuente = cargar_fuente(int(pixeles * 0.8))
    caja = dibujo.textbbox((0, 0), letra, font=fuente)
    x = (pixeles - (caja[2] - caja[0])) / 2 - caja[0]
    y = (pixeles - (caja[3] - caja[1])) / 2 - caja[1]
    dibujo.text((x, y), letra, font=fuente, fill=0)
    pequena = imagen.resize((LADO_IMAGEN, LADO_IMAGEN), Image.Resampling.LANCZOS)
    return 1.0 - (np.asarray(pequena, dtype=np.float32) / 255.0)


def main() -> None:
    reconocedor = Reconocedor()
    print("Modelo cargado. Probando el alfabeto con letras impresas...\n")

    aciertos = 0
    fallos: list[str] = []
    for letra in string.ascii_uppercase:
        predicha, confianza, _ = reconocedor.reconocer_tinta(glyph(letra))
        ok = predicha == letra
        aciertos += ok
        if not ok:
            fallos.append(f"{letra}->{predicha}({confianza:.0%})")
        print(f"  {letra} -> {predicha}  {confianza:5.1%}  {'OK' if ok else 'x'}")

    print(f"\nPrecisión con letras impresas: {aciertos}/26")

    # Comprobación del camino completo: trazos -> rasterizado -> modelo.
    circulo = [
        [
            (0.5 + 0.3 * np.cos(a), 0.5 + 0.3 * np.sin(a))
            for a in np.linspace(0, 2 * np.pi, 60)
        ]
    ]
    predicha, confianza, _ = reconocedor.reconocer(circulo)
    print(f"Trazo circular dibujado -> {predicha} ({confianza:.1%})")

    vertical = [[(0.5, 0.15), (0.5, 0.85)]]
    predicha, confianza, _ = reconocedor.reconocer(vertical)
    print(f"Trazo vertical dibujado -> {predicha} ({confianza:.1%})")

    if fallos:
        print("\nConfusiones con fuente impresa: " + ", ".join(fallos))
    print("\nSi las letras impresas fallan demasiado, revisa el transpose del preprocesado.")


if __name__ == "__main__":
    main()
