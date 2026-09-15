"""Monta el feed que lee Business Central a partir de los ficheros por pais.

Entrada : pt_holidays.json, it_holidays.json, es_holidays_feed.json (si existe)
Salida  : data/<ISO>/<anio>/<shard>.json  +  data/index.json

El shard son los DOS PRIMEROS DIGITOS del codigo postal. Un municipio aparece
en todos los shards que le tocan por sus codigos postales (Madrid tiene 280xx,
asi que solo el 28; pero hay municipios a caballo de dos prefijos).

Los codigos postales de `pc` se comparan en BC POR PREFIJO: en Portugal el
codigo del feed es de 4 digitos ("2430") y el de BC viene completo
("2430-123"); en Espana e Italia coinciden los 5 digitos y el prefijo equivale
a la igualdad.
"""
import io, json, os, collections, datetime, shutil

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
OUT = DATA
YEARS = [2026, 2027, 2028]


def load(name):
    p = os.path.join(BUILD, name)
    if not os.path.exists(p):
        print("aviso: falta", name)
        return []
    return json.load(io.open(p, encoding="utf-8"))


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    countries = {"PT": load("pt_holidays.json"),
                 "IT": load("it_holidays.json"),
                 "ES": load("es_holidays_feed.json")}

    index = {"generated": datetime.date.today().isoformat(), "countries": {}}
    for iso, municipios in countries.items():
        if not municipios:
            continue
        stats = {"municipalities": len(municipios), "years": {}}
        for year in YEARS:
            shards = collections.defaultdict(list)
            for m in municipios:
                hol = [{"date": h["date"], "name": h["name"]}
                       for h in m["holidays"] if h.get("year") == year]
                if not hol:
                    continue
                entry = {"name": m["name"], "key": m["key"], "pc": m["pc"], "holidays": hol}
                if m.get("sub"):
                    entry["sub"] = m["sub"]
                destinos = {pc[:2] for pc in m["pc"] if len(pc) >= 2 and pc[:2].isdigit()}
                if not destinos:
                    # Sin codigo postal no hay shard posible: el municipio solo
                    # se podra emparejar por nombre, y para eso tiene que estar
                    # en algun fichero. Se deja en el shard "00".
                    destinos = {"00"}
                for d in destinos:
                    shards[d].append(entry)

            ydir = os.path.join(OUT, iso, str(year))
            os.makedirs(ydir, exist_ok=True)
            total = 0
            for shard, entries in sorted(shards.items()):
                doc = {"country": iso, "year": year, "shard": shard,
                       "generated": index["generated"], "municipalities": entries}
                json.dump(doc, io.open(os.path.join(ydir, shard + ".json"), "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                total += len(entries)
            stats["years"][year] = {"shards": len(shards), "entries": total}
        index["countries"][iso] = stats

    json.dump(index, io.open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # informe
    print(json.dumps(index, ensure_ascii=False, indent=1))
    n = sum(len(files) for _, _, files in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
    print("ficheros:", n, "tamano total: %.1f KB" % (size / 1024))

    # comprobaciones concretas
    for iso, year, shard, needle in (("IT", 2026, "56", "Pisa"),
                                     ("PT", 2026, "24", "Marinha Grande"),
                                     ("ES", 2026, "30", "Murcia")):
        p = os.path.join(OUT, iso, str(year), shard + ".json")
        if not os.path.exists(p):
            print("CHECK", iso, shard, "-> NO EXISTE EL SHARD")
            continue
        doc = json.load(io.open(p, encoding="utf-8"))
        hit = [m for m in doc["municipalities"] if m["name"] == needle]
        print("CHECK", iso, shard, needle, "->", hit[0]["holidays"] if hit else "NO ESTA",
              "| municipios en el shard:", len(doc["municipalities"]))


if __name__ == "__main__":
    main()
