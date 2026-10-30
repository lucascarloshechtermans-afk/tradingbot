# Strategy log — one-week swing study (indicator_lab/week)

Zie `indicator_lab/week/run.py` voor het protocol. Train = 2015-01-01 .. 2023-04-06, test (out-of-sample) = 2023-04-07 .. 2026-10-23.

| run | strategie | instellingen | set | trades | winrate | gem. winst | gem. verlies | PF | expectancy | max DD (rekening) | CAGR (rekening) | % +10% geraakt | % +20% geraakt | gem. houdtijd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 VCP (Minervini) | geen filters | train | 251 | 41% | +8.0% | -7.4% | 0.74 | -1.15% | -29.7% | -3.7% | 29% | 6% | 6.2 d |
| 1 | 1 VCP (Minervini) | geen filters | test | 302 | 45% | +7.8% | -7.6% | 0.85 | -0.61% | -24.1% | -5.8% | 30% | 6% | 6.1 d |
| 2 | 1 VCP (Minervini) | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 201 | 41% | +8.1% | -7.5% | 0.74 | -1.13% | -23.6% | -3.0% | 29% | 6% | 6.0 d |
| 2 | 1 VCP (Minervini) | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 247 | 45% | +7.8% | -7.6% | 0.84 | -0.69% | -22.9% | -5.3% | 30% | 6% | 6.1 d |
| 3 | 1 VCP (Minervini) | ruimte >= 10% tot sterke weerstand | train | 163 | 42% | +8.5% | -7.5% | 0.81 | -0.85% | -22.9% | -1.8% | 32% | 9% | 6.2 d |
| 3 | 1 VCP (Minervini) | ruimte >= 10% tot sterke weerstand | test | 162 | 45% | +8.8% | -7.7% | 0.94 | -0.26% | -12.2% | -1.5% | 31% | 10% | 6.2 d |
| 4 | 1 VCP (Minervini) | RS top 20% | train | 103 | 38% | +7.6% | -7.1% | 0.65 | -1.55% | -20.1% | -1.9% | 29% | 5% | 6.4 d |
| 4 | 1 VCP (Minervini) | RS top 20% | test | 124 | 47% | +8.6% | -7.6% | 0.99 | -0.05% | -7.4% | -0.4% | 34% | 10% | 5.7 d |
| 5 | 1 VCP (Minervini) | volume >= 1.5x op signaaldag | train | 251 | 41% | +8.0% | -7.4% | 0.74 | -1.15% | -29.7% | -3.7% | 29% | 6% | 6.2 d |
| 5 | 1 VCP (Minervini) | volume >= 1.5x op signaaldag | test | 302 | 45% | +7.8% | -7.6% | 0.85 | -0.61% | -24.1% | -5.8% | 30% | 6% | 6.1 d |
| 6 | 1 VCP (Minervini) | geen earnings in de houdtijd | train | 230 | 40% | +7.8% | -7.4% | 0.71 | -1.26% | -29.5% | -3.8% | 28% | 5% | 6.2 d |
| 6 | 1 VCP (Minervini) | geen earnings in de houdtijd | test | 276 | 45% | +7.4% | -7.6% | 0.78 | -0.91% | -26.8% | -7.5% | 28% | 4% | 6.1 d |
| 7 | 1 VCP (Minervini) | marktregime (SPY > SMA50, EMA20 > EMA50) + ruimte >= 10% tot sterke weerstand | train | 133 | 41% | +8.6% | -7.8% | 0.78 | -0.99% | -21.9% | -1.7% | 32% | 8% | 6.0 d |
| 7 | 1 VCP (Minervini) | marktregime (SPY > SMA50, EMA20 > EMA50) + ruimte >= 10% tot sterke weerstand | test | 134 | 47% | +8.9% | -7.7% | 1.02 | +0.09% | -8.8% | 0.0% | 34% | 11% | 6.2 d |
| 8 | 2 Qullamaggie breakout | geen filters | train | 1588 | 46% | +7.4% | -7.1% | 0.89 | -0.41% | -48.6% | -7.4% | 29% | 6% | 6.8 d |
| 8 | 2 Qullamaggie breakout | geen filters | test | 1505 | 48% | +8.2% | -7.5% | 1.01 | +0.03% | -38.1% | -1.4% | 33% | 8% | 6.4 d |
| 9 | 2 Qullamaggie breakout | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 1215 | 44% | +7.5% | -7.2% | 0.80 | -0.83% | -57.9% | -9.7% | 28% | 6% | 6.6 d |
| 9 | 2 Qullamaggie breakout | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 1252 | 46% | +8.3% | -7.5% | 0.95 | -0.19% | -46.9% | -7.7% | 33% | 8% | 6.4 d |
| 10 | 2 Qullamaggie breakout | ruimte >= 10% tot sterke weerstand | train | 1103 | 44% | +7.5% | -7.2% | 0.83 | -0.68% | -44.1% | -6.7% | 28% | 8% | 7.0 d |
| 10 | 2 Qullamaggie breakout | ruimte >= 10% tot sterke weerstand | test | 1035 | 46% | +8.2% | -7.4% | 0.95 | -0.18% | -27.8% | -1.5% | 31% | 10% | 6.6 d |
| 11 | 2 Qullamaggie breakout | RS top 20% | train | 498 | 44% | +7.7% | -7.1% | 0.87 | -0.51% | -41.0% | -3.6% | 30% | 6% | 6.7 d |
| 11 | 2 Qullamaggie breakout | RS top 20% | test | 460 | 46% | +8.4% | -7.8% | 0.92 | -0.34% | -30.2% | -5.0% | 32% | 10% | 5.9 d |
| 12 | 2 Qullamaggie breakout | volume >= 1.5x op signaaldag | train | 1588 | 46% | +7.4% | -7.1% | 0.89 | -0.41% | -48.6% | -7.4% | 29% | 6% | 6.8 d |
| 12 | 2 Qullamaggie breakout | volume >= 1.5x op signaaldag | test | 1505 | 48% | +8.2% | -7.5% | 1.01 | +0.03% | -38.1% | -1.4% | 33% | 8% | 6.4 d |
| 13 | 2 Qullamaggie breakout | geen earnings in de houdtijd | train | 1446 | 46% | +7.2% | -7.0% | 0.86 | -0.51% | -51.6% | -8.2% | 28% | 5% | 6.8 d |
| 13 | 2 Qullamaggie breakout | geen earnings in de houdtijd | test | 1388 | 47% | +7.9% | -7.3% | 0.98 | -0.09% | -47.5% | -6.7% | 32% | 6% | 6.4 d |
| 14 | 3 Episodic pivot | geen filters | train | 427 | 34% | +8.5% | -7.9% | 0.56 | -2.29% | -65.2% | -11.4% | 29% | 9% | 3.9 d |
| 14 | 3 Episodic pivot | geen filters | test | 458 | 35% | +8.8% | -8.0% | 0.59 | -2.15% | -65.0% | -23.7% | 29% | 8% | 3.9 d |
| 15 | 3 Episodic pivot | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 273 | 34% | +8.7% | -8.1% | 0.56 | -2.31% | -49.1% | -7.6% | 29% | 10% | 3.6 d |
| 15 | 3 Episodic pivot | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 360 | 36% | +8.7% | -8.1% | 0.59 | -2.13% | -56.6% | -18.9% | 31% | 9% | 3.8 d |
| 16 | 3 Episodic pivot | ruimte >= 10% tot sterke weerstand | train | 307 | 32% | +8.6% | -8.1% | 0.50 | -2.77% | -60.9% | -9.9% | 28% | 10% | 3.6 d |
| 16 | 3 Episodic pivot | ruimte >= 10% tot sterke weerstand | test | 340 | 31% | +8.8% | -8.1% | 0.48 | -2.89% | -64.3% | -23.9% | 26% | 8% | 3.8 d |
| 17 | 3 Episodic pivot | RS top 20% | train | 189 | 28% | +9.2% | -7.8% | 0.46 | -3.06% | -46.8% | -6.9% | 24% | 9% | 3.4 d |
| 17 | 3 Episodic pivot | RS top 20% | test | 214 | 30% | +8.9% | -8.3% | 0.46 | -3.11% | -52.5% | -17.4% | 25% | 8% | 3.1 d |
| 18 | 3 Episodic pivot | volume >= 1.5x op signaaldag | train | 427 | 34% | +8.5% | -7.9% | 0.56 | -2.29% | -65.2% | -11.4% | 29% | 9% | 3.9 d |
| 18 | 3 Episodic pivot | volume >= 1.5x op signaaldag | test | 458 | 35% | +8.8% | -8.0% | 0.59 | -2.15% | -65.0% | -23.7% | 29% | 8% | 3.9 d |
| 19 | 3 Episodic pivot | geen earnings in de houdtijd | train | 427 | 34% | +8.5% | -7.9% | 0.56 | -2.29% | -65.2% | -11.4% | 29% | 9% | 3.9 d |
| 19 | 3 Episodic pivot | geen earnings in de houdtijd | test | 458 | 35% | +8.8% | -8.0% | 0.59 | -2.15% | -65.0% | -23.7% | 29% | 8% | 3.9 d |
| 20 | 4 S/R flip retest | geen filters | train | 20605 | 41% | +8.2% | -6.3% | 0.91 | -0.34% | -79.0% | -17.0% | 30% | 5% | 5.5 d |
| 20 | 4 S/R flip retest | geen filters | test | 16825 | 42% | +8.5% | -6.4% | 0.97 | -0.11% | -56.7% | -18.0% | 31% | 6% | 5.2 d |
| 21 | 4 S/R flip retest | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 13118 | 40% | +8.2% | -6.2% | 0.89 | -0.42% | -78.1% | -17.0% | 29% | 5% | 5.4 d |
| 21 | 4 S/R flip retest | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 12838 | 40% | +8.6% | -6.4% | 0.89 | -0.42% | -52.6% | -15.5% | 30% | 6% | 5.1 d |
| 22 | 4 S/R flip retest | ruimte >= 10% tot sterke weerstand | train | 11679 | 41% | +8.5% | -6.7% | 0.87 | -0.49% | -86.8% | -21.8% | 32% | 8% | 5.5 d |
| 22 | 4 S/R flip retest | ruimte >= 10% tot sterke weerstand | test | 9004 | 42% | +8.9% | -6.8% | 0.96 | -0.15% | -59.5% | -18.1% | 33% | 9% | 5.4 d |
| 23 | 4 S/R flip retest | RS top 20% | train | 4729 | 42% | +8.3% | -6.5% | 0.94 | -0.22% | -74.1% | -12.9% | 33% | 5% | 5.2 d |
| 23 | 4 S/R flip retest | RS top 20% | test | 3462 | 44% | +9.1% | -7.2% | 0.98 | -0.08% | -54.1% | -13.2% | 36% | 8% | 4.5 d |
| 24 | 4 S/R flip retest | volume >= 1.5x op signaaldag | train | 3822 | 39% | +8.1% | -6.4% | 0.79 | -0.81% | -75.6% | -15.7% | 28% | 6% | 5.1 d |
| 24 | 4 S/R flip retest | volume >= 1.5x op signaaldag | test | 3668 | 42% | +8.6% | -6.6% | 0.94 | -0.21% | -54.1% | -11.9% | 32% | 7% | 4.9 d |
| 25 | 4 S/R flip retest | geen earnings in de houdtijd | train | 19224 | 40% | +8.0% | -6.2% | 0.85 | -0.56% | -86.5% | -21.6% | 29% | 4% | 5.4 d |
| 25 | 4 S/R flip retest | geen earnings in de houdtijd | test | 15553 | 41% | +8.3% | -6.3% | 0.93 | -0.25% | -58.4% | -18.5% | 30% | 5% | 5.2 d |
| 26 | 5 Failed breakdown / spring | geen filters | train | 5475 | 45% | +8.1% | -6.9% | 0.95 | -0.18% | -71.3% | -11.7% | 32% | 5% | 6.0 d |
| 26 | 5 Failed breakdown / spring | geen filters | test | 4596 | 44% | +8.6% | -7.0% | 0.96 | -0.16% | -48.0% | -6.9% | 33% | 5% | 5.7 d |
| 27 | 5 Failed breakdown / spring | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 3255 | 42% | +8.0% | -6.8% | 0.85 | -0.60% | -73.1% | -14.0% | 29% | 5% | 6.1 d |
| 27 | 5 Failed breakdown / spring | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 3386 | 41% | +8.8% | -7.0% | 0.88 | -0.47% | -41.7% | -4.7% | 31% | 5% | 5.6 d |
| 28 | 5 Failed breakdown / spring | ruimte >= 10% tot sterke weerstand | train | 2605 | 45% | +8.4% | -7.2% | 0.95 | -0.20% | -65.0% | -7.6% | 34% | 8% | 6.1 d |
| 28 | 5 Failed breakdown / spring | ruimte >= 10% tot sterke weerstand | test | 2157 | 43% | +8.9% | -7.4% | 0.90 | -0.43% | -54.2% | -17.0% | 33% | 8% | 5.7 d |
| 29 | 5 Failed breakdown / spring | RS top 20% | train | 1263 | 43% | +8.2% | -6.8% | 0.89 | -0.42% | -52.1% | -6.3% | 32% | 4% | 5.8 d |
| 29 | 5 Failed breakdown / spring | RS top 20% | test | 1122 | 42% | +9.2% | -7.5% | 0.89 | -0.47% | -41.9% | -8.9% | 35% | 7% | 5.0 d |
| 30 | 5 Failed breakdown / spring | volume >= 1.5x op signaaldag | train | 1077 | 47% | +8.2% | -7.2% | 0.99 | -0.03% | -37.5% | -3.0% | 34% | 6% | 5.8 d |
| 30 | 5 Failed breakdown / spring | volume >= 1.5x op signaaldag | test | 978 | 42% | +8.4% | -7.6% | 0.79 | -0.91% | -61.0% | -21.9% | 30% | 5% | 5.2 d |
| 31 | 5 Failed breakdown / spring | geen earnings in de houdtijd | train | 5047 | 44% | +8.0% | -6.8% | 0.91 | -0.36% | -74.8% | -14.1% | 31% | 4% | 6.0 d |
| 31 | 5 Failed breakdown / spring | geen earnings in de houdtijd | test | 4200 | 43% | +8.4% | -6.9% | 0.92 | -0.31% | -51.0% | -9.8% | 31% | 4% | 5.7 d |
| 32 | 6 Pullback in sterke trend | geen filters | train | 4605 | 42% | +8.8% | -6.5% | 0.98 | -0.06% | -50.9% | -7.2% | 33% | 7% | 5.1 d |
| 32 | 6 Pullback in sterke trend | geen filters | test | 4589 | 43% | +8.8% | -6.6% | 1.01 | +0.05% | -58.8% | -17.9% | 34% | 8% | 5.2 d |
| 33 | 6 Pullback in sterke trend | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 3534 | 42% | +8.7% | -6.5% | 0.95 | -0.17% | -48.7% | -6.0% | 33% | 7% | 5.1 d |
| 33 | 6 Pullback in sterke trend | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 3627 | 43% | +8.8% | -6.6% | 1.02 | +0.08% | -45.7% | -10.7% | 34% | 8% | 5.2 d |
| 34 | 6 Pullback in sterke trend | ruimte >= 10% tot sterke weerstand | train | 3136 | 43% | +8.9% | -6.9% | 0.99 | -0.06% | -47.8% | -6.9% | 35% | 10% | 5.1 d |
| 34 | 6 Pullback in sterke trend | ruimte >= 10% tot sterke weerstand | test | 3160 | 43% | +9.0% | -6.9% | 1.00 | -0.00% | -62.6% | -21.1% | 35% | 10% | 5.2 d |
| 35 | 6 Pullback in sterke trend | RS top 20% | train | 2166 | 41% | +9.2% | -7.0% | 0.91 | -0.37% | -54.5% | -8.6% | 35% | 10% | 4.7 d |
| 35 | 6 Pullback in sterke trend | RS top 20% | test | 2008 | 45% | +9.4% | -7.3% | 1.04 | +0.14% | -43.9% | -11.7% | 38% | 12% | 4.7 d |
| 36 | 6 Pullback in sterke trend | volume >= 1.5x op signaaldag | train | 793 | 44% | +8.2% | -6.5% | 1.00 | -0.00% | -27.3% | -1.4% | 32% | 6% | 5.3 d |
| 36 | 6 Pullback in sterke trend | volume >= 1.5x op signaaldag | test | 752 | 45% | +8.7% | -6.7% | 1.05 | +0.18% | -34.7% | -3.6% | 35% | 8% | 5.1 d |
| 37 | 6 Pullback in sterke trend | geen earnings in de houdtijd | train | 4279 | 41% | +8.6% | -6.5% | 0.93 | -0.27% | -68.3% | -12.6% | 32% | 7% | 5.1 d |
| 37 | 6 Pullback in sterke trend | geen earnings in de houdtijd | test | 4262 | 42% | +8.6% | -6.5% | 0.96 | -0.15% | -65.9% | -22.6% | 32% | 7% | 5.2 d |
| 38 | 6 Pullback in sterke trend | ruimte >= 10% tot sterke weerstand + volume >= 1.5x op signaaldag | train | 571 | 43% | +8.2% | -6.6% | 0.91 | -0.32% | -31.0% | -3.1% | 32% | 8% | 5.4 d |
| 38 | 6 Pullback in sterke trend | ruimte >= 10% tot sterke weerstand + volume >= 1.5x op signaaldag | test | 543 | 46% | +8.9% | -7.0% | 1.08 | +0.30% | -29.1% | -1.4% | 37% | 10% | 5.2 d |
| 39 | 7 Squeeze breakout (TTM) | geen filters | train | 1190 | 42% | +7.8% | -7.6% | 0.75 | -1.08% | -66.7% | -11.2% | 30% | 5% | 6.3 d |
| 39 | 7 Squeeze breakout (TTM) | geen filters | test | 1067 | 45% | +8.0% | -7.4% | 0.90 | -0.41% | -47.0% | -11.1% | 33% | 5% | 6.0 d |
| 40 | 7 Squeeze breakout (TTM) | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 832 | 42% | +7.9% | -7.5% | 0.77 | -1.00% | -57.7% | -9.4% | 30% | 6% | 6.1 d |
| 40 | 7 Squeeze breakout (TTM) | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 820 | 44% | +8.1% | -7.5% | 0.83 | -0.70% | -46.8% | -11.4% | 32% | 5% | 5.9 d |
| 41 | 7 Squeeze breakout (TTM) | ruimte >= 10% tot sterke weerstand | train | 556 | 39% | +8.3% | -7.9% | 0.68 | -1.54% | -59.6% | -9.3% | 30% | 8% | 6.1 d |
| 41 | 7 Squeeze breakout (TTM) | ruimte >= 10% tot sterke weerstand | test | 468 | 44% | +8.4% | -7.7% | 0.85 | -0.64% | -44.0% | -9.3% | 32% | 8% | 6.0 d |
| 42 | 7 Squeeze breakout (TTM) | RS top 20% | train | 282 | 46% | +7.3% | -7.8% | 0.79 | -0.89% | -30.9% | -3.2% | 33% | 5% | 5.9 d |
| 42 | 7 Squeeze breakout (TTM) | RS top 20% | test | 296 | 45% | +8.2% | -7.8% | 0.84 | -0.69% | -31.1% | -7.8% | 34% | 7% | 5.5 d |
| 43 | 7 Squeeze breakout (TTM) | volume >= 1.5x op signaaldag | train | 330 | 39% | +8.1% | -7.7% | 0.68 | -1.49% | -40.8% | -5.3% | 31% | 7% | 5.7 d |
| 43 | 7 Squeeze breakout (TTM) | volume >= 1.5x op signaaldag | test | 334 | 40% | +8.0% | -7.6% | 0.69 | -1.44% | -48.4% | -13.6% | 30% | 5% | 5.3 d |
| 44 | 7 Squeeze breakout (TTM) | geen earnings in de houdtijd | train | 1067 | 42% | +7.7% | -7.6% | 0.74 | -1.14% | -65.3% | -10.8% | 29% | 5% | 6.2 d |
| 44 | 7 Squeeze breakout (TTM) | geen earnings in de houdtijd | test | 959 | 46% | +7.7% | -7.3% | 0.91 | -0.37% | -48.9% | -10.6% | 33% | 4% | 6.1 d |
| 45 | 7 Squeeze breakout (TTM) | marktregime (SPY > SMA50, EMA20 > EMA50) + RS top 20% | train | 171 | 48% | +7.5% | -7.7% | 0.89 | -0.43% | -14.5% | -1.1% | 35% | 6% | 5.5 d |
| 45 | 7 Squeeze breakout (TTM) | marktregime (SPY > SMA50, EMA20 > EMA50) + RS top 20% | test | 195 | 43% | +8.2% | -7.9% | 0.76 | -1.08% | -22.5% | -5.9% | 34% | 7% | 5.2 d |
| 46 | 8 Inside bar / NR7 aan S/R | geen filters | train | 6139 | 42% | +8.4% | -6.6% | 0.91 | -0.35% | -79.1% | -17.1% | 31% | 6% | 5.7 d |
| 46 | 8 Inside bar / NR7 aan S/R | geen filters | test | 4645 | 43% | +8.4% | -6.7% | 0.95 | -0.21% | -51.8% | -15.9% | 30% | 6% | 5.8 d |
| 47 | 8 Inside bar / NR7 aan S/R | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 3624 | 39% | +8.3% | -6.6% | 0.81 | -0.77% | -79.8% | -17.4% | 28% | 6% | 5.6 d |
| 47 | 8 Inside bar / NR7 aan S/R | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 3395 | 40% | +8.5% | -6.7% | 0.84 | -0.62% | -52.1% | -16.5% | 29% | 6% | 5.6 d |
| 48 | 8 Inside bar / NR7 aan S/R | ruimte >= 10% tot sterke weerstand | train | 2972 | 42% | +8.8% | -7.1% | 0.89 | -0.44% | -71.7% | -13.7% | 33% | 10% | 5.6 d |
| 48 | 8 Inside bar / NR7 aan S/R | ruimte >= 10% tot sterke weerstand | test | 2126 | 42% | +8.9% | -7.2% | 0.88 | -0.50% | -49.5% | -14.8% | 31% | 10% | 5.7 d |
| 49 | 8 Inside bar / NR7 aan S/R | RS top 20% | train | 1266 | 43% | +8.9% | -7.1% | 0.93 | -0.29% | -42.8% | -5.9% | 34% | 8% | 5.1 d |
| 49 | 8 Inside bar / NR7 aan S/R | RS top 20% | test | 944 | 43% | +8.9% | -7.6% | 0.89 | -0.50% | -40.4% | -12.9% | 34% | 9% | 5.1 d |
| 50 | 8 Inside bar / NR7 aan S/R | volume >= 1.5x op signaaldag | train | 765 | 44% | +8.7% | -7.1% | 0.96 | -0.14% | -25.1% | -2.0% | 35% | 10% | 5.1 d |
| 50 | 8 Inside bar / NR7 aan S/R | volume >= 1.5x op signaaldag | test | 572 | 41% | +9.9% | -7.2% | 0.95 | -0.22% | -27.7% | -2.9% | 34% | 9% | 5.2 d |
| 51 | 8 Inside bar / NR7 aan S/R | geen earnings in de houdtijd | train | 5650 | 41% | +8.2% | -6.6% | 0.87 | -0.48% | -73.3% | -14.8% | 30% | 6% | 5.7 d |
| 51 | 8 Inside bar / NR7 aan S/R | geen earnings in de houdtijd | test | 4219 | 42% | +8.1% | -6.5% | 0.89 | -0.40% | -54.7% | -18.6% | 29% | 5% | 5.8 d |
| 52 | 8 Inside bar / NR7 aan S/R | RS top 20% + volume >= 1.5x op signaaldag | train | 170 | 43% | +8.9% | -7.5% | 0.90 | -0.43% | -14.0% | -1.0% | 35% | 12% | 4.5 d |
| 52 | 8 Inside bar / NR7 aan S/R | RS top 20% + volume >= 1.5x op signaaldag | test | 132 | 47% | +10.1% | -7.8% | 1.14 | +0.59% | -7.3% | 2.1% | 42% | 15% | 4.5 d |
| 53 | 9 Anchored VWAP reclaim | geen filters | train | 18736 | 47% | +8.3% | -7.3% | 1.02 | +0.09% | -68.5% | -9.8% | 36% | 7% | 5.8 d |
| 53 | 9 Anchored VWAP reclaim | geen filters | test | 13711 | 47% | +8.4% | -7.2% | 1.02 | +0.08% | -63.4% | -16.6% | 34% | 6% | 5.8 d |
| 54 | 9 Anchored VWAP reclaim | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 8482 | 43% | +8.2% | -7.1% | 0.86 | -0.56% | -71.2% | -13.5% | 31% | 6% | 6.0 d |
| 54 | 9 Anchored VWAP reclaim | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 8912 | 43% | +8.6% | -7.2% | 0.90 | -0.40% | -51.0% | -11.2% | 33% | 6% | 5.6 d |
| 55 | 9 Anchored VWAP reclaim | ruimte >= 10% tot sterke weerstand | train | 9813 | 47% | +8.7% | -7.6% | 1.03 | +0.11% | -69.1% | -7.3% | 39% | 11% | 5.7 d |
| 55 | 9 Anchored VWAP reclaim | ruimte >= 10% tot sterke weerstand | test | 6701 | 46% | +8.7% | -7.5% | 1.00 | +0.01% | -67.4% | -21.9% | 35% | 9% | 5.8 d |
| 56 | 9 Anchored VWAP reclaim | RS top 20% | train | 2623 | 46% | +8.7% | -7.6% | 0.98 | -0.08% | -65.0% | -7.7% | 37% | 7% | 5.3 d |
| 56 | 9 Anchored VWAP reclaim | RS top 20% | test | 1913 | 46% | +9.0% | -7.9% | 0.99 | -0.06% | -66.7% | -20.5% | 38% | 9% | 4.8 d |
| 57 | 9 Anchored VWAP reclaim | volume >= 1.5x op signaaldag | train | 4173 | 47% | +8.3% | -7.6% | 0.95 | -0.19% | -52.6% | -3.2% | 37% | 8% | 5.2 d |
| 57 | 9 Anchored VWAP reclaim | volume >= 1.5x op signaaldag | test | 3179 | 46% | +8.4% | -7.5% | 0.94 | -0.23% | -62.3% | -19.4% | 33% | 6% | 5.4 d |
| 58 | 9 Anchored VWAP reclaim | geen earnings in de houdtijd | train | 17354 | 47% | +8.2% | -7.2% | 1.00 | -0.01% | -76.1% | -14.3% | 35% | 6% | 5.8 d |
| 58 | 9 Anchored VWAP reclaim | geen earnings in de houdtijd | test | 12463 | 46% | +8.2% | -7.0% | 0.99 | -0.03% | -62.0% | -18.1% | 33% | 5% | 5.9 d |
| 59 | 10 RS leader breakout | geen filters | train | 814 | 39% | +8.4% | -7.6% | 0.72 | -1.31% | -63.0% | -10.9% | 28% | 11% | 5.0 d |
| 59 | 10 RS leader breakout | geen filters | test | 606 | 41% | +9.4% | -8.1% | 0.81 | -0.92% | -51.8% | -16.7% | 33% | 15% | 4.4 d |
| 60 | 10 RS leader breakout | marktregime (SPY > SMA50, EMA20 > EMA50) | train | 470 | 37% | +9.0% | -7.8% | 0.67 | -1.65% | -52.1% | -8.3% | 29% | 14% | 4.2 d |
| 60 | 10 RS leader breakout | marktregime (SPY > SMA50, EMA20 > EMA50) | test | 439 | 38% | +9.9% | -8.3% | 0.75 | -1.30% | -47.2% | -15.5% | 33% | 16% | 4.0 d |
| 61 | 10 RS leader breakout | ruimte >= 10% tot sterke weerstand | train | 684 | 38% | +8.6% | -7.7% | 0.69 | -1.50% | -62.2% | -10.9% | 28% | 13% | 4.8 d |
| 61 | 10 RS leader breakout | ruimte >= 10% tot sterke weerstand | test | 554 | 40% | +9.5% | -8.1% | 0.79 | -1.01% | -50.5% | -15.7% | 33% | 16% | 4.3 d |
| 62 | 10 RS leader breakout | RS top 20% | train | 585 | 41% | +8.5% | -7.6% | 0.77 | -1.04% | -48.6% | -6.9% | 30% | 12% | 4.8 d |
| 62 | 10 RS leader breakout | RS top 20% | test | 462 | 39% | +9.7% | -8.3% | 0.76 | -1.19% | -47.1% | -15.1% | 33% | 16% | 4.0 d |
| 63 | 10 RS leader breakout | volume >= 1.5x op signaaldag | train | 814 | 39% | +8.4% | -7.6% | 0.72 | -1.31% | -63.0% | -10.9% | 28% | 11% | 5.0 d |
| 63 | 10 RS leader breakout | volume >= 1.5x op signaaldag | test | 606 | 41% | +9.4% | -8.1% | 0.81 | -0.92% | -51.8% | -16.7% | 33% | 15% | 4.4 d |
| 64 | 10 RS leader breakout | geen earnings in de houdtijd | train | 765 | 39% | +8.3% | -7.6% | 0.69 | -1.44% | -65.0% | -11.4% | 27% | 10% | 5.0 d |
| 64 | 10 RS leader breakout | geen earnings in de houdtijd | test | 572 | 40% | +9.3% | -8.1% | 0.77 | -1.11% | -54.3% | -18.1% | 33% | 15% | 4.4 d |

