# Obnova CzechRad Studio po reinstalaci počítače

Tento návod popisuje obnovu vývojového projektu a QGIS pluginu. Veřejný
repozitář neobsahuje osobní LOGy, projektové databáze ani QGIS projekty, protože
mohou obsahovat citlivé časové a polohové údaje.

## Co je uložené na GitHubu

- celý zdrojový kód pluginu;
- dokumentace a roadmapa;
- automatické testy a anonymizovaná testovací data;
- instalační ZIP poslední veřejně otestované verze.

Repozitář:
<https://github.com/hobitvacek/CzechRad-Studio>

Testovací verze 0.6.0:
<https://github.com/hobitvacek/CzechRad-Studio/raw/refs/heads/main/test-builds/czechrad_studio-0.6.0-test.zip>

SHA-256:
`E411B22E93AC4DB29B01F322B742F47F37A00F93CE3328992ADD99EDBB4ADE92`

## Co je nutné před reinstalací zazálohovat zvlášť

- všechny původní soubory `*.LOG`, včetně `NOGPS.LOG`;
- projektové databáze CzechRad Studio `*.gpkg`;
- uložené QGIS projekty `*.qgz` nebo `*.qgs`;
- zvolený archiv automatického monitoringu;
- případné vlastní styly, podkladové vrstvy a exporty;
- volitelně celý aktivní profil QGIS, pokud se mají zachovat ostatní pluginy
  a nastavení.

Typická umístění profilů ve Windows:

```text
%APPDATA%\QGIS\QGIS3\profiles\default
%APPDATA%\QGIS\QGIS4\profiles\default
```

Osobní LOGy ani GeoPackage neposílej do veřejného repozitáře bez kontroly GPS
souřadnic. Pro jejich zálohu použij vlastní soukromé cloudové úložiště nebo
externí disk.

## Obnova po reinstalaci

1. Nainstaluj QGIS 3.22 nebo novější, případně QGIS 4.x.
2. Stáhni poslední testovací ZIP z odkazu výše.
3. V QGIS otevři **Zásuvné moduly → Spravovat a instalovat zásuvné moduly →
   Instalovat ze ZIP**.
4. V CzechRad Studio znovu vyber zazálohovaný GeoPackage a aktivní misi.
5. Nastav složku pro monitoring a místní archiv.
6. Otevři příslušný QGIS projekt nebo znovu načti požadované LOGy.

Pro pokračování ve vývoji naklonuj repozitář pomocí GitHub Desktop nebo:

```text
git clone https://github.com/hobitvacek/CzechRad-Studio.git
```

Zdrojové LOGy plugin při běžném importu úmyslně nemění.
