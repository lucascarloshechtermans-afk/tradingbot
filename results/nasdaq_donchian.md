# Donchian 20-breakout op alle liquide NASDAQ-aandelen

## Conclusie

1. **Per trade winstgevend, maar niet beter dan willekeurig.** Originele uitstap: 14.721 trades, winrate 37%, PF 1,09,
   +0,67% per trade; willekeurige NASDAQ-aandelen met dezelfde uitstapregel deden +1,28% per trade. Het verschil
   (-0,62%) is negatief: de breakout-instap voegt niets toe.
2. **+10% en eruit verhoogt de winrate fors** (58-60%; +10% gehaald in 56-59% van de trades), maar de winst per trade
   daalt naar +0,22-0,34% en is ook niet beter dan willekeurig.
3. **Als rekening verliest elke variant van SPY en QQQ.** 2015-2026: -0,1% tot 2,5% per jaar met dalingen van -53% tot
   -75%; SPY 13,5% en QQQ 18,5% per jaar. In 2023-2026 ging het beter (tot 11% per jaar), maar nog steeds onder SPY (21%)
   en QQQ (30%).
4. **Zelfde beeld als bij XOM:** de Donchian 20-breakout geeft veel kleine verliezen en af en toe een grote winnaar, maar
   niet genoeg om de index te verslaan.
5. **Eerlijk advies:** QQQ (of SPY) vasthouden; deze breakout-strategie op losse NASDAQ-aandelen niet traden.


Regels: `indicator_lab/week/nasdaq_donchian_rules.md` (vooraf gecommit). 1496 NASDAQ-aandelen (> $5, > $20M/dag), 81799 breakout-signalen 2015-2026; alleen aandelen die op 2026-10-23 genoteerd waren. Kosten 0,05% + $0,02 per kant.

## Per trade

| uitstap                                    | periode   |   trades | +10% geraakt   | winrate   | gem./trade   |   PF |   gem. dagen | random: winrate / gem.   | verschil vs random [95%]   |     t |
|:-------------------------------------------|:----------|---------:|:---------------|:----------|:-------------|-----:|-------------:|:-------------------------|:---------------------------|------:|
| verkopen na slot onder 20-daagse laag      | 2015-2026 |    14721 | 21%            | 37%       | 0.67%        | 1.09 |         45.1 | 33% / 1.28%              | -0.62% [-1.21, +0.01]      | -1.99 |
| verkopen na slot onder 20-daagse laag      | 2023-2026 |     6716 | 22%            | 37%       | 0.81%        | 1.09 |         44.2 | 33% / 2.00%              | -1.19% [-2.40, +0.02]      | -1.94 |
| +10% en eruit, anders 20-daagse-laag-regel | 2015-2026 |    29844 | 56%            | 58%       | 0.22%        | 1.04 |         20.2 | 49% / 0.29%              | -0.07% [-0.30, +0.15]      | -0.65 |
| +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 |    14251 | 59%            | 60%       | 0.34%        | 1.06 |         18.8 | 48% / 0.20%              | +0.14% [-0.22, +0.47]      |  0.77 |

## Als rekening

|   posities | uitstap                                    | periode   | CAGR   | max daling   | verschil vs RND [95%]   | verschil vs SPY [95%]   | verschil vs QQQ [95%]   |
|-----------:|:-------------------------------------------|:----------|:-------|:-------------|:------------------------|:------------------------|:------------------------|
|         10 | verkopen na slot onder 20-daagse laag      | 2015-2026 | -0.1%  | -68.0%       | -0.10% [-0.23, +0.03]   | -0.23% [-0.39, -0.06]   | -0.32% [-0.50, -0.15]   |
|         10 | verkopen na slot onder 20-daagse laag      | 2023-2026 | 11.1%  | -35.3%       | +0.01% [-0.17, +0.22]   | -0.15% [-0.41, +0.13]   | -0.30% [-0.60, +0.03]   |
|         10 | +10% en eruit, anders 20-daagse-laag-regel | 2015-2026 | 1.2%   | -52.7%       | -0.07% [-0.16, +0.01]   | -0.22% [-0.33, -0.12]   | -0.31% [-0.45, -0.19]   |
|         10 | +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 | 3.1%   | -31.0%       | -0.05% [-0.18, +0.08]   | -0.31% [-0.48, -0.15]   | -0.45% [-0.73, -0.22]   |
|          3 | verkopen na slot onder 20-daagse laag      | 2015-2026 | 2.5%   | -75.1%       | -0.04% [-0.22, +0.14]   | -0.17% [-0.38, +0.03]   | -0.26% [-0.49, -0.05]   |
|          3 | verkopen na slot onder 20-daagse laag      | 2023-2026 | 9.1%   | -51.1%       | +0.02% [-0.20, +0.30]   | -0.18% [-0.46, +0.14]   | -0.33% [-0.69, +0.07]   |
|          3 | +10% en eruit, anders 20-daagse-laag-regel | 2015-2026 | 2.2%   | -67.2%       | -0.04% [-0.17, +0.08]   | -0.20% [-0.34, -0.08]   | -0.29% [-0.46, -0.15]   |
|          3 | +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 | 0.1%   | -47.4%       | -0.09% [-0.24, +0.09]   | -0.36% [-0.56, -0.15]   | -0.51% [-0.79, -0.24]   |

## Ter vergelijking: kopen en vasthouden

| index   | periode   | CAGR   | max daling (weekbasis)   |
|:--------|:----------|:-------|:-------------------------|
| SPY     | 2015-2026 | 13.5%  | -31.8%                   |
| SPY     | 2023-2026 | 21.1%  | -16.9%                   |
| QQQ     | 2015-2026 | 18.5%  | -35.1%                   |
| QQQ     | 2023-2026 | 29.7%  | -21.3%                   |
