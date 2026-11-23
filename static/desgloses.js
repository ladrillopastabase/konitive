/* Desglose único de las 13 pruebas: solo tiempo, errores y puntuación. */
(function () {
  function numero(valor) {
    const n = Number(valor);
    if (!Number.isFinite(n) || n <= 0) return "0";
    return String(Math.round(n * 100) / 100);
  }

  // Segundos con dos decimales como máximo: 16.400000000000002 → "16.4", 1.256 → "1.26".
  globalThis.numero = numero;
  globalThis.textoDesglose = function textoDesglose(dato) {
    const d = dato || {};
    const tiempo = d.tiempo ?? d.tiempo_total;
    return `TIEMPO ${numero(tiempo)} s · ERRORES ${numero(d.errores)} · PUNTUACIÓN ${numero(d.puntuacion)}`;
  };
})();
