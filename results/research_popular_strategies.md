# Onderzoek: de meest gebruikte en "meest winstgevende" swingstrategieën

Datum: 2026-10-30. Doel: zoveel mogelijk bekende, veelgebruikte strategieën met (beweerde) winst verzamelen, ze in
exacte regels omzetten en ze daarna allemaal op dezelfde manier testen (`popular_rules.md`, `popular.py`).

## Wat het internet zegt (samengevat, met bronnen)

**1. De meeste "hoge winrate"-claims zijn niet betrouwbaar.** Bij zoeken naar de meest winstgevende swingstrategieën
komen vooral marketingpagina's en e-books naar boven (bv. "97,71% winrate"). Een backtest-site merkt zelf op dat
resultaten slechter worden als gedelistte aandelen meetellen, en dat minder dan 30 signalen niets bewijst. Ervaren
swingtraders melden volgens VectorVest-cijfers 35-50% winrate. Bronnen:
[Everand](https://www.everand.com/book/522609751/The-97-Swing-Trade-Learn-a-Swing-Trading-Strategy-for-Beginners-With-a-97-71-Win-Rate-Swing-Trading-Books),
[easyswing methodology](https://easyswing.pages.dev/methodology),
[Hyrotrader](https://www.hyrotrader.com/de/blog/most-profitable-trading-strategy/),
[Quantified Strategies, 5 swing strategies](https://quantifiedstrategies.substack.com/p/5-swing-trading-strategies-2024-backtest-2df).

**2. Mean reversion (Connors RSI(2), IBS, Double 7s, lage closes) is de populairste "hoge winrate"-familie.**
Regels RSI(2): slot boven SMA200, RSI(2) < 10 (Connors gebruikte vaak < 5), uit boven de 5-daagse SMA. Een
onafhankelijke backtest op de Nasdaq 100 (2016-2026) gaf +26,9% totaal tegen +528% kopen-en-vasthouden. IBS-regel
(Quantified Strategies): IBS < 0,25 en RSI(21) < 45. Quantified Strategies verkoopt een Connors-bundel met "77% win,
0,6% per trade" op SPY (verkopercijfers). Recent artikel: kopen na vijf dalingen op rij. Bronnen:
[MQL5 RSI2](https://www.mql5.com/en/articles/17636), [LuxAlgo RSI 2](https://www.luxalgo.com/library/concept/rsi-2/),
[ProRealCode RSI-2](https://www.prorealcode.com/prorealtime-trading-strategies/rsi-2-strategy-larry-connors),
[Backtrex Nasdaq 100](https://backtrex.com/en/backtests/connors-rsi-2-nasdaq-100),
[Backtrex S&P 500](https://backtrex.com/en/backtests/connors-rsi-2-sp-500),
[Quantified Strategies R3](https://quantifiedstrategies.substack.com/p/larry-connors-r3-strategy-it-still-795),
[Quantified Strategies classical mean reversion](https://quantifiedstrategies.substack.com/p/the-classical-mean-reversion-strategy),
[Quantified Strategies mean reversion](https://www.quantifiedstrategies.com/product-category/mean-reversion-strategies/),
[5-day low](https://www.pulse.bot/stock-trading/news/buy-weakness-win-big-the-5-day-low-trading-strategy-89cc6501-8f84-4450-99be-3ca7240658ad/),
[TradingView IBS-script](https://www.tradingview.com/script/2KH3h0AC-S4-IBS-Mean-Rev-3candleExit).

**3. Trend en breakout (golden cross, MACD, Donchian/Turtle, 52-weeks-hoog).** Brock, Lakonishok & LeBaron (1992)
vonden dat 26 voortschrijdend-gemiddelde- en range-breakout-regels op de Dow (1897-1986) beter waren dan cash; Sullivan,
Timmermann & White (1999) toonden met een "Reality Check"-bootstrap dat data snooping groot is, en de beste regel
herhaalde zijn prestatie niet in 1987-1996. Een test van 856 indicatorregels met correctie voor meervoudig testen vond
voor de golden/death cross geen enkel significant resultaat. Het 52-weeks-hoog-effect (George & Hwang 2004) werkte in
18 van 20 landen. Bronnen:
[Sullivan, Timmermann & White](https://bashtage.github.io/kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf),
[FMG discussion paper](https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf),
[Data snooping](https://data-snooping.martinsewell.com/),
[856 tests](https://reigraph-blog.pages.dev/do-technical-indicators-actually-work),
[Golden cross backtest](https://investagrams.com/daily/2023/01/backtesting-the-golden-cross-signal),
[Bhootra 2018, Finance Research Letters](https://econpapers.repec.org/RePEc:eee:finlet:v:25:y:2018:i:c:p:259-265),
[52-week high Finland](https://aaltodoc.aalto.fi/items/b61712b8-9ed1-4788-9b26-7cfd405c8f82).

**4. "Pro"-methodes (Minervini, O'Neil/CAN SLIM, Qullamaggie, Raschke).** Minervini's trend template is een filter
(koers boven 50/150/200-daags gemiddelde, stijgende 200-daagse, dicht bij het 52-weeks-hoog), geen koopsignaal;
O'Neil: cup-with-handle, stop 7-8% onder het pivot. Qullamaggie: breakout na een sterke stijging en een strakke
consolidatie, en de "episodic pivot" (gap > 10% op grote volume na nieuws); zijn eigen winrate wordt op 25-30% geschat.
Raschke's "Holy Grail": ADX(14) > 30 en stijgend, terugval naar het 20-daags gemiddelde, kopen boven de high van die
bar. Bronnen:
[Minervini trend template](https://therighttrader.com/learn/trading-strategies/minervini-trend-template),
[vcpscanner playbooks](https://vcpscanner.com/playbooks),
[Cup and handle](https://curvedtrading.com/articles/en/bullish/cup-and-handle-trading-strategy/),
[Qullamaggie setups](https://tikamalma.substack.com/p/qullamaggie-swing-trading-setups),
[Complete Traders Edge](https://completetradersedge.com/kristjan-kullamagi-qullamaggie/),
[Episodic pivot](https://therighttrader.com/learn/trading-strategies/episodic-pivot),
[Chartmill Kullamägi screen](https://chartmill.com/documentation/stock-screener/technical-analysis-trading-strategies/467-Kristjan-Kullamagi-Continuation-Breakout-Screen),
[Holy Grail](https://therighttrader.com/learn/trading-strategies/holy-grail-setup),
[Holy Grail (Street Smarts)](https://tradingsetupsreview.com/the-holy-grail-trading-setup).

**5. Populairste indicatoren bij particulieren:** voortschrijdende gemiddelden, RSI, MACD, Bollinger Bands; in een
poll gebruikte 41% oscillatoren. Bronnen: [onedayadvisor](https://www.onedayadvisor.com/2025/02/most-popular-indicator-use-by-most.html),
[Traders Union](https://tradersunion.com/interesting-articles/best-forex-indicators-for-successful-trading/).

**6. Wetenschap over anomalieën:** Hou, Xue & Zhang (2020) testten 447 anomalieën; 64% is niet significant op 5%,
85% niet bij t > 3. Momentum en waarde houden stand, maar kleiner dan gerapporteerd. Bronnen:
[NBER w23394](https://www.nber.org/papers/w23394.pdf), [Alpha Architect](https://alphaarchitect.com/replicating-anomalies/).

## Wat dat betekent voor de test
- Elke strategie wordt met **dezelfde** uitstap getest (jouw regel: +10% en eruit), dezelfde kosten, hetzelfde
  universum, en vergeleken met willekeurige instappen op dezelfde dagen en met SPY.
- Omdat er ~30 strategieën getest worden, wordt gecorrigeerd voor meervoudig testen (Bonferroni) — precies het punt
  van Sullivan, Timmermann & White.
- Al eerder getest in deze repo (en daarom hier opnieuw meegenomen onder dezelfde regels): de 10 week-setups
  (`build.py`), de earnings-gap, jouw v4.1 en jouw support + EMA + RSI-strategie.
