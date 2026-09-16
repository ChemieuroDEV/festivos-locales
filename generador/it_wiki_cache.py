"""Descarga y cachea en disco el wikitexto del infobox de articulos de it.wikipedia.

Por que existe: it_patroni_raw.json guarda el valor YA limpiado de los parametros
Patrono/Festivo, asi que no sirve para re-diagnosticar por que fallo el parseo ni
para probar un regex nuevo. Aqui se guarda el bloque crudo del infobox (o los
primeros 4000 caracteres si no se localiza), que es lo unico que necesitamos y
mantiene el cache acotado (~30 MB para los 7.900 comuni).

Cache: it_wikitext_cache.json  {titulo_pedido: {"res": titulo_final, "txt": ...,
       "missing": bool}}. Se guarda cada 10 lotes, asi que se puede relanzar sin
repetir descargas.

Uso como libreria:  from it_wiki_cache import ensure, get
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "it_wikitext_cache.json")
API = "https://it.wikipedia.org/w/api.php"
UA = "chemieuro-festivos/1.0 (davidberna@gmail.com)"

_cache = None


def load():
    global _cache
    if _cache is None:
        if os.path.exists(CACHE):
            _cache = json.load(io.open(CACHE, encoding="utf-8"))
        else:
            _cache = {}
    return _cache


def save():
    if _cache is not None:
        tmp = CACHE + ".tmp"
        json.dump(_cache, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, CACHE)


def extract_infobox(text):
    """Devuelve el bloque {{Divisione amministrativa ...}} con llaves equilibradas.
    Si no lo encuentra, los primeros 4000 caracteres (por si el infobox es otro)."""
    # Dentro de <nowiki> hay llaves sueltas (Fanna, Meduno) que descuadran el
    # conteo y cortan el infobox a la tercera linea. Se neutralizan sin mover
    # ninguna posicion del texto.
    text = re.sub(r"<nowiki>.*?</nowiki>",
                  lambda m: re.sub(r"[{}]", " ", m.group(0)), text, flags=re.S)
    m = re.search(r"\{\{\s*Divisione amministrativa", text, re.I)
    if not m:
        m = re.search(r"\{\{\s*[Cc]omune", text)
    if not m:
        return text[:4000]
    i = m.start()
    depth = 0
    j = i
    n = len(text)
    while j < n:
        if text.startswith("{{", j):
            depth += 1
            j += 2
            continue
        if text.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                # un infobox de comune nunca son 3 lineas: si sale tan corto es
                # que el conteo se ha descuadrado y vale mas cortar por tamano
                return text[i:j] if j - i > 600 else text[i:i + 6000]
            continue
        j += 1
    return text[i:i + 6000]


def ensure(titles, log=True):
    """Descarga los titulos que no esten ya en el cache. 50 por peticion."""
    c = load()
    pending = [t for t in dict.fromkeys(titles) if t and t not in c]
    if log:
        print("cache", len(c), "pendientes", len(pending), flush=True)
    for i in range(0, len(pending), 50):
        batch = pending[i:i + 50]
        q = urllib.parse.urlencode({
            "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "format": "json", "formatversion": "2", "redirects": "1",
            # solo la seccion 0 (la del infobox): 100 KB por lote en vez de 1,2 MB
            "rvsection": "0", "titles": "|".join(batch)})
        req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
        data = None
        for attempt in range(4):
            try:
                data = json.load(urllib.request.urlopen(req, timeout=60))
                break
            except Exception as e:
                print("reintento", attempt, e, flush=True)
                time.sleep(5 * (attempt + 1))
        if data is None:
            continue
        q2 = data.get("query", {})
        # redirects y normalizaciones: mapear el titulo devuelto al pedido
        back = {}
        for r in q2.get("normalized", []):
            back[r["to"]] = r["from"]
        for r in q2.get("redirects", []):
            back[r["to"]] = back.get(r["from"], r["from"])
        seen = set()
        for p in q2.get("pages", []):
            title = p.get("title", "")
            orig = back.get(title, title)
            seen.add(orig)
            if p.get("missing"):
                c[orig] = {"res": title, "txt": "", "missing": True}
                continue
            try:
                text = p["revisions"][0]["slots"]["main"]["content"]
            except Exception:
                text = ""
            c[orig] = {"res": title, "txt": extract_infobox(text), "missing": not text}
        for t in batch:                      # lo que no volvio, marcar como fallido
            if t not in c:
                c[t] = {"res": t, "txt": "", "missing": True}
        if (i // 50) % 10 == 0:
            save()
            if log:
                print("lote", i // 50, "de", (len(pending) + 49) // 50, flush=True)
        time.sleep(0.5)
    save()
    return c


def get(title):
    return load().get(title)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ensure(sys.argv[1:])
    for t in sys.argv[1:]:
        print("=" * 20, t)
        print(get(t)["txt"][:3000])
