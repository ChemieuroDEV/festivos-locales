"""Descarga las fuentes oficiales de festivos locales a la carpeta 'fuentes/'.

Cada fuente va aislada: si una cambia de sitio o se cae, se anota y se sigue
con las demas. Lo que NO se hace nunca es dejar un fichero a medias: se baja a
un temporal y solo se renombra si la descarga termino entera y con el tipo de
contenido esperado.

Las URL de Aragon, Euskadi, Galicia, Navarra, Baleares y Castilla-La Mancha
llevan el ano dentro, asi que se construyen a partir de AÑO. Las demas son
fijas y multi-ano. Cuando una comunidad publique el ano siguiente con otra URL,
esto fallara de forma visible (queda en el informe) en vez de publicar datos
viejos como si fueran nuevos.
"""
import io, os, sys, json, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEST = os.path.join(ROOT, "fuentes")
UA = "chemieuro-festivos/1.0 (+https://github.com/ChemieuroDEV/festivos-locales)"
TIMEOUT = 180


def anios():
    env = (os.environ.get("YEARS") or "").strip()
    if env:
        return [int(x) for x in env.replace(" ", "").split(",") if x]
    hoy = datetime.date.today()
    # A partir de septiembre ya interesa el ano siguiente; antes, el actual.
    base = hoy.year + (1 if hoy.month >= 9 else 0)
    return sorted({hoy.year, base})


def fuentes(anio):
    """(nombre de fichero, URL). El ano solo afecta a las que lo llevan dentro."""
    a = anio
    return [
        # --- Espana: datos abiertos autonomicos (URL fija multi-ano)
        ("cat.csv", "https://analisi.transparenciacatalunya.cat/api/views/b4eh-r8up/rows.csv?accessType=DOWNLOAD"),
        ("mad.csv", "https://datos.comunidad.madrid/dataset/f160eb6c-6715-471e-9bc0-38497aae950f/resource/ba59e7e8-3d8d-4221-a5fa-b5e78b82707f/download/festivos_locales.csv"),
        ("and.csv", "https://www.juntadeandalucia.es/ssdigitales/festa/download-pro/dataset-work-calendar.csv"),
        ("cyl.csv", "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/fiestas-locales-calendario-de-fiestas-de-caracter-local/exports/csv?delimiter=;"),
        ("ast.csv", "https://descargas.asturias.es/asturias/opendata/CulturayOcio/calendario/dataset_calendario_festivos.csv"),
        # --- Espana: datos abiertos con el ano en la URL
        ("ara_%d.csv" % a, "https://opendata.aragon.es/datos/catalogo/dataset/f861c5f7-5424-4b3c-90bf-a6d2c2f5b0bd/recurso/5ff8c1f8-fb7e-4343-abba-eb7dbd796dbc/descarga/festivos_aragon_%d_completo.csv" % a),
        ("eus_%d.json" % a, "https://opendata.euskadi.eus/contenidos/ds_eventos/calendario_laboral_%d/opendata/calendario_laboral_%d.json" % (a, a)),
        ("gal_%d.csv" % a, "https://ficheiros-web.xunta.gal/abertos/calendarios/calendario_laboral-%d.csv" % a),
        # --- Espana: boletines oficiales (cambian de URL cada ano: revisar)
        ("nav_%d.csv" % a, "https://datosabiertos.navarra.es/dataset/0cf3088d-a191-45b4-979a-aa6ec709786a/resource/f48e36ae-a700-4796-ab37-9ec0a353cfa1/download/calendario_festivos_por_localidad_%d.csv" % a),
        ("bal_%d.csv" % a, "https://intranet.caib.es/opendatacataleg/dataset/e89fb44b-67f3-4e29-affc-2df135b719e5/resource/edf08154-bbc0-4259-a254-3b0185411354/download/calendari-laboral-%d.csv" % a),
        ("clm_%d.html" % a, "https://docm.jccm.es/docm/verArchivoHtml.do?ruta=2025/12/12/html/2025_9468.html&tipo=rutaDocm"),
        ("can_%d.html" % a, "https://www.gobiernodecanarias.org/boc/2025/165/3029.html"),
        ("val_%d.pdf" % a, "https://dogv.gva.es/datos/2025/11/14/pdf/2025_46326_es.pdf"),
        ("mur_%d.pdf" % a, "https://www.borm.es/services/anuncio/ano/2025/numero/3546/pdf?id=837607"),
        ("rio_%d.pdf" % a, "https://ias1.larioja.org/boletin/Bor_Boletin_visor_Servlet?referencia=36153930-1-PDF-571537"),
        ("cnt_%d.pdf" % a, "https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=428192"),
        ("ext_%d.pdf" % a, "https://doe.juntaex.es/pdfs/doe/2025/2040o/25063799.pdf"),
        # --- Codigos postales y maestros
        ("geo_ES.zip", "https://download.geonames.org/export/zip/ES.zip"),
        ("cp_pt.csv", "https://raw.githubusercontent.com/centraldedados/codigos_postais/master/data/codigos_postais.csv"),
        ("concelhos_pt.csv", "https://raw.githubusercontent.com/centraldedados/codigos_postais/master/data/concelhos.csv"),
        ("comuni_it.json", "https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json"),
        ("subdiv_IT.json", "https://openholidaysapi.org/Subdivisions?countryIsoCode=IT&languageIsoCode=IT"),
        ("subdiv_ES.json", "https://openholidaysapi.org/Subdivisions?countryIsoCode=ES&languageIsoCode=ES"),
        # --- Portugal: feriados municipales ya resueltos por ano
        ("icalendario_pt.html", "https://icalendario.pt/feriados/municipais/"),
    ]


def bajar(nombre, url):
    destino = os.path.join(DEST, nombre)
    tmp = destino + ".tmp"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r, io.open(tmp, "wb") as fh:
        datos = r.read()
        if not datos:
            raise ValueError("respuesta vacia")
        if nombre.endswith(".pdf") and not datos.startswith(b"%PDF"):
            raise ValueError("no es un PDF")
        if nombre.endswith(".zip") and not datos.startswith(b"PK"):
            raise ValueError("no es un ZIP")
        fh.write(datos)
    os.replace(tmp, destino)
    return len(datos)


def main():
    os.makedirs(DEST, exist_ok=True)
    resumen = {"fecha": datetime.date.today().isoformat(), "anios": anios(), "ok": {}, "fallos": {}}

    pendientes = {}
    for a in resumen["anios"]:
        for nombre, url in fuentes(a):
            pendientes[nombre] = url

    for nombre, url in sorted(pendientes.items()):
        try:
            n = bajar(nombre, url)
            resumen["ok"][nombre] = n
            print("OK   %-24s %8d bytes" % (nombre, n), flush=True)
        except Exception as e:
            resumen["fallos"][nombre] = "%s: %s" % (type(e).__name__, e)
            print("FALLO %-24s %s" % (nombre, e), flush=True)

    json.dump(resumen, io.open(os.path.join(DEST, "_descarga.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nDescargadas %d fuentes, %d fallos." % (len(resumen["ok"]), len(resumen["fallos"])))
    # Un fallo suelto no aborta: generar.py trabajara con lo que haya y
    # verificar.py decidira si el resultado es publicable.
    return 0


if __name__ == "__main__":
    sys.exit(main())
