import random
from juego.rastreo import (
    CELDAS, HAMSTERS, LADOS, BoardManager, CatSpawner,
    HamsterManager, MovementSystem,
)
from juego.rastreo import (
    DifficultyManager, GameManager, NIVELES, RONDAS_RASTREO,
    ScoreManager, SelectionManager,
)

def probar_tablero_arranca_con_10_gatos_y_2_hamsters():
    tablero = BoardManager(random.Random(7))
    tablero.inicializar()
    assert len(tablero.instantanea()) == CELDAS == 12
    assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_desplazamientos_en_los_cuatro_lados():
    for lado in LADOS:
        tablero = BoardManager(random.Random(3))
        hamsters = HamsterManager(random.Random(3))
        tablero.inicializar()
        movimiento = MovementSystem(tablero, hamsters).aplicar(lado, 0)
        assert movimiento["lado"] == lado
        assert len(tablero.instantanea()) == 12
        assert sorted(tablero.instantanea()) == sorted(["G"] * 10 + list(HAMSTERS))

def probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas():
    rng = random.Random(11)
    tablero, hamsters = BoardManager(rng), HamsterManager(rng)
    tablero.inicializar()
    sistema, spawner = MovementSystem(tablero, hamsters), CatSpawner(rng)
    finales = set()
    for _ in range(200):
        lado, linea = spawner.siguiente()
        sistema.aplicar(lado, linea)
        pos = hamsters.posiciones(tablero)
        assert set(pos) == set(HAMSTERS)
        assert len(set(pos.values())) == 2
        finales.update(pos.values())
    assert finales <= set(range(12))

def probar_cuatro_niveles_con_parametros_independientes():
    assert tuple(NIVELES) == ("facil", "normal", "dificil", "experto")
    claves = {"observacion", "movimiento", "entradas", "intervalo", "animacion"}
    for parametros in NIVELES.values():
        assert set(parametros) == claves
    assert NIVELES["facil"]["entradas"] < NIVELES["experto"]["entradas"]
    assert NIVELES["facil"]["animacion"] > NIVELES["experto"]["animacion"]
    for parametros in NIVELES.values():
        assert parametros["entradas"] * parametros["intervalo"] <= parametros["movimiento"]

def probar_seleccion_exige_dos_casillas_distintas():
    seleccion = SelectionManager()
    assert seleccion.registrar(3) is True
    assert seleccion.registrar(3) is False
    assert seleccion.registrar(9) is True
    assert seleccion.registrar(1) is False
    assert seleccion.seleccionadas() == (3, 9)
    assert seleccion.completa() is True

def probar_puntaje_y_generador_son_deterministas():
    assert ScoreManager.evaluar((3, 9), {"h1": 3, "h2": 7}) == {
        "aciertos": 1, "errores": 1, "precision": 50.0,
    }
    a = GameManager.generar("normal", semilla=42)
    b = GameManager.generar("normal", semilla=42)
    assert a == b
    assert RONDAS_RASTREO == 6
    assert len(a["observacion"]) == 12
    assert len(a["movimientos"]) == NIVELES["normal"]["entradas"]
    assert set(a["final"]) == {"h1", "h2"}
    assert len(set(a["final"].values())) == 2
    assert all(m["lado"] in LADOS for m in a["movimientos"])

def main():
    probar_tablero_arranca_con_10_gatos_y_2_hamsters()
    probar_desplazamientos_en_los_cuatro_lados()
    probar_rastreo_no_duplica_ni_pierde_hamsters_tras_200_entradas()
    probar_cuatro_niveles_con_parametros_independientes()
    probar_seleccion_exige_dos_casillas_distintas()
    probar_puntaje_y_generador_son_deterministas()
    print("\nOK - Rastreo de hamsters correcto")

if __name__ == "__main__":
    main()
