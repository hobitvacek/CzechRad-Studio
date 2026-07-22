# Roadmapa

Roadmapa popisuje záměr, nikoli závazné termíny. Každá verze musí projít automatickými testy a ručním smoke testem v QGIS 4.

## 0.1.0 – Foundation

- [x] Struktura repozitáře a kostra QGIS pluginu.
- [x] Vize, architektura, roadmapa a návrh exportu SÚRO.
- [x] Licenční a autorské informace.
- [x] Základní kontraktní testy.

## 0.2.0 – CzechRad importer

- [x] Specifikace a datové třídy CzechRad LOG 2.x.
- [x] Parser bez závislosti na QGIS.
- [x] Validace kontrolních součtů, času, GPS a číselných polí.
- [x] Import jednoho LOGu do dočasné vrstvy.
- [x] Anonymizovaná testovací sada.

## 0.3.0 – Monitoring

- [x] Výběr a uložení sledované složky.
- [x] Detekce nových a změněných LOGů.
- [x] Kontrola ustálení souboru a bezpečné opakování.
- [x] Aktualizace bez duplicit a bez ztráty poslední platné revize.

## 0.4.0 – GeoPackage a mise

- [ ] Verzované databázové schéma a migrace.
- [ ] Zdrojové LOGy, měření a zařízení.
- [ ] Mise složené z více denních LOGů.
- [ ] Stav importu, kontroly a archivace.

## 0.5.0 – Měřicí úseky

- [ ] Rozdělení podle času a bodů v mapě.
- [ ] Typ pohybu, výška, orientace a popis trasy.
- [ ] Zvýraznění nezařazených nových dat.
- [ ] Návrhy hranic podle mezer, rychlosti a zastavení.

## 0.6.0 – Podklady pro SÚRO

- [ ] Dialog metadat po importu s možností odložit vyplnění.
- [ ] Metadata po jednotlivých úsecích.
- [ ] Validace proti schválenému exportnímu profilu.
- [ ] Předvyplněný formulář nebo exportní balíček po ověření se SÚRO.
- [ ] Evidence revizí a uživatelsky potvrzeného odeslání.

## 1.0.0 – První stabilní vydání

- [ ] Dokumentovaný instalační ZIP.
- [ ] Migrace dat mezi podporovanými verzemi.
- [ ] Česká uživatelská dokumentace.
- [ ] Stabilní import, monitoring, mise, úseky a kontrolovaný export.
- [ ] Ověřený postup pro aktuální QGIS 4.

## Po verzi 1.0

- statistiky, grafy, heatmapy a trasy;
- exporty CSV, GeoJSON, GPX a reporty;
- další zařízení přes oddělené reader rozhraní;
- volitelná synchronizace až po samostatném bezpečnostním návrhu.

