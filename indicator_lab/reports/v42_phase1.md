# Swing v4.1 → v4.2 — fase 1 (onderzoek in Python)

## Conclusie (punt 9)

1. **Kosten: de voorsprong overleeft realistische Belgische kosten niet op schone data.** Op de 84 holdout-tickers
   (2015-2024/10) zakt v4 van PF 1,39 / 3,5% per jaar (0,1%/kant) naar PF 1,08 / 0,3% per jaar (0,5%/kant) en wordt
   negatief bij 0,7%/kant. Alleen op de (niet point-in-time) DEV-aandelen blijft er iets over (10,6% bij 0,5%/kant).
2. **Ablatie: het model voegt niets toe.** b (regels + regime) ≈ c (v4) in alle vier de cellen (DEV 11,4% vs 10,6%;
   holdout 0,8% vs 0,3%). AUC van het 17-feature-model op de v2+regime-trades: 0,45-0,54 (= muntworp); na de
   regime-regel filtert het maar 1-4% van de breakouts weg. De mini-modellen (d, e) zijn niet beter. **Wat wél werkt
   is de regime-regel**: a → b verbetert alle cellen (holdout: PF 0,91 → 1,09).
3. **Regime-regel blokkeert gemiddeld 61% van de handelsdagen** (2021: 92%, 2024: 93%, 2022: 15%). Een lagere drempel
   (0,00) geeft per trade meer winst maar minder trades; dat is op DEV ook iets beter (MAR 0,47 vs 0,42), maar de keuze
   van 0,03 blijft staan (niets gekozen op de holdout).
4. **Fill op de signaal-close ≈ fill op de volgende open**: de gemiddelde overnight gap na een signaal is ~0%
   (0,00-0,04 ATR). Een live BUY vlak voor het slot kost of wint dus niets wezenlijks.
5. **Gap-filter: geen consistent effect** (verschillen binnen de ruis, slaat 0,2-1,5% van de trades over) → weglaten.
6. **Earnings-regel: geen consistent effect** (DEV iets slechter, holdout gemengd) → weglaten.
7. **Jouw echte plan (10 posities, 1% risico, max 10%, idle cash in SPY > SMA200, 0,5%/kant): verslaat SPY niet.**
   DEV 10,9% vs SPY 13,2% (wel kleinere daling: MAR 0,47 vs 0,39); holdout-tickers 4,1% vs 13,2%; laatste 2 jaar
   -1,0% / 3,3% vs 15,5%.
8. **Survivorship**: holdout grotendeels point-in-time (S&P 500 van ~2015), maar zonder gedelistte aandelen zonder
   data; DEV duidelijk te optimistisch.

**Aanbeveling:** de eenvoudigste variant **b (regels + regime, zonder model)** is even goed als v4 en eerlijker. Maar
**geen enkele variant verslaat SPY na realistische kosten op schone data** — voor rendement is SPY kopen en houden beter;
de indicator beperkt alleen de daling.


Engine: `swing4/lab.py` + `sim2.py` (= de v4.1-regels; fill volgende open, 4×ATR-trail, 20-daagse-laag-exit, max 10 posities à 1/10, gemiddelde van 20 selectievolgordes). **De holdout is al één keer gebruikt (fase 3)**: alles hieronder op de holdout is een tweede blik en wordt alleen gerapporteerd, er wordt niets op gekozen.

## 1. Kosten per kant (v4 = huidig)

**DEV (253, 2015-2024/10)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| kosten 0.1%/kant                  |     2778 | 49.5%     | +4.31%       |      0.345 | 2.57 | 14.4%  | -20.4%   |  0.72 | 62%        |          |
| kosten 0.3%/kant                  |     2778 | 47.6%     | +3.89%       |      0.298 | 2.32 | 12.5%  | -23.1%   |  0.55 | 62%        |          |
| kosten 0.5%/kant                  |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |          |
| kosten 0.7%/kant                  |     2778 | 44.1%     | +3.06%       |      0.205 | 1.91 | 8.7%   | -28.7%   |  0.31 | 62%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

