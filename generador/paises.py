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
    # Solo en Baviera, Sajonia y Turingia, y segun la confesion mayoritaria del
    # municipio (Maria Himmelfahrt, Fronleichnam). Pendiente de dato propio:
    # OpenHolidays no lo modela.
    "DE": "Algunos municipios de Baviera, Sajonia y Turingia.",
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
                    "published": iso in con_municipales_publicados}
    for iso, nota in SIN_MUNICIPALES.items():
        out[iso] = {"municipal": False, "note": nota, "published": False}
    for iso in con_country_json:
        out.setdefault(iso, {"municipal": False, "note": "", "published": False})
        out[iso]["countryFeed"] = True
    return out
