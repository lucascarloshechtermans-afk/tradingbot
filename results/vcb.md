# Volatility compression breakout (NASDAQ, dagbars)

## Conclusie

1. **Compressie alleen verbetert de breakout niet:** op 2015-2022 maakt compressie + breakout +0,03% per trade (kaal
   +0,53%); in de test is het beter (+1,32%), maar dat is één periode en niet beter dan willekeurig.
2. **Compressie + trend is de beste variant** en is in beide periodes positief: +0,93% (train) en +1,93% per trade
   (test), PF 1,17 / 1,29. Maar het verschil met willekeurige aandelen is niet aantoonbaar ([-0,77, +2,18] in de test).
3. **"+10% en eruit" verhoogt de winrate** (50-54%) maar verlaagt de winst per trade sterk.
4. **Als rekening verslaat geen variant SPY (21%) of QQQ (30%) in 2023-2026.** Beste: compressie + breakout met de
   20-daagse-laag-uitstap, 18,0% per jaar (max daling -30%), net onder SPY maar niet aantoonbaar slechter of beter.
5. **Eerlijk oordeel:** de volatility compression breakout is een iets nettere breakout, geen aantoonbare edge.


Regels: `indicator_lab/week/vcb_rules.md` (vooraf gecommit). 1496 NASDAQ-aandelen; signalen 2015-2026: kale breakout 81799, V1 15901, V2 10947. Kosten 0,05% + $0,02 per kant.

## Per trade

| variant                       | uitstap                                    | periode   |   trades | winrate   | +10% geraakt   | gem./trade   |   PF |   gem. dagen | verschil vs random [95%]   |
|:------------------------------|:-------------------------------------------|:----------|---------:|:----------|:---------------|:-------------|-----:|-------------:|:---------------------------|
| kale 20-daagse breakout       | verkopen na slot onder 20-daagse laag      | 2015-2022 |     8092 | 37%       | 20%            | 0.53%        | 1.07 |         45.8 | -0.32% [-0.95, +0.32]      |
| kale 20-daagse breakout       | verkopen na slot onder 20-daagse laag      | 2023-2026 |     6716 | 37%       | 22%            | 0.81%        | 1.09 |         44.2 | -1.19% [-2.40, +0.02]      |
| kale 20-daagse breakout       | +10% en eruit, anders 20-daagse-laag-regel | 2015-2022 |    15640 | 56%       | 54%            | 0.11%        | 1.02 |         21.5 | -0.22% [-0.50, +0.05]      |
| kale 20-daagse breakout       | +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 |    14251 | 60%       | 59%            | 0.34%        | 1.06 |         18.8 | +0.14% [-0.22, +0.47]      |
| compressie + breakout         | verkopen na slot onder 20-daagse laag      | 2015-2022 |     3893 | 35%       | 17%            | 0.03%        | 1    |         43.1 | +0.04% [-0.69, +0.79]      |
| compressie + breakout         | verkopen na slot onder 20-daagse laag      | 2023-2026 |     3531 | 36%       | 20%            | 1.32%        | 1.19 |         42.3 | -0.05% [-1.39, +1.32]      |
| compressie + breakout         | +10% en eruit, anders 20-daagse-laag-regel | 2015-2022 |     4930 | 50%       | 47%            | 0.08%        | 1.02 |         21.9 | -0.05% [-0.39, +0.31]      |
| compressie + breakout         | +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 |     4491 | 54%       | 53%            | 0.22%        | 1.04 |         19.2 | +0.14% [-0.34, +0.59]      |
| compressie + breakout + trend | verkopen na slot onder 20-daagse laag      | 2015-2022 |     2649 | 36%       | 18%            | 0.93%        | 1.17 |         45   | +0.46% [-0.40, +1.34]      |
| compressie + breakout + trend | verkopen na slot onder 20-daagse laag      | 2023-2026 |     2228 | 38%       | 20%            | 1.93%        | 1.29 |         43.5 | +0.64% [-0.77, +2.18]      |
| compressie + breakout + trend | +10% en eruit, anders 20-daagse-laag-regel | 2015-2022 |     3405 | 50%       | 47%            | 0.26%        | 1.06 |         22.9 | +0.08% [-0.37, +0.51]      |
| compressie + breakout + trend | +10% en eruit, anders 20-daagse-laag-regel | 2023-2026 |     2846 | 54%       | 52%            | 0.44%        | 1.09 |         19.8 | +0.34% [-0.14, +0.80]      |

## Als rekening (10 posities, test 2023-2026)

| variant                       | uitstap                                    | CAGR 2023-2026   | max daling   | verschil vs RND [95%]   | verschil vs SPY [95%]   | verschil vs QQQ [95%]   |
|:------------------------------|:-------------------------------------------|:-----------------|:-------------|:------------------------|:------------------------|:------------------------|
| kale 20-daagse breakout       | verkopen na slot onder 20-daagse laag      | 11.1%            | -35.3%       | +0.01% [-0.16, +0.22]   | -0.15% [-0.39, +0.13]   | -0.30% [-0.61, +0.03]   |
| kale 20-daagse breakout       | +10% en eruit, anders 20-daagse-laag-regel | 3.1%             | -31.0%       | -0.05% [-0.18, +0.08]   | -0.31% [-0.48, -0.15]   | -0.45% [-0.72, -0.23]   |
| compressie + breakout         | verkopen na slot onder 20-daagse laag      | 18.0%            | -29.8%       | +0.13% [-0.05, +0.34]   | -0.03% [-0.28, +0.26]   | -0.18% [-0.48, +0.13]   |
| compressie + breakout         | +10% en eruit, anders 20-daagse-laag-regel | 4.6%             | -29.3%       | -0.02% [-0.19, +0.15]   | -0.28% [-0.48, -0.10]   | -0.42% [-0.72, -0.16]   |
| compressie + breakout + trend | verkopen na slot onder 20-daagse laag      | 13.5%            | -32.8%       | +0.05% [-0.14, +0.27]   | -0.11% [-0.34, +0.12]   | -0.26% [-0.54, +0.01]   |
| compressie + breakout + trend | +10% en eruit, anders 20-daagse-laag-regel | 6.0%             | -30.6%       | -0.00% [-0.20, +0.21]   | -0.25% [-0.45, -0.07]   | -0.40% [-0.69, -0.14]   |

SPY 2023-2026: 21.1% per jaar; QQQ 29.7%.
