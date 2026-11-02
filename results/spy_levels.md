# SPY: raken trades vanaf de support-levels hun doel?

## Conclusie

1. **Het doel (eerstvolgende weerstand) wordt in ~40% van de trades geraakt**, de stop in ~53%; in 6-8% loopt de tijd af.
2. **Dat is iets beter dan nodig om quitte te spelen** (break-even 42% in 1995-2014, 34% in 2015-2026): gemiddeld +0,07% en
   +0,41% per trade (gem. +0,17 en +0,64 R), met kosten 0,1% per kant.
3. **Maar niet beter dan gewoon SPY vasthouden:** SPY steeg over dezelfde houdduur (11-12 dagen) vanaf een willekeurige dag
   gemiddeld +0,46% (1995-2014) en +0,68% (2015-2026) — meer dan de support-trades. De t-waarde van 2015-2026 (2,95) is te
   optimistisch omdat signalen op opeenvolgende dagen overlappen.
4. **De controle "elke dag"** raakt vaker het doel (62%) omdat de weerstand dan dichterbij ligt, maar verdient bijna niets:
   hoe vaak je je doel raakt zegt weinig zonder de afstand tot doel en stop.
5. **Eerlijk oordeel:** de levels werken op SPY ongeveer zoals je verwacht (doel vaker geraakt dan break-even), maar trades
   vanaf support verslaan het simpelweg vasthouden van SPY niet.


Regels: docstring van `indicator_lab/spy_levels.py` (vooraf gecommit). Data SPY 1993-01-29 .. 2026-10-30 (gecorrigeerd voor dividend). Doel = eerstvolgende weerstand, stop onder de support-zone (max 8%), max 60 dagen, kosten 0,1% per kant. Break-even % = hoe vaak het doel minstens geraakt moet worden om quitte te spelen.

| periode   | variant               |   trades | doel geraakt   | stop geraakt   | tijd (60 d)   | break-even %   | winrate   | gem./trade   |   gem. R |   gem. dagen |
|:----------|:----------------------|---------:|:---------------|:---------------|:--------------|:---------------|:----------|:-------------|---------:|-------------:|
| 1995-2014 | aan support (signaal) |      651 | 39%            | 53%            | 8%            | 42%            | 47%       | +0.07%       |     0.17 |           11 |
| 1995-2014 | elke dag (controle)   |     3370 | 62%            | 36%            | 2%            | 62%            | 64%       | -0.11%       |    -0.04 |            4 |
| 2015-2026 | aan support (signaal) |      395 | 40%            | 54%            | 6%            | 34%            | 46%       | +0.41%       |     0.64 |           12 |
| 2015-2026 | elke dag (controle)   |     1895 | 62%            | 37%            | 1%            | 59%            | 63%       | +0.06%       |     0.06 |            5 |
