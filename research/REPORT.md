# Dropshipping-productonderzoek Benelux — REPORT

Datum: **20 november 2026**. Markt: BE + NL, daarna de EU. Kanaal: Shopify + TikTok/Meta. Budget: klein, solo.
Alle getallen zijn terug te voeren op `data/raw_signals.csv` (bron, URL en datum per signaal) of op de scripts in `scripts/`. Legenda: **FEIT** (staat in de bron), **AFLEIDING** (mijn redenering), **AANNAME** (niet onderbouwd, bewust gekozen), **ONBEKEND** (niet gevonden), **ONBEVESTIGD** (gevonden, maar niet opnieuw te controleren).

---

## Managementsamenvatting

1. **Breed gezocht:** 88 kandidaat-producten en 308 signalen uit TikTok-trackers (FastMoss, Kalodata, EchoTik), 17 Amazon-bestsellerlijsten (DE/FR/NL, eigen fetch), AliExpress (eigen fetch, NL-prijzen), Exploding Topics, ASInsight, Sell The Trend en Benelux-winkels. Daarvan haalden 15 de shortlist en voldoen **5 aan alle harde regels**: ≥ 3 onafhankelijke bronnen, prijs ≥ €20, bekende kostprijs en positieve marge.

2. **De belangrijkste bevinding is onprettig:** met AliExpress-inkoop en betaalde ads maakt **geen enkel product winst op een bestelling van één stuk, zelfs niet bij een CPA van €20**. Hieronder staan de maximale CPA's (= brutomarge per order). De beste is **€16,65** (zelfverwarmende dierenmand). De rest ligt tussen €6 en €13. Reden: de producten die nu trending zijn, worden in de Benelux al heel goedkoop verkocht (Amazon.de, Action, Kruidvat, ANWB, Lidl), terwijl de AliExpress-prijzen inclusief 21% btw relatief hoog zijn. *(AFLEIDING op basis van `data/unit_economics.csv`.)*

3. **Drie veelgenoemde "winners" vallen af op harde cijfers:**
   - **Oplaadbare handwarmers:** inkoop €18,69–20,19 per 2-pack, terwijl Amazon.de ze voor €11,39–18,99 verkoopt.
   - **Wake-up lights:** inkoop mediaan €37,99, terwijl bol.com budgetmodellen vanaf €29,98 heeft.
   - **"Titanium" snijplanken:** de best verkochte AliExpress-versies zijn volgens hun eigen titel van rvs 304/316, en er zijn fraudeklachten op Trustpilot. Dit is een juridisch risico (misleiding), geen kans.

4. **Advies:** test hooguit **#1, de zelfverwarmende dierenmand**, en dan eerst **organisch** (eigen TikTok-video's, CPA ≈ €0) en **in een bundel** om de orderwaarde te verhogen. Betaal pas voor ads als organische video's aantoonbaar add-to-carts opleveren. De producten #2–#5 zijn alleen interessant met een goedkopere of EU-leverancier dan ik heb kunnen vinden.

---

## Ranking van de shortlist (uit `products_scored.csv`)

![Overzicht van alle 15 producten](images/overzicht.png)

*Foto's: hoofdfoto van de beste AliExpress-leverancierslisting (bron per foto in `data/images.csv`). Handafdruk-gipsset: geen foto, want er is geen leverancier gevonden (AliExpress gaf alleen babysets; eBay, Fruugo, Walmart en Desertcart blokkeerden). Deze foto's zijn alleen voor intern onderzoek. Voor je eigen winkel en advertenties heb je toestemming van de leverancier of eigen foto's nodig.*

Totaalscore 0–10, gewichten in DECISIONS.md. "Eindlijst" = voldoet aan alle harde regels.

