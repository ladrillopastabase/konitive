/* Desglose único de las 13 pruebas: solo tiempo, errores y Brain Age. */
(function () {
  function numero(valor) {
    const n = Number(valor);
    if (!Number.isFinite(n) || n <= 0) return "0";
    return String(Math.round(n * 100) / 100);
  }

  globalThis.textoDesglose = function textoDesglose(dato) {
    const d = dato || {};
    const tiempo = d.tiempo ?? d.tiempo_total;
    return `TIEMPO ${numero(tiempo)} s · ERRORES ${numero(d.errores)} · BRAIN AGE ${numero(d.brain_age)}`;
  };
})();
