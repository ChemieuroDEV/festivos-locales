"""Decide si el feed recien generado es publicable.

La pregunta que responde es una sola: ¿el resultado nuevo es razonable
comparado con el que ya esta publicado? Si una comunidad cambia el formato de
su CSV y su parser devuelve vacio, el feed nuevo saldria con miles de
municipios menos y, publicado, convertiria en "sin datos" localidades que antes
si teniamos. Business Central conserva lo ultimo que descargo, asi que un feed
viejo hace menos dano que un feed roto.

Sale con codigo != 0 (y el workflow se para antes del commit) si:
  - el feed nuevo no tiene ningun municipio de un pais que antes si tenia;
  - un pais pierde mas del 20 % de sus municipios;
  - falta el fichero index.json o esta mal formado.

La primera generacion, sin nada publicado con que comparar, pasa siempre.
"""
import io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UMBRAL = 0.20


def index_actual():
    p = os.path.join(ROOT, "data", "index.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        print("index.json ilegible:", e)
        return None


def index_publicado():
    """El index.json tal como esta en el ultimo commit, sin tocar el disco."""
    try:
        out = subprocess.run(["git", "show", "HEAD:data/index.json"], cwd=ROOT,
                             capture_output=True, timeout=60)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout.decode("utf-8"))
    except Exception:
        return None


def main():
    nuevo = index_actual()
    if not nuevo or not nuevo.get("countries"):
        print("ERROR: el feed generado no tiene paises. No se publica.")
        return 1

    for iso, st in sorted(nuevo["countries"].items()):
        print("%s: %d municipios" % (iso, st["municipalities"]))

    viejo = index_publicado()
    if not viejo:
        print("\nNo hay feed publicado con el que comparar: se publica.")
        return 0

    problemas = []
    for iso, st in viejo.get("countries", {}).items():
        antes = st.get("municipalities", 0)
        ahora = nuevo["countries"].get(iso, {}).get("municipalities", 0)
        if antes and not ahora:
            problemas.append("%s ha desaparecido entero (antes %d municipios)" % (iso, antes))
        elif antes and ahora < antes * (1 - UMBRAL):
            problemas.append("%s pierde el %.0f %% de sus municipios (%d -> %d)"
                             % (iso, 100.0 * (antes - ahora) / antes, antes, ahora))
        elif ahora > antes:
            print("%s gana %d municipios." % (iso, ahora - antes))

    if problemas:
        print("\nNO SE PUBLICA. Alguna fuente ha debido de cambiar de formato:")
        for p in problemas:
            print("  -", p)
        print("\nRevisa 'fuentes/_descarga.json' y el parser de esa comunidad.")
        return 1

    print("\nEl feed nuevo es consistente con el publicado: se publica.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