**TICKER-holdout (84, 2015-2024/10)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| kosten 0.1%/kant                  |      974 | 46.3%     | +1.04%       |      0.13  | 1.39 | 3.5%   | -17.4%   |  0.2  | 50%        |          |
| kosten 0.3%/kant                  |      974 | 44.0%     | +0.64%       |      0.08  | 1.22 | 1.9%   | -20.3%   |  0.09 | 50%        |          |
| kosten 0.5%/kant                  |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |          |
| kosten 0.7%/kant                  |      974 | 39.7%     | -0.17%       |     -0.018 | 0.95 | -1.3%  | -29.0%   | -0.04 | 50%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

**TIME-holdout (253, 2024/10-nu)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| kosten 0.1%/kant                  |      568 | 41.0%     | +1.77%       |      0.068 | 1.41 | 0.7%   | -21.9%   |  0.03 | 55%        |          |
| kosten 0.3%/kant                  |      568 | 39.1%     | +1.36%       |      0.03  | 1.3  | -1.7%  | -22.8%   | -0.07 | 55%        |          |
| kosten 0.5%/kant                  |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |          |
| kosten 0.7%/kant                  |      568 | 37.1%     | +0.56%       |     -0.045 | 1.11 | -6.2%  | -24.8%   | -0.25 | 55%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

**TICKER+TIME (84, 2024/10-nu)**

| variant                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:----------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| kosten 0.1%/kant                  |      203 | 39.4%     | +1.36%       |      0.053 | 1.38 | 3.4%   | -12.9%   |  0.27 | 48%        |          |
| kosten 0.3%/kant                  |      203 | 36.5%     | +0.95%       |      0.012 | 1.25 | 1.6%   | -13.8%   |  0.12 | 48%        |          |
| kosten 0.5%/kant                  |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |          |
| kosten 0.7%/kant                  |      203 | 32.0%     | +0.15%       |     -0.069 | 1.03 | -1.8%  | -15.6%   | -0.11 | 48%        |          |
| SPY kopen & houden (total return) |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

## 2. Ablatie van het model (kosten 0,5%/kant)

**DEV (253, 2015-2024/10)**

| variant                                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:--------------------------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| a v2 (alleen regels)                              |     6898 | 40.8%     | +1.77%       |      0.126 | 1.49 | 9.4%   | -33.4%   |  0.28 | 93%        |          |
| b v2 + regime                                     |     2857 | 46.1%     | +3.57%       |      0.257 | 2.13 | 11.4%  | -24.8%   |  0.47 | 63%        |          |
| c v4 (regels + model + regime) = huidig           |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |          |
| d v2 + regime + mini-model (rvol, spyRoc63, er20) |     2844 | 46.0%     | +3.50%       |      0.251 | 2.11 | 12.6%  | -24.3%   |  0.53 | 63%        |          |
| e v2 + regime + mini-model (rvol, er20)           |     2683 | 45.8%     | +3.60%       |      0.258 | 2.13 | 11.4%  | -25.3%   |  0.46 | 62%        |          |
| SPY kopen & houden (total return)                 |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

Model-diagnose op de v2+regime-trades:

| model                         |   trades v2+regime |   AUC (winst ja/nee) |   score sd | score p10-p90   | % weggefilterd na regime   |
|:------------------------------|-------------------:|---------------------:|-----------:|:----------------|:---------------------------|
| c v4 (17 features)            |               2857 |                0.508 |      0.129 | 0.40-0.75       | 4%                         |
| d mini (rvol, spyRoc63, er20) |               2857 |                0.527 |      0.085 | 0.43-0.64       | 1%                         |
| e mini (rvol, er20)           |               2857 |                0.521 |      0.056 | 0.38-0.52       | 9%                         |

**TICKER-holdout (84, 2015-2024/10)**

