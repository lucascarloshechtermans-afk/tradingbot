# C6 Bollinger-onderband: eigen uitstap en nieuwe data

## Conclusie (na de run geschreven; de regels zijn niet aangepast)

1. **De voorsprong per trade is echt en herhaalt zich op nieuwe data:** op aandelen met $5-20M omzet per dag (nooit
   gebruikt in de vorige studie) is C6 met de klassieke uitstap M20 +0,30% per trade beter dan willekeurige aandelen
   [+0,12, +0,48], t = 3,15; ook bij M5, +10% en 5/10 is het verschil 2015-2026 positief.
2. **Als rekening verliest C6 het van SPY, met elke uitstap en met 3 of 10 posities.** Hoofdvariant (nieuwe data, M20,
   10 posities, 2015-2026): -0,11% per week (-7% per jaar), grootste daling -71%; SPY +0,27% per week (13,5% per jaar).
   Verschil met SPY -0,38% per week [-0,54, -0,23]. **Vooraf vastgelegd oordeel: NIET GESLAAGD.**
3. **Waarom per trade wel en als rekening niet:** de signalen komen in golven, vooral als de hele markt daalt. Per trade
   telt elk signaal mee; een rekening met 3 of 10 plekken kan op zo'n dag maar een paar van de honderden signalen nemen
   en zit dan vol in dalende aandelen. Bovendien betaalt de rekening elke week kosten en staat vaak in cash als SPY stijgt.
4. **De eigen uitstap (M20/M5) is niet beter dan +10% en eruit:** M20 geeft een hogere winrate (44% vs 38%) maar een lagere
   winst per trade; M5 (Connors-stijl) wint vaker (54%) maar verdient bijna niets per trade na kosten.
5. **Eerlijk advies:** C6 is een echte, kleine voorsprong in de keuze van aandelen, maar geen systeem dat SPY verslaat.
   SPY aanhouden blijft het beste uit al dit onderzoek. Gebruik `bollinger_mr.pine` hooguit als watchlist.

(De kolommen "max daling (2015-2026)" en "max daling (test)" staan elk alleen ingevuld bij hun eigen periode.)


Regels: `indicator_lab/week/c6_rules.md` (vooraf gecommit). Signaal: slot > SMA200 en slot < onderste Bollinger-band (20, 2); instap volgende open; stop onder support (max 8%); max 20 dagen; kosten 0,05% + $0,02 per kant; alleen aandelen die op 2026-10-23 genoteerd waren. 16 vergelijkingen; Bonferroni-grens |t| > 2.96.

**Vooraf vastgelegd oordeel (dataset B, uitstap M20, 10 posities, 2015-2026): NIET GESLAAGD** — verschil per trade vs random +0.30% [+0.12, +0.48], rekening vs SPY -0.38% per week [-0.54, -0.23].

## A — zelfde liquide aandelen als de vorige studie (> $20M/dag)

SPY 2015-2026: +0.27% per week, CAGR 13.5%.

### Per trade

| uitstap                                   | periode   |   trades | +10% geraakt   | winrate   | gem./trade   |   PF |   gem. dagen | random: winrate / gem.   | verschil vs random [95%]   |    t |
|:------------------------------------------|:----------|---------:|:---------------|:----------|:-------------|-----:|-------------:|:-------------------------|:---------------------------|-----:|
| m20: uit na slot boven SMA20 (middenband) | 2015-2026 |    35776 | 6%             | 44%       | 0.16%        | 1.07 |          6.5 | 48% / -0.01%             | +0.17% [+0.01, +0.34]      | 2.05 |
| m20: uit na slot boven SMA20 (middenband) | 2023-2026 |    14971 | 8%             | 44%       | 0.28%        | 1.11 |          6.7 | 48% / -0.02%             | +0.30% [+0.04, +0.57]      | 2.23 |
| m5: uit na slot boven SMA5 (Connors)      | 2015-2026 |    36859 | 2%             | 54%       | 0.03%        | 1.02 |          3.5 | 53% / -0.09%             | +0.13% [+0.02, +0.24]      | 2.32 |
| m5: uit na slot boven SMA5 (Connors)      | 2023-2026 |    15382 | 3%             | 53%       | 0.07%        | 1.04 |          3.7 | 53% / -0.08%             | +0.15% [-0.01, +0.32]      | 1.81 |
| d: +10% en eruit                          | 2015-2026 |    35237 | 23%            | 38%       | 0.36%        | 1.14 |          8.8 | 35% / 0.06%              | +0.30% [+0.14, +0.45]      | 3.9  |
| d: +10% en eruit                          | 2023-2026 |    14794 | 26%            | 38%       | 0.40%        | 1.15 |          8.6 | 34% / -0.03%             | +0.43% [+0.20, +0.66]      | 3.68 |
| e: helft op +5%, rest op +10%             | 2015-2026 |    35237 | 23%            | 43%       | 0.25%        | 1.11 |          8.8 | 41% / 0.01%              | +0.23% [+0.11, +0.35]      | 3.77 |
| e: helft op +5%, rest op +10%             | 2023-2026 |    14794 | 26%            | 43%       | 0.26%        | 1.11 |          8.6 | 40% / -0.09%             | +0.35% [+0.15, +0.54]      | 3.56 |

