"""Decide si el feed recien generado es publicable.

La pregunta que responde es una sola: ¿lo nuevo es razonable comparado con lo
que ya esta publicado? Si una comunidad cambia el formato de su fichero y su
parser devuelve vacio, el feed saldria con municipios de menos y, publicado,
convertiria en "sin datos" localidades que antes si teniamos. Business Central
conserva lo ultimo que descargo, asi que un feed viejo hace menos dano que un
feed roto.

Sale con codigo != 0 (y el workflow se para antes del commit) si:

  - DESAPARECE algun fichero que ya estaba publicado. Esta es la comprobacion
    que de verdad importa, y la que faltaba: en la primera ejecucion real, el
    generador se puso a trabajar sobre un ano que casi ninguna comunidad habia
    publicado todavia, varias fuentes salieron vacias y se borraron Alava,
    Guipuzcoa, Vizcaya y Pontevedra enteras. La perdida era del 8 % de los
    municipios, por debajo del umbral de entonces, asi que se publico sin que
    saltara nada.
  - un pais se queda sin ningun municipio;
  - un pais pierde mas del 10 % de sus municipios;
  - falta index.json o esta mal formado.

La primera generacion, sin nada publicado con que comparar, pasa siempre.
"""
import io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UMBRAL = 0.10


def index_actual():
    p = os.path.join(ROOT, "data", "index.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception as e:
        print("index.json ilegible:", e)
        return None


def git(*args):
    try:
        out = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, timeout=120)
        if out.returncode != 0:
            return None
        return out.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None


def index_publicado():
    txt = git("show", "HEAD:data/index.json")
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def ficheros_publicados():
    """Los ficheros de data/ tal como estan en el ultimo commit."""
    txt = git("ls-tree", "-r", "--name-only", "HEAD", "data")
    if txt is None:
        return None
    return {l.strip() for l in txt.splitlines() if l.strip().endswith(".json")}


def ficheros_ahora():
    base = os.path.join(ROOT, "data")
    out = set()
    for r, _, fs in os.walk(base):
        for f in fs:
            if f.endswith(".json"):
                rel = os.path.relpath(os.path.join(r, f), ROOT)
                out.add(rel.replace(os.sep, "/"))
    return out


def main():
    nuevo = index_actual()
    if not nuevo or not nuevo.get("countries"):
        print("ERROR: el feed generado no tiene paises. No se publica.")
        return 1

    for iso, st in sorted(nuevo["countries"].items()):
        print("%s: %d municipios" % (iso, st["municipalities"]))

    antes_ficheros = ficheros_publicados()
    if antes_ficheros is None:
        print("\nNo hay feed publicado con el que comparar: se publica.")
        return 0

    problemas = []

    # 1. ficheros que desaparecen
    desaparecidos = sorted(antes_ficheros - ficheros_ahora())
    if desaparecidos:
        problemas.append("desaparecen %d fichero(s) que ya estaban publicados: %s"
                         % (len(desaparecidos), ", ".join(desaparecidos[:12])))

    # 2. municipios por pais
    viejo = index_publicado() or {}
    for iso, st in viejo.get("countries", {}).items():
        antes = st.get("municipalities", 0)
        ahora = nuevo["countries"].get(iso, {}).get("municipalities", 0)
        if antes and not ahora:
            problemas.append("%s ha desaparecido entero (antes %d municipios)" % (iso, antes))
        elif antes and ahora < antes * (1 - UMBRAL):
            problemas.append("%s pierde el %.1f %% de sus municipios (%d -> %d)"
                             % (iso, 100.0 * (antes - ahora) / antes, antes, ahora))
        elif ahora > antes:
            print("%s gana %d municipios." % (iso, ahora - antes))

    if problemas:
        print("\nNO SE PUBLICA. Alguna fuente ha debido de fallar o de cambiar de formato:")
        for p in problemas:
            print("  -", p)
        print("\nRevisa 'fuentes/_descarga.json' y el informe de esta ejecucion.")
        return 1

    nuevos = sorted(ficheros_ahora() - antes_ficheros)
    if nuevos:
        print("\nSe publican %d fichero(s) nuevos: %s" % (len(nuevos), ", ".join(nuevos[:8])))
    print("\nEl feed nuevo es consistente con el publicado: se publica.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
