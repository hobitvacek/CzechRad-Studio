# Roadmapa

Roadmapa popisuje záměr, nikoli závazné termíny. Každá verze musí projít automatickými testy a ručním smoke testem v QGIS 4.

## 0.1.0 – Foundation

- [x] Struktura repozitáře a kostra QGIS pluginu.
- [x] Vize, architektura, roadmapa a návrh exportu SÚRO.
- [x] Licenční a autorské informace.
- [x] Základní kontraktní testy.

## 0.2.0 – CzechRad importer

- [ ] Specifikace a datové třídy CzechRad LOG 2.x.
- [ ] Parser bez závislosti na QGIS.
- [ ] Nezávislá validace kontrolních součtů, času, radiačních hodnot a GPS.
- [ ] Rozpoznání `NOGPS*.LOG` a zachování měření bez použitelné polohy.
- [ ] Import jednoho trasového LOGu a NOGPS zdroje bez vytváření falešné geometrie.
- [ ] Syntetická anonymizovaná testovací sada včetně ztráty GPS v budově a NOGPS souboru obsahujícího více dnů.

## 0.3.0 – Monitoring

- [ ] Výběr a uložení sledované složky.
- [ ] Detekce nových a změněných trasových i `NOGPS*.LOG` souborů.
- [ ] Kontrola ustálení souboru a bezpečné opakování.
- [ ] Aktualizace bez duplicit a bez ztráty poslední platné revize.

## 0.4.0 – GeoPackage a mise

- [ ] Verzované databázové schéma a migrace.
- [ ] Zdrojové LOGy, měření a zařízení.
- [ ] Mise složené z více denních LOGů.
- [ ] Stav importu, kontroly a archivace.

## 0.5.0 – Měřicí úseky

- [ ] Rozdělení podle času a bodů v mapě.
- [ ] Typ pohybu včetně vnitřního měření, výška, orientace a popis trasy.
- [ ] Časové přiřazení NOGPS záznamů k misi s potvrzením uživatele.
- [ ] Ruční přiřazení budovy, podlaží, popisu nebo geometrie bez přepsání původních GPS polí.
- [ ] Zvýraznění nezařazených nových dat a období bez GPS.
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