| # | Foto | Product | Score | Verkoop | Inkoop (mediaan) | Brutomarge | Break-even ROAS | Max CPA | Eindlijst? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | <img src="images/self-warming-pet-bed.jpg" width="90"> | **Zelfverwarmende dierenmand (cave/nest)** | **6,08** | €39,95 | €14,59 | €16,65 (41,7%) | **2,40** | €16,65 | ✅ |
| 2 | <img src="images/book-clamp-reading-light.jpg" width="90"> | Leeslampje met klem | 5,59 | €19,95 | €5,89 | €9,65 | 2,07 | €9,65 | ❌ prijs < €20; Amazon.de €10–16 met 14k–43k reviews |
| 3 | <img src="images/electric-matcha-whisk.jpg" width="90"> | Elektrische matcha-klopper | 5,23 | €14,95 | €5,59 | €5,94 | 2,52 | €5,94 | ❌ prijs < €20; Action-set €6,95 |
| 4 | <img src="images/wearable-heated-blanket.jpg" width="90"> | **Draagbare USB-warmtedeken** | **4,80** | €59,95 | €34,59 | €10,74 (17,9%) | 5,58 | €10,74 | ✅ |
| 5 | <img src="images/electric-ice-scraper.jpg" width="90"> | Elektrische ijskrabber | 4,60 | €49,95 | €25,99 (1 listing) | €11,96 | 4,18 | €11,96 | ❌ < 3 bron-domeinen |
| 6 | <img src="images/fascia-massage-ring.jpg" width="90"> | **Fascia-massagering (elektrisch)** | **4,60** | €44,95 | €24,59 | €9,44 (21,0%) | 4,76 | €9,44 | ✅ |
| 7 | <img src="images/sunrise-alarm-clock.jpg" width="90"> | Wake-up light | 4,40 | €44,95 | €37,99 | −€5,03 | n.v.t. | — | ❌ negatieve marge |
| 8 | <img src="images/bluetooth-label-printer.jpg" width="90"> | Bluetooth-labelprinter | 4,40 | €39,95 | €33,89 | −€4,63 | n.v.t. | — | ❌ negatieve marge |
| 9 | <img src="images/mug-warmer.jpg" width="90"> | Mok-warmer | 4,34 | €19,95 | €9,29 | €5,99 | 3,33 | €5,99 | ❌ prijs < €20 |
| 10 | <img src="images/hand-casting-kit.jpg" width="90"> | Handafdruk-gipsset (Valentijn) | 4,30 | €29,95 | ONBEKEND | ONBEKEND | ONBEKEND | — | ❌ geen leverancier gevonden |
| 11 | <img src="images/cordless-pressure-washer.jpg" width="90"> | **Draadloze hogedrukreiniger (auto)** | **4,20** | €59,95 | €32,19 | €13,33 (22,2%) | 4,50 | €13,33 | ✅ |
| 12 | <img src="images/rechargeable-hand-warmer.jpg" width="90"> | Oplaadbare handwarmer | 4,15 | €24,95 | €20,39 | −€2,15 | n.v.t. | — | ❌ negatieve marge |
| 13 | <img src="images/heated-seat-cushion.jpg" width="90"> | Verwarmd zitkussen 12V | 4,05 | €39,95 | €20,79 | €9,51 | 4,20 | €9,51 | ❌ < 3 bron-domeinen |
| 14 | <img src="images/heated-eye-mask.jpg" width="90"> | **Verwarmd oogmasker (USB)** | **3,75** | €29,95 | €16,89 (2 listings) | €6,00 (20,0%) | 4,99 | €6,00 | ✅ |
| 15 | <img src="images/titanium-cutting-board.jpg" width="90"> | "Titanium" snijplank | 3,30 | €34,95 | €38,79 (puur titanium) | −€13,18 | n.v.t. | — | ❌ negatieve marge + misleiding |

Ter vergelijking (**ONBEVESTIGD**, de bron gaf 403 bij herverificatie): in zoekresultaten noemde Triple Whale een mediaan-ROAS op Meta van ~1,88, en 2,25 voor Home & Garden. Als die cijfers ongeveer kloppen, zit zelfs #1 (break-even ROAS 2,40) boven het gemiddelde dat adverteerders halen.

