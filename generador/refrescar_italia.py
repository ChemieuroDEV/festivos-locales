"""Lee de it.wikipedia el infobox de cada comune (parametros Patrono y Festivo).

Entrada: wikidata_it_sitelinks.csv (codice ISTAT, nombre, URL del articulo).
Salida:  it_patroni_raw.json  {codice: {"nome":..., "title":..., "patrono":..., "festivo":...}}
Va en lotes de 50 titulos por peticion (limite de la API) y respeta el User-Agent.
"""
import csv, io, json, re, sys, time, urllib.parse, urllib.request, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), "datos_base", "wikidata_it_sitelinks.csv")
OUT = os.path.join(os.path.dirname(HERE), "datos_base", "it_patroni_raw.json")
API = "https://it.wikipedia.org/w/api.php"
UA = "chemieuro-festivos/1.0 (davidberna@gmail.com)"

rows = list(csv.DictReader(io.open(SRC, encoding="utf-8")))
titles = {}
for r in rows:
    if not r.get("art") or "/wiki/" not in r["art"]:
        continue
    t = urllib.parse.unquote(r["art"].split("/wiki/", 1)[1]).replace("_", " ")
    titles[t] = (r["codice"], r["comuneLabel"])

result = {}
if os.path.exists(OUT):
    result = json.load(io.open(OUT, encoding="utf-8"))
done_titles = {v["title"] for v in result.values()}
pending = [t for t in titles if t not in done_titles]
print("total", len(titles), "pendientes", len(pending), flush=True)

PAT = re.compile(r"^\s*\|\s*Patrono\s*=\s*(.*?)\s*$", re.M)
FES = re.compile(r"^\s*\|\s*Festivo\s*=\s*(.*?)\s*$", re.M)


def clean(s):
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)
    s = re.sub(r"\{\{[^}]*\}\}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", s).strip()


for i in range(0, len(pending), 50):
    batch = pending[i:i + 50]
    q = urllib.parse.urlencode({
        "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
        "format": "json", "formatversion": "2", "redirects": "1", "titles": "|".join(batch)})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            data = json.load(urllib.request.urlopen(req, timeout=60))
            break
        except Exception as e:
            print("reintento", attempt, e, flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        continue
    # los redirects cambian el titulo: mapear de vuelta
    redir = {r["to"]: r["from"] for r in data.get("query", {}).get("redirects", [])}
    norm = {r["to"]: r["from"] for r in data.get("query", {}).get("normalized", [])}
    for p in data.get("query", {}).get("pages", []):
        title = p.get("title", "")
        orig = redir.get(title, title)
        orig = norm.get(orig, orig)
        key = titles.get(orig) or titles.get(title)
        if not key:
            continue
        codice, nome = key
        text = ""
        try:
            text = p["revisions"][0]["slots"]["main"]["content"]
        except Exception:
            pass
        pm = PAT.search(text)
        fm = FES.search(text)
        result[codice] = {"nome": nome, "title": orig,
                          "patrono": clean(pm.group(1)) if pm else "",
                          "festivo": clean(fm.group(1)) if fm else ""}
    if (i // 50) % 10 == 0:
        json.dump(result, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print("lote", i // 50, "acumulado", len(result), flush=True)
    time.sleep(0.5)

json.dump(result, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
con_fecha = sum(1 for v in result.values() if v["festivo"])
print("FIN", len(result), "con festivo", con_fecha, flush=True)
