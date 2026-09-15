"""Prepara los dos ficheros intermedios de Portugal.

  1. pt_feriados_raw.json  - el feriado municipal de cada uno de los 308
     concelhos, para los proximos tres anos, leido de la tabla publicada en
     icalendario.pt. Esa tabla trae los moviles YA RESUELTOS por ano (el de
     Marinha Grande es la Quinta-feira da Ascensao, que cae distinto cada ano),
     que es justo lo que hace falta y lo que no da ninguna lista estatica.

  2. pt_concelho_cp.json - los prefijos de codigo postal de cada concelho, a
     partir del fichero de codigos postales de CTT publicado por Central de
     Dados. En Portugal el codigo es NNNN-NNN y un concelho agrupa muchos, asi
     que se guardan los cuatro primeros digitos y el feed compara por prefijo.
"""
import io, os, csv, json, re, collections, unicodedata

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = os.path.join(_RAIZ, "fuentes")
BUILD = os.path.join(_RAIZ, "build")
os.makedirs(BUILD, exist_ok=True)


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


def feriados():
    p = os.path.join(FUENTES, "icalendario_pt.html")
    h = io.open(p, encoding="utf-8", errors="replace").read()
    filas = re.findall(r'<tr class="o-table__tr">(.*?)</tr>', h, re.S)
    out = []
    for f in filas:
        muni = re.search(r'data-title="munic[^"]*" class="o-table__th">(.*?)</th>', f)
        dist = re.search(r'data-title="distrito"[^>]*>(.*?)</td>', f)
        nom = re.search(r'data-title="nome"[^>]*>(.*?)</td>', f)
        fechas = re.findall(r'data-title="(\d{4})" data-date="(\d{8})"', f)
        if muni and fechas:
            out.append({"municipio": limpiar(muni.group(1)),
                        "distrito": limpiar(dist.group(1)) if dist else "",
                        "nome": limpiar(nom.group(1)) if nom else "",
                        "dates": {y: d for y, d in fechas}})
    if len(out) < 250:
        raise ValueError("solo %d concelhos: la tabla ha debido de cambiar de formato" % len(out))
    json.dump(out, io.open(os.path.join(BUILD, "pt_feriados_raw.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    return len(out)


def limpiar(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


def codigos_postales():
    conc = {}
    with io.open(os.path.join(FUENTES, "concelhos_pt.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            conc[(r["cod_distrito"], r["cod_concelho"])] = r["nome_concelho"]

    cp4 = collections.defaultdict(set)
    locs = collections.defaultdict(set)
    with io.open(os.path.join(FUENTES, "cp_pt.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = (r["cod_distrito"], r["cod_concelho"])
            cp4[k].add(r["num_cod_postal"])
            locs[k].add((r["nome_localidade"] or "").strip().upper())
            locs[k].add((r["desig_postal"] or "").strip().upper())

    out = {conc[k]: {"cp4": sorted(v), "localidades": sorted(x for x in locs[k] if x)}
           for k, v in cp4.items() if k in conc}
    if len(out) < 250:
        raise ValueError("solo %d concelhos con codigo postal" % len(out))
    json.dump(out, io.open(os.path.join(BUILD, "pt_concelho_cp.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    return len(out)


def main():
    n1 = feriados()
    n2 = codigos_postales()
    print("Portugal: %d concelhos con feriado, %d con codigos postales" % (n1, n2))


if __name__ == "__main__":
    main()
