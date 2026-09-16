"""Festivos municipales de Portugal e Italia, normalizados para el feed.

PORTUGAL: feriado municipal de cada uno de los 308 concelhos (icalendario.pt,
que publica 2026/2027/2028 ya resueltos, incluidos los moviles tipo
"Quinta-feira da Ascensao"). Los codigos postales salen del dataset de CTT de
centraldedados/codigos_postais: se toman los prefijos de 4 digitos del concelho.

ITALIA: el patrono de cada comune y su dia, leidos del infobox de it.wikipedia
(campos Patrono y Festivo). Solo se aceptan los que dan una fecha FIJA
("17 giugno") o una regla de domingo/lunes resoluble ("prima domenica di
agosto"). Los CAP salen de matteocontrini/comuni-json.

Salida: pt_holidays.json e it_holidays.json, con la forma
  {"key":..., "name":..., "sub":..., "pc":[...], "holidays":[{"date":...,"name":...}]}
que es exactamente la que consume el feed. Ademas un informe por pais.
"""
import io, json, os, re, sys, unicodedata, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
YEARS = [2026, 2027, 2028]


def norm_key(s):
    """Misma normalizacion que NormalizeLocality en AL: mayusculas, sin acentos,
    solo A-Z 0-9 y espacios simples."""
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


# --------------------------------------------------------------- PORTUGAL
def build_pt():
    fer = json.load(io.open(os.path.join(HERE, "pt_feriados_raw.json"), encoding="utf-8"))
    cps = json.load(io.open(os.path.join(HERE, "pt_concelho_cp.json"), encoding="utf-8"))
    cps_norm = {norm_key(k): v for k, v in cps.items()}

    out, sin_cp = [], []
    for f in fer:
        key = norm_key(f["municipio"])
        info = cps_norm.get(key)
        pc = []
        if info:
            # El feed empareja por codigo postal completo; en PT el CP es
            # NNNN-NNN y el concelho agrupa muchos, asi que se listan los
            # prefijos de 4 digitos, que es lo que suele traer BC.
            pc = sorted(info["cp4"])
        else:
            sin_cp.append(f["municipio"])
        hol = []
        for y in YEARS:
            d = f["dates"].get(str(y))
            if d:
                hol.append({"year": y, "date": f"{d[0:4]}-{d[4:6]}-{d[6:8]}",
                            "name": f["nome"] or "Feriado municipal"})
        out.append({"key": key, "name": f["municipio"], "sub": "", "pc": pc, "holidays": hol})
    return out, sin_cp


# --------------------------------------------------------------- ITALIA
MESI = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
        "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
ORD = {"prima": 1, "primo": 1, "seconda": 2, "secondo": 2, "terza": 3, "terzo": 3,
       "quarta": 4, "quarto": 4, "1ª": 1, "2ª": 2, "3ª": 3, "4ª": 4, "1°": 1, "2°": 2, "3°": 3, "4°": 4}
GIORNI = {"domenica": 6, "lunedi": 0, "lunedì": 0, "martedi": 1, "martedì": 1,
          "mercoledi": 2, "mercoledì": 2, "giovedi": 3, "giovedì": 3,
          "venerdi": 4, "venerdì": 4, "sabato": 5}

RE_FIJA = re.compile(r"^(\d{1,2})\s*[º°]?\s+([a-zà-ú]+)$", re.I)
RE_ORD = re.compile(r"^(prima|primo|seconda|secondo|terza|terzo|quarta|quarto|1[ª°]|2[ª°]|3[ª°]|4[ª°])\s+"
                    r"(domenica|luned[ìi]|marted[ìi])\s+(?:di|del mese di|del)\s+([a-zà-ú]+)$", re.I)
RE_ULT = re.compile(r"^ultim[ao]\s+(domenica|luned[ìi])\s+(?:di|del mese di|del)\s+([a-zà-ú]+)$", re.I)


def nth_weekday(year, month, weekday, n):
    d = datetime.date(year, month, 1)
    shift = (weekday - d.weekday()) % 7
    d = d + datetime.timedelta(days=shift + 7 * (n - 1))
    return d if d.month == month else None


def last_weekday(year, month, weekday):
    if month == 12:
        nxt = datetime.date(year + 1, 1, 1)
    else:
        nxt = datetime.date(year, month + 1, 1)
    d = nxt - datetime.timedelta(days=1)
    while d.weekday() != weekday:
        d -= datetime.timedelta(days=1)
    return d


