"""Pruebas del corpus curado de «Contar sílabas».

El archivo juego/frases_silabas.json debe ser verificable por sí mismo: al
concatenar las sílabas de cada frase se tiene que reconstruir la frase original
ignorando espacios y mayúsculas. Además se comprueba que el generador respeta
los tres niveles de dificultad y no repite la frase anterior.
"""
from __future__ import annotations

import apoyo  # primero: deja la raíz del proyecto en sys.path

import re

from juego.minijuegos import RONDAS_MINI, cargar_frases, generar_silabas


def normalizar(texto: str) -> str:
    """Compara ignorando espacios y mayúsculas, como pide la especificación."""
    return re.sub(r"\s+", "", texto).casefold()


def validar_corpus() -> None:
    frases = cargar_frases()
    assert len(frases) >= 60, f"El corpus tiene solo {len(frases)} frases"

    vistas: set[str] = set()
    for frase in frases:
        assert set(frase) == {"frase", "silabas"}, frase
        assert isinstance(frase["frase"], str) and frase["frase"].strip(), frase
        silabas = frase["silabas"]
        assert isinstance(silabas, list) and len(silabas) >= 2, frase
        assert all(isinstance(s, str) and s.strip() and not s.isspace() for s in silabas), frase
        assert " " not in "".join(silabas), frase
        assert normalizar(frase["frase"]) == normalizar("".join(silabas)), frase
        vistas.add(frase["frase"])

    assert len(vistas) == len(frases), "Hay frases repetidas en el corpus"
    print(f"Corpus: {len(frases)} frases válidas, ninguna repetida")


def validar_generador() -> None:
    anterior = None
    for ronda in range(1, RONDAS_MINI["silabas"] + 1):
        dificultad = "FÁCIL" if ronda <= 3 else ("MEDIA" if ronda <= 7 else "DIFÍCIL")
        for _ in range(40):
            reto = generar_silabas(ronda, anterior)
            assert reto["frase"] != anterior, reto
            assert reto["dificultad"] == dificultad, reto
            assert reto["total"] == len(reto["silabas"]), reto
            assert reto["esperado"] == f"{reto['total']:02d}", reto
            assert normalizar(reto["frase"]) == normalizar("".join(reto["silabas"])), reto
            anterior = reto["frase"]
    print("Generador: niveles, total coherente y sin repeticiones correctos")


def main() -> None:
    validar_corpus()
    validar_generador()
    print("\nOK - Contar sílabas correcto")


if __name__ == "__main__":
    main()
