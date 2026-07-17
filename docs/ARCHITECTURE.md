# Architektura

## Kontext

CzechRad Studio je Python plugin pro QGIS 4 a Qt6. Uživatelské rozhraní používá pouze verzově nezávislé importy `qgis.PyQt`. Doménová logika má být oddělena od QGIS API tak, aby parser, validace a datový model šly testovat i bez spuštěného QGIS.

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

GeoPackage je lokální autoritativní úložiště odvozených dat. Schéma bude verzované tabulkou migrací. Zápisy importu proběhnou v transakci: buď se uloží celá validní revize, nebo žádná. Původní LOG zůstává mimo databázi jako zdrojový důkaz; volitelný archiv se bude řešit samostatně.

## Logování a chyby

Technické události se zapisují do QGIS Message Log pod značkou `CzechRad Studio`. Uživateli se zobrazují stručné a opravitelné zprávy. Log nesmí bez výslovného diagnostického režimu obsahovat celé GPS trasy ani osobní údaje.

## Testovací strategie

1. Jednotkové testy parseru a doménových pravidel bez QGIS.
2. Testovací LOGy: normální, prázdný, poškozený, duplicitní, špatná GPS a postupně rozšiřovaný.
3. Kontraktní testy povinných souborů a metadata pluginu.
4. Integrační testy databázových migrací v dočasném GeoPackage.
5. Ruční smoke test v podporovaných verzích QGIS 4 před vydáním ZIPu.

## Bezpečnost a soukromí

- žádné automatické síťové odesílání v základu;
- explicitní potvrzení každého exportu;
- atomické zápisy a zálohované migrace;
- kontrola cest, názvů a obsahu souborů před archivací;
- anonymizace testovacích LOGů před zveřejněním.