def parse_festivo(txt, year):
    """Devuelve (fecha ISO, motivo-descarte). Solo fechas deterministas."""
    t = txt.strip()
    # varias fechas separadas por ; o , -> se coge la primera, es la principal
    t = re.split(r"[;]", t)[0].strip()
    t = re.sub(r"\(.*?\)", "", t).strip()
    t = re.split(r",", t)[0].strip()

    m = RE_FIJA.match(t)
    if m:
        mes = MESI.get(m.group(2).lower())
        if not mes:
            return None, "mes desconocido: " + t
        try:
            return datetime.date(year, mes, int(m.group(1))).isoformat(), None
        except ValueError:
            return None, "fecha invalida: " + t

    m = RE_ORD.match(t)
    if m:
        n = ORD.get(m.group(1).lower())
        wd = GIORNI.get(m.group(2).lower())
        mes = MESI.get(m.group(3).lower())
        if n and wd is not None and mes:
            d = nth_weekday(year, mes, wd, n)
            if d:
                return d.isoformat(), None
        return None, "ordinal no resuelto: " + t

    m = RE_ULT.match(t)
    if m:
        wd = GIORNI.get(m.group(1).lower())
        mes = MESI.get(m.group(2).lower())
        if wd is not None and mes:
            return last_weekday(year, mes, wd).isoformat(), None
        return None, "ultimo no resuelto: " + t

    return None, "formato no reconocido: " + t


def clean_patrono(nombre):
    """El infobox de Wikipedia no siempre trae el campo Patrono donde toca: a
    veces el valor arrastra otro parametro de la plantilla ("|Festivo = 11
    settembre"). Si el texto huele a plantilla, no se inventa un santo: se
    pone el generico."""
    nombre = (nombre or "").strip()
    if (not nombre) or ("|" in nombre) or ("=" in nombre) or ("{" in nombre) or len(nombre) > 90:
        return "Festa patronale"
    return nombre[:1].upper() + nombre[1:]


def build_it():
    """Italia se construye en it_festivi.py.

    Se saco de aqui cuando el parseo italiano crecio (fechas multiples, reglas
    de domingo, fiestas de la Pascua, y la lectura del wikitexto crudo en vez
    del valor ya limpiado). Portugal no tiene nada que ver con eso y sigue
    intacto arriba. El informe detallado de Italia lo escribe `python
    it_festivi.py` en it_report.txt; aqui solo se resume.
    """
    from it_festivi import build_it as _build_it
    return _build_it()


def main():
    rep = io.open(os.path.join(HERE, "pt_it_report.txt"), "w", encoding="utf-8")

    pt, sin_cp = build_pt()
    json.dump(pt, io.open(os.path.join(HERE, "pt_holidays.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    rep.write("== PORTUGAL ==\n")
    rep.write("concelhos: %d\n" % len(pt))
    rep.write("sin codigos postales: %d %s\n" % (len(sin_cp), sin_cp))
    rep.write("sin festivos 2026: %d\n" % sum(1 for m in pt if not any(h["year"] == 2026 for h in m["holidays"])))
    for m in pt[:5]:
        rep.write("  %s | %s | cp4=%s | %s\n" % (m["key"], m["name"], m["pc"][:4],
                                                 [h for h in m["holidays"] if h["year"] == 2026]))
    for nombre in ("Marinha Grande", "Lisboa", "Porto", "Leiria", "Estarreja", "Maia"):
        f = [m for m in pt if m["name"] == nombre]
        rep.write("  CHECK %s -> %s\n" % (nombre, [h for h in f[0]["holidays"] if h["year"] == 2026] if f else "NO ESTA"))

    it, descartes = build_it()
    json.dump(it, io.open(os.path.join(HERE, "it_holidays.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    rep.write("\n== ITALIA ==\n")
    rep.write("comuni con festivo resuelto: %d\n" % len(it))
    rep.write("descartes: %s\n" % dict(descartes))
    rep.write("con subdivision: %d\n" % sum(1 for m in it if m["sub"]))
    rep.write("sin CAP: %d\n" % sum(1 for m in it if not m["pc"]))
    for nombre in ("Pisa", "Milano", "Cremona", "Opera", "Roma", "Parma", "Piacenza", "Ravenna"):
        f = [m for m in it if m["name"] == nombre]
        if f:
            rep.write("  CHECK %s -> sub=%s cap=%s %s\n" % (nombre, f[0]["sub"], f[0]["pc"][:3],
                                                            [h for h in f[0]["holidays"] if h["year"] == 2026]))
        else:
            rep.write("  CHECK %s -> NO ESTA\n" % nombre)

    # claves duplicadas: el feed solo puede emparejar por nombre si es unica
    for pais, data in (("PT", pt), ("IT", it)):
        c = collections.Counter(m["key"] for m in data)
        dup = [k for k, n in c.items() if n > 1]
        rep.write("\n%s claves duplicadas: %d %s\n" % (pais, len(dup), dup[:15]))
    rep.close()
    print(io.open(os.path.join(HERE, "pt_it_report.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
