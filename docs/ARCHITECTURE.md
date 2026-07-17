# Architektura

## Kontext

CzechRad Studio je Python plugin pro QGIS 4 a Qt6. Uživatelské rozhraní používá pouze verzově nezávislé importy `qgis.PyQt`. Doménová logika má být oddělena od QGIS API tak, aby parser, validace a datový model šly testovat i bez spuštěného QGIS.

## Tok dat

```text
Denní LOG + NOGPS*.LOG (neměnné zdroje)
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
- druh zdroje: trasový LOG / NOGPS / jiný podporovaný formát;
- stav importu a revize.

### Measurement

- ID zdrojového LOGu a pořadí záznamu;
- čas v UTC;
- původní radiační hodnoty bez nevratných přepočtů;
- původní GPS stav, WGS84 souřadnice, výška, počet satelitů a HDOP;
- stav polohy: `gps_valid`, `gps_invalid`, `manual` nebo `none`;
- ručně přiřazené místo nebo geometrie oddělené od původních GPS polí;
- samostatná validita radiačního měření, času a polohy včetně důvodů;
- původní řádek nebo jeho otisk pro audit.

### Mission

- uživatelský název, popis a časový rozsah;
- vazba na jeden či více denních LOGů;
- stav zpracování a archivace.

### Segment

- vazba na misi a zdrojový LOG;
- čas od–do a odvozený rozsah měření;
- typ pohybu včetně vnitřního měření a zahrnutí do exportu;
- volitelná ruční poloha, budova, podlaží nebo popis místa;
- výška, orientace, popis trasy a poznámky;
- stav kontroly a revize.

### SuroSubmission

- vazba na misi a vybrané úseky;
- snapshot metadat použitých při exportu;
- verze exportního profilu;
- stav koncept / připraveno / exportováno / označeno jako odeslané;
- datum a otisk vytvořeného balíčku.

## Měření bez GPS

Soubory `NOGPS*.LOG` jsou plnohodnotné zdroje radiačních měření vznikající při startu bez fixu i při ztrátě GPS v budovách, podchodech nebo jiných zakrytých místech. Název souboru není důvodem k vyřazení hodnot.

- Radiační hodnota, čas a poloha se validují nezávisle.
- Příznak GPS `A` sám nestačí; nulové souřadnice, nula satelitů nebo sentinel `HDOP=9999` znamenají nedůvěryhodnou polohu.
- Nedůvěryhodné souřadnice se uchovají pro audit, ale nepoužijí se jako geometrie mapové vrstvy.
- Pokud je čas důvěryhodný, záznamy se podle časového intervalu navrhnou k přiřazení mezi poslední a následující část stejné mise.
- Čas má samostatný stav `valid`, `untrusted` nebo `missing`. Do databáze měření se NOGPS záznam zařadí pouze se stavem `valid`.
- Chybějící, výchozí nebo nedůvěryhodný čas, například datum zařízení před získáním GPS času, se jako měření nepoužije. Zdrojový soubor se zachová pro audit a importní protokol uvede počet a důvod přeskočení.
- Uživatel může vytvořit vnitřní úsek a přiřadit mu budovu, podlaží, popis nebo ruční bod či plochu. Ruční poloha nikdy nepřepíše původní GPS pole.
- Trasa se přes období bez GPS nespojí zavádějící přímkou; UI zobrazí časovou mezeru a počet nepřiřazených měření.

Soubor NOGPS může obsahovat záznamy z více dnů. Import jej proto dělí podle důvěryhodných časových intervalů a vazby na mise, nikoli podle názvu souboru.

## Identita a aktualizace LOGu

Název souboru sám nestačí. Import používá kombinaci zařízení, data obsaženého v LOGu a otisku obsahu. Při rozšíření denního LOGu vznikne nová revize stejného zdroje. Záznamy se párují deterministicky podle pořadí a obsahu; existující úseky zůstávají zachovány a nové záznamy se označí jako nezařazené. První implementace může bezpečně znovu parsovat celý soubor, dokud testy neprokážou správnost přírůstkového importu.

## Automatický import z karty

Po prvním výběru zdrojové karty může uživatel zapnout automatický import při jejím vložení. Karta je vždy zdroj pouze pro čtení: plugin na ní nepřejmenovává ani nemaže soubory a nepoužívá ji jako pracovní databázi.

1. Rozpoznat nakonfigurovanou kartu nebo podporovanou strukturu a hlavičku CzechRad; neprocházet automaticky libovolné USB disky.
2. Počkat na ustálení velikosti souborů.
3. Kopírovat do lokálního archivu nejprve pod dočasným názvem, ověřit velikost a SHA-256 a až potom provést atomické přejmenování.
4. Pokud už archiv obsahuje stejný hash, soubor znovu nevytvářet ani neimportovat.
5. Pokud existuje stejný název s jiným hashem, vytvořit nejnižší volnou variantu `nazev-1.LOG`, `nazev-2.LOG` atd. Soubory, které již mají číselnou příponu, se řídí stejným pravidlem bez přepsání.
6. V databázi uchovat původní název, cestu na zdroji, archivní název, velikost, hash a čas importu.
7. Parser a databázi spouštět až nad ověřenou archivní kopií.

Čas změny souboru na kartě není autoritativní, protože zařízení nebo FAT mohou používat výchozí hodnotu. Identita a duplicita se určují obsahem a hashem. Opakované vložení stejné karty je idempotentní.

## Monitoring

`QFileSystemWatcher` slouží jen jako rychlý signál. Periodická kontrola zachytí změny, které operační systém nebo připojené zařízení neoznámí spolehlivě. Import začne až po dvou shodných kontrolách velikosti a času změny. Selhání je opakovatelné a nesmí odstranit poslední platnou revizi.

## Databáze

GeoPackage je lokální autoritativní úložiště odvozených dat. Schéma bude verzované tabulkou migrací. Zápisy importu proběhnou v transakci: buď se uloží celá validní revize, nebo žádná. Původní LOG zůstává mimo databázi jako zdrojový důkaz; volitelný archiv se bude řešit samostatně.

## Logování a chyby

Technické události se zapisují do QGIS Message Log pod značkou `CzechRad Studio`. Uživateli se zobrazují stručné a opravitelné zprávy. Log nesmí bez výslovného diagnostického režimu obsahovat celé GPS trasy ani osobní údaje.

## Testovací strategie

1. Jednotkové testy parseru a doménových pravidel bez QGIS.
2. Syntetické anonymizované testovací LOGy: normální, prázdný, poškozený, duplicitní, špatná GPS, ztráta GPS uprostřed mise, více dnů v NOGPS a postupně rozšiřovaný.
3. Kontraktní testy povinných souborů a metadata pluginu.
4. Integrační testy databázových migrací v dočasném GeoPackage.
5. Ruční smoke test v podporovaných verzích QGIS 4 před vydáním ZIPu.

## Bezpečnost a soukromí

- žádné automatické síťové odesílání v základu;
- explicitní potvrzení každého exportu;
- atomické zápisy a zálohované migrace;
- kontrola cest, názvů a obsahu souborů před archivací;
- anonymizace testovacích LOGů před zveřejněním.
