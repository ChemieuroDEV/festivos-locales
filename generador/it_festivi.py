r"""Festa del santo patrono de cada comune italiano, leida del infobox de it.wikipedia.

Por que esta separado de parse_pt_it.py: el parseo italiano ha crecido mucho
(fechas multiples, reglas de domingo, fiestas ligadas a la Pascua) y Portugal no
tiene que enterarse. parse_pt_it.py importa build_it() de aqui y sigue generando
sus 308 concelhos exactamente igual.

Contrato
--------
Entrada : it_wikitext_cache.json (bloque crudo del infobox, ver it_wiki_cache.py)
          it_titulos.json        (codice ISTAT -> titulo del articulo)
          it_patroni_raw.json    (respaldo para los que ya se habian leido)
          comuni_it.json         (CAP y sigla de provincia)
          subdiv_IT.json         (codigo de subdivision de OpenHolidays)
Salida  : lista [{key,name,sub,pc,holidays:[{year,date,name}]}] + contador de descartes

Decisiones de diseno
--------------------
1. NO SE INVENTA NADA. Si el texto no da una fecha determinista para un ano
   concreto, ese comune se descarta y el motivo se cuenta. "prima settimana di
   agosto", "settembre" o "primo fine settimana" no son fechas: fuera.
2. El valor del parametro se lee del wikitexto CRUDO, no de la version ya
   limpiada. El regex viejo (`...=\s*(.*?)\s*$` con re.M) tenia una trampa: el
   `\s*` se comia el salto de linea y, si el valor estaba vacio, acababa
   capturando la linea siguiente ("|PIL ="). Aqui el valor se corta en el
   siguiente `|` de primer nivel de la plantilla, asi que vale igual si el valor
   esta vacio, ocupa varias lineas o lleva plantillas dentro.
3. Un comune puede tener VARIAS fechas ("25 luglio e 8 settembre"): se emiten
   todas, que es lo que hace ya el fichero de Espana. Antes solo se cogia la
   primera.
4. Las fiestas moviles se resuelven con la Pascua gregoriana (Meeus/Butcher)
   solo cuando el desplazamiento es inequivoco (lunedi dell'Angelo = Pascua+1,
   Pentecoste = Pascua+49...). "Corpus Domini" y "Ascensione" no se resuelven
   porque en Italia se trasladan al domingo segun la diocesis: se descartan.
"""
import collections
import datetime
import io
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
YEARS = [2026, 2027, 2028]


# ------------------------------------------------------------------ utilidades
def norm_key(s):
    """Misma normalizacion que NormalizeLocality en AL."""
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    out, last_sep = [], True
    for ch in s:
        if ch.isascii() and (ch.isalpha() or ch.isdigit()):
            out.append(ch)
            last_sep = False
        elif not last_sep:
            out.append(" ")
            last_sep = True
    return "".join(out).strip()[:50]


