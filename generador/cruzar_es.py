"""Cruza los festivos locales de Espana con los codigos postales de cada
municipio y deja el fichero con la forma que consume el feed.

La tabla de codigos postales es la de GeoNames (ES.zip), que trae para cada
codigo postal el municipio, su codigo INE y la provincia. Se probo antes el
dataset de ds-codigos-postales y estaba incompleto (una sola fila en media
docena de provincias enteras), asi que Barcelona o Ibi no cruzaban.

Dos vias de cruce, en este orden:
  1. Por codigo INE, cuando la comunidad lo publica (Cataluna, Aragon, Madrid,
     Galicia y Castilla y Leon). Es exacto.
  2. Por nombre normalizado DENTRO de la provincia, para las otras doce. La
     provincia sale del INE si lo hay y, si no, del nombre que trae la fuente.

Un municipio que no cruza NO se inventa: se queda fuera y sale en el informe.
Vale mas que Business Central diga "no lo se" a que diga "laborable" por un
cruce dudoso.
"""
import io, csv, json, os, re, zipfile, collections, unicodedata

# --- rutas dentro del repositorio (insertado por ajustar_rutas_repo.py) ------
import os as _os, datetime as _dt
_RAIZ = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
FUENTES = _os.path.join(_RAIZ, "fuentes")
BUILD = _os.path.join(_RAIZ, "build")
DATA = _os.path.join(_RAIZ, "data")
_os.makedirs(BUILD, exist_ok=True)


def _anio():
    """Ano de trabajo: el de YEARS si viene, si no el actual (o el siguiente a
    partir de septiembre, que es cuando las comunidades ya han publicado)."""
    env = (_os.environ.get("YEARS") or "").strip()
    if env:
        return int(env.replace(" ", "").split(",")[0])
    hoy = _dt.date.today()
    return hoy.year + (1 if hoy.month >= 9 else 0)


ANIO = _anio()
# ----------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    out, sep = [], True
    for ch in s:
        if ch.isascii() and (ch.isalpha() or ch.isdigit()):
            out.append(ch); sep = False
        elif not sep:
            out.append(" "); sep = True
    return "".join(out).strip()


def variantes(nombre):
    """El INE escribe 'Molsosa, La' y la gente escribe 'La Molsosa'; en Galicia,
    Euskadi y Cataluna conviven las dos lenguas separadas por '/'. Se generan
    todas las formas para que el cruce no dependa de cual eligio cada fuente."""
    v = set()
    for parte in re.split(r"\s*/\s*", (nombre or "").strip()):
        parte = parte.strip()
        if not parte:
            continue
        v.add(norm(parte))
        v.add(norm(re.sub(r"\s*\(.*?\)\s*", " ", parte)))
        m = re.match(r"^(.*),\s*(el|la|los|las|l|els|les|o|a|os|as|lo|es|sa|ses)$", parte, re.I)
        if m:
            v.add(norm(m.group(2) + " " + m.group(1)))
        m2 = re.match(r"^(el|la|los|las|l|els|les|o|a|os|as|lo|es|sa|ses)\s+(.*)$", parte, re.I)
        if m2:
            v.add(norm(m2.group(2) + " " + m2.group(1)))
        # "Vitoria-Gasteiz" -> tambien "Vitoria" y "Gasteiz"
        if "-" in parte and len(parte.split("-")) == 2:
            for t in parte.split("-"):
                if len(t.strip()) > 3:
                    v.add(norm(t))
    return {x for x in v if x}


