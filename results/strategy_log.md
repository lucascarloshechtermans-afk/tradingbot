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
