# Donchian 20-daagse breakout op XOM

## Conclusie

1. **De strategie is op zich winstgevend, maar veel minder dan XOM gewoon vasthouden.** Over 1962-2026: 191 trades,
   winrate 41%, profit factor 1,62, gemiddeld +1,6% per trade (winnaars +10,1%, verliezers -4,3%). Maar 3,7% per jaar
   tegen 12,6% voor XOM kopen-en-vasthouden. In elke deelperiode bleef hij onder XOM kopen-en-vasthouden.
2. **De grootste daling is nauwelijks kleiner:** -52% tegen -62% voor XOM, en in 1993-2009 zelfs groter (-52% vs -34%).
3. **De breakout-timing voegt op XOM niets toe:** 1.000 willekeurige strategieën met precies dezelfde houdperiodes
   (dus dezelfde tijd in de markt) haalden over 1962-2026 een mediaan van 6,6% per jaar; de Donchian-strategie was
   slechter dan 99% daarvan. Een grote, rustige waarde-aandeel als XOM keert vaak terug na een uitbraak (geen sterke
   trendpersistentie).
4. **Langere kanalen (55 of 100 dagen) deden het beter** (6,0% en 8,6% per jaar), maar ook die blijven onder
   kopen-en-vasthouden, en ze zijn hier achteraf bekeken: dat is geen bewijs, alleen een aanwijzing.
5. **Eerlijk oordeel:** als trendvolger op dit ene aandeel niet aan te raden; XOM vasthouden (of SPY) leverde meer op
   bij een vergelijkbaar risico. Bij een breed mandje aandelen of grondstoffen werkt trendvolgen doorgaans beter dan
   op één aandeel.


Regels (vooraf vastgelegd in `indicator_lab/xom_donchian.py`): kopen op de open na een slot boven het hoogste hoog van de vorige 20 dagen, verkopen op de open na een slot onder het laagste laag van de vorige 20 dagen; alleen long; kosten 0,10% per kant; cash 0% rente. Data: Yahoo, gecorrigeerd voor splitsingen en dividend, 1962-01-02 .. 2026-10-30. Tijd in de markt: 60%. Strategie op dit moment LONG sinds 2026-07-20 (28.4%).

## Resultaat

| periode   |   trades | winrate   |   PF | gem./trade   | gem. winst / verlies   |   gem. dagen | CAGR strategie   | max daling   |   Sharpe | CAGR XOM kopen+houden   | max daling XOM   | CAGR SPY   | random timing: mediaan CAGR / % beter dan strategie   |
|:----------|---------:|:----------|-----:|:-------------|:-----------------------|-------------:|:-----------------|:-------------|---------:|:------------------------|:-----------------|:-----------|:------------------------------------------------------|
| 1962-2026 |      191 | 40.8%     | 1.62 | 1.6%         | 10.1% / -4.3%          |           51 | 3.7%             | -52.1%       |     0.31 | 12.6%                   | -62.4%           | -          | 6.6% / 99%                                            |
| 1962-1992 |       88 | 43.2%     | 1.81 | 1.9%         | 9.6% / -4.0%           |           54 | 4.4%             | -39.7%       |     0.37 | 14.1%                   | -42.4%           | -          | 7.5% / 98%                                            |
| 1993-2009 |       51 | 43.1%     | 1.21 | 0.6%         | 7.6% / -4.8%           |           54 | 0.6%             | -52.1%       |     0.12 | 12.2%                   | -33.7%           | 7.6%       | 7.6% / 100%                                           |
| 2010-2026 |       52 | 34.6%     | 1.72 | 2.0%         | 13.9% / -4.3%          |           44 | 5.6%             | -43.9%       |     0.4  | 10.1%                   | -62.4%           | 13.9%      | 4.8% / 41%                                            |
| 2021-2026 |       17 | 35.3%     | 1.47 | 1.7%         | 15.2% / -5.6%          |           42 | 14.7%            | -43.9%       |     0.73 | 34.6%                   | -20.5%           | 14.6%      | 10.7% / 25%                                           |

Random timing = 1.000 strategieën met precies dezelfde houdperiodes op willekeurige startdagen (zelfde tijd in de markt): als de breakout-timing iets toevoegt, moet de strategie beter zijn dan de meeste.

## Gevoeligheid voor de kanaallengte (alleen ter controle, niets gekozen)

| kanaal    | periode   |   trades | winrate   |   PF | CAGR   | max daling   |
|:----------|:----------|---------:|:----------|-----:|:-------|:-------------|
| 10 dagen  | 1962-2026 |      354 | 43.8%     | 1.24 | 1.8%   | -60.1%       |
| 10 dagen  | 2010-2026 |       83 | 41.0%     | 1.72 | 6.4%   | -34.4%       |
| 20 dagen  | 1962-2026 |      191 | 40.8%     | 1.62 | 3.7%   | -52.1%       |
| 20 dagen  | 2010-2026 |       52 | 34.6%     | 1.72 | 5.6%   | -43.9%       |
| 55 dagen  | 1962-2026 |       73 | 46.6%     | 2.97 | 6.0%   | -49.8%       |
| 55 dagen  | 2010-2026 |       21 | 38.1%     | 2.34 | 4.8%   | -44.5%       |
| 100 dagen | 1962-2026 |       38 | 55.3%     | 6.6  | 8.6%   | -41.2%       |
| 100 dagen | 2010-2026 |       10 | 50.0%     | 4.71 | 7.3%   | -38.9%       |