| variant                                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:--------------------------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| a v2 (alleen regels)                              |     2347 | 36.5%     | -0.31%       |     -0.047 | 0.91 | -2.9%  | -37.8%   | -0.08 | 85%        |          |
| b v2 + regime                                     |      990 | 42.2%     | +0.29%       |      0.036 | 1.09 | 0.8%   | -24.0%   |  0.04 | 51%        |          |
| c v4 (regels + model + regime) = huidig           |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |          |
| d v2 + regime + mini-model (rvol, spyRoc63, er20) |      989 | 42.4%     | +0.29%       |      0.036 | 1.09 | 0.5%   | -23.7%   |  0.02 | 51%        |          |
| e v2 + regime + mini-model (rvol, er20)           |      922 | 43.0%     | +0.33%       |      0.044 | 1.11 | 0.9%   | -22.6%   |  0.04 | 50%        |          |
| SPY kopen & houden (total return)                 |          |           |              |            |      | 13.2%  | -33.7%   |  0.39 | 100%       |     0.79 |

Model-diagnose op de v2+regime-trades:

| model                         |   trades v2+regime |   AUC (winst ja/nee) |   score sd | score p10-p90   | % weggefilterd na regime   |
|:------------------------------|-------------------:|---------------------:|-----------:|:----------------|:---------------------------|
| c v4 (17 features)            |                990 |                0.503 |      0.126 | 0.41-0.75       | 3%                         |
| d mini (rvol, spyRoc63, er20) |                990 |                0.506 |      0.078 | 0.43-0.63       | 1%                         |
| e mini (rvol, er20)           |                990 |                0.519 |      0.055 | 0.38-0.52       | 10%                        |

**TIME-holdout (253, 2024/10-nu)**

| variant                                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:--------------------------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| a v2 (alleen regels)                              |     1315 | 34.1%     | -0.37%       |     -0.063 | 0.93 | -7.6%  | -31.6%   | -0.23 | 94%        |          |
| b v2 + regime                                     |      580 | 36.9%     | +0.75%       |     -0.019 | 1.15 | -5.5%  | -23.8%   | -0.23 | 55%        |          |
| c v4 (regels + model + regime) = huidig           |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |          |
| d v2 + regime + mini-model (rvol, spyRoc63, er20) |      577 | 37.1%     | +0.78%       |     -0.017 | 1.16 | -4.4%  | -23.6%   | -0.18 | 55%        |          |
| e v2 + regime + mini-model (rvol, er20)           |      527 | 35.9%     | +0.69%       |     -0.03  | 1.14 | -5.1%  | -24.6%   | -0.21 | 54%        |          |
| SPY kopen & houden (total return)                 |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

Model-diagnose op de v2+regime-trades:

| model                         |   trades v2+regime |   AUC (winst ja/nee) |   score sd | score p10-p90   | % weggefilterd na regime   |
|:------------------------------|-------------------:|---------------------:|-----------:|:----------------|:---------------------------|
| c v4 (17 features)            |                580 |                0.544 |      0.083 | 0.45-0.65       | 3%                         |
| d mini (rvol, spyRoc63, er20) |                580 |                0.541 |      0.058 | 0.45-0.60       | 1%                         |
| e mini (rvol, er20)           |                580 |                0.459 |      0.049 | 0.40-0.52       | 12%                        |

**TICKER+TIME (84, 2024/10-nu)**

| variant                                           |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |   Sharpe |
|:--------------------------------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|---------:|
| a v2 (alleen regels)                              |      463 | 34.3%     | -0.02%       |     -0.05  | 1    | -9.2%  | -25.0%   | -0.36 | 86%        |          |
| b v2 + regime                                     |      204 | 34.8%     | +0.72%       |     -0.021 | 1.18 | -1.8%  | -16.7%   | -0.1  | 48%        |          |
| c v4 (regels + model + regime) = huidig           |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |          |
| d v2 + regime + mini-model (rvol, spyRoc63, er20) |      204 | 34.8%     | +0.72%       |     -0.021 | 1.18 | -1.8%  | -16.7%   | -0.1  | 48%        |          |
| e v2 + regime + mini-model (rvol, er20)           |      191 | 34.6%     | +0.27%       |     -0.045 | 1.07 | 0.2%   | -14.4%   |  0.03 | 46%        |          |
| SPY kopen & houden (total return)                 |          |           |              |            |      | 15.5%  | -18.8%   |  0.83 | 100%       |     0.95 |

