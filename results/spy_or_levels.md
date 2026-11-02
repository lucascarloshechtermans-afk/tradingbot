# SPY 2 Levels (opening range 9:30-9:45): raken de trades hun doel?

## Conclusie (60 handelsdagen: klein, dus voorzichtig)

1. **Het doel wordt in ~60% van de trades dezelfde dag geraakt** (CALL 62%, PUT 60%); het level zelf wordt op 75-88% van
   de dagen geraakt.
2. **Maar de winst is bijna nul:** gemiddeld +0,04% per trade bruto. Als het doel niet geraakt wordt, verlies je
   gemiddeld 0,17-0,24% (meer dan de winst van ~0,21% als het wel lukt).
3. **De koers gaat eerst flink tegen je in:** gemiddeld 1,3 keer de hele range (0,22-0,24%) voor het doel of het slot.
   Met een stop net achter het level zou je dus vaak uitgestopt worden.
4. **Na kosten** (spread, commissie, of de optiepremie bij calls/puts) blijft er niets over.
5. Voor een betrouwbaar oordeel zijn jaren aan 1-minuutdata nodig (betaald) en de exacte regels van de indicator.


Regels: docstring van `indicator_lab/spy_or_levels.py`. Data: Yahoo 5-minutenbars SPY, 2026-08-10 .. 2026-11-02 (60 handelsdagen; langere intraday-geschiedenis is niet gratis beschikbaar). Geen kosten (bruto).

| kant                                            |   dagen | level geraakt   | doel dezelfde dag geraakt   | gem. resultaat (bruto)   | gem. resultaat als doel NIET geraakt   | gem. max tegenbeweging   | gem. range 9:30-9:45   |
|:------------------------------------------------|--------:|:----------------|:----------------------------|:-------------------------|:---------------------------------------|:-------------------------|:-----------------------|
| CALL (koop aan het lage level, doel hoge level) |      60 | 53 (88%)        | 62%                         | +0.04%                   | -0.24%                                 | -0.24% (-1.3x range)     | 0.21%                  |
| PUT (short aan het hoge level, doel lage level) |      60 | 45 (75%)        | 60%                         | +0.04%                   | -0.17%                                 | -0.22% (-1.3x range)     | 0.21%                  |
