# Vize CzechRad Studio

## Poslání

CzechRad Studio má uživateli umožnit soustředit se na měření, nikoli na obsluhu GIS. Plugin má převést denní LOG soubory z detektoru CzechRad na přehledné mise a měřicí úseky, bezpečně je archivovat, zobrazit na mapě a připravit podklady pro další zpracování nebo odeslání SÚRO.

## Základní principy

1. **LOG je neměnný zdroj.** Původní soubor se neupravuje a lze z něj znovu vytvořit odvozená data.
2. **Mise je pracovní celek.** Jedna mise může zahrnovat více denních LOGů.
3. **Úsek nese kontext měření.** Denní LOG lze rozdělit na pěší, automobilové, stacionární nebo vyřazené úseky s vlastními metadaty.
4. **Bez duplicit a ztráty údajů.** Aktualizace LOGu zachová již popsané úseky a označí nová data jako nezařazená.
5. **Uživatel má poslední slovo.** Automatické návrhy rozdělení, validace i export se vždy dají zkontrolovat a opravit.
6. **Soukromí je výchozí.** Polohová data zůstávají lokální, dokud uživatel výslovně nevytvoří export nebo je neodešle.
7. **Otevřenost a dohledatelnost.** Formáty, změny dat a exporty jsou verzované a auditovatelné.

## Cílový pracovní postup

1. Uživatel vloží SD kartu nebo přepne detektor do režimu přenosu dat.
2. Plugin nalezne nový či změněný denní LOG ve sledované složce.
3. Parser a validátor vytvoří měření a zobrazí trasu v QGIS.
4. Uživatel na mapě a časové ose vytvoří nebo upraví měřicí úseky.
5. Plugin doplní automaticky zjistitelná metadata a požádá jen o chybějící kontext.
6. Uživatel zkontroluje mapu, statistiky a podklady pro SÚRO.
7. Plugin vytvoří verzovaný exportní balíček; odeslání zůstává vědomým krokem uživatele.

## Mimo rozsah prvního stabilního vydání

- přímá komunikace s hardwarem v reálném čase;
- automatické odesílání formulářů bez kontroly uživatele;
- cloudová synchronizace a centrální server;
- podpora dalších detektorů bez dostupných testovacích dat a specifikace.
