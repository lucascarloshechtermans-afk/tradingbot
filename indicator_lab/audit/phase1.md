# Swing v4 audit — fase 1: tests en bugfixes

Datum: 2026-10-23. Geen strategieregel en geen modelfit is veranderd; v4.1 geeft op Amerikaanse charts exact dezelfde
signalen als v4. Origineel `swing_v4.pine` en `swing_v4_strategy.pine` zijn onaangeroerd; de fixes staan in
`swing_v4_1.pine` en `swing_v4_1_strategy.pine` (GEN-regions via `export_pine`, nooit met de hand).

Zekerheid: **bewezen** = door een test of meting in deze repo aangetoond; **sterk vermoeden** = consistent met alle
metingen maar niet direct te testen; **hypothese** = niet getest.

## Wat er gedraaid is

| test / meting | resultaat |
|---|---|
| volledige testsuite (`pytest`) | **441 geslaagd, 0 gefaald** (was 422; +19 nieuw in `tests/test_v41_scenarios.py`) |
| 17 synthetische OHLC-scenario's door 5 implementaties (research-engine, swing4 core, swing4 sim2, Pine-indicator-emulatie, Pine-strategy-emulatie) | alle 17 geslaagd: zelfde in- en uitstapdag, zelfde fill-prijs (≤1e-9), zelfde rendement (≤1e-12; strategy ≤1e-4 door TradingView's commissieformule) |
| SPY-feestdag op niet-US-chart (ASML.AS, echte data) | geslaagd: v4.1 gebruikt SPY's laatste slot vóór de datum, v4 de dag daarvoor |
| TradingView-export round-trip (`pine_parity.compare_tv`) | geslaagd: lezer en vergelijking geven 0 verschil op een export die uit de emulatie zelf is gemaakt |
| compile-check (TextToQuant `validate_indicator`) | `swing_v4_1.pine`: ok, 35 plots, 0 meldingen · `swing_v4_1_strategy.pine`: ok, 0 meldingen (gecontroleerd met één modeljaar; de overige jaren zijn identiek gegenereerde regels) |
| `export_pine --check` | in sync (8 Pine-bestanden) |
| indicator vs strategy vs Python-engine op 20 echte tickers, 2015 → 2026-10 | 19/20 identieke trades; 1 afwijking verklaard (zie B8) |

De scenario's: normale BUY/SELL via de 20-daagse low (vult volgende open) · gap bij entry · stop op de instapdag ·
geen look-ahead (high van de fill-bar verhoogt de stop pas vanaf de volgende bar) · trailing stop na meerdere bars ·
gap door de stop (vult op de open) · geen herinstap op de exit-bar · open positie aan het einde telt niet mee ·
kosten (engine-formule en TradingView-commissie) · stop en half-profit-target op dezelfde bar (stop wint, geen halve
winst) · halve winst + exit (50/50 geboekt) · ontbrekende ATR (geen entry) · ontbrekende feature (volume/SPY: quality na,
geen BUY) · jaarwissel (andere walk-forward-fit en drempel) · te weinig historie (geen signaal) · twee machine-runs delen
geen toestand · benchmark-rijen tegen een handberekening.

**Wat niet kon:** de Pine-runtime zelf draait hier niet. "Pine" in de tests is `pine_sim`, een regel-voor-regel
Python-emulatie van het Pine-script. Synthetische koersen kun je niet in TradingView laden. Echte pariteit met
TradingView gaat via een export (instructie onderaan); die stap moet jij doen en is dus **nog niet gevalideerd**.

## Bevindingen