PROV = {
    "ALAVA": "01", "ARABA ALAVA": "01", "ARABA": "01", "ALAVA ARABA": "01", "ALBACETE": "02",
    "ALICANTE": "03", "ALACANT": "03", "ALMERIA": "04", "AVILA": "05", "BADAJOZ": "06",
    "BALEARES": "07", "ILLES BALEARS": "07", "ISLAS BALEARES": "07", "BARCELONA": "08",
    "BURGOS": "09", "CACERES": "10", "CADIZ": "11", "CASTELLON": "12", "CASTELLO": "12",
    "CIUDAD REAL": "13", "CORDOBA": "14", "A CORUNA": "15", "LA CORUNA": "15", "CORUNA": "15",
    "CUENCA": "16", "GIRONA": "17", "GERONA": "17", "GRANADA": "18", "GUADALAJARA": "19",
    "GUIPUZCOA": "20", "GIPUZKOA": "20", "HUELVA": "21", "HUESCA": "22", "JAEN": "23",
    "LEON": "24", "LLEIDA": "25", "LERIDA": "25", "LA RIOJA": "26", "RIOJA": "26", "LUGO": "27",
    "MADRID": "28", "MALAGA": "29", "MURCIA": "30", "REGION DE MURCIA": "30", "NAVARRA": "31",
    "NAFARROA": "31", "OURENSE": "32", "ORENSE": "32", "ASTURIAS": "33",
    "PRINCIPADO DE ASTURIAS": "33", "PALENCIA": "34", "LAS PALMAS": "35", "PONTEVEDRA": "36",
    "SALAMANCA": "37", "SANTA CRUZ DE TENERIFE": "38", "TENERIFE": "38", "CANTABRIA": "39",
    "SEGOVIA": "40", "SEVILLA": "41", "SORIA": "42", "TARRAGONA": "43", "TERUEL": "44",
    "TOLEDO": "45", "VALENCIA": "46", "VALLADOLID": "47", "VIZCAYA": "48", "BIZKAIA": "48",
    "ZAMORA": "49", "ZARAGOZA": "50", "CEUTA": "51", "MELILLA": "52",
    "MALLORCA": "07", "MENORCA": "07", "EIVISSA": "07", "IBIZA": "07", "FORMENTERA": "07",
}


_MINUS = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E", "A", "DA", "DAS", "DO", "DOS",
          "I", "EN", "SE", "AL", "D", "L", "SA", "ES", "SES", "DE LA"}


def presentable(nombre):
    """Los boletines dan el municipio TODO EN MAYUSCULAS y eso acaba en la
    pantalla del usuario. Si no hay ninguna minuscula, se pasa a capitalizado
    dejando en minuscula las particulas."""
    n = (nombre or "").strip()
    if not n or any(c.islower() for c in n):
        return n
    partes = []
    for i, p in enumerate(n.split()):
        partes.append(p.capitalize() if (i == 0 or p not in _MINUS) else p.lower())
    return " ".join(partes)


def geonames():
    """Devuelve (por_ine, por_nombre_provincia, nombre_oficial_por_ine)."""
    por_ine = collections.defaultdict(set)
    por_nom = collections.defaultdict(set)
    nombre_ine = {}
    nombre_cp = {}
    z = zipfile.ZipFile(os.path.join(FUENTES, "geo_ES.zip"))
    for line in z.read("ES.txt").decode("utf-8", errors="replace").splitlines():
        f = line.split("\t")
        if len(f) < 9:
            continue
        cp, lugar, prov, muni, ine = f[1], f[2], f[5], f[7], f[8]
        if len(cp) != 5:
            continue
        if ine and len(ine) == 5:
            por_ine[ine].add(cp)
            nombre_ine.setdefault(ine, muni or lugar)
        if muni:
            nombre_cp.setdefault(cp, muni)
        p = cp[:2]
        # el nombre del municipio y el del nucleo: los dos sirven para cruzar
        for nombre in (muni, lugar):
            for v in variantes(nombre):
                por_nom[(p, v)].add(cp)
    return por_ine, por_nom, nombre_ine, nombre_cp