Model-diagnose op de v2+regime-trades:

| model                         |   trades v2+regime |   AUC (winst ja/nee) |   score sd | score p10-p90   | % weggefilterd na regime   |
|:------------------------------|-------------------:|---------------------:|-----------:|:----------------|:---------------------------|
| c v4 (17 features)            |                204 |                0.448 |      0.065 | 0.46-0.62       | 1%                         |
| d mini (rvol, spyRoc63, er20) |                204 |                0.436 |      0.049 | 0.46-0.58       | 0%                         |
| e mini (rvol, er20)           |                204 |                0.415 |      0.046 | 0.41-0.52       | 8%                         |

## 3. Regime-regel

% handelsdagen waarop de regel (SPY 63d > 3%) een BUY blokkeert:

|   jaar | % geblokkeerd   |
|-------:|:----------------|
|   2015 | 29%             |
|   2016 | 51%             |
|   2017 | 84%             |
|   2018 | 50%             |
|   2019 | 61%             |
|   2020 | 71%             |
|   2021 | 92%             |
|   2022 | 15%             |
|   2023 | 62%             |
|   2024 | 93%             |
|   2025 | 64%             |
|   2026 | 62%             |

Gemiddeld 2015-2026: 61%.

Gevoeligheid van de drempel (v4, 0,5%/kant; op de holdout alleen rapporteren):

**DEV (253, 2015-2024/10)**

| variant       |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| drempel 0.000 |     1529 | 46.6%     | +4.37%       |      0.261 | 2.25 | 9.0%   | -19.2%   |  0.47 | 40%        |
| drempel 0.015 |     2022 | 45.9%     | +3.81%       |      0.24  | 2.13 | 7.9%   | -19.3%   |  0.41 | 50%        |
| drempel 0.030 |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |
| drempel 0.045 |     3802 | 43.4%     | +2.66%       |      0.184 | 1.82 | 9.9%   | -27.0%   |  0.37 | 72%        |
| drempel 0.060 |     4678 | 42.3%     | +2.32%       |      0.164 | 1.71 | 12.9%  | -30.1%   |  0.43 | 82%        |

**TICKER-holdout (84, 2015-2024/10)**

| variant       |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| drempel 0.000 |      533 | 43.7%     | +0.52%       |      0.058 | 1.15 | 2.6%   | -17.4%   |  0.15 | 33%        |
| drempel 0.015 |      702 | 41.9%     | +0.14%       |      0.019 | 1.04 | 1.1%   | -20.2%   |  0.05 | 42%        |
| drempel 0.030 |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |
| drempel 0.045 |     1314 | 39.9%     | +0.07%       |      0.008 | 1.02 | -1.5%  | -29.8%   | -0.05 | 63%        |
| drempel 0.060 |     1604 | 38.3%     | -0.12%       |     -0.019 | 0.96 | -2.0%  | -31.0%   | -0.07 | 72%        |

**TIME-holdout (253, 2024/10-nu)**

| variant       |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| drempel 0.000 |      273 | 48.0%     | +5.55%       |      0.248 | 2.51 | 6.0%   | -16.1%   |  0.38 | 29%        |
| drempel 0.015 |      368 | 45.1%     | +3.44%       |      0.137 | 1.87 | -0.1%  | -21.2%   |  0.01 | 41%        |
| drempel 0.030 |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |
| drempel 0.045 |      721 | 36.1%     | +0.48%       |     -0.027 | 1.1  | -9.0%  | -27.9%   | -0.32 | 62%        |
| drempel 0.060 |      853 | 35.2%     | +0.15%       |     -0.039 | 1.03 | -5.3%  | -32.0%   | -0.16 | 76%        |

