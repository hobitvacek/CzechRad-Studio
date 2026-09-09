# CzechRad Studio – stav projektu pro pokračování

Datum zálohy: 9. září 2026

## Kde projekt najít

- repozitář: https://github.com/hobitvacek/CzechRad-Studio
- stabilní vývojová větev: `main`
- záloha před reinstalací: `backup/pre-reinstall-2026-09-09`
- veřejně otestovaná verze pluginu: `0.6.0`

Soukromý odkaz na úplnou konverzaci není v tomto veřejném souboru záměrně
uveden. Uživatel jej musí uchovat odděleně.

## Ověřený stav

- 87 automatických testů prošlo;
- plugin byl prakticky odzkoušen v QGIS;
- jeden instalační ZIP podporuje QGIS 3.22+ s Qt5 i QGIS 4.x s Qt6;
- zdrojové LOGy plugin při běžné práci úmyslně nemění.

## Hotové části

- parser CzechRad `CZRA1`, staršího `CZRDD` a Safecast `BNRDD`;
- oddělené kalibrace CzechRad 328,5 CPM/µSv/h a Safecast 334 CPM/µSv/h;
- import denního LOGu a kumulativního `NOGPS.LOG`;
- zachování radiačních hodnot bez vytváření falešných GPS souřadnic;
- monitoring složky, bezpečné kopírování a číslování souborů stejného názvu;
- GeoPackage, zařízení, mise, revize LOGů a více samostatných měření za den;
- návrhy zastavení, ztráty GPS a mezer záznamu;
- ochrana zvýšených hodnot při stacionárním měření před sloučením do průměru;
- ruční úseky podle času nebo dvěma kliknutími v mapě;
- úprava metadat úseků a zvýraznění uložených i nezařazených dat;
- místní kontrola základní připravenosti úseků pro SÚRO;
- jednoduchý uživatelský návod a návod k obnově po reinstalaci.

## Důležitá rozhodnutí

- Jeden denní LOG není automaticky jedna mise; může obsahovat více tras a úseků.
- Původní LOG je vstup a nesmí se kvůli mapě nebo exportu přepisovat.
- NOGPS s platným datem a časem se uchovává pro budoucí vnitřní úseky.
- Záznamu bez důvěryhodné polohy se poloha nikdy nevymýšlí.
- Automatické návrhy musí před použitím potvrdit uživatel.
- Externí vrstvy Safecast, SÚJB MonRas/SVZ a PAA jsou zatím pouze evidované;
  současná verze je nestahuje.
- Nic se automaticky neposílá do SÚRO ani jiné síťové služby.

## Nejbližší plán vývoje

1. Po novém nebo změněném importu nabídnout údaje pro SÚRO.
2. Umožnit volby **Uložit jako koncept**, **Připraveno ke kontrole** a
   **Vyplnit později**.
3. Při nové revizi LOGu zachovat již potvrzená uživatelská metadata.
4. Oddělit chyby a varování validátoru.
5. Exportní profil a předvyplnění formuláře dokončit až po ověření aktuálních
   požadavků se SÚRO.

## Co není ve veřejné záloze

- osobní měřicí LOGy a jejich GPS trasy;
- uživatelské GeoPackage databáze;
- QGIS projekty a profily;
- přihlašovací údaje nebo připojení k externím službám.

Tyto soubory je nutné obnovit ze soukromé zálohy uživatele.
