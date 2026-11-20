# DECISIONS — keuzes, aannames en gewichten

Onderzoeksdatum: **2026-11-20** (gecontroleerd met `date`: Fri Nov 20 22:48 UTC 2026).
Doelmarkt: België + Nederland, kanaal: Shopify + TikTok/Meta-ads, solo-starter met klein budget.

Legenda: **FEIT** = staat letterlijk in een bron (zie `data/raw_signals.csv`), **AFLEIDING** = mijn redenering op basis van feiten, **AANNAME** = niet onderbouwd met een bron, bewust gekozen.

## 1. Opzet en werkwijze

| # | Beslissing | Type | Reden |
|---|---|---|---|
| D1 | Map `research/` in de bestaande repo in plaats van `/research` op de root van het bestandssysteem | Keuze | Alleen bestanden in de werkmap zijn voor de gebruiker te openen en te committen |
| D2 | Geen bot-checks, captcha's of login-muren omzeilen. Een geblokkeerde pagina = één poging, gelogd als BLOCKED | Keuze | Ethisch en contractueel. Zie LIMITATIONS.md |
| D3 | Amazon-lijsten in een gewone headless browser, één keer per URL, 3 s pauze (`scripts/fetch_amazon_lists.js`) | Keuze | Movers & Shakers gaf overal BLOCKED of EMPTY. Best Sellers (DE/FR/NL) laadden wel |
| D4 | AliExpress-zoekresultaten met NL-locale (EUR), gesorteerd op orders, met 20 s pauze na een rate limit (`scripts/aliexpress_search.py`) | Keuze | Geeft prijs, aantal verkocht, rating en plaatsingsdatum per listing |
| D5 | Kandidaten zijn "producttypes" (bijv. "zelfverwarmende dierenmand"). Per type koppel ik concrete leverancierslistings met URL | Keuze | Eén listing-ID is te vluchtig (prijzen en varianten wisselen dagelijks). Het type plus de beste bewezen listing is reproduceerbaar |
| D6 | Concurrentieprijzen alleen uit Benelux-winkels (bol, ANWB, MediaMarkt NL/BE, Decathlon BE, Kruidvat, Action, BCC) of Amazon.de/.nl | Keuze | Doelmarkt is BE+NL |

## 2. Filterregels fase 2 (`scripts/filter_candidates.py`)

Codes: SAT (verzadigd), BIG (breekbaar, groot, zwaar of maatgevoelig), IP (merk of kopie), REG (gereguleerd: medisch, cosmetica, voeding, speelgoed, losse batterijen, hoog GPSR-risico), LOW (verkoopprijs < €20 zonder natuurlijke bundel), WOW (geen 3-seconden-demo), FIT (geen Benelux-fit, seizoen voorbij of te weinig info).

- **AFLEIDING:** "Verzadigd" heb ik in de praktijk vooral gemeten aan Benelux-retail. Als Action, Kruidvat, ALDI of Lidl het product al voor een fractie van de prijs verkoopt, geldt het als SAT. De Meta Ad Library kon ik niet bereiken (zie LIMITATIONS).
- Producten met integrated lithium (handwarmers, massagering, hogedrukreiniger) zijn niet automatisch gefilterd, want de brief noemt alleen *losse* lithiumbatterijen. Ze krijgen wel een lagere risicoscore.
- Bundelproducten (matcha-klopper, mok-warmer, leeslampje) mochten eerst door als "alleen als bundel". In de eindselectie (§5) valt alles af met een realistische verkoopprijs onder €20.

## 3. Unit economics (`scripts/margins.py`)

