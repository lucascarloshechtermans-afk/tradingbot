# Vervolg op C6 (Bollinger-onderband boven SMA200) — vooraf vastgelegde regels

Aanleiding: in `results/popular_strategies.md` was C6 de enige strategie die per trade aantoonbaar beter was dan
willekeurige aandelen, ook na correctie voor 30 tests (+0,41% per trade, t = 3,52; ook positief op de trainjaren).
Daar werd C6 alleen getest met vaste doelen (+10%, of de helft op +5%). Hier: C6 met de uitstap waarmee
Bollinger-mean-reversion normaal wordt gehandeld, en op data die in die studie niet gebruikt is.
Dit bestand is gecommit vóór de eerste run. Code: `indicator_lab/week/c6_followup.py`. Rapport: `results/c6_followup.md`.

## 1. Signaal (ongewijzigd)
Slot > SMA200 en slot < onderste Bollinger-band (SMA20 - 2 x standaardafwijking van 20 slotkoersen). Instap op de
open van de volgende dag. Eén open trade per aandeel. Kosten 0,05% + $0,02 per kant. Stop = `mfe.std_stop` (onder de
dichtstbijzijnde support-zone - 0,25 ATR, minstens 1 ATR, hooguit 8%), zelfde bar: stop eerst; gaps vullen op de open.

## 2. Uitstappen (vier, naast elkaar)
- **M20** (klassiek): verkopen op de open na het eerste slot boven de middelste band (SMA20); max 20 handelsdagen.
- **M5** (Connors-stijl): verkopen op de open na het eerste slot boven de SMA5; max 20 handelsdagen.
- **d**: +10% en eruit (referentie uit de vorige studie).
- **e**: helft op +5%, rest op +10% (referentie uit de vorige studie).

## 3. Data
- **A — zelfde data als de vorige studie** (liquide: > $5, > $20M/dag; 2015-2022 train, 2023-2026 test). De
  signalen zijn daar al gezien; nieuw is alleen de uitstap M20/M5, die niet op deze data gekozen is.
- **B — nieuwe data** (nergens in de populaire-strategieënstudie gebruikt): aandelen met slot > $5 en een
  50-daagse dollaromzet van **$5M tot $20M** per dag, 2015-2026 (hele periode, en apart 2023-2026).
- Alleen aandelen die op 2026-10-23 genoteerd waren (geen gedelistte aandelen: survivorship bias).

## 4. Metingen
- Per trade: aantal, winrate, gemiddeld per trade, profit factor, gemiddelde houdduur; verschil met 5 willekeurige
  aandelen per signaal uit hetzelfde universum op dezelfde dag, met dezelfde uitstap (bootstrap over instapweken,
  10.000x, 95%-interval, t-waarde).
- Rekening: **3 posities** (elk 1/3, zoals eerder) én **10 posities** (elk 1/10; zo wordt mean reversion meestal
  gehandeld), 20 runs; weekrendement, CAGR, max daling, Sharpe (per run); verschil met RND (zelfde rekening en uitstap)
  en met SPY (dividend-gecorrigeerd), moving-block bootstrap (4 weken, 10.000x).
- Aantal vergelijkingen: 4 uitstappen x 2 rekeningen x 2 datasets = 16; Bonferroni-grens wordt vermeld.
- **Oordeel "geslaagd"** alleen als op **dataset B** (nieuwe data) zowel het verschil per trade met random als het
  verschil van de rekening met SPY een 95%-interval helemaal boven 0 heeft, voor de vooraf gekozen hoofdvariant
  **M20 met 10 posities**. De andere varianten worden getoond, maar tellen niet voor het oordeel.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
