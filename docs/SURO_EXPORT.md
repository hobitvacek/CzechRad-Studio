# Návrh exportu pro SÚRO

## Stav dokumentu

Toto je technický návrh, nikoli oficiální specifikace SÚRO. Před implementací je nutné potvrdit aktuální pole, povinné údaje, způsob přiložení LOG souborů a přijatelné formáty přímo se SÚRO.

Referenční zdroje:

- https://www.suro.cz/aplikace/czechrad-wiki/index.php/Detektor_SAFECAST_bGeigie_Nano_-_protokoly
- https://docs.google.com/forms/d/e/1FAIpQLSd0gvlxChO1ZA1T3_KRN3AYtVJHoSnxzIemJmNIqiNpy3nMoA/viewform

## Zásady

- Původní LOG se do exportu přikládá beze změny.
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
