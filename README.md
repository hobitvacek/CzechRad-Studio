# CzechRad Studio

CzechRad Studio je připravovaný open-source plugin pro QGIS 3.22+ a QGIS 4, který má zjednodušit import, správu, kontrolu a export radiačních měření z detektorů CzechRad.

Projekt navazuje na [Radiation ToolBox Plugin](https://gitlab.com/opengeolabs/radiation-toolbox/qgis-radiation-toolbox-plugin), který vytvořila společnost OpenGeoLabs s.r.o. pro SÚRO. CzechRad Studio je samostatný odvozený projekt; není oficiálním produktem ani službou SÚRO, OpenGeoLabs nebo výrobce CzechRad.

## Stav projektu

Aktuální experimentální verze `0.5.0` obsahuje použitelný import, monitoring, projektovou databázi, první základ měřicích úseků a společnou podporu Qt5/Qt6:

- platná kostra Python pluginu s `classFactory()`;
- import denního LOGu a volitelného NOGPS.LOG do QGIS;
- rozpoznání CzechRad `CZRA1`, staršího `CZRDD` a Safecast `BNRDD`;
- zobrazení pětisekundové hodnoty µSv/h jako na displeji přístroje,
  vyhlazeného minutového µSv/h nebo původního CPM s barevnou legendou;
- volitelné sloučení stabilních dlouhých zastavení pouze pro zobrazení;
- označení zastavení se zvýšenou radiací jako možného stacionárního měření;
- bezpečné sledování karty nebo složky, archivaci a automatickou obnovu vrstev;
- jeden společný instalační balíček pro QGIS 3.22–3.44 a QGIS 4.x;
- projektový GeoPackage s verzovaným schématem a atomickým importem;
- trvalé uložení zařízení, denních LOGů, jejich revizí a měření bez nevratné úpravy zdroje;
- mise složené z více denních LOGů a ochranu proti duplicitnímu importu;
- nové revize změněného denního LOGu se zachováním předchozího stavu;
- automatické návrhy stacionárních úseků, pobytu bez GPS a hranic podle
  delších mezer v záznamu;
- oddělené uložení návrhů a uživatelských úseků, které se při nové revizi
  denního LOGu neztratí;
- modulární adresáře pro import, monitoring, databázi, mise, úseky a export SÚRO;
- počáteční architektura, vize a roadmapa;
- základní testy kontraktu pluginu bez závislosti na QGIS.

Ruční editor hranic a metadat úseků a export pro SÚRO zatím nejsou implementovány.

## Instalace vývojové verze

1. Stáhněte nebo naklonujte repozitář.
2. Zkopírujte adresář `czechrad_studio` do adresáře Python pluginů profilu QGIS 3 nebo QGIS 4.
3. V QGIS otevřete správce zásuvných modulů a zapněte **CzechRad Studio**.

Plugin je v této fázi označen jako experimentální a je určen pouze pro vývojové testování.

Po instalaci otevřete **Zásuvné moduly → CzechRad Studio → Projekt a aktivní mise…**,
vytvořte nebo otevřete soubor `.gpkg` a založte misi. Následující ruční i
automatické importy se budou do aktivní mise ukládat bez duplicit.

## Dokumentace

- [Vize projektu](docs/VISION.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Roadmapa](docs/ROADMAP.md)
- [Návrh exportu pro SÚRO](docs/SURO_EXPORT.md)

## Licence a původ

Projekt je šířen pod licencí `GPL-3.0-or-later`. Podrobnosti o původním projektu a změnách jsou v [NOTICE.md](NOTICE.md); úplné licenční podmínky jsou v [LICENSE](LICENSE).

## Hlášení chyb

Chyby a návrhy evidujte v [GitHub Issues](https://github.com/hobitvacek/CzechRad-Studio/issues). K hlášení nepřikládejte neveřejné polohové údaje bez kontroly a anonymizace.
