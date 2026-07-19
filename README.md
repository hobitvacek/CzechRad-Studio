# CzechRad Studio

CzechRad Studio je připravovaný open-source plugin pro QGIS 4, který má zjednodušit import, správu, kontrolu a export radiačních měření z detektorů CzechRad.

Projekt navazuje na [Radiation ToolBox Plugin](https://gitlab.com/opengeolabs/radiation-toolbox/qgis-radiation-toolbox-plugin), který vytvořila společnost OpenGeoLabs s.r.o. pro SÚRO. CzechRad Studio je samostatný odvozený projekt; není oficiálním produktem ani službou SÚRO, OpenGeoLabs nebo výrobce CzechRad.

## Stav projektu

Aktuální experimentální verze `0.2.1` obsahuje první použitelný import:

- platná kostra Python pluginu s `classFactory()`;
- import denního LOGu a volitelného NOGPS.LOG do QGIS;
- zobrazení CPM i dopočteného µSv/h s barevnou legendou;
- volitelné sloučení stabilních dlouhých zastavení pouze pro zobrazení;
- modulární adresáře pro import, monitoring, databázi, mise, úseky a export SÚRO;
- počáteční architektura, vize a roadmapa;
- základní testy kontraktu pluginu bez závislosti na QGIS.

Monitoring složky, databáze a export pro SÚRO zatím nejsou implementovány.

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