## Ranglijst (out-of-sample 2023-04-07 .. 2026-10-23, beste configuratie per strategie)

| strategie                   | filters (gekozen op train)   |   test trades | winrate   |   PF | expectancy   | % +10%   | % +20%   | max DD   | CAGR   | houdtijd   | oordeel   |
|:----------------------------|:-----------------------------|--------------:|:----------|-----:|:-------------|:---------|:---------|:---------|:-------|:-----------|:----------|
| 6 Pullback in sterke trend  | vol_surge                    |           752 | 45%       | 1.05 | +0.18%       | 35%      | 8%       | -34.7%   | -3.6%  | 5.1 d      | verworpen |
| 2 Qullamaggie breakout      | geen                         |          1505 | 48%       | 1.01 | +0.03%       | 33%      | 8%       | -38.1%   | -1.4%  | 6.4 d      | verworpen |
| 9 Anchored VWAP reclaim     | room10                       |          6701 | 46%       | 1    | +0.01%       | 35%      | 9%       | -67.4%   | -21.9% | 5.8 d      | verworpen |
| 4 S/R flip retest           | rs_top20                     |          3462 | 44%       | 0.98 | -0.08%       | 36%      | 8%       | -54.1%   | -13.2% | 4.5 d      | verworpen |
| 8 Inside bar / NR7 aan S/R  | vol_surge                    |           572 | 41%       | 0.95 | -0.22%       | 34%      | 9%       | -27.7%   | -2.9%  | 5.2 d      | verworpen |
| 1 VCP (Minervini)           | room10                       |           162 | 45%       | 0.94 | -0.26%       | 31%      | 10%      | -12.2%   | -1.5%  | 6.2 d      | verworpen |
| 5 Failed breakdown / spring | vol_surge                    |           978 | 42%       | 0.79 | -0.91%       | 30%      | 5%       | -61.0%   | -21.9% | 5.2 d      | verworpen |
| 7 Squeeze breakout (TTM)    | regime, rs_top20             |           195 | 43%       | 0.76 | -1.08%       | 34%      | 7%       | -22.5%   | -5.9%  | 5.2 d      | verworpen |
| 10 RS leader breakout       | rs_top20                     |           462 | 39%       | 0.76 | -1.19%       | 33%      | 16%      | -47.1%   | -15.1% | 4.0 d      | verworpen |
| 3 Episodic pivot            | regime                       |           360 | 36%       | 0.59 | -2.13%       | 31%      | 9%       | -56.6%   | -18.9% | 3.8 d      | verworpen |