### Als rekening

|   posities | uitstap   | periode   | gem./week   | CAGR   | max daling (2015-2026)   | verschil vs RND [95%]   | verschil vs SPY [95%]   | max daling (test)   |
|-----------:|:----------|:----------|:------------|:-------|:-------------------------|:------------------------|:------------------------|:--------------------|
|          3 | m20       | 2015-2026 | -0.07%      | -5.0%  | -77.2%                   | +0.09% [-0.07, +0.24]   | -0.34% [-0.49, -0.20]   | nan                 |
|          3 | m20       | 2023-2026 | +0.14%      | 6.2%   | nan                      | +0.27% [+0.06, +0.50]   | -0.25% [-0.47, -0.03]   | -35.9%              |
|          3 | m5        | 2015-2026 | -0.24%      | -13.3% | -87.3%                   | +0.00% [-0.17, +0.18]   | -0.51% [-0.69, -0.34]   | nan                 |
|          3 | m5        | 2023-2026 | +0.04%      | 0.6%   | nan                      | +0.24% [-0.00, +0.50]   | -0.35% [-0.63, -0.09]   | -41.3%              |
|          3 | d         | 2015-2026 | +0.07%      | 2.3%   | -54.6%                   | +0.03% [-0.12, +0.16]   | -0.20% [-0.33, -0.07]   | nan                 |
|          3 | d         | 2023-2026 | +0.20%      | 9.6%   | nan                      | +0.08% [-0.12, +0.28]   | -0.19% [-0.41, +0.02]   | -30.9%              |
|          3 | e         | 2015-2026 | +0.02%      | 0.2%   | -52.0%                   | +0.01% [-0.11, +0.12]   | -0.25% [-0.38, -0.13]   | nan                 |
|          3 | e         | 2023-2026 | +0.12%      | 5.5%   | nan                      | +0.06% [-0.10, +0.23]   | -0.27% [-0.48, -0.08]   | -27.9%              |
|         10 | m20       | 2015-2026 | -0.09%      | -6.1%  | -71.5%                   | +0.05% [-0.08, +0.16]   | -0.36% [-0.49, -0.24]   | nan                 |
|         10 | m20       | 2023-2026 | +0.13%      | 5.7%   | nan                      | +0.22% [+0.07, +0.40]   | -0.26% [-0.44, -0.08]   | -25.6%              |
|         10 | m5        | 2015-2026 | -0.25%      | -13.2% | -83.1%                   | -0.01% [-0.15, +0.12]   | -0.52% [-0.66, -0.38]   | nan                 |
|         10 | m5        | 2023-2026 | -0.04%      | -3.3%  | nan                      | +0.15% [-0.06, +0.37]   | -0.43% [-0.66, -0.22]   | -29.5%              |
|         10 | d         | 2015-2026 | +0.03%      | 0.3%   | -47.8%                   | -0.02% [-0.13, +0.09]   | -0.24% [-0.35, -0.13]   | nan                 |
|         10 | d         | 2023-2026 | +0.15%      | 6.9%   | nan                      | +0.02% [-0.15, +0.19]   | -0.24% [-0.44, -0.05]   | -24.9%              |
|         10 | e         | 2015-2026 | -0.01%      | -1.3%  | -44.8%                   | -0.02% [-0.11, +0.06]   | -0.28% [-0.39, -0.17]   | nan                 |
|         10 | e         | 2023-2026 | +0.07%      | 3.0%   | nan                      | -0.02% [-0.16, +0.13]   | -0.32% [-0.51, -0.14]   | -22.3%              |

## B — nieuwe data: aandelen met $5M-$20M omzet per dag

SPY 2015-2026: +0.27% per week, CAGR 13.5%.

### Per trade

