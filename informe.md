# Informe de generación

Generado el 2026-09-15. Se regenera con los datos, así que siempre describe lo que hay publicado.

| País | Municipios | Años publicados |
| --- | --- | --- |
| ES | 7207 | 2026 |
| IT | 5354 | 2026, 2027, 2028 |
| PT | 308 | 2026, 2027, 2028 |

Un municipio que no aparece no es un municipio sin festivos: es un municipio del
que no tenemos el dato. Business Central los distingue y lo dice en pantalla.

## Descarga de fuentes

32 bajadas correctamente, **3 con fallo**:

- `cnt_2026.pdf`: URLError: <urlopen error [Errno 110] Connection timed out>
- `cnt_2027.pdf`: URLError: <urlopen error [Errno 110] Connection timed out>
- `eus_2027.json`: HTTPError: HTTP Error 404: Not Found

## España — parseo de las 17 comunidades

```
==============================================================================
FESTIVOS LOCALES DE ESPANA 2026 - INFORME DE PARSEO
==============================================================================

Total de filas obtenidas: 16748
Municipios distintos:     8757
Filas sin INE:            7442 (44.4%)

------------------------------------------------------------------------------
RESUMEN POR COMUNIDAD
------------------------------------------------------------------------------
CODE  COMUNIDAD                FILAS    MUNIS    MEDIA  SIN INE DESCART
CAT   Cataluna                  2794     1398     2.00        0       0
ARA   Aragon                    1355      687     1.97      225       0
MAD   Madrid                     338      169     2.00        0       0
AND   Andalucia                 1548      774     2.00     1548       0
PV    Pais Vasco                   0        0     0.00        0       0
GAL   Galicia                      0        0     0.00        0       0
CYL   Castilla y Leon           5044     2564     1.97        0     122
CLM   Castilla-La Mancha        2058     1030     2.00     2058       0
NAV   Navarra                    655      655     1.00      655      39
RIO   La Rioja                   342      174     1.97      342       1
CNT   Cantabria                    0        0     0.00        0       0
AST   Asturias                   164       78     2.10      164       4
EXT   Extremadura                884      444     1.99      884       0
BAL   Illes Balears              212      107     1.98      212       0
CAN   Canarias                   176       88     2.00      176       0
VAL   Comunitat Valenciana      1088      544     2.00     1088       3
MUR   Murcia                      90       45     2.00       90       0

------------------------------------------------------------------------------
AVISOS DE CALIDAD (lo normal es 2 festivos locales por municipio)
------------------------------------------------------------------------------
[VACIA]  Pais Vasco (PV): 0 filas. Ver la seccion de errores.
[VACIA]  Galicia (GAL): 0 filas. Ver la seccion de errores.
[ESPERADA] Navarra (NAV): media 1.00. en Navarra el segundo festivo local es el 3 de diciembre (San Francisco Javier) para toda la comunidad, y es autonomico: no se anyade aqui. Media 1.00 es lo correcto.
[VACIA]  Cantabria (CNT): 0 filas. Ver la seccion de errores.

------------------------------------------------------------------------------
DISTRIBUCION: CUANTOS FESTIVOS TIENE CADA MUNICIPIO (global)
------------------------------------------------------------------------------
  1 festivo         781 municipios
  2 festivos       7968 municipios
  3 festivos          5 municipios
  4 festivos          1 municipios
  6 festivos          2 municipios

------------------------------------------------------------------------------
DISTRIBUCION POR COMUNIDAD (1 / 2 / 3 / 4+)
------------------------------------------------------------------------------
CODE  COMUNIDAD                    1       2       3      4+
CAT   Cataluna                     2    1396       0       0
ARA   Aragon                      19     668       0       0
MAD   Madrid                       0     169       0       0
AND   Andalucia                    0     774       0       0
PV    Pais Vasco                   0       0       0       0
GAL   Galicia                      0       0       0       0
CYL   Castilla y Leon             84    2480       0       0
CLM   Castilla-La Mancha           3    1026       1       0
NAV   Navarra                    655       0       0       0
RIO   La Rioja                     6     168       0       0
CNT   Cantabria                    0       0       0       0
AST   Asturias                     6      65       4       3
EXT   Extremadura                  4     440       0       0
BAL   Illes Balears                2     105       0       0
CAN   Canarias                     0      88       0       0
VAL   Comunitat Valenciana         0     544       0       0
MUR   Murcia                       0      45       0       0

------------------------------------------------------------------------------
FILAS DESCARTADAS Y POR QUE
------------------------------------------------------------------------------
  AST        2  duplicado exacto en el origen (mismo municipio y misma fecha)
  AST        2  fecha ilegible
  CYL      122  sin fecha en el origen (fiesta movil descrita en prosa o celda vacia)
  NAV       39  fecha movil descrita en prosa (ej. 'Tercer sabado de septiembre'), sin dia concreto: no se inventa
  RIO        1  linea sin fecha concreta (ej. 'RestantesmunicipiosdeLaRioja:lasdosfiestastradicionalesdecadaunodeello')
  VAL        1  el propio DOGV dice 'SIN DETERMINAR': el municipio no ha fijado fechas (SACAÑET)
  VAL        1  el propio DOGV dice 'SIN DETERMINAR': el municipio no ha fijado fechas (VILANOVA D'ALCOLEA)
  VAL        1  el propio DOGV dice 'SIN DETERMINAR': el municipio no ha fijado fechas (PAIPORTA)

------------------------------------------------------------------------------
NOTAS DE CADA FUENTE
------------------------------------------------------------------------------
  CAT   incluye nuclis/pedanies (columna Pedania != 000), que comparten el INE del municipio
  ARA   leido como utf-8-sig
  MAD   las entidades locales menores (entidad_codigo != 00) llevan el INE de su municipio matriz y el campo extra municipio_matriz
  AND   la fuente no trae INE y la descripcion es siempre 'FIESTA LOCAL EN X (PROV)', asi que el nombre de la fiesta queda vacio
  CYL   la columna 'municipio' es en realidad la localidad; varias localidades comparten INE
  NAV   el 3 de diciembre (San Francisco Javier) es autonomico en toda Navarra y NO se anyade aqui
  RIO   el PDF del BOR sale sin espacios; los nombres se despegan contra el listado de municipios de La Rioja (0 nombres) y, si no casa, por heuristica
  RIO   nombres despegados: 0 por diccionario, 174 por heuristica
  AST   algunos concejos (Llanes, Pilona, Salas, Mieres, Siero, Tineo, Valdes) declaran fechas distintas por parroquia y salen con 3-6 filas: es como viene en el origen, no es un fallo del parser
  EXT   el DOE no da el nombre de la fiesta, solo las dos fechas
  BAL   la fuente da la fecha en catalan y sin anyo ('29 de juny'); se le pone 2026
  CAN   el BOC no indica la provincia de cada municipio: provincia queda vacia a proposito
  MUR   el BORM no da el nombre de la fiesta, solo la fecha

------------------------------------------------------------------------------
PARSERS QUE HAN FALLADO
------------------------------------------------------------------------------
  === PV ===
    Traceback (most recent call last):
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 1436, in main
        rs = fn() or []
             ^^^^
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 455, in parse_pv
        txt, _ = read_text(os.path.join(SRC, "eus_%d.json" % ANIO))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 288, in read_text
        with io.open(path, "r", encoding=enc, newline="") as f:
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/festivos-locales/festivos-locales/fuentes/eus_2027.json'
  === CNT ===
    Traceback (most recent call last):
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 1436, in main
        rs = fn() or []
             ^^^^
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 1086, in parse_cnt
        pages = pdf_pages("cnt_%d.pdf" % ANIO, layout=True)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/home/runner/work/festivos-locales/festivos-locales/generador/parse_es.py", line 774, in pdf_pages
        reader = PdfReader(os.path.join(SRC, name))
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/pypdf/_reader.py", line 151, in __init__
        self._initialize_stream(stream)
      File "/opt/hostedtoolcache/Python/3.12.14/x64/lib/python3.12/site-packages/pypdf/_reader.py", line 172, in _initialize_stream
        with open(stream, "rb") as fh:
             ^^^^^^^^^^^^^^^^^^
    FileNotFoundError: [Errno 2] No such file or directory: '/home/runner/work/festivos-locales/festivos-locales/fuentes/cnt_2027.pdf'

------------------------------------------------------------------------------
LOS 10 PRIMEROS EJEMPLOS DE CADA COMUNIDAD
------------------------------------------------------------------------------

  [CAT] Cataluna  (2794 filas)
    08242  Marganell                        BARCELONA              2026-05-11  -
    08001  Abrera                           BARCELONA              2026-05-25  -
    08001  Abrera                           BARCELONA              2026-06-29  -
    08002  Aguilar de Segarra               BARCELONA              2026-05-04  -
    08002  Aguilar de Segarra               BARCELONA              2026-12-07  -
    08003  Alella                           BARCELONA              2026-08-01  -
    08003  Alella                           BARCELONA              2026-05-25  -
    08004  Alpens                           BARCELONA              2026-02-17  -
    08004  Alpens                           BARCELONA              2026-09-28  -
    08005  Ametlla del Vallès, l'           BARCELONA              2026-02-16  -

  [ARA] Aragon  (1355 filas)
    22001  Abiego                           HUESCA                 2026-04-30  -
    22001  Abiego                           HUESCA                 2026-08-14  -
    22002  Abizanda                         HUESCA                 2026-01-12  San Victorián
    22002  Abizanda                         HUESCA                 2026-05-09  San Gregorio
    22003  Adahuesca                        HUESCA                 2026-08-25  Santa Nunilo
    22003  Adahuesca                        HUESCA                 2026-10-22  Santa Alodia
    22004  Agüero                           HUESCA                 2026-02-03  San Blas
    22004  Agüero                           HUESCA                 2026-07-25  Santiago
    22907  Aínsa-Sobrarbe                   HUESCA                 2026-01-20  -
    22907  Aínsa-Sobrarbe                   HUESCA                 2026-09-14  -

  [MAD] Madrid  (338 filas)
    28002  Ajalvir                          MADRID                 2026-02-03  -
    28002  Ajalvir                          MADRID                 2026-05-15  -
    28003  Alameda del Valle                MADRID                 2026-07-17  -
    28003  Alameda del Valle                MADRID                 2026-07-27  -
    28005  Alcalá de Henares                MADRID                 2026-08-06  -
    28005  Alcalá de Henares                MADRID                 2026-10-09  -
    28006  Alcobendas                       MADRID                 2026-01-24  -
    28006  Alcobendas                       MADRID                 2026-05-15  -
    28007  Alcorcón                         MADRID                 2026-04-06  -
    28007  Alcorcón                         MADRID                 2026-09-08  -

  [AND] Andalucia  (1548 filas)
    -      ABLA                             ALMERÍA                2026-04-20  -
    -      ABLA                             ALMERÍA                2026-04-21  -
    -      ABRUCENA                         ALMERÍA                2026-03-19  -
    -      ABRUCENA                         ALMERÍA                2026-05-11  -
    -      ADRA                             ALMERÍA                2026-09-08  -
    -      ADRA                             ALMERÍA                2026-09-10  -
    -      ALBÁNCHEZ                        ALMERÍA                2026-08-17  -
    -      ALBÁNCHEZ                        ALMERÍA                2026-08-18  -
    -      ALBOLODUY                        ALMERÍA                2026-08-17  -
    -      ALBOLODUY                        ALMERÍA                2026-09-14  -

  [PV] Pais Vasco  (0 filas)
    (sin datos)

  [GAL] Galicia  (0 filas)
    (sin datos)

  [CYL] Castilla y Leon  (5044 filas)
    24090  LUCILLO                          LEÓN                   2026-01-02  -
    24117  POZUELO DEL PÁRAMO               LEÓN                   2026-01-02  -
    24066  ROBLEDINO DE LA VALDUERNA        LEÓN                   2026-01-02  -
    24227  VALDESOGO DE ABAJO               LEÓN                   2026-01-02  LA CIRCUNCISIÓN DEL SEÑOR
    24043  CASTRILLO DE CABRERA             LEÓN                   2026-01-05  -
    24172  TRUCHAS                          LEÓN                   2026-01-05  -
    24193  CAMPOHERMOSO                     LEÓN                   2026-01-07  SAN JULIÁN
    24167  CAMPOSALINAS                     LEÓN                   2026-01-07  SAN JULIANO
    24183  CEGOÑAL                          LEÓN                   2026-01-07  -
    24057  CONGOSTO                         LEÓN                   2026-01-07  SAN JULIANO

  [CLM] Castilla-La Mancha  (2058 filas)
    -      Abengibre                        ALBACETE               2026-05-08  -
    -      Abengibre                        ALBACETE               2026-09-29  -
    -      Aguas Nuevas                     ALBACETE               2026-01-17  -
    -      Aguas Nuevas                     ALBACETE               2026-05-15  -
    -      Alatoz                           ALBACETE               2026-05-15  -
    -      Alatoz                           ALBACETE               2026-06-24  -
    -      Albacete                         ALBACETE               2026-06-24  -
    -      Albacete                         ALBACETE               2026-09-08  -
    -      Albatana                         ALBACETE               2026-01-23  -
    -      Albatana                         ALBACETE               2026-05-15  -

  [NAV] Navarra  (655 filas)
    -      ABÁIGAR                          NAVARRA                2026-01-22  -
    -      ABÁRZUZA                         NAVARRA                2026-08-17  -
    -      ABAURREGAINA / ABAURREA ALTA     NAVARRA                2026-06-30  -  {"alias": "ABAURREA ALTA"}
    -      ABAURREPEA / ABAURREA BAJA       NAVARRA                2026-11-14  -  {"alias": "ABAURREA BAJA"}
    -      ABERIN                           NAVARRA                2026-01-20  -
    -      ABÍNZANO                         NAVARRA                2026-05-15  -
    -      ABLITAS                          NAVARRA                2026-07-22  -
    -      ACEDO                            NAVARRA                2026-12-02  -
    -      ADIÓS                            NAVARRA                2026-11-30  -
    -      ADOÁIN                           NAVARRA                2026-12-07  -

  [RIO] La Rioja  (342 filas)
    -      Ábalos                           LA RIOJA               2026-08-03  -
    -      Ábalos                           LA RIOJA               2026-09-08  -
    -      Agoncillo                        LA RIOJA               2026-05-15  -
    -      Agoncillo                        LA RIOJA               2026-09-21  -
    -      Aguilar Río del Alhama           LA RIOJA               2026-05-04  La Cruz
    -      Aguilar Río del Alhama           LA RIOJA               2026-08-17  San Roque
    -      Ajamil de Cameros                LA RIOJA               2026-07-10  San Cristóbal
    -      Ajamil de Cameros                LA RIOJA               2026-08-17  Rosario de las Vacas
    -      Larriba                          LA RIOJA               2026-09-07  San Juan
    -      Torremuña                        LA RIOJA               2026-08-05  La Virgen Blanca

  [CNT] Cantabria  (0 filas)
    (sin datos)

  [AST] Asturias  (164 filas)
    -      ALLANDE                          ASTURIAS               2026-09-09  -
    -      ALLER                            ASTURIAS               2026-11-11  Festividad de San Martin de Los Humani
    -      ALLER                            ASTURIAS               2026-11-26  Festividad del Mercaon de Cabañaquinta
    -      AMIEVA                           ASTURIAS               2026-06-13  San Antonio en Sames
    -      AMIEVA                           ASTURIAS               2026-07-25  Santiago en Vis
    -      AVILES                           ASTURIAS               2026-04-06  Lunes de Pascua
    -      AVILES                           ASTURIAS               2026-08-28  San Agustin
    -      BELMONTE DE MIRANDA              ASTURIAS               2026-05-15  San Isidro
    -      BELMONTE DE MIRANDA              ASTURIAS               2026-08-31  La Gira
    -      BIMENES                          ASTURIAS               2026-10-19  Feries de San Julian

  [EXT] Extremadura  (884 filas)
    -      BADAJOZ                          BADAJOZ                2026-02-17  -
    -      BADAJOZ                          BADAJOZ                2026-06-24  -
    -      ACEDERA                          BADAJOZ                2026-04-06  -
    -      ACEDERA                          BADAJOZ                2026-09-07  -
    -      ACEUCHAL                         BADAJOZ                2026-05-15  -
    -      ACEUCHAL                         BADAJOZ                2026-09-09  -
    -      AHILLONES                        BADAJOZ                2026-05-15  -
    -      AHILLONES                        BADAJOZ                2026-09-14  -
    -      ALANGE                           BADAJOZ                2026-05-15  -
    -      ALANGE                           BADAJOZ                2026-09-12  -

  [BAL] Illes Balears  (212 filas)
    -      Alaró                            ILLES BALEARS          2026-06-24  Sant Joan
    -      Alaró                            ILLES BALEARS          2026-06-29  Sant Pere
    -      Alcúdia                          ILLES BALEARS          2026-06-29  Sant Pere
    -      Alcúdia                          ILLES BALEARS          2026-07-02  Mare de Déu de la Victòria
    -      Algaida                          ILLES BALEARS          2026-01-16  Sant Honorat  {"localidad": "Algaida i Randa"}
    -      Algaida                          ILLES BALEARS          2026-07-25  Sant Jaume  {"localidad": "Algaida i Randa"}
    -      Algaida                          ILLES BALEARS          2026-01-17  Sant Antoni  {"localidad": "Pina"}
    -      Algaida                          ILLES BALEARS          2026-09-26  Sant Cosme i Sant Damià  {"localidad": "Pina"}
    -      Andratx                          ILLES BALEARS          2026-12-07  -
    -      Andratx                          ILLES BALEARS          2026-06-29  -

  [CAN] Canarias  (176 filas)
    -      ADEJE                                                   2026-01-20  Festividad de San Sebastián
    -      ADEJE                                                   2026-02-17  Martes de Carnaval
    -      AGAETE                                                  2026-06-29  Festividad de San Pedro Apóstol
    -      AGAETE                                                  2026-08-05  Festividad de Nuestra Señora de las Ni
    -      AGÜIMES                                                 2026-01-20  Festividad de San Sebastián
    -      AGÜIMES                                                 2026-02-19  Jueves de Carnaval
    -      AGULO                                                   2026-04-27  Festividad de San Marcos Evangelista
    -      AGULO                                                   2026-09-24  Festividad de Nuestra Señora de las Me
    -      ALAJERÓ                                                 2026-07-16  Festividad de Nuestra Señora del Carme
    -      ALAJERÓ                                                 2026-09-15  Festividad de Nuestra Señora del Buen 

  [VAL] Comunitat Valenciana  (1088 filas)
    -      ATZÚBIA, L                       ALICANTE               2026-04-13  San Vicente Ferrer
    -      ATZÚBIA, L                       ALICANTE               2026-09-04  Cristo del Milagro
    -      AGOST                            ALICANTE               2026-03-11  Día de la Vella
    -      AGOST                            ALICANTE               2026-06-29  Festividad de San Pedro Apóstol, Patró
    -      AGRES                            ALICANTE               2026-02-16  -
    -      AGRES                            ALICANTE               2026-09-07  -
    -      AIGÜES                           ALICANTE               2026-08-27  -
    -      AIGÜES                           ALICANTE               2026-08-28  -
    -      ALBATERA                         ALICANTE               2026-04-13  día de San Vicente
    -      ALBATERA                         ALICANTE               2026-07-25  día de Santiago Apóstol

  [MUR] Murcia  (90 filas)
    -      ABANILLA                         MURCIA                 2026-05-04  -
    -      ABANILLA                         MURCIA                 2026-09-14  -
    -      ABARÁN                           MURCIA                 2026-04-07  -
    -      ABARÁN                           MURCIA                 2026-09-28  -
    -      ÁGUILAS                          MURCIA                 2026-02-17  -
    -      ÁGUILAS                          MURCIA                 2026-03-27  -
    -      ALBUDEITE                        MURCIA                 2026-08-31  -
    -      ALBUDEITE                        MURCIA                 2026-09-08  -
    -      ALCANTARILLA                     MURCIA                 2026-05-29  -
    -      ALCANTARILLA                     MURCIA                 2026-09-15  -

==============================================================================
COMPROBACIONES CONCRETAS PEDIDAS
==============================================================================
[ OK ] Murcia debe tener el 15/09/2026          ine=-       fechas=2026-04-07, 2026-09-15  [INE 30030 no disponible: MUR no publica codigo INE]
[ OK ] Zaragoza debe tener dos fechas           ine=50297   fechas=2026-01-29, 2026-03-05
[ OK ] Barcelona                                ine=08019   fechas=2026-05-25, 2026-09-24
[ OK ] Sevilla                                  ine=-       fechas=2026-04-22, 2026-06-04
[ OK ] Valencia                                 ine=-       fechas=2026-01-22, 2026-04-13
[FALLO] Bilbao                                   NO aparece en la salida (PV)
[FALLO] Vigo                                     NO aparece en la salida (GAL)
[ OK ] Badajoz debe tener 17/02 y 24/06         ine=-       fechas=2026-02-17, 2026-06-24

Nota sobre el INE: lo traen CAT, ARA, MAD, GAL y CYL (y MAD lo compone
como '28' + codigo de municipio). No lo publican: AND, PV, NAV, CLM, CAN, VAL, MUR, RIO, CNT, AST, EXT, BAL.
En esas comunidades `ine` va vacio a proposito; el cruce por nombre es
el paso siguiente del pipeline, no de este script.

==============================================================================
Tiempos por parser (s): CAT=0.3, ARA=0.0, MAD=0.0, AND=0.0, PV=0.0, GAL=0.0, CYL=0.1, CLM=0.0, NAV=0.0, RIO=0.4, CNT=0.0, AST=0.0, EXT=0.6, BAL=0.0, CAN=0.0, VAL=0.6, MUR=0.3
==============================================================================
```