## Controle en combinatie (indicator_lab/week/extra.py)

| run | strategie | instellingen | set | trades | winrate | gem. winst | gem. verlies | PF | expectancy | max DD (rekening) | CAGR (rekening) | % +10% geraakt | % +20% geraakt | gem. houdtijd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| – | 0 Willekeurige instap (controle) | elke 21e handelsdag, zelfde exits | train | 21574 | 39% | +8.3% | -6.7% | 0.80 | -0.81% | -85.3% | -19.0% | 30% | 5% | 5.3 d |
| – | 0 Willekeurige instap (controle) | elke 21e handelsdag, zelfde exits | test | 17209 | 42% | +8.4% | -6.6% | 0.93 | -0.28% | -53.6% | -10.4% | 31% | 6% | 5.4 d |
| – | Combinatie top 3 op train: 9, 6, 5 | 9: room10; 6: vol_surge; 5: vol_surge | train | 11446 | 47% | +8.6% | -7.5% | 1.02 | +0.09% | -67.3% | -9.0% | 38% | 10% | 5.7 d |
| – | Combinatie top 3 op train: 9, 6, 5 | 9: room10; 6: vol_surge; 5: vol_surge | test | 8232 | 46% | +8.7% | -7.5% | 0.98 | -0.07% | -76.3% | -31.1% | 35% | 8% | 5.7 d |