**TICKER+TIME (84, 2024/10-nu)**

| variant       |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| drempel 0.000 |       92 | 32.6%     | +2.12%       |      0.004 | 1.55 | 0.6%   | -9.6%    |  0.07 | 27%        |
| drempel 0.015 |      144 | 34.7%     | +1.27%       |     -0.02  | 1.37 | 1.5%   | -10.8%   |  0.15 | 35%        |
| drempel 0.030 |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |
| drempel 0.045 |      262 | 34.4%     | -0.05%       |     -0.055 | 0.99 | -4.8%  | -17.9%   | -0.26 | 56%        |
| drempel 0.060 |      314 | 33.8%     | +0.21%       |     -0.043 | 1.05 | -9.1%  | -20.9%   | -0.43 | 65%        |

## 4. Fill op de signaal-close (live BUY) vs volgende open (v4, 0,5%/kant)

**DEV (253, 2015-2024/10)**

| variant                   |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| fill volgende open (v4.1) |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |
| fill op signaal-close     |     2783 | 45.6%     | +3.47%       |      0.249 | 2.09 | 10.4%  | -23.9%   |  0.44 | 62%        |

Overnight gap na een signaal: gemiddeld +0.01% (mediaan -0.01%), = +0.00 ATR; 48% van de gaps is omhoog.

**TICKER-holdout (84, 2015-2024/10)**

| variant                   |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| fill volgende open (v4.1) |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |
| fill op signaal-close     |      973 | 41.7%     | +0.25%       |      0.032 | 1.08 | 1.0%   | -22.4%   |  0.05 | 52%        |

Overnight gap na een signaal: gemiddeld +0.04% (mediaan -0.00%), = -0.00 ATR; 48% van de gaps is omhoog.

**TIME-holdout (253, 2024/10-nu)**

| variant                   |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| fill volgende open (v4.1) |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |
| fill op signaal-close     |      569 | 38.7%     | +0.99%       |      0.004 | 1.21 | -6.0%  | -24.4%   | -0.24 | 55%        |

Overnight gap na een signaal: gemiddeld +0.07% (mediaan +0.08%), = +0.04 ATR; 55% van de gaps is omhoog.

**TICKER+TIME (84, 2024/10-nu)**

| variant                   |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| fill volgende open (v4.1) |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |
| fill op signaal-close     |      203 | 36.0%     | +0.54%       |     -0.031 | 1.13 | 2.8%   | -13.3%   |  0.21 | 50%        |

Overnight gap na een signaal: gemiddeld +0.07% (mediaan +0.02%), = +0.01 ATR; 51% van de gaps is omhoog.

## 5. Gap-filter bij instap (sla over als open > signaal-close + x·ATR; v4, 0,5%/kant)

**DEV (253, 2015-2024/10)**

| variant            |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:-------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| geen filter (v4.1) |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |
| x = 1.0            |     2764 | 45.7%     | +3.44%       |      0.248 | 2.1  | 11.9%  | -23.6%   |  0.51 | 62%        |
| x = 1.5            |     2770 | 45.7%     | +3.44%       |      0.249 | 2.1  | 11.7%  | -25.1%   |  0.47 | 62%        |
| x = 2.0            |     2772 | 45.8%     | +3.48%       |      0.252 | 2.11 | 11.2%  | -25.8%   |  0.44 | 62%        |

**TICKER-holdout (84, 2015-2024/10)**

