"""Las descripciones del selector individual responden al puntero y al teclado.

Prueba de integración: levanta el cliente real en un servidor local, lo abre en
Chrome headless y dispara los eventos sobre los botones verdaderos. No revisa
código fuente: comprueba lo que el jugador lee en la pantalla.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
STATIC = RAIZ / "static"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

JUEGOS = [
    "pajaros", "escritura", "cajas", "operaciones", "stroop", "triangulos",
    "relojes", "menor", "memoria", "vuelto", "silabas", "rastreo", "ppt",
]

HARNESS = """<!doctype html><meta charset="utf-8">
<iframe id="f" src="/index.html" style="width:1200px;height:900px"></iframe>
<pre id="resultado">PENDIENTE</pre>
<script>
const salida = document.getElementById('resultado');
const terminar = (datos) => { salida.textContent = JSON.stringify(datos); };
document.getElementById('f').addEventListener('load', () => {
  try {
    const d = document.getElementById('f').contentDocument;
    const titulo = d.getElementById('ficha-juego-titulo');
    const texto = d.getElementById('ficha-juego-texto');
    if (!titulo || !texto) { terminar({error: 'Falta la ficha lateral'}); return; }
    const leer = () => [titulo.textContent.trim(), texto.textContent.trim()];
    const boton = (juego) => d.querySelector('[data-juego="' + juego + '"]');
    const evento = (elemento, tipo, Tipo) =>
      elemento.dispatchEvent(new Tipo(tipo, {bubbles: false}));

    const resultado = {inicial: leer(), hover: {}, foco: {}, por_juego: {}};
    for (const juego of JUEGOS) {
      const b = boton(juego);
      if (!b) { terminar({error: 'Falta el boton ' + juego}); return; }
      evento(b, 'mouseenter', MouseEvent);
      resultado.hover[juego] = leer();
      resultado.por_juego[juego] = leer()[1];
      evento(b, 'mouseleave', MouseEvent);
    }
    evento(boton('stroop'), 'focus', FocusEvent);
    resultado.foco.stroop = leer();
    evento(boton('stroop'), 'blur', FocusEvent);

    boton('cajas').click();
    evento(boton('rastreo'), 'mouseenter', MouseEvent);
    const al_hover = leer()[1];
    evento(boton('rastreo'), 'mouseleave', MouseEvent);
    resultado.vuelve_a_seleccion = {al_hover, al_salir: leer()[1]};

    d.getElementById('btn-todos').click();
    const br = boton('rastreo');
    evento(br, 'mouseenter', MouseEvent);
    br.click();
    resultado.click_mantiene_ficha = leer();
    evento(br, 'mouseleave', MouseEvent);
    terminar(resultado);
  } catch (error) {
    terminar({error: String(error)});
  }
});
</script>"""


class Silencioso(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def translate_path(self, path):
        # index.html pide /static/app.js; el servidor de prueba sirve static/ en /.
        if path.startswith("/static/"):
            path = path[len("/static"):]
        return super().translate_path(path)


def levantar_servidor():
    servidor = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(Silencioso, directory=str(STATIC))
    )
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    return servidor, hilo


def leer_cliente() -> dict:
    nombre = f"__test_ficha_{os.getpid()}.html"
    archivo = STATIC / nombre
    archivo.write_text(
        HARNESS.replace("<script>", f"<script>const JUEGOS = {json.dumps(JUEGOS)};"),
        encoding="utf-8",
    )
    servidor, hilo = levantar_servidor()
    try:
        puerto = servidor.server_address[1]
        proceso = subprocess.run(
            [
                str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox",
                "--virtual-time-budget=6000", "--dump-dom",
                f"http://127.0.0.1:{puerto}/{nombre}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        salida = proceso.stdout
        inicio = salida.find('<pre id="resultado">')
        if inicio < 0:
            raise AssertionError(f"Chrome no devolvió el resultado: {salida[-500:]}")
        crudo = salida[inicio + len('<pre id="resultado">'):].split("</pre>", 1)[0]
        if crudo.strip() == "PENDIENTE":
            raise AssertionError("El navegador no terminó de cargar el cliente real")
        return json.loads(crudo)
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
        archivo.unlink(missing_ok=True)


def probar_ficha_lateral_con_conita_y_objetivo() -> None:
    datos = leer_cliente()
    assert "error" not in datos, datos.get("error")
    assert "Conita" in datos["inicial"][1], datos["inicial"]
    for juego, texto in datos["por_juego"].items():
        assert "Conita" in texto, (juego, texto)
        assert len(texto) > 40, (juego, texto)
    assert len(set(datos["por_juego"].values())) == len(JUEGOS), datos["por_juego"]
    assert datos["por_juego"]["rastreo"] != datos["por_juego"]["pajaros"]


def probar_hover_y_foco_cambian_la_ficha() -> None:
    datos = leer_cliente()
    assert "error" not in datos, datos.get("error")
    assert "hámster" in datos["hover"]["pajaros"][1].lower(), datos["hover"]["pajaros"]
    assert "color de la tinta" in datos["hover"]["stroop"][1], datos["hover"]["stroop"]
    assert "tinta" in datos["foco"]["stroop"][1], datos["foco"]["stroop"]
    assert datos["foco"]["stroop"][0].strip() == "STROOP", datos["foco"]["stroop"]


def probar_al_salir_vuelve_a_la_prueba_elegida() -> None:
    datos = leer_cliente()
    assert "error" not in datos, datos.get("error")
    assert "hámster" in datos["vuelve_a_seleccion"]["al_hover"].lower()
    assert "caja" in datos["vuelve_a_seleccion"]["al_salir"].lower(), datos["vuelve_a_seleccion"]


def probar_click_mantiene_la_ficha_visible() -> None:
    datos = leer_cliente()
    assert "error" not in datos, datos.get("error")
    assert datos["click_mantiene_ficha"][0].strip() == "RASTREO DE HÁMSTERS", (
        datos["click_mantiene_ficha"]
    )


def main() -> None:
    probar_ficha_lateral_con_conita_y_objetivo()
    probar_hover_y_foco_cambian_la_ficha()
    probar_al_salir_vuelve_a_la_prueba_elegida()
    probar_click_mantiene_la_ficha_visible()
    print("OK - Descripciones individuales con hover, foco y selección")


if __name__ == "__main__":
    main()