Combinatie test-PF 0.98 vs beste losse strategie 1.05: **combinatie NIET beter, niet gebruiken**.

## Conclusie (eerlijk)
- **Geen van de 10 strategieën haalt het doel.** Geen enkele heeft out-of-sample een profit factor > 1,3; alle 10 zijn
  verworpen. Het dichtst bij: 6 pullback in trend + volume surge (test-PF 1,05, +0,18% per trade) en 2 Qullamaggie
  (PF 1,01). De combinatie van de top 3 (gekozen op train) is niet beter (PF 0,98).
- **Wat realistisch is binnen 1 week** (universum ADR > 4%, > $20M/dag, deze exits): ongeveer 1 op 3 trades raakt
  +10% en ongeveer 1 op 12 raakt +20% vóór de stop. Willekeurige instappen halen al 31% en 6%: het grootste deel van
  die kans komt van de beweeglijkheid van het aandeel, niet van de setup. Gemiddelde winnaar ~+8,5%, gemiddelde
  verliezer ~-7%, winrate 40-48%: dat telt op tot ongeveer nul per trade na kosten.
- **Gemiddelde trade overschat de rekening:** bij setup 6 vielen op volle dagen (6% van de dagen 10 posities) juist de
  grootste winnaars weg; de genomen trades gemiddeld -0,08% in plaats van +0,18%.
