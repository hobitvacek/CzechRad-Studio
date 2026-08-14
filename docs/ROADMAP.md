# Roadmapa

Roadmapa popisuje z mØr, nikoli z vazn‚ term¡ny. Ka§d  verze mus¡ proj¡t automatickìmi testy a ruŸn¡m smoke testem v podporovan‚m QGIS 3 i QGIS 4.

## 0.1.0 - Foundation

- [x] Struktura repozit ýe a kostra QGIS pluginu.
- [x] Vize, architektura, roadmapa a n vrh exportu SéRO.
- [x] LicenŸn¡ a autorsk‚ informace.
- [x] Z kladn¡ kontraktn¡ testy.

## 0.2.0 - CzechRad importer

- [x] Specifikace a datov‚ tý¡dy CzechRad LOG 2.x.
- [x] Parser bez z vislosti na QGIS.
- [x] Validace kontroln¡ch souŸt…, Ÿasu, GPS a Ÿ¡selnìch pol¡.
- [x] Import jednoho LOGu do doŸasn‚ vrstvy.
- [x] Anonymizovan  testovac¡ sada.

## 0.3.0 - Monitoring

- [x] VìbØr a ulo§en¡ sledovan‚ slo§ky.
- [x] Detekce novìch a zmØnØnìch LOG….
- [x] Kontrola ust len¡ souboru a bezpeŸn‚ opakov n¡.
- [x] Aktualizace bez duplicit a bez ztr ty posledn¡ platn‚ revize.

## 0.3.1 - QGIS 3 / QGIS 4 compatibility

- [x] Jedinì k¢d a instalaŸn¡ ZIP pro QGIS 3.22+ a QGIS 4.x.
- [x] Qt5/Qt6 kompatibiln¡ enumy dialog…, tlaŸ¡tek a typ… atribut….
- [x] Import `QAction` a spouçtØn¡ dialog… nez visl‚ na verzi Qt.
- [x] Zachov n¡ kompatibility se starç¡m Pythonem pou§¡vanìm linuxovìmi sestaven¡mi QGIS 3.

## 0.4.0 - GeoPackage a mise

- [x] Verzovan‚ datab zov‚ sch‚ma a migrace.
- [x] Zdrojov‚ LOGy, mØýen¡ a zaý¡zen¡.
- [x] Mise slo§en‚ z v¡ce denn¡ch LOG….
- [x] Stav importu, aktu ln¡ revize a archivace pýedchoz¡ch reviz¡.

## 0.5.0 - MØýic¡ £seky

- [x] RuŸn¡ rozdØlen¡ konkr‚tn¡ho z znamu podle Ÿasu.
- [ ] RuŸn¡ vìbØr hranic £seku podle bod… v mapØ.
- [x] Pýehled a potvrzov n¡ automatickìch n vrh… v aktivn¡ misi.
- [x] ZvìraznØn¡ vybran‚ho automatick‚ho n vrhu v mapØ.
- [x] Pýehled, oprava metadat a mapov‚ zvìraznØn¡ ulo§enìch £sek….
- [x] Typ pohybu, vìçka, orientace a popis trasy u potvrzenìch n vrh….
- [ ] ZvìraznØn¡ nezaýazenìch novìch dat.
- [x] Datab zovì model n vrh… a u§ivatelskìch £sek… odolnì v…Ÿi reviz¡m LOGu.
- [x] N vrhy podle delç¡ch mezer, zastaven¡ a ztr ty GPS.
- [ ] DoplnØn¡ n vrh… podle rychlosti po ovØýen¡ na v¡ce pý¡stroj¡ch a tras ch.

## 0.6.0 - Podklady pro SéRO

- [ ] Dialog metadat po importu s mo§nost¡ odlo§it vyplnØn¡.
- [ ] Metadata po jednotlivìch £sec¡ch.
- [ ] Validace proti schv len‚mu exportn¡mu profilu.
- [ ] PýedvyplnØnì formul ý nebo exportn¡ bal¡Ÿek po ovØýen¡ se SéRO.
- [ ] Evidence reviz¡ a u§ivatelsky potvrzen‚ho odesl n¡.

## 1.0.0 - Prvn¡ stabiln¡ vyd n¡

- [ ] Dokumentovanì instalaŸn¡ ZIP.
- [ ] Migrace dat mezi podporovanìmi verzemi.
- [ ] ¬esk  u§ivatelsk  dokumentace.
- [ ] Stabiln¡ import, monitoring, mise, £seky a kontrolovanì export.
- [ ] OvØýenì postup pro podporovanì QGIS 3 i aktu ln¡ QGIS 4.

## Po verzi 1.0

- statistiky, grafy, heatmapy a trasy;
- exporty CSV, GeoJSON, GPX a reporty;
- dalç¡ zaý¡zen¡ pýes oddØlen‚ reader rozhran¡;
- voliteln  synchronizace a§ po samostatn‚m bezpeŸnostn¡m n vrhu.
