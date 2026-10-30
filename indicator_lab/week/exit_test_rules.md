# Exit-test — vooraf vastgelegde regels

Vraag: zit het probleem van het weekplan (`three_week.py`) in de **uitstap** (+10% en eruit op vrijdag) of in de
**instappen**? Dit bestand is gecommit vóór de eerste run. Na het zien van testresultaten worden deze regels niet meer
veranderd; een nieuw idee komt als aparte hypothese onderaan en draait niet mee in de hoofdtabel.

Code: `indicator_lab/week/exit_test.py`. Rapport: `results/exit_test.md`.

## 1. Vast (gelijk aan three_week.py)
- **Data**: de Swing 20/21-cache (`twenty/data20`), dagbars 2015-01-01 .. 2026-10-23. Dit zijn alleen aandelen die op
  2026-10-23 nog genoteerd waren: **gedelistte aandelen zitten er niet in** (survivorship bias, gunstig voor elke
  long-strategie én voor RND). Het script telt ook hoeveel tickers vóór 2026-09 ophouden en zet dat in het rapport.
- **Universum** op de signaaldag: slot > $5, 50-daagse gemiddelde dollaromzet > $20M, ADR(20) > 4%.
- **Kosten**: 0,05% commissie + $0,02 slippage per kant.
- **Strategieën** (13 + controle): de 10 setups van `build.py` met hun eigen instap (volgende open of buy-stop),
  S11 earnings-gap, S12 = jouw indicator v4.1 (`pine_sim.V41` BUY, volgende open), en RND (willekeurig aandeel uit het
  universum, volgende open) als controle. De vraag noemde "12 strategieën + v4.1 + RND"; three_week.py heeft er
  10 + S11 + S12(v4.1) + RND, en precies die worden gebruikt (afwijking alleen in de telling, niet in de inhoud).
- **Instap-modi**: M1 maandag = alleen instappen op de eerste handelsdag van de week (signalen van de laatste
  handelsdag van de vorige week); M2 doorlopend = instappen op elke dag, wie eerst komt.
- **Stop** (alle exits): `mfe.std_stop` = onder de support - 0,25 ATR, minstens 1 ATR, hooguit 8% onder de instap.
  Zelfde bar: stop eerst. Een open voorbij stop of doel vult op de open.
- **20 runs** per variant; per run een andere willekeurige volgorde bij signalen op dezelfde dag (bij RND ook welk
  aandeel). Gerapporteerd: het gemiddelde over de runs en de spreiding (standaardafwijking van "test gem./week").

## 2. De enige variabele: drie exits
- **(a) Week**: eruit bij +10% (limiet), anders op het slot van de laatste handelsdag van de instapweek.
  Maximaal 3 nieuwe posities per week (huidige regel).
- **(b) Maand**: eruit bij +20% (limiet), anders op het slot van de 20e handelsdag (instapdag = dag 1).
- **(c) Trailing**: geen winstdoel. Stop = max(beginstop, hoogste slot sinds instap - 2 x ATR(14) van die dag),
  na elk slot bijgewerkt en geldig vanaf de volgende dag; maximaal 60 handelsdagen, dan eruit op het slot.
- Bij alle exits: **maximaal 3 posities tegelijk**, elk bij instap 1/3 van de rekeningwaarde van het vorige slot
  (hooguit de beschikbare cash). Een nieuwe positie alleen als er een plek vrij is. Instappen gebeuren op de open,
  uitstappen in de loop van de dag: een plek die vandaag vrijkomt is pas morgen weer bruikbaar.
- Kleine afwijking t.o.v. three_week.py bij (a): daar was elke positie 1/3 van de rekening aan het begin van de week,
  hier 1/3 van de rekeningwaarde van het vorige slot. De rekening wordt dagelijks gewaardeerd op slotkoersen.

## 3. Train / test
- Train = weken t/m 2022-12-31; test = weken vanaf 2023-01-01 t/m 2026-10-23. Eén doorlopende simulatie; posities
  die over de grens lopen tellen in de week waarin hun rendement valt.
- Train dient alleen om per exit x modus de **3 beste strategieën** (op gemiddeld rendement per week, RND niet
  meegeteld) aan te wijzen. Op de test wordt niets gekozen of afgesteld; alle strategieën worden getoond.

## 4. Statistiek
- Weekrendement per strategie = gemiddelde over de 20 runs van het weekrendement van de rekening.
- Verschil met RND (zelfde exit, zelfde modus) en met SPY kopen-en-vasthouden (dividend-gecorrigeerde slotkoersen)
  per testweek; gemiddeld verschil met 95%-interval uit een moving-block bootstrap (blokken van 4 weken,
  10.000 trekkingen, percentielinterval).
- "Beter dan random" / "beter dan SPY" alleen als het **hele** interval boven 0 ligt.
- Aantal vergelijkingen: 13 strategieën x 3 exits x 2 modi = 78 varianten (+ 6 RND-controles); bij zoveel intervallen
  kan er door toeval eens één boven 0 vallen. Dat wordt in het rapport vermeld.

## 5. Rapport
Eén tabel per exit x modus met: strategie | train gem./week | test trades/week | test winrate | test gem./trade |
test gem./week (± sd) | verschil vs RND [95%] | verschil vs SPY [95%] | test CAGR | test max daling |
gem. houdduur (handelsdagen). De 3 op train gekozen strategieën zijn gemarkeerd. Bovenaan maximaal 5 zinnen conclusie.
Geen advies om (papier) te traden, tenzij een strategie in de test aantoonbaar beter is dan SPY.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
