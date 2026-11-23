"""Corre todas las pruebas en paralelo y resume.

    python tests/correr.py            # todas
    python tests/correr.py rastreo    # solo las que contienen "rastreo"

Cada prueba es un script independiente con su propio servidor en un puerto
libre, así que pueden ir a la vez. Sale con código 1 si alguna falla.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CARPETA = Path(__file__).resolve().parent


def correr(prueba: Path) -> tuple[Path, int, float, str]:
    inicio = time.monotonic()
    proceso = subprocess.run(
        [sys.executable, str(prueba)],
        cwd=CARPETA.parent,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    return prueba, proceso.returncode, time.monotonic() - inicio, proceso.stdout + proceso.stderr


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    pruebas = sorted(p for p in CARPETA.glob("test_*.py") if filtro in p.stem)
    fallos = []
    with ThreadPoolExecutor(max_workers=8) as grupo:
        for prueba, codigo, segundos, salida in grupo.map(correr, pruebas):
            estado = "ok   " if codigo == 0 else "FALLA"
            print(f"{estado} {prueba.name:<38} {segundos:5.1f} s")
            if codigo:
                fallos.append((prueba, salida))
    for prueba, salida in fallos:
        print(f"\n===== {prueba.name} =====\n{salida[-3000:]}")
    print(f"\n{len(pruebas) - len(fallos)}/{len(pruebas)} pruebas correctas")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
