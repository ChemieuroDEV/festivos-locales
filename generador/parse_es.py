# -*- coding: utf-8 -*-
"""
parse_es.py  -- Festivos LOCALES (municipales) de Espana 2026.

Lee los boletines ya descargados en es_src/ y produce:
    es_holidays.json         lista de {ine, municipio, provincia, fecha, nombre, fuente}
    es_holidays_report.txt   informe de control de calidad

Reglas duras:
  - No se inventa NI UN dato. Lo que no se puede parsear se descarta y se cuenta.
  - Un parser que falle no tumba al resto (todo va dentro de try/except).
  - `ine` solo se rellena cuando la fuente lo trae. Si no, "".

Dependencias: solo stdlib + pypdf.
"""

import io
import os
import re
import csv
import sys
import json
import unicodedata
import collections
import traceback

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

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = FUENTES
YEAR = 2026

# ---------------------------------------------------------------------------
# Utilidades comunes
# ---------------------------------------------------------------------------

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

MESES_CA = {
    "gener": 1, "febrer": 2, "marc": 3, "abril": 4, "maig": 5, "juny": 6,
    "juliol": 7, "agost": 8, "setembre": 9, "octubre": 10, "novembre": 11,
    "desembre": 12,
}

# Provincias por prefijo INE (solo las que necesitamos deducir).
PROV_BY_INE2 = {
    "01": "ARABA/ALAVA", "02": "ALBACETE", "03": "ALICANTE", "04": "ALMERIA",
    "05": "AVILA", "06": "BADAJOZ", "07": "ILLES BALEARS", "08": "BARCELONA",
    "09": "BURGOS", "10": "CACERES", "11": "CADIZ", "12": "CASTELLON",
    "13": "CIUDAD REAL", "14": "CORDOBA", "15": "A CORUNA", "16": "CUENCA",
    "17": "GIRONA", "18": "GRANADA", "19": "GUADALAJARA", "20": "GIPUZKOA",
    "21": "HUELVA", "22": "HUESCA", "23": "JAEN", "24": "LEON", "25": "LLEIDA",
    "26": "LA RIOJA", "27": "LUGO", "28": "MADRID", "29": "MALAGA",
    "30": "MURCIA", "31": "NAVARRA", "32": "OURENSE", "33": "ASTURIAS",
    "34": "PALENCIA", "35": "LAS PALMAS", "36": "PONTEVEDRA", "37": "SALAMANCA",
    "38": "SANTA CRUZ DE TENERIFE", "39": "CANTABRIA", "40": "SEGOVIA",
    "41": "SEVILLA", "42": "SORIA", "43": "TARRAGONA", "44": "TERUEL",
    "45": "TOLEDO", "46": "VALENCIA", "47": "VALLADOLID", "48": "BIZKAIA",
    "49": "ZAMORA", "50": "ZARAGOZA", "51": "CEUTA", "52": "MELILLA",
}

