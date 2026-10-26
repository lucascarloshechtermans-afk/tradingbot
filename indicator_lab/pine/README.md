# Pine-scripts (TradingView) — handleiding

| Bestand | Wat | Gebruik |
|---|---|---|
| `swing_v3_quality_model.pine` | **Hoofdindicator (beste versie)**: BUY/SELL-labels, trailing stop, infotabel, earnings-waarschuwing, alerts | dagelijks op de grafiek |
| `swing_v3_strategy.pine` | Zelfde regels als **strategy**, voor de Strategy Tester van TradingView (trades, equity, statistieken) | per aandeel nakijken hoe het historisch deed |
| `swing_v3_watchlist_dashboard.pine` | **Dashboard**: dezelfde v3-regels voor 12 tickers naar keuze in één tabel (BUY vandaag / SELL vandaag / LONG + stop / -) | elke avond je watchlist checken zonder Pine Screener |
| `swing_v2_strong_close.pine` | v2 zonder kwaliteitsmodel (ook als schakelaar in v3) | ter vergelijking |
| `swing_v1_donchian.pine` | eerste versie | ter vergelijking |
| `v3_model.json` | coëfficiënten van het kwaliteitsmodel (al ingebakken in de scripts) | naslag |

## Installeren
1. TradingView → onderaan **Pine Editor** → alles weg → de inhoud van het `.pine`-bestand plakken.
2. **Save** → **Add to chart**. Gebruik een **daggrafiek** (1D); de scripts zijn op dagbars getest.
3. Voor de strategy: open daarna het tabblad **Strategy Tester**. Kosten (0,10% per kant) staan al ingesteld.

## Wat je ziet
- **BUY** (groen): signaal op de slotkoers → koop bij de opening van de volgende dag. Zet **meteen na de aankoop een
  stop op aankoopprijs − 4×ATR** (staat in de alert); daarna volgt de rode trailing-stoplijn.
- **BUY? / SELL?** (vaag): voorlopig signaal terwijl de dagkaars nog loopt — kan nog verdwijnen. Pas na de slotkoers telt het.
- **SELL** (rood): de trailing stop (rode lijn) is geraakt, of de koers sloot onder het 20-daagse dieptepunt → verkoop
  (bij een stop: op de stop; anders bij de opening van de volgende dag).
- **Oranje ✕**: breakout die het kwaliteitsmodel afkeurt (bewust geen BUY).
- **Gele bol** onder een BUY: er komen binnen 7 dagen kwartaalcijfers → volgens het onderzoek beter overslaan.
- **Tabel** rechtsboven: status, breakout-kwaliteit, stop, risico tot de stop, dagen in de trade, volgende cijfers,
  **positiegrootte** als je nu koopt (instellingen *Account size*, *Risk per trade %*, *Max position %*: standaard
  1% risico tot de initiële stop, max 10% van de rekening per positie ≈ 10 posities), een check op daggrafiek, en
  **statistiek van dit aandeel**: aantal trades, winrate, profit factor en gemiddelde trade sinds 2015 (instelbaar),
  met kosten en exact dezelfde vulregels als de backtest (getest in `tests/test_pine_emulator.py`).

## Alerts
Rechtsklik op de indicator → **Add alert** → kies *"Any alert() function call"* voor een bericht mét geschatte stop en
kwaliteitsscore, of een van de vaste meldingen (BUY / SELL / HALF PROFIT).

## Hele watchlist scannen
TradingView **Pine Screener** → kies deze indicator → filter op **Status = 1** (nieuwe BUY vandaag) of **-1** (SELL).
Gebruik een watchlist van beweeglijke groei-/momentumaandelen en houd ~10 posities aan (zie PROGRESS.md, E35).

## Watchlist-dashboard (zonder Pine Screener)
Zet `swing_v3_watchlist_dashboard.pine` op een willekeurige **daggrafiek** en vul in de instellingen bij *Watchlist* je 12
tickers in (standaard: NVDA, AMD, META, TSLA, AVGO, PLTR, CRWD, ANET, MU, GE, CAT, COIN — beweeglijke namen, zie E35).
Per ticker draait de volledige v3-logica op zijn eigen historie. Pine v6 (gebruikt geneste `request.security`).

## Hoe zeker is het dat dit hetzelfde doet als de backtest?
- Alle scripts zijn **gecompileerd en gelint** met een externe Pine-compiler (geen fouten).
- `indicator_lab/pine_emulator.py` voert de Pine-logica bar voor bar na in Python. Op 102 tickers gaven de BUY/SELL-signalen
  **exact** dezelfde trades als de backtest-engine (0 onverklaarde verschillen; 32 verschillen waren posities die op de
  laatste datadag nog open stonden). Enkel `ta.percentrank` (rekent zonder de huidige bar) verandert 4 van de 3246
  signalen (0,1%). Een automatische test (`tests/test_pine_emulator.py`) bewaakt dit.
- Kleine verschillen blijven mogelijk: TradingView's SPY is niet dividend-gecorrigeerd (tenzij die instelling aan staat)
  en dataleveranciers verschillen soms een cent in hoog/laag.

