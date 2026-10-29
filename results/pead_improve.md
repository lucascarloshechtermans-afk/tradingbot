# Post-earnings gap — stap 5 (verbeteringen, eerlijke random, walk-forward)

Events: 2631; met EPS-data: 99%. Basis (hoogste train-PF van de 54): ADR > 3%, EPS any, exit A-EMA20, 40 dagen (train-PF 1.11).

## Verbeteringen (één tegelijk, gekozen op train)

| wijziging                          |   train trades |   train PF |   test trades |   test PF | test exp.   | gehouden   |
|:-----------------------------------|---------------:|-----------:|--------------:|----------:|:------------|:-----------|
| I1 winstverrassing >= +10%         |            448 |       1.02 |           675 |      0.97 | -0.15%      | nee        |
| I2 slot in bovenste 25% van de dag |            348 |       0.95 |           575 |      0.95 | -0.26%      | nee        |
| I3 slot boven SMA200               |            514 |       1.24 |           869 |      1.04 | +0.18%      | ja         |
| I4 gap >= 8%                       |            316 |       1.28 |           619 |      1    | +0.01%      | nee        |
| I5 volume >= 3x                    |            431 |       1.28 |           656 |      1.03 | +0.12%      | ja         |

## Eindvariant: basis + slot boven SMA200, volume >= 3x

| set   |   trades | winrate   |   PF |   PF zonder top 5% | exp.   |   exp. (R) | max DD   |   dagen |
|:------|---------:|:----------|-----:|-------------------:|:-------|-----------:|:---------|--------:|
| train |      431 | 30%       | 1.28 |               0.66 | +0.93% |       0.12 | -22.7%   |    15.4 |
| test  |      656 | 30%       | 1.03 |               0.55 | +0.12% |       0.07 | -32.6%   |    15.1 |

Eerlijke random (zelfde stopafstand): winrate 31%, PF 0.85. t-waarde gemiddelde testtrade 0.22 (Bonferroni-grens bij 59 varianten: 3.34).

### Walk-forward per jaar (PF en aantal trades)

|   jaar |   PF |   trades |
|-------:|-----:|---------:|
|   2015 | 0.2  |       22 |
|   2016 | 1.65 |       35 |
|   2017 | 2.31 |       47 |
|   2018 | 1.45 |       72 |
|   2019 | 1.07 |       68 |
|   2020 | 1.82 |       72 |
|   2021 | 0.81 |      106 |
|   2022 | 0.73 |        9 |
|   2023 | 1.12 |      126 |
|   2024 | 1.14 |      184 |
|   2025 | 0.92 |      181 |
|   2026 | 0.98 |      165 |

**Oordeel: NIET GOEDGEKEURD** (eisen: exp > 0, PF >= 1,3, PF > random).