| variant            |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:-------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| geen filter (v4.1) |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |
| x = 1.0            |      968 | 42.0%     | +0.28%       |      0.033 | 1.09 | 0.8%   | -23.6%   |  0.03 | 50%        |
| x = 1.5            |      970 | 42.0%     | +0.26%       |      0.031 | 1.09 | 0.7%   | -23.3%   |  0.03 | 50%        |
| x = 2.0            |      972 | 42.1%     | +0.27%       |      0.033 | 1.09 | 0.7%   | -23.8%   |  0.03 | 50%        |

**TIME-holdout (253, 2024/10-nu)**

| variant            |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:-------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| geen filter (v4.1) |      568 | 37.7%     | +0.96%       |     -0.008 | 1.2  | -4.0%  | -23.7%   | -0.17 | 55%        |
| x = 1.0            |      565 | 37.9%     | +0.98%       |     -0.008 | 1.21 | -3.9%  | -23.8%   | -0.16 | 56%        |
| x = 1.5            |      566 | 37.8%     | +1.00%       |     -0.004 | 1.21 | -2.9%  | -24.2%   | -0.12 | 56%        |
| x = 2.0            |      566 | 37.8%     | +1.00%       |     -0.004 | 1.21 | -2.9%  | -24.2%   | -0.12 | 56%        |

**TICKER+TIME (84, 2024/10-nu)**

| variant            |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:-------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| geen filter (v4.1) |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |
| x = 1.0            |      200 | 35.0%     | +0.66%       |     -0.023 | 1.17 | 2.0%   | -14.4%   |  0.15 | 48%        |
| x = 1.5            |      202 | 35.1%     | +0.61%       |     -0.024 | 1.15 | 1.0%   | -14.3%   |  0.08 | 48%        |
| x = 2.0            |      202 | 35.1%     | +0.61%       |     -0.024 | 1.15 | 1.0%   | -14.3%   |  0.08 | 48%        |

## 6. Earnings-regel: geen BUY als er cijfers zijn binnen 7 kalenderdagen (v4, 0,5%/kant)

Aandelen met earnings-data: 95%.

**DEV (253, 2015-2024/10)**

| variant             |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| zonder regel (v4.1) |     2778 | 45.7%     | +3.47%       |      0.251 | 2.11 | 10.6%  | -25.9%   |  0.42 | 62%        |
| met earnings-blok   |     2691 | 45.3%     | +3.34%       |      0.24  | 2.06 | 10.0%  | -29.0%   |  0.35 | 62%        |

**TICKER-holdout (84, 2015-2024/10)**

| variant             |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| zonder regel (v4.1) |      974 | 42.0%     | +0.23%       |      0.031 | 1.08 | 0.3%   | -23.9%   |  0.01 | 50%        |
| met earnings-blok   |      929 | 42.4%     | +0.27%       |      0.037 | 1.09 | -0.3%  | -22.4%   | -0.01 | 50%        |

**TIME-holdout (253, 2024/10-nu)**

| variant             |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| zonder regel (v4.1) |      568 | 37.7%     | +0.96%       |     -0.008 |  1.2 | -4.0%  | -23.7%   | -0.17 | 55%        |
| met earnings-blok   |      533 | 36.8%     | +0.95%       |     -0.003 |  1.2 | -2.1%  | -24.2%   | -0.08 | 54%        |

**TICKER+TIME (84, 2024/10-nu)**

| variant             |   trades | winrate   | expectancy   |   exp. (R) |   PF | CAGR   | max DD   |   MAR | exposure   |
|:--------------------|---------:|:----------|:-------------|-----------:|-----:|:-------|:---------|------:|:-----------|
| zonder regel (v4.1) |      203 | 35.0%     | +0.55%       |     -0.029 | 1.14 | -0.1%  | -14.6%   | -0    | 48%        |
| met earnings-blok   |      194 | 35.6%     | +0.86%       |     -0.001 | 1.22 | 2.0%   | -13.1%   |  0.17 | 47%        |

## 7. Jouw echte plan: max 10 posities, 1% risico per trade, max 10% per positie, idle cash in SPY als SPY > SMA200 (E48), kosten 0,5%/kant

**DEV (253, 2015-2024/10)**