| # | probleem | bewijs | impact | aanpassing | validatie | prio | zekerheid |
|---|---|---|---|---|---|---|---|
| B1 | De tabel noemde de chart-statistieken "OOS", terwijl alleen de modelcoëfficiënten walk-forward zijn; regels, drempel en regime zijn gekozen op 2015–2024 | E-log + swing4-log: ~500 varianten op deze historie (stap 1 overfit-meting) | gebruiker overschat de betrouwbaarheid | label "Backtest 2015+"; volle tabel: regel "model walk-forward; rules + regime chosen on 2015-24 = in-sample; price returns, no dividends" | compileert; tekstwijziging | P1 | bewezen |
| B2 | Geen benchmark in de tabel | — | een mooie trade-statistiek kan nog steeds achterblijven bij kopen en vasthouden | nieuwe rijen: systeem gecompoundeerd (100% per trade, gesloten trades), buy & hold aandeel, SPY over exact hetzelfde venster, % bars in een trade; label "prijs" | `pine_sim.bench` = Pine-logica; test tegen handberekening | P1 | bewezen |
| B3 | Model: coëfficiënten wisselen van teken; spy_roc63 telt dubbel (model + regime); drempel = 25e percentiel van eigen trainingsvoorspellingen | swing4 fase 1, swing5 fase 0 | onbekend; mogelijk overfit | geen (meten in fase 2) | — | P1 | — |
| B4 | SELL-label toonde de stopprijs, de alert de slotkoers; bij een exit via de 20-daagse low stond nergens dat die op de volgende open vult | code | verkeerde verwachting van de verkoopprijs | label "SELL stop + fill-prijs" of "SELL next open"; alert met dezelfde tekst; twee aparte alertconditions (stop geraakt / exit volgende open) | scenario's gap-door-stop (label = open) en low-exit (geen prijs) | P2 | bewezen |
| B5 | Het earnings-filter (`earnings.future_time`) bestaat alleen live, dus niet in historie en statistieken | TradingView-documentatie; E38/E40 testten het in Python met echte rapportdata (131 aandelen): duidelijk per-trade-effect, geen portefeuillewinst | het filter lijkt getest maar is dat in Pine niet | input-label "LIVE ONLY: not in the history/statistics, untested as a rule" | — | P2 | bewezen (niet te backtesten in TV); een point-in-time aankondigingskalender is met onze databronnen niet te bouwen: **niet opnieuw getest** |
| B6 | "Geen strategy()-versie" | `swing_v4_strategy.pine` bestaat al sinds de v4-ronde (R6-methodiek) | — | `swing_v4_1_strategy.pine` toegevoegd (met de feestdag-fix) | tabel hieronder: aantal trades en gemiddeld rendement gelijk aan indicator en engine | P2 | bewezen |
| B7 | Niet-US-chart op een Amerikaanse feestdag: SPY-waarde twee dagen oud | ASML.AS: 102 van 3.788 handelsdagen zonder SPY-bar; op 99 daarvan verandert spy_roc63 (max 3,5 %-pt) | features iets fout op ~2,6% van de dagen; op ASML 0 signalen veranderd | generator: `FEATURES_V41` vergelijkt de datum van de SPY-bar met de chartdatum en gebruikt [0] als SPY die dag geen bar had | test op echte data; US-charts per constructie onveranderd | P3 | bewezen in Python; dat TradingView op zo'n dag de vorige SPY-bar teruggeeft is een **sterk vermoeden** (de datumvergelijking is in beide gevallen correct) |
| B8 | NIEUW: Pine en Python gebruiken een andere modelversie | NFLX 2015-07-16: features identiek, kans 0,354 (Pine, bevroren JSON-fit) vs 0,347 (Python, refit op de herziene koersen van 23-10) | 1 van 309 trades verschilt (20 tickers) | geen (een refit is een modelwijziging; beslissen in fase 2) | — | P3 | bewezen |

Indicator vs strategy vs Python-engine (v4.1, 2015-01 → 2026-10, 0,1% kosten per kant). "sys" = alle trades
achter elkaar met 100% van het kapitaal. B&H en SPY hier op dividend-gecorrigeerde Yahoo-koersen (in TradingView zijn
het prijsrendementen, dus lager):