- Filters (regime, RS, ruimte >= 10%, geen earnings) verbeterden niets structureel; "geen earnings in de houdtijd"
  maakte het overal iets slechter (de grote uitschieters zitten vaak rond earnings).

## Zoektocht naar 70% winrate (indicator_lab/week/winrate.py)

Eén vast winstdoel voor de hele positie, verder dezelfde stop, tijdstop (10 dagen), kosten en universum; geen filters.

| strategie                        | doel   |   train trades | train winrate   |   train PF | train per trade   |   test trades | test winrate   |   test PF | test per trade   | voldoet (test: >= 70% winrate én PF > 1,3)   |
|:---------------------------------|:-------|---------------:|:----------------|-----------:|:------------------|--------------:|:---------------|----------:|:-----------------|:---------------------------------------------|
| 0 Willekeurige instap (controle) | +3%    |          21574 | 64%             |       0.7  | -0.74%            |         17209 | 65%            |      0.78 | -0.52%           | –                                            |
| 0 Willekeurige instap (controle) | +5%    |          21574 | 53%             |       0.77 | -0.76%            |         17209 | 55%            |      0.86 | -0.44%           | –                                            |
| 0 Willekeurige instap (controle) | +10%   |          21574 | 39%             |       0.8  | -0.81%            |         17209 | 42%            |      0.93 | -0.28%           | –                                            |
| 1 VCP (Minervini)                | +3%    |            253 | 65%             |       0.61 | -1.10%            |           305 | 67%            |      0.66 | -0.92%           | nee                                          |
| 1 VCP (Minervini)                | +5%    |            252 | 53%             |       0.66 | -1.22%            |           305 | 57%            |      0.77 | -0.77%           | nee                                          |
| 1 VCP (Minervini)                | +10%   |            251 | 41%             |       0.73 | -1.19%            |           302 | 45%            |      0.82 | -0.75%           | nee                                          |
| 2 Qullamaggie breakout           | +3%    |           1712 | 71%             |       0.81 | -0.44%            |          1637 | 71%            |      0.83 | -0.40%           | nee                                          |
| 2 Qullamaggie breakout           | +5%    |           1684 | 59%             |       0.89 | -0.34%            |          1605 | 61%            |      0.96 | -0.13%           | nee                                          |
| 2 Qullamaggie breakout           | +10%   |           1612 | 46%             |       0.89 | -0.42%            |          1527 | 48%            |      0.98 | -0.07%           | nee                                          |
| 3 Episodic pivot                 | +3%    |            431 | 50%             |       0.33 | -2.68%            |           459 | 49%            |      0.32 | -2.82%           | nee                                          |
| 3 Episodic pivot                 | +5%    |            430 | 43%             |       0.45 | -2.46%            |           459 | 44%            |      0.43 | -2.61%           | nee                                          |
| 3 Episodic pivot                 | +10%   |            429 | 34%             |       0.56 | -2.27%            |           459 | 35%            |      0.59 | -2.13%           | nee                                          |
| 4 S/R flip retest                | +3%    |          26666 | 65%             |       0.79 | -0.46%            |         21571 | 65%            |      0.8  | -0.46%           | nee                                          |
| 4 S/R flip retest                | +5%    |          24034 | 54%             |       0.87 | -0.39%            |         19624 | 55%            |      0.89 | -0.33%           | nee                                          |
| 4 S/R flip retest                | +10%   |          21114 | 41%             |       0.91 | -0.32%            |         17247 | 42%            |      0.97 | -0.13%           | nee                                          |
| 5 Failed breakdown / spring      | +3%    |           5913 | 70%             |       0.87 | -0.28%            |          4888 | 67%            |      0.78 | -0.53%           | nee                                          |
| 5 Failed breakdown / spring      | +5%    |           5729 | 59%             |       0.94 | -0.19%            |          4781 | 57%            |      0.88 | -0.37%           | nee                                          |
| 5 Failed breakdown / spring      | +10%   |           5499 | 45%             |       0.95 | -0.18%            |          4617 | 44%            |      0.95 | -0.20%           | nee                                          |
| 6 Pullback in sterke trend       | +3%    |           5100 | 66%             |       0.78 | -0.50%            |          5153 | 67%            |      0.81 | -0.44%           | nee                                          |
| 6 Pullback in sterke trend       | +5%    |           4832 | 55%             |       0.88 | -0.35%            |          4834 | 56%            |      0.92 | -0.24%           | nee                                          |
| 6 Pullback in sterke trend       | +10%   |           4638 | 42%             |       0.96 | -0.13%            |          4603 | 43%            |      1    | +0.01%           | nee                                          |
| 7 Squeeze breakout (TTM)         | +3%    |           1190 | 65%             |       0.63 | -1.06%            |          1068 | 72%            |      0.86 | -0.32%           | nee                                          |
| 7 Squeeze breakout (TTM)         | +5%    |           1190 | 56%             |       0.75 | -0.85%            |          1068 | 60%            |      0.93 | -0.21%           | nee                                          |
| 7 Squeeze breakout (TTM)         | +10%   |           1190 | 43%             |       0.76 | -1.05%            |          1067 | 46%            |      0.92 | -0.34%           | nee                                          |
| 8 Inside bar / NR7 aan S/R       | +3%    |           6368 | 67%             |       0.79 | -0.48%            |          4821 | 67%            |      0.84 | -0.37%           | nee                                          |
| 8 Inside bar / NR7 aan S/R       | +5%    |           6296 | 55%             |       0.86 | -0.41%            |          4756 | 56%            |      0.89 | -0.33%           | nee                                          |
| 8 Inside bar / NR7 aan S/R       | +10%   |           6172 | 42%             |       0.91 | -0.36%            |          4667 | 43%            |      0.93 | -0.25%           | nee                                          |
| 9 Anchored VWAP reclaim          | +3%    |          21329 | 72%             |       0.91 | -0.19%            |         15560 | 70%            |      0.85 | -0.34%           | nee                                          |
| 9 Anchored VWAP reclaim          | +5%    |          20104 | 61%             |       0.98 | -0.07%            |         14661 | 59%            |      0.94 | -0.17%           | nee                                          |
| 9 Anchored VWAP reclaim          | +10%   |          18879 | 47%             |       1.03 | +0.12%            |         13804 | 47%            |      1.01 | +0.05%           | nee                                          |
| 10 RS leader breakout            | +3%    |           1001 | 64%             |       0.59 | -1.20%            |           777 | 62%            |      0.52 | -1.52%           | nee                                          |
| 10 RS leader breakout            | +5%    |            960 | 55%             |       0.71 | -1.03%            |           738 | 53%            |      0.64 | -1.38%           | nee                                          |
| 10 RS leader breakout            | +10%   |            861 | 40%             |       0.7  | -1.39%            |           663 | 41%            |      0.75 | -1.22%           | nee                                          |

