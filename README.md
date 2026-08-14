# CzechRad Studio

CzechRad Studio je pýipravovanì open-source plugin pro QGIS 3.22+ a QGIS 4, kterì m  zjednoduçit import, spr vu, kontrolu a export radiaŸn¡ch mØýen¡ z detektor… CzechRad.

Projekt navazuje na [Radiation ToolBox Plugin](https://gitlab.com/opengeolabs/radiation-toolbox/qgis-radiation-toolbox-plugin), kterì vytvoýila spoleŸnost OpenGeoLabs s.r.o. pro SéRO. CzechRad Studio je samostatnì odvozenì projekt; nen¡ ofici ln¡m produktem ani slu§bou SéRO, OpenGeoLabs nebo vìrobce CzechRad.

## Stav projektu

Aktu ln¡ experiment ln¡ verze `0.5.4` obsahuje pou§itelnì import, monitoring, projektovou datab zi, editor mØýic¡ch £sek… a spoleŸnou podporu Qt5/Qt6:

- platn  kostra Python pluginu s `classFactory()`;
- import denn¡ho LOGu a voliteln‚ho NOGPS.LOG do QGIS;
- rozpozn n¡ CzechRad `CZRA1`, starç¡ho `CZRDD` a Safecast `BNRDD`;
- zobrazen¡ pØtisekundov‚ hodnoty uSv/h jako na displeji pý¡stroje,
  vyhlazen‚ho minutov‚ho uSv/h nebo p…vodn¡ho CPM s barevnou legendou;
- voliteln‚ slouŸen¡ stabiln¡ch dlouhìch zastaven¡ pouze pro zobrazen¡;
- oznaŸen¡ zastaven¡ se zvìçenou radiac¡ jako mo§n‚ho stacion rn¡ho mØýen¡;
- bezpeŸn‚ sledov n¡ karty nebo slo§ky, archivaci a automatickou obnovu vrstev;
- jeden spoleŸnì instalaŸn¡ bal¡Ÿek pro QGIS 3.22-3.44 a QGIS 4.x;
- projektovì GeoPackage s verzovanìm sch‚matem a atomickìm importem;
- trval‚ ulo§en¡ zaý¡zen¡, denn¡ch LOG…, jejich reviz¡ a mØýen¡ bez nevratn‚ £pravy zdroje;
- mise slo§en‚ z v¡ce denn¡ch LOG… a ochranu proti duplicitn¡mu importu;
- nov‚ revize zmØnØn‚ho denn¡ho LOGu se zachov n¡m pýedchoz¡ho stavu;
- automatick‚ n vrhy stacion rn¡ch £sek…, pobytu bez GPS a hranic podle
  delç¡ch mezer v z znamu;
- oddØlen‚ ulo§en¡ n vrh… a u§ivatelskìch £sek…, kter‚ se pýi nov‚ revizi
  denn¡ho LOGu neztrat¡;
- pýehled nevyý¡zenìch n vrh… v aktivn¡ misi, jejich potvrzen¡ nebo pýeskoŸen¡;
- doplnØn¡ typu £seku, vìçky a orientace detektoru, popisu trasy, pozn mky a
  volby pro budouc¡ podklady SéRO;
- samostatnì pýehled ulo§enìch £sek… s opravou metadat a zvìraznØn¡m v mapØ;
- ruŸn¡ vytvoýen¡ £seku podle Ÿasu v konkr‚tn¡m LOGu, vŸetnØ rozliçen¡
  nØkolika karet se stejnìm denn¡m n zvem;
- modul rn¡ adres ýe pro import, monitoring, datab zi, mise, £seky a export SéRO;
- poŸ teŸn¡ architektura, vize a roadmapa;
- z kladn¡ testy kontraktu pluginu bez z vislosti na QGIS.

RuŸn¡ vìbØr hranic kliknut¡m do mapy a export pro SéRO zat¡m nejsou implementov ny.

## Instalace vìvojov‚ verze

1. St hnØte nebo naklonujte repozit ý.
2. Zkop¡rujte adres ý `czechrad_studio` do adres ýe Python plugin… profilu QGIS 3 nebo QGIS 4.
3. V QGIS otevýete spr vce z suvnìch modul… a zapnØte **CzechRad Studio**.

Plugin je v t‚to f zi oznaŸen jako experiment ln¡ a je urŸen pouze pro vìvojov‚ testov n¡.

Po instalaci otevýete **Z suvn‚ moduly  CzechRad Studio  Projekt a aktivn¡ mise**,
vytvoýte nebo otevýete soubor `.gpkg` a zalo§te misi. N sleduj¡c¡ ruŸn¡ i
automatick‚ importy se budou do aktivn¡ mise ukl dat bez duplicit.

Automatick‚ n vrhy zkontrolujete pýes **Z suvn‚ moduly  CzechRad Studio 
MØýic¡ £seky**. Potvrzen¡ nikdy neupravuje p…vodn¡ LOG.
Potvrzen‚ £seky lze pozdØji opravit pýes **CzechRad Studio  Ulo§en‚ £seky**.
Ve stejn‚m oknØ lze tlaŸ¡tkem **Novì £sek podle Ÿasu** rozdØlit
denn¡ LOG na vlastn¡ trasy bez zmØny zdrojovìch dat.

## Dokumentace

- [Vize projektu](docs/VISION.md)
- [Architektura](docs/ARCHITECTURE.md)
- [Roadmapa](docs/ROADMAP.md)
- [N vrh exportu pro SéRO](docs/SURO_EXPORT.md)

## Licence a p…vod

Projekt je ç¡ýen pod licenc¡ `GPL-3.0-or-later`. Podrobnosti o p…vodn¡m projektu a zmØn ch jsou v [NOTICE.md](NOTICE.md); £pln‚ licenŸn¡ podm¡nky jsou v [LICENSE](LICENSE).

## Hl çen¡ chyb

Chyby a n vrhy evidujte v [GitHub Issues](https://github.com/hobitvacek/CzechRad-Studio/issues). K hl çen¡ nepýikl dejte neveýejn‚ polohov‚ £daje bez kontroly a anonymizace.
