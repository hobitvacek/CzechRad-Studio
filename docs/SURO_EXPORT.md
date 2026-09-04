# Návrh exportu pro SÚRO

## Stav dokumentu

Toto je technický návrh, nikoli oficiální specifikace SÚRO. Před implementací je nutné potvrdit aktuální pole, povinné údaje, způsob přiložení LOG souborů a přijatelné formáty přímo se SÚRO.

Referenční zdroje:

- https://www.suro.cz/aplikace/czechrad-wiki/index.php/Detektor_SAFECAST_bGeigie_Nano_-_protokoly
- https://docs.google.com/forms/d/e/1FAIpQLSd0gvlxChO1ZA1T3_KRN3AYtVJHoSnxzIemJmNIqiNpy3nMoA/viewform

## Zásady

- Původní denní LOG se vždy archivuje beze změny.
- Pro odeslání lze vytvořit odvozené LOGy jednotlivých potvrzených úseků;
  CzechRad Studio je označí jako odvozené a zachová platnou strukturu i kontrolní součty.
- Jeden denní LOG může obsahovat více měřicích úseků s rozdílnými podmínkami.
- Plugin předvyplní pouze údaje, které lze spolehlivě odvodit.
- Uživatel musí před exportem potvrdit údaje, které LOG neobsahuje.
- Plugin formulář automaticky neodešle bez vědomého kroku uživatele.
- Stav „odesláno“ je uživatelské potvrzení, dokud neexistuje oficiální potvrzovací API.

## Navržený pracovní postup

1. Nový nebo změněný LOG se bezpečně načte a zobrazí na mapě.
2. Plugin nabídne dialog **Údaje pro SÚRO** s možnostmi:
   - uložit jako koncept;
   - připravit ke kontrole;
   - vyplnit později.
3. Při změně LOGu se existující údaje zachovají a aktualizují se pouze odvozené statistiky.
4. Nové body se označí jako nezařazené, dokud je uživatel nepřiřadí k úseku.
5. Před exportem validátor zobrazí chyby a varování odděleně.
6. Uživatel zkontroluje předvyplněný formulář nebo vytvořený balíček a teprve poté jej odešle.

## Ověřený komunitní způsob odesílání

Následující struktura vychází z anonymizovaného příkladu uživatele, který data
z CzechRad pravidelně odesílá déle než jeden rok. Je to praktický vzor, nikoli
oficiální nebo neměnná specifikace SÚRO. Zdrojový snímek ani osobní údaje se
neukládají do repozitáře.

### E-mail

- příjemce `czechrad@suro.cz`;
- předmět ve tvaru `Data z přístroje CzechRad <číslo zařízení>`;
- krátká informace, zda byla data rozdělena nebo upravena v GIS;
- způsob zveřejnění jména odesílatele;
- očíslovaný seznam přiložených měřicích úseků.

### Popis každého úseku

- název přiloženého LOGu;
- datum měření;
- místo nebo slovní popis trasy;
- způsob pohybu, například chůze, kolo nebo automobil;
- přibližná výška detektoru nad zemí;
- způsob nesení detektoru;
- orientace sondy;
- volitelná poznámka, například rozdělení měření přes půlnoc.

### Více úseků stejného dne

Odvozené soubory používají stabilní pořadové označení, například:

```text
07960719.1.LOG
07960719.2.LOG
07960719.3.LOG
```

Číslování se v pozdější revizi nemění. Nově vytvořený úsek dostane další volné
číslo, aby bylo možné dohledat dříve odeslané přílohy.

### Generovaný text

```text
Dobrý den,

zasílám data naměřená přístrojem CzechRad <zařízení>. Denní záznam byl
v programu CzechRad Studio rozdělen na jednotlivé měřicí úseky.

1. <název souboru>
Datum: <datum>
Trasa: <místo nebo trasa>
Způsob měření: <způsob pohybu>
Výška detektoru: <výška>
Umístění: <způsob nesení>
Orientace sondy: <orientace>
Poznámka: <volitelná poznámka>

Data můžete zveřejnit pod jménem: <jméno, přezdívka nebo anonymně>.
```

CzechRad Studio připraví text a přílohy, ale před první stabilní verzí nebude
e-mail bez výslovné kontroly uživatele automaticky odesílat.

## Metadata

### Automaticky z LOGu

- název a otisk zdrojového souboru;
- zařízení a sériové číslo, pokud je ve formátu přítomné;
- čas začátku a konce v UTC;
- počet všech, platných a vyřazených měření;
- časový rozsah a základní prostorový rozsah vybraných úseků;
- použitá verze parseru a exportního profilu.

### Vyplňuje nebo potvrzuje uživatel

- způsob měření pro každý úsek;
- výška a orientace detektoru;
- slovní popis trasy nebo úseku;
- informace o případném převozu radioaktivního materiálu;
- způsob uvedení autora a případné kontaktní údaje;
- poznámky k nestandardním podmínkám.

Přesné názvy, typy a povinnost polí budou uloženy ve verzovaném exportním profilu až po jejich ověření.

## Revize

Pokud byl LOG po vytvoření exportu změněn, původní export se nepřepisuje. Vznikne nová revize s vazbou na předchozí balíček, novým otiskem vstupu a seznamem změn. Uživatel je výslovně upozorněn, pokud dřívější revizi označil jako odeslanou.

## Navržený balíček

Dokud SÚRO nepotvrdí jinou strukturu, lokální archiv může obsahovat:

```text
CRS-YYYY-NNNNN-revN/
├── source/<originalni-soubor>.LOG
├── metadata.json
├── summary.txt
└── manifest.sha256
```

`metadata.json` a `manifest.sha256` jsou interní pomůcky CzechRad Studio a nesmí být prezentovány jako formát požadovaný SÚRO. Exportní funkce musí umět vytvořit také pouze podklady, které uživatel skutečně potřebuje k aktuálnímu formuláři.

## Ochrana soukromí

Export obsahuje citlivou časovou a polohovou stopu. Před vytvořením balíčku musí plugin zobrazit vybrané úseky a příjemce. Koncepty a logy nesmí být bez souhlasu nahrávány do GitHub Issues, telemetrie ani jiné síťové služby.

