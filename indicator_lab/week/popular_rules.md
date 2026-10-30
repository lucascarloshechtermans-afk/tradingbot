# Populaire strategieën met "+10% en eruit" — vooraf vastgelegde regels

Bron van de strategieën: `results/research_popular_strategies.md`. Code: `indicator_lab/week/popular.py`.
Rapport: `results/popular_strategies.md`. Dit bestand is gecommit vóór de eerste run; na het zien van testresultaten
worden de regels niet veranderd (nieuwe ideeën alleen onderaan als aparte, niet-geteste hypothese).

## 1. Gemeenschappelijk
- **Data**: Swing 20/21-cache, dagbars 2015-01-01 .. 2026-10-23, alleen aandelen die op 2026-10-23 genoteerd waren
  (geen gedelistte aandelen: survivorship bias, gunstig voor elke long-strategie én voor de controle).
- **Universum** op de signaaldag: slot > $5 en 50-daagse gemiddelde dollaromzet > $20M (alle liquide aandelen).
- **Signaal** op het slot van dag t; **instap** op de open van t+1, tenzij anders vermeld (buy-stop: alleen als de
  high van t+1 het niveau raakt; vulling op max(open, niveau)).
- **Uitstap (jouw regel)**: hele positie eruit bij **+10%** (limiet; een gap erboven vult op de open). Stop =
  `mfe.std_stop` (onder de dichtstbijzijnde support-zone - 0,25 ATR, minstens 1 ATR, hooguit 8% onder de instap).
  Zelfde bar: stop eerst. Geen van beide na **20 handelsdagen**: eruit op het slot van dag 20.
- **Kosten**: 0,05% + $0,02 per kant. Win = netto resultaat > 0.
- **Train** = signalen 2015-2022, **test** = 2023-01 .. 2026-10. Er wordt niets gekozen op de test.

## 2. Gemeten per strategie (train en test)
- Per trade (elk signaal, geen limiet op posities): aantal, **% dat +10% haalt** (binnen 5 / 10 / 20 dagen),
  **winrate**, gemiddeld netto per trade, profit factor, gemiddelde houdduur; t-waarde van het gemiddelde.
- **Willekeurige controle per trade**: voor elk signaal 5 willekeurige aandelen uit hetzelfde universum op dezelfde
  dag, zelfde instap (volgende open), stop en exit. Verschil in gemiddelde per trade met een 95%-interval uit een
  bootstrap over signaaldagen (clusters per dag, 10.000x).
- **Rekening** (zoals de exit-test): max 3 posities tegelijk, elk 1/3 van de rekening, instappen op elke dag zodra
  er een plek vrij is, willekeurige keuze bij meer signalen dan plekken (20 runs). Weekrendement, CAGR, max daling,
  Sharpe (weekrendementen, x √52, zonder risicovrije rente), en verschil met RND (willekeurige aandelen, zelfde
  rekening en exit) en met SPY (dividend-gecorrigeerd) met een moving-block bootstrap (4 weken, 10.000x).
- **Meervoudig testen**: 30 strategieën. Een verschil telt alleen als "aantoonbaar" als het 95%-interval boven 0 ligt;
  daarnaast wordt per trade de Bonferroni-grens (|t| > 3,19 voor 30 tests, tweezijdig 5%) gerapporteerd.

## 3. De strategieën (alle long, dagbars)
Uit eerder werk (zelfde regels als in `build.py` / `three_week.py`):
- W1-W10: de 10 setups van `build.py` (VCP, Qullamaggie breakout, episodic pivot, S/R flip retest, failed breakdown,
  pullback in sterke trend, TTM squeeze, inside bar / NR7 aan S/R, AVWAP reclaim, RS leader breakout), met hun eigen
  instap (volgende open of buy-stop).
- S11 earnings-gap (reactiedag, gap >= 5%, volume >= 2x, slot > open).
- S12 jouw indicator v4.1 (`pine_sim.V41` BUY).
- S13 jouw support + EMA-tap + lage RSI (`support_ema.py`, alle liquide aandelen, EMA 50/100/200, RSI(14) <= 35).

Nieuw uit het onderzoek:
- C1 **Connors RSI(2) < 10**: slot > SMA200 en RSI(2) < 10.
- C2 **Connors RSI(2) < 5**: slot > SMA200 en RSI(2) < 5.
- C3 **Double 7s**: slot > SMA200 en slot = laagste slot van de laatste 7 dagen.
- C4 **IBS**: IBS = (slot - laag) / (hoog - laag) < 0,25 en RSI(21) < 45.
- C5 **5 dalingen op rij**: 5 lagere slotkoersen op rij.
- C6 **Bollinger mean reversion**: slot > SMA200 en slot < onderste band (20, 2).
- C7 **Williams %R**: slot > SMA200 en %R(14) < -90.
- C8 **Golden cross**: SMA50 kruist boven SMA200.
- C9 **MACD-crossover**: MACD(12, 26) kruist boven zijn signaallijn (9).
- C10 **Donchian 20 (Turtle systeem 1)**: slot boven het hoogste hoog van de vorige 20 dagen.
- C11 **Turtle 55**: slot boven het hoogste hoog van de vorige 55 dagen.
- C12 **52-weeks-hoog** (George & Hwang): slot boven het hoogste hoog van de vorige 252 dagen.
- C13 **Holy Grail** (Raschke): ADX(14) > 30 en hoger dan 5 dagen eerder, laag <= EMA20 < slot; buy-stop boven de
  high van de signaaldag.
- C14 **Supertrend (10, 3)**: de Supertrend draait van dalend naar stijgend.
- C15 **Stochastic (14, 3)**: %K kruist boven %D terwijl %K < 20.
- C16 **Pocket pivot** (Morales & Kacher): stijgende dag, volume hoger dan het hoogste volume van de dalende dagen in de
  vorige 10 dagen, slot > SMA50.
- C17 **NR7** (Crabel): kleinste dagrange van 7 dagen en slot > SMA200; buy-stop boven de high van de signaaldag.
- RND: willekeurig aandeel uit het universum (controle).

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
