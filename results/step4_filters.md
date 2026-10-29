# Stap 4 en 5 — filters en combinatie (setups 2 en 6, exits uit stap 3)

## Setup 2 Qullamaggie breakout — exit ('S0', 0.08, 0.05, 1.0, 3, 10)

Filters die op train hielpen: geen rally > 2 ATR.

| filters             |   train trades | train winrate   |   train PF |   test trades | test winrate   |   test PF |   test PF zonder top 5% | test exp.   |   test exp. (R) | test gem. winst   | test gem. verlies   |   test dagen |
|:--------------------|---------------:|:----------------|-----------:|--------------:|:---------------|----------:|------------------------:|:------------|----------------:|:------------------|:--------------------|-------------:|
| geen                |           1623 | 60%             |       0.96 |          1733 | 61%            |      0.98 |                    0.85 | -0.07%      |           -0.01 | +4.8%             | -7.6%               |          4.1 |
| marktregime         |           1217 | 59%             |       0.9  |          1444 | 60%            |      0.94 |                    0.81 | -0.18%      |           -0.02 | +4.8%             | -7.6%               |          4   |
| geen rally > 2 ATR  |           1208 | 61%             |       0.99 |          1191 | 60%            |      0.96 |                    0.84 | -0.11%      |           -0.01 | +4.8%             | -7.5%               |          4.4 |
| ruimte >= 1,5x T1   |           1199 | 59%             |       0.94 |          1273 | 60%            |      0.92 |                    0.81 | -0.23%      |           -0.03 | +4.8%             | -7.6%               |          4   |
| supportsterkte >= 2 |            733 | 58%             |       0.88 |           810 | 61%            |      0.97 |                    0.86 | -0.08%      |           -0.01 | +4.7%             | -7.5%               |          4.2 |
| geen rally > 2 ATR  |           1208 | 61%             |       0.99 |          1191 | 60%            |      0.96 |                    0.84 | -0.11%      |           -0.01 | +4.8%             | -7.5%               |          4.4 |

## Setup 6 Pullback in sterke trend — exit ('S4', 0.08, 0.07, 0.5, 2, 20)

Filters die op train hielpen: geen.

| filters             |   train trades | train winrate   |   train PF |   test trades | test winrate   |   test PF |   test PF zonder top 5% | test exp.   |   test exp. (R) | test gem. winst   | test gem. verlies   |   test dagen |
|:--------------------|---------------:|:----------------|-----------:|--------------:|:---------------|----------:|------------------------:|:------------|----------------:|:------------------|:--------------------|-------------:|
| geen                |           6377 | 55%             |       1.07 |          6939 | 56%            |      1.07 |                    0.9  | +0.26%      |            0.03 | +7.1%             | -8.3%               |          6.3 |
| marktregime         |           4925 | 55%             |       1.06 |          5312 | 56%            |      1.1  |                    0.93 | +0.35%      |            0.04 | +7.1%             | -8.3%               |          6.3 |
| geen rally > 2 ATR  |           6377 | 55%             |       1.07 |          6939 | 56%            |      1.07 |                    0.9  | +0.26%      |            0.03 | +7.1%             | -8.3%               |          6.3 |
| ruimte >= 1,5x T1   |           4075 | 55%             |       1.05 |          4482 | 56%            |      1.07 |                    0.9  | +0.24%      |            0.03 | +7.1%             | -8.4%               |          5.7 |
| supportsterkte >= 2 |           1167 | 57%             |       1.13 |          1415 | 56%            |      1.06 |                    0.88 | +0.22%      |            0.03 | +7.1%             | -8.4%               |          6.7 |

## Setups 2 + 6 samen (elk met eigen exit en filters)

| set   |   trades | winrate   |   PF |   PF zonder top 5% | exp.   |   exp. (R) | gem. winst   | gem. verlies   |   dagen |
|:------|---------:|:----------|-----:|-------------------:|:-------|-----------:|:-------------|:---------------|--------:|
| train |     2375 | 59%       | 1.07 |               0.92 | +0.22% |       0.03 | +5.8%        | -7.8%          |     5.6 |
| test  |     2606 | 58%       | 1.02 |               0.85 | +0.07% |       0.01 | +6.0%        | -8.0%          |     5.7 |

## Eindtabel (test 2023-2026)

Totaal geteste combinaties in de winrate-studie: 1462; Bonferroni-grens (5% familywise, tweezijdig) voor de t-waarde van de gemiddelde trade: 4.14.

| variant     |   test trades | winrate   |   PF |   PF zonder top 5% | exp.   |   exp. (R) | houdtijd   | max DD (10x10%)   | random winrate / PF   | train winrate / PF   | jaren met PF > 1   | oordeel                                                                                                                                                          |
|:------------|--------------:|:----------|-----:|-------------------:|:-------|-----------:|:-----------|:------------------|:----------------------|:---------------------|:-------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| setup 2, F2 |          1191 | 60%       | 0.96 |               0.84 | -0.11% |      -0.01 | 4.4 d      | -26.9%            | 55% / 0.94            | 61% / 0.99           | 6 / 12             | AFGEWEZEN: winrate 60% < 70%; PF 0.96 < 1,3; PF zonder top 5% 0.84 < 1,2; winrate maar +5 pp vs random; PF maar +0.03 vs random; t = -0.6 < Bonferroni-grens 4.1 |
| setup 6, F4 |          1415 | 56%       | 1.06 |               0.88 | +0.22% |       0.03 | 6.7 d      | -34.0%            | 55% / 1.02            | 57% / 1.13           | 8 / 12             | AFGEWEZEN: winrate 56% < 70%; PF 1.06 < 1,3; PF zonder top 5% 0.88 < 1,2; winrate maar +1 pp vs random; PF maar +0.04 vs random; t = 1.0 < Bonferroni-grens 4.1  |
