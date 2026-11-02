# SPY Twee Levels — backtest van de echte indicatorregels

## Conclusie

1. **Over deze 60 dagen werkt het licht positief:** 36 trades (19 CALL, 17 PUT), doel gehaald in 44%, 75% winnaars
   (de rest sluit vaak met een kleine winst op het slot), gemiddeld +0,10% per trade bruto; slechtste trade -1,01%.
   Met een stop 1:1 iets minder: +0,08% per trade, 19% uitgestopt.
2. **Maar dit is geen bewijs:** 36 trades is heel weinig (t = 2,14 is net boven de 2, en met enkele varianten getest is
   dat niet genoeg). En dit is **dezelfde periode** als waarop de indicator gemaakt en getest is (header: 7/8-30/10/2026),
   dus in-sample.
3. **Kosten:** op het aandeel SPY zelf blijft +0,10% bruto na een kleine commissie waarschijnlijk positief; met 0DTE-opties
   (spread + tijdswaarde) is dat zeer onzeker.
4. **Wat nodig is:** minstens 1-2 jaar 5-minutendata (betaald, bv. Polygon, Alpha Vantage premium) om op data te testen
   die niet gebruikt is, of de indicator vanaf nu een paar maanden live op papier volgen.


Regels: docstring van `indicator_lab/spy_twee_levels.py`. Data: Yahoo 5-minutenbars SPY 2026-08-10 .. 2026-11-02 (gratis intraday-geschiedenis is beperkt tot ~60 dagen). Bruto, zonder optiekosten.

| variant                        |   trades | CALL / PUT   | doel gehaald   | stop   | winnaars   | gem./trade   | slechtste   | beste   |    t |
|:-------------------------------|---------:|:-------------|:---------------|:-------|:-----------|:-------------|:------------|:--------|-----:|
| zoals de indicator (geen stop) |       36 | 19 / 17      | 44.4%          | 0%     | 75%        | +0.104%      | -1.01%      | +0.45%  | 2.14 |
| met stop 1:1                   |       36 | 19 / 17      | 41.7%          | 19%    | 72%        | +0.083%      | -0.83%      | +0.45%  | 1.74 |
