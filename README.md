# Festivos locales

Calendario de festivos **municipales** de España, Portugal e Italia, publicado como
ficheros JSON estáticos para que Business Central los lea solo.

Existe porque ninguna API pública cubre este nivel. OpenHolidays API, que es la que usa
la extensión para lo nacional y lo regional, llega hasta la provincia o la isla: el
patrón de Pisa (San Ranieri, 17 de junio) o la Romería de la Fuensanta en Murcia no
están en ninguna parte en formato consultable. Aquí sí.

## Para qué sirve

La ficha de carga de Business Central muestra, bajo la fecha estimada de entrega, una
barra de días en verde o rojo según sean laborables o festivos **en la localidad donde
se descarga la mercancía**. Sin estos datos, una entrega programada el día del patrón
llega a un almacén cerrado.

## Cómo se consulta

```
<base>/data/<PAÍS>/<AÑO>/<PREFIJO-CP>.json
```

El prefijo son los dos primeros dígitos del código postal. Un ejemplo real, Pisa:

```
data/IT/2026/56.json
```

```json
{
  "country": "IT",
  "year": 2026,
  "shard": "56",
  "generated": "2026-09-15",
  "municipalities": [
    {
      "name": "Pisa",
      "key": "PISA",
      "pc": ["56121", "56122", "56123", "56124", "56125", "56126", "56127", "56128"],
      "holidays": [{ "date": "2026-06-17", "name": "San Ranieri" }],
      "sub": "IT-TO-PI"
    }
  ]
}
```

- `key` es el nombre del municipio en mayúsculas, sin acentos y con espacios simples.
  Business Central normaliza igual el nombre de la ciudad de descarga.
- `alt` son los nombres alternativos. Es lo que permite que una entrega a Xixona
  encuentre el municipio publicado como Jijona.
- `pc` se compara **por prefijo**. En Portugal el código del feed tiene cuatro dígitos
  y el que trae Business Central viene completo, `2430-123`.
- `sub` es el código de subdivisión de OpenHolidays, para que la extensión pueda además
  aplicar los festivos regionales sin que nadie los teclee.
- Un prefijo sin datos devuelve **404**, y eso no es un error.

## Los otros tres ficheros

`_names.json` en cada país y año mapea el nombre del municipio al prefijo donde está.
Se consulta cuando el código postal de la entrega no lleva a ninguna parte, que pasa más
de lo que parece: apareció una dirección de Pisa con el código postal de Zaragoza.

`_country.json` trae los festivos **nacionales** de los países que OpenHolidays API no
cubre. Se comprobó el 15 de septiembre de 2026: esa API devuelve vacío para el Reino
Unido, Finlandia, Dinamarca, Noruega y Grecia. Sin este fichero, una entrega a Londres
no detectaba ni el día de Navidad.

`_countries.json` dice de cada país si **tiene** festivos municipales. Sirve para no
confundir dos cosas distintas: que no exista el concepto, como en Francia o Polonia,
donde con lo nacional y regional está todo cubierto, y que existan y no los tengamos,
que es lo único que merece un aviso en pantalla.

## Cobertura

| País | Municipios | Fuente |
| --- | --- | --- |
| España | 8.025 | API de festivos de Chemieuro, por código INE, más los boletines autonómicos para los municipios que la API no trae |
| Italia | 5.354 comuni | Patrón de cada municipio y su día, del infobox de la Wikipedia italiana |
| Portugal | 308 de 308 concelhos | Feriado municipal oficial, con los años móviles ya resueltos |

Festivos nacionales propios para Reino Unido, Finlandia, Dinamarca, Noruega y Grecia.
Los del Reino Unido vienen de la publicación oficial del gobierno británico; el resto,
de Nager.Date, contrastado con OpenHolidays en Suecia e Irlanda, donde coincide al
cien por cien.

Dónde **no** hay nada que buscar, porque el concepto no existe: Francia (salvo Alsacia
y Mosela, que es departamental y ya lo da OpenHolidays), Reino Unido, Polonia, Países
Bajos, Bélgica, Irlanda, Austria, Rumanía, Suecia y los países del este y del norte.

Pendiente: Alemania, donde sí hay festivos por municipio en Baviera, Sajonia y Turingia
según la confesión mayoritaria, y Suiza, con festivos comunales. Ninguno de los dos
está cubierto todavía.

El detalle de qué sale de dónde, y qué quedó fuera, está en `informe.md`, que se
regenera con los datos.

## Cómo se actualiza

Solo, por GitHub Actions. Se ejecuta cada mes de septiembre a enero, que es cuando las
comunidades publican el año siguiente y sus correcciones, y otra vez en abril y julio
por si hay modificaciones a mitad de año. Si un festivo cambia, el commit lo dice.

Antes de publicar, `generador/verificar.py` compara el resultado con lo que ya estaba:
si una fuente cambia de formato y su parser devuelve vacío, **no se sube nada**. Es
preferible un feed de la semana pasada a un feed roto, porque Business Central conserva
lo que ya había descargado y la ficha sigue avisando de lo que no puede comprobar.

También se puede lanzar a mano desde la pestaña Actions, indicando los años.

## Lo que este feed no garantiza

Un municipio que no aparece no es un municipio sin festivos: es un municipio del que no
tenemos el dato. La extensión lo distingue y lo dice en pantalla en lugar de pintarlo
de verde. Si detectas un festivo mal o uno que falta, abre una incidencia con el
municipio, la fecha y el enlace al boletín.

Los datos proceden de fuentes oficiales y de Wikipedia, cada una con su licencia; el
conjunto se publica para reutilización con la misma vocación abierta.