## Pine-versie
De scripts zijn `//@version=5` en compileren ook als `//@version=6` (getest). TradingView ondersteunt beide.

## Niet-Amerikaanse aandelen
Het kwaliteitsmodel gebruikt SPY als marktreferentie (getraind op Amerikaanse aandelen). Op beurzen die vóór New York
sluiten (bv. Euronext) gebruikt het script automatisch de SPY-slotkoers van de **vorige** dag, anders zou het een koers
gebruiken die er op het signaalmoment nog niet is. Het model is niet getest op Europese aandelen: gebruik daar eventueel
*Use quality model = uit* (v2-regels, die marktneutraal zijn).

## Model bijwerken (1× per jaar)
`python -m indicator_lab.export_pine` hertraint het kwaliteitsmodel op alle afgesloten breakouts en schrijft de nieuwe
coëfficiënten in alle drie de v3-bestanden (`--check` controleert of ze in sync zijn). Daarna opnieuw in TradingView plakken.

## Instellingen
- **Use quality model** uit = v2. **Min breakout quality %**: standaard de modeldrempel (~39%); hoger = strenger
  (minder maar betere signalen). De tabel toont de kwaliteit alleen op dagen met een breakout.
- **Take half profit at +x ATR**: 0 = uit; 4 = de "½"-variant uit onderzoek E22 (rustiger, iets minder rendement).
- **Earnings warning window / Block BUY**: waarschuwing of blokkade vóór cijfers (werkt alleen op recente bars,
  want TradingView kent enkel de eerstvolgende cijferdatum).

Geen financieel advies. De scripts plaatsen geen orders.

## Swing v4.1 (aanbevolen versie van v4)

`swing_v4_1.pine` geeft dezelfde BUY/SELL als v4 op Amerikaanse aandelen. Verschillen:
- de statistieken heten "Backtest", niet "OOS": de regels zijn op dezelfde historie gekozen;
- nieuwe regels in de tabel: **vs B&H (prijs)** = systeem met 100% per trade · kopen en vasthouden van dit aandeel ·
  SPY, over hetzelfde venster; **In trade** = % van de dagen dat je een positie hebt. Prijsrendement, zonder dividend;
- SELL-label en alert zeggen hetzelfde: "SELL stop + prijs" (stop geraakt, al verkocht) of "SELL next open"
  (slot onder de 20-daagse low: verkoop bij de volgende opening);
- het earnings-blok werkt alleen live en zit niet in de historische statistieken;
- Europese aandelen: op een Amerikaanse feestdag wordt de juiste SPY-dag gebruikt.

`swing_v4_1_strategy.pine` is dezelfde logica als strategy (Strategy Tester, trade-export). Zet "Order size" in
Properties op ~10% als je het met de portefeuille-opzet uit het onderzoek wilt vergelijken.

## Marktregime-indicator (`market_regime_sma200.pine`) — de regel die de onafhankelijke tests doorstond
Op een **daggrafiek van een index of index-ETF** (SPY, QQQ, VT, ...): groen = boven de 200-daagse lijn (belegd),
rood = eronder (cash). **IN** / **UIT** verschijnt op de slotkoers; de ingebouwde backtest-tabel rekent met handelen op
de slot van de volgende dag en 0,1% kosten per wissel. Instelling *Band %*: 0 = regel T1, 2 = variant T2 (minder wissels).

Waarom deze: van alles wat in `indicator_lab/` is getest (v1-v6, klassiekers, TA-concepten, pro-methodes, rotatie) is dit
het enige dat op nooit gebruikte data standhield: S&P 500 1960-1992, SPY 1993-2011, Nasdaq-100 1987-2011 en 12
buitenlandse indexen (`indicator_lab/timing/reports/confirm.md`: betere MAR op 9 van 12, mediane max daling een derde
kleiner). Het is een **risicoregel**, geen rendementsmachine: het rendement is meestal 1-2% per jaar lager.
Verwachte tabel (Yahoo-data mét dividend, kas 0%): SPY sinds 1993 regel 8,2%/jaar, max -25%, tegen kopen en vasthouden
10,8%, max -55%; QQQ sinds 1999 8,5% / -47% tegen 8,8% / -83%. TradingView rekent standaard zonder dividend, dus de
getallen daar wijken iets af. Met band 0% wissel je ~6-7 keer per jaar (veel kleine schijnsignalen rond de lijn).

**Erbij:**
- `market_regime_sma200_strategy.pine`: dezelfde regel als *strategy* voor de Strategy Tester (tradelijst, equitycurve).
  Vult op de open van de volgende dag (TradingView-standaard), 0,1% commissie per kant.
- `market_regime_dashboard.pine`: het regime van 12 markten tegelijk (standaard SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV,
  SMH, EFA, EEM, GLD; zelf aan te passen) met afstand tot de SMA200 en het aantal dagen sinds de laatste wissel. Tijdens
  de handelsdag is de rij van vandaag voorlopig; alleen de slotkoers telt.

