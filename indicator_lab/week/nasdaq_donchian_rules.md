# Donchian 20-breakout op alle NASDAQ-aandelen — vooraf vastgelegde regels

Vraag van de gebruiker: de XOM-strategie (`indicator_lab/xom_donchian.py`) testen op alle NASDAQ-aandelen, ook met
de regel "+10% winst en eruit". Dit bestand is gecommit vóór de eerste run. Code: `indicator_lab/week/nasdaq_donchian.py`.
Rapport: `results/nasdaq_donchian.md`.

## Signaal en uitstappen
- **Kopen**: slot > hoogste hoog van de vorige 20 dagen; instap op de open van de volgende dag. Eén open trade per aandeel.
- **Uitstap DC** (zoals bij XOM): verkopen op de open na een slot < laagste laag van de vorige 20 dagen. Geen andere stop.
- **Uitstap DC+10**: zelfde, maar eerder eruit als de koers +10% boven de instap komt (limiet; een gap erboven vult op
  de open). Zelfde bar: de 20-daagse-laag-regel kan pas op de volgende open uitvoeren, dus het doel gaat voor.
- Maximale houdduur 250 handelsdagen (veiligheidsgrens; daarna verkopen op het slot). Kosten 0,05% + $0,02 per kant.

## Data en universum
- Swing 20/21-cache, alleen aandelen met een NASDAQ-notering (lijst `h4/nasdaq_list.py`), slot > $5 en 50-daagse
  dollaromzet > $20M op de signaaldag; 2015-2026 (train 2015-2022, test 2023-2026). Alleen aandelen die op 2026-10-23
  nog genoteerd waren (geen gedelistte aandelen: survivorship bias, gunstig voor elke long-strategie én voor de controle).
- Dezelfde breakout-signalen als C10 in `results/popular_strategies.md` (daar op alle Amerikaanse aandelen en met
  andere uitstappen getest).

## Metingen
- Per trade: aantal, winrate, % dat +10% haalt, gemiddeld per trade, profit factor, gemiddelde houdduur; verschil met
  5 willekeurige NASDAQ-aandelen per signaal (zelfde dag, zelfde uitstapregel op hun eigen koers), bootstrap over
  instapweken (10.000x, 95%-interval).
- Rekening: 10 posities (elk 1/10) en 3 posities (elk 1/3), 20 runs met willekeurige keuze bij meer signalen dan
  plekken; CAGR, max daling; verschil met RND (zelfde rekening en uitstap), met SPY en met QQQ (moving-block
  bootstrap, 4 weken, 10.000x).
- "Aantoonbaar beter" alleen als het hele 95%-interval boven 0 ligt. 2 uitstappen x 2 rekeningen = 4 varianten.

## Nieuwe hypotheses (na het zien van resultaten; niet in de hoofdtabel)
_(nog geen)_