| Parameter | Waarde | Type | Bron of reden |
|---|---|---|---|
| Btw NL en BE | 21% | FEIT | [government.nl VAT rates](https://www.government.nl/topics/vat/vat-rates-and-exemptions), [accountable.eu BE](https://www.accountable.eu/nl-be/help-center/welke-btw-tarieven-gelden-er-in-belgie/) |
| Inkoopprijs | mediaan van `minPrice` over relevante AliExpress-listings met ≥ 100 verkocht. Spreiding p25 tot p75 staat in `data/unit_economics.csv` | FEIT (ruwe data) plus AFLEIDING (mediaan) | AliExpress geeft per listing alleen de goedkoopste variant. Dat kan een accessoire zijn, daarom de mediaan en niet het minimum |
| Prijzen inclusief 21% btw, verzending gratis | `taxRate: 0.21` in de AliExpress-data; meeste listings: "Free shipping", "No import charges" | FEIT | eigen fetch, `data/aliexpress_search*.json` |
| Btw op AliExpress-inkoop niet terugvorderbaar | kostprijs is inclusief btw | AANNAME (conservatief) | B2C/IOSS-factuur. Met een B2B-leverancier wordt de marge ~17% beter |
| Betaalkosten | 2% + €0,25 per order | AANNAME | NL-tarief Shopify Payments niet gevonden. Proxy: UK Basic-tarief volgens [Airwallex](https://www.airwallex.com/uk/blog/shopify-payments-fees-explained) |
| Retourreserve | 4–8% × kostprijs (per product in `margins.py`) | AANNAME | Retouren bij dropshipping worden zelden doorverkocht |
| Verkoopprijs per product | zie kolom `sell_price_basis` | AFLEIDING | Gebaseerd op Benelux-concurrentieprijzen. Waar geen prijs gevonden is, staat dat er expliciet bij (AANNAME) |
| CPA | scenario's €20 / €30 / €40 | AANNAME | De benchmarks die ik vond (Triple Whale $38,99; SuperAds NL €43,67) konden niet herbevestigd worden. Zie `data/verification.csv` |
| Conversieratio voor de stopregel | 2% | AANNAME | Alleen gebruikt om een max-CPC voor de test af te leiden: max-CPC = brutomarge × 2% |
| Break-even ROAS | verkoopprijs / brutomarge | Definitie uit de brief | Brutomarge = prijs excl. btw − inkoop − betaalkosten − retourreserve |

## 4. Scoringsmodel (`scripts/score.py`)

Per criterium een score van 0–10. Gewogen totaal:

| Criterium | Gewicht | Hoe gescoord |
|---|---|---|
| Trendmomentum | 0,15 | Oordeel (AFLEIDING), reden per product in `products_scored.csv` |
| Lage verzadiging | 0,15 | Oordeel: 10 = weinig aanbieders in de Benelux |
| **Marge** | **0,20** | **Mechanisch:** `10 × (4,0 − BE-ROAS) / 2,5`, begrensd op 0–10. Negatieve of onbekende marge = 0 |
| Wow-factor / viraal | 0,10 | Oordeel |
| Levertijd | 0,10 | **Mechanisch:** 4 voor alle producten. Bij geen enkel product is EU-voorraad bevestigd |
| Laag risico / compliance | 0,10 | Oordeel: 10 = geen elektronica, geen claims |
| Probleemoplossend | 0,10 | Oordeel |
| Seizoensfit (dec–mei) | 0,10 | Oordeel |

Waarom marge het zwaarst weegt: zonder positieve marge na advertentiekosten is het geen bedrijf. Een ander gewicht verandert de top-1 niet: de zelfverwarmende dierenmand is de enige met marge-score > 0 die ook door alle harde regels komt.

## 5. Regels voor de eindlijst

Een product komt alleen in de eindlijst als het aan alle vier deze regels voldoet:
1. ≥ 3 ondersteunende signalen van ≥ 3 verschillende brondomeinen (rijen met tegenbewijs tellen niet mee). Dit is de eis uit de brief.
2. Verkoopprijs ≥ €20.
3. Bekende kostprijs.
4. Positieve brutomarge.

Er voldoen **5 producten** aan. Ik heb de lijst niet aangevuld tot 10 met producten die een regel breken. Dat volgt de instructie "liever 5 goed onderbouwde producten dan 10 gokken".

## 6. Correcties na verificatie (fase 5)

- **Chewy Mora Pets:** 227 beoordelingen / $23,59 is gecorrigeerd naar **237 / $18,56** (Small).
- **SuperAds NL €43,67:** niet op de pagina gevonden en verwijderd als feit.
- **Triple Whale CPA, ROAS 1,88 en ROAS 2,25:** de pagina gaf 403. Deze cijfers zijn ONBEVESTIGD en staan alleen als context in het rapport.
- **MediaMarkt-prijzen (massagering, Lanaform), Fruugo, CPSC:** 403 en daarom ONBEVESTIGD.
- **Herbevestigd:** Kalodata ($1,78M fascia-ring; $1,97M hogedrukreiniger), ANWB Pleafs €87,96, Sell The Trend SnuggleHeat ($64.335/maand; inkoop $6,52, verkoop $39,95) en ASInsight (20.000/maand, 135 producten).