## Winrate-studie stap 1 (indicator_lab/week/mfe.py, rapport: results/step1_mfe.md)
Kosten 0,05%/kant + 2 ticks; vast doel (max +10%, hele positie eruit); 10 setups x 4 houdtijden x 6 doelen = 240
combinaties (x train/test), elk vergeleken met 20 willekeurige runs op dezelfde datums.
- >= 70% winrate op test kan alleen met een doel van +2% of +3%; dan is de profit factor 0,63-0,93 (verliesgevend) en
  halen willekeurige instappen hetzelfde (66-74%). Eis 3 (10 procentpunt beter dan random) faalt overal.
- Hoogste test-PF van alle 240 combinaties: 1,08 (6 pullback, 20 dagen, +10%; winrate 42%). Niets haalt PF >= 1,3.
- Mediane MFE / MAE in 10 dagen: +5,5..+6,3% / -4,6..-8,0%: de koers beweegt ongeveer even ver mee als tegen.

## Winrate-studie stap 2 en 3 (indicator_lab/week/variants.py; results/step2_stops.md, step3_exits.md)
Stap 2: 10 setups x 10 stops (standaard, sterke support >= 1,5, 1/1,5/2 ATR; max 5% of 8%) x 4 doelen = 400
combinaties. Stap 3: 10 setups x 81 exits (T1 +3/+5/+7%, 50/70/100% verkopen, rest op +10% / EMA10-trail / 2 ATR-trail /
tijd, 10/15/20 dagen; alles max +10%) = 810 combinaties. Totaal winrate-studie tot nu toe: 240 + 400 + 810 = 1450.
- Beste per setup (gekozen op train) haalt op test 39-61% winrate en PF 0,54-1,07; hoogste: 6 pullback (stop 2 ATR,
  max 8%; 50% op +7%, rest 2 ATR-trail tot +10%, 20 dagen): 56% winrate, PF 1,07, +0,26% per trade, random 54% / 1,01.
