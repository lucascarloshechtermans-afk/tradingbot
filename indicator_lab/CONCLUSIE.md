# Conclusie van het onderzoek (stand oktober 2026)

## Wat standhield op data die nooit gebruikt was
**De marktregime-regel: beleg in de index zolang die boven zijn 200-daagse gemiddelde sluit, anders cash.**

| test (nooit eerder gebruikt) | regel | kopen en vasthouden |
|---|---|---|
| SPY 1993-2011 | 7,0%/jaar, max -24% | 7,7%/jaar, max -55% |
| S&P 500 1960-1992 | 8,5%/jaar, max -18% | 6,2%/jaar, max -48% |
| Nasdaq-100 1987-2011 | 10,5%/jaar, max -41% | 11,7%/jaar, max -83% |
| 12 buitenlandse beurzen (tot 60 jaar) | betere rendement/daling-verhouding op 9 van 12; mediane max daling een derde kleiner | |

Het is een **risicoregel**: de grote crashes (2000-2002, 2008, 1929-1932) worden grotendeels ontweken, het rendement
is meestal 1-2% per jaar lager, en in rustige stijgende jaren (2024-2026) kost hij rendement.
Indicator: `pine/market_regime_sma200.pine` (+ strategy-versie en dashboard). Getest in `timing/` en
`tests/test_regime_pine.py`.

## Wat NIET standhield (allemaal getest op het hele NASDAQ-universum, met kosten en jouw regel 1 BUY per 2 weken)
| idee | uitslag | rapport |
|---|---|---|
| eigen breakout-indicator v1-v6 (ook met kwaliteitsmodel) | onder SPY op elke onafhankelijke test | `swing5/`, `swing6/`, `h4/reports/nasdaq_daily.md` |
| 4H in plaats van dag, winstdoelen 10-20% | hogere winrate, niet meer rendement | `h4/reports/test4h_nasdaq.md` |
| 10 bekende strategieën met hoge winrate (RSI2, Bollinger, MACD, Supertrend, ...) | verliezen op rekeningniveau | `h4/reports/classics_*.md` |
| "koop de paniek" | geen van 16 varianten beter dan SPY | `panic/reports/dev.md` |
| EMA-pullbacks, support/resistance, marktstructuur, gamma exposure (GEX) | alle vijf negatief | `h4/reports/ta_concepts_*.md` |
| 9 methodes van pro's (Minervini, Qullamaggie, Raschke, Weinstein, pocket pivot, AVWAP, NR7) | geen beter dan SPY; Minervini 4H zakte op de holdout (-0,4%/jaar) | `h4/reports/pro_concepts_*.md`, `h4/reports/holdout_minervini4h.md` |
| relatieve-sterkte-rotatie (top 10/20 sterkste aandelen) | -7% tot -22%/jaar | `rotation/reports/dev.md` |
| volatiliteitsdoel, hefboom 2x in uptrend | gezakt / te groot risico (-81%) | `timing/reports/holdout.md`, `leverage.md` |

## Wat dit betekent voor jou
1. Een mechanische koop/verkoop-indicator voor losse aandelen die de index verslaat, is in dit onderzoek niet gevonden.
   Hoge winrates bestaan wel, maar ze leveren niet meer geld op dan SPY vasthouden.
2. Wat wel aantoonbaar helpt, is **minder diep vallen**: de regime-regel op SPY/QQQ.
3. Wil je toch swingtraden met losse aandelen, doe het dan met een klein deel van je geld, en vergelijk je resultaat
   eerlijk met SPY. Nieuwe ideeën kunnen het best eerst op papier lopen (geen echte orders).