| ticker   |   n ind |   n strat |   n engine | zelfde trades   |   avg ind % |   avg strat % |   avg engine % | sys 100%/trade   | B&H    | SPY   | in trade   |
|:---------|--------:|----------:|-----------:|:----------------|------------:|--------------:|---------------:|:-----------------|:-------|:------|:-----------|
| SPY      |      17 |        17 |         17 | True            |       2.929 |         2.932 |          2.929 | 59%              | 349%   | 349%  | 25%        |
| QQQ      |      19 |        19 |         19 | True            |       3.265 |         3.268 |          3.265 | 70%              | 646%   | 349%  | 21%        |
| AAPL     |      13 |        13 |         13 | True            |       5.091 |         5.096 |          5.091 | 75%              | 1333%  | 349%  | 16%        |
| MSFT     |      14 |        14 |         14 | True            |       8.172 |         8.18  |          8.172 | 179%             | 1222%  | 349%  | 27%        |
| NVDA     |      17 |        17 |         17 | True            |      14.859 |        14.874 |         14.859 | 559%             | 43809% | 349%  | 23%        |
| IWM      |       9 |         9 |          9 | True            |       2.001 |         2.003 |          2.001 | 19%              | 169%   | 349%  | 12%        |
| DIA      |      17 |        17 |         17 | True            |       2.617 |         2.619 |          2.617 | 50%              | 271%   | 349%  | 25%        |
| AMZN     |      14 |        14 |         14 | True            |       8.465 |         8.473 |          8.465 | 178%             | 1509%  | 349%  | 18%        |
| GOOGL    |      17 |        17 |         17 | True            |       0.379 |         0.379 |          0.379 | 2%               | 1126%  | 349%  | 16%        |
| META     |      17 |        17 |         17 | True            |       3.877 |         3.881 |          3.877 | 55%              | 729%   | 349%  | 19%        |
| JPM      |      14 |        14 |         14 | True            |       4.735 |         4.74  |          4.735 | 82%              | 624%   | 349%  | 20%        |
| XOM      |      14 |        14 |         14 | True            |       2.269 |         2.271 |          2.269 | 31%              | 221%   | 349%  | 18%        |
| JNJ      |      14 |        14 |         14 | True            |       1.613 |         1.615 |          1.613 | 22%              | 248%   | 349%  | 19%        |
| HD       |      18 |        18 |         18 | True            |       3.18  |         3.183 |          3.18  | 71%              | 308%   | 349%  | 25%        |
| KO       |      16 |        16 |         16 | True            |       0.121 |         0.122 |          0.121 | 1%               | 218%   | 349%  | 16%        |
| CAT      |      15 |        15 |         15 | True            |       3.458 |         3.462 |          3.458 | 45%              | 897%   | 349%  | 17%        |
| UNH      |      17 |        17 |         17 | True            |       2.905 |         2.908 |          2.905 | 48%              | 404%   | 349%  | 28%        |
| AMD      |      15 |        15 |         15 | True            |      25.235 |        25.26  |         25.235 | 955%             | 19278% | 349%  | 18%        |
| COST     |      18 |        18 |         18 | True            |       1.985 |         1.987 |          1.985 | 32%              | 784%   | 349%  | 24%        |
| NFLX     |      15 |        15 |         14 | False           |       3.431 |         3.434 |          3.982 | 54%              | 1222%  | 349%  | 18%        |

Wat deze tabel ook laat zien (**bewezen voor deze 20 tickers en dit venster**): met 100% per trade op één aandeel blijft
het systeem op **alle 20** achter bij buy & hold van datzelfde aandeel. Het zit maar 12–28% van de tijd in een trade.
Dat past bij de holdout-uitkomst (v4 versloeg SPY niet) en is precies waarom de benchmark-rijen nodig waren.

## Gewijzigde bestanden

- `indicator_lab/pine/swing_v4_1.pine` (nieuw): B1, B2, B4, B5, B7
- `indicator_lab/pine/swing_v4_1_strategy.pine` (nieuw): B7 (fills identiek aan v4-strategy)
- `indicator_lab/export_pine.py`: `FEATURES_V41` voor de v4.1-bestanden; v3/v4-bestanden byte-voor-byte ongewijzigd
- `indicator_lab/pine_sim.py`: state machine (`machine`) en orderboek (`book`) los van de data, zodat scenario's erdoorheen kunnen; `bench`; config `V41`
- `indicator_lab/pine_parity.py`: feestdag-fix (`version="v41"`), `read_tv_export` + `compare_tv` (`--tv`)
- `tests/test_v41_scenarios.py` (nieuw, 19 tests)
- `PROGRESS.md`: dubbele "Session 9"-sectie verwijderd

## Pariteit met echte TradingView-output (jouw stap)

1. Zet `swing_v4_1.pine` op een **daggrafiek** van een aandeel, Inputs → Debug: "show the raw model features" aan.
2. Grafiekmenu (pijltje naast de naam) → **Export chart data…** → CSV.
3. `python -m indicator_lab.pine_parity --tv export.csv` (voeg `--non-us` toe voor een Europees aandeel).

Je krijgt per feature het grootste verschil (in standaarddeviaties), het grootste verschil in quality, en de dagen waarop
BUY/SELL verschilt als de Python-state-machine op TradingView's eigen quality draait. Verwacht: kleine verschillen in
de SPY-features (TradingView's SPY is niet dividend-gecorrigeerd), verder ~0.

## Klaar voor fase 2?

Fase 2 meet (nog niets verbeteren): stabiliteit van de coëfficiënten, het model zonder SPY-features met het regime als
harde regel, de baselines (v2, alleen regime, 3 stabiele features), de 25%-drempel, regimevarianten per marktfase, en de
Deflated Sharpe Ratio en PBO met het werkelijke aantal trials (499, N_eff 56–93 uit stap 1 van de overfit-meting).