- Geen enkele variant haalt alle eisen (70% winrate, PF >= 1,3, 10 pp boven random): 0 van 1450.

## Winrate-studie stap 4 en 5 (indicator_lab/week/filters.py; results/step4_filters.md)

12 extra combinaties (totaal 1462).

| variant     |   test trades | winrate   |   PF |   PF zonder top 5% | exp.   |   exp. (R) | houdtijd   | max DD (10x10%)   | random winrate / PF   | train winrate / PF   | jaren met PF > 1   | oordeel                                                                                                                                                          |
|:------------|--------------:|:----------|-----:|-------------------:|:-------|-----------:|:-----------|:------------------|:----------------------|:---------------------|:-------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| setup 2, F2 |          1191 | 60%       | 0.96 |               0.84 | -0.11% |      -0.01 | 4.4 d      | -26.9%            | 55% / 0.94            | 61% / 0.99           | 6 / 12             | AFGEWEZEN: winrate 60% < 70%; PF 0.96 < 1,3; PF zonder top 5% 0.84 < 1,2; winrate maar +5 pp vs random; PF maar +0.03 vs random; t = -0.6 < Bonferroni-grens 4.1 |
| setup 6, F4 |          1415 | 56%       | 1.06 |               0.88 | +0.22% |       0.03 | 6.7 d      | -34.0%            | 55% / 1.02            | 57% / 1.13           | 8 / 12             | AFGEWEZEN: winrate 56% < 70%; PF 1.06 < 1,3; PF zonder top 5% 0.88 < 1,2; winrate maar +1 pp vs random; PF maar +0.04 vs random; t = 1.0 < Bonferroni-grens 4.1  |

