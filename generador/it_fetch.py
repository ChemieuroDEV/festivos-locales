"""Localiza el articulo de it.wikipedia de CADA uno de los 7.904 comuni y cachea
su infobox.

De donde sale el titulo, por orden:
  1. wikidata_it_sitelinks.csv  (6.675 comuni, el sitelink de Wikidata)
  2. it_patroni_raw.json        (titulo ya usado en la primera pasada)
  3. candidatos por nombre      ("Nome", "Nome (Italia)", "Nome (Provincia)"...)

Un candidato solo se acepta si el infobox del articulo es de un comune
(Grado amministrativo = 3) y coinciden nombre y provincia con comuni_it.json.
Asi no se cuela el articulo del dialecto "bergamasco" por el comune Bergamasco.

Salida: it_titulos.json {codice: titulo} + el cache de it_wiki_cache.py.
Es idempotente: lo ya descargado no se vuelve a pedir.
"""
import csv, io, json, os, re, sys, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import it_wiki_cache as W
from it_festivi import infobox_params, clean_value, norm_key

comuni = json.load(io.open(os.path.join(HERE, "comuni_it.json"), encoding="utf-8"))
raw = json.load(io.open(os.path.join(HERE, "it_patroni_raw.json"), encoding="utf-8"))

sitelinks = {}
for r in csv.DictReader(io.open(os.path.join(HERE, "wikidata_it_sitelinks.csv"), encoding="utf-8")):
    art = r.get("art") or ""
    if "/wiki/" in art:
        sitelinks[r["codice"]] = urllib.parse.unquote(art.split("/wiki/", 1)[1]).replace("_", " ")

TIT = os.path.join(HERE, "it_titulos.json")
titulos = json.load(io.open(TIT, encoding="utf-8")) if os.path.exists(TIT) else {}


def alts(s):
    """Variantes normalizadas de un topónimo. Los nombres bilingues vienen con
    barra ("Bolzano/Bozen", "Valle d'Aosta/Vallée d'Aoste") y cada fuente elige
    una mitad distinta, asi que se comparan por conjuntos."""
    s = clean_value(s or "")
    out = {norm_key(s)}
    for part in re.split(r"[/–-]| - ", s):
        k = norm_key(part)
        if k:
            out.add(k)
    out.discard("")
    return out


def es_el_comune(txt, c, titulo=""):
    """El infobox describe a ESTE comune?"""
    p = infobox_params(txt)
    if not p:
        return False
    # grado 3 = comune. Wikipedia pone 4 en unos cuantos (fusionados, o
    # simplemente mal), y son igualmente el articulo de esa localidad.
    if p.get("grado amministrativo", "").strip() not in ("3", "4", ""):
        return False
    # muchos articulos dejan |Nome vacio y se apoyan en el titulo de la pagina
    nom = alts(p.get("nome", "")) or alts(re.sub(r"\s*\(.*\)$", "", titulo))
    if not (nom & alts(c["nome"])):
        return False
    sitio = alts(p.get("divisione amm grado 2", "")) | alts(p.get("divisione amm grado 1", ""))
    mio = alts(c["provincia"]["nome"]) | alts(c["regione"]["nome"])
    if sitio <= {"NO"}:                       # comuni de region sin provincia
        return True
    return bool(sitio & mio)


def candidatos(c):
    n = c["nome"]
    out = [n, n + " (Italia)", n + " (comune)", n + " (comune italiano)"]
    for campo in ("provincia", "regione"):
        v = c[campo]["nome"]
        for parte in [v] + v.split("/"):      # "Trentino-Alto Adige/Südtirol"
            t = "%s (%s)" % (n, parte.strip())
            if t not in out:
                out.append(t)
    return out


# Los 7 comuni cuyo articulo existe pero con otro nombre: renombrados
# (Pettoranello "di" Molise), fusionados (Campospinoso Albaredo) o pasados de
# provincia en 2021 (Montecopiolo y Sassofeltrio, de Pesaro a Rimini). Se fijan
# a mano porque la comprobacion automatica nombre+provincia no puede aceptarlos
# sin abrir la puerta a emparejamientos falsos.
ALIAS = {
    "018026": "Campospinoso",                     # Campospinoso Albaredo
    "021045": "Magrè sulla Strada del Vino",
    "083053": "Moio Alcantara",                   # articulo: Mojo Alcantara
    "021053": "Montagna (Italia)",                # Montagna sulla Strada del Vino
    "041033": "Montecopiolo",                     # hoy provincia de Rimini
    "094034": "Pettoranello del Molise",          # articulo: Pettoranello di Molise
    "041060": "Sassofeltrio",                     # hoy provincia de Rimini
}

# --- ronda 0: sitelink de Wikidata y titulo de la primera pasada ------------
ronda0 = {}
for c in comuni:
    cod = c["codice"]
    if cod in titulos:
        continue
    t = sitelinks.get(cod) or (raw.get(cod) or {}).get("title")
    if t:
        ronda0[cod] = t
print("ronda 0 (sitelinks/raw):", len(ronda0))
W.ensure(list(ronda0.values()))
cache = W.load()

by_cod = {c["codice"]: c for c in comuni}
sin = []
for cod, t in ronda0.items():
    e = cache.get(t) or {}
    if e.get("txt") and es_el_comune(e["txt"], by_cod[cod], t):
        titulos[cod] = t
    elif e.get("txt"):
        # el articulo existe pero el infobox no cuadra: se guarda igual, porque
        # el nombre del infobox puede venir en bilingue; se reintenta por nombre
        titulos[cod] = t
    else:
        sin.append(cod)
json.dump(titulos, io.open(TIT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("resueltos tras ronda 0:", len(titulos), "| sin articulo:", len(sin))

# --- ronda 1: comuni sin titulo conocido, por candidatos --------------------
pend = [c for c in comuni if c["codice"] not in titulos]
print("comuni sin titulo:", len(pend))
for nivel in range(2):
    if not pend:
        break
    cands = []
    for c in pend:
        cs = candidatos(c)
        cands += ([cs[0]] if nivel == 0 else cs[1:])
    W.ensure(cands)
    cache = W.load()
    resto = []
    for c in pend:
        cs = candidatos(c)
        elegido = None
        for t in ([cs[0]] if nivel == 0 else cs[1:]):
            e = cache.get(t) or {}
            if e.get("txt") and es_el_comune(e["txt"], c, t):
                elegido = t
                break
        if elegido:
            titulos[c["codice"]] = elegido
        else:
            resto.append(c)
    pend = resto
    json.dump(titulos, io.open(TIT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("nivel", nivel, "-> resueltos", len(titulos), "| pendientes", len(pend))

for cod, t in ALIAS.items():
    e = (W.load().get(t) or {})
    if cod not in titulos and e.get("txt"):
        titulos[cod] = t
pend = [c for c in pend if c["codice"] not in titulos]
json.dump(titulos, io.open(TIT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("tras alias manuales -> resueltos", len(titulos))

print("SIN LOCALIZAR:", len(pend))
for c in pend[:40]:
    print("   ", c["codice"], c["nome"], "(%s)" % c["provincia"]["nome"])
io.open(os.path.join(HERE, "it_sin_articulo.txt"), "w", encoding="utf-8").write(
    "\n".join("%s\t%s\t%s" % (c["codice"], c["nome"], c["provincia"]["nome"]) for c in pend))
