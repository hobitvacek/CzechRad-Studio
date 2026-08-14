# Jednoduchý návod k CzechRad Studio 0.5.5

Tento návod je určen pro testovací verzi pluginu CzechRad Studio. Plugin je
stále experimentální. Zdrojové soubory LOG nikdy úmyslně neupravuje; při
automatickém importu je pouze kopíruje do zvoleného místního archivu.

## 1. Co je potřeba

- QGIS 3.22 nebo novější, případně QGIS 4.x;
- instalační ZIP `czechrad_studio-0.5.5-test.zip`;
- denní soubor zařízení, například `07960808.LOG`;
- volitelně odpovídající `NOGPS.LOG` ze stejné karty;
- pro projektovou databázi libovolnou zapisovatelnou složku na počítači.

Plugin používá stejný balíček pro Windows a Linux i pro QGIS 3 a QGIS 4.

## 2. Instalace ze ZIP

1. Spusť QGIS.
2. Otevři **Zásuvné moduly → Spravovat a instalovat zásuvné moduly**.
3. Zvol **Instalovat ze ZIP**.
4. Vyber `czechrad_studio-0.5.5-test.zip` a potvrď instalaci.
5. Pokud se objeví upozornění na experimentální nebo neověřený plugin,
   pokračuj pouze tehdy, pokud ZIP pochází z repozitáře CzechRad Studio.
6. V nabídce **Zásuvné moduly** se objeví položka **CzechRad Studio**.

Při aktualizaci ze starší testovací verze doporučujeme starou verzi nejprve
odinstalovat, QGIS ukončit a potom nainstalovat nový ZIP.

## 3. Založení projektu a mise

1. Otevři **CzechRad Studio → Projekt a aktivní mise…**.
2. U položky projektového GeoPackage vyber existující soubor `.gpkg`, nebo
   napiš cestu k novému souboru, například `D:\Radiace\CzechRad.gpkg`.
3. Vytvoř misi, například `Ostrava – srpen 2026`.
4. Vyber ji jako aktivní a potvrď dialog.

GeoPackage uchovává importy, jejich revize, měření, návrhy úseků a uživatelská
metadata. Původní LOG zůstává samostatným zdrojovým souborem.

## 4. Ruční načtení měření

1. Klikni na ikonu **CzechRad Studio** nebo otevři stejnojmennou položku menu.
2. Vyber denní LOG.
3. Pokud ho máš, vyber také `NOGPS.LOG` ze stejné karty.
4. Zvol způsob zobrazení radiace:
   - **µSv/h – stejně jako displej přístroje** pro rychlé pětisekundové hodnoty;
   - vyhlazenou minutovou hodnotu;
   - nebo původní CPM.
5. Volitelně zapni sloučení stabilních dlouhých zastavení pro přehlednější mapu.
6. Stiskni **Načíst do mapy**.

Po úspěšném importu se zobrazí barevné body, legenda a souhrn počtu měření,
NOGPS záznamů, zastavení a návrhů úseků.

## 5. Automatické kopírování z karty

1. Otevři **CzechRad Studio → Nastavit automatický import…**.
2. Jako zdroj vyber kartu nebo složku s LOGy.
3. Jako archiv vyber jinou složku na pevném disku. Archiv nesmí být na kartě
   ani uvnitř sledované složky.
4. Zapni monitoring a potvrď nastavení.

Plugin čeká, až se soubor přestane měnit, a teprve potom vytvoří ověřenou kopii.
Stejný obsah nekopíruje znovu. Odlišný soubor se stejným názvem dostane příponu
`-1`, `-2` a podobně.

## 6. Měřicí úseky

### Automatické návrhy

Otevři **CzechRad Studio → Měřicí úseky…**. Zde lze prohlížet návrhy delších
zastavení, ztrát GPS a mezer v záznamu. Vybraný návrh lze ukázat v mapě,
potvrdit jako skutečný úsek nebo přeskočit.

### Úsek podle času

V nabídce **CzechRad Studio → Uložené úseky…** klikni na
**Nový úsek podle času…**, vyber konkrétní záznam a nastav čas UTC od–do.

### Úsek podle bodů v mapě

1. V okně **Uložené úseky** klikni na **Nový úsek z mapy…**.
2. Klikni přibližně na začátek požadované části trasy. Připnutý bod bude zelený.
3. Klikni na konec trasy. Připnutý bod bude červený.
4. Druhý bod se vybírá pouze ze stejného záznamu nebo karty jako první bod.
5. Ve formuláři zkontroluj předvyplněné časy a doplň typ pohybu, název,
   výšku a orientaci detektoru, popis trasy a poznámku.
6. Potvrď vytvoření úseku.

Kliknutí vzdálené více než 500 metrů od měřené trasy se odmítne. V takovém
případě mapu přibliž a klikni znovu blíže k bodům.

## 7. Co zatím testovací verze neumí

- sama neodesílá data do SÚRO;
- nevytváří ještě hotový formulář nebo exportní balíček SÚRO;
- nerozhoduje automaticky, zda ztráta GPS skutečně znamená vstup do budovy;
- nenahrazuje odborné vyhodnocení radiační situace.

## 8. Doporučený test

Tester by měl ověřit:

1. instalaci ZIPu a spuštění pluginu;
2. vytvoření GeoPackage a mise;
3. načtení dvojice denní LOG + NOGPS.LOG;
4. správné přiblížení mapy a zobrazení legendy;
5. vytvoření úseku podle času;
6. vytvoření úseku dvěma kliknutími v mapě;
7. uložení a pozdější úpravu metadat úseku;
8. zavření a opětovné otevření QGIS a kontrolu uložených dat;
9. volitelně monitoring samostatné testovací složky nebo karty.

Při hlášení chyby uveď operační systém, přesnou verzi QGIS, verzi pluginu,
provedený krok a celý text chyby. Pomůže také snímek obrazovky. LOG obsahující
GPS trasu neposílej veřejně bez kontroly, protože může prozrazovat pohyb a
soukromá místa uživatele.

## 9. Odkazy

- [Zdrojový kód a dokumentace](https://github.com/hobitvacek/CzechRad-Studio)
- [Hlášení chyb](https://github.com/hobitvacek/CzechRad-Studio/issues)
- [Testovací vydání](https://github.com/hobitvacek/CzechRad-Studio/releases)

