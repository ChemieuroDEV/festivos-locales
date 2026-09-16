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
OUT = DATA
YEARS = [2026, 2027, 2028]


def load(name):
    p = os.path.join(BUILD, name)
    if not os.path.exists(p):
        print("aviso: falta", name)
        return []
    return json.load(io.open(p, encoding="utf-8"))


def main():
    # NO se borra data/ entera: solo se reescribe lo que se genera en esta
    # pasada. Si se esta generando 2027, el 2026 que ya estaba publicado tiene
    # que seguir ahi. Borrarlo todo dejo sin festivos a cuatro provincias en la
    # primera ejecucion real del workflow.
    os.makedirs(OUT, exist_ok=True)

    countries = {"PT": load("pt_holidays.json"),
                 "IT": load("it_holidays.json"),
                 "ES": load("es_holidays_feed.json"),
                 # Alemania: Maria Himmelfahrt en los municipios catolicos de
                 # Baviera y en todo el Sarre, y Fronleichnam en los municipios
                 # catolicos de Sajonia y Turingia. Solo van los municipios que
                 # TIENEN alguno: para el resto, lo del Land ya lo da la API.
                 "DE": load("de_holidays.json")}

    # El indice se reconstruye contando lo que hay en disco al final, no solo
    # lo generado ahora, para que refleje tambien los anos que se conservan.
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
                # Codigo INE y nombres alternativos. Los alternativos son los
                # que permiten que una carga a "Xixona" encuentre el municipio
                # publicado como "Jijona": los boletines usan una lengua y la
                # carga puede venir con la otra.
                if m.get("ine"):
                    entry["ine"] = m["ine"]
                if m.get("alt"):
                    entry["alt"] = sorted(set(m["alt"]) - {m["key"]})
                destinos = {pc[:2] for pc in m["pc"] if len(pc) >= 2 and pc[:2].isdigit()}
                if not destinos:
                    # Sin codigo postal no hay shard posible: el municipio solo
                    # se podra emparejar por nombre, y para eso tiene que estar
                    # en algun fichero. Se deja en el shard "00".
                    destinos = {"00"}
                for d in destinos:
                    shards[d].append(entry)

            if not shards:
                # Ese pais no tiene datos de ese ano en esta pasada: no se toca
                # lo que hubiera publicado, que es mejor que nada.
                continue

            ydir = os.path.join(OUT, iso, str(year))
            if os.path.exists(ydir):
                shutil.rmtree(ydir)
            os.makedirs(ydir, exist_ok=True)
            total = 0
            for shard, entries in sorted(shards.items()):
                doc = {"country": iso, "year": year, "shard": shard,
                       "generated": index["generated"], "municipalities": entries}
                json.dump(doc, io.open(os.path.join(ydir, shard + ".json"), "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
                total += len(entries)

            # Indice de nombres: segunda via para cuando el codigo postal de la
            # carga no corresponde a la ciudad. Solo nombres UNICOS en el pais:
            # con dos municipios homonimos no hay forma de decidir y no se
            # arriesga. Business Central lo pide solo si falla el codigo postal.
            en_shard = collections.defaultdict(set)
            for shard, entries in shards.items():
                for e in entries:
                    en_shard[e["key"]].add(shard)
                    for a in e.get("alt", []):
                        en_shard[a].add(shard)
            nombres = {k: list(v)[0] for k, v in en_shard.items() if len(v) == 1}
            json.dump({"country": iso, "year": year, "generated": index["generated"],
                       "names": nombres},
                      io.open(os.path.join(ydir, "_names.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))

            stats["years"][year] = {"shards": len(shards), "entries": total,
                                    "names": len(nombres)}
        index["countries"][iso] = stats

    # --- festivos nacionales de los paises que OpenHolidays no cubre --------
    # Comprobado el 15/09/2026: la API devuelve vacio para el Reino Unido,
    # Finlandia, Dinamarca, Noruega y Grecia; ni Navidad. Son 343 clientes
    # britanicos y 36 finlandeses cuyas entregas no se comprobaban en absoluto.
    con_country = []
    p_paises = os.path.join(BUILD, "paises_sin_cobertura.json")
    if os.path.exists(p_paises):
        datos = json.load(io.open(p_paises, encoding="utf-8"))
        for iso, info in sorted(datos.items()):
            for year, fest in sorted(info.get("years", {}).items()):
                if not fest:
                    continue
                ydir = os.path.join(OUT, iso, str(year))
                os.makedirs(ydir, exist_ok=True)
                doc = {"country": iso, "year": int(year),
                       "generated": index["generated"], "holidays": fest}
                json.dump(doc, io.open(os.path.join(ydir, "_country.json"), "w", encoding="utf-8"),
                          ensure_ascii=False, separators=(",", ":"))
            if info.get("years"):
                con_country.append(iso)
        index["countryFeed"] = con_country
        print("festivos nacionales publicados para:", ", ".join(con_country))

    # --- metadatos por pais -------------------------------------------------
    try:
        import paises as _paises
        index["countries_meta"] = _paises.construir(
            set(index["countries"].keys()), con_country)
        json.dump({"generated": index["generated"], "countries": index["countries_meta"]},
                  io.open(os.path.join(OUT, "_countries.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("metadatos de %d paises" % len(index["countries_meta"]))
    except Exception as e:
        print("aviso: no se han podido escribir los metadatos de paises:", e)

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
