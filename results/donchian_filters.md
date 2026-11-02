# Donchian 20-breakout met filters tegen valse signalen (NASDAQ, dagbars)

## Conclusie

1. **De filters verminderen het aantal valse signalen nauwelijks:** het aandeel verliezende trades bleef rond 62%
   (basis 63%). Breakouts falen vaak, ook met trend, sterk slot en een niet-te-verre uitbraak.
2. **Wel werden de winnaars beter:** met F1 + F3 + F5 en de 20-daagse-laag-uitstap verdubbelde de winst per trade in de
   test (+1,55% tegen +0,81%, PF 1,21 tegen 1,09), maar niet aantoonbaar beter dan willekeurige aandelen
   (+0,02% [-1,12, +1,26]).
3. **Jouw v4.1 heeft de minste valse signalen** (56% verlies, winrate 44%) en de hoogste winst per trade (+5,2%, PF 1,78),
   maar heel weinig trades: als rekening met 10 posities maar 3,5% per jaar (veel cash).
4. **Als rekening verslaat niets SPY (21%) of QQQ (30%) in 2023-2026.** Beste: eindversie met de 20-daagse-laag-uitstap,
   12,0% per jaar (max daling -33%), en met +10% 11,3% per jaar (max daling -23%).
5. **Eerlijk advies:** filters maken de breakout netter maar niet winstgevend genoeg; QQQ/SPY vasthouden blijft beter.


Regels: `indicator_lab/week/donchian_filters_rules.md` (vooraf gecommit). 1496 NASDAQ-aandelen (> $5, > $20M/dag); alleen aandelen die op 2026-10-23 genoteerd waren. Kosten 0,05% + $0,02 per kant.

## 1. Elk filter apart op de trainjaren 2015-2022 (uitstap: 20-daagse laag)

| variant                                                      |   trades | valse signalen (verlies)   | winrate   | +10% geraakt   | gem./trade   |   PF |   gem. dagen | verschil vs random [95%]   |
|:-------------------------------------------------------------|---------:|:---------------------------|:----------|:---------------|:-------------|-----:|-------------:|:---------------------------|
| basis (alle breakouts)                                       |     8092 | 63%                        | 37%       | 20%            | 0.53%        | 1.07 |         45.8 | -0.32% [-0.95, +0.32]      |
| F1 trend: slot > SMA200 en SMA50 > SMA200 — gehouden         |     4954 | 62%                        | 38%       | 20%            | 1.48%        | 1.23 |         47.2 | +0.37% [-0.44, +1.21]      |
| F2 volume >= 1,5x gemiddelde                                 |     4975 | 62%                        | 38%       | 20%            | 0.23%        | 1.03 |         47.7 | -0.42% [-1.29, +0.49]      |
| F3 sterk slot (bovenste 30% van de dag) — gehouden           |     7473 | 62%                        | 38%       | 20%            | 0.68%        | 1.1  |         45.9 | -0.17% [-0.83, +0.52]      |
| F4 markt: QQQ boven SMA200                                   |     6808 | 64%                        | 36%       | 20%            | 0.93%        | 1.13 |         46.3 | -0.35% [-1.22, +0.48]      |
| F5 niet te ver: <= 2 ATR boven het 20-daagse hoog — gehouden |     7971 | 63%                        | 37%       | 20%            | 0.71%        | 1.1  |         45.7 | -0.29% [-0.91, +0.35]      |

## 2. Test 2023-2026 per trade (één keer gemeten)

| variant                                                               |   trades | valse signalen (verlies)   | winrate   | +10% geraakt   | gem./trade   |   PF |   gem. dagen | verschil vs random [95%]   |
|:----------------------------------------------------------------------|---------:|:---------------------------|:----------|:---------------|:-------------|-----:|-------------:|:---------------------------|
| basis — verkopen na slot onder 20-daagse laag                         |     6716 | 63%                        | 37%       | 22%            | 0.81%        | 1.09 |         44.2 | -1.19% [-2.40, +0.02]      |
| basis — +10% en eruit, anders 20-daagse-laag-regel                    |    14251 | 40%                        | 60%       | 59%            | 0.34%        | 1.06 |         18.8 | +0.14% [-0.22, +0.47]      |
| eindversie: F1 + F3 + F5 — verkopen na slot onder 20-daagse laag      |     3755 | 62%                        | 38%       | 21%            | 1.55%        | 1.21 |         44.6 | +0.02% [-1.12, +1.26]      |
| eindversie: F1 + F3 + F5 — +10% en eruit, anders 20-daagse-laag-regel |     6837 | 42%                        | 58%       | 56%            | 0.36%        | 1.07 |         19.7 | +0.37% [-0.10, +0.84]      |
| jouw v4.1 — verkopen na slot onder 20-daagse laag                     |     1721 | 56%                        | 44%       | 28%            | 5.20%        | 1.78 |         48.7 | +0.40% [-2.45, +3.91]      |
| jouw v4.1 — +10% en eruit, anders 20-daagse-laag-regel                |     1812 | 41%                        | 59%       | 57%            | 0.70%        | 1.14 |         20.3 | -0.28% [-0.99, +0.38]      |

## 3. Test 2023-2026 als rekening (10 posities, elk 1/10)

| variant                                                               | CAGR   | max daling   | verschil vs RND [95%]   | verschil vs SPY [95%]   | verschil vs QQQ [95%]   |
|:----------------------------------------------------------------------|:-------|:-------------|:------------------------|:------------------------|:------------------------|
| basis — verkopen na slot onder 20-daagse laag                         | 11.1%  | -35.3%       | +0.01% [-0.16, +0.22]   | -0.15% [-0.39, +0.13]   | -0.30% [-0.61, +0.03]   |
| basis — +10% en eruit, anders 20-daagse-laag-regel                    | 3.1%   | -31.0%       | -0.05% [-0.18, +0.08]   | -0.31% [-0.48, -0.15]   | -0.45% [-0.72, -0.23]   |
| eindversie: F1 + F3 + F5 — verkopen na slot onder 20-daagse laag      | 12.0%  | -32.6%       | +0.03% [-0.16, +0.23]   | -0.13% [-0.37, +0.12]   | -0.28% [-0.58, +0.02]   |
| eindversie: F1 + F3 + F5 — +10% en eruit, anders 20-daagse-laag-regel | 11.3%  | -22.6%       | +0.09% [-0.06, +0.26]   | -0.16% [-0.33, +0.01]   | -0.31% [-0.56, -0.08]   |
| jouw v4.1 — verkopen na slot onder 20-daagse laag                     | 3.5%   | -35.5%       | -0.12% [-0.39, +0.14]   | -0.28% [-0.56, -0.03]   | -0.43% [-0.78, -0.13]   |
| jouw v4.1 — +10% en eruit, anders 20-daagse-laag-regel                | -0.6%  | -28.1%       | -0.13% [-0.32, +0.08]   | -0.38% [-0.58, -0.19]   | -0.53% [-0.82, -0.26]   |

SPY 2023-2026: 21.1% per jaar; QQQ: 29.7% per jaar.