## Eindoordeel winrate-studie
Na 1462 combinaties (stap 1-5) haalt geen enkele variant de eisen. Hoogste test-PF: 1,07 (6 pullback, 56% winrate);
hoogste test-winrate bij een op train gekozen variant: 61% (2 Qullamaggie, PF 0,98). 70% winrate komt alleen voor bij
doelen van +2/+3%, en dan is de PF < 1 en is willekeurig instappen even goed. Geen variant haalt PF >= 1,3, dus er is
geen winrate-niveau dat eisen 2-5 haalt. build.py en week_swing.pine blijven daarom ongewijzigd (alleen bij een
goedgekeurde variant zouden de defaults veranderen).

## Post-earnings gap (setup 11), stap 1-4: 54 varianten — zie results/pead_week.md
Uitkomst (test 2023-2026): hoogste PF 1,19 (ADR > 2%, EPS-verrassing > 0, exit A-EMA20, 40 dagen; 604 trades, winrate
30%, +0,66%/trade, train-PF 1,16); geen variant haalt PF >= 1,3 en PF zonder top 5% is overal < 1 (max 0,95).
EPS-verrassing > 0 verbetert de PF met ~0,1-0,15; ADR > 4% is het slechtst (tegenwind van de beweeglijkste aandelen).
Let op: EPS-data voor 1735 van 3044 aandelen met earningsdatums (ophalen liep nog); random-stop ligt dichter bij de
instap (gewone dag-low i.p.v. gap-dag-low), waardoor random een lagere winrate heeft.

## Controle gap-setup zonder earnings (results/pead_nonearn.md): 27 varianten x 2 groepen
Uitkomst: gaps ZONDER earnings verliezen in alle 27 varianten (test-PF 0,52-0,82, -1,1 tot -3,8% per trade, max
daling -86 tot -98%); dezelfde gaps MET earnings zitten rond quitte (PF 0,81-1,06). De cijfers zijn dus de motor van
het effect, niet de gap zelf: een gap zonder nieuws is eerder een valkuil.

## Post-earnings gap stap 5 (results/pead_improve.md): 5 extra varianten; eindvariant test PF 1.03, exp +0.12%, 656 trades, random-PF 0.85: niet goedgekeurd
Correctie met volledige EPS-data (99% van de events): de eerdere PF 1,19 voor "EPS-verrassing > 0" (stap 1-4) was een
artefact van de onvolledige EPS-dekking (vooral bekende namen). Met volledige data: ADR > 2%, EMA20-trail, 40 dagen:
"any" PF 1,06 (test), "verrassing > 0" PF 1,00. Stap 5: verbeteringen tilden train-PF naar 1,28 maar test zakte naar
1,03 (t = 0,22): overfit op train. Niet goedgekeurd; build.py en week_swing.pine blijven ongewijzigd.

## Swing v4.2-ronde (indicator_lab/swing7/reports): 3 regels uit eerder onderzoek op v4.1
Ontwikkeling (1260 aandelen): R1 SPY > SMA200 verworpen, R3 geen cijfers binnen 5 sessies verworpen, R2 1-jaars ATR% <= 5
geaccepteerd (MAR 0,12 vs -0,02). Enige holdout-run (1304 aandelen): v4.2 MAR 0,08 vs v4.1 0,11, CAGR 2,5% vs 3,4%
(SPY 13,2%): NIET goedgekeurd. v4.1 blijft de versie; swing_v4_2.pine heeft beide filters standaard uit.
