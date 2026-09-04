# Budoucí referenční datové vrstvy

Tento dokument eviduje možné zdroje pro pozdější srovnání vlastních měření.
V aktuální verzi CzechRad Studio se žádný z nich automaticky nestahuje ani
neodesílá data uživatele do sítě.

## QGIS Processing Tools

Referenční projekt:
[juhele/QGIS-Processing-tools](https://github.com/juhele/QGIS-Processing-tools/)
(CC0 1.0, Jan Helebrant).

Pro budoucí volitelný modul jsou zajímavé zejména:

- Safecast Point Loader pro veřejná mobilní měření v aktuálním výřezu mapy;
- Safecast Fixed Sensors Loader, který je připraven pro QGIS 3 i QGIS 4;
- MonRas SVZ Point Loader pro veřejnou českou Síť včasného zjištění;
- PAA Point Loader pro veřejné referenční body v Polsku.

## Podmínky případného začlenění

- referenční vrstvy musí být jasně oddělené od vlastních měření;
- stažení musí spustit uživatel a musí být omezené rozsahem mapy;
- doplní se lokální mezipaměť a šetrné omezení četnosti dotazů;
- každý zdroj bude mít vlastní převod jednotek a uvedení původu dat;
- kalibrace Safecast 334 CPM/µSv/h se nesmí zaměnit za CzechRad
  328,5 CPM/µSv/h;
- změna nebo nedostupnost externí služby nesmí narušit import vlastních LOGů;
- kód musí projít testem v podporovaném QGIS 3 i QGIS 4.

Začlenění je odloženo až za stabilní import, mise, úseky a podklady pro SÚRO.