## España — cruce con códigos postales

```
municipios con festivos: 7421
cruzados con codigo postal: 7207 ({'nombre': 4808, 'ine': 2399})
sin cruzar: 214
fallos por fuente: {'VAL': 36, 'CYL': 35, 'CLM': 28, 'ARA': 27, 'NAV': 26, 'RIO': 21, 'EXT': 11, 'AND': 10, 'CAT': 8, 'AST': 5, 'MAD': 4, 'BAL': 2, 'CAN': 1}
filas sin provincia deducible: {('CAN', '(vacia)'): 176}

primeros 30 sin cruzar:
  AND  18  EL PINAR
  AND  18  HUÉTOR SANTILLÁN
  AND  18  TORRENUEVA COSTA
  AND  18  VILLA DE OTURA
  AND  21  CORTELAZOR LA REAL
  AND  23  BEJÍJAR
  AND  23  TORREDELCAMPO
  AND  29  LA VIÑUELA
  AND  41  ALANÍS DE LA SIERRA
  AND  41  LANTEJUELA
  ARA  22  Binaced – Valcarca
  ARA  22  Buera y Huerta de Vero
  ARA  22  Cartuja de Monegros
  ARA  22  Coscujuela de Fantova
  ARA  22  Estopiñán del Castillo
  ARA  22  Hoz y Costean (Hoz de Barbastro)
  ARA  22  La Masadera
  ARA  22  Monesma y Cajigar (Noguero)
  ARA  22  Paúl
  ARA  22  Salinas (Bielsa)
  ARA  22  San Juan de Flumen
  ARA  22  San Lorenzo de Flumen
  ARA  22  Santa Cilia de Jaca
  ARA  22  Santa Engracia de Loarre
  ARA  22  Valle de Lierp (Egea)
  ARA  22  Veracruz (Beranuy)
  ARA  22  Viacamp – Litera
  ARA  22  Villanueva de Sijena
  ARA  44  Santa Eulalia del Campo
  ARA  44  Veguillas de la Sierra

claves repetidas: 29  ['TURRILLAS', 'VALSEQUILLO', 'DOMINGO PEREZ', 'CORTEGANA', 'ALINS', 'MONTESA', 'SAN JORGE', 'MIERES', 'MOYA', 'VALVERDE', 'CABANES', 'TORRENT']

CHECK Murcia                 -> [(['30001', '30002'], ['2026-04-07', '2026-09-15'])]
CHECK Zaragoza               -> [(['50001', '50002'], ['2026-01-29', '2026-03-05'])]
CHECK Barcelona              -> [(['08001', '08002'], ['2026-05-25', '2026-09-24'])]
CHECK Madrid                 -> [(['28001', '28002'], ['2026-05-15', '2026-11-09'])]
CHECK Sevilla                -> [(['41001', '41002'], ['2026-04-22', '2026-06-04'])]
CHECK Bilbao                 -> NO CRUZA
CHECK Pamplona               -> [(['31001', '31002'], ['2026-11-30'])]
CHECK Alcantarilla           -> [(['30820'], ['2026-05-29', '2026-09-15'])]
CHECK Molina de Segura       -> [(['30500', '30506'], ['2026-01-22', '2026-09-21'])]
CHECK Ibi                    -> [(['03440'], ['2026-09-11', '2026-09-14'])]
CHECK Arganda del Rey        -> [(['28500'], ['2026-09-11', '2026-09-14'])]
CHECK Rubi                   -> [(['08191'], ['2026-02-16', '2026-06-29'])]
CHECK Terrassa               -> [(['08221', '08222'], ['2026-04-02', '2026-07-06'])]
CHECK Jerez de la Frontera   -> [(['11400', '11401'], ['2026-05-11', '2026-09-24'])]
CHECK Vitoria-Gasteiz        -> NO CRUZA
CHECK Santander              -> NO CRUZA
```