**Waarom niet 10 producten in de eindlijst:** de overige producten breken een harde regel. Ik heb de lijst niet aangevuld met gokken (zie DECISIONS.md §5).

---

## De 5 producten van de eindlijst

### 1. Zelfverwarmende dierenmand (cave/nest, zonder stroom) — score 6,08

<img src="images/self-warming-pet-bed.jpg" width="260">

**Waarom nu (AFLEIDING):** de winterpiek loopt van december tot februari. Er zit geen elektronica in, dus het compliance-risico is het laagste van de hele lijst. Sell The Trend zette het product als pick voor januari 2026.

**Bewijs:**
- **FEIT, herbevestigd:** Sell The Trend, "SnuggleHeat Self-Warming Pet Bed", januari 2026: *"$64,335 Estimated Monthly Revenue. Buy for $6.52, sell for $39.95"*. Bron: [sellthetrend.com/blog/winning-products](https://www.sellthetrend.com/blog/winning-products). Dit is een schatting van de tool zelf.
- **FEIT, gecorrigeerd na herverificatie:** Chewy, Mora Pets Self-Warming Cat Bed: 4,6 sterren, 237 beoordelingen, $18,56 (Small). Bron: [chewy.com](https://www.chewy.com/best/heated-cat-beds_s112296).
- **FEIT:** roundup "best heated pet beds" van oktober 2026. Bron: [fypower.org](https://fypower.org/best-heated-pet-beds-for-winter/).
- **FEIT (eigen fetch):** 7 relevante AliExpress-listings met ≥ 100 verkocht, €11,59–24,99. Beste listing: ["Bear Head Shape Nest… Self-Warming", €14,59, 246 verkocht, 4,6★](https://www.aliexpress.com/item/1005007856096850.html).
- **FEIT, prijsanker NL:** zelfverwarmende matjes kosten €10,99–20,09 ([beslist.nl](https://www.beslist.nl/products/dieren_accessoires/r/warmtemat/)), gewone manden €25,99–59,99 (bol.com), en de Lanaform verwarmingsmand €87,20 (MediaMarkt BE).

**Unit economics (`scripts/margins.py`):**
- Verkoop €39,95 (AFLEIDING), inkoop €14,59 (p25 €13,38 tot p75 €17,24).
- Brutomarge €16,65 (41,7%), break-even ROAS 2,40, max CPA €16,65.
- Max CPC bij 2% conversie (AANNAME): €0,33.
- Bij een CPA van €40 (scenario) zou een orderwaarde van ~€96 nodig zijn.

**Leverancier:** AliExpress (China). Levertijd naar NL is ONBEKEND, want de productpagina's waren niet uit te lezen. EU-voorraad is niet bevestigd. Alternatief: zoek "self-warming cat cave" in de CJ- en Spocket-app met filter op EU-warehouse.

**Risico's:**
- Maatkeuze (S/M/L) leidt tot retouren.
- Volumineus pakket, dus verzendkosten bij een EU-leverancier.
- Geur of kwaliteit van goedkoop pluche.
- De claim "zelfverwarmend" betekent eigenlijk "isolerend/reflecterend". Overdrijf dat niet in je advertenties (misleiding).
- Na februari is er weinig vraag meer.

**Marketing:** doelgroep katten- en kleine-hondeneigenaren van 25–55 jaar in NL/BE, eigenaren van oudere dieren en mensen die de verwarming lager zetten.
- *Hook 1:* "Ligt jouw kat ook altijd op de verwarming? Kijk wat er gebeurt als je dít neerlegt."
- *Hook 2:* "Geen stekker, geen stroom, toch warm: 30-secondentest met mijn kat."
- *Hook 3:* "De verwarming gaat 's nachts uit… deze 3 dieren hadden het niet door."
- *Bundel:* mand + zelfverwarmend matje (inkoop €4–9) voor €54,95, of 2e mand −20%.

**Falingsargument (advocaat van de duivel):** het bewijs voor groei is dun. Er is geen enkel groeicijfer, alleen een vermelding in januari bij een tool die zelf aan dropshippers verkoopt, en Amerikaanse lijstjes. Chewy verkoopt een vergelijkbare mand voor **$18,56**, dus jouw €39,95 is twee keer de Amerikaanse winkelprijs. In NL koop je een mand bij bol voor €26–30. Met een max CPA van €16,65 verdien je **alleen geld met organisch bereik**. Een klein budget aan betaalde ads is waarschijnlijk binnen een week op zonder winst.

**Eerste teststap:**
1. **Week 1: €0.** Bestel 1 testexemplaar (≈ €15) en film 3 korte video's (hooks hierboven) voor TikTok en Reels.
2. **Organisch doel:** ≥ 1 video met > 5.000 views en een kliks-naar-shop-ratio ≥ 1%.
3. **Pas dan €50 betaald** (TikTok Spark Ads op de beste organische video). Stop zodra de CPC > €0,33 na €20 uitgave, of als er 0 add-to-carts zijn na €35.

---

### 2. Draagbare USB-warmtedeken / warmtesjaal — score 4,80

<img src="images/wearable-heated-blanket.jpg" width="260">

**Waarom nu (AFLEIDING):** het is volop winter. AliExpress-listings die op 3 en 15 november 2026 zijn geplaatst, staan al op 183–900+ verkocht (eigen fetch). Dat is het sterkste "nieuw en stijgend"-signaal uit dit onderzoek.

**Bewijs:**
- **FEIT (eigen fetch):** [listing geplaatst 2026-11-15, 900+ verkocht, €50,75](https://www.aliexpress.com/item/1005013630579646.html) en [listing geplaatst 2026-11-15, 457 verkocht, €44,81](https://www.aliexpress.com/item/1005013642860874.html).
- **FEIT, herbevestigd:** ANWB Pleafs draadloze warmtedeken €87,96 (normaal €109,95). Bron: [anwb.nl](https://www.anwb.nl/webwinkel/p/237718/warmtedeken-40x110cm?anwb_color=21531).
- **FEIT:** Benable-lijst "Viral right now, November 2026" noemt de Bedsure Heated Blanket. Bron: [benable.com](https://benable.com/lulosyyc2/what-s-viral-right-now-november-2026-the-tiktok-finds-everyone-s-buying-before-they-sell-out).
- **FEIT:** dodropshipping (data van Sell The Trend) meldt voor de shark blanket "over $158k in sales from 11 stores", met een gemiddelde marge van 69%. Bron: [dodropshipping.com](https://dodropshipping.com/winning-dropshipping-product-examples/).
- **ONBEVESTIGD (403):** USB-poncho €44,74 op Fruugo en Lanaform Heat Wrap €74,12 bij MediaMarkt BE.

**Unit economics:**
- Verkoop €59,95, inkoop mediaan €34,59 (p25 €26,69 tot p75 €42,10).
- Brutomarge €10,74 (17,9%), break-even ROAS 5,58, max CPA €10,74, max CPC €0,21.
- Met inkoop op p25 (€26,69) stijgt de marge naar ~€19,3. Dat is AFLEIDING, dezelfde formule.

**Leverancier:** de goedkoopste bewezen listing is een [USB-warmtesjaal voor nek en schouders, €16,06, 479 verkocht](https://www.aliexpress.com/item/1005010439420305.html). Dat is een kleiner product. Er wordt geen powerbank meegeleverd. EU-voorraad is ONBEKEND.

**Risico's:**
- Verwarmingselement op het lichaam. Hittegerelateerde producten zijn een focus van EU Safety Gate (alert "heated plush", 3 juli 2026, brandwonden).
- CE- en GPSR-documentatie van de leverancier is nodig.
- "Powerbank niet inbegrepen" leidt tot teleurstelling en retouren.
- Het seizoen stopt in maart.

**Marketing:** thuiswerkers en mensen die op stookkosten besparen, 30–65 jaar.
- *Hook 1:* "Thuiswerken met de verwarming op 17 graden? Zo houd ik het vol."
- *Hook 2:* "Een deken met een knop."
- *Hook 3:* "Mijn vriendin pakt hem elke avond af."
- *Bundel:* 2 stuks −15%. Een powerbank als upsell raad ik af, want dat is een losse lithiumbatterij en valt onder de uitsluiting.

**Falingsargument:** met een break-even ROAS van 5,6 moet je ongeveer 3× beter adverteren dan het (onbevestigde) Meta-gemiddelde. De ANWB verkoopt een merkversie met accu voor €88, wat het vertrouwen van klanten wint van een nieuwe Shopify-store. En de nieuwste AliExpress-listings betekenen ook dat andere verkopers precies nu instappen (hoeveel is ONBEKEND: de Meta Ad Library was niet bereikbaar).

**Eerste teststap:** alleen doorgaan als je een leverancier vindt met inkoop ≤ €25 (liefst met EU-voorraad). Daarna €50 TikTok, 3 creatives. Stop zodra de CPC > €0,21 na €20, of bij 0 add-to-carts na €35. Deadline voor de test: half januari, vanwege het seizoen.

---

### 3. Elektrische fascia-massagering — score 4,60

<img src="images/fascia-massage-ring.jpg" width="260">

**Waarom nu (AFLEIDING):** januari draait om goede voornemens, fitness en herstel. In de US was het in juli 2026 een topproduct op TikTok Shop. Ik vond nog maar weinig Benelux-aanbieders.

**Bewijs:**
- **FEIT, herbevestigd:** Kalodata via Quicksync: *"ADDWIN's Fascia Ring mini massage device did $1.78 million in July 2026 at $22.39 a unit"*. Bron: [quicksync.pro](https://quicksync.pro/blog/tiktok-shop-trending-products-2026/).
- **FEIT:** Sell The Trend noemt de FlexRelief Fascia Ring in mei 2026 met een geschatte omzet van $53.025 per maand (uit een samenvatting van de pagina, niet woordelijk).
- **FEIT (eigen fetch):** [Electric Fascia Ring met warmte en riem, €31,99, 1.000+ verkocht](https://www.aliexpress.com/item/1005009874177673.html).
- **ONBEVESTIGD (403):** MediaMarkt NL €74,99 en BE €43,99 (promo) voor een "Italian Design"-massagering.
- **FEIT, prijsbodem:** eBay.de €18,83 voor een vibrerende ring.

**Unit economics:**
- Verkoop €44,95, inkoop mediaan €24,59 (3 elektrische listings, p25 €20,79 tot p75 €28,29).
- Brutomarge €9,44 (21,0%), break-even ROAS 4,76, max CPA €9,44, max CPC €0,19.

**Risico's:**
- AliExpress-titels beloven "fat burning". **Gezondheids- en afslankclaims zijn in de EU niet toegestaan.**
- Massageapparaat met accu, dus CE/EMC- en batterijdocumentatie nodig.
- Het US-succes is geen garantie voor de Benelux.

**Marketing:** kantoorwerkers en recreatieve sporters van 25–50 jaar.
- *Hook 1:* "Na 8 uur zitten: 60 seconden voor je kuiten."
- *Hook 2:* "Massagegun vs. deze ring."
- *Hook 3:* "Wat gebeurt er als je dit om je bovenarm doet?"
- *Bundel:* 2e ring voor je partner −20%.

**Falingsargument:** het enige Europese bewijs is één marketplace-listing bij MediaMarkt, waarvan de prijs niet te bevestigen was. De piek in de US lag in juli. Op eBay.de staat er al een voor €18,83, zodat Europese klanten jouw €44,95 makkelijk kunnen onderbieden. Met een max CPA van €9,44 is betaald adverteren vrijwel kansloos.

**Eerste teststap:** alleen organisch (3 video's, week 1–2) in januari. Betaalde test alleen als een video > 10.000 views haalt.

---

### 4. Draadloze hogedrukreiniger (auto/tuin) — score 4,20

<img src="images/cordless-pressure-washer.jpg" width="260">

**Waarom (AFLEIDING):** in de US was het een TikTok-topper in juli 2026. Op TikTok Shop in Europa groeit de categorie Home Improvement met +202% tot +298%. Het product scoort het hoogst op wow-factor (9/10).

**Bewijs:**
- **FEIT, herbevestigd:** Kalodata: *"SEESE's 1000PSI cordless pressure washer did $1.97 million on TikTok Shop in July 2026"*. Bron: [quicksync.pro](https://quicksync.pro/blog/tiktok-shop-trending-products-2026/).
- **FEIT:** Lengow/Kalodata, TikTok Shop Home Improvement 11 april tot 9 juli 2026: DE +228%, FR +202%, ES +298%, IT +207%. Bron: [blog.lengow.com](https://blog.lengow.com/tiktok-shop-europe-q2-2026-e500m-across-four-markets/).
- **FEIT (eigen fetch):** 7 accu-listings met ≥ 100 verkocht, bijvoorbeeld een [Portable Cordless Pressure Washer, €43,79, 405 verkocht](https://www.aliexpress.com/item/1005012692809628.html).

**Unit economics:**
- Verkoop €59,95 (**AANNAME**, ik vond geen NL-concurrentieprijs), inkoop mediaan €32,19.
- Brutomarge €13,33 (22,2%), break-even ROAS 4,50, max CPA €13,33, max CPC €0,27.

**Risico's:**
- Lithium-accupack (transportregels) en letselwaarschuwingen bij hoge druk.
- Lidl verkoopt een Parkside-accureiniger (DE-folder juli 2026).
- Veel AliExpress-listings zijn "voor Makita-accu", dus **zonder accu**. Dat geeft verwarring en retouren.

**Marketing:** autobezitters zonder buitenkraan, appartementbewoners en fietsers, 25–55 jaar.
- *Hook 1:* "Auto wassen zonder kraan."
- *Hook 2:* "Kijk wat 3 seconden met deze velg doen."
- *Hook 3:* "€10 bij de wasstraat vs. dit."
- *Bundel:* schuimkop plus microvezeldoeken.

**Falingsargument:** **het seizoen is fout.** In de Benelux wast bijna niemand in december of januari zijn auto buiten. De vraag begint pas rond maart (AFLEIDING), zodat de test pas over 3–4 maanden zinvol is. Discounters (Lidl Parkside) zetten een lage prijs neer, en de verkoopprijs van €59,95 is een aanname zonder bron.

**Eerste teststap:** in februari een NL-prijsonderzoek doen (Lidl, Action, Praxis, bol). Begin maart €50 TikTok met 3 creatives. Stop zodra de CPC > €0,27.

---

### 5. Verwarmd oogmasker (USB) — score 3,75

<img src="images/heated-eye-mask.jpg" width="260">

**Waarom (AFLEIDING):** winter, ogen moe van schermen, positionering op slaap. Dit is het zwakst onderbouwde product van de vijf.

**Bewijs:**
- **FEIT:** Accio noemt de categorie "poised for growth" (kwalitatief). Bron: [accio.com](https://www.accio.com/business/heated-eye-mask-trends).
- **FEIT (eigen fetch):** 2 relevante listings met ≥ 100 verkocht, onder andere [Electric Heated Eye Massager, €19,19, 167 verkocht](https://www.aliexpress.com/item/1005007480941484.html).
- **FEIT, NL-prijzen:** Blephasol €27,95 (medisch hulpmiddel) en Renpho Eyeris 1 €61,99. Bron: [deonlinedrogist.nl](https://www.deonlinedrogist.nl/drogist/blephasol-verwarmend-oogmasker-1st.htm).
- **FEIT:** Walmart FACEMOON $19,99 (was $35,99). Daaruit blijkt prijsdruk.

**Unit economics:** verkoop €29,95, inkoop €16,89, brutomarge €6,00 (20,0%), break-even ROAS 4,99, max CPA €6,00, max CPC €0,12.

**Risico's:** **"Droge ogen" of "MGD" is een medische claim.** In NL worden zulke maskers als medisch hulpmiddel verkocht. Zeg het niet. Verder warmte bij de ogen en maar 2 leveranciers.

**Marketing:** schermwerkers en mensen met slaapproblemen.
- *Hook 1:* "10 minuten na een dag beeldscherm."
- *Hook 2:* "Mijn avondritueel in 3 stappen."
- *Hook 3:* "Warmte + donker = …"

**Falingsargument:** €6 marge, 2 leveranciers, en de sterkste verkooptekst ("droge ogen") mag je juridisch niet gebruiken. Met deze cijfers is het geen product om mee te starten.

**Eerste teststap:** niet testen, tenzij een EU-leverancier een inkoopprijs ≤ €10 biedt.

---

## Wat de cijfers zeggen over het model zelf (AFLEIDING)

- **Trending is niet hetzelfde als winstgevend.** De sterkste vraagsignalen in de Benelux (Amazon.nl Sport #1/#5/#6 handwarmers, Amazon.de Lighting leeslampjes met 43.000 reviews) gaan over producten die marketplaces al voor €10–19 verkopen. Een nieuwe Shopify-store met betaalde ads kan daar niet tegenop.
- **De btw maakt AliExpress duur voor de Benelux.** Prijzen zijn inclusief 21% btw, en het douanerecht van €3 per artikel geldt sinds juli 2026 (al eerder in dit gesprek met bronnen besproken). Daardoor is het "AliExpress-margevoordeel" uit oude cursussen grotendeels verdwenen.
- **Wat de rekensom wél kan laten kloppen:**
  1. organisch TikTok-bereik (CPA ≈ €0);
  2. bundels die de orderwaarde boven ~€80–100 tillen;
  3. een B2B-leverancier (btw aftrekbaar, scheelt ~17% op de inkoop);
  4. een eigen merk of niche met een prijs die niet direct naast Amazon staat.

## Bestanden

| Bestand | Inhoud |
|---|---|
| `REPORT.pdf` / `REPORT.html` | dit rapport met alle foto's erin (gemaakt met `scripts/build_report_pdf.py`) |
| `products_scored.csv` | alle 15 shortlistproducten met scores, onderbouwing per score, marges en leverancierslink |
| `data/raw_signals.csv` | 308 ruwe signalen (product, bron, url, metric, waarde, datum) |
| `data/filter_results.csv` | oordeel per kandidaat in fase 2 met reden |
| `data/unit_economics.csv` | marge, break-even ROAS, max CPA/CPC, CPA-scenario's per product |
| `data/verification.csv` | herverificatie van de belangrijkste cijfers in fase 5 |
| `images/` + `data/images.csv` | productfoto per shortlistproduct, `overzicht.png` (alle 15) en bron per foto |
| `data/aliexpress_search*.json`, `data/amazon_lists.json` | ruwe data van de eigen fetch |
| `scripts/` | fetch-, filter-, marge- en scoringsscripts (reproduceerbaar) |
| `DECISIONS.md`, `LIMITATIONS.md` | keuzes, aannames, gewichten en wat ontbrak |

**Opnieuw draaien:**

```bash
cd research/scripts && python3 build_signals.py && python3 filter_candidates.py && python3 margins.py && python3 score.py
```
