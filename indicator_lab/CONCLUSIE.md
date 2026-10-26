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
| Connors-mean-reversion (RSI2, Double 7s, IBS) op 17 indexen, 1963-2026 | beter dan kopen-en-vasthouden in 1-2 van 17 perioden | `meanrev/reports/index_mr.md` |
| 10 klassiekers op de 300 grootste Amerikaanse aandelen | geen enkele beter dan SPY (beste 9,7%/jaar vs 13,2%) | `largecap/reports/dev.md` |
| Faber GTAA5 en Antonacci Dual Momentum, alleen jaren ná publicatie | beide onder SPY (4,5% en 8,0%/jaar vs 11,2% en 13,6%) | `timing/reports/allocation.md` |
| Faber-sectorrotatie (top 3 van 9 sector-ETF's), alleen ná publicatie 2010-2026 | 12,3%/jaar vs SPY 14,1% | `timing/reports/sectors.md` |
| post-earnings drift (winstverrassing / koersreactie, 60 dagen vasthouden) | op 131 bekende namen 24-28%/jaar, maar op 468 willekeurige nooit gebruikte aandelen 10-12% vs SPY 14,9%: het effect is echt (+0,4 tot +1,4% per trade) maar te klein | `earnings_drift/reports/` |

## Wat dit betekent voor jou
1. Een mechanische koop/verkoop-indicator voor losse aandelen die de index verslaat, is in dit onderzoek niet gevonden.
   Hoge winrates bestaan wel, maar ze leveren niet meer geld op dan SPY vasthouden.
2. Wat wel aantoonbaar helpt, is **minder diep vallen**: de regime-regel op SPY/QQQ.
3. Wil je toch swingtraden met losse aandelen, doe het dan met een klein deel van je geld, en vergelijk je resultaat
   eerlijk met SPY. Nieuwe ideeën kunnen het best eerst op papier lopen (geen echte orders).

## Een eerlijke waarschuwing over al dit testen
Er zijn inmiddels ruim 15 afzonderlijke hypotheses vooraf vastgelegd en getest. Bij zoveel pogingen kan er ook puur
door toeval eens één slagen. Daarom telt alleen wat op meerdere onafhankelijke datasets standhoudt; dat is tot nu toe
alleen de SMA200-regime-regel (VS 1960-2011 én 12 buitenlandse beurzen).

