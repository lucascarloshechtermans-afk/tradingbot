# LIMITATIONS — wat ik niet kon bereiken en wat dat betekent

## Bronnen die niet bereikbaar waren (2026-11-20)

| Bron uit de brief | Resultaat | Gevolg voor de betrouwbaarheid |
|---|---|---|
| **TikTok Creative Center** (Top Products, hashtags, Top Ads) | Redirect (301) naar een JS- en login-omgeving. Niet uitgelezen | Geen officiële TikTok-data voor BE/NL. TikTok-signalen komen van derde partijen (FastMoss, Kalodata via Lengow/Quicksync, EchoTik, Sell The Trend). Dat zijn **schattingen van tools** en vooral **US/UK/DE/FR**, geen Benelux |
| **Meta Ad Library** | 403 | **Ik weet niet** hoeveel adverteerders een product nu pushen of hoe lang hun ads lopen. Het verzadigingscriterium is daardoor gebaseerd op het retailaanbod in de Benelux, niet op advertentiedata. Dit is de grootste blinde vlek |
| **Google Trends** | 429 (rate limit), ook bij een gewone browserlaadbeurt | **Geen 90-dagen- of 12-maandencurves.** De trendfase is afgeleid uit indirecte signalen: plaatsingsdatums op AliExpress, seizoenspieken uit SaleHoo en Accio, en Exploding Topics (US-gericht). Iedere uitspraak over de trendfase is daarom een AFLEIDING |
| **Amazon Movers & Shakers** (.com/.de/.fr/.nl) | Allemaal BLOCKED of EMPTY (Amazon.com toonde "no movers available") | De "stijgers van de afgelopen 24 uur" ontbreken. Wel gebruikt: 17 Best Sellers-lijsten (DE, FR, NL) |
| **bol.com** | 403 | De grootste NL-marktplaats is niet direct uitgelezen. Bol-prijzen komen alleen uit zoekresultaten en vergelijkingssites |
| **Reddit** (r/BuyItForLife, r/shutupandtakemymoney) | 403, pullpush-API 429 | Geen Reddit-signalen |
| **Kickstarter** | 403 | Alleen via Gadget Flow en TCF (secundair) |
| **Etsy** | 403 | Geen Etsy-data |
| **AliExpress-productpagina's** | Bot-check ("punish"). Bewust niet omzeild | Geen prijs per variant, geen exacte levertijd naar NL, geen reviews per product. Kosten zijn een **mediaan van de goedkoopste varianten** uit de zoekresultaten. De werkelijke prijs van de gewenste variant kan hoger liggen, dus de marges zijn eerder te optimistisch dan te somber |
| **AliExpress-zoekpagina's** | Na ~15 snelle zoekopdrachten lege resultaten (rate limit). Daarna trager opnieuw geprobeerd | 41 van de 71 geplande zoektermen in `data/candidates.txt` zijn nooit opgehaald (pressure washer wel, via een andere zoekterm). Voorbeelden: slaaphoofdband, interactief kattenspeeltje, pootreiniger, kattenhangmat, ruitenafdekhoes, monitorlamp. Ze hadden geen ander signaal en staan daarom **niet** in de 88 kandidaten. Ze zijn niet onderzocht, niet afgekeurd. De shortlist is wel volledig opgehaald |
| **CJ Dropshipping / Spocket / BigBuy** (EU-voorraad) | Login of redirect | **Bij geen enkel product is EU-voorraad bevestigd.** Levertijd = 4/10 voor alle producten. Vóór een test moet je dit zelf in de CJ- of Spocket-app controleren en een testbestelling naar NL/BE doen |
| **Bronnen bij herverificatie** | Triple Whale, MediaMarkt NL/BE, Fruugo en CPSC gaven 403 | Die cijfers zijn als ONBEVESTIGD gemarkeerd (`data/verification.csv`) |

## Inhoudelijke beperkingen

1. **Geen Benelux-specifieke vraagdata.** Bijna alle vraag- en groeicijfers gaan over de US. Alleen Amazon.nl/.de/.fr (eigen fetch) en Lengow/FastMoss (DE/FR/ES/IT) gaan over Europa.
2. **"Aantal verkocht" op AliExpress is cumulatief** sinds de plaatsing en wereldwijd. Een hoog getal bij een oude listing zegt weinig over de huidige groei. Daarom heb ik ook de plaatsingsdatum vastgelegd.
3. **Schattingen van tools** (Kalodata, FastMoss, ASInsight, Accio, Sell The Trend, Exploding Topics) zijn geen geauditeerde verkoopcijfers. Accio-pagina's zijn deels AI-gegenereerd.
4. **CPA en ROAS zijn onbekend voor jouw account.** Het margemodel rekent daarom met scenario's (€20, €30, €40) en geeft per product de *maximale* CPA en CPC. Je eigen testdata vervangt deze aannames.
5. **Compliance is niet juridisch getoetst.** CE, GPSR, WEEE (NL: registratie bij Stichting OPEN) en batterijregels moet je per leverancier controleren aan de hand van conformiteitsverklaringen.
6. **Momentopname.** Amazon-rangen veranderen elk uur en AliExpress-prijzen elke dag. Draai de scripts opnieuw vóór een beslissing:

```bash
cd research/scripts
python3 build_signals.py
python3 filter_candidates.py
python3 margins.py
python3 score.py
```