MAX_DIA_MES = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
               7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def norm_key(s):
    """Clave de comparacion: sin acentos, sin espacios, minusculas."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(s or "").lower())


def clean_text(s):
    """Quita caracteres no imprimibles (el \\uffff de La Rioja) y normaliza espacios."""
    if s is None:
        return ""
    s = s.replace("\uffff", "").replace("\xa0", " ").replace("’", "'")
    s = "".join(c for c in s if c == "\n" or c == "\t" or unicodedata.category(c)[0] != "C")
    return s


def squash(s):
    return " ".join((s or "").split())


def mk_date(year, month, day):
    """Devuelve 'YYYY-MM-DD' o None si la fecha no es valida."""
    try:
        month = int(month)
        day = int(day)
    except (TypeError, ValueError):
        return None
    if not (1 <= month <= 12):
        return None
    maxd = MAX_DIA_MES[month]
    if month == 2 and year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        maxd = 29
    if not (1 <= day <= maxd):
        return None
    return "%04d-%02d-%02d" % (year, month, day)


def month_from_word(word):
    w = strip_accents((word or "").strip().lower())
    return MESES_ES.get(w)


# --- reparacion de artefactos de kerning en los PDFs -----------------------
# Los boletines en PDF parten palabras: 'XÀTIV A', 'FA V ARA', 'V ALENCIA',
# 'RIBAMONTÁN AL MONT E'. Es un espacio espurio del PDF, no parte del nombre.
# Solo se aplica a las fuentes que vienen de PDF, nunca a los CSV oficiales.

# Palabras cortas que SI pueden ir legitimamente delante de una V
# ('LA VALL D'UIXO', 'DE LES VALLS', 'SAN VICENTE'): ahi el espacio es real.
_PDF_KEEP_BEFORE_V = {"LA", "EL", "LES", "ELS", "LOS", "LAS", "LO", "L'",
                      "DE", "DEL", "DELS", "D'", "I", "Y", "O", "A", "EN",
                      "SAN", "SANT", "SANTA", "SANTO", "SANTES", "VILA"}

_UNA_LETRA = re.compile(r"^[A-ZÁÉÍÓÚÜÑ]$")


def fix_pdf_spacing(name):
    """
    Pega los espacios espurios que mete la extraccion de texto del PDF.

    El artefacto siempre gira alrededor de una V mayuscula, que el extractor
    separa del resto de la palabra, y aparece de tres formas:
        (a) una V suelta        'FA V ARA'  'V ALENCIA'  'LA V ALL D'UIXO'
        (b) palabra acabada en V + una sola letra   'XATIV A'  'DAYA NUEV A'
        (c) fragmento corto + palabra que empieza por V   'TA VERNES'
    Ademas se pega una letra suelta al final del nombre ('MONT E' -> 'MONTE').
    No se toca nunca el texto de los CSV oficiales, solo el de los PDF.
    """
    n = squash(name)
    if not n:
        return n
    toks = n.split()
    out = []
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        prev = out[-1] if out else None

        # (a) token que es solo 'V'
        if t == "V" and nxt:
            if prev is None or prev.upper().rstrip(",.") in _PDF_KEEP_BEFORE_V:
                out.append("V" + nxt)               # la V abre palabra
            else:
                out[-1] = prev + "V" + nxt          # la V va dentro de la palabra
            i += 2
            continue

        # (b) palabra acabada en V seguida de una sola letra
        if len(t) >= 2 and t.endswith("V") and nxt and _UNA_LETRA.match(nxt):
            out.append(t + nxt)
            i += 2
            continue

        # (c) fragmento de 1-2 letras, no articulo, delante de palabra con V
        if (len(t) <= 2 and t.isalpha() and t.isupper()
                and t.upper() not in _PDF_KEEP_BEFORE_V
                and nxt and nxt.startswith("V") and len(nxt) >= 2):
            out.append(t + nxt)
            i += 2
            continue

        out.append(t)
        i += 1

    # letra suelta al final ('RIBAMONTAN AL MONT E'); Y/O/I son conjunciones
    if len(out) >= 2 and _UNA_LETRA.match(out[-1]) and out[-1] not in ("Y", "O", "I") \
            and len(out[-2]) >= 2 and out[-2].isalpha():
        out[-2] = out[-2] + out[-1]
        out.pop()
    return squash(" ".join(out))


_TOKEN_RE = re.compile(
    r"(?P<num>\d{1,2})|(?P<mes>" + "|".join(sorted(MESES_ES, key=len, reverse=True)) + r")",
    re.IGNORECASE)


def extract_dates_es(text, year=YEAR):
    """
    Extractor generico de fechas en castellano dentro de un texto libre.

    Recorre numeros y nombres de mes en orden; los numeros pendientes se
    asignan al primer mes que aparece detras. Cubre:
        "8 de mayo y 29 de septiembre"   -> 08-05, 29-09
        "3 y 4 de agosto"                -> 03-08, 04-08
        "17 de enero y de 15 mayo"       -> 17-01, 15-05   (erratas del BOE)
        "4y7deseptiembre"                -> 04-09, 07-09   (texto pegado)

    Devuelve (fechas, numeros_huerfanos).
    """
    t = strip_accents((text or "").lower())
    fechas = []
    pend = []
    for m in _TOKEN_RE.finditer(t):
        if m.group("num"):
            pend.append(int(m.group("num")))
        else:
            mes = MESES_ES[m.group("mes")]
            for d in pend:
                f = mk_date(year, mes, d)
                if f and f not in fechas:
                    fechas.append(f)
            pend = []
    return fechas, pend


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

class Report(object):
    def __init__(self):
        self.discards = collections.Counter()   # (fuente, motivo) -> n
        self.notes = []                         # (fuente, texto)
        self.errors = []                        # (fuente, traceback)

    def discard(self, fuente, motivo, n=1):
        self.discards[(fuente, motivo)] += n

    def note(self, fuente, texto):
        self.notes.append((fuente, texto))

    def error(self, fuente, tb):
        self.errors.append((fuente, tb))


REP = Report()


def row(ine, municipio, provincia, fecha, nombre, fuente, **extra):
    d = {
        "ine": (ine or "").strip(),
        "municipio": squash(municipio),
        "provincia": squash(provincia),
        "fecha": fecha,
        "nombre": squash(nombre),
        "fuente": fuente,
    }
    for k, v in extra.items():
        if v:
            d[k] = squash(v)
    return d


def read_text(path, encodings=("utf-8-sig", "utf-8", "cp1252", "latin-1")):
    """Lee un fichero probando codificaciones hasta que una no rompe."""
    last = None
    for enc in encodings:
        try:
            with io.open(path, "r", encoding=enc, newline="") as f:
                return f.read(), enc
        except UnicodeDecodeError as e:
            last = e
    raise last


# ---------------------------------------------------------------------------
# 1. CATALUNA  (cat.csv)
# ---------------------------------------------------------------------------

def parse_cat():
    F = "CAT"
    out = []
    txt, _ = read_text(os.path.join(SRC, "cat.csv"), ("utf-8-sig", "utf-8", "latin-1"))
    rd = csv.DictReader(io.StringIO(txt))
    col_muni = None
    for c in rd.fieldnames or []:
        if c and c.strip().lower().startswith("ajuntament"):
            col_muni = c            # la cabecera real trae un espacio final
    if col_muni is None:
        raise RuntimeError("cat.csv: no encuentro la columna de ayuntamiento")

    for r in rd:
        if (r.get("Any calendari") or "").strip() != str(YEAR):
            continue
        festiu = (r.get("Festiu") or "").strip()
        if "prueba" in festiu.lower():
            REP.discard(F, "fila de prueba en el origen")
            continue
        raw = (r.get("Data") or "").strip()
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
        if not m:
            REP.discard(F, "fecha ilegible")
            continue
        fecha = mk_date(int(m.group(3)), m.group(2), m.group(1))
        if not fecha or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha invalida o de otro anyo")
            continue
        ine = re.sub(r"\D", "", r.get("Codi municipi INE") or "").zfill(5)
        if len(ine) != 5 or ine == "00000":
            ine = ""
        muni = (r.get(col_muni) or "").strip()
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        nombre = "" if festiu.lower() in ("festiu local", "festa local") else festiu
        prov = PROV_BY_INE2.get(ine[:2], "")
        out.append(row(ine, muni, prov, fecha, nombre, F))
    REP.note(F, "incluye nuclis/pedanies (columna Pedania != 000), que comparten el INE del municipio")
    return out


# ---------------------------------------------------------------------------
# 2. ARAGON  (ara_2026.csv)
# ---------------------------------------------------------------------------

def parse_ara():
    F = "ARA"
    out = []
    txt, enc = read_text(os.path.join(SRC, "ara_%d.csv" % ANIO))
    REP.note(F, "leido como %s" % enc)
    for r in csv.DictReader(io.StringIO(txt), delimiter=";"):
        raw = (r.get("Fecha") or "").strip()
        m = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", raw)
        if not m:
            REP.discard(F, "fecha ilegible")
            continue
        fecha = mk_date(int(m.group(3)), m.group(2), m.group(1))
        if not fecha or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha invalida o de otro anyo")
            continue
        ine = re.sub(r"\D", "", r.get("CodigoINE") or "")
        ine = ine.zfill(5) if ine else ""
        if len(ine) != 5 or ine == "00000":
            ine = ""            # las pedanias vienen sin codigo INE
        muni = (r.get("Municipio") or "").strip()
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        prov = (r.get("Provincia") or "").strip().upper()
        out.append(row(ine, muni, prov, fecha, (r.get("NombreFestivo") or "").strip(), F))
    return out


# ---------------------------------------------------------------------------
# 3. MADRID  (mad.csv)
# ---------------------------------------------------------------------------

def parse_mad():
    F = "MAD"
    out = []
    txt, _ = read_text(os.path.join(SRC, "mad.csv"), ("cp1252", "utf-8", "latin-1"))
    rd = csv.DictReader(io.StringIO(txt), delimiter=";")
    col_anyo = None
    for c in rd.fieldnames or []:
        if c and strip_accents(c.strip().lower()) == "ano":
            col_anyo = c
    for r in rd:
        if col_anyo and (r.get(col_anyo) or "").strip() != str(YEAR):
            REP.discard(F, "fila de otro anyo")
            continue
        fecha = (r.get("fecha_festivo") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha) or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha ilegible")
            continue
        cod = re.sub(r"\D", "", r.get("municipio_codigo") or "")
        ine = ("28" + cod.zfill(3)) if cod else ""
        muni_nombre = (r.get("municipio_nombre") or "").strip()
        ent_nombre = (r.get("entidad_nombre") or "").strip() or muni_nombre
        extra = {}
        if norm_key(ent_nombre) != norm_key(muni_nombre):
            extra["municipio_matriz"] = muni_nombre
        out.append(row(ine, ent_nombre, "MADRID", fecha, "", F, **extra))
    REP.note(F, "las entidades locales menores (entidad_codigo != 00) llevan el INE de su municipio "
                "matriz y el campo extra municipio_matriz")
    return out


# ---------------------------------------------------------------------------
# 4. ANDALUCIA  (and.csv)
# ---------------------------------------------------------------------------

_AND_GENERIC = re.compile(r"^\s*fiesta\s+local\s+en\s+.+$", re.IGNORECASE)


def parse_and():
    F = "AND"
    out = []
    txt, _ = read_text(os.path.join(SRC, "and.csv"))
    for r in csv.DictReader(io.StringIO(txt), delimiter="|"):
        if (r.get("type") or "").strip().upper() != "LOCAL":
            continue
        if (r.get("year") or "").strip() != str(YEAR):
            continue
        raw = (r.get("date") or "").strip()
        if not re.match(r"^\d{8}$", raw):
            REP.discard(F, "fecha ilegible")
            continue
        fecha = mk_date(int(raw[:4]), raw[4:6], raw[6:8])
        if not fecha or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha invalida o de otro anyo")
            continue
        muni = (r.get("municipality") or "").strip()
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        desc = squash(r.get("description") or "")
        nombre = "" if _AND_GENERIC.match(desc) else desc
        out.append(row("", muni, (r.get("province") or "").strip(), fecha, nombre, F))
    REP.note(F, "la fuente no trae INE y la descripcion es siempre 'FIESTA LOCAL EN X (PROV)', "
                "asi que el nombre de la fiesta queda vacio")
    return out


# ---------------------------------------------------------------------------
# 5. PAIS VASCO  (eus_2026.json)
# ---------------------------------------------------------------------------

_EUS_NO_LOCAL = {norm_key(x) for x in
                 ("CAE", "EAE", "Todos/denak", "Araba/Alava", "Alava - Araba",
                  "Araba", "Alava", "Bizkaia", "Gipuzkoa")}


def parse_pv():
    F = "PV"
    out = []
    txt, _ = read_text(os.path.join(SRC, "eus_%d.json" % ANIO))
    data = json.loads(txt)
    for r in data:
        muni = squash(r.get("municipalityEs") or "")
        terr = squash(r.get("territory") or "")
        if not muni or norm_key(muni) in _EUS_NO_LOCAL or norm_key(muni) == norm_key(terr):
            REP.discard(F, "festivo autonomico o de territorio, no local")
            continue
        raw = (r.get("date") or "").strip()
        m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", raw)
        if not m:
            REP.discard(F, "fecha ilegible")
            continue
        fecha = mk_date(int(m.group(1)), m.group(2), m.group(3))
        if not fecha or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha invalida o de otro anyo")
            continue
        out.append(row("", muni, terr, fecha, r.get("descripcionEs") or "", F))
    REP.note(F, "municipalitycode es codigo EUSTAT, NO es INE: se deja ine vacio a proposito")
    return out


# ---------------------------------------------------------------------------
# 6. GALICIA  (gal_2026.csv)
# ---------------------------------------------------------------------------

def parse_gal():
    F = "GAL"
    out = []
    txt, _ = read_text(os.path.join(SRC, "gal_%d.csv" % ANIO))
    for r in csv.DictReader(io.StringIO(txt), delimiter=";"):
        if (r.get("ambito") or "").strip().lower() != "municipal":
            continue
        fecha = (r.get("fecha") or "").strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha) or not fecha.startswith(str(YEAR)):
            REP.discard(F, "fecha ilegible o de otro anyo")
            continue
        ine = re.sub(r"\D", "", r.get("id_municipio") or "").zfill(5)
        if len(ine) != 5 or ine == "00000":
            ine = ""
        muni = (r.get("lugar") or "").strip()
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        desc = squash(r.get("descripcion") or "")
        nombre = "" if strip_accents(desc.lower()).startswith("festa local") else desc
        out.append(row(ine, muni, PROV_BY_INE2.get(ine[:2], ""), fecha, nombre, F))
    return out


# ---------------------------------------------------------------------------
# 7. CASTILLA Y LEON  (cyl.csv)
# ---------------------------------------------------------------------------

def parse_cyl():
    F = "CYL"
    out = []
    txt, _ = read_text(os.path.join(SRC, "cyl.csv"), ("utf-8-sig", "utf-8", "latin-1"))
    for r in csv.DictReader(io.StringIO(txt), delimiter=";"):
        fecha = (r.get("fecha_fiesta") or "").strip()
        if not fecha:
            REP.discard(F, "sin fecha en el origen (fiesta movil descrita en prosa o celda vacia)")
            continue
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
            REP.discard(F, "fecha ilegible")
            continue
        if not fecha.startswith(str(YEAR)):
            continue                       # el fichero es multi-anyo
        ine = re.sub(r"\D", "", r.get("ine") or "").zfill(5)
        if len(ine) != 5 or ine == "00000":
            ine = ""
        muni = (r.get("municipio") or "").strip()
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        nf = squash(r.get("nombre_fiesta") or "")
        nombre = "" if strip_accents(nf.upper()) == "FIESTA LOCAL" else nf
        prov = (r.get("provincia") or "").strip().upper() or PROV_BY_INE2.get(ine[:2], "")
        out.append(row(ine, muni, prov, fecha, nombre, F))
    REP.note(F, "la columna 'municipio' es en realidad la localidad; varias localidades comparten INE")
    return out


# ---------------------------------------------------------------------------
# 8. NAVARRA  (nav_2026.csv)
# ---------------------------------------------------------------------------

def parse_nav():
    F = "NAV"
    out = []
    txt, _ = read_text(os.path.join(SRC, "nav_%d.csv" % ANIO), ("latin-1",))
    for r in csv.DictReader(io.StringIO(txt)):
        loc = squash(r.get("LOCALIDAD") or "")
        if not loc:
            continue
        dia = (r.get("DIA") or "").strip()
        mes = month_from_word(r.get("MES") or "")
        if not dia.isdigit() or mes is None:
            REP.discard(F, "fecha movil descrita en prosa (ej. 'Tercer sabado de septiembre'), "
                           "sin dia concreto: no se inventa")
            continue
        fecha = mk_date(YEAR, mes, dia)
        if not fecha:
            REP.discard(F, "fecha invalida")
            continue
        extra = {}
        muni = loc
        if " / " in loc:
            a, b = [x.strip() for x in loc.split(" / ", 1)]
            extra["alias"] = b
        notas = squash(r.get("NOTAS") or "")
        nombre = "" if notas in ("", "*") else notas
        out.append(row("", muni, "NAVARRA", fecha, nombre, F, **extra))
    REP.note(F, "el 3 de diciembre (San Francisco Javier) es autonomico en toda Navarra y NO se anyade aqui")
    return out


# ---------------------------------------------------------------------------
# 9. ASTURIAS  (ast.csv, separador \xa7)
# ---------------------------------------------------------------------------

def parse_ast():
    F = "AST"
    out = []
    seen = set()
    txt, _ = read_text(os.path.join(SRC, "ast.csv"), ("latin-1",))
    for r in csv.DictReader(io.StringIO(txt), delimiter="\xa7"):
        if (r.get("AMBITO") or "").strip().upper() != "LOCAL":
            continue
        raw = (r.get("FECHA") or "").strip()
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
        if not m:
            REP.discard(F, "fecha ilegible")
            continue
        if m.group(3) != str(YEAR):
            continue                       # el fichero es multi-anyo
        fecha = mk_date(YEAR, m.group(2), m.group(1))
        if not fecha:
            REP.discard(F, "fecha invalida")
            continue
        muni = squash(r.get("COMUNIDAD - MUNICIPIO") or "")
        if not muni:
            REP.discard(F, "sin nombre de municipio")
            continue
        key = (norm_key(muni), fecha)
        if key in seen:
            REP.discard(F, "duplicado exacto en el origen (mismo municipio y misma fecha)")
            continue
        seen.add(key)
        out.append(row("", muni, "ASTURIAS", fecha,
                       squash(r.get("FIESTA - LOCALIDAD") or ""), F))
    REP.note(F, "algunos concejos (Llanes, Pilona, Salas, Mieres, Siero, Tineo, Valdes) "
                "declaran fechas distintas por parroquia y salen con 3-6 filas: es como "
                "viene en el origen, no es un fallo del parser")
    return out


# ---------------------------------------------------------------------------
# 10. BALEARES  (bal_2026.csv, fecha en catalan sin anyo)
# ---------------------------------------------------------------------------

_BAL_DATE = re.compile(r"^(\d{1,2})\s*d(?:e\s+|')\s*([A-Za-zZÀ-ÿ]+)\s*$")


def parse_bal():
    F = "BAL"
    out = []
    txt, _ = read_text(os.path.join(SRC, "bal_%d.csv" % ANIO), ("latin-1", "utf-8"))
    txt = txt.replace("’", "'")
    rd = csv.DictReader(io.StringIO(txt))
    col_amb = col_data = col_muni = col_loc = col_nom = None
    for c in rd.fieldnames or []:
        k = norm_key(c)
        if k == "ambit":
            col_amb = c
        elif k == "data":
            col_data = c
        elif k == "municipi":
            col_muni = c
        elif k == "localitat":
            col_loc = c
        elif k == "nomfesta":
            col_nom = c
    if not (col_amb and col_data and col_muni):
        raise RuntimeError("bal_2026.csv: cabeceras inesperadas -> %r" % (rd.fieldnames,))

    for r in rd:
        if norm_key(r.get(col_amb) or "") != "local":
            continue
        raw = squash(r.get(col_data) or "").replace("’", "'")
        m = _BAL_DATE.match(raw)
        if not m:
            REP.discard(F, "fecha en catalan que no encaja con el patron 'N de mes' (ej. %r)" % raw)
            continue
        mes = MESES_CA.get(strip_accents(m.group(2).lower()))
        if mes is None:
            mes = month_from_word(m.group(2))   # el fichero mezcla 'agost' y 'agosto'
        if mes is None:
            REP.discard(F, "mes desconocido (%r)" % m.group(2))
            continue
        fecha = mk_date(YEAR, mes, m.group(1))
        if not fecha:
            REP.discard(F, "fecha invalida")
            continue
        muni = squash(r.get(col_muni) or "")
        loc = squash(r.get(col_loc) or "") if col_loc else ""
        extra = {}
        if loc and norm_key(loc) != norm_key(muni):
            extra["localidad"] = loc
        nombre = squash(r.get(col_nom) or "") if col_nom else ""
        if _BAL_DATE.match(nombre.replace("’", "'")):
            nombre = ""      # en varias filas el 'Nom festa' repite la fecha
        out.append(row("", muni, "ILLES BALEARS", fecha, nombre, F, **extra))
    REP.note(F, "la fuente da la fecha en catalan y sin anyo ('29 de juny'); se le pone 2026")
    return out


# ---------------------------------------------------------------------------
# 11. CASTILLA-LA MANCHA  (clm_2026.html, tablas del DOCM)
# ---------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")


def html_text(fragment):
    import html as _html
    t = _TAG.sub(" ", fragment)
    t = _html.unescape(t)
    return squash(t.replace("\xa0", " "))


def parse_clm():
    F = "CLM"
    out = []
    txt, _ = read_text(os.path.join(SRC, "clm_%d.html" % ANIO))
    prov = ""
    for tr in re.findall(r"<tr\b.*?</tr>", txt, re.S):
        tds = re.findall(r"<td\b.*?</td>", tr, re.S)
        cells = [html_text(td) for td in tds]
        cells = [c for c in cells if c]
        if not cells:
            continue
        if len(cells) == 1:
            m = re.search(r"fiestas\s+locales\s+de\s+(.+)$", cells[0], re.IGNORECASE)
            if m:
                prov = squash(m.group(1)).upper().rstrip(".")
            continue
        if len(cells) < 2:
            continue
        muni, datestr = cells[0], cells[1]
        if norm_key(muni) in ("municipios", "municipio") or norm_key(datestr) in ("fiestas", "fiesta"):
            continue
        fechas, huerf = extract_dates_es(datestr)
        if not fechas:
            REP.discard(F, "celda de fechas sin fecha reconocible (ej. %r)" % datestr[:60])
            continue
        if huerf:
            REP.discard(F, "numero suelto sin mes detras en la celda de fechas", len(huerf))
        for f in fechas:
            out.append(row("", muni, prov, f, "", F))
    return out


# ---------------------------------------------------------------------------
# 12. CANARIAS  (can_2026.html, BOC)
# ---------------------------------------------------------------------------

_CAN_MUNI = re.compile(r"^([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ0-9 ,'\.\-/]*[A-ZÁÉÍÓÚÜÑ\.])\.?$")
_CAN_FEST = re.compile(r"^(\d{1,2})\s+(?:de\s+)?([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)\s*:\s*(.*)$")


def parse_can():
    F = "CAN"
    out = []
    txt, _ = read_text(os.path.join(SRC, "can_%d.html" % ANIO))
    paras = [html_text(p) for p in
             re.findall(r"<p class=\"justificado\"[^>]*>(.*?)</p>", txt, re.S)]

    # El anexo empieza tras 'RELACION DE FIESTAS LOCALES PARA EL ANO 2026'
    start = 0
    for i, p in enumerate(paras):
        if strip_accents(p.upper()).startswith("RELACION DE FIESTAS LOCALES"):
            start = i + 1
            break
    if not start:
        raise RuntimeError("can_2026.html: no encuentro el encabezado del anexo")

    muni = ""
    for p in paras[start:]:
        if not p:
            continue
        mf = _CAN_FEST.match(p)
        if mf:
            if not muni:
                REP.discard(F, "fecha antes de conocer el municipio")
                continue
            mes = month_from_word(mf.group(2))
            fecha = mk_date(YEAR, mes, mf.group(1)) if mes else None
            if not fecha:
                REP.discard(F, "fecha ilegible (%r)" % p[:60])
                continue
            nombre = squash(mf.group(3)).rstrip(".")
            out.append(row("", muni, "", fecha, nombre, F))
            continue
        mm = _CAN_MUNI.match(p)
        if mm and len(p) < 70:
            muni = squash(mm.group(1)).rstrip(".")
            continue
        REP.discard(F, "parrafo del anexo que no es ni municipio ni fecha")
    REP.note(F, "el BOC no indica la provincia de cada municipio: provincia queda vacia a proposito")
    return out


# ---------------------------------------------------------------------------
# Lectura de PDFs
# ---------------------------------------------------------------------------

def pdf_pages(name, layout=False):
    from pypdf import PdfReader
    reader = PdfReader(os.path.join(SRC, name))
    pages = []
    for p in reader.pages:
        if layout:
            t = p.extract_text(extraction_mode="layout")
        else:
            t = p.extract_text()
        pages.append(clean_text(t or ""))
    return pages


def dump_pdf_text(name, pages, suffix=""):
    """Vuelca el texto extraido a es_src/_<name>.txt para poder inspeccionarlo."""
    path = os.path.join(SRC, "_%s%s.txt" % (os.path.splitext(name)[0], suffix))
    with io.open(path, "w", encoding="utf-8") as f:
        for i, t in enumerate(pages):
            f.write(u"===== PAGE %d =====\n" % i)
            f.write(t)
            f.write(u"\n")


# ---------------------------------------------------------------------------
# 13. COMUNIDAD VALENCIANA  (val_2026.pdf, DOGV)
# ---------------------------------------------------------------------------

_VAL_PROV = re.compile(r"RELACI[OÓ]N DE FIESTAS LOCALES EN LA PROVINCIA DE\s+(.+?)\s*\d{4}\s*$",
                       re.IGNORECASE)
_VAL_HEAD = re.compile(r"^([^:]{2,80}?)\s*:\s*(.*)$")
_VAL_NOISE = re.compile(r"^(N[uú]m\.|CVE:|https?://|Signat|Firmado)", re.IGNORECASE)
_VAL_DATE = re.compile(
    r"(\d{1,2})(?:\s*y\s*(\d{1,2}))?\s+(?:de\s+)?(" + "|".join(MESES_ES) + r")",
    re.IGNORECASE)


def _val_is_head(prefix):
    """
    Decide si 'algo:' abre municipio o es solo un ':' dentro de una linea.

    En el anexo del DOGV el municipio va SIEMPRE en mayusculas, aunque lleve
    preposiciones en minuscula ('HONDON de los FRAILES'), y las entidades
    locales menores se anuncian con la palabra 'Eatim'.
    """
    p = fix_pdf_spacing(prefix.strip())
    if not p or len(p.split()) > 8:
        return False
    if re.search(r"\beatim\b", p, re.IGNORECASE):
        return True
    for tok in p.split():
        tok = re.sub(r"[^A-Za-zÁÉÍÓÚÜÑÀÈÒÇàèòçáéíóúüñ]", "", tok)
        if len(tok) >= 2:
            return tok == tok.upper()
    return False


def parse_val():
    F = "VAL"
    out = []
    pages = pdf_pages("val_%d.pdf" % ANIO)
    dump_pdf_text("val_%d.pdf" % ANIO, pages)

    lines = []
    for t in pages:
        lines.extend(t.split("\n"))

    started = False
    prov = ""
    records = []          # (prov, prefijo, cuerpo)
    for raw in lines:
        ln = squash(raw)
        if not ln or _VAL_NOISE.match(ln):
            continue
        mp = _VAL_PROV.search(ln)
        if mp:
            prov = fix_pdf_spacing(squash(mp.group(1)).upper())
            started = True
            continue
        if not started:
            continue
        mh = _VAL_HEAD.match(ln)
        if mh and _val_is_head(mh.group(1)):
            records.append([prov, fix_pdf_spacing(squash(mh.group(1))), squash(mh.group(2))])
        elif records:
            records[-1][2] += " " + ln
        else:
            REP.discard(F, "linea del anexo antes del primer municipio")

    if not records:
        raise RuntimeError("val_2026.pdf: no he podido reconstruir ningun municipio")

    for prov, muni, body in records:
        body = squash(body)
        if not body:
            REP.discard(F, "municipio sin texto de fechas (%r)" % muni[:40])
            continue
        got = 0
        for chunk in re.split(r"\s*;\s*", body):
            chunk = chunk.strip()
            if not chunk:
                continue
            ms = list(_VAL_DATE.finditer(chunk))
            if not ms:
                continue
            for i, m in enumerate(ms):
                end = ms[i + 1].start() if i + 1 < len(ms) else len(chunk)
                nombre = chunk[m.end():end]
                nombre = re.sub(r"^[\s,.:;\-]+", "", nombre)
                nombre = re.sub(r"[\s,.:;\-]+$", "", nombre)
                nombre = re.sub(r"\s+y$", "", nombre).strip()
                if len(nombre) > 120:
                    nombre = ""
                mes = month_from_word(m.group(3))
                for d in (m.group(1), m.group(2)):
                    if not d:
                        continue
                    fecha = mk_date(YEAR, mes, d)
                    if not fecha:
                        REP.discard(F, "fecha invalida en %r" % muni[:40])
                        continue
                    out.append(row("", muni, prov, fecha, nombre, F))
                    got += 1
        if not got:
            if "determinar" in strip_accents(body.lower()):
                REP.discard(F, "el propio DOGV dice 'SIN DETERMINAR': el municipio no ha "
                               "fijado fechas (%s)" % muni[:40])
            else:
                REP.discard(F, "municipio sin ninguna fecha reconocible (%r)" % muni[:40])
    return out


# ---------------------------------------------------------------------------
# 14. MURCIA  (mur_2026.pdf, BORM)
# ---------------------------------------------------------------------------

_DIAS = "Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo"
_MESES_CAP = "|".join(MESES_ES)
_MUR_ROW = re.compile(
    r"^(\d{1,2})\s+(.+?)\s+(?:%s)\s+(\d{1,2})\s+(%s)\s+(?:%s)\s+(\d{1,2})\s+(%s)\s*$"
    % (_DIAS, _MESES_CAP, _DIAS, _MESES_CAP), re.IGNORECASE)


def parse_mur():
    F = "MUR"
    out = []
    pages = pdf_pages("mur_%d.pdf" % ANIO)
    dump_pdf_text("mur_%d.pdf" % ANIO, pages)
    seen_nums = set()
    for t in pages:
        for raw in t.split("\n"):
            ln = squash(raw)
            m = _MUR_ROW.match(ln)
            if not m:
                continue
            num = int(m.group(1))
            if num in seen_nums:
                REP.discard(F, "numero de municipio repetido")
                continue
            muni = fix_pdf_spacing(squash(m.group(2)).rstrip("."))
            pairs = ((m.group(3), m.group(4)), (m.group(5), m.group(6)))
            ok = 0
            for d, mes in pairs:
                fecha = mk_date(YEAR, month_from_word(mes), d)
                if not fecha:
                    REP.discard(F, "fecha invalida en %r" % muni)
                    continue
                out.append(row("", muni, "MURCIA", fecha, "", F))
                ok += 1
            if ok:
                seen_nums.add(num)
    if not out:
        raise RuntimeError("mur_2026.pdf: la tabla de municipios no ha encajado con el patron")
    REP.note(F, "el BORM no da el nombre de la fiesta, solo la fecha")
    return out


# ---------------------------------------------------------------------------
# 15. LA RIOJA  (rio_2026.pdf, BOR -- el texto viene sin espacios)
# ---------------------------------------------------------------------------

_RIO_LINE = re.compile(r"^([^:]{2,70}):(.+)$")
_RIO_DATE = re.compile(
    r"(\d{1,2})(?:y(\d{1,2}))?de(" + "|".join(MESES_ES) + r")(?:\(([^)]*)\))?",
    re.IGNORECASE)
_RIO_PART = re.compile(
    r"(?<=[a-zaeiounc])(delas|delos|dela|del|de|las|los|la|el|en)(?=[A-ZÁÉÍÓÚÜÑ])")

# Como se reparte cada particula pegada al separarla ('delas' -> 'de las')
_RIO_SPLIT = {"delas": ["de", "las"], "delos": ["de", "los"], "dela": ["de", "la"]}


def _rio_unglue(s, dictionary):
    """
    Separa un nombre pegado ('BanosdeRioTobia'). Primero intenta casar contra el
    listado real de municipios de La Rioja; si no casa, aplica una heuristica.
    """
    s = s.strip()
    hit = dictionary.get(norm_key(s))
    if hit:
        return hit, True
    t = re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÁÉÍÓÚÜÑ])", " ", s)
    parts = t.split()
    fixed = []
    for i, tok in enumerate(parts):
        if i < len(parts) - 1:          # nunca al ultimo token: 'Gravalos' no es 'Grava los'
            changed = True
            while changed:
                changed = False
                for part in ("delas", "delos", "dela", "del", "de", "las", "los", "la", "el", "en"):
                    low = strip_accents(tok.lower())
                    if low.endswith(part) and len(tok) - len(part) >= 3:
                        fixed.append(tok[len(tok) - len(part):].lower())
                        tok = tok[:len(tok) - len(part)]
                        changed = True
                        break
            fixed.append(tok)
            # los particulas se han ido apilando al reves para este token
            k = len(fixed)
            j = k - 1
            start = j
            while start > 0 and fixed[start - 1] in ("delas", "delos", "dela", "del",
                                                     "de", "las", "los", "la", "el", "en"):
                start -= 1
            fixed[start:k] = [fixed[k - 1]] + list(reversed(fixed[start:k - 1]))
        else:
            fixed.append(tok)
    res = " ".join(x for x in fixed if x)
    res = res.replace("dela ", "de la ").replace("delas ", "de las ").replace("delos ", "de los ")
    return squash(res), False


def _rio_dictionary():
    """Listado de municipios de La Rioja a partir de cp_es_join.csv (si existe)."""
    d = {}
    path = os.path.join(FUENTES, "cp_es_join.csv")
    if not os.path.exists(path):
        return d
    try:
        txt, _ = read_text(path)
        for r in csv.DictReader(io.StringIO(txt)):
            mid = (r.get("municipio_id") or "").strip()
            nom = squash(r.get("nombre") or "")
            if mid.startswith("26") and nom:
                d.setdefault(norm_key(nom), nom)
    except Exception:
        return {}
    return d


def parse_rio():
    F = "RIO"
    out = []
    pages = pdf_pages("rio_%d.pdf" % ANIO)
    pages = [p.replace("\uffff", "") for p in pages]
    dump_pdf_text("rio_%d.pdf" % ANIO, pages)
    dic = _rio_dictionary()
    REP.note(F, "el PDF del BOR sale sin espacios; los nombres se despegan contra el listado "
                "de municipios de La Rioja (%d nombres) y, si no casa, por heuristica" % len(dic))
    matched = 0
    heur = 0
    for t in pages:
        for raw in t.split("\n"):
            ln = squash(raw).replace("\uffff", "")
            if not ln or ":" not in ln:
                continue
            m = _RIO_LINE.match(ln)
            if not m:
                continue
            name_raw = m.group(1).strip().rstrip(";")
            rest = m.group(2)
            if not name_raw or not name_raw[0].isupper():
                continue
            ms = list(_RIO_DATE.finditer(rest))
            if not ms:
                REP.discard(F, "linea sin fecha concreta (ej. %r)" % ln[:70])
                continue
            muni, from_dict = _rio_unglue(name_raw, dic)
            if from_dict:
                matched += 1
            else:
                heur += 1
            for mm in ms:
                mes = month_from_word(mm.group(3))
                nombre_raw = mm.group(4) or ""
                if norm_key(nombre_raw) in ("fiestaslocales", "fiestalocal", ""):
                    nombre = ""
                else:
                    # mismo problema de texto pegado que en el nombre del municipio
                    nombre = re.sub(
                        r"(?<=[a-zà-ÿ])(delas|delos|dela|del|de|las|los|la|el|y)"
                        r"(?=[A-ZÁÉÍÓÚÜÑ])",
                        lambda m: " " + " ".join(_RIO_SPLIT.get(m.group(1),
                                                                [m.group(1)])) + " ",
                        nombre_raw)
                    nombre = squash(re.sub(r"(?<=[a-zà-ÿ])(?=[A-ZÁÉÍÓÚÜÑ])", " ", nombre))
                for d in (mm.group(1), mm.group(2)):
                    if not d:
                        continue
                    fecha = mk_date(YEAR, mes, d)
                    if not fecha:
                        REP.discard(F, "fecha invalida en %r" % muni)
                        continue
                    out.append(row("", muni, "LA RIOJA", fecha, nombre, F))
    REP.note(F, "nombres despegados: %d por diccionario, %d por heuristica" % (matched, heur))
    return out


# ---------------------------------------------------------------------------
# 16. CANTABRIA  (cnt_2026.pdf, BOC -- tabla de 4 columnas)
# ---------------------------------------------------------------------------

def parse_cnt():
    F = "CNT"
    out = []
    pages = pdf_pages("cnt_%d.pdf" % ANIO, layout=True)
    dump_pdf_text("cnt_%d.pdf" % ANIO, pages, "_layout")
    started = False
    muni = ""
    for t in pages:
        for raw in t.split("\n"):
            ln = raw.rstrip()
            if not ln.strip():
                continue
            if not started:
                if strip_accents(ln.upper()).strip().startswith("FIESTAS LOCALES"):
                    started = True
                continue
            m = re.match(r"^(?P<left>.*?)\s+(?P<dia>\d{1,2})\s+(?P<mes>[A-Za-zÁÉÍÓÚÜÑ]+)\s*$",
                         ln.rstrip())
            if not m:
                continue
            mes = month_from_word(m.group("mes"))
            dia = m.group("dia")
            if mes is None:
                continue                       # cabecera de tabla o pie de pagina
            # La columna AYUNTAMIENTO y la columna FESTIVIDAD estan separadas por
            # un hueco ancho; dentro de un nombre nunca hay 3 espacios seguidos.
            cols = [x for x in re.split(r"\s{3,}", m.group("left").strip()) if x]
            if len(cols) >= 2:
                muni = fix_pdf_spacing(squash(cols[0]).rstrip("."))
                fest = squash(" ".join(cols[1:]))
            elif len(cols) == 1:
                fest = squash(cols[0])         # linea de continuacion
            else:
                continue
            if not muni:
                REP.discard(F, "fila sin municipio conocido")
                continue
            fecha = mk_date(YEAR, mes, dia)
            if not fecha:
                REP.discard(F, "fecha invalida en %r" % muni)
                continue
            nombre = "" if fest in ("-", "--", "") else fest
            out.append(row("", muni, "CANTABRIA", fecha, nombre, F))
    if not out:
        raise RuntimeError("cnt_2026.pdf: la tabla de fiestas locales no ha encajado")
    return out


# ---------------------------------------------------------------------------
# 17. EXTREMADURA  (ext_2026.pdf, DOE)
# ---------------------------------------------------------------------------

_EXT_LINE = re.compile(r"^(.{2,70}?)\.\-\s*(.+)$")
_EXT_PROV = re.compile(r"^La provincia de\s+(.+?)\.?\s*$", re.IGNORECASE)


def parse_ext():
    F = "EXT"
    out = []
    pages = pdf_pages("ext_%d.pdf" % ANIO)
    dump_pdf_text("ext_%d.pdf" % ANIO, pages)
    prov = ""
    for t in pages:
        for raw in t.split("\n"):
            ln = squash(raw)
            if not ln:
                continue
            mp = _EXT_PROV.match(ln)
            if mp:
                prov = squash(mp.group(1)).upper().rstrip(".")
                continue
            m = _EXT_LINE.match(ln)
            if not m:
                continue
            muni = fix_pdf_spacing(squash(m.group(1)))
            fechas, huerf = extract_dates_es(m.group(2))
            if not fechas:
                REP.discard(F, "linea con '.-' pero sin fechas (%r)" % ln[:60])
                continue
            if huerf:
                REP.discard(F, "numero suelto sin mes detras", len(huerf))
            for f in fechas:
                out.append(row("", muni, prov, f, "", F))
    if not out:
        raise RuntimeError("ext_2026.pdf: no he reconocido ninguna linea de municipio")
    REP.note(F, "el DOE no da el nombre de la fiesta, solo las dos fechas")
    return out


# ---------------------------------------------------------------------------
# Control de calidad
# ---------------------------------------------------------------------------

PARSERS = [
    ("CAT", "Cataluna", parse_cat),
    ("ARA", "Aragon", parse_ara),
    ("MAD", "Madrid", parse_mad),
    ("AND", "Andalucia", parse_and),
    ("PV", "Pais Vasco", parse_pv),
    ("GAL", "Galicia", parse_gal),
    ("CYL", "Castilla y Leon", parse_cyl),
    ("CLM", "Castilla-La Mancha", parse_clm),
    ("NAV", "Navarra", parse_nav),
    ("RIO", "La Rioja", parse_rio),
    ("CNT", "Cantabria", parse_cnt),
    ("AST", "Asturias", parse_ast),
    ("EXT", "Extremadura", parse_ext),
    ("BAL", "Illes Balears", parse_bal),
    ("CAN", "Canarias", parse_can),
    ("VAL", "Comunitat Valenciana", parse_val),
    ("MUR", "Murcia", parse_mur),
]


def muni_key(r):
    """
    Clave de municipio para el control de calidad.

    Incluye la provincia (hay municipios homonimos: 'Fuentes' existe en Cuenca
    y en Toledo) y las entidades submunicipales que algunas fuentes listan
    aparte (localitat en Baleares, alias en Navarra, entidad menor en Madrid):
    si no, esos municipios salen con 4, 6 u 8 festivos y falsean la media.
    """
    sub = r.get("localidad") or r.get("alias") or ""
    return (r["fuente"], r.get("ine") or "", norm_key(r["provincia"]),
            norm_key(r["municipio"]), norm_key(sub))


# Comunidades cuya media != 2 NO es un fallo del parser, sino de la fuente.
MEDIA_ESPERADA = {
    "NAV": (1.0, "en Navarra el segundo festivo local es el 3 de diciembre "
                 "(San Francisco Javier) para toda la comunidad, y es autonomico: "
                 "no se anyade aqui. Media 1.00 es lo correcto."),
    "PV": (1.0, "el dataset de Open Data Euskadi solo publica UN festivo local "
                "por municipio (284 filas, 284 municipios). Es una limitacion "
                "de la fuente, no del parser: falta el segundo festivo."),
}


CHECKS = [
    # (titulo, fuente, municipio, fechas exigidas o None = al menos dos, INE esperado)
    ("Murcia debe tener el 15/09/2026", "MUR", "Murcia", ["2026-09-15"], "30030"),
    ("Zaragoza debe tener dos fechas", "ARA", "Zaragoza", None, "50297"),
    ("Barcelona", "CAT", "Barcelona", None, "08019"),
    ("Sevilla", "AND", "Sevilla", None, ""),
    ("Valencia", "VAL", "Valencia", None, ""),
    ("Bilbao", "PV", "Bilbao", None, ""),
    ("Vigo", "GAL", "Vigo", None, "36057"),
    ("Badajoz debe tener 17/02 y 24/06", "EXT", "Badajoz",
     ["2026-02-17", "2026-06-24"], ""),
]

# Fuentes que NO publican el codigo INE; ahi el campo `ine` va vacio a proposito
# y el cruce por nombre queda para el paso siguiente del pipeline.
SIN_INE = ["AND", "PV", "NAV", "CLM", "CAN", "VAL", "MUR", "RIO", "CNT",
           "AST", "EXT", "BAL"]


def build_report(rows, per_source, durations):
    L = []
    w = L.append
    w(u"=" * 78)
    w(u"FESTIVOS LOCALES DE ESPANA 2026 - INFORME DE PARSEO")
    w(u"=" * 78)
    w(u"")
    w(u"Total de filas obtenidas: %d" % len(rows))
    w(u"Municipios distintos:     %d" % len({muni_key(r) for r in rows}))
    w(u"Filas sin INE:            %d (%.1f%%)" % (
        sum(1 for r in rows if not r["ine"]),
        100.0 * sum(1 for r in rows if not r["ine"]) / max(1, len(rows))))
    w(u"")

    # ---- resumen por comunidad -------------------------------------------
    w(u"-" * 78)
    w(u"RESUMEN POR COMUNIDAD")
    w(u"-" * 78)
    w(u"%-5s %-22s %7s %8s %8s %8s %7s" %
      ("CODE", "COMUNIDAD", "FILAS", "MUNIS", "MEDIA", "SIN INE", "DESCART"))
    for code, nombre, _ in PARSERS:
        rs = per_source.get(code, [])
        munis = {muni_key(r) for r in rs}
        desc = sum(n for (f, _m), n in REP.discards.items() if f == code)
        media = (len(rs) / float(len(munis))) if munis else 0.0
        w(u"%-5s %-22s %7d %8d %8.2f %8d %7d" %
          (code, nombre, len(rs), len(munis), media,
           sum(1 for r in rs if not r["ine"]), desc))
    w(u"")

    # ---- aviso de medias sospechosas -------------------------------------
    w(u"-" * 78)
    w(u"AVISOS DE CALIDAD (lo normal es 2 festivos locales por municipio)")
    w(u"-" * 78)
    hay_aviso = False
    for code, nombre, _ in PARSERS:
        rs = per_source.get(code, [])
        munis = {muni_key(r) for r in rs}
        if not rs:
            w(u"[VACIA]  %s (%s): 0 filas. Ver la seccion de errores." % (nombre, code))
            hay_aviso = True
            continue
        media = len(rs) / float(len(munis))
        if code in MEDIA_ESPERADA:
            esperada, motivo = MEDIA_ESPERADA[code]
            hay_aviso = True
            estado = u"ESPERADA" if abs(media - esperada) < 0.15 else u"DUDOSA"
            w(u"[%s] %s (%s): media %.2f. %s" % (estado, nombre, code, media, motivo))
            continue
        if media < 1.6 or media > 2.6:
            hay_aviso = True
            w(u"[DUDOSA] %s (%s): media %.2f festivos por municipio. "
              u"Sospechoso: revisar el parser o la fuente." % (nombre, code, media))
    if not hay_aviso:
        w(u"Ninguna comunidad se sale del rango 1.6 - 2.6 de media.")
    w(u"")

    # ---- distribucion global de festivos por municipio --------------------
    cnt = collections.Counter()
    for r in rows:
        cnt[muni_key(r)] += 1
    dist = collections.Counter(cnt.values())
    w(u"-" * 78)
    w(u"DISTRIBUCION: CUANTOS FESTIVOS TIENE CADA MUNICIPIO (global)")
    w(u"-" * 78)
    for k in sorted(dist):
        etiqueta = u"%d festivo%s" % (k, u"" if k == 1 else u"s")
        w(u"  %-14s %6d municipios" % (etiqueta, dist[k]))
    w(u"")

    w(u"-" * 78)
    w(u"DISTRIBUCION POR COMUNIDAD (1 / 2 / 3 / 4+)")
    w(u"-" * 78)
    w(u"%-5s %-22s %7s %7s %7s %7s" % ("CODE", "COMUNIDAD", "1", "2", "3", "4+"))
    for code, nombre, _ in PARSERS:
        rs = per_source.get(code, [])
        c = collections.Counter()
        for r in rs:
            c[muni_key(r)] += 1
        d = collections.Counter(c.values())
        cuatro = sum(v for k, v in d.items() if k >= 4)
        w(u"%-5s %-22s %7d %7d %7d %7d" %
          (code, nombre, d.get(1, 0), d.get(2, 0), d.get(3, 0), cuatro))
    w(u"")

    # ---- descartes --------------------------------------------------------
    w(u"-" * 78)
    w(u"FILAS DESCARTADAS Y POR QUE")
    w(u"-" * 78)
    if not REP.discards:
        w(u"Ninguna.")
    else:
        for (f, motivo), n in sorted(REP.discards.items(), key=lambda x: (x[0][0], -x[1])):
            w(u"  %-5s %6d  %s" % (f, n, motivo))
    w(u"")

    # ---- notas ------------------------------------------------------------
    w(u"-" * 78)
    w(u"NOTAS DE CADA FUENTE")
    w(u"-" * 78)
    for f, texto in REP.notes:
        w(u"  %-5s %s" % (f, texto))
    w(u"")

    # ---- errores ----------------------------------------------------------
    w(u"-" * 78)
    w(u"PARSERS QUE HAN FALLADO")
    w(u"-" * 78)
    if not REP.errors:
        w(u"Ninguno: los 17 parsers han terminado sin excepcion.")
    else:
        for f, tb in REP.errors:
            w(u"  === %s ===" % f)
            for ln in tb.strip().split("\n"):
                w(u"    " + ln)
    w(u"")

    # ---- ejemplos ---------------------------------------------------------
    w(u"-" * 78)
    w(u"LOS 10 PRIMEROS EJEMPLOS DE CADA COMUNIDAD")
    w(u"-" * 78)
    for code, nombre, _ in PARSERS:
        rs = per_source.get(code, [])
        w(u"")
        w(u"  [%s] %s  (%d filas)" % (code, nombre, len(rs)))
        if not rs:
            w(u"    (sin datos)")
            continue
        for r in rs[:10]:
            extra = {k: v for k, v in r.items()
                     if k not in ("ine", "municipio", "provincia", "fecha", "nombre", "fuente")}
            w(u"    %-6s %-32s %-22s %s  %s%s" % (
                r["ine"] or "-", r["municipio"][:32], r["provincia"][:22],
                r["fecha"], (r["nombre"] or "-")[:38],
                (u"  " + json.dumps(extra, ensure_ascii=False)) if extra else u""))
    w(u"")

    # ---- comprobaciones concretas ----------------------------------------
    w(u"=" * 78)
    w(u"COMPROBACIONES CONCRETAS PEDIDAS")
    w(u"=" * 78)
    for titulo, fuente, muni, esperadas, ine_esp in CHECKS:
        hits = [r for r in rows
                if r["fuente"] == fuente and norm_key(r["municipio"]) == norm_key(muni)]
        fechas = sorted({r["fecha"] for r in hits})
        ines = sorted({r["ine"] for r in hits if r["ine"]})
        if not hits:
            w(u"[FALLO] %-40s NO aparece en la salida (%s)" % (titulo, fuente))
            continue
        ok = True
        detalle = u""
        if esperadas:
            faltan = [f for f in esperadas if f not in fechas]
            if faltan:
                ok = False
                detalle = u"  faltan: %s" % ", ".join(faltan)
        elif len(fechas) < 2:
            ok = False
            detalle = u"  solo %d fecha(s)" % len(fechas)
            if fuente in MEDIA_ESPERADA:
                detalle += u" -> NO es fallo del parser: %s" % MEDIA_ESPERADA[fuente][1]
        if ine_esp and ine_esp not in ines:
            detalle += (u"  [INE %s no disponible: %s no publica codigo INE]"
                        % (ine_esp, fuente)) if fuente in SIN_INE else \
                       (u"  [OJO: se esperaba INE %s y hay %s]" % (ine_esp, ines or "-"))
            if fuente not in SIN_INE:
                ok = False
        w(u"[%s] %-40s ine=%-7s fechas=%s%s" % (
            u" OK " if ok else u"FALLO", titulo,
            ",".join(ines) or "-", ", ".join(fechas), detalle))
    w(u"")
    w(u"Nota sobre el INE: lo traen CAT, ARA, MAD, GAL y CYL (y MAD lo compone")
    w(u"como '28' + codigo de municipio). No lo publican: %s." % ", ".join(SIN_INE))
    w(u"En esas comunidades `ine` va vacio a proposito; el cruce por nombre es")
    w(u"el paso siguiente del pipeline, no de este script.")
    w(u"")
    w(u"=" * 78)
    w(u"Tiempos por parser (s): " + ", ".join(
        "%s=%.1f" % (k, v) for k, v in durations))
    w(u"=" * 78)
    return u"\n".join(L)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    import time
    rows = []
    per_source = {}
    durations = []
    for code, nombre, fn in PARSERS:
        t0 = time.time()
        try:
            rs = fn() or []
        except Exception:
            REP.error(code, traceback.format_exc())
            rs = []
            print("FALLO %s (%s): ver el informe" % (code, nombre))
        per_source[code] = rs
        rows.extend(rs)
        durations.append((code, time.time() - t0))
        print("%-5s %-22s %6d filas" % (code, nombre, len(rs)))

    rows.sort(key=lambda r: (r["fuente"], r["provincia"], r["municipio"], r["fecha"]))

    out_json = os.path.join(BUILD, "es_holidays.json")
    with io.open(out_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    texto = build_report(rows, per_source, durations)
    out_txt = os.path.join(BUILD, "es_holidays_report.txt")
    with io.open(out_txt, "w", encoding="utf-8") as f:
        f.write(texto)

    print("")
    print("Escrito %s (%d filas)" % (out_json, len(rows)))
    print("Escrito %s" % out_txt)


if __name__ == "__main__":
    main()
