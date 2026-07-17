# CzechRad Studio

CzechRad Studio je připravovaný open-source plugin pro QGIS 4, který má zjednodušit import, správu, kontrolu a export radiačních měření z detektorů CzechRad.

Projekt navazuje na [Radiation ToolBox Plugin](https://gitlab.com/opengeolabs/radiation-toolbox/qgis-radiation-toolbox-plugin), který vytvořila společnost OpenGeoLabs s.r.o. pro SÚRO. CzechRad Studio je samostatný odvozený projekt; není oficiálním produktem ani službou SÚRO, OpenGeoLabs nebo výrobce CzechRad.

## Stav projektu

Aktuální verze `0.1.0` je pouze technický základ:

- platná kostra Python pluginu s `classFactory()`;
- minimální menu a akce pro ověření načtení v QGIS;
- modulární adresáře pro import, monitoring, databázi, mise, úseky a export SÚRO;
- počáteční architektura, vize a roadmapa;
- základní testy kontraktu pluginu bez závislosti na QGIS.

Import LOG souborů, monitoring složky, databáze a export pro SÚRO zatím nejsou implementovány.

## Instalace vývojové verze

1. Stáhněte nebo naklonujte repozitář.
2. Zkopírujte adresář `czechrad_studio` do adresáře Python pluginů profilu QGIS 4.
3. V QGIS otevřete správce zásuvných modulů a zapněte **CzechRad Studio**.

Plugin je v této fázi označen jako experimentální a je určen pouze pro vývojové testování.

## Dokumentace

- [Vize projektu](docs/VISION.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Roadmapa](docs/ROADMAP.md)
- [Návrh exportu pro SÚRO](docs/SURO_EXPORT.md)

## Licence a původ

Projekt je šířen pod licencí `GPL-3.0-or-later`. Podrobnosti o původním projektu a změnách jsou v [NOTICE.md](NOTICE.md); úplné licenční podmínky jsou v [LICENSE](LICENSE).

## Hlášení chyb

Chyby a návrhy evidujte v [GitHub Issues](https://github.com/hobitvacek/CzechRad-Studio/issues). K hlášení nepřikládejte neveřejné polohové údaje bez kontroly a anonymizace.
