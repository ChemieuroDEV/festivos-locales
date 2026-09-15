"""Orquesta la generacion del feed a partir de lo descargado en 'fuentes/'.

Llama, en orden, a los tres pasos que ya existen como scripts independientes:
  1. parse_es    -> festivos locales de las 17 comunidades espanolas
  2. cruzar_es   -> les pega los codigos postales de cada municipio
  3. parse_pt_it -> Portugal (feriado municipal) e Italia (patron de cada comune)
  4. build_feed  -> los reparte en ficheros por pais, ano y prefijo postal

Cada paso va aislado: si el de Espana revienta, Portugal e Italia se publican
igual, y verificar.py decidira despues si lo que ha quedado es publicable. Al
final escribe informe.md, que es lo que se lee para saber que hay dentro.
"""
import io, os, sys, json, traceback, datetime

# --- rutas dentro del repositorio (insertado por ajustar_rutas_repo.py) ------
import os as _os, datetime as _dt
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
FUENTES = _os.path.join(_RAIZ, "fuentes")
BUILD = _os.path.join(_RAIZ, "build")
DATA = _os.path.join(_RAIZ, "data")
_os.makedirs(BUILD, exist_ok=True)


def _anio():
    """Ano de trabajo.

    Con YEARS puesto, manda YEARS. Sin YEARS, NO se decide por el calendario:
    se mira que se ha podido descargar de verdad. Se prueba el ano siguiente y,
    si su fichero de Aragon no esta (es el que antes publica y siempre lleva el
    ano en el nombre), se trabaja con el ano en curso.

    Decidirlo por el calendario fue un error: en septiembre de 2026 el
    generador se puso a parsear 2027, que casi ninguna comunidad habia
    publicado, y el feed perdio provincias enteras."""
    env = (_os.environ.get("YEARS") or "").strip()
    if env:
        return int(env.replace(" ", "").split(",")[0])
    hoy = _dt.date.today()
    siguiente = hoy.year + 1
    marcador = _os.path.join(FUENTES, "ara_%d.csv" % siguiente)
    if _os.path.exists(marcador) and _os.path.getsize(marcador) > 5000:
        return siguiente
    return hoy.year


ANIO = _anio()
# ----------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PASOS = [
    ("Portugal: feriados municipales y codigos postales", "preparar_pt"),
    ("Espana: parsear las 17 comunidades", "parse_es"),
    ("Espana: cruzar con codigos postales", "cruzar_es"),
    ("Portugal e Italia", "parse_pt_it"),
    ("Repartir en ficheros por pais, ano y prefijo postal", "build_feed"),
]


def main():
    # Italia no se rehace en cada pasada: su origen es el infobox de 6.600
    # articulos de Wikipedia y cambia poquisimo. El fichero vive versionado en
    # datos_base/ y se refresca a mano con refrescar_italia.py.
    base = os.path.join(ROOT, "datos_base", "it_patroni_raw.json")
    destino = os.path.join(ROOT, "build", "it_patroni_raw.json")
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    if os.path.exists(base) and not os.path.exists(destino):
        import shutil
        shutil.copy(base, destino)

    fallos = []
    for titulo, modulo in PASOS:
        print("\n=== %s ===" % titulo, flush=True)
        try:
            mod = __import__(modulo)
            mod.main()
        except Exception:
            fallos.append((titulo, traceback.format_exc()))
            print("FALLO en '%s':\n%s" % (titulo, traceback.format_exc()), flush=True)

    escribir_informe(fallos)
    if fallos:
        print("\n%d paso(s) han fallado. verificar.py dira si lo generado se publica." % len(fallos))
    return 0


def leer(nombre):
    p = os.path.join(BUILD, nombre)
    return io.open(p, encoding="utf-8").read().strip() if os.path.exists(p) else ""


def escribir_informe(fallos):
    index = {}
    p = os.path.join(ROOT, "data", "index.json")
    if os.path.exists(p):
        index = json.load(io.open(p, encoding="utf-8"))

    out = ["# Informe de generación\n\n",
           "Generado el %s. Se regenera con los datos, así que siempre describe lo que hay publicado.\n\n"
           % index.get("generated", datetime.date.today().isoformat()),
           "| País | Municipios | Años publicados |\n| --- | --- | --- |\n"]
    for iso, st in sorted(index.get("countries", {}).items()):
        anios = ", ".join(str(y) for y, v in sorted(st["years"].items()) if v["entries"])
        out.append("| %s | %d | %s |\n" % (iso, st["municipalities"], anios or "—"))
    out.append("\nUn municipio que no aparece no es un municipio sin festivos: es un municipio del\n"
               "que no tenemos el dato. Business Central los distingue y lo dice en pantalla.\n")

    descarga = os.path.join(ROOT, "fuentes", "_descarga.json")
    if os.path.exists(descarga):
        d = json.load(io.open(descarga, encoding="utf-8"))
        out.append("\n## Descarga de fuentes\n\n%d bajadas correctamente" % len(d.get("ok", {})))
        if d.get("fallos"):
            out.append(", **%d con fallo**:\n\n" % len(d["fallos"]))
            for k, v in sorted(d["fallos"].items()):
                out.append("- `%s`: %s\n" % (k, v))
        else:
            out.append(", ninguna con fallo.\n")

    if fallos:
        out.append("\n## Pasos que han fallado\n\n")
        for titulo, tb in fallos:
            out.append("### %s\n\n```\n%s\n```\n" % (titulo, tb.strip()))

    for titulo, fichero in (("España — parseo de las 17 comunidades", "es_holidays_report.txt"),
                            ("España — cruce con códigos postales", "es_cruce_report.txt"),
                            ("Portugal e Italia", "pt_it_report.txt")):
        txt = leer(fichero)
        if txt:
            out.append("\n## %s\n\n```\n%s\n```\n" % (titulo, txt))

    io.open(os.path.join(ROOT, "informe.md"), "w", encoding="utf-8").write("".join(out))
    print("\ninforme.md escrito.")


if __name__ == "__main__":
    sys.exit(main())
