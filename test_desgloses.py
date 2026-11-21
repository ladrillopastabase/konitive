"""El desglose único del cliente: tiempo, errores y Brain Age."""
from __future__ import annotations

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

CODIGO = r"""
global.window = global;
const codigo = require('fs').readFileSync('static/desgloses.js', 'utf8');
new Function(codigo)();
process.stdout.write(JSON.stringify([
  textoDesglose({ tiempo: 2, errores: 1, brain_age: 7 }),
  textoDesglose({}),
  textoDesglose({ tiempo: 1.256, errores: 2, brain_age: 11.256 }),
]));
"""


def probar_texto_desglose() -> None:
    resultado = subprocess.run(
        ["node", "-e", CODIGO],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    import json

    completo, vacio, decimales = json.loads(resultado.stdout)
    assert completo == "TIEMPO 2 s · ERRORES 1 · BRAIN AGE 7", completo
    assert vacio == "TIEMPO 0 s · ERRORES 0 · BRAIN AGE 0", vacio
    assert decimales == "TIEMPO 1.26 s · ERRORES 2 · BRAIN AGE 11.26", decimales


def main() -> None:
    probar_texto_desglose()
    print("OK - Desglose único TIEMPO / ERRORES / BRAIN AGE")


if __name__ == "__main__":
    main()
