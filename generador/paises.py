"""Metadatos por pais: que esperar de cada uno.

Existe para que Business Central pueda distinguir dos cosas que no son lo
mismo y que antes se mostraban igual ("sin datos"):

  - "en este pais NO HAY festivos municipales": Francia, Polonia, Paises
    Bajos, Belgica, los nordicos... El concepto no existe, y decir "sin
    festivos locales conocidos" da a entender que falta un dato que en
    realidad no deberia estar. Con lo nacional y regional basta.
  - "en este pais SI los hay y no los tenemos": ahi si hay que avisar.

Y tambien para saber a quien no cubre OpenHolidays API, que es la que da lo
nacional y lo regional. Comprobado el 15/09/2026: devuelve vacio para el Reino
Unido, Finlandia, Dinamarca, Noruega y Grecia. Para esos, el propio feed
publica sus festivos nacionales en _country.json.

Las clasificaciones vienen de una revision pais a pais (dictamen de
2026-09-15), contrastada con la propia API de OpenHolidays y con fuentes
oficiales; los casos dudosos estan comentados.
"""

# Paises con festivos MUNICIPALES reales, con cierre efectivo de empresas.
CON_MUNICIPALES = {
    "ES": "Dos festivos locales por municipio, fijados por cada ayuntamiento.",
    "IT": "Fiesta del santo patron de cada comune.",
    "PT": "Un feriado municipal por concelho.",
    # Maria Himmelfahrt (15 de agosto) en los municipios de mayoria catolica de
    # Baviera y en todo el Sarre; Fronleichnam en los municipios catolicos de
    # Sajonia y Turingia. OpenHolidays no lo modela: el dato sale del buscador
    # oficial del Bayerisches Landesamt fur Statistik y de las normas de cada
    # Land.
    "DE": "Maria Himmelfahrt en Baviera y el Sarre, Fronleichnam en Sajonia y Turingia, segun el municipio.",
    # Cantonales y algunos comunales. OpenHolidays trae solo unos pocos.
    "CH": "Festivos cantonales y, en algunos cantones, comunales.",
    "GR": "Fiesta del santo patron de cada ciudad.",
}

# Paises donde el concepto NO EXISTE: por debajo de lo nacional o regional no
# hay nada. Verificado con OpenHolidays (cero entradas locales) y, en los casos
# que podian inducir a error, con fuente propia:
#   - Austria: cada Land tiene su patron, pero no cierra el sector privado.
#   - Rumania: el "dia de la ciudad" es una conmemoracion, no un dia no laborable.
#   - Francia: lo unico por debajo de lo nacional es Alsacia-Mosela (Viernes
#     Santo y 26 de diciembre), que es DEPARTAMENTAL y OpenHolidays ya lo da.
#   - Reino Unido: Escocia tiene "local holidays" por council, pero no obligan
#     a cerrar. Se deja fuera a proposito para no pintar en rojo dias en los que
#     se entrega con normalidad.
SIN_MUNICIPALES = {
    "FR": "Francia no tiene festivos municipales; lo unico local es Alsacia-Mosela, que es departamental.",
    "GB": "El Reino Unido no tiene festivos municipales de obligado cumplimiento.",
    "PL": "Polonia no tiene festivos municipales.",
    "NL": "Paises Bajos no tiene festivos municipales.",
    "BE": "Belgica no tiene festivos municipales.",
    "IE": "Irlanda no tiene festivos municipales.",
    "AT": "Austria no tiene festivos municipales que obliguen a cerrar.",
    "RO": "Rumania no tiene festivos municipales.",
    "SE": "Suecia no tiene festivos municipales.",
    "FI": "Finlandia no tiene festivos municipales.",
    "DK": "Dinamarca no tiene festivos municipales.",
    "NO": "Noruega no tiene festivos municipales.",
    "CZ": "Chequia no tiene festivos municipales.",
    "HU": "Hungria no tiene festivos municipales.",
    "BG": "Bulgaria no tiene festivos municipales.",
    "HR": "Croacia no tiene festivos municipales.",
    "SK": "Eslovaquia no tiene festivos municipales.",
    "SI": "Eslovenia no tiene festivos municipales.",
    "LT": "Lituania no tiene festivos municipales.",
    "LV": "Letonia no tiene festivos municipales.",
    "EE": "Estonia no tiene festivos municipales.",
    "LU": "Luxemburgo no tiene festivos municipales.",
}

# Paises que OpenHolidays API NO cubre en absoluto (devuelve vacio hasta para
# Navidad). Para estos, el feed publica _country.json con lo nacional.
SIN_OPENHOLIDAYS = ["GB", "FI", "DK", "NO", "GR"]

# Paises cuyo feed es COMPLETO, en el sentido que le importa a quien lo
# consulta: si un municipio de ese pais no aparece en el feed, se puede
# concluir que NO tiene festivos municipales, y no que nos falte el dato.
#
#   - Alemania: el feed es una lista de EXCEPCIONES a proposito. Solo estan los
#     1.879 municipios que tienen Maria Himmelfahrt o Fronleichnam; los otros
#     8.000 y pico no tienen ninguno de los dos, y para ellos basta con los
#     festivos del Land. Que un municipio aleman no aparezca es la respuesta,
#     no una laguna.
#   - Portugal: los 308 concelhos, todos.
#
# Espana e Italia NO estan: ahi faltan municipios de verdad. En Espana, porque
# algunos ayuntamientos aun no han comunicado sus fiestas del ano (Argentona,
# Calaf o Cardona estan en el dataset de 2025 y no en el de 2026). En Italia,
# porque el patron sale del infobox de Wikipedia y no todos los comuni lo
# tienen. En esos dos casos, "no encontrado" si merece un aviso en pantalla.
FEED_COMPLETO = ["DE", "PT"]


def construir(con_municipales_publicados, con_country_json):
    """Metadatos listos para publicar.

    con_municipales_publicados: ISO de los paises para los que el feed tiene
    municipios de verdad en esta pasada.
    con_country_json: ISO de los paises para los que el feed publica sus
    festivos nacionales.
    """
    out = {}
    for iso, nota in CON_MUNICIPALES.items():
        out[iso] = {"municipal": True, "note": nota,
                    "published": iso in con_municipales_publicados,
                    "complete": iso in FEED_COMPLETO}
    for iso, nota in SIN_MUNICIPALES.items():
        out[iso] = {"municipal": False, "note": nota, "published": False}
    for iso in con_country_json:
        out.setdefault(iso, {"municipal": False, "note": "", "published": False})
        out[iso]["countryFeed"] = True
    return out