| uitstap                                   | periode   |   trades | +10% geraakt   | winrate   | gem./trade   |   PF |   gem. dagen | random: winrate / gem.   | verschil vs random [95%]   |    t |
|:------------------------------------------|:----------|---------:|:---------------|:----------|:-------------|-----:|-------------:|:-------------------------|:---------------------------|-----:|
| m20: uit na slot boven SMA20 (middenband) | 2015-2026 |    17334 | 7%             | 44%       | 0.11%        | 1.04 |          6.6 | 47% / -0.19%             | +0.30% [+0.12, +0.48]      | 3.15 |
| m20: uit na slot boven SMA20 (middenband) | 2023-2026 |     5736 | 8%             | 44%       | 0.12%        | 1.04 |          6.8 | 46% / -0.27%             | +0.39% [+0.02, +0.74]      | 2.1  |
| m5: uit na slot boven SMA5 (Connors)      | 2015-2026 |    17856 | 2%             | 54%       | -0.05%       | 0.97 |          3.5 | 52% / -0.26%             | +0.21% [+0.10, +0.31]      | 3.93 |
| m5: uit na slot boven SMA5 (Connors)      | 2023-2026 |     5893 | 3%             | 53%       | -0.08%       | 0.96 |          3.7 | 51% / -0.32%             | +0.24% [+0.05, +0.43]      | 2.4  |
| d: +10% en eruit                          | 2015-2026 |    17093 | 25%            | 37%       | 0.14%        | 1.05 |          8.6 | 36% / -0.10%             | +0.24% [+0.08, +0.39]      | 2.93 |
| d: +10% en eruit                          | 2023-2026 |     5686 | 27%            | 38%       | 0.07%        | 1.02 |          8.4 | 36% / -0.05%             | +0.12% [-0.15, +0.39]      | 0.89 |
| e: helft op +5%, rest op +10%             | 2015-2026 |    17093 | 25%            | 43%       | 0.08%        | 1.04 |          8.6 | 41% / -0.16%             | +0.24% [+0.11, +0.38]      | 3.6  |
| e: helft op +5%, rest op +10%             | 2023-2026 |     5686 | 27%            | 43%       | 0.04%        | 1.02 |          8.4 | 41% / -0.17%             | +0.21% [-0.03, +0.44]      | 1.75 |

### Als rekening

|   posities | uitstap   | periode   | gem./week   | CAGR   | max daling (2015-2026)   | verschil vs RND [95%]   | verschil vs SPY [95%]   | max daling (test)   |
|-----------:|:----------|:----------|:------------|:-------|:-------------------------|:------------------------|:------------------------|:--------------------|
|          3 | m20       | 2015-2026 | -0.02%      | -3.1%  | -71.1%                   | +0.33% [+0.17, +0.50]   | -0.29% [-0.47, -0.11]   | nan                 |
|          3 | m20       | 2023-2026 | +0.20%      | 8.9%   | nan                      | +0.61% [+0.33, +0.90]   | -0.18% [-0.50, +0.10]   | -38.2%              |
|          3 | m5        | 2015-2026 | -0.45%      | -22.8% | -95.5%                   | +0.08% [-0.08, +0.26]   | -0.72% [-0.91, -0.54]   | nan                 |
|          3 | m5        | 2023-2026 | -0.32%      | -17.1% | nan                      | +0.30% [-0.05, +0.61]   | -0.71% [-1.05, -0.41]   | -63.6%              |
|          3 | d         | 2015-2026 | +0.02%      | -0.6%  | -60.5%                   | +0.13% [+0.00, +0.26]   | -0.25% [-0.39, -0.10]   | nan                 |
|          3 | d         | 2023-2026 | +0.04%      | 0.9%   | nan                      | +0.12% [-0.08, +0.33]   | -0.34% [-0.57, -0.16]   | -42.2%              |
|          3 | e         | 2015-2026 | -0.04%      | -3.4%  | -60.9%                   | +0.09% [-0.01, +0.20]   | -0.31% [-0.44, -0.18]   | nan                 |
|          3 | e         | 2023-2026 | +0.01%      | -0.6%  | nan                      | +0.11% [-0.06, +0.28]   | -0.38% [-0.58, -0.21]   | -37.5%              |
|         10 | m20       | 2015-2026 | -0.11%      | -7.2%  | -70.5%                   | +0.26% [+0.14, +0.39]   | -0.38% [-0.54, -0.23]   | nan                 |
|         10 | m20       | 2023-2026 | +0.04%      | 0.1%   | nan                      | +0.43% [+0.16, +0.69]   | -0.35% [-0.63, -0.11]   | -33.8%              |
|         10 | m5        | 2015-2026 | -0.34%      | -17.6% | -90.8%                   | +0.21% [+0.07, +0.34]   | -0.61% [-0.76, -0.47]   | nan                 |
|         10 | m5        | 2023-2026 | -0.22%      | -11.9% | nan                      | +0.40% [+0.11, +0.67]   | -0.60% [-0.88, -0.38]   | -50.8%              |
|         10 | d         | 2015-2026 | -0.05%      | -4.2%  | -57.4%                   | +0.03% [-0.07, +0.14]   | -0.32% [-0.46, -0.19]   | nan                 |
|         10 | d         | 2023-2026 | +0.01%      | -0.7%  | nan                      | +0.13% [-0.04, +0.31]   | -0.38% [-0.60, -0.19]   | -30.0%              |
|         10 | e         | 2015-2026 | -0.08%      | -5.0%  | -56.3%                   | +0.05% [-0.04, +0.15]   | -0.35% [-0.48, -0.23]   | nan                 |
|         10 | e         | 2023-2026 | +0.00%      | -0.7%  | nan                      | +0.17% [+0.01, +0.32]   | -0.38% [-0.59, -0.21]   | -26.5%              |