def strip_accents(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def infobox_params(txt):
    """Parte la plantilla en parametros de PRIMER nivel.

    Hay que llevar la cuenta de {{ }}, [[ ]] y de las tablas {| |}: un `|`
    dentro de una plantilla anidada no separa parametros."""
    if not txt:
        return {}
    i = txt.find("{{")
    if i < 0:
        return {}
    body = txt[i + 2:]
    if body.endswith("}}"):
        body = body[:-2]
    parts, buf = [], []
    depth_t = depth_l = depth_tab = 0
    j, n = 0, len(body)
    while j < n:
        if body.startswith("{|", j):
            depth_tab += 1
            buf.append(body[j:j + 2]); j += 2; continue
        if body.startswith("|}", j) and depth_tab:
            depth_tab -= 1
            buf.append(body[j:j + 2]); j += 2; continue
        if body.startswith("{{", j):
            depth_t += 1
            buf.append(body[j:j + 2]); j += 2; continue
        if body.startswith("}}", j):
            depth_t = max(0, depth_t - 1)
            buf.append(body[j:j + 2]); j += 2; continue
        if body.startswith("[[", j):
            depth_l += 1
            buf.append(body[j:j + 2]); j += 2; continue
        if body.startswith("]]", j):
            depth_l = max(0, depth_l - 1)
            buf.append(body[j:j + 2]); j += 2; continue
        if body[j] == "|" and depth_t == 0 and depth_l == 0 and depth_tab == 0:
            parts.append("".join(buf)); buf = []; j += 1; continue
        buf.append(body[j]); j += 1
    parts.append("".join(buf))

    params = {}
    for p in parts[1:]:                       # parts[0] es el nombre de la plantilla
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = re.sub(r"\s+", " ", k.strip()).lower()
        if k and k not in params:
            params[k] = v.strip()
    return params


TEMPLATE_KEEP = re.compile(r"\{\{\s*(?:nowrap|maiuscoletto|small|q|lang\|[^|}]*)\s*\|", re.I)


def clean_value(s, drop_templates=None):
    """Texto plano del valor de un parametro. Los comentarios HTML y las <ref>
    se van; los <br> pasan a ';' porque separan fechas distintas."""
    if not s:
        return ""
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", " ", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", " ", s, flags=re.S)
    s = re.sub(r"<\s*br\s*/?\s*>", " ; ", s, flags=re.I)
    # plantillas: guardar cuales aparecen (para el informe) y quedarse con el
    # ultimo parametro cuando la plantilla es de las que envuelven texto
    def _tpl(m):
        inner = m.group(1)
        name = inner.split("|")[0].strip().lower()
        if drop_templates is not None:
            drop_templates[name] += 1
        if TEMPLATE_KEEP.match("{{" + inner + "|"):
            return " " + inner.split("|", 1)[1].replace("|", " ") + " "
        return " "
    for _ in range(3):                        # plantillas anidadas, un par de vueltas
        s2 = re.sub(r"\{\{([^{}]*)\}\}", _tpl, s)
        if s2 == s:
            break
        s = s2
    s = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("'''", "").replace("''", "")
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------ calendario
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
        "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
        "dicembre": 12}
ORD = {"prima": 1, "primo": 1, "1a": 1, "1o": 1, "1": 1, "i": 1,
       "seconda": 2, "secondo": 2, "2a": 2, "2o": 2, "2": 2, "ii": 2,
       "terza": 3, "terzo": 3, "3a": 3, "3o": 3, "3": 3, "iii": 3,
       "quarta": 4, "quarto": 4, "4a": 4, "4o": 4, "4": 4, "iv": 4,
       "quinta": 5, "quinto": 5, "5a": 5, "5o": 5, "5": 5, "v": 5,
       "ultima": -1, "ultimo": -1, "penultima": -2, "penultimo": -2}
GIORNI = {"domenica": 6, "lunedi": 0, "martedi": 1, "mercoledi": 2, "giovedi": 3,
          "venerdi": 4, "sabato": 5}

MESI_RE = "|".join(MESI)
ORD_RE = "|".join(sorted((re.escape(k) for k in ORD), key=len, reverse=True))
GIO_RE = "|".join(GIORNI)


