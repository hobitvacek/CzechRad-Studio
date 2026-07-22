# Architektura

## Kontext

CzechRad Studio je jeden Python plugin pro QGIS 3 / Qt5 a QGIS 4 / Qt6. Uživatelské rozhraní používá pouze verzově nezávislé importy `qgis.PyQt` a malou izolovanou kompatibilní vrstvu. Doménová logika je oddělena od QGIS API tak, aby parser, validace, mise a databáze šly testovat i bez spuštěného QGIS.

## Tok dat

```text
Denní LOG (neměnný zdroj)
        ↓
Importer → Parser → Validator
        ↓
Doménový model (měření, mise, úseky)
        ↓
GeoPackage repository
        ↓
QGIS vrstvy a uživatelské rozhraní
        ↓
Kontrolovaný export pro SÚRO
```

## Moduly

- `core/` – verze, společné typy, nastavení a logování.
- `importer/` – rozpoznání formátu, parsování CzechRad LOG 2.x, validace a stabilní identita zdroje.
- `monitoring/` – sledování adresáře, kontrola ustálení souboru a plánování importu.
- `database/` – schéma GeoPackage, migrace a repository rozhraní.
- `missions/` – seskupení více denních LOGů do uživatelského pracovního celku.
- `segments/` – časové či prostorové části LOGu a jejich metadata.
- `suro/` – validační pravidla, mapování formuláře, verzovaný export a stav odeslání.
- `ui/` – QGIS akce, dock widgety, dialogy a prezentační logika.
- `tests/` – jednotkové, kontraktní a později integrační testy.

Závislosti směřují od UI a infrastruktury k doménovému modelu. Doménové moduly nesmí importovat `qgis` ani `qgis.PyQt`.

## Přístroje a radiační hodnoty

Parser rozlišuje typ věty přímo z prvního pole záznamu. Aktuálně podporuje
`CZRA1`, starší CzechRad `CZRDD` a Safecast `BNRDD`. Doménový model uchovává
typ i rodinu přístroje a volí kalibraci 328,5 CPM/µSv/h pro CzechRad nebo
334 CPM/µSv/h pro Safecast. Rychlá hodnota odpovídající displeji se počítá
z počtu impulzů za posledních pět sekund; minutové CPM zůstává samostatnou,
vyhlazenou hodnotou.

## Navržený datový model

### SourceLog

- stabilní interní ID;
- absolutní nebo relativní cesta k původnímu souboru;
- název, velikost, čas změny a kryptografický otisk;
- formát a verze parseru;
- sériové číslo zařízení;
- interval začátku a konce;
- stav importu a revize.

### Measurement

- ID zdrojového LOGu a pořadí záznamu;
- čas v UTC;
- původní radiační hodnoty bez nevratných přepočtů;
- GPS stav, WGS84 souřadnice, výška, počet satelitů a HDOP;
- příznaky validity a důvod vyřazení;
- původní řádek nebo jeho otisk pro audit.

### Mission

- uživatelský název, popis a časový rozsah;
- vazba na jeden či více denních LOGů;
- stav zpracování a archivace.

### Segment

- vazba na misi a zdrojový LOG;
- čas od–do a odvozený rozsah měření;
- typ pohybu a zahrnutí do exportu;
- výška, orientace, popis trasy a poznámky;
- stav kontroly a revize.

Automatické návrhy jsou uloženy zvlášť v `segment_proposals` a vždy patří ke
konkrétní revizi denního LOGu. Potvrzené či ručně vytvořené úseky jsou v
`measurement_segments` navázané na stabilní `source_log_id`; nová revize LOGu
je proto nesmaže. Návrh nikdy automaticky neurčuje definitivní význam úseku.

### SuroSubmission

- vazba na misi a vybrané úseky;
- snapshot metadat použitých při exportu;
- verze exportního profilu;
- stav koncept / připraveno / exportováno / označeno jako odeslané;
- datum a otisk vytvořeného balíčku.

## Identita a aktualizace LOGu

Název souboru sám nestačí. Import používá kombinaci zařízení, data obsaženého v LOGu a otisku obsahu. Při rozšíření denního LOGu vznikne nová revize stejného zdroje. Záznamy se párují deterministicky podle pořadí a obsahu; existující úseky zůstávají zachovány a nové záznamy se označí jako nezařazené. První implementace může bezpečně znovu parsovat celý soubor, dokud testy neprokážou správnost přírůstkového importu.

## Monitoring

`QFileSystemWatcher` slouží jen jako rychlý signál. Periodická kontrola zachytí změny, které operační systém nebo připojené zařízení neoznámí spolehlivě. Import začne až po dvou shodných kontrolách velikosti a času změny. Selhání je opakovatelné a nesmí odstranit poslední platnou revizi.

## Databáze

GeoPackage je lokální autoritativní úložiště odvozených dat. Schéma je verzované tabulkou `crs_schema_migrations`. Zápisy importu probíhají v transakci: buď se uloží celá validní revize, nebo žádná. Stejný otisk se nevkládá znovu; změněný denní LOG vytvoří novou aktuální revizi a předchozí zůstane dohledatelná. Kumulativní `NOGPS.LOG` se identifikuje jen podle záznamů přiřazených danému dni, takže růst souboru nevytváří falešné revize starších tras. Původní LOG zůstává mimo databázi jako zdrojový důkaz a ověřená archivní kopie je spravována monitoringem.

## Logování a chyby

Technické události se zapisují do QGIS Message Log pod značkou `CzechRad Studio`. Uživateli se zobrazují stručné a opravitelné zprávy. Log nesmí bez výslovného diagnostického režimu obsahovat celé GPS trasy ani osobní údaje.

## Testovací strategie

1. Jednotkové testy parseru a doménových pravidel bez QGIS.
2. Testovací LOGy: normální, prázdný, poškozený, duplicitní, špatná GPS a postupně rozšiřovaný.
3. Kontraktní testy povinných souborů a metadata pluginu.
4. Integrační testy databázových migrací v dočasném GeoPackage.
5. Ruční smoke test v podporovaném QGIS 3 i QGIS 4 před vydáním ZIPu.

## Bezpečnost a soukromí

- žádné automatické síťové odesílání v základu;
- explicitní potvrzení každého exportu;
- atomické zápisy a zálohované migrace;
- kontrola cest, názvů a obsahu souborů před archivací;
- anonymizace testovacích LOGů před zveřejněním.
