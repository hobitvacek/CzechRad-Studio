# Vize CzechRad Studio

## Poslání

CzechRad Studio má uživateli umožnit soustředit se na měření, nikoli na obsluhu GIS. Plugin má převést denní LOG soubory z detektoru CzechRad na přehledné mise a měřicí úseky, bezpečně je archivovat, zobrazit na mapě a připravit podklady pro další zpracování nebo odeslání SÚRO.

## Základní principy

1. **LOG je neměnný zdroj.** Původní soubor se neupravuje a lze z něj znovu vytvořit odvozená data.
2. **Mise je pracovní celek.** Jedna mise může zahrnovat více denních LOGů.
3. **Úsek nese kontext měření.** Denní LOG lze rozdělit na pěší, automobilové, stacionární, vnitřní nebo vyřazené úseky s vlastními metadaty.
4. **Měření bez GPS není chyba.** Radiační hodnoty vzniklé v budově nebo při ztrátě signálu se zachovají jako měření bez polohy; souřadnice se nikdy automaticky nevymýšlejí.
5. **Bez duplicit a ztráty údajů.** Aktualizace LOGu zachová již popsané úseky a označí nová data jako nezařazená.
6. **Uživatel má poslední slovo.** Automatické návrhy rozdělení, přiřazení NOGPS záznamů, validace i export se vždy dají zkontrolovat a opravit.
7. **Soukromí je výchozí.** Polohová data zůstávají lokální, dokud uživatel výslovně nevytvoří export nebo je neodešle.
8. **Otevřenost a dohledatelnost.** Formáty, změny dat a exporty jsou verzované a auditovatelné.

## Cílový pracovní postup

1. Uživatel vloží dříve nastavenou SD kartu nebo přepne detektor do režimu přenosu dat.
2. Plugin kartu rozpozná, bezpečně zkopíruje nové či změněné LOGy do lokálního archivu a shodný obsah znovu nekopíruje. Zdrojovou kartu nemění.
3. Při shodě názvu a rozdílném obsahu vytvoří v archivu variantu s příponou `-1`, `-2` atd.; potom nalezne denní LOGy i soubory `NOGPS*.LOG`.
4. Parser zachová všechna radiační měření, vyhodnotí důvěryhodnost času a polohy a zobrazí trasu i časové mezery v QGIS.
5. Záznamy bez GPS se podle důvěryhodného času navrhnou k přiřazení k misi; uživatel na mapě a časové ose vytvoří nebo upraví venkovní i vnitřní měřicí úseky.
6. Plugin doplní automaticky zjistitelná metadata a požádá jen o chybějící kontext.
7. Uživatel zkontroluje mapu, statistiky a podklady pro SÚRO.
8. Plugin vytvoří verzovaný exportní balíček; odeslání zůstává vědomým krokem uživatele.

## Mimo rozsah prvního stabilního vydání

- přímá komunikace s hardwarem v reálném čase;
- automatické odesílání formulářů bez kontroly uživatele;
- cloudová synchronizace a centrální server;
- podpora dalších detektorů bez dostupných testovacích dat a specifikace.
