"""Pone a cada municipio espanol su codigo de subdivision de OpenHolidays.

Sin este paso, Espana pierde los festivos AUTONOMICOS. San Jose, el 19 de marzo,
llega de OpenHolidays con las subdivisiones ES-PV, ES-VC, ES-MC, ES-NC y ES-GA,
y solo se aplica a una localidad cuyo codigo empiece por una de ellas. Una
entrega a Valencia ese dia salia "laborable" por no tener ES-VC-VN puesto.

Se perdio al pasar Espana a generarse desde la API de Chemieuro: ese origen no
trae subdivision y el paso que la calculaba se habia quedado dentro de
cruzar_es.py, que ya no manda sobre el fichero final. Aqui se aplica al
resultado, venga de donde venga.

La subdivision sale de la PROVINCIA (los dos primeros digitos del codigo
postal), a nivel provincial (ES-VC-VN), nunca de isla: un festivo insular no
vale para toda la provincia.
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = os.path.join(_RAIZ, "fuentes")
BUILD = os.path.join(_RAIZ, "build")


def main():
    from cruzar_es import subdivisiones_por_provincia

    p = os.path.join(BUILD, "es_holidays_feed.json")
    if not os.path.exists(p):
        print("aviso: no hay es_holidays_feed.json que completar")
        return

    subs = subdivisiones_por_provincia()
    if not subs:
        print("aviso: sin arbol de subdivisiones; Espana se queda sin festivos autonomicos")
        return

    municipios = json.load(io.open(p, encoding="utf-8"))
    puestas = ya = sin_cp = 0
    for m in municipios:
        if m.get("sub"):
            ya += 1
            continue
        # La provincia sale del INE si lo hay y, si no, del codigo postal.
        prov = (m.get("ine") or "")[:2]
        if not prov:
            cps = [c for c in m.get("pc", []) if len(c) >= 2 and c[:2].isdigit()]
            prov = cps[0][:2] if cps else ""
        if not prov:
            sin_cp += 1
            continue
        sub = subs.get(prov, "")
        if sub:
            m["sub"] = sub
            puestas += 1

    json.dump(municipios, io.open(p, "w", encoding="utf-8"), ensure_ascii=False)

    con = sum(1 for m in municipios if m.get("sub"))
    print("Espana: subdivision puesta a %d municipios (ya la tenian %d, sin provincia %d)"
          % (puestas, ya, sin_cp))
    print("  con subdivision: %d de %d" % (con, len(municipios)))
    for nombre in ("València", "Valencia", "Zaragoza", "Murcia", "Bilbao"):
        hit = [m for m in municipios if m["name"] == nombre]
        if hit:
            print("  CHECK %-12s -> %s" % (nombre, hit[0].get("sub") or "(sin subdivision)"))


if __name__ == "__main__":
    main()