## Portugal e Italia

```
== PORTUGAL ==
concelhos: 308
sin codigos postales: 6 ['Calheta', 'Lagoa', 'Lagoa', 'Quarteira', 'Valença do Minho', 'Vila Nova do Corvo']
sin festivos 2026: 0
  ABRANTES | Abrantes | cp4=['2200', '2205', '2230'] | [{'year': 2026, 'date': '2026-06-14', 'name': 'Elevação a cidade'}]
  AGUEDA | Águeda | cp4=['3750', '3754'] | [{'year': 2026, 'date': '2026-05-25', 'name': 'Pentecostes (Festa de São Geraldo)'}]
  AGUIAR DA BEIRA | Aguiar da Beira | cp4=['3570'] | [{'year': 2026, 'date': '2026-02-10', 'name': 'Restauração do concelho'}]
  ALANDROAL | Alandroal | cp4=['7200', '7250'] | [{'year': 2026, 'date': '2026-04-13', 'name': 'Segunda-feira de Pascoela (Nossa Senhora da Boa Nova)'}]
  ALBERGARIA A VELHA | Albergaria-a-Velha | cp4=['3850'] | [{'year': 2026, 'date': '2026-08-17', 'name': 'Segunda-feira da Senhora do Socorro'}]
  CHECK Marinha Grande -> [{'year': 2026, 'date': '2026-05-14', 'name': 'Quinta-feira da Ascensão'}]
  CHECK Lisboa -> [{'year': 2026, 'date': '2026-06-13', 'name': 'Santo António'}]
  CHECK Porto -> [{'year': 2026, 'date': '2026-06-24', 'name': 'São João Baptista'}]
  CHECK Leiria -> [{'year': 2026, 'date': '2026-05-22', 'name': 'Elevação a cidade e fundação da diocese'}]
  CHECK Estarreja -> [{'year': 2026, 'date': '2026-06-13', 'name': 'Santo António'}]
  CHECK Maia -> [{'year': 2026, 'date': '2026-07-13', 'name': 'Nossa Senhora do Bom Despacho'}]

== ITALIA ==
comuni con festivo resuelto: 5354
descartes: {'infobox sin campo Festivo': 768, 'formato no reconocido': 459, 'comune sin CAP': 36}
con subdivision: 5296
sin CAP: 0
  CHECK Pisa -> sub=IT-TO-PI cap=['56121', '56122', '56123'] [{'year': 2026, 'date': '2026-06-17', 'name': 'San Ranieri'}]
  CHECK Milano -> sub=IT-LO-MI cap=['20121', '20122', '20123'] [{'year': 2026, 'date': '2026-12-07', 'name': "Sant'Ambrogio"}]
  CHECK Cremona -> sub=IT-LO-CR cap=['26100'] [{'year': 2026, 'date': '2026-11-13', 'name': "Sant'Omobono"}]
  CHECK Opera -> sub=IT-LO-MI cap=['20090'] [{'year': 2026, 'date': '2026-06-29', 'name': 'San Pietro e san Paolo'}]
  CHECK Roma -> sub=IT-LA-RM cap=['00118', '00119', '00120'] [{'year': 2026, 'date': '2026-06-29', 'name': 'Santi Pietro e Paolo'}]
  CHECK Parma -> sub=IT-ER-PR cap=['43121', '43122', '43123'] [{'year': 2026, 'date': '2026-01-13', 'name': "Sant'Ilario di Poitiers"}]
  CHECK Piacenza -> sub=IT-ER-PC cap=['29121', '29122'] [{'year': 2026, 'date': '2026-07-04', 'name': "Sant'Antonino di Piacenza, santa Giustina di Antiochia"}]
  CHECK Ravenna -> NO ESTA

PT claves duplicadas: 1 ['LAGOA']

IT claves duplicadas: 1 ['CASTRO']
```