| variant                                 | CAGR   | max DD   |   MAR |   Sharpe | exposure (aandelen)   | exposure   |
|:----------------------------------------|:-------|:---------|------:|---------:|:----------------------|:-----------|
| c v4 (regels + model + regime) = huidig | 10.9%  | -23.4%   |  0.47 |     0.82 | 53%                   |            |
| b v2 + regime                           | 11.2%  | -23.6%   |  0.48 |     0.84 | 54%                   |            |
| SPY kopen & houden (total return)       | 13.2%  | -33.7%   |  0.39 |     0.79 |                       | 100%       |

**TICKER-holdout (84, 2015-2024/10)**

| variant                                 | CAGR   | max DD   |   MAR |   Sharpe | exposure (aandelen)   | exposure   |
|:----------------------------------------|:-------|:---------|------:|---------:|:----------------------|:-----------|
| c v4 (regels + model + regime) = huidig | 4.1%   | -24.0%   |  0.17 |     0.38 | 47%                   |            |
| b v2 + regime                           | 4.6%   | -23.7%   |  0.19 |     0.42 | 48%                   |            |
| SPY kopen & houden (total return)       | 13.2%  | -33.7%   |  0.39 |     0.79 |                       | 100%       |

**TIME-holdout (253, 2024/10-nu)**

| variant                                 | CAGR   | max DD   |   MAR |   Sharpe | exposure (aandelen)   | exposure   |
|:----------------------------------------|:-------|:---------|------:|---------:|:----------------------|:-----------|
| c v4 (regels + model + regime) = huidig | -1.0%  | -17.8%   | -0.05 |    -0    | 42%                   |            |
| b v2 + regime                           | -2.6%  | -19.4%   | -0.13 |    -0.12 | 42%                   |            |
| SPY kopen & houden (total return)       | 15.5%  | -18.8%   |  0.83 |     0.95 |                       | 100%       |

**TICKER+TIME (84, 2024/10-nu)**

| variant                                 | CAGR   | max DD   |   MAR |   Sharpe | exposure (aandelen)   | exposure   |
|:----------------------------------------|:-------|:---------|------:|---------:|:----------------------|:-----------|
| c v4 (regels + model + regime) = huidig | 3.3%   | -14.1%   |  0.24 |     0.32 | 41%                   |            |
| b v2 + regime                           | 2.7%   | -14.9%   |  0.19 |     0.27 | 42%                   |            |
| SPY kopen & houden (total return)       | 15.5%  | -18.8%   |  0.83 |     0.95 |                       | 100%       |

## 8. Survivorship bias

- De 84 holdout-tickers (`swing4/holdout.json`) zijn **S&P 500-leden van ~2015**, gekozen op lidmaatschap rond 2015 (niet op latere prestaties), met bewust latere achterblijvers en index-verlaters (KSS, M, XRX, NWL, VFC, LUMN, IVZ, BEN, F, VTRS, BIIB, MOS). Dat is grotendeels point-in-time.
- Maar: alleen aandelen waarvan Yahoo nog data heeft konden gekozen worden. Drie vielen af (IPG overgenomen, EA en EQR zonder data); aandelen die tussen 2015 en 2024 verdwenen (overnames, faillissementen) en waarvan geen data meer bestaat, ontbreken. Ongeveer een kwart van de S&P 500 van 2015 is er in 2024 niet meer; een deel daarvan zou in de holdout hebben gezeten. Faillissementen ontbreken dus vooral → de holdout is licht te optimistisch, overnames (vaak met een koerssprong) ontbreken ook → dat werkt de andere kant op. Netto: kleine, onbekende bias; geen point-in-time-database met gedelistte koersen beschikbaar in deze omgeving.
- De 253 DEV-tickers zijn **niet** point-in-time: grotendeels namen die eerder in dit project gekozen werden (o.a. bekende volatiele groeiers) — daar zijn de cijfers duidelijk te optimistisch.