def easter(year):
    """Pascua gregoriana (algoritmo de Meeus/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def nth_weekday(year, month, weekday, n):
    """n>0: n-esimo <weekday> del mes. n=-1 ultimo, n=-2 penultimo."""
    if n > 0:
        d = datetime.date(year, month, 1)
        d += datetime.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
        return d if d.month == month else None
    nxt = datetime.date(year + 1, 1, 1) if month == 12 else datetime.date(year, month + 1, 1)
    d = nxt - datetime.timedelta(days=1)
    while d.weekday() != weekday:
        d -= datetime.timedelta(days=1)
    d += datetime.timedelta(days=7 * (n + 1))
    return d if d.month == month else None


def next_weekday(base, weekday):
    """Primer <weekday> ESTRICTAMENTE posterior a base."""
    return base + datetime.timedelta(days=((weekday - base.weekday()) % 7) or 7)


def _norm_txt(t):
    """Minusculas sin acentos, con separaciones arregladas, para buscar fechas.
    'maggio8' -> 'maggio 8' (hay infoboxes sin espacio entre dos fechas)."""
    t = strip_accents(t.lower())
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"([a-z])(\d)", r"\1 \2", t)
    t = re.sub(r"(\d)([a-z])", r"\1 \2", t)
    # Los indicadores ordinales no se descomponen con NFD y llegan vivos hasta
    # aqui. Se traducen DESPUES de separar cifra y letra: si se hiciera antes,
    # el "3a" recien creado se partiria en "3 a" y el ordinal se perderia.
    t = t.replace("ª", "a").replace("º", "o").replace("°", "o")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\bdell'\s*", "dell'", t)
    return t


# marcadores que indican que lo que viene ya no es la fiesta vigente
RE_CORTE = re.compile(r"\b(anticamente|un tempo|in passato|fino al|fino agli|storicamente|"
                      r"prima del|sino al)\b")

RE_DIA_MES = re.compile(r"\b((?:\d{1,2}\s*[oa]?\s*(?:-|e|,|/)\s*)*\d{1,2})\s*[oa]?\s+"
                        r"(?:di\s+)?(" + MESI_RE + r")\b")
# "Primo maggio" es el 1 de mayo, no un ordinal de domingo
RE_PRIMO_MES = re.compile(r"\bprimo\s+(" + MESI_RE + r")\b")
# el valor entero es una fecha numerica: "06/12"
RE_NUM = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
RE_ORD_GIO = re.compile(r"\b(" + ORD_RE + r")\s+(" + GIO_RE + r")\s+"
                        r"(?:di|del mese di|del|dell|d'|in)\s*(" + MESI_RE + r")\b")
RE_REL_ORD = re.compile(r"\b(" + GIO_RE + r")\s+(?:dopo|successivo|seguente|che segue|"
                        r"che seguono)\s*(?:a|al|alla|all'|la|il|l')?\s*(?:la\s+|il\s+)?"
                        r"(" + ORD_RE + r")\s+(" + GIO_RE + r")\s+"
                        r"(?:di|del mese di|del|dell|d'|in)\s*(" + MESI_RE + r")\b")
RE_SUF_LUN = re.compile(r"\be\s+(?:il\s+)?(" + GIO_RE + r")\s+(?:successivo|seguente|dopo)")

# fiestas moviles: desplazamiento en dias respecto al domingo de Pascua
PASQUA = [
    (r"venerdi\s+santo", -2),
    (r"luned[ìi]?\s+dopo\s+l'?ottava\s+di\s+pasqua", 8),
    (r"ottava\s+di\s+pasqua", 7), (r"8\s+giorni\s+dopo\s+pasqua", 7),
    (r"marted[ìi]?\s+in\s+albis", 9),
    (r"domenica\s+(?:dopo|successiva\s+all')\s*l?'?ascensione", 42),
    (r"luned[ìi]?\s*dell'angelo", 1), (r"pasquetta", 1),
    (r"luned[ìi]?\s+(?:di|dopo|dell[ae])\s+pasqua", 1),
    (r"marted[ìi]?\s+(?:dopo|di|dell[ae])\s+pasqua", 2),
    (r"domenica\s+in\s+albis", 7),
    (r"(prima|seconda|terza|quarta)\s+domenica\s+dopo\s+(?:la\s+)?pasqua", None),  # 7*n
    (r"luned[ìi]?\s+(?:di|dopo|dell[ae])\s+pentecoste", 50),
    (r"marted[ìi]?\s+(?:dopo|di|dell[ae])\s+pentecoste", 51),
    (r"(prima|seconda|terza)\s+domenica\s+dopo\s+(?:la\s+)?pentecoste", None),     # 49+7n
    (r"\bpentecoste\b", 49),
]
RE_DOM_PASQUA = re.compile(r"\b(prima|seconda|terza|quarta)\s+domenica\s+dopo\s+(?:la\s+)?pasqua\b")
RE_DOM_PENT = re.compile(r"\b(prima|seconda|terza)\s+domenica\s+dopo\s+(?:la\s+)?pentecoste\b")


def parse_festivo(txt, year):
    """Todas las fechas deterministas del texto, para ese ano.

    Devuelve (lista de fechas ISO ordenadas, motivo_de_descarte_si_vacia)."""
    if not txt:
        return [], "campo Festivo vacio"
    t = _norm_txt(txt)
    corte = RE_CORTE.search(t)
    if corte:
        t = t[:corte.start()]
    found = []

    # --- fiestas ligadas a la Pascua
    pas = easter(year)
    m = RE_DOM_PASQUA.search(t)
    if m:
        found.append(pas + datetime.timedelta(days=7 * ORD[m.group(1)]))
    m = RE_DOM_PENT.search(t)
    if m:
        found.append(pas + datetime.timedelta(days=49 + 7 * ORD[m.group(1)]))
    for pat, off in PASQUA:
        if off is None:
            continue
        if re.search(pat, t):
            found.append(pas + datetime.timedelta(days=off))
            break

    # --- "lunedi dopo la terza domenica di settembre" (antes que RE_ORD_GIO,
    #     que tambien casaria con la parte "terza domenica di settembre")
    consumido = []
    for m in RE_REL_ORD.finditer(t):
        wd_obj = GIORNI[m.group(1)]
        base = nth_weekday(year, MESI[m.group(4)], GIORNI[m.group(3)], ORD[m.group(2)])
        if base:
            found.append(next_weekday(base, wd_obj))
            consumido.append((m.start(), m.end()))

    def solapado(a, b):
        return any(not (b <= s or a >= e) for s, e in consumido)

    # --- "terza domenica di agosto", "ultima domenica di luglio"
    for m in RE_ORD_GIO.finditer(t):
        if solapado(m.start(), m.end()):
            continue
        d = nth_weekday(year, MESI[m.group(3)], GIORNI[m.group(2)], ORD[m.group(1)])
        if d:
            found.append(d)
            # "... e lunedi successivo"
            suf = RE_SUF_LUN.match(t[m.end():].strip())
            if suf:
                found.append(next_weekday(d, GIORNI[suf.group(1)]))

    # --- "Primo maggio" y "06/12"
    for m in RE_PRIMO_MES.finditer(t):
        found.append(datetime.date(year, MESI[m.group(1)], 1))
    m = RE_NUM.match(t)
    if m:
        try:
            found.append(datetime.date(year, int(m.group(2)), int(m.group(1))))
        except ValueError:
            pass

    # --- fechas fijas, incluidas las listas "3-4-5 agosto" / "15 e 16 agosto"
    for m in RE_DIA_MES.finditer(t):
        mes = MESI[m.group(2)]
        for dia in re.findall(r"\d{1,2}", m.group(1)):
            try:
                found.append(datetime.date(year, mes, int(dia)))
            except ValueError:
                pass

    if not found:
        return [], "formato no reconocido: " + re.sub(r"\s+", " ", txt.strip())[:80]
    return sorted({d.isoformat() for d in found}), None


def clean_patrono(nombre):
    """El nombre que va al feed. Si el valor huele a plantilla rota, generico."""
    nombre = (nombre or "").strip()
    # el <br> del infobox se convirtio en " ; " para separar fechas; en el
    # nombre del santo queda feo y se normaliza a coma
    nombre = re.sub(r"\s*[;,]\s*(?=[;,])", "", nombre)
    nombre = re.sub(r"\s*;\s*", ", ", nombre).strip(" ,;")
    if (not nombre) or ("|" in nombre) or ("=" in nombre) or ("{" in nombre) or len(nombre) > 90:
        return "Festa patronale"
    return nombre[:1].upper() + nombre[1:]


# ------------------------------------------------------------------ construccion
def _load(name, default=None):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    return json.load(io.open(p, encoding="utf-8"))


def leer_infobox(codice, titulos, cache, raw):
    """(patrono, festivo) de un comune, del wikitexto si lo hay y si no del
    fichero antiguo. Devuelve tambien de donde salio, para el informe."""
    t = titulos.get(codice)
    ent = cache.get(t) if t else None
    if ent and ent.get("txt"):
        p = infobox_params(ent["txt"])
        # un punado de articulos llaman al parametro de otra forma
        fest = ""
        for k in ("festivo", "festivi", "giorno festivo", "altre festivita",
                  "altre festività"):
            fest = clean_value(p.get(k, ""))
            if fest:
                break
        patr = clean_value(p.get("patrono", "") or p.get("co-patrono", ""))
        alt = clean_value(p.get("nome", "")) or re.sub(r"\s*\(.*\)$", "", t)
        return patr, fest, "wikitexto", alt  # el articulo esta, diga o no diga nada
    v = raw.get(codice)
    if v:
        f = (v.get("festivo") or "").strip()
        if f.startswith("|") or "=" in f:     # basura del regex viejo
            f = ""
        return (v.get("patrono") or ""), f, "raw", (v.get("nome") or "")
    return "", "", "sin articulo", ""


def build_it(detalle=None):
    """Devuelve (lista de comuni con festivo, Counter de descartes)."""
    raw = _load("it_patroni_raw.json", {}) or {}
    titulos = _load("it_titulos.json", {}) or {}
    # la etiqueta de Wikidata es el nombre de uso ("Reggio Emilia"), que no
    # siempre es el oficial del ISTAT ("Reggio nell'Emilia")
    labels = {}
    p_csv = os.path.join(HERE, "wikidata_it_sitelinks.csv")
    if os.path.exists(p_csv):
        import csv
        for row in csv.DictReader(io.open(p_csv, encoding="utf-8")):
            if row.get("comuneLabel"):
                labels[row["codice"]] = row["comuneLabel"]
    cache = _load("it_wikitext_cache.json", {}) or {}
    comuni = _load("comuni_it.json", []) or []

    subs = {}
    tree = _load("subdiv_IT.json", [])
    if tree:
        def walk(nodes):
            for n in nodes:
                iso = n.get("isoCode", "")
                if iso.startswith("IT-") and len(iso) == 5:
                    subs[iso[3:]] = n["code"]
                walk(n.get("children", []))
        walk(tree)

    out, descartes = [], collections.Counter()
    for c in comuni:
        codice, nome = c["codice"], c["nome"]
        patr, fest, origen, wikinome = leer_infobox(codice, titulos, cache, raw)
        if origen == "sin articulo" and not fest:
            descartes["sin articulo de wikipedia localizado"] += 1
            if detalle is not None:
                detalle.append((nome, "sin articulo", ""))
            continue
        if not fest:
            # Se separan los dos casos porque no son el mismo problema: el
            # primero es un infobox a medias (hay santo, falta el dia) y el
            # segundo un articulo que no habla del patrono. Ni uno ni otro se
            # pueden completar sin inventar.
            motivo = ("infobox con Patrono pero sin Festivo" if patr
                      else "infobox sin Patrono ni Festivo")
            descartes[motivo] += 1
            if detalle is not None:
                detalle.append((nome, "sin campo Festivo", ""))
            continue

        hol, motivo = [], None
        nombre = clean_patrono(patr)
        for y in YEARS:
            fechas, why = parse_festivo(fest, y)
            motivo = motivo or why
            for iso in fechas:
                hol.append({"year": y, "date": iso, "name": nombre})
        if not hol:
            descartes["formato de Festivo no resoluble"] += 1
            if detalle is not None:
                detalle.append((nome, "formato", fest))
            continue

        # "Reggio nell'Emilia" en el ISTAT es "Reggio Emilia" en Wikipedia y en
        # media Italia. Se guarda la variante en `alt`, igual que hace el
        # fichero de Espana, para poder emparejar tambien por ese nombre.
        alt = []
        k = norm_key(nome)
        for cand in (wikinome, (raw.get(codice) or {}).get("nome", ""), labels.get(codice, "")):
            if cand and norm_key(cand) != k and cand not in alt:
                alt.append(cand)
        out.append({"key": k, "name": nome, "alt": alt,
                    "sub": subs.get(c.get("sigla", ""), ""),
                    "pc": sorted(c.get("cap", [])), "holidays": hol})
    return out, descartes


def grupos_v1():
    """Reconstruye en que grupo cayo cada comune en la PRIMERA pasada, para poder
    decir cuantos se han recuperado de cada uno.

    No hace falta el parser viejo: el grupo se deduce de it_patroni_raw.json y
    de la salida antigua (it_holidays_v1.json).
      A  infobox sin campo Festivo   (valor vacio, o la basura "|PIL =")
      B  formato no reconocido       (tenia texto y no se resolvio)
      C  comune sin CAP              (codigo que no esta en comuni_it.json)
      D  ni siquiera estaba en it_patroni_raw.json
      OK resuelto ya entonces
    """
    raw = _load("it_patroni_raw.json", {}) or {}
    comuni = _load("comuni_it.json", []) or []
    v1 = _load("it_holidays_v1.json", []) or []
    ok_v1 = {m["name"] for m in v1}
    cod_comuni = {c["codice"] for c in comuni}
    g = {}
    for cod, v in raw.items():
        f = (v.get("festivo") or "").strip()
        if not f or f.startswith("|") or "=" in f:
            g[cod] = "A"
        elif cod not in cod_comuni:
            g[cod] = "C"
        elif v.get("nome") in ok_v1:
            g[cod] = "OK"
        else:
            g[cod] = "B"
    for c in comuni:
        g.setdefault(c["codice"], "D")
    return g


def main():
    """Genera it_holidays.json y el informe it_report.txt."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    detalle = []
    out, descartes = build_it(detalle)
    json.dump(out, io.open(os.path.join(HERE, "it_holidays.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    comuni = _load("comuni_it.json", []) or []
    by_cod = {c["codice"]: c for c in comuni}
    antes = _load("it_holidays_v1.json", None)
    resueltos = {m["name"] for m in out}
    r = []
    A = r.append
    A("INFORME ITALIA - festa patronale de cada comune")
    A("=" * 66)
    A("comuni totales (ISTAT, comuni_it.json) ................ %d" % len(comuni))
    if antes is not None:
        A("con festivo resuelto ANTES ............................ %d" % len(antes))
    A("con festivo resuelto AHORA ............................ %d" % len(out))
    if antes is not None:
        A("ganancia .............................................. +%d" % (len(out) - len(antes)))
    A("cobertura ............................................. %.1f%% de los comuni"
      % (100.0 * len(out) / max(1, len(comuni))))
    A("")

    A("QUE SE HA RECUPERADO DE CADA GRUPO DE LA PRIMERA PASADA")
    etiquetas = {
        "A": "768 'infobox sin campo Festivo'",
        "B": "459 'formato no reconocido'",
        "C": "36 'comune sin CAP' (codigos ISTAT viejos)",
        "D": "comuni que no estaban en it_patroni_raw.json",
        "OK": "ya resueltos en la primera pasada",
    }
    g = grupos_v1()
    tot = collections.Counter(g.values())
    rec = collections.Counter(grp for cod, grp in g.items()
                              if by_cod.get(cod) and by_cod[cod]["nome"] in resueltos)
    for k in ("A", "B", "C", "D", "OK"):
        A("  %-45s %4d de %4d" % (etiquetas[k], rec[k], tot[k]))
    A("  (el grupo C son codigos ISTAT que ya no existen: no hay comune que")
    A("   rellenar, sus localidades entran por su codigo actual)")
    A("")

    A("DIAGNOSTICO: POR QUE FALLABAN LOS DOS GRUPOS")
    A("  A) 'infobox sin campo Festivo' (768). Se descargo el wikitexto crudo de")
    A("     20 de ellos (diag_wikitext/) y el campo esta REALMENTE vacio:")
    A("     '|Festivo = ' seguido de '|PIL = '. El '|PIL =' que se veia en")
    A("     it_patroni_raw.json no era el valor, era el regex viejo: el '\\s*'")
    A("     posterior al '=' se comia el salto de linea y '$' (con re.M) cerraba")
    A("     al final de la linea SIGUIENTE. Se ha corregido leyendo el parametro")
    A("     hasta el siguiente '|' de primer nivel de la plantilla, pero el dato")
    A("     no existe: de los 761 que siguen siendo comuni, solo 4 tienen hoy")
    A("     algo escrito en Festivo. Este grupo no es recuperable sin inventar.")
    A("  B) 'formato no reconocido' (459). Aqui si habia dato y el parser se")
    A("     quedaba corto: solo aceptaba una fecha por comune (cortaba en la")
    A("     primera coma o punto y coma), no entendia los ordinales escritos")
    A("     '1a/3a/III', ni las listas ('15 e 16 agosto', '3-4-5 agosto'), ni el")
    A("     dia relativo a un domingo ('lunedi dopo la III domenica di")
    A("     settembre'), ni nada ligado a la Pascua. Recuperados 426 de 459.")
    A("  C) Comuni que no estaban en it_patroni_raw.json (1.330): les faltaba el")
    A("     sitelink en Wikidata. Se ha localizado el articulo de los 7.904 por")
    A("     nombre y candidatos, comprobando nombre+provincia del infobox, y 7 a")
    A("     mano (renombrados o cambiados de provincia). Recuperados 1.114.")
    A("")
    A("  Margen que queda y NO se ha tocado por no inventar: 5 comuni llevan la")
    A("  fecha dentro del campo Patrono ('san Giovanni Battista (24 giugno)').")
    A("  Se ha preferido no deducir el festivo del santoral del patrono.")
    A("")
    A("MOTIVOS DE DESCARTE (sobre los 7.904 comuni)")
    for k, n in descartes.most_common():
        A("  %-48s %5d" % (k, n))
    A("  %-48s %5d" % ("TOTAL descartados", sum(descartes.values())))
    A("")

    if antes is not None:
        ahora = {m["key"] for m in out}
        ya = {m["key"] for m in antes}
        alt = {norm_key(a) for m in out for a in m["alt"]}
        A("CAMBIOS RESPECTO A it_holidays_v1.json")
        A("  claves nuevas ....................................... %d" % len(ahora - ya))
        A("  claves que desaparecen .............................. %d" % len(ya - ahora))
        A("    (son el mismo comune con el nombre oficial del ISTAT en vez del")
        A("     de Wikipedia; %d de %d siguen emparejables por el campo `alt`)"
          % (len((ya - ahora) & alt), len(ya - ahora)))
        A("")

    fmt = collections.Counter(f for _, m, f in detalle if m == "formato")
    A("LOS 20 FORMATOS DE 'Festivo' QUE SIGUEN SIN RESOLVERSE")
    A("  textos distintos: %d | comuni afectados: %d" % (len(fmt), sum(fmt.values())))
    for t, n in fmt.most_common(20):
        A("  %3d  %s" % (n, t[:90]))
    A("")

    porano = collections.Counter()
    for m in out:
        for h in m["holidays"]:
            porano[h["year"]] += 1
    A("SALIDA")
    A("  fechas emitidas por ano ............................. %s" % dict(sorted(porano.items())))
    A("  comuni con mas de una fecha en 2026 ................. %d"
      % sum(1 for m in out if sum(1 for h in m["holidays"] if h["year"] == 2026) > 1))
    A("  con subdivision OpenHolidays ........................ %d" % sum(1 for m in out if m["sub"]))
    A("  sin codigo postal ................................... %d" % sum(1 for m in out if not m["pc"]))
    A("  con nombre alternativo en `alt` ..................... %d" % sum(1 for m in out if m["alt"]))
    dup = [k for k, n in collections.Counter(m["key"] for m in out).items() if n > 1]
    A("  claves duplicadas (homonimos de distinta provincia) . %d %s" % (len(dup), dup[:10]))
    A("")

    by_name = {m["name"]: m for m in out}
    desc_by_name = {n: (mot, f) for n, mot, f in detalle}
    nombres_istat = {c["nome"] for c in comuni}
    A("COMPROBACIONES PEDIDAS")
    CHECKS = ["Pisa", "Milano", "Agrate Brianza", "Altopascio", "Andria",
              "Cassano d'Adda", "Cernusco sul Naviglio", "Concesio",
              "Desenzano del Garda", "Bergamasco", "Cavaria con Premezzo",
              "Guamo", "Crespellano"]
    for n in CHECKS:
        m = by_name.get(n)
        if m:
            f26 = ["%s (%s)" % (h["date"], h["name"]) for h in m["holidays"] if h["year"] == 2026]
            A("  %-22s ENTRA    2026: %s" % (n, "; ".join(f26)))
        elif n not in nombres_istat:
            A("  %-22s NO ENTRA: no es un comune del ISTAT (frazione o comune suprimido)" % n)
        else:
            mot, f = desc_by_name.get(n, ("desconocido", ""))
            A("  %-22s NO ENTRA: %s%s" % (n, mot, (" -> %r" % f) if f else ""))
    A("")
    A("RESULTADO: it_holidays.json tiene %d comuni." % len(out))

    txt = "\n".join(r) + "\n"
    io.open(os.path.join(HERE, "it_report.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