def main():
    rows = json.load(io.open(os.path.join(BUILD, "es_holidays.json"), encoding="utf-8"))
    por_ine, por_nom, nombre_ine, nombre_cp = geonames()

    grupos = collections.defaultdict(lambda: {"name": None, "prov": "", "ine": "",
                                              "fuente": None, "hol": []})
    sin_prov = collections.Counter()
    for r in rows:
        ine = r.get("ine") or ""
        prov = ine[:2] if len(ine) == 5 else ""
        if not prov:
            prov = PROV.get(norm(r.get("provincia", "")), "")
            if not prov:
                sin_prov[(r.get("fuente", "?"), r.get("provincia") or "(vacia)")] += 1
        key = (ine or (prov + "|" + norm(r["municipio"])))
        g = grupos[key]
        g["name"] = g["name"] or r["municipio"]
        g["prov"], g["ine"], g["fuente"] = prov, ine, r["fuente"]
        g["hol"].append({"year": int(r["fecha"][:4]), "date": r["fecha"],
                         "name": r["nombre"] or "Fiesta local"})

    out, no_cruza = [], []
    via = collections.Counter()
    fallos = collections.Counter()
    for key, g in grupos.items():
        cps, como = set(), ""
        if g["ine"] and g["ine"] in por_ine:
            cps, como = por_ine[g["ine"]], "ine"
        if not cps:
            provincias = [g["prov"]] if g["prov"] else list({k[0] for k in por_nom})
            for v in variantes(g["name"]):
                for p in provincias:
                    cps |= por_nom.get((p, v), set())
                if cps and g["prov"]:
                    break
            como = "nombre" if cps else ""
        if not cps:
            no_cruza.append((g["fuente"], g["prov"], g["name"]))
            fallos[g["fuente"]] += 1
            continue
        via[como] += 1
        vistos, hol = set(), []
        for h in sorted(g["hol"], key=lambda x: x["date"]):
            if h["date"] not in vistos:
                vistos.add(h["date"]); hol.append(h)
        # Nombre presentable. Con INE se usa el oficial de GeoNames. Sin INE se
        # usa el de la FUENTE, no el del codigo postal mas bajo: ese codigo
        # puede pertenecer a otro municipio cuando el cruce fue por el nombre de
        # un nucleo, y entonces los festivos acabarian firmados por el municipio
        # equivocado. Solo se arregla el TODO EN MAYUSCULAS de los boletines.
        nombre = nombre_ine.get(g["ine"]) or presentable(g["name"])
        out.append({"key": norm(nombre)[:50], "name": nombre, "sub": "",
                    "pc": sorted(cps), "holidays": hol})

    # Dos filas del mismo municipio (por ejemplo una con INE y otra sin el) se
    # fusionan si apuntan a los mismos codigos postales: son el mismo sitio.
    final, por_clave = [], {}
    for m in out:
        k = (m["key"], tuple(m["pc"]))
        if k in por_clave:
            fechas = {h["date"] for h in por_clave[k]["holidays"]}
            por_clave[k]["holidays"] += [h for h in m["holidays"] if h["date"] not in fechas]
            por_clave[k]["holidays"].sort(key=lambda h: h["date"])
        else:
            por_clave[k] = m
            final.append(m)

    json.dump(final, io.open(os.path.join(BUILD, "es_holidays_feed.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    rep = io.open(os.path.join(BUILD, "es_cruce_report.txt"), "w", encoding="utf-8")
    rep.write("municipios con festivos: %d\n" % len(grupos))
    rep.write("cruzados con codigo postal: %d (%s)\n" % (len(final), dict(via)))
    rep.write("sin cruzar: %d\n" % len(no_cruza))
    rep.write("fallos por fuente: %s\n" % dict(fallos.most_common()))
    rep.write("filas sin provincia deducible: %s\n" % dict(sin_prov.most_common(8)))
    rep.write("\nprimeros 30 sin cruzar:\n")
    for f, p, n in no_cruza[:30]:
        rep.write("  %-4s %-3s %s\n" % (f, p or "--", n))
    c = collections.Counter(m["key"] for m in final)
    dup = [k for k, n in c.items() if n > 1]
    rep.write("\nclaves repetidas: %d  %s\n" % (len(dup), dup[:12]))
    rep.write("\n")
    for nombre in ("Murcia", "Zaragoza", "Barcelona", "Madrid", "Sevilla", "Bilbao", "Pamplona",
                   "Alcantarilla", "Molina de Segura", "Ibi", "Arganda del Rey", "Rubi",
                   "Terrassa", "Jerez de la Frontera", "Vitoria-Gasteiz", "Santander"):
        hit = [m for m in final if norm(m["name"]) == norm(nombre)]
        rep.write("CHECK %-22s -> %s\n" % (nombre, [(m["pc"][:2], [h["date"] for h in m["holidays"]]) for m in hit][:2] or "NO CRUZA"))
    rep.close()
    print(io.open(os.path.join(BUILD, "es_cruce_report.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
