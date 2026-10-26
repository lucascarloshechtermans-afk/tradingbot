# Hefboom alleen in een uptrend — eenmalige test

## S&P 500 1929-10-21 .. 1959-12-31 (nooit gebruikt)

| variant                          | CAGR   | max DD   |   MAR |   Sharpe (kas 0%) |
|:---------------------------------|:-------|:---------|------:|------------------:|
| kopen en vasthouden 1x           | 2.5%   | -84.4%   |  0.03 |              0.22 |
| L2: 2x boven SMA200, anders cash | 6.1%   | -81.1%   |  0.08 |              0.35 |
| T1: 1x boven SMA200, anders cash | 5.4%   | -53.8%   |  0.1  |              0.43 |
| 2x altijd (zonder filter)        | -4.7%  | -98.9%   | -0.05 |              0.14 |

**Vooraf vastgelegd criterium (CAGR hoger én max daling niet dieper dan kopen en vasthouden): GESLAAGD.**

Kosten: 3%/jaar rente op het geleende deel + 1%/jaar productkosten, 0,1% per wissel per eenheid, kas 0%, prijsindex zonder dividend.

## Beschrijvend (data al gebruikt voor T1): 12 buitenlandse indexen

| index   | B&H CAGR   | B&H max DD   | L2 CAGR   | L2 max DD   | L2 beter (CAGR hoger, DD niet dieper)   |
|:--------|:-----------|:-------------|:----------|:------------|:----------------------------------------|
| ^GDAXI  | 8.2%       | -73%         | 8.1%      | -73%        | nee                                     |
| ^FTSE   | 5.2%       | -53%         | -2.6%     | -93%        | nee                                     |
| ^N225   | 6.4%       | -82%         | 6.2%      | -74%        | nee                                     |
| ^HSI    | 5.9%       | -65%         | 5.2%      | -87%        | nee                                     |
| ^GSPTSE | 6.2%       | -50%         | 5.8%      | -64%        | nee                                     |
| ^AXJO   | 4.3%       | -54%         | -0.0%     | -52%        | nee                                     |
| ^FCHI   | 4.1%       | -65%         | 1.8%      | -68%        | nee                                     |
| ^SSMI   | 6.3%       | -56%         | 3.8%      | -78%        | nee                                     |
| ^AEX    | 5.7%       | -72%         | 3.9%      | -76%        | nee                                     |
| ^BVSP   | 13.3%      | -65%         | 6.3%      | -82%        | nee                                     |
| ^KS11   | 8.7%       | -56%         | 10.6%     | -76%        | nee                                     |
| ^TWII   | 7.1%       | -66%         | 8.4%      | -59%        | ja                                      |

## Oordeel (achteraf toegevoegd, na het lezen van de uitslag)
Het vooraf vastgelegde criterium is formeel gehaald, maar het criterium was te zwak: een max daling van -81% is
onacceptabel en op 11 van de 12 buitenlandse indexen was de hefboomregel slechter (FTSE -93%). **Hefboom wordt niet
aanbevolen.** De regel zonder hefboom (T1) heeft op dezelfde 1929-1959-periode de beste MAR en Sharpe.
