"""
Explosive Breakout Swing Scanner - modulaire confidence-score versie
========================================================================
Filosofie: kwaliteit boven kwantiteit. Elke factor is een losse, testbare
module die een score 0-100 teruggeeft. Hard filters (liquiditeit, earnings,
pump-and-dump, market cap) sluiten een ticker volledig uit, ongeacht score.
De overgebleven modules (trend, momentum, volume/institutioneel, volatiliteit,
relatieve sterkte) worden gewogen gecombineerd tot 1 CONFIDENCE-score (0-100).

EERLIJKE BEPERKING: "institutionele koop-activiteit" wordt hier benaderd met
volume-gedrag (OBV-richting, verhouding up/down-volume) - dit is een PROXY,
geen daadwerkelijke orderflow- of 13F-data. yfinance heeft dat niet.

Presets: --preset conservative | balanced | aggressive (default: balanced)

Gebruik:
    python swing_scanner.py                       -> scan van vandaag (balanced)
    python swing_scanner.py --preset conservative  -> scan met strengere filters
    python swing_scanner.py --preset aggressive    -> scan met meer signalen
    python swing_scanner.py --backtest             -> backtest (balanced, 24 maanden)
    python swing_scanner.py --backtest --preset conservative

BELANGRIJK: geen enkele combinatie van filters garandeert winst. Elke module
hieronder is gebaseerd op gangbare technische-analyse-logica, niet op een
bewezen edge voor jouw specifieke watchlist - valideer altijd met --backtest
voordat je een preset live gebruikt.

Installatie: pip install yfinance pandas numpy
"""

import sys
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ============================================================================
# WATCHLIST
# ============================================================================
WATCHLIST = [
    # AI / quantum / cloud / software
    "SMCI", "SOUN", "IONQ", "RGTI", "QUBT", "AI", "PLTR", "BBAI",
    "DELL", "NVDA", "AMD", "AVGO", "MRVL", "ARM", "CRWD", "NET",
    "DDOG", "MDB", "SNOW", "PANW", "ZS", "OKTA", "TEAM", "NOW",
    "WDAY", "HUBS", "TWLO", "DOCU", "ZI", "GTLB", "PATH", "APP",
    "CDNS", "SNPS", "FTNT", "CYBR", "S",
    # crypto-adjacent
    "RIOT", "MARA", "CLSK", "APLD", "CIFR", "HUT", "KEEL", "COIN", "HOOD",
    # fintech
    "UPST", "AFRM", "SOFI", "PYPL",
    # EV / energie momentum
    "RIVN", "LCID", "PLUG", "FCEL", "QS", "ENPH", "FSLR", "SEDG",
    # biotech / speculatief
    "OCGN", "MRNA", "CRSP", "NTLA", "BEAM", "ARWR", "IONS", "ALNY",
    "ALGN", "VRTX", "BIIB", "GILD",
    # halfgeleiders
    "MU", "QCOM", "INTC", "ON", "LRCX", "KLAC", "ASML", "WOLF", "ENTG",
    # consumer / gaming / retail momentum
    "DKNG", "RBLX", "ABNB", "CHWY", "ETSY", "ROKU", "PINS", "SNAP",
    "DASH", "CVNA", "TTWO", "AXON", "TTD", "MELI",
    # China ADR's
    "PDD", "BIDU", "JD", "NTES", "TCOM", "BILI", "IQ", "LI", "ZM",
]

# --- sector-mapping: voor relatieve sterkte per sector + spreidingscontrole ---
# Fallback = SPY voor tickers die niet met zekerheid in 1 sector-ETF passen.
SECTOR_ETF = {
    "SMCI": "SOXX", "AMD": "SOXX", "NVDA": "SOXX", "AVGO": "SOXX", "MRVL": "SOXX",
    "ARM": "SOXX", "MU": "SOXX", "QCOM": "SOXX", "INTC": "SOXX", "ON": "SOXX",
    "LRCX": "SOXX", "KLAC": "SOXX", "ASML": "SOXX", "WOLF": "SOXX", "ENTG": "SOXX",
    "SOUN": "XLK", "IONQ": "XLK", "RGTI": "XLK", "QUBT": "XLK", "AI": "XLK",
    "PLTR": "XLK", "BBAI": "XLK", "DELL": "XLK", "CRWD": "XLK", "NET": "XLK",
    "DDOG": "XLK", "MDB": "XLK", "SNOW": "XLK", "PANW": "XLK", "ZS": "XLK",
    "OKTA": "XLK", "TEAM": "XLK", "NOW": "XLK", "WDAY": "XLK", "HUBS": "XLK",
    "TWLO": "XLK", "DOCU": "XLK", "ZI": "XLK", "GTLB": "XLK", "PATH": "XLK",
    "APP": "XLK", "CDNS": "XLK", "SNPS": "XLK", "FTNT": "XLK", "CYBR": "XLK", "S": "XLK",
    "RIOT": "BLOK", "MARA": "BLOK", "CLSK": "BLOK", "APLD": "BLOK",
    "CIFR": "BLOK", "HUT": "BLOK", "KEEL": "BLOK", "COIN": "BLOK",
    "UPST": "XLF", "AFRM": "XLF", "SOFI": "XLF", "PYPL": "XLF", "HOOD": "XLF",
    "RIVN": "DRIV", "LCID": "DRIV", "PLUG": "ICLN", "FCEL": "ICLN", "QS": "DRIV",
    "ENPH": "ICLN", "FSLR": "ICLN", "SEDG": "ICLN",
    "OCGN": "XBI", "MRNA": "XBI", "CRSP": "XBI", "NTLA": "XBI", "BEAM": "XBI",
    "ARWR": "XBI", "IONS": "XBI", "ALNY": "XBI", "ALGN": "XBI", "VRTX": "XBI",
    "BIIB": "XBI", "GILD": "XBI",
    "DKNG": "XLY", "RBLX": "XLY", "ABNB": "XLY", "CHWY": "XLY", "ETSY": "XLY",
    "ROKU": "XLY", "PINS": "XLY", "SNAP": "XLY", "DASH": "XLY", "CVNA": "XLY",
    "TTWO": "XLY", "AXON": "XLY", "TTD": "XLY",
    "PDD": "KWEB", "BIDU": "KWEB", "JD": "KWEB", "NTES": "KWEB", "TCOM": "KWEB",
    "BILI": "KWEB", "IQ": "KWEB", "LI": "KWEB", "ZM": "XLK",
}
DEFAULT_SECTOR_ETF = "SPY"  # fallback voor onbekende tickers (bv. de brede NASDAQ-scan)

# --- aparte watchlist voor de 'explosive'-preset -------------------------
# De hoofd-WATCHLIST hierboven bestaat uit gevestigde, liquide namen (SMCI,
# PLTR, NVDA...) die vrijwel allemaal 100M+ aandelen float hebben - daar kan
# de explosive-preset (MAX_FLOAT=30M) per definitie nooit iets in vinden.
# Dit is een kleinere, kleinschaligere selectie. LET OP: micro-caps hebben
# een veel hogere kans op naamswijzigingen/overnames/delistings dan de
# hoofdlijst - verwacht vaker een "possibly delisted"-melding hier, dat is
# normaal voor dit segment, geen fout in het script.
EXPLOSIVE_WATCHLIST = [
    # kleinere/vluchtigere namen uit de hoofdlijst zelf
    "SOUN", "RGTI", "QUBT", "BBAI", "IONQ", "CIFR", "HUT", "APLD",
    "OCGN", "ARWR", "BEAM", "NTLA",
    # aanvullende kleinere small-caps (verifieer periodiek zelf op actualiteit)
    "BOLD", "PLUG", "FCEL", "QS", "CHPT",
]
# Hierboven is een FALLBACK (gebruikt als de live NASDAQ-lijst niet op te
# halen is). Standaard gebruikt de explosive-backtest onderstaande, veel
# bredere, DYNAMISCH opgehaalde NASDAQ-lijst - dezelfde methode als de
# dagelijkse scan - zodat de float/market-cap-filters zelf bepalen wie
# erin past, i.p.v. dat wij losse tickers moeten blijven raden.
EXPLOSIVE_BACKTEST_UNIVERSE_SIZE = 300  # groter = meer kans op treffers, maar ook veel langere wachttijd

# --- dagelijkse scan: (bijna) hele NASDAQ i.p.v. vaste watchlist ---------
USE_FULL_NASDAQ_SCAN = True
MAX_UNIVERSE_SIZE = 3000   # verhoogd van 1500: de NASDAQ heeft er ruim 3000.
                            # Meer aandelen doorzoeken met DEZELFDE kwaliteitseisen
                            # is geen verwatering - je vist in een grotere vijver.
                            # De scan duurt hierdoor wel ongeveer twee keer zo lang.
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
DOWNLOAD_CHUNK_SIZE = 200

HIST_PERIOD = "24mo"   # verhoogd van 9mo: de EMA300 vraagt ~310 handelsdagen
                        # (~15 maanden). Met 9mo zou de scan elk aandeel weren.
BACKTEST_PERIOD = "48mo"  # verlengd van 24mo: bij 24mo bleef TEST met alle filters te klein (n=4) om iets te concluderen
TRAIN_TEST_SPLIT = 0.7

# --- trade-mechanica ---------------------------------------------------
STOP_ATR_MULT = 1.5
TARGET_ATR_MULT = 3.0
HOLD_DAYS = 3
COMMISSION_PCT = 0.001         # 0.1% kosten per kant (entry + exit = 0.2% totaal per trade)
# LET OP: vaste slippage is vervangen door SLIPPAGE_TIERS (verderop in dit bestand) -
# slippage schaalt nu mee met de liquiditeit van de ticker i.p.v. 1 vast percentage.

# --- account / risk ------------------------------------------------------
ACCOUNT_SIZE = 10_000
RISK_PCT_PER_TRADE = 0.01
MAX_POSITION_PCT = 0.20

# ============================================================================
# PRESETS - conservatief / gebalanceerd / agressief
# ============================================================================
# Elke preset stelt de HARDE filters en de MIN_CONFIDENCE-drempel in.
# De module-gewichten (hoe de confidence-score wordt opgebouwd) blijven
# hetzelfde over presets - alleen de strengheid van de poort verandert.
PRESETS = {
    "elite": {
        # Bewust de strengste variant: mikt op 0-3 signalen per dag, en soms
        # helemaal 0 - dat is geen bug, dat is het hele punt van "alleen A+".
        "MIN_CONFIDENCE": 93,
        "RVOL_MIN": 3.5,
        "MIN_MARKET_CAP": 400_000_000,
        "MIN_DOLLAR_VOLUME": 25_000_000,
        "TREND_R2_MIN": 0.80,
        "EARNINGS_BLACKOUT_DAYS": 5,
        "MAX_SIGNALS_PER_DAY": 3,
        "ATR_PCT_RANGE": (0.03, 0.06),
        "MAX_SINGLE_DAY_MOVE": 0.30,
        "MODULE_FLOOR": 55,
    },
    "conservative": {
        "MIN_CONFIDENCE": 90,
        "RVOL_MIN": 3.0,
        "MIN_MARKET_CAP": 300_000_000,
        "MIN_DOLLAR_VOLUME": 20_000_000,
        "TREND_R2_MIN": 0.75,          # harde eis: alleen zeer schone trends
        "EARNINGS_BLACKOUT_DAYS": 5,
        "MAX_SIGNALS_PER_DAY": 5,
        "ATR_PCT_RANGE": (0.03, 0.07), # smalle, "gezonde" volatiliteitsband
        "MAX_SINGLE_DAY_MOVE": 0.35,   # pump-detectie: >35% op 1 dag = verdacht
        "MODULE_FLOOR": 50,
    },
    "balanced": {
        # GEMETEN via grid-sweep (48mo, RVOL x CONF x FLOOR samen, met
        # train/test-validatie). Gekozen: RVOL 0.8 / CONF 60 / FLOOR 0, omdat
        # die als een van de vijf ROBUUSTE combinaties uit de test kwam:
        #   TRAIN +0.37%  TEST +0.08%  (2789 + 1369 trades)
        # De grid beval RVOL 1.2 aan (TEST +0.10%), maar dat verschil valt
        # binnen de ruis terwijl die variant 3x minder trades heeft; op 1369
        # trades is de meting zelf betrouwbaarder. RVOL 0.8 kwam bovendien ook
        # uit de losse RVOL-sweep als optimum - twee onafhankelijke metingen.
        "MIN_CONFIDENCE": 60,
        "RVOL_MIN": 0.8,   # GEMETEN optimum (sweep op 48mo echte data):
                            #   RVOL 0.8 -> 306 signalen, +0.04% per trade
                            #   RVOL 2.0 ->  43 signalen, -1.12% per trade
                            #   RVOL 3.0 ->  15 signalen, -3.26% per trade
                            # Monotoon dalend: hoe hoger de volume-eis, hoe slechter.
                            # Bevestigt dat een volumePIEK eisen = te laat instappen.
        "MIN_MARKET_CAP": 150_000_000,
        "MIN_DOLLAR_VOLUME": 10_000_000,
        "TREND_R2_MIN": 0.60,
        "EARNINGS_BLACKOUT_DAYS": 3,
        "MAX_SIGNALS_PER_DAY": 10,
        "ATR_PCT_RANGE": (0.025, 0.09),
        "MAX_SINGLE_DAY_MOVE": 0.45,
        "MODULE_FLOOR": 0,   # gemeten: 0/20/30 gaven vrijwel gelijke resultaten
    },
    "aggressive": {
        "MIN_CONFIDENCE": 75,
        "RVOL_MIN": 1.5,
        "MIN_MARKET_CAP": 50_000_000,
        "MIN_DOLLAR_VOLUME": 5_000_000,
        "TREND_R2_MIN": 0.45,
        "EARNINGS_BLACKOUT_DAYS": 1,
        "MAX_SIGNALS_PER_DAY": 20,      # bewust buiten de 2-10 range: dat is de aard van "agressief"
        "ATR_PCT_RANGE": (0.02, 0.14),
        "MAX_SINGLE_DAY_MOVE": 0.60,
        "MODULE_FLOOR": 25,
    },
    "meer": {
        # Bewust ingesteld op MEER signalen. Let op: dit verlaagt de lat, het
        # verhoogt niet de kwaliteit. De benchmark liet zien dat de selectie
        # geen aantoonbare edge heeft - meer signalen betekent dus vooral meer
        # trades, niet meer winst. Gebruik dit als watchlist-generator waaruit
        # je zelf kiest, niet als "meer kansen om te winnen".
        "MIN_CONFIDENCE": 70,
        "RVOL_MIN": 1.2,
        "MIN_MARKET_CAP": 100_000_000,
        "MIN_DOLLAR_VOLUME": 5_000_000,
        "TREND_R2_MIN": 0.30,
        "EARNINGS_BLACKOUT_DAYS": 2,
        "MAX_SIGNALS_PER_DAY": 15,
        "ATR_PCT_RANGE": (0.02, 0.12),
        "MAX_SINGLE_DAY_MOVE": 0.50,
        "MODULE_FLOOR": 20,
        "MAX_EXTENSION": 0.10,
        "MAX_PER_SECTOR": 4,
    },
    "explosive": {
        # Expliciete keuze: kleinere, vluchtigere aandelen voor kans op grote
        # 1-dags-moves. Geen "veiligere" variant - dit accepteert bewust een
        # groter verliesrisico per trade in ruil voor grotere winst-potentie.
        "MIN_CONFIDENCE": 65,
        "RVOL_MIN": 3.0,                # juist HOGER: bij meer ruis moet volume-bevestiging sterker zijn
        "MIN_MARKET_CAP": 15_000_000,   # laat micro-caps toe (bewust risico)
        "MAX_FLOAT": 30_000_000,        # het kenmerk dat deze preset definieert: low float
        "MIN_DOLLAR_VOLUME": 3_000_000, # lager dan andere presets, maar niet 0 - moet nog verhandelbaar zijn
        "TREND_R2_MIN": 0.25,           # explosieve movers hebben vaak geen nette trend vooraf (nieuws/squeeze)
        "EARNINGS_BLACKOUT_DAYS": 2,
        "MAX_SIGNALS_PER_DAY": 8,
        "ATR_PCT_RANGE": (0.06, 0.30),  # bewust hoge ondergrens: moet al aantoonbaar vluchtig zijn
        "MAX_SINGLE_DAY_MOVE": 0.70,    # ruimer dan andere presets - grote 1-dags-moves zijn hier het DOEL
        "MODULE_FLOOR": 20,             # losser: deze stijl is inherent ruizig, te streng filtert alles weg
        "REQUIRE_UPTREND": False,       # low-float runners komen vaak "uit het niets", zonder nette trend vooraf
    },
}
# Kernmodules die individueel de MODULE_FLOOR moeten halen - een aandeel dat op
# EEN van deze dimensies zwak is, mag niet meer gemaskeerd worden door de rest.
# (momentum en catalyst blijven bewust wel compensabel: dat zijn bevestigers,
# geen fundamentele voorwaarden voor een geldige swing-setup.)
CORE_MODULES_WITH_FLOOR = ["trend", "volume", "rs"]

# module-gewichten voor de samengestelde confidence-score (som = 1.0)
MODULE_WEIGHTS = {
    "trend": 0.17,
    "momentum": 0.12,
    "volume": 0.17,      # bevat de "institutioneel"-proxy (OBV + up/down-volume)
    "volatility": 0.08,
    "rs": 0.17,
    "catalyst": 0.12,    # korte-termijn: recente earnings-beat / analist-upgrade / short-squeeze
    "structuur": 0.17,   # ruimte omhoog, weekbevestiging, ADX, marktstructuur, squeeze, VWAP
}
CATALYST_LOOKBACK_DAYS = 14

MIN_PRICE = 3.0

# --- entry-kwaliteit: hoe ver boven het uitbraakpunt mag je nog instappen? ---
# Gebaseerd op O'Neil/Minervini: wie te ver boven de pivot koopt, wordt door een
# NORMALE terugval uitgestopt terwijl de breakout eigenlijk intact is. De stop-
# afstand zwelt dan op en de hele risk/reward klopt niet meer. Dit was het
# grootste gat in deze scanner: er werd wel gecheckt DAT er een breakout was,
# maar nooit HOE VER de koers er al boven stond.
#
# BELANGRIJK over het gekozen getal: de klassieke "max 5% boven de pivot"-regel
# gaat uit van INTRADAY instappen op het moment dat de koers de pivot doorbreekt.
# Deze scanner werkt op DAGSLOTKOERSEN - tegen de tijd dat een aandeel *sluit*
# boven zijn 20-daags hoog, staat het daar vaak al 5-10% boven, puur door hoe
# de meting werkt. 5% hanteren op dagdata is daarom veel strenger dan de regel
# bedoelt (het halveerde het aantal signalen zonder inhoudelijke reden).
# GEMETEN op 1063 gesimuleerde slotkoers-breakouts: 99.7% valt binnen 5%
# extensie. Dat komt doordat HIGH20 een MEELOPEND 20-daags maximum is - stijgt
# de koers door, dan stijgt de pivot mee. Het filter bindt dus zelden, en weert
# vooral de echte uitschieters (nieuws-gaps). Daarom de literatuurwaarde 5%.
MAX_EXTENSION_ABOVE_PIVOT = 0.05

# --- structuur-gebaseerde stop i.p.v. puur ATR ---------------------------
# Minervini plaatst de stop onder het laatste contractie-dieptepunt (3-7% risico),
# niet op een generieke volatiliteitsafstand. We nemen de KRAPSTE van beide en
# begrenzen het totale risico hard - dat verkleint de verliezers structureel.
# GEMETEN (3000 gesimuleerde setups) en GETEST op echte backtest-data:
#   - de structuur-stop greep in 75.5% van de gevallen in en halveerde de
#     risico-afstand (7.9% -> 4.5%). Gevolg: kleinere verliezen (-7.25% -> -5.71%)
#     maar VEEL vaker uitgestopt (win rate 53.7% -> 41.9%). Netto ongunstig.
#     Daarom uitgezet: dit is een reeel gemeten nadeel, geen theoretische zorg.
#   - de 8%-limiet greep maar in 2.7% van de gevallen in - die laat normale
#     trades met rust en vangt alleen de uitschieters (in een eerdere test een
#     trade met 30% risico!). Die blijft dus AAN: bescherming zonder bijwerking.
USE_STRUCTURE_STOP = False         # zie meting hierboven - maakte stops te krap
STRUCTURE_STOP_LOOKBACK = 10       # (ongebruikt zolang USE_STRUCTURE_STOP=False)
STRUCTURE_STOP_BUFFER = 0.005      # (idem)
MAX_STOP_PCT = 0.08                # blijft AAN: nooit meer dan 8% risico per trade
MAX_PRICE = 2000.0   # was 100: dat stamt uit de eerste versie, gericht op kleine
                     # momentum-aandelen, en sloot juist dure BEKENDE namen uit.
                     # Positiegrootte vangt een hoge koers al op (minder aandelen).
RSI_PERIOD = 14
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
ATR_PERIOD = 14

# --- marktregime-filter --------------------------------------------------
# Alleen signalen toelaten als de bredere markt (SPY) zelf niet in een
# downtrend zit. Breakouts falen vaker tijdens een dalende markt.
USE_MARKET_REGIME_FILTER = False  # standaard UIT: nog geen bewijs dat dit helpt (zie check_regime.py)
# In de LIVE SCAN blokkeert dit nooit meer de hele scan, ongeacht deze instelling -
# je krijgt hooguit een waarschuwing te zien, de scan draait altijd door.
# In de BACKTEST kun je 'm op True zetten om te TESTEN of regime-filtering historisch
# uberhaupt iets opgeleverd zou hebben - dat is dan een bewuste, meetbare keuze.
REGIME_SMA_PERIOD = 50

# --- exit-logica: trailing stop + gedeeltelijk winst nemen --------------
USE_TRAILING_EXIT = True
MAX_HOLD_DAYS = 5            # max aantal dagen dat een positie wordt aangehouden
PARTIAL_EXIT_AT_R = 1.0      # neem 50% winst zodra prijs 1x het risico heeft bewogen
PARTIAL_EXIT_FRACTION = 0.5
BREAKEVEN_AFTER_PARTIAL = True  # stop naar entry zodra partial exit is genomen

# --- variabele slippage o.b.v. liquiditeit -------------------------------
# Hoe lager de dollar-volume, hoe groter de aanname van slippage bij een stop.
SLIPPAGE_TIERS = [  # (min_dollar_volume, slippage_pct)
    (50_000_000, 0.003),
    (20_000_000, 0.006),
    (10_000_000, 0.010),
    (0,          0.015),
]

# --- spreiding: max aantal signalen per sector per dag -------------------
MAX_SIGNALS_PER_SECTOR = 2

# --- live logging ----------------------------------------------------
SCAN_LOG_FILE = "scan_log.csv"

# --- cross-sectionele ranking (zie de functies verderop voor de onderbouwing) ---
MOMENTUM_LOOKBACK = 126      # ~6 maanden meetperiode (Levy gebruikte 26 weken)
MOMENTUM_SKIP = 5            # laatste week overslaan (korte-termijn-omkeereffect)
TOP_N_PERCENTIEL = 10        # alleen de sterkste 10% komt in aanmerking

# --- SAMENGESTELDE MOMENTUM-SCORE ----------------------------------------
# GEMETEN (--test-momentum, 48mo echte data, 6 walk-forward vensters):
#   enkel (126 dagen)      : 819 trades, +1.217% per trade, win 54.3%, med +1.94
#   multi (63/126/252)     : 915 trades, +1.552% per trade, win 56.6%, med +2.80
#   gewogen (50/30/20)     : 955 trades, +1.482% per trade, win 56.2%, med +2.65
#
# 'multi' wint op ALLE maten tegelijk - meer trades, hoger rendement, hogere
# win rate en hogere mediaan - en in 4 van de 6 vensters. Dat is ongebruikelijk;
# meestal betaal je voor meer rendement met minder trades of een lagere win rate.
#
# Waarom het werkt: een enkele meting over 126 dagen kijkt alleen naar begin-
# en eindpunt. Twee aandelen met beide +80% kunnen totaal anders zijn opgebouwd -
# gestage klim versus een eenmalige sprong. Getest op kunstmatige data maakte
# 'multi' dat onderscheid het scherpst (22.5 tegen 18.2 voor de enkele meting).
# De overlap met de oude methode is 62%, dus het is een wezenlijk andere selectie.
MOMENTUM_METHODE = "multi"   # "enkel", "multi" of "gewogen"

# --- EARNINGS-BLACKOUT ----------------------------------------------------
# Aantal dagen voor een earnings-datum waarin geen nieuwe posities worden
# geopend. Reden: een gap na cijfers gaat dwars door een stop-loss heen -
# je verliest dan meer dan je berekend had, hoe goed de setup ook was.
# Dit zat in de oude drempel-scan maar ontbrak in de ranking-scan.
EARNINGS_BLACKOUT_DAGEN = 5

# Optie-analyse tonen bij elke kandidaat. Zet op False als je alleen met
# aandelen handelt - het scheelt een paar seconden per kandidaat.
TOON_OPTIE_ADVIES = True

# --- ALLEEN GROTE, BEKENDE BEDRIJVEN --------------------------------------
# Minimale marktwaarde. $2 miljard is waar mid-cap begint. Referentie: de
# voorbeelden die als "bekende namen" zijn genoemd (Marvell, Nebius, Rocket
# Lab, AXT) zitten allemaal boven deze grens.
#
# LET OP - DIT IS NIET TE BACKTESTEN. yfinance levert alleen de HUIDIGE
# marktwaarde. Toepassen op historische data zou aandelen meenemen die pas
# LATER groot werden (AXT was in nov 2025 nog $366M waard, in mei 2026 $7.8B),
# en de verliezers die klein bleven weglaten. Dat geeft een misleidend
# positief resultaat. Dit filter is daarom een keuze over WELKE aandelen je
# wilt handelen, geen bewezen verbetering van het rendement.
GEBRUIK_MARKTWAARDE_FILTER = True
MIN_MARKTWAARDE = 2_000_000_000     # $2 miljard

# Minimaal DOLLARVOLUME per dag (koers x gemiddeld dagvolume). Dit is de
# beste maat voor "bekende naam": een aandeel waar dagelijks honderden
# miljoenen in omgaan, wordt gevolgd door analisten, media en instellingen.
# Een obscuur aandeel boven $2 miljard marktwaarde kan nog steeds maar een
# paar miljoen per dag verhandelen.
# Referentie: AXT (AXTI) ~12M aandelen/dag x ~$50 = ~$600M per dag.
# Marvell, Nebius en Rocket Lab liggen daar ver boven.
# Vroeger stond deze grens op $5M - dat liet obscure namen door.
MIN_DAGVOLUME_DOLLAR = 100_000_000   # $100 miljoen per dag

# Trendfilter bovenop de ranking. GEMETEN op 48mo echte data (--test-trendfilter):
#   geen filter                : +0.480% per trade, 5203 trades
#   koers > EMA21 alleen       : +0.444% per trade  <- SLECHTER dan geen filter
#   koers > EMA21 EN EMA9>EMA21: +0.631% per trade, 2917 trades  <- gekozen
#   koers > SMA50              : +0.561% per trade
# Waarom de dubbele eis en niet alleen "boven de EMA21": dat laatste zegt enkel
# waar de koers vandaag staat. De eis dat EMA9 boven EMA21 ligt zegt dat de
# kortetermijntrend zelf omhoog gericht is - dat onderscheidt een aandeel dat
# opveert van eentje dat toevallig een dag boven de lijn sluit.
GEBRUIK_TRENDFILTER = True

# Extra eis: koers ook boven de EMA300. GEMETEN (--test-trendfilter, 48mo):
#   geen filter              : +0.480% per trade, 5203 trades
#   EMA21 + EMA9>21          : +0.631% per trade, 2917 trades
#   EMA21 + EMA9>21 + EMA300 : +0.798% per trade, 2426 trades  <- gekozen
# Doorslaggevend: in venster 6 (de zwakste periode) is dit de ENIGE variant
# die positief uitkomt (+0.04% tegen -0.19% zonder).
#
# EERLIJKE KANTTEKENING: de EMA300 vraagt ~15 maanden historie, dus jonge
# beursgangers vallen automatisch af. Een deel van de winst kan dus komen
# doordat gevestigde bedrijven stabieler zijn, niet doordat de trend intact
# is. Met deze data zijn die twee verklaringen niet te scheiden.
GEBRUIK_EMA300_FILTER = True

# --- LEESBAARHEIDSFILTER ("clean price action", geen barcode) -------------
# GEMETEN (--test-trendfilter, 48mo echte data, 6 walk-forward vensters):
#   geen extra filter              +0.450% per trade, win 50.5%, 5224 trades
#   EMA9/21/300 (vorige stand)     +0.848% per trade, win 51.0%, 2425 trades
#   + boven VWAP                   +0.963% per trade, win 51.7%, 2242 trades
#   + leesbaar (gekozen)           +1.428% per trade, win 55.5%,  853 trades
#
# Doorslaggevend: variant 4 wint in 4 van de 6 vensters - het hoogste
# consistentiecijfer van dit hele project - en is in ALLE zes vensters
# positief, inclusief de twee periodes waarin eerdere versies faalden.
# VWAP voegde niets toe (variant 5 vrijwel identiek, 0/6 vensters) en is
# daarom weggelaten.
#
# Wat het meet: de efficiency ratio (netto koersbeweging / totale afgelegde
# weg). Een aandeel dat gestaag klimt scoort hoog; eentje dat heen en weer
# springt naar hetzelfde eindpunt scoort laag. Bij het testen bleek een
# "barcode" met een HOGER eindrendement (+121% vs +107%) toch een efficiency
# van 0.27 tegen 1.00 te hebben - de maat kijkt naar het verloop, niet naar
# de uitkomst.
GEBRUIK_LEESBAARHEIDSFILTER = True
MIN_EFFICIENCY = 0.35    # koersbeweging moet minstens 35% "rechtdoor" zijn

# --- VIX-ONDERGRENS -------------------------------------------------------
# GEMETEN (--test-vix, 48mo echte data, 818 signalen):
#   VIX <13    :  81 trades, +0.29% per trade, win 43.2%, mediaan -3.24
#   VIX 13-14  : 119 trades, +0.63% per trade, win 48.7%, mediaan -0.98
#   VIX 14-15  : 111 trades, -0.07% per trade, win 49.6%, mediaan -1.49
#   VIX 15-16  :  88 trades, +0.30% per trade, win 48.9%, mediaan -1.00
#   VIX 16-18  : 226 trades, +3.28% per trade, win 65.9%, mediaan +3.50  <-- omslag
#   VIX 18-20  : 105 trades, +2.11% per trade, win 61.0%, mediaan +3.08
#   VIX 20-25  :  78 trades, -0.04% per trade, win 51.3%
#   VIX >25    :  10 trades, -7.28% per trade, win 10.0%
#
# Alles onder VIX 16 heeft een NEGATIEVE mediaan en een win rate rond 48%.
# Boven 16 springt het naar 66% win rate. Niet handelen onder 16 gaf
# +2.117% per trade tegen +1.228% zonder filter (+0.889pp), en won in
# 3 van de 5 bruikbare vensters.
#
# Waarom dit logisch is: bij zeer lage volatiliteit bewegen aandelen te
# weinig om binnen 5 dagen een zinvolle swing te maken. De strategie heeft
# beweging nodig - te veel is slecht (VIX>25 gaf -7.28%), maar te weinig ook.
#
# PRIJS HIERVAN: je gaat van 818 naar 419 trades - de helft weg, ongeveer
# 100 per jaar. Bij zeer lage VIX sta je dus wekenlang aan de kant.
GEBRUIK_VIX_FILTER = True
VIX_MINIMUM = 16.0    # onder dit niveau geen nieuwe posities openen
VIX_MAXIMUM = 25.0    # boven dit niveau ook niet (VIX>25 gaf -7.28% per trade)

# --- PORTFOLIO HEAT: totaal open risico begrenzen -------------------------
# Het probleem dat dit oplost: elke trade riskeert 1% van je account, maar er
# was geen limiet op het AANTAL gelijktijdige posities. Neem je 15 signalen,
# dan riskeer je 15% tegelijk. De backtest zag dat niet, want die rekent elke
# trade los door alsof je oneindig kapitaal hebt.
#
# MAX_PORTFOLIO_HEAT is het maximale TOTALE open risico. Bij 6% en 1% per
# trade kun je dus maximaal 6 posities tegelijk aanhouden. Signalen die
# daarboven komen worden overgeslagen - dat is wat er in de praktijk ook
# gebeurt, en het maakt de backtest eerlijker.
MAX_PORTFOLIO_HEAT = 0.06      # 6% van het account als totaal open risico
MAX_GELIJKTIJDIGE_POSITIES = 6  # harde bovengrens, ook als de heat het toelaat

# ============================================================================
# BASIS-INDICATOREN
# ============================================================================

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs_ = avg_gain / avg_loss
    return 100 - (100 / (1 + rs_))


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def atr(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low, (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, min_periods=period).mean()


def obv(df):
    """On-Balance Volume: loopt op bij up-days, af bij down-days.
    Een stijgende OBV-trend terwijl de koers ook stijgt = volume bevestigt
    de trend (accumulatie-proxy)."""
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def linreg_trend(closes, lookback=20):
    """Lineaire regressie op log(close). Geeft (slope, r2) terug.
    r2 dicht bij 1 = schone, consistente trend. r2 laag = choppy/alle kanten op."""
    y = np.log(closes.values[-lookback:])
    if len(y) < lookback or np.any(np.isnan(y)) or np.any(y <= 0):
        return 0.0, 0.0
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, max(0.0, r2)


def adx(df, period=14):
    """ADX = trendKRACHT (0-100), los van richting. Verschilt wezenlijk van de
    R2 die de scanner al gebruikt: R2 meet hoe RECHT een trend loopt, ADX meet
    hoe STERK hij duwt. Een aandeel kan netjes-maar-slap stijgen (hoge R2, lage
    ADX) of hard-maar-grillig (lage R2, hoge ADX). Vuistregel: ADX > 25 = trend."""
    high, low, close = df["High"], df["Low"], df["Close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_ = tr.ewm(alpha=1/period, min_periods=period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/period, min_periods=period).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/period, min_periods=period).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1/period, min_periods=period).mean(), plus_di, minus_di


def money_flow_index(df, period=14):
    """MFI = RSI maar dan volume-gewogen. Onderscheidt zich van OBV doordat het
    genormaliseerd is (0-100) en van RSI doordat volume meeweegt: een prijsstijging
    op groot volume telt zwaarder dan dezelfde stijging op dun volume."""
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    raw_flow = typical * df["Volume"]
    pos_flow = raw_flow.where(typical > typical.shift(1), 0).rolling(period).sum()
    neg_flow = raw_flow.where(typical < typical.shift(1), 0).rolling(period).sum()
    ratio = pos_flow / neg_flow.replace(0, np.nan)
    return 100 - (100 / (1 + ratio))


def compute_overhead_resistance(df, lookback=252):
    """RUIMTE OMHOOG - waarschijnlijk de belangrijkste ontbrekende factor.

    Als een aandeel uitbreekt maar er ligt 3% hoger een oude top waar destijds
    veel volume verhandeld werd, dan zitten daar verkopers klaar die 'eindelijk
    quitte' willen spelen. Die overhead supply remt de swing af, hoe mooi de
    setup verder ook is. Omgekeerd: breekt een aandeel uit met vrij zicht naar
    boven (bv. richting all-time high), dan is er geen structurele weerstand.

    Kijkt 252 handelsdagen (ca. 1 jaar) terug: overhead supply uit een top van
    maanden geleden is nog steeds relevant, want die kopers zitten er nog.
    Een kortere lookback (120) miste juist de oudere toppen die het meest
    remmend werken - dat bleek bij het testen.

    Retourneert het percentage tot de eerstvolgende relevante weerstand.
    Grote waarde (of NaN bij all-time high) = veel ruimte = gunstig."""
    if len(df) < 30:
        return np.nan
    window = df.iloc[-lookback:] if len(df) >= lookback else df
    current = df["Close"].iloc[-1]
    # zwing-toppen: lokale maxima die boven de huidige koers liggen
    highs = window["High"]
    is_pivot_high = (highs > highs.shift(1)) & (highs > highs.shift(-1))
    resistances = highs[is_pivot_high & (highs > current * 1.005)]
    if len(resistances) == 0:
        return np.nan  # geen weerstand boven ons = vrije baan
    nearest = resistances.min()
    return (nearest - current) / current


def compute_weekly_confirmation(df):
    """MULTI-TIMEFRAME: bevestigt de weekgrafiek de dagtrend? Alles in deze
    scanner keek tot nu toe alleen naar dagkoersen. Een dag-breakout tegen een
    dalende weektrend in is wezenlijk zwakker dan eentje die met de weektrend
    meeloopt - dat is standaard praktijk bij swingtraders en ontbrak volledig."""
    try:
        wk = df.resample("W").agg({"Open": "first", "High": "max", "Low": "min",
                                    "Close": "last", "Volume": "sum"}).dropna()
        if len(wk) < 12:
            return {"weekly_uptrend": None, "weekly_above_sma10": None}
        wk_sma10 = wk["Close"].rolling(10).mean()
        laatste = wk["Close"].iloc[-1]
        boven_sma = bool(laatste > wk_sma10.iloc[-1]) if not pd.isna(wk_sma10.iloc[-1]) else None
        # weektrend: hogere toppen EN hogere bodems over de laatste 4 weken
        hh = wk["High"].iloc[-1] > wk["High"].iloc[-4]
        hl = wk["Low"].iloc[-1] > wk["Low"].iloc[-4]
        return {"weekly_uptrend": bool(hh and hl), "weekly_above_sma10": boven_sma}
    except Exception:
        return {"weekly_uptrend": None, "weekly_above_sma10": None}


def analyseer_basis_kwaliteit(df, lookback=40):
    """Beoordeelt de KWALITEIT van de consolidatie (basis) waaruit een aandeel
    uitbreekt. Onderzoek toont dat dit de sterkste enkele voorspeller is:
    krappe bases geven ~51% slagingskans tegen ~35% voor brede bases - 16
    procentpunt verschil uit een variabele. De logica is 'opgeslagen energie':
    een strak samengedrukte veer schiet verder dan een slappe.

    Beoordeelt drie dingen:
      1. hoe KRAP de basis is (hoogte t.o.v. de koers)
      2. hoe VAAK het weerstandsniveau getest is (2-3 tests = sterk niveau)
      3. of het volume tijdens de basis OPDROOGDE (verkopers uitgeput)
    """
    if len(df) < lookback + 5:
        return None
    basis = df.iloc[-lookback:-1]     # de periode VOOR vandaag
    top = basis["High"].max()
    bodem = basis["Low"].min()
    huidige = df["Close"].iloc[-1]
    if top <= 0:
        return None

    hoogte_pct = (top - bodem) / top

    # Hoe vaak is de top benaderd? Tel LOSSE aanrakingen, niet losse dagen:
    # in een krappe basis ligt bijna elke dag binnen 2% van de top, wat anders
    # 20+ "tests" zou opleveren terwijl het er in werkelijkheid 2 of 3 zijn.
    # Een nieuwe test telt pas als de koers er eerst weer vanaf is gezakt.
    dicht_bij_top = (basis["High"] >= top * 0.98).values
    tests = 0
    in_test = False
    for raakt in dicht_bij_top:
        if raakt and not in_test:
            tests += 1
            in_test = True
        elif not raakt:
            in_test = False

    # volume tijdens de tweede helft van de basis t.o.v. de eerste helft
    helft = len(basis) // 2
    vol_vroeg = basis["Volume"].iloc[:helft].mean()
    vol_laat = basis["Volume"].iloc[helft:].mean()
    vol_trend = vol_laat / vol_vroeg if vol_vroeg > 0 else 1.0

    score = 0.0
    if hoogte_pct <= 0.12:
        score += 40; kwaliteit = "zeer krap"
    elif hoogte_pct <= 0.20:
        score += 30; kwaliteit = "krap"
    elif hoogte_pct <= 0.30:
        score += 15; kwaliteit = "gemiddeld"
    else:
        score += 0; kwaliteit = "breed (zwak)"

    if 2 <= tests <= 6:
        score += 30      # meerdere afketsingen = een echt, erkend niveau
    elif tests == 1:
        score += 12
    elif tests > 6:
        score += 15      # heel vaak getest kan ook uitputting betekenen

    if vol_trend < 0.8:
        score += 30      # volume droogde op tijdens de basis
    elif vol_trend < 1.0:
        score += 18
    else:
        score += 5

    return {
        "basis_hoogte_pct": round(hoogte_pct * 100, 1),
        "basis_kwaliteit": kwaliteit,
        "aantal_tests": tests,
        "volume_trend_in_basis": round(vol_trend, 2),
        "basis_score": round(min(100.0, score), 1),
        "weerstand": top,
    }


def bepaal_fase(df, row):
    """Bepaalt in welke FASE een aandeel zit t.o.v. zijn uitbraakpunt.
    Dit is de kern van de gecombineerde scan: hetzelfde aandeel kan vandaag
    'aan het opladen' zijn en morgen 'aan het uitbreken', en die twee vragen
    om totaal verschillende beoordelingen."""
    pivot = row.get("HIGH20", np.nan)
    close = row["Close"]
    if pd.isna(pivot) or pivot <= 0:
        return "onbekend", np.nan

    afstand = (close - pivot) / pivot   # positief = boven de pivot
    if afstand > 0.06:
        return "TE LAAT", afstand        # al te ver doorgeschoten
    elif afstand > 0.0:
        return "BREEKT UIT", afstand     # vandaag boven het niveau
    elif afstand > -0.05:
        return "OPLADEN", afstand        # vlak eronder, coilt
    else:
        return "VER WEG", afstand


def scoor_breakout_kwaliteit(df, row, basis_info):
    """Scoort een ACTUELE breakout op de factoren die onderzoek als
    doorslaggevend aanwijst voor het slagen ervan."""
    score = 0.0
    redenen = []

    # 1. basiskwaliteit (sterkste enkele voorspeller)
    if basis_info:
        score += basis_info["basis_score"] * 0.35
        redenen.append(f"basis {basis_info['basis_kwaliteit']} ({basis_info['basis_hoogte_pct']}% hoog, "
                       f"{basis_info['aantal_tests']}x getest)")

    # 2. volume op de uitbraakdag: onderzoek noemt >150% van het gemiddelde
    rvol = row["Volume"] / row["VOL_SMA20"] if row["VOL_SMA20"] else 0
    if rvol >= 2.0:
        score += 25; redenen.append(f"volume {rvol:.1f}x gemiddeld (sterk)")
    elif rvol >= 1.5:
        score += 18; redenen.append(f"volume {rvol:.1f}x gemiddeld (voldoende)")
    elif rvol >= 1.2:
        score += 8; redenen.append(f"volume {rvol:.1f}x (zwak)")
    else:
        redenen.append(f"volume {rvol:.1f}x - ONVOLDOENDE (breakouts op laag volume falen vaker)")

    # 3. beslissende slotkoers, geen lont door het niveau
    cs = row.get("CLOSE_STRENGTH", np.nan)
    if not pd.isna(cs):
        if cs >= 0.7:
            score += 20; redenen.append("beslissende slotkoers, hoog in de dagrange")
        elif cs >= 0.5:
            score += 10; redenen.append("redelijke slotkoers")
        else:
            redenen.append("zwakke slotkoers (lont) - verhoogd risico op mislukking")

    # 4. weektrend loopt mee
    wk = compute_weekly_confirmation(df)
    if wk["weekly_uptrend"]:
        score += 15; redenen.append("weektrend bevestigt")
    elif wk["weekly_uptrend"] is False:
        redenen.append("weektrend loopt NIET mee - breakouts tegen de hogere trend falen vaker")

    # 5. ruimte tot de volgende weerstand
    room = compute_overhead_resistance(df)
    if pd.isna(room):
        score += 15; redenen.append("geen weerstand boven (vrije baan)")
    elif room >= 0.10:
        score += 12; redenen.append(f"{room*100:.0f}% ruimte tot de volgende weerstand")
    elif room >= 0.05:
        score += 6; redenen.append(f"{room*100:.0f}% ruimte tot de volgende weerstand")
    else:
        redenen.append(f"weerstand al op {room*100:.0f}% - weinig swingruimte")

    return round(min(100.0, score), 1), redenen


def detect_coiling_setup(df, row):
    """PRE-BREAKOUT DETECTIE - het aandeel herkennen terwijl het zich OPLAADT,
    niet nadat het al gesprongen is.

    Dit is bewust het SPIEGELBEELD van de gewone scanner:
      gewone scanner              deze modus
      -------------------------   ---------------------------
      RVOL > 2 (volumepiek)       volume DROOGT OP
      koers BOVEN de pivot        koers NET ONDER de pivot
      breakout al gebeurd         breakout moet nog komen

    De reden: de benchmark toonde dat instappen NA de sprong systematisch op
    lokale toppen landt. Wie het patroon herkent terwijl het samendrukt, koopt
    op het uitbraakpunt zelf in plaats van er 5% boven.

    Retourneert een dict met de losse kenmerken plus een score 0-100.
    """
    kenmerken = {}
    score = 0.0

    # --- 1. VOLUME DROOGT OP (het belangrijkste pre-breakout signaal) ---
    # Tijdens een gezonde consolidatie verliezen verkopers interesse: het
    # volume zakt weg. Dat is het tegenovergestelde van wat de gewone scanner zoekt.
    vol_recent = df["Volume"].iloc[-5:].mean()
    vol_basis = df["Volume"].iloc[-30:-5].mean()
    vol_ratio = vol_recent / vol_basis if vol_basis > 0 else 1.0
    kenmerken["volume_dryup_ratio"] = round(vol_ratio, 2)
    if vol_ratio < 0.6:
        score += 25; kenmerken["volume_dryup"] = "sterk"
    elif vol_ratio < 0.8:
        score += 18; kenmerken["volume_dryup"] = "aanwezig"
    elif vol_ratio < 1.0:
        score += 8; kenmerken["volume_dryup"] = "licht"
    else:
        kenmerken["volume_dryup"] = "geen (volume neemt toe)"

    # --- 2. RANGE TREKT SAMEN (volatility contraction) ---
    rng = (df["High"] - df["Low"]) / df["Close"]
    rng_recent = rng.iloc[-5:].mean()
    rng_basis = rng.iloc[-30:-5].mean()
    rng_ratio = rng_recent / rng_basis if rng_basis > 0 else 1.0
    kenmerken["range_contraction_ratio"] = round(rng_ratio, 2)
    if rng_ratio < 0.6:
        score += 25; kenmerken["range_contraction"] = "sterk"
    elif rng_ratio < 0.8:
        score += 18; kenmerken["range_contraction"] = "aanwezig"
    elif rng_ratio < 1.0:
        score += 8; kenmerken["range_contraction"] = "licht"
    else:
        kenmerken["range_contraction"] = "geen"

    # --- 3. KOERS COILT VLAK ONDER DE WEERSTAND ---
    # Ideaal: 0-4% onder het uitbraakpunt. Boven de pivot = te laat (dat is
    # precies de fout die de gewone scanner maakt).
    pivot = row.get("HIGH20", np.nan)
    close = row["Close"]
    if not pd.isna(pivot) and pivot > 0:
        afstand = (pivot - close) / pivot
        kenmerken["afstand_tot_pivot_pct"] = round(afstand * 100, 2)
        if -0.005 <= afstand <= 0.04:
            score += 25; kenmerken["positie"] = "vlak onder de pivot (ideaal)"
        elif 0.04 < afstand <= 0.10:
            score += 12; kenmerken["positie"] = "nadert de pivot"
        elif afstand < -0.005:
            kenmerken["positie"] = "AL BOVEN de pivot (te laat)"
        else:
            kenmerken["positie"] = "nog ver van de pivot"
    else:
        kenmerken["positie"] = "onbekend"

    # --- 4. UPTREND MOET INTACT ZIJN ---
    # Een consolidatie is alleen interessant binnen een opgaande trend;
    # anders is het gewoon een aandeel dat stilligt na een daling.
    boven_ma = (close > row.get("SMA50", np.inf)) if not pd.isna(row.get("SMA50", np.nan)) else False
    ma_gestapeld = False
    try:
        ma_gestapeld = row["SMA10"] > row["SMA21"] > row["SMA50"]
    except Exception:
        pass
    if boven_ma and ma_gestapeld:
        score += 15; kenmerken["trend"] = "uptrend intact, MA's gestapeld"
    elif boven_ma:
        score += 8; kenmerken["trend"] = "boven SMA50"
    else:
        kenmerken["trend"] = "geen uptrend"

    # --- 5. NIET IN VRIJE VAL / geen recente crash ---
    laatste_10d = df["Close"].pct_change().iloc[-10:]
    if laatste_10d.min() < -0.12:
        score -= 15; kenmerken["waarschuwing"] = "recente forse daling"

    # --- 6. BOLLINGER-SQUEEZE als bevestiging ---
    if row.get("BB_SQUEEZE", False):
        score += 10; kenmerken["bollinger"] = "squeeze actief"

    kenmerken["score"] = round(max(0.0, min(100.0, score)), 1)
    return kenmerken


def bereken_leesbaarheid(df, lookback=30):
    """CLEAN PRICE ACTION - meet of een grafiek leesbaar is of een barcode.

    Twee maten die samen vangen wat een trader bedoelt met "schone chart":

    1. EFFICIENCY RATIO (Kaufman): netto koersbeweging gedeeld door de totale
       afgelegde weg. Een aandeel dat van 10 naar 15 gaat in een rechte lijn
       scoort ~1.0. Eentje dat via 12-9-14-11-15 hetzelfde eindpunt haalt
       scoort veel lager - zelfde uitkomst, maar onleesbaar verlopen.

    2. RICHTINGSWISSELINGEN: hoe vaak draait de koers van omhoog naar omlaag
       binnen de periode. Veel wisselingen = barcode-achtig gedrag.

    Retourneert een score 0-100 waarbij hoog = goed leesbaar.
    """
    if len(df) < lookback + 1:
        return None
    venster = df["Close"].iloc[-lookback:]
    netto = abs(venster.iloc[-1] - venster.iloc[0])
    weg = venster.diff().abs().sum()
    efficiency = (netto / weg) if weg > 0 else 0.0

    richtingen = np.sign(venster.diff().dropna())
    wisselingen = int((richtingen.diff().abs() > 0).sum())
    wissel_ratio = wisselingen / len(richtingen) if len(richtingen) > 0 else 1.0

    # efficiency telt zwaarder: dat is de kern van "leesbaar"
    eff_score = min(100.0, efficiency * 250)          # 0.40 efficiency -> 100
    wissel_score = max(0.0, (1 - wissel_ratio) * 200)  # weinig wisselingen -> hoog
    return {
        "efficiency": round(efficiency, 3),
        "wissel_ratio": round(wissel_ratio, 3),
        "score": round(min(100.0, eff_score * 0.7 + wissel_score * 0.3), 1),
    }


def compute_indicators(df, spy_close=None):
    df = df.copy()
    df["RSI"] = rsi(df["Close"], RSI_PERIOD)
    df["MACD"], df["MACD_signal"], df["MACD_hist"] = macd(df["Close"], MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    df["SMA10"] = df["Close"].rolling(10).mean()
    df["SMA21"] = df["Close"].rolling(21).mean()
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
    df["ATR"] = atr(df, ATR_PERIOD)
    df["ATR_PCT"] = df["ATR"] / df["Close"]
    df["HIGH20"] = df["High"].rolling(20).max().shift(1)

    # --- entry-kwaliteit: hoe ver staat de koers boven het uitbraakpunt? ---
    df["EXTENSION_PCT"] = (df["Close"] - df["HIGH20"]) / df["HIGH20"]

    # --- structuur-stop: dieptepunt van de recente consolidatie ---
    df["STRUCT_LOW"] = df["Low"].rolling(STRUCTURE_STOP_LOOKBACK).min()

    # --- trend-template (Minervini): langere MA's + 52-weeks positie ---
    df["SMA150"] = df["Close"].rolling(150).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()
    df["SMA200_RISING"] = df["SMA200"] > df["SMA200"].shift(21)  # stijgend over ~1 maand
    df["HIGH_52W"] = df["High"].rolling(252, min_periods=100).max()
    df["LOW_52W"] = df["Low"].rolling(252, min_periods=100).min()
    df["PCT_FROM_52W_HIGH"] = (df["Close"] - df["HIGH_52W"]) / df["HIGH_52W"]   # 0 = op de top
    df["PCT_ABOVE_52W_LOW"] = (df["Close"] - df["LOW_52W"]) / df["LOW_52W"]

    # --- pocket-pivot volume: overtreft het up-volume het grootste down-volume ---
    # van de laatste 10 dagen? Dat is een strengere accumulatie-check dan RVOL
    # t.o.v. een gemiddelde, omdat het expliciet koop- tegen verkoopdruk afzet.
    is_down_day = df["Close"] < df["Close"].shift(1)
    down_vol_only = df["Volume"].where(is_down_day, 0)
    df["MAX_DOWN_VOL_10D"] = down_vol_only.rolling(10).max()
    df["POCKET_PIVOT"] = (df["Close"] > df["Close"].shift(1)) & (df["Volume"] > df["MAX_DOWN_VOL_10D"])

    # --- EMA naast SMA: reageert sneller op een kentering ---
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    # lange EMA's - alleen gebruikt in de trendfilter-test, om te meten of ze
    # iets toevoegen. LET OP: EMA300 vraagt ~15 maanden historie; jongere
    # aandelen vallen daardoor af, wat op zichzelf al een filter is.
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False, min_periods=200).mean()
    df["EMA300"] = df["Close"].ewm(span=300, adjust=False, min_periods=300).mean()

    # --- ADX: trendKRACHT (los van trendRICHTING en van R2) ---
    df["ADX"], df["PLUS_DI"], df["MINUS_DI"] = adx(df, 14)

    # --- MFI: volume-gewogen momentum ---
    df["MFI"] = money_flow_index(df, 14)

    # --- Bollinger Bands + squeeze-detectie ---
    bb_mid = df["Close"].rolling(20).mean()
    bb_std = df["Close"].rolling(20).std()
    df["BB_UPPER"] = bb_mid + 2 * bb_std
    df["BB_LOWER"] = bb_mid - 2 * bb_std
    df["BB_WIDTH"] = (df["BB_UPPER"] - df["BB_LOWER"]) / bb_mid
    # squeeze = bandbreedte in het laagste kwart van de afgelopen 6 maanden;
    # samengeknepen volatiliteit gaat vaak vooraf aan een uitbraak
    df["BB_SQUEEZE"] = df["BB_WIDTH"] < df["BB_WIDTH"].rolling(126, min_periods=40).quantile(0.25)

    # --- Marktstructuur: hogere toppen en hogere bodems (Dow-theorie) ---
    swing_high = df["High"].rolling(10).max()
    swing_low = df["Low"].rolling(10).min()
    df["HIGHER_HIGH"] = swing_high > swing_high.shift(10)
    df["HIGHER_LOW"] = swing_low > swing_low.shift(10)
    df["MARKET_STRUCTURE_UP"] = df["HIGHER_HIGH"] & df["HIGHER_LOW"]

    # --- Gap-analyse ---
    df["GAP_PCT"] = (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)
    df["GAP_UP"] = df["GAP_PCT"] > 0.02

    # --- VWAP over 20 dagen (benadering op dagdata) ---
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP20"] = (typical * df["Volume"]).rolling(20).sum() / df["Volume"].rolling(20).sum()
    df["ABOVE_VWAP"] = df["Close"] > df["VWAP20"]

    # leesbaarheid ("clean price action") als rollende kolom
    rng_close = df["Close"]
    netto30 = (rng_close - rng_close.shift(30)).abs()
    weg30 = rng_close.diff().abs().rolling(30).sum()
    df["EFFICIENCY"] = (netto30 / weg30.replace(0, np.nan)).fillna(0)
    richting = np.sign(rng_close.diff())
    df["WISSEL_RATIO"] = (richting.diff().abs() > 0).rolling(30).mean()

    day_range_pct = (df["High"] - df["Low"]) / df["Close"]
    recent_range = day_range_pct.rolling(10).mean()
    prior_range = day_range_pct.shift(10).rolling(10).mean()
    df["VCP_CONTRACTION"] = recent_range < prior_range

    rng = (df["High"] - df["Low"]).replace(0, np.nan)
    df["CLOSE_STRENGTH"] = (df["Close"] - df["Low"]) / rng

    df["OBV"] = obv(df)
    df["OBV_SLOPE20"] = df["OBV"].diff(20)

    # up/down-volume ratio over 10 dagen (accumulatie-proxy)
    up_day = df["Close"].diff() > 0
    down_day = df["Close"].diff() < 0
    up_vol = (df["Volume"].where(up_day, 0)).rolling(10).sum()
    down_vol = (df["Volume"].where(down_day, 0)).rolling(10).sum().replace(0, np.nan)
    df["UPDOWN_VOL_RATIO"] = up_vol / down_vol

    if spy_close is not None:
        if isinstance(spy_close, pd.DataFrame):
            spy_close = spy_close.iloc[:, 0]
        for n in (10, 20, 60):
            stock_ret = df["Close"].pct_change(n)
            spy_ret = spy_close.pct_change(n).reindex(df.index)
            df[f"RS_{n}D"] = stock_ret - spy_ret
    else:
        for n in (10, 20, 60):
            df[f"RS_{n}D"] = np.nan

    # trend-kwaliteit (rolling toegepast op laatste 20 dagen op elk punt is
    # duur; we berekenen 'm daarom losstaand per rij in de scan/backtest-loop
    # i.p.v. als kolom, om onnodige rekentijd te besparen)
    return df


_FUNDAMENTALS_CACHE = {}


def get_fundamentals(ticker):
    """Haalt fundamentals op, met cache binnen dezelfde run.

    Waarom caching nodig is: deze functie doet een losse netwerkoproep per
    ticker en wordt op 20 plekken aangeroepen. In de backtests wordt dezelfde
    ticker honderden keren opgevraagd, elke keer opnieuw over het netwerk.
    De gegevens veranderen niet tijdens een run, dus een cache scheelt veel
    tijd zonder dat de uitkomst verandert."""
    if ticker in _FUNDAMENTALS_CACHE:
        return _FUNDAMENTALS_CACHE[ticker]
    try:
        info = yf.Ticker(ticker).get_info()
        resultaat = {
            "float": info.get("floatShares"),
            "market_cap": info.get("marketCap"),
            "short_pct_float": info.get("shortPercentOfFloat"),  # squeeze-dynamiek
            "avg_volume": info.get("averageVolume"),
        }
    except Exception:
        resultaat = {"float": None, "market_cap": None,
                     "short_pct_float": None, "avg_volume": None}
    _FUNDAMENTALS_CACHE[ticker] = resultaat
    return resultaat


def get_recent_catalyst_info(ticker, lookback_days=14):
    """Korte-termijn-relevante 'fundamentals': is er de LAATSTE ~2 weken een
    concrete aanleiding geweest (earnings-beat, analist-upgrade)? Dit is
    bewust ANDERS dan lange-termijn fundamentals (omzetgroei, institutioneel
    eigendomsniveau) - die zeggen weinig over een trade van een paar dagen.
    Alleen zinvol voor de LIVE scan; voor de backtest is hier geen betrouwbare
    historische reconstructie van te maken via yfinance (zelfde beperking als
    de earnings-blackout-filter)."""
    result = {"earnings_surprise_pct": None, "days_since_earnings": None, "recent_upgrade": False}
    try:
        t = yf.Ticker(ticker)
        edates = t.get_earnings_dates(limit=8)
        if edates is not None and len(edates) > 0:
            now = pd.Timestamp.today()
            past = edates[edates.index <= now].sort_index(ascending=False)
            if len(past) > 0:
                days_since = (now - past.index[0]).days
                surprise = None
                for col in ("Surprise(%)", "surprisePercent"):
                    if col in past.columns:
                        val = past.iloc[0][col]
                        surprise = float(val) if pd.notna(val) else None
                        break
                result["days_since_earnings"] = days_since
                result["earnings_surprise_pct"] = surprise
    except Exception:
        pass

    try:
        t = yf.Ticker(ticker)
        upgrades = getattr(t, "upgrades_downgrades", None)
        if upgrades is not None and len(upgrades) > 0:
            cutoff = pd.Timestamp.today() - pd.Timedelta(days=lookback_days)
            idx = upgrades.index if not isinstance(upgrades.index, pd.RangeIndex) else pd.to_datetime(upgrades.get("GradeDate", []))
            recent = upgrades[idx >= cutoff] if len(idx) == len(upgrades) else upgrades.iloc[:0]
            if "Action" in recent.columns:
                result["recent_upgrade"] = bool((recent["Action"].astype(str).str.lower() == "up").any())
            elif len(recent) > 0:
                result["recent_upgrade"] = True
    except Exception:
        pass

    return result


_EARNINGS_CACHE = {}


def get_next_earnings_gap_days(ticker, as_of_date=None):
    """Aantal kalenderdagen tot de eerstvolgende bekende earnings-datum.
    None als onbekend/niet op te halen (dan slaan we de earnings-check over
    i.p.v. de ticker onterecht te blokkeren).

    Gecachet binnen dezelfde run: dit is een losse netwerkoproep per ticker
    en de earnings-datum verandert niet tijdens een scan."""
    sleutel = (ticker, str(as_of_date))
    if sleutel in _EARNINGS_CACHE:
        return _EARNINGS_CACHE[sleutel]
    try:
        t = yf.Ticker(ticker)
        edates = t.get_earnings_dates(limit=8)
        if edates is None or len(edates) == 0:
            _EARNINGS_CACHE[sleutel] = None
            return _EARNINGS_CACHE[sleutel]
        ref = pd.Timestamp(as_of_date) if as_of_date is not None else pd.Timestamp.today()
        future = edates.index[edates.index >= ref]
        if len(future) == 0:
            _EARNINGS_CACHE[sleutel] = None
            return _EARNINGS_CACHE[sleutel]
        _EARNINGS_CACHE[sleutel] = (future.min() - ref).days
        return _EARNINGS_CACHE[sleutel]
    except Exception:
        _EARNINGS_CACHE[sleutel] = None
        return _EARNINGS_CACHE[sleutel]


def get_nasdaq_universe(max_size=MAX_UNIVERSE_SIZE):
    try:
        df = pd.read_csv(NASDAQ_LISTED_URL, sep="|")
        df = df[df["Test Issue"] == "N"]
        if "ETF" in df.columns:
            df = df[df["ETF"] == "N"]
        symbols = df["Symbol"].dropna().astype(str).tolist()
        symbols = [s for s in symbols if s.isalpha() and 1 <= len(s) <= 5]
        if max_size and len(symbols) > max_size:
            symbols = symbols[:max_size]
        print(f"NASDAQ-universum opgehaald: {len(symbols)} tickers (gecapt op max {max_size})")
        return symbols
    except Exception as e:
        print(f"Kon de NASDAQ-lijst niet ophalen ({e}). Val terug op de vaste watchlist.")
        return list(WATCHLIST)


# ============================================================================
# MARKTREGIME / SECTOR / SLIPPAGE / EXIT-SIMULATIE
# ============================================================================

def is_market_regime_bullish(spy_series, as_of_index=None):
    """True als SPY boven zijn eigen SMA(REGIME_SMA_PERIOD) sluit op de
    referentiedatum. Simpele, veelgebruikte 'is de markt uberhaupt gezond'-
    check (vergelijkbaar met wat bv. IBD's 'market direction'-concept doet)."""
    s = spy_series if as_of_index is None else spy_series.iloc[:as_of_index + 1]
    if len(s) < REGIME_SMA_PERIOD:
        return True  # onvoldoende data -> niet onterecht blokkeren
    sma = s.rolling(REGIME_SMA_PERIOD).mean().iloc[-1]
    return bool(s.iloc[-1] > sma)


def get_dynamic_slippage(dollar_volume):
    """Hoe lager de dollar-volume (liquiditeit), hoe groter de aanname
    van slippage bij een stop-loss - realistischer dan 1 vast percentage
    voor alle tickers."""
    if dollar_volume is None:
        dollar_volume = 0
    for threshold, pct in SLIPPAGE_TIERS:
        if dollar_volume >= threshold:
            return pct
    return SLIPPAGE_TIERS[-1][1]


def get_sector_etf(ticker):
    return SECTOR_ETF.get(ticker, DEFAULT_SECTOR_ETF)


def add_sector_rs(df, sector_close, spy_close):
    """Voegt RS-kolommen toe t.o.v. de SECTOR-ETF (i.p.v. alleen SPY).
    Een aandeel dat zijn eigen sector verslaat is een sterker signaal dan
    eentje dat alleen de brede markt verslaat."""
    df = df.copy()
    if sector_close is not None:
        if isinstance(sector_close, pd.DataFrame):
            sector_close = sector_close.iloc[:, 0]
        for n in (10, 20, 60):
            stock_ret = df["Close"].pct_change(n)
            sector_ret = sector_close.pct_change(n).reindex(df.index)
            df[f"RS_SECTOR_{n}D"] = stock_ret - sector_ret
    else:
        for n in (10, 20, 60):
            df[f"RS_SECTOR_{n}D"] = np.nan
    return df


def simulate_trailing_exit(future_df, entry, atr_initial, preset, initial_stop=None):
    """Simuleert een trade dag-voor-dag i.p.v. een vaste hold-periode:
    - initiele stop = entry - STOP_ATR_MULT * ATR
    - zodra prijs 1x het risico in de plus staat: neem PARTIAL_EXIT_FRACTION
      winst, verplaats stop naar breakeven voor de rest
    - trailing: de stop mag daarna alleen omhoog (nooit omlaag) meebewegen
      met (close - STOP_ATR_MULT * ATR_die_dag)
    - stopt uiterlijk na MAX_HOLD_DAYS dagen (sluit op de laatste close)

    Retourneert (rendement_%_blended, outcome_str, dagen_gehouden).
    """
    stop = (entry - STOP_ATR_MULT * atr_initial) if initial_stop is None else initial_stop
    initial_risk = entry - stop
    partial_taken = False
    partial_return = None
    remaining_fraction = 1.0

    n_days = min(MAX_HOLD_DAYS, len(future_df))
    for day_idx in range(n_days):
        day = future_df.iloc[day_idx]

        # 1. is de (huidige) stop geraakt?
        if day["Low"] <= stop:
            final_return = (stop - entry) / entry * 100
            if partial_taken:
                blended = partial_return * PARTIAL_EXIT_FRACTION + final_return * (1 - PARTIAL_EXIT_FRACTION)
            else:
                blended = final_return
            return blended, ("stop_na_partial" if partial_taken else "stop"), day_idx + 1

        # 2. partial-exit trigger (nog niet genomen)
        if not partial_taken and day["High"] >= entry + PARTIAL_EXIT_AT_R * initial_risk:
            partial_return = (entry + PARTIAL_EXIT_AT_R * initial_risk - entry) / entry * 100
            partial_taken = True
            if BREAKEVEN_AFTER_PARTIAL:
                stop = max(stop, entry)

        # 3. trail de stop omhoog (nooit omlaag) o.b.v. de ATR van die dag
        if not pd.isna(day.get("ATR", np.nan)):
            new_stop = day["Close"] - STOP_ATR_MULT * day["ATR"]
            stop = max(stop, new_stop)

    # geen stop geraakt binnen MAX_HOLD_DAYS -> sluiten op de laatste close
    last_close = future_df["Close"].iloc[n_days - 1]
    final_return = (last_close - entry) / entry * 100
    if partial_taken:
        blended = partial_return * PARTIAL_EXIT_FRACTION + final_return * (1 - PARTIAL_EXIT_FRACTION)
    else:
        blended = final_return
    return blended, ("tijd_na_partial" if partial_taken else "tijd"), n_days


# ============================================================================
# POSITIE-TRACKER: dagelijkse trailing-stop-status voor LOPENDE trades
# ============================================================================
# De backtest hierboven bewijst dat de winstgevendheid van deze strategie
# vrijwel volledig zit in de trailing-stop/partial-exit-trades. Maar de
# dagelijkse scan geeft alleen entry/stop/target voor VANDAAG - hij zegt
# niks over hoe je een positie op dag 2, 3, ... zou moeten bijsturen. Deze
# module lost dat op: jij logt wat je kocht, en --positions herberekent
# elke dag de actuele trailing-stop met exact dezelfde logica als de backtest.

POSITIONS_FILE = "positions.csv"

# Versie-marker: verschijnt bovenaan elke run, zodat je altijd kunt zien of je
# de meest recente versie van dit bestand draait (en niet per ongeluk een oude).
SCRIPT_VERSIE = "2026-08-06-n  (scan ~10x sneller, zelfde uitkomst)"


def compute_live_position_status(price_since_entry, entry, atr_initial, initial_stop=None):
    """Zelfde dag-voor-dag logica als simulate_trailing_exit, maar voor een
    NOG NIET afgesloten positie: stopt bij de laatste beschikbare dag i.p.v.
    een vaste horizon, en geeft de HUIDIGE status terug in plaats van een
    eindresultaat."""
    stop = (entry - STOP_ATR_MULT * atr_initial) if initial_stop is None else initial_stop
    initial_risk = entry - stop
    partial_taken = False

    for day_idx in range(len(price_since_entry)):
        day = price_since_entry.iloc[day_idx]
        days_held = day_idx + 1

        if day["Low"] <= stop:
            return {
                "final": True,
                "status": "GESLOTEN (stop geraakt)",
                "exit_price": round(stop, 2),
                "exit_date": price_since_entry.index[day_idx],
                "days_held": days_held,
            }

        if not partial_taken and day["High"] >= entry + PARTIAL_EXIT_AT_R * initial_risk:
            partial_taken = True
            if BREAKEVEN_AFTER_PARTIAL:
                stop = max(stop, entry)

        if not pd.isna(day.get("ATR", np.nan)):
            stop = max(stop, day["Close"] - STOP_ATR_MULT * day["ATR"])

        if days_held >= MAX_HOLD_DAYS:
            return {
                "final": True,
                "status": "GESLOTEN (tijdslimiet bereikt)",
                "exit_price": round(day["Close"], 2),
                "exit_date": price_since_entry.index[day_idx],
                "days_held": days_held,
            }

    last_day = price_since_entry.iloc[-1]
    return {
        "final": False,
        "status": "NOG OPEN - houd aan",
        "current_price": round(last_day["Close"], 2),
        "current_stop": round(stop, 2),
        "partial_taken": partial_taken,
        "days_held": len(price_since_entry),
        "unrealized_pct": round((last_day["Close"] - entry) / entry * 100, 2),
    }


def add_position(ticker, entry_price, shares):
    """Voegt een nieuwe LOPENDE positie toe aan positions.csv. De ATR van
    vandaag wordt gebruikt als benadering van de ATR op het moment van kopen
    (redelijk voor een positie die net vandaag/gisteren geopend is)."""
    try:
        df = yf.download(ticker, period="3mo", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        df = compute_indicators(df)
        atr = df["ATR"].iloc[-1]
        if pd.isna(atr):
            print(f"Kon geen betrouwbare ATR bepalen voor {ticker} - probeer het later opnieuw.")
            return
    except Exception as e:
        print(f"Kon data voor {ticker} niet ophalen: {e}")
        return

    entry_date = datetime.now().strftime("%Y-%m-%d")
    last_row = df.iloc[-1]
    initial_stop = compute_stop(last_row, float(entry_price))
    row = pd.DataFrame([{
        "Ticker": ticker, "EntryDate": entry_date, "EntryPrice": float(entry_price),
        "InitialATR": round(float(atr), 4), "InitialStop": round(float(initial_stop), 4),
        "Shares": int(shares), "Status": "open",
    }])
    header = not pd.io.common.file_exists(POSITIONS_FILE)
    row.to_csv(POSITIONS_FILE, mode="a", header=header, index=False)
    print(f"Positie toegevoegd: {ticker}  entry={entry_price}  shares={shares}  "
          f"ATR={atr:.2f}  initiele stop={initial_stop:.2f} "
          f"({(float(entry_price)-initial_stop)/float(entry_price)*100:.1f}% risico)")
    print(f"Opgeslagen in {POSITIONS_FILE}. Gebruik --positions om 'm dagelijks te updaten.")


def track_positions():
    """Herberekent voor elke OPEN positie in positions.csv de actuele
    trailing-stop-status, met dezelfde logica als de backtest-simulatie."""
    try:
        positions = pd.read_csv(POSITIONS_FILE)
    except Exception:
        print(f"Geen {POSITIONS_FILE} gevonden. Voeg eerst een positie toe met:")
        print("  python swing_scanner.py --add-position TICKER PRIJS AANTAL")
        return

    open_mask = positions["Status"] == "open"
    if open_mask.sum() == 0:
        print("Geen open posities in positions.csv.")
        return

    print(f"{open_mask.sum()} open positie(s):\n")
    for idx in positions[open_mask].index:
        pos = positions.loc[idx]
        ticker = pos["Ticker"]
        try:
            df = yf.download(ticker, start=pos["EntryDate"], auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna()
            if len(df) < 2:
                print(f"[{ticker}] nog geen nieuwe koersdata sinds entry-datum, morgen opnieuw proberen.\n")
                continue
            df = compute_indicators(df)
            future = df.iloc[1:]  # eerste rij = entry-dag zelf, niet meerekenen

            saved_stop = pos["InitialStop"] if "InitialStop" in pos.index and not pd.isna(pos["InitialStop"]) else None
            status = compute_live_position_status(
                future, pos["EntryPrice"], pos["InitialATR"], initial_stop=saved_stop)
            print(f"[{ticker}]  entry={pos['EntryPrice']}  shares={pos['Shares']}  status: {status['status']}")
            if status["final"]:
                pnl_pct = (status["exit_price"] - pos["EntryPrice"]) / pos["EntryPrice"] * 100
                print(f"    -> Exit rond {status['exit_price']} op {status['exit_date'].date()} "
                      f"({status['days_held']} dagen gehouden, {pnl_pct:+.2f}%)")
                print(f"    Zet Status op 'closed' in {POSITIONS_FILE} zodra je 'm echt verkocht hebt.")
                positions.loc[idx, "Status"] = "review"  # vraagt bevestiging i.p.v. automatisch te sluiten
            else:
                print(f"    Huidige koers: {status['current_price']}  |  Nieuwe stop: {status['current_stop']}  "
                      f"|  Ongerealiseerd: {status['unrealized_pct']:+.2f}%")
                print(f"    Partial-exit genomen: {'ja' if status['partial_taken'] else 'nee'}  |  "
                      f"Dagen gehouden: {status['days_held']}/{MAX_HOLD_DAYS}")
            print()
        except Exception as e:
            print(f"[{ticker}] fout bij bijwerken: {e}\n")

    positions.to_csv(POSITIONS_FILE, index=False)
    print("(status 'review' = het script adviseert te sluiten, maar sluit 'm niet zelf af -")
    print(" pas de Status-kolom in positions.csv handmatig aan naar 'closed' zodra je verkocht hebt)")


# ============================================================================
# HARDE FILTERS (uitsluiten, ongeacht confidence-score)
# ============================================================================

def hard_filter_liquidity_price(row, fund, preset):
    """Sluit micro-caps, illiquide en te goedkope/dure namen uit.
    Doel: pump-and-dump-gevoelige aandelen (dun verhandeld, laag market cap)
    buiten de deur houden."""
    price = row["Close"]
    if not (MIN_PRICE <= price <= MAX_PRICE):
        return False, "prijs buiten range"
    if fund["market_cap"] and fund["market_cap"] < preset["MIN_MARKET_CAP"]:
        return False, f"market cap onder {preset['MIN_MARKET_CAP']/1e6:.0f}M (te klein/manipulatiegevoelig)"
    max_float = preset.get("MAX_FLOAT")  # alleen actief als de preset dit expliciet instelt
    if max_float and fund["float"] and fund["float"] > max_float:
        return False, f"float boven {max_float/1e6:.0f}M (te groot voor deze preset)"
    # gebruik het MAXIMUM van fundamentals-avg_volume (kan maanden achterlopen)
    # en de snellere VOL_SMA20 (reageert binnen 20 dagen) - een net ontwaakt
    # aandeel toont zijn nieuwe liquiditeit eerder in VOL_SMA20 dan in yfinance's
    # (trage) 'averageVolume'-veld.
    avg_vol = max(fund["avg_volume"] or 0, row["VOL_SMA20"] or 0)
    if avg_vol and price * avg_vol < preset["MIN_DOLLAR_VOLUME"]:
        return False, "te weinig dollar-volume (illiquide)"
    return True, ""


def hard_filter_pump_dump(df, row, preset):
    """Sluit verdachte single-day spikes uit: een enorme koersbeweging op
    1 dag (vaak reverse split, nieuws-flash-crash-herstel, of manipulatie)
    is geen betrouwbare swing-setup, ook al zou de score hoog uitvallen."""
    recent = df["Close"].pct_change().tail(5)
    if recent.abs().max() > preset["MAX_SINGLE_DAY_MOVE"]:
        return False, f"extreme 1-dag beweging (>{preset['MAX_SINGLE_DAY_MOVE']*100:.0f}%) - pump/dump-risico"
    return True, ""


def hard_filter_rvol(row, preset):
    """RVOL_MIN stond al in elke preset gedefinieerd maar werd nergens
    daadwerkelijk afgedwongen - dit was dode config. Nu een echte harde eis:
    zonder een aantoonbare volume-piek is er simpelweg geen reden om aan te
    nemen dat er 'iets aan de hand is' met dit aandeel vandaag."""
    rvol = row["Volume"] / row["VOL_SMA20"] if row["VOL_SMA20"] else 0
    if rvol < preset["RVOL_MIN"]:
        return False, f"RVOL {rvol:.1f}x onder de vereiste {preset['RVOL_MIN']}x"
    return True, ""


def compute_stop(row, entry=None):
    """Bepaalt de stop-loss. Combineert 3 principes:
      1. ATR-gebaseerd (volatiliteit)  - de oude methode
      2. Structuur-gebaseerd: net onder het dieptepunt van de recente
         consolidatie. Daar is de setup namelijk feitelijk mislukt, en dat is
         waar Minervini/O'Neil hun stop plaatsen (typisch 3-7% risico).
      3. Harde limiet: nooit meer dan MAX_STOP_PCT risico, ongeacht wat 1 en 2
         zeggen. Voorkomt dat een volatiel aandeel een absurd wijde stop krijgt.

    We nemen de KRAPSTE (hoogste) van 1 en 2, en begrenzen daarna op 3.
    Krapper = kleinere verliezers, maar ook meer kans om uitgestopt te worden
    op ruis; de MAX_STOP_PCT-limiet is de belangrijkste bescherming tegen de
    grote verliezers die we in de backtest zagen."""
    entry = row["Close"] if entry is None else entry
    atr_stop = entry - STOP_ATR_MULT * row["ATR"]

    if USE_STRUCTURE_STOP:
        struct_low = row.get("STRUCT_LOW", np.nan)
        if not pd.isna(struct_low) and struct_low < entry:
            struct_stop = struct_low * (1 - STRUCTURE_STOP_BUFFER)
            stop = max(atr_stop, struct_stop)  # krapste van de twee
        else:
            stop = atr_stop
    else:
        stop = atr_stop

    # harde risicolimiet
    min_allowed_stop = entry * (1 - MAX_STOP_PCT)
    stop = max(stop, min_allowed_stop)

    # veiligheid: stop moet altijd onder de entry liggen
    if stop >= entry:
        stop = entry * (1 - MAX_STOP_PCT)
    return stop


def hard_filter_extension(row, preset):
    """Weigert setups waar de koers al te ver BOVEN het uitbraakpunt (pivot)
    staat. Dit was het grootste gat in deze scanner: er werd wel gecheckt DAT
    er een breakout was, nooit hoe ver de koers er al boven stond.

    Waarom dit ertoe doet (O'Neil/Minervini): koop je 10% boven de pivot en
    valt de koers normaal terug naar die pivot, dan word je uitgestopt terwijl
    de breakout eigenlijk intact is. Je stop-afstand zwelt op, je risk/reward
    verslechtert, en je verliezers worden groter - precies het patroon dat we
    in de backtest terugzagen (verliezers gemiddeld -7.6%)."""
    ext = row.get("EXTENSION_PCT", np.nan)
    if pd.isna(ext):
        return True, ""  # geen pivot-data -> niet onterecht blokkeren
    max_ext = preset.get("MAX_EXTENSION", MAX_EXTENSION_ABOVE_PIVOT)
    if ext > max_ext:
        return False, f"te ver boven de pivot ({ext*100:.1f}% > {max_ext*100:.0f}%) - te laat om nog in te stappen"
    return True, ""


def hard_filter_choppiness(df, preset):
    """Sluit zijwaartse/choppy aandelen uit via trend-kwaliteit (R² van een
    lineaire regressie op de laatste 50 dagen - bewust langer dan de VCP-
    consolidatie-periode zelf, anders wordt een rustige consolidatie vóór
    een breakout onterecht als 'choppy' gezien terwijl dat precies is wat
    je zoekt). Lage R² = koers zigzagt zonder duidelijke richting over de
    langere termijn -> dat willen we wel vermijden.

    Presets met REQUIRE_UPTREND=False (zoals 'explosive') slaan deze eis
    over: low-float runners komen vaak "uit het niets" zonder nette
    voorafgaande trend, en dat hier alsnog eisen zou precies de setups
    weren die deze preset juist moet vinden."""
    slope, r2 = linreg_trend(df["Close"], lookback=50)
    if not preset.get("REQUIRE_UPTREND", True):
        return True, "", r2
    if slope <= 0:
        return False, "geen opwaartse trend", r2
    if r2 < preset["TREND_R2_MIN"]:
        return False, f"trend te choppy (R²={r2:.2f} < {preset['TREND_R2_MIN']})", r2
    return True, "", r2


def hard_filter_earnings(ticker, preset, as_of_date=None):
    """Sluit tickers uit met earnings binnen de blackout-periode: een
    earnings-gap kan een technische stop-loss volledig irrelevant maken
    (koers kan er 20%+ doorheen gappen, ongeacht waar je stop lag)."""
    days = get_next_earnings_gap_days(ticker, as_of_date)
    if days is None:
        return True, ""  # onbekend -> niet onterecht blokkeren
    if 0 <= days <= preset["EARNINGS_BLACKOUT_DAYS"]:
        return False, f"earnings over {days} dagen (binnen blackout)"
    return True, ""


# ============================================================================
# MODULES (elk 0-100, samen -> confidence-score)
# ============================================================================

def module_trend(df, r2):
    """Beloont een schone, consistente uptrend (hoge R²), prijsstructuur
    (MA-alignment) EN de klassieke 'trend template' die Minervini gebruikt om
    een echte Stage-2-uptrend te herkennen:
      - koers boven SMA50/150/200, netjes gestapeld (50 > 150 > 200)
      - de 200-daagse zelf stijgend over ~1 maand
      - koers binnen 25% van de 52-weeks top (dicht bij een nieuwe high)
      - koers minstens 25% boven de 52-weeks bodem
    Deze langere-termijn-checks ontbraken volledig: de scanner keek alleen naar
    SMA10/21/50, wat een kortstondig opvlammen niet onderscheidt van een echte,
    door instituten gedragen trend."""
    row = df.iloc[-1]
    score = min(100, r2 * 100) * 0.5  # regressie-kwaliteit weegt nu voor de helft mee

    if row["Close"] > row["SMA10"] > row["SMA21"] > row["SMA50"]:
        score += 10

    # trend-template: lange MA's
    sma150, sma200 = row.get("SMA150", np.nan), row.get("SMA200", np.nan)
    if not pd.isna(sma150) and not pd.isna(sma200):
        if row["Close"] > sma150 and row["Close"] > sma200:
            score += 10
        if row["SMA50"] > sma150 > sma200:
            score += 10
        if row.get("SMA200_RISING", False):
            score += 5

    # trend-template: positie in de 52-weeks range
    pct_from_high = row.get("PCT_FROM_52W_HIGH", np.nan)
    pct_above_low = row.get("PCT_ABOVE_52W_LOW", np.nan)
    if not pd.isna(pct_from_high) and pct_from_high >= -0.25:
        score += 10   # binnen 25% van de 52-weeks top
        if pct_from_high >= -0.05:
            score += 5  # vrijwel op een nieuwe high - het sterkste signaal
    if not pd.isna(pct_above_low) and pct_above_low >= 0.25:
        score += 5

    return round(min(100, score), 1)


def module_momentum(row):
    """RSI in een 'gezonde' zone (55-75) scoort het hoogst - momentum aanwezig
    maar niet uitgeput. RSI >85 wordt bewust AFGESTRAFT: dat is vaker het
    teken van een bijna-uitgebluste pump dan van een gezonde doorzet."""
    rsi_val = row["RSI"]
    if 55 <= rsi_val <= 75:
        base = 85
    elif 45 <= rsi_val < 55:
        base = 55
    elif 75 < rsi_val <= 85:
        base = 45  # extended, verhoogd omslagrisico
    elif rsi_val > 85:
        base = 15  # exhaustion / pump-risico
    else:
        base = 20
    if row["MACD"] > row["MACD_signal"] and row["MACD_hist"] > 0:
        base = min(100, base + 15)
    return round(base, 1)


def module_volume(row):
    """Volume/'institutioneel'-proxy: RVOL (interesse-piek) + OBV-richting
    (accumuleert het volume mee met de trend?) + up/down-volumeratio (wordt
    er meer verhandeld op groene dan op rode dagen?) + pocket pivot. GEEN echte
    orderflow-data - een aanname op basis van geaggregeerd dagvolume.

    De 'pocket pivot' is de strengste van de vier: het eist dat het volume van
    vandaag (een up-dag) HOGER is dan het grootste down-volume van de laatste
    10 dagen. Dat zet koopdruk direct af tegen recente verkoopdruk, in plaats
    van tegen een gemiddelde - een aanzienlijk hardere test voor accumulatie."""
    rvol = row["Volume"] / row["VOL_SMA20"] if row["VOL_SMA20"] else 0
    rvol_score = min(100, (rvol / 5) * 100)

    obv_score = 100 if (not pd.isna(row["OBV_SLOPE20"]) and row["OBV_SLOPE20"] > 0) else 20

    ud_ratio = row.get("UPDOWN_VOL_RATIO", np.nan)
    if pd.isna(ud_ratio):
        ud_score = 50
    else:
        ud_score = min(100, (ud_ratio / 2.0) * 100)

    base = (rvol_score + obv_score + ud_score) / 3

    # Pocket pivot als BONUS, niet als vierde deler. Reden: als vierde
    # component meetellen verlaagde elke setup ZONDER pocket pivot met ~17
    # punten, wat via het confidence-gewicht de effectieve drempel stilletjes
    # met ~3.5 punten verhoogde en het aantal signalen halveerde. Als bonus
    # voegt het onderscheidend vermogen toe zonder de lat ongemerkt te verleggen.
    if row.get("POCKET_PIVOT", False):
        base = min(100, base + 12)

    return round(base, 1)


def module_volatility(row, preset, fund=None):
    """Beloont een 'goldilocks'-band van volatiliteit: genoeg ATR% om
    ergens heen te kunnen bewegen, maar niet zo extreem dat het aandeel
    onbeheersbaar/manipulatiegevoelig is. VCP (samentrekkende range) is
    een bonus - duidt op een opgebouwde, geen achterna-gejaagde, setup.
    Lage float is een STRUCTURELE verklaring waarom een aandeel uberhaupt
    explosief kan bewegen (weinig verhandelbare aandelen = grotere impact
    per order) - vandaar de bonus, los van de ATR% die er vandaag toevallig is."""
    lo, hi = preset["ATR_PCT_RANGE"]
    atr_pct = row["ATR_PCT"]
    if lo <= atr_pct <= hi:
        base = 80
    elif atr_pct > hi:
        base = 35
    else:
        base = 25
    if row.get("VCP_CONTRACTION", False):
        base = min(100, base + 20)
    if row["CLOSE_STRENGTH"] >= 0.65:
        base = min(100, base + 10)
    if fund and fund.get("float"):
        if fund["float"] < 20_000_000:
            base = min(100, base + 20)
        elif fund["float"] < 50_000_000:
            base = min(100, base + 10)
    return round(base, 1)


def module_relative_strength(row):
    """Multi-timeframe RS t.o.v. SPY EN t.o.v. de eigen sector-ETF (10/20/60
    dagen). Een aandeel dat alleen de brede markt verslaat is minder
    overtuigend dan eentje dat ook zijn eigen sectorgenoten verslaat -
    dat laatste wijst eerder op aandeel-specifieke kracht i.p.v. gewoon
    'de hele sector staat er goed voor'."""
    spy_vals = [row.get(f"RS_{n}D", np.nan) for n in (10, 20, 60)]
    sector_vals = [row.get(f"RS_SECTOR_{n}D", np.nan) for n in (10, 20, 60)]

    def sub_score(vals):
        valid = [v for v in vals if not pd.isna(v)]
        if not valid:
            return 50.0
        positive = sum(1 for v in valid if v > 0)
        return (positive / len(valid)) * 100

    spy_score = sub_score(spy_vals)
    sector_score = sub_score(sector_vals)
    return round((spy_score + sector_score) / 2, 1)


def module_catalyst(fund=None, catalyst_info=None):
    """Korte-termijn 'fundamentals': short-squeeze-potentieel (short interest,
    statisch beschikbaar) + recente earnings-beat/analist-upgrade (alleen
    bekend in de live scan, niet reconstrueerbaar in de backtest). Zonder
    data blijft dit netjes neutraal (50) i.p.v. de trade te straffen voor
    iets wat we simpelweg niet konden opzoeken."""
    score = 50.0
    if fund and fund.get("short_pct_float") and fund["short_pct_float"] > 0.20:
        score += 15

    if catalyst_info:
        days = catalyst_info.get("days_since_earnings")
        surprise = catalyst_info.get("earnings_surprise_pct")
        if days is not None and days <= CATALYST_LOOKBACK_DAYS and surprise is not None:
            if surprise > 10:
                score += 25
            elif surprise > 0:
                score += 15
            elif surprise < 0:
                score -= 15
        if catalyst_info.get("recent_upgrade"):
            score += 15

    return round(max(0.0, min(100.0, score)), 1)


def module_structuur(df, row):
    """NIEUWE INFORMATIEDIMENSIE - meet dingen die de andere 6 modules niet
    dekken. Bewust samengesteld uit factoren die iets ANDERS zeggen dan
    momentum/volume/trend, zodat dit geen zevende variant van hetzelfde wordt:

      1. RUIMTE OMHOOG (overhead resistance) - is er een oude top vlak boven
         ons waar verkopers wachten? Dit was de belangrijkste blinde vlek: de
         scanner keek nooit hoeveel ruimte een uitbraak eigenlijk had.
      2. WEEKBEVESTIGING - loopt de weektrend mee met de dagtrend?
      3. ADX - hoe hard duwt de trend (los van hoe recht hij loopt)?
      4. MARKTSTRUCTUUR - hogere toppen en hogere bodems (Dow-theorie)?
      5. BOLLINGER-SQUEEZE - samengeknepen volatiliteit vlak voor de uitbraak?
      6. BOVEN VWAP - handelt het boven de volume-gewogen gemiddelde prijs?
    """
    score = 0.0
    onderdelen = 0

    # 1. ruimte tot de eerstvolgende weerstand
    room = compute_overhead_resistance(df)
    onderdelen += 1
    if pd.isna(room):
        score += 100          # geen weerstand boven ons = vrije baan
    elif room >= 0.15:
        score += 90
    elif room >= 0.08:
        score += 70
    elif room >= 0.04:
        score += 45
    else:
        score += 15           # weerstand vlak boven = weinig swingruimte

    # 2. weekbevestiging
    wk = compute_weekly_confirmation(df)
    onderdelen += 1
    if wk["weekly_uptrend"] is None:
        score += 50
    else:
        deel = 0
        if wk["weekly_uptrend"]:
            deel += 60
        if wk["weekly_above_sma10"]:
            deel += 40
        score += deel

    # 3. ADX - trendkracht
    onderdelen += 1
    adx_val = row.get("ADX", np.nan)
    if pd.isna(adx_val):
        score += 50
    elif adx_val >= 35:
        score += 100
    elif adx_val >= 25:
        score += 80
    elif adx_val >= 20:
        score += 50
    else:
        score += 20

    # 4. marktstructuur
    onderdelen += 1
    score += 100 if row.get("MARKET_STRUCTURE_UP", False) else 30

    # 5. Bollinger-squeeze
    onderdelen += 1
    score += 100 if row.get("BB_SQUEEZE", False) else 55

    # 6. boven VWAP
    onderdelen += 1
    score += 100 if row.get("ABOVE_VWAP", False) else 35

    return round(score / onderdelen, 1)


def compute_confidence(df, row, r2, preset, fund=None, catalyst_info=None):
    """Combineert alle modules tot 1 gewogen confidence-score (0-100)."""
    scores = {
        "trend": module_trend(df, r2),
        "momentum": module_momentum(row),
        "volume": module_volume(row),
        "volatility": module_volatility(row, preset, fund),
        "rs": module_relative_strength(row),
        "catalyst": module_catalyst(fund, catalyst_info),
        "structuur": module_structuur(df, row),
    }
    confidence = sum(scores[k] * MODULE_WEIGHTS[k] for k in scores)
    return round(confidence, 1), scores


# ============================================================================
# EVALUATIE VAN 1 TICKER OP 1 DAG (gedeeld door scan en backtest)
# ============================================================================

def evaluate_ticker_day(ticker, df_upto_today, fund, preset, check_earnings=False, as_of_date=None):
    """Voert alle harde filters + modules uit voor 1 ticker op de laatste
    rij van df_upto_today. Retourneert None als een harde filter faalt,
    anders een dict met score-uitsplitsing."""
    row = df_upto_today.iloc[-1]
    if row[["RSI", "ATR", "VOL_SMA20", "SMA50"]].isna().any():
        return None

    ok, reason = hard_filter_liquidity_price(row, fund, preset)
    if not ok:
        return None

    ok, reason = hard_filter_pump_dump(df_upto_today, row, preset)
    if not ok:
        return None

    ok, reason = hard_filter_rvol(row, preset)
    if not ok:
        return None

    ok, reason = hard_filter_extension(row, preset)
    if not ok:
        return None

    ok, reason, r2 = hard_filter_choppiness(df_upto_today, preset)
    if not ok:
        return None

    if check_earnings:
        ok, reason = hard_filter_earnings(ticker, preset, as_of_date)
        if not ok:
            return None

    # catalyst-info (recente earnings-beat/upgrade) alleen ophalen in de live
    # scan (check_earnings=True) - in de backtest is dit niet betrouwbaar
    # historisch te reconstrueren via yfinance, dus blijft daar neutraal (None).
    catalyst_info = get_recent_catalyst_info(ticker, CATALYST_LOOKBACK_DAYS) if check_earnings else None

    confidence, sub_scores = compute_confidence(df_upto_today, row, r2, preset, fund=fund, catalyst_info=catalyst_info)

    # module-floor: sluit compensatie uit - 1 zwakke KERNmodule mag niet
    # gemaskeerd worden door hoge scores elders (zie uitleg bij CORE_MODULES_WITH_FLOOR)
    for module_name in CORE_MODULES_WITH_FLOOR:
        if sub_scores[module_name] < preset["MODULE_FLOOR"]:
            return None

    if confidence < preset["MIN_CONFIDENCE"]:
        return None

    return {"row": row, "confidence": confidence, "sub_scores": sub_scores, "r2": r2}


# ============================================================================
# DAGELIJKSE SCAN
# ============================================================================

def bereken_totaalscore(row, info, stop):
    """SAMENGESTELDE SCORE over alle criteria, i.p.v. alleen momentum.

    Het idee: een aandeel dat op ALLE punten uitblinkt is een betere kandidaat
    dan eentje dat alleen hard is gestegen. Elk onderdeel scoort 0-100 en wordt
    gemiddeld.

    Let op de vorm van elke deelscore - niet alles is "meer is beter":
      - momentum, efficiency, langetermijntrend: meer is beter
      - afstand boven EMA21: een OPTIMUM. Net erboven is goed, ver erboven
        betekent doorgeschoten (dat maten we eerder met het extension-filter)
      - positie t.o.v. 20-daags hoog: net eronder of net erboven is ideaal
      - risico: LAGER is beter, want dat geeft een betere risk/reward
    """
    deel = {}

    # 1. momentum-percentiel (0-100, direct bruikbaar)
    deel["momentum"] = float(info["percentiel"])

    # 2. chart-leesbaarheid: 0.35 = minimum, 0.80+ = uitstekend
    eff = row.get("EFFICIENCY", np.nan)
    if pd.isna(eff):
        deel["chart"] = 50.0
    else:
        deel["chart"] = float(min(100, max(0, (eff - 0.30) / 0.50 * 100)))

    # 3. afstand boven EMA21 - OPTIMUM rond 2-6%
    try:
        afst = (row["Close"] / row["EMA21"] - 1) * 100
        if 1 <= afst <= 6:
            deel["ema21"] = 100.0
        elif afst < 1:
            deel["ema21"] = max(0.0, 60 + afst * 40)      # 0% -> 60, dichtbij is ok
        else:
            deel["ema21"] = max(0.0, 100 - (afst - 6) * 8)  # ver erboven = doorgeschoten
    except Exception:
        deel["ema21"] = 50.0

    # 4. langetermijntrend: hoe ver boven EMA300
    e300 = row.get("EMA300", np.nan)
    if pd.isna(e300) or e300 <= 0:
        deel["ema300"] = 50.0
    else:
        boven = (row["Close"] / e300 - 1) * 100
        deel["ema300"] = float(min(100, max(0, boven * 1.5)))   # 67% erboven -> 100

    # 5. positie t.o.v. 20-daags hoog - net eronder of net erboven is ideaal
    h20 = row.get("HIGH20", np.nan)
    if pd.isna(h20) or h20 <= 0:
        deel["pivot"] = 50.0
    else:
        afst = (row["Close"] / h20 - 1) * 100
        if -3 <= afst <= 3:
            deel["pivot"] = 100.0
        elif afst > 3:
            deel["pivot"] = max(0.0, 100 - (afst - 3) * 10)     # doorgeschoten
        else:
            deel["pivot"] = max(0.0, 100 + afst * 6)            # nog ver eronder

    # 6. nabijheid 52-weeks top
    pct52 = row.get("PCT_FROM_52W_HIGH", np.nan)
    if pd.isna(pct52):
        deel["52w"] = 50.0
    else:
        deel["52w"] = float(min(100, max(0, 100 + pct52 * 300)))  # -33% -> 0, 0% -> 100

    # 7. volume
    try:
        rvol = row["Volume"] / row["VOL_SMA20"]
        deel["volume"] = float(min(100, max(0, rvol * 50)))       # 2.0x -> 100
    except Exception:
        deel["volume"] = 50.0

    # 8. risico - lager is beter (betere risk/reward per trade)
    try:
        risico = (row["Close"] - stop) / row["Close"] * 100
        deel["risico"] = float(min(100, max(0, 100 - (risico - 2) * 14)))  # 2% -> 100, 9% -> 2
    except Exception:
        deel["risico"] = 50.0

    totaal = float(np.mean(list(deel.values())))
    return round(totaal, 1), {k: round(v, 0) for k, v in deel.items()}


# ============================================================================
# OPTIE-ANALYSE: aandelen of calls?
# ============================================================================
# BELANGRIJK: dit onderdeel is NIET gebacktest en kan dat ook niet worden -
# yfinance levert geen historische optiedata. Alles wat hieronder berekend
# wordt, gaat over de prijs van opties op DIT MOMENT, niet over of de
# strategie historisch gewerkt heeft. Alle gevalideerde cijfers in dit script
# (+2.33% per trade, zes vensters positief) gelden voor AANDELEN.
#
# Met opties kun je je volledige inleg verliezen, ook als het aandeel maar
# licht daalt of zelfs stil blijft staan. Bij aandelen verlies je bij een stop
# een vooraf bepaald percentage; bij een call kan de premie naar nul gaan.

OPTIE_MIN_DAGEN_TOT_EXPIRY = 14     # minder tijdwaarde-verlies bij langere looptijd
OPTIE_MAX_DAGEN_TOT_EXPIRY = 60
OPTIE_MAX_SPREAD_PCT = 10.0         # bied-laat verschil t.o.v. de middenprijs
OPTIE_MIN_OPEN_INTEREST = 100
OPTIE_MAX_IV_RV_RATIO = 1.5         # boven dit niveau zijn opties duur t.o.v.
                                     # hoeveel het aandeel werkelijk beweegt


def _kies_expiry(expiries, vandaag=None):
    """Kiest de eerste expiratiedatum die genoeg tijd heeft. Te kort betekent
    dat tijdwaarde snel wegloopt tijdens je houdperiode; te lang betekent dat
    je onnodig veel premie betaalt voor tijd die je niet gebruikt."""
    vandaag = vandaag or pd.Timestamp.today().normalize()
    geschikt = []
    for e in expiries:
        try:
            dagen = (pd.Timestamp(e) - vandaag).days
        except Exception:
            continue
        if OPTIE_MIN_DAGEN_TOT_EXPIRY <= dagen <= OPTIE_MAX_DAGEN_TOT_EXPIRY:
            geschikt.append((dagen, e))
    if not geschikt:
        return None, None
    geschikt.sort()
    return geschikt[0][1], geschikt[0][0]


def analyseer_calls(ticker, row, df, stop, target=None, hold_dagen=None):
    """Berekent of calls op dit moment gunstiger zijn dan aandelen.

    Vier vragen worden beantwoord:
      1. Zijn de opties duur? (implied volatility t.o.v. gerealiseerde)
      2. Zijn ze verhandelbaar? (bied-laat verschil, open interest)
      3. Haal je de breakeven binnen je houdperiode?
      4. Hoeveel tijdwaarde verlies je onderweg?

    Retourneert een dict met het oordeel, of None als er geen bruikbare
    opties zijn.
    """
    hold_dagen = hold_dagen or MAX_HOLD_DAYS
    koers = float(row["Close"])
    atr = float(row["ATR"])

    try:
        t = yf.Ticker(ticker)
        expiries = list(t.options)
    except Exception as e:
        return {"fout": f"geen optiedata beschikbaar ({e})"}
    if not expiries:
        return {"fout": "geen optieketen gevonden"}

    expiry, dagen_tot_expiry = _kies_expiry(expiries)
    if expiry is None:
        return {"fout": f"geen expiratie tussen {OPTIE_MIN_DAGEN_TOT_EXPIRY} "
                        f"en {OPTIE_MAX_DAGEN_TOT_EXPIRY} dagen"}

    try:
        keten = t.option_chain(expiry)
        calls = keten.calls
    except Exception as e:
        return {"fout": f"kon optieketen niet ophalen ({e})"}
    if calls is None or len(calls) == 0:
        return {"fout": "lege optieketen"}

    # kies de call die het dichtst bij de koers ligt (at-the-money)
    calls = calls.copy()
    calls["afstand"] = (calls["strike"] - koers).abs()
    calls = calls.sort_values("afstand")
    optie = calls.iloc[0]

    strike = float(optie["strike"])
    bid = float(optie.get("bid", 0) or 0)
    ask = float(optie.get("ask", 0) or 0)
    iv = float(optie.get("impliedVolatility", 0) or 0) * 100
    oi = int(optie.get("openInterest", 0) or 0)
    volume = int(optie.get("volume", 0) or 0)

    if ask <= 0:
        return {"fout": "geen geldige laatprijs"}
    midden = (bid + ask) / 2 if bid > 0 else ask
    spread_pct = ((ask - bid) / midden * 100) if midden > 0 and bid > 0 else 100.0

    # gerealiseerde volatiliteit over 3 maanden, op jaarbasis
    rv = bereken_gerealiseerde_volatiliteit(df, 63, skip=0)
    iv_rv = (iv / rv) if (rv and rv > 0 and iv > 0) else np.nan

    # breakeven en benodigde beweging
    breakeven = strike + ask
    beweging_nodig = (breakeven - koers) / koers * 100

    # hoeveel kan het aandeel realistisch bewegen in de houdperiode?
    # ATR is de gemiddelde dagbeweging; over meerdere dagen schaalt dat
    # ongeveer met de wortel van het aantal dagen (niet lineair)
    verwachte_beweging = (atr * np.sqrt(hold_dagen)) / koers * 100

    # tijdwaarde-verlies: benadering via de wortel-van-tijd-regel
    resterend = max(dagen_tot_expiry - hold_dagen, 1)
    theta_verlies_pct = (1 - np.sqrt(resterend / dagen_tot_expiry)) * 100

    # oordeel opbouwen
    bezwaren = []
    if not np.isnan(iv_rv) and iv_rv > OPTIE_MAX_IV_RV_RATIO:
        bezwaren.append(f"opties duur: IV {iv:.0f}% tegen werkelijke beweging "
                        f"{rv:.0f}% (ratio {iv_rv:.2f})")
    if spread_pct > OPTIE_MAX_SPREAD_PCT:
        bezwaren.append(f"bied-laat verschil {spread_pct:.0f}% - je verliest veel "
                        f"bij in- en uitstappen")
    if oi < OPTIE_MIN_OPEN_INTEREST:
        bezwaren.append(f"open interest {oi} is laag - moeilijk verhandelbaar")
    if beweging_nodig > verwachte_beweging:
        bezwaren.append(f"breakeven vraagt {beweging_nodig:.1f}%, terwijl het aandeel "
                        f"in {hold_dagen} dagen doorgaans {verwachte_beweging:.1f}% beweegt")

    return {
        "expiry": expiry, "dagen_tot_expiry": dagen_tot_expiry,
        "strike": strike, "bid": bid, "ask": ask, "midden": midden,
        "iv": iv, "rv": rv, "iv_rv": iv_rv,
        "spread_pct": spread_pct, "open_interest": oi, "volume": volume,
        "breakeven": breakeven, "beweging_nodig": beweging_nodig,
        "verwachte_beweging": verwachte_beweging,
        "theta_verlies_pct": theta_verlies_pct,
        "premie_pct_van_koers": ask / koers * 100,
        "bezwaren": bezwaren,
        "advies": "aandelen" if bezwaren else "calls kunnen",
    }


def toon_optie_advies(ticker, analyse, koers):
    """Print het optie-oordeel in gewone taal."""
    if analyse is None:
        return
    if "fout" in analyse:
        print(f"   Opties: {analyse['fout']} -> aandelen")
        return

    a = analyse
    if a["advies"] == "calls kunnen":
        kop = "CALLS KUNNEN"
    else:
        kop = "AANDELEN (calls ongunstig)"
    print(f"   Opties: {kop}")
    print(f"      Call {a['strike']:.1f} vervalt {a['expiry']} "
          f"({a['dagen_tot_expiry']} dagen), laatprijs {a['ask']:.2f} "
          f"= {a['premie_pct_van_koers']:.1f}% van de koers")
    if not np.isnan(a["iv_rv"]):
        duiding = ("goedkoop" if a["iv_rv"] < 1.0 else
                   "redelijk" if a["iv_rv"] <= 1.3 else "duur")
        print(f"      IV {a['iv']:.0f}% tegen werkelijke beweging {a['rv']:.0f}% "
              f"(ratio {a['iv_rv']:.2f} - {duiding})")
    print(f"      Breakeven {a['breakeven']:.2f}: aandeel moet {a['beweging_nodig']:+.1f}% "
          f"stijgen; verwacht in {MAX_HOLD_DAYS} dagen ~{a['verwachte_beweging']:.1f}%")
    print(f"      Tijdwaarde-verlies over {MAX_HOLD_DAYS} dagen: ~{a['theta_verlies_pct']:.0f}% "
          f"van de premie, ook als het aandeel stilstaat")
    print(f"      Bied-laat {a['spread_pct']:.0f}%, open interest {a['open_interest']}")
    for b in a["bezwaren"]:
        print(f"      ! {b}")


def leg_keuze_uit(ticker, row, info, df, stop):
    """Bouwt een leesbare uitleg waarom dit aandeel geselecteerd is.
    Elk punt verwijst naar de eis die het aandeel daadwerkelijk haalde,
    zodat je kunt beoordelen of de selectie klopt met wat je op de grafiek ziet."""
    regels = []

    # 1. ranking - de kernreden
    regels.append(f"Sterker dan {info['percentiel']:.0f}% van alle gescande aandelen "
                  f"({info['momentum']:+.0f}% over 6 maanden, laatste week niet meegeteld)")

    # 2. leesbaarheid
    eff = row.get("EFFICIENCY", np.nan)
    if not pd.isna(eff):
        if eff >= 0.60:
            oordeel = "zeer rechtlijnig"
        elif eff >= 0.45:
            oordeel = "netjes leesbaar"
        elif eff >= MIN_EFFICIENCY:
            oordeel = "net boven de drempel, niet strak"
        else:
            oordeel = "ONDER de drempel"
        regels.append(f"Chart {oordeel} (efficiency {eff:.2f}; "
                      f"{eff*100:.0f}% van de beweging is netto vooruitgang)")

    # 3. trendstructuur
    try:
        afstand_ema21 = (row["Close"] / row["EMA21"] - 1) * 100
        regels.append(f"Koers {afstand_ema21:+.1f}% boven EMA21, en EMA9 ligt boven EMA21 "
                      f"(kortetermijntrend wijst omhoog)")
    except Exception:
        pass
    e300 = row.get("EMA300", np.nan)
    if not pd.isna(e300):
        regels.append(f"Koers {((row['Close']/e300)-1)*100:+.0f}% boven EMA300 "
                      f"(langetermijntrend intact)")

    # 4. positie t.o.v. recente hoogtes
    h20 = row.get("HIGH20", np.nan)
    if not pd.isna(h20) and h20 > 0:
        afst = (row["Close"] / h20 - 1) * 100
        if afst >= 0:
            regels.append(f"Boven het 20-daags hoog ({afst:+.1f}%) - breekt uit")
        elif afst > -5:
            regels.append(f"Vlak onder het 20-daags hoog ({afst:+.1f}%) - laadt op")
        else:
            regels.append(f"{abs(afst):.0f}% onder het 20-daags hoog - consolideert")

    pct52 = row.get("PCT_FROM_52W_HIGH", np.nan)
    if not pd.isna(pct52):
        if pct52 >= -0.05:
            regels.append("Vrijwel op een 52-weeks top (geen weerstand boven)")
        elif pct52 >= -0.25:
            regels.append(f"Binnen {abs(pct52)*100:.0f}% van de 52-weeks top")

    # 4b. RSI - als informatie, niet als filter. Uit de meting bleek dat
    # filteren op RSI het resultaat niet verbeterde, maar de stand zegt je wel
    # of het momentum nog ruimte heeft of al ver opgerekt is.
    rsi = row.get("RSI", np.nan)
    if not pd.isna(rsi):
        if rsi >= 80:
            duiding = "zeer hoog - sterk momentum, maar weinig ruimte over"
        elif rsi >= 70:
            duiding = "hoog - krachtig momentum"
        elif rsi >= 60:
            duiding = "gezond momentum"
        elif rsi >= 50:
            duiding = "momentum bevestigt de trend"
        elif rsi >= 40:
            duiding = "zwak - momentum hapert"
        else:
            duiding = "laag - terugval of consolidatie"
        regels.append(f"RSI {rsi:.0f} ({duiding})")

    # 4c. MACD - eveneens als informatie. De meting liet zien dat een MACD-
    # crossover eisen juist SLECHTER presteerde (+1.26% met tegen +1.85%
    # zonder), waarschijnlijk omdat de beweging dan al gemaakt is.
    macd, sig = row.get("MACD", np.nan), row.get("MACD_signal", np.nan)
    hist = row.get("MACD_hist", np.nan)
    if not pd.isna(macd) and not pd.isna(sig):
        boven = macd > sig
        positie = "boven" if boven else "onder"
        extra = ""
        if not pd.isna(hist):
            extra = ", histogram positief" if hist > 0 else ", histogram negatief"
        nul = " en boven nul" if macd > 0 else " en onder nul"
        regels.append(f"MACD {positie} de signaallijn{nul}{extra}")

    # 4d. SUPPORT EN WEERSTAND met concrete niveaus
    if df is not None and len(df) > 60:
        try:
            koers = row["Close"]
            # support: laagste punt van de laatste 20 dagen (waar de setup faalt)
            steun = float(df["Low"].iloc[-20:].min())
            afst_steun = (koers - steun) / koers * 100
            regels.append(f"Steun rond {steun:.2f} ({afst_steun:.1f}% eronder) "
                          f"= laagste punt van de laatste 20 dagen")
            # weerstand: eerstvolgende swing-top boven de koers
            ruimte = compute_overhead_resistance(df)
            if pd.isna(ruimte):
                regels.append("Geen weerstand boven de koers - vrije baan")
            else:
                weerstand = koers * (1 + ruimte)
                regels.append(f"Weerstand rond {weerstand:.2f} ({ruimte*100:.1f}% erboven) "
                              f"= eerstvolgende oude top")
        except Exception:
            pass

    # 5. volume
    try:
        rvol = row["Volume"] / row["VOL_SMA20"]
        if rvol >= 2.0:
            regels.append(f"Volume {rvol:.1f}x het gemiddelde - duidelijk verhoogde interesse")
        elif rvol >= 1.2:
            regels.append(f"Volume {rvol:.1f}x het gemiddelde")
        else:
            regels.append(f"Volume {rvol:.1f}x het gemiddelde - rustig "
                          f"(dat is geen bezwaar; de meting toonde dat een volumepiek "
                          f"eisen juist slechter presteert)")
    except Exception:
        pass

    # 6. risico en risk/reward
    risico_pct = (row["Close"] - stop) / row["Close"] * 100
    regels.append(f"Stop op {stop:.2f} = {risico_pct:.1f}% risico "
                  f"(ATR {row['ATR']/row['Close']*100:.1f}% per dag)")
    if df is not None:
        try:
            rr, target, dagen_nodig = bereken_rr(df, row, stop)
            if not np.isnan(rr):
                oordeel = "gunstig" if rr >= 2 else ("acceptabel" if rr >= 1.5 else "krap")
                regels.append(f"Target {target:.2f} geeft R:R van 1:{rr:.1f} ({oordeel}); "
                              f"~{dagen_nodig:.1f} ATR-dagen nodig "
                              f"(je houdt maximaal {MAX_HOLD_DAYS})")
        except Exception:
            pass

    # 7. waarschuwingen
    waarschuwingen = []
    if info["momentum"] > 300:
        waarschuwingen.append(f"momentum van {info['momentum']:.0f}% is extreem - "
                              f"controleer op reverse split of overname")
    if row["Close"] < 5:
        waarschuwingen.append("koers onder $5: bredere spreads, hogere werkelijke slippage")
    if risico_pct > 7:
        waarschuwingen.append(f"risico van {risico_pct:.1f}% is aan de hoge kant")
    if not pd.isna(eff) and eff < 0.42:
        waarschuwingen.append("chart zit dicht bij de leesbaarheidsdrempel")
    if df is not None:
        try:
            rr2, _, dagen2 = bereken_rr(df, row, stop)
            if not np.isnan(rr2) and rr2 < 1.5:
                waarschuwingen.append(
                    f"R:R van 1:{rr2:.1f} is krap - weinig ruimte tot de weerstand")
            if not np.isnan(dagen2) and dagen2 > MAX_HOLD_DAYS * 1.5:
                waarschuwingen.append(
                    f"target vraagt ~{dagen2:.0f} ATR-dagen, terwijl je er {MAX_HOLD_DAYS} houdt")
        except Exception:
            pass

    return regels, waarschuwingen


def scan_gevalideerd(top_pct=TOP_N_PERCENTIEL, max_results=20):
    """DAGELIJKSE SCAN - volgt EXACT dezelfde volgorde als de walk-forward.

    Waarom deze functie de oude scan_ranking vervangt: die filterde EERST en
    rangschikte daarna alleen de overblijvers. De walk-forward (+2.33% per
    trade, alle zes vensters positief) doet het omgekeerde: eerst het hele
    universum rangschikken op momentum, daarna filteren. Dat zijn twee
    verschillende methodes - de scan draaide dus niet wat er gevalideerd was.
    Bovendien: met maar een handvol overblijvers is een top-10% betekenisloos.

    Volgorde (identiek aan walk_forward_actueel):
      1. alle tickers met genoeg historie rangschikken op momentum
      2. de sterkste top_pct% selecteren
      3. daarop de filters toepassen (_passeert_filters: prijs, liquiditeit,
         trend, EMA300, leesbaarheid)
      4. daarna de extra eisen: bekende naam, earnings-blackout
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print(f"DAGELIJKSE SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 78)
    print(f"Momentum: {MOMENTUM_METHODE}, sterkste {top_pct}% van het hele universum")
    if GEBRUIK_MARKTWAARDE_FILTER:
        print(f"Bekende namen: marktwaarde >= ${MIN_MARKTWAARDE/1e9:.0f} mld, "
              f"dagvolume >= ${MIN_DAGVOLUME_DOLLAR/1e6:.0f}M")
    print()

    universe = get_nasdaq_universe(MAX_UNIVERSE_SIZE) if USE_FULL_NASDAQ_SCAN else list(WATCHLIST)
    print(f"Universum: {len(universe)} tickers")

    spy = yf.download("SPY", period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]
    if not is_market_regime_bullish(spy):
        print("LET OP: SPY onder zijn SMA50 - zwakkere marktomgeving.")

    # --- VIX-controle ---
    vix_nu = None
    if GEBRUIK_VIX_FILTER:
        vix_reeks = haal_vix(periode="1y")
        if vix_reeks is not None:
            vix_nu = float(vix_reeks.iloc[-1])
            print(f"VIX vandaag: {vix_nu:.1f}  (bruikbaar bereik {VIX_MINIMUM:.0f}-{VIX_MAXIMUM:.0f})")
            if vix_nu < VIX_MINIMUM or vix_nu > VIX_MAXIMUM:
                print()
                print("!" * 78)
                reden = "TE LAAG" if vix_nu < VIX_MINIMUM else "TE HOOG"
                print(f"VIX {reden} - GEEN NIEUWE POSITIES VANDAAG")
                print("!" * 78)
                if vix_nu < VIX_MINIMUM:
                    print("Gemeten: bij VIX onder 16 was het rendement +0.3% per trade met een")
                    print("negatieve mediaan; tussen 16 en 20 was dat +2.4% met 61% win rate.")
                else:
                    print("Gemeten: bij VIX boven 25 was het rendement sterk negatief.")
                print("De scan toont hieronder wat er gevonden zou zijn, ter informatie.")
                print("!" * 78)
            else:
                print("-> VIX in het gunstige bereik.")
        else:
            print("VIX niet beschikbaar - controleer de VIX zelf voordat je handelt.")
    print()

    # --- koersdata ophalen ---
    all_data = {}
    n_chunks = (len(universe) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = universe[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=HIST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    all_data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    # --- STAP 1: ruwe data verzamelen (NOG GEEN indicatoren) ---
    # De ranking gebruikt alleen slotkoersen. compute_indicators is ~200x
    # trager dan een momentum-berekening (20 ms tegen 0.1 ms per ticker), dus
    # die draaien we pas voor de sterkste 10% in plaats van voor alles.
    # Dit verandert NIETS aan de uitkomst - alleen de volgorde van rekenen.
    min_hist = 320 if MOMENTUM_METHODE != "enkel" else MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 30
    ruw = {}
    te_kort = 0
    for ticker in universe:
        df = all_data.get(ticker)
        if df is None:
            continue
        try:
            df = df.dropna()
            if len(df) < min_hist:
                te_kort += 1
                continue
            ruw[ticker] = df
        except Exception:
            continue
    print(f"\n{len(ruw)} tickers met genoeg historie ({te_kort} te kort).")
    if len(ruw) < 20:
        print("Te weinig tickers om te rangschikken.")
        return

    # --- STAP 2: rangschikken op slotkoersen alleen ---
    ranking = (rangschik_universum(ruw) if MOMENTUM_METHODE == "enkel"
               else rangschik_universum_v2(ruw, MOMENTUM_METHODE))
    drempel = 100 - top_pct
    top = [t for t, i in ranking.items() if i["percentiel"] >= drempel]
    print(f"Sterkste {top_pct}%: {len(top)} tickers.")

    # --- STAP 2b: nu pas de volledige indicatoren, alleen voor de toppers ---
    print(f"Indicatoren berekenen voor {len(top)} tickers...")
    voorbereid = {}
    for ticker in top:
        try:
            voorbereid[ticker] = compute_indicators(ruw[ticker], spy_close=spy)
        except Exception:
            continue
    top = [t for t in top if t in voorbereid]

    # --- STAP 3 + 4: filters op de toppers ---
    afgevallen = {"prijs/liquiditeit/trend/leesbaarheid": 0,
                  "geen bekende naam (marktwaarde)": 0,
                  "geen bekende naam (dagvolume)": 0,
                  "earnings binnen blackout": 0}
    kandidaten = []
    for ticker in top:
        df = voorbereid[ticker]
        row = df.iloc[-1]
        if not _passeert_filters(row):
            afgevallen["prijs/liquiditeit/trend/leesbaarheid"] += 1
            continue
        dagvolume = row["Close"] * row["VOL_SMA20"]
        if GEBRUIK_MARKTWAARDE_FILTER and dagvolume < MIN_DAGVOLUME_DOLLAR:
            afgevallen["geen bekende naam (dagvolume)"] += 1
            continue
        mw = None
        if GEBRUIK_MARKTWAARDE_FILTER:
            try:
                mw = get_fundamentals(ticker).get("market_cap")
            except Exception:
                mw = None
            if mw is None or mw < MIN_MARKTWAARDE:
                afgevallen["geen bekende naam (marktwaarde)"] += 1
                continue
        if EARNINGS_BLACKOUT_DAGEN > 0:
            dagen = get_next_earnings_gap_days(ticker)
            if dagen is not None and 0 <= dagen <= EARNINGS_BLACKOUT_DAGEN:
                afgevallen["earnings binnen blackout"] += 1
                continue

        info = ranking[ticker]
        stop = compute_stop(row, row["Close"])
        risico = row["Close"] - stop
        if risico <= 0:
            continue
        aandelen = int((ACCOUNT_SIZE * RISK_PCT_PER_TRADE) / risico)
        aandelen = max(0, min(aandelen, int((ACCOUNT_SIZE * MAX_POSITION_PCT) / row["Close"])))
        kandidaten.append({
            "Ticker": ticker,
            "Mrkt_mld": round(mw / 1e9, 1) if mw else None,
            "Vol_mln": round(dagvolume / 1e6, 0),
            "Rang": info["percentiel"],
            "Chart": round(float(row.get("EFFICIENCY", np.nan)), 2),
            "Koers": round(row["Close"], 2),
            "Stop": round(stop, 2),
            "Risico_%": round(risico / row["Close"] * 100, 1),
            "Aandelen": aandelen,
            "_row": row, "_info": info, "_stop": stop, "_df": df,
        })

    print("\nWaar vielen de sterkste namen af?")
    for reden, n in afgevallen.items():
        print(f"   {reden:42s} {n:4d}")

    if not kandidaten:
        print("\nGeen kandidaten vandaag.")
        print("Dat is een geldige uitkomst - geen duidelijke setup betekent geen trade.")
        return

    eind = pd.DataFrame(kandidaten).sort_values("Rang", ascending=False).head(max_results)
    kolommen = ["Ticker", "Mrkt_mld", "Vol_mln", "Rang", "Chart", "Koers", "Stop", "Risico_%", "Aandelen"]
    if not GEBRUIK_MARKTWAARDE_FILTER:
        kolommen = [k for k in kolommen if k not in ("Mrkt_mld", "Vol_mln")]

    print("\n" + "=" * 78)
    print(f"KANDIDATEN ({len(eind)})")
    print("=" * 78)
    print(eind[kolommen].to_string(index=False))
    print("\nMrkt_mld = marktwaarde (miljard $), Vol_mln = verhandeld per dag (miljoen $)")
    print("Rang = percentiel binnen het hele universum, Chart = leesbaarheid (0-1)")

    print("\n" + "=" * 78)
    print("WAAROM DEZE AANDELEN?")
    print("=" * 78)
    for _, r in eind.iterrows():
        regels, waarschuwingen = leg_keuze_uit(
            r["Ticker"], r["_row"], r["_info"], r["_df"], r["_stop"])
        print(f"\n{r['Ticker']}  (${r['Koers']:.2f}, rang {r['Rang']:.0f})")
        for regel in regels:
            print(f"   + {regel}")
        for w in waarschuwingen:
            print(f"   ! {w}")
        if TOON_OPTIE_ADVIES:
            try:
                analyse = analyseer_calls(r["Ticker"], r["_row"], r["_df"], r["_stop"])
                toon_optie_advies(r["Ticker"], analyse, r["Koers"])
            except Exception as e:
                print(f"   Opties: analyse mislukt ({e})")

    if TOON_OPTIE_ADVIES:
        print()
        print("-" * 78)
        print("OVER HET OPTIE-ADVIES")
        print("-" * 78)
        print("Dit is NIET gebacktest en kan dat ook niet worden - er is geen")
        print("historische optiedata beschikbaar. De gevalideerde cijfers van dit")
        print("script (+2.33% per trade, zes vensters positief) gelden voor AANDELEN.")
        print()
        print("Het advies rekent alleen uit of calls op DIT MOMENT redelijk geprijsd")
        print("zijn: is de implied volatility niet veel hoger dan hoe het aandeel")
        print("werkelijk beweegt, zijn ze verhandelbaar, en haal je de breakeven")
        print("binnen je houdperiode? 'Calls kunnen' betekent dat er geen bezwaren")
        print("zijn - niet dat het een beter idee is dan aandelen.")

    # risicobudget
    max_pos = min(MAX_GELIJKTIJDIGE_POSITIES, int(MAX_PORTFOLIO_HEAT / RISK_PCT_PER_TRADE))
    open_nu = 0
    try:
        open_nu = int((pd.read_csv(POSITIONS_FILE)["Status"] == "open").sum())
    except Exception:
        pass
    ruimte = max(0, max_pos - open_nu)
    print("\n" + "-" * 78)
    print(f"RISICOBUDGET: {open_nu} van {max_pos} posities open -> ruimte voor {ruimte}")
    if ruimte == 0:
        print("   >> Budget vol. Geen nieuwe posities tot er een sluit.")
    elif ruimte < len(eind):
        print(f"   >> Neem alleen de bovenste {ruimte} (hoogste rang).")

    try:
        log = eind[kolommen].copy()
        log.insert(0, "ScanDatum", datetime.now().strftime("%Y-%m-%d"))
        log.insert(1, "Methode", "gevalideerd")
        header = not pd.io.common.file_exists(SCAN_LOG_FILE)
        log.to_csv(SCAN_LOG_FILE, mode="a", header=header, index=False)
    except Exception:
        pass
    return eind


def scan_ranking(top_pct=TOP_N_PERCENTIEL, max_results=20):
    """DAGELIJKSE SCAN OP BASIS VAN CROSS-SECTIONELE RANKING.

    In plaats van "voldoet dit aandeel aan drempel X", vraagt deze scan:
    "hoort dit aandeel vandaag bij de sterkste top_pct% van het universum?"

    Waarom dit de gemeten voorkeur heeft boven vaste drempels (--ranking test,
    48 maanden, 6 walk-forward vensters):
        drempels: +0.354% per trade, faalde in venster 5 (-0.05%) en 6 (-1.41%)
        ranking:  +0.457% per trade, hield stand in venster 5 (+0.59%) en 6 (-0.39%)
    Een vaste lat breekt wanneer de markt verandert; een relatieve lat beweegt mee.

    Let op de keerzijde die ook uit die test bleek: ranking heeft een IETS LAGERE
    win rate (50.5% vs 51.7%) en lagere mediaan. Je krijgt dus meer kleine
    verliezers en grotere winnaars - dat vraagt discipline om vol te houden.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print(f"RANKING-SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 78)
    if MOMENTUM_METHODE == "enkel":
        print(f"Selecteert de sterkste {top_pct}% op {MOMENTUM_LOOKBACK}-daags momentum")
    else:
        weging = "gelijk gewogen" if MOMENTUM_METHODE == "multi" else "50/30/20 gewogen"
        print(f"Selecteert de sterkste {top_pct}% op SAMENGESTELD momentum")
        print(f"(3, 6 en 12 maanden, {weging} - gemeten +1.55% vs +1.22% bij een enkele meting)")
    print(f"(laatste {MOMENTUM_SKIP} dagen overgeslagen wegens korte-termijn-omkeer).")
    print("De lat beweegt mee met de markt i.p.v. vast te staan.")
    if GEBRUIK_MARKTWAARDE_FILTER:
        print(f"Alleen bekende namen: marktwaarde minimaal ${MIN_MARKTWAARDE/1e9:.0f} miljard")
        print(f"en minimaal ${MIN_DAGVOLUME_DOLLAR/1e6:.0f} miljoen verhandeld per dag.")
    if GEBRUIK_TRENDFILTER:
        extra = " en > EMA300" if GEBRUIK_EMA300_FILTER else ""
        print(f"Trendfilter AAN: koers > EMA21, EMA9 > EMA21{extra}.")
    if GEBRUIK_LEESBAARHEIDSFILTER:
        print(f"Leesbaarheidsfilter AAN: efficiency >= {MIN_EFFICIENCY} (geen barcode-charts).")
        print("Gemeten: +1.43% per trade, win rate 55.5% (vs +0.45% zonder filters).")
    print()

    universe = get_nasdaq_universe(MAX_UNIVERSE_SIZE) if USE_FULL_NASDAQ_SCAN else list(WATCHLIST)
    print(f"Universum: {len(universe)} tickers")

    spy = yf.download("SPY", period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]
    if not is_market_regime_bullish(spy):
        print("\nLET OP: SPY onder zijn SMA50. De ranking selecteert nog steeds de")
        print("relatief sterkste namen, maar in een zwakke markt zijn ook die vaak")
        print("negatief. Overweeg kleinere posities.\n")

    # --- VIX-controle: staat de markt in het bruikbare volatiliteitsbereik? ---
    vix_nu = None
    if GEBRUIK_VIX_FILTER:
        vix_reeks = haal_vix(periode="1y")   # 3mo gaf ~65 dagen, minimum is 100
        if vix_reeks is not None and len(vix_reeks) > 0:
            vix_nu = float(vix_reeks.iloc[-1])
            print(f"VIX vandaag: {vix_nu:.1f}  (bruikbaar bereik: "
                  f"{VIX_MINIMUM:.0f} - {VIX_MAXIMUM:.0f})")
            if vix_nu < VIX_MINIMUM:
                print()
                print("=" * 78)
                print("GEEN NIEUWE POSITIES VANDAAG - VIX TE LAAG")
                print("=" * 78)
                print(f"De VIX staat op {vix_nu:.1f}, onder de ondergrens van {VIX_MINIMUM:.0f}.")
                print()
                print("Gemeten op 48 maanden: bij VIX onder 16 was het rendement +0.3%")
                print("per trade met een win rate van 48% en een NEGATIEVE mediaan.")
                print("Boven 16 was dat +3.3% met een win rate van 66%.")
                print()
                print("Bij zeer lage volatiliteit bewegen aandelen te weinig om binnen")
                print("5 dagen een zinvolle swing te maken.")
                print()
                print("De scan draait toch door, zodat je ziet WAT er zou zijn gevonden -")
                print("maar neem deze kandidaten niet, of alleen met een halve positie.")
                print("=" * 78)
                print()
            elif vix_nu > VIX_MAXIMUM:
                print()
                print("=" * 78)
                print("VOORZICHTIG - VIX TE HOOG")
                print("=" * 78)
                print(f"De VIX staat op {vix_nu:.1f}, boven de bovengrens van {VIX_MAXIMUM:.0f}.")
                print("Gemeten: bij VIX boven 25 was het rendement -7.3% per trade")
                print("met een win rate van 10% (wel op slechts 10 trades).")
                print("=" * 78)
                print()
            else:
                print("-> VIX in het gunstige bereik.\n")
        else:
            print("VIX niet beschikbaar - filter overgeslagen.\n")

    all_data = {}
    n_chunks = (len(universe) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = universe[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=HIST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    all_data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    # basisfilters: prijs en liquiditeit. Bewust MINIMAAL - de ranking doet
    # de selectie, deze filters houden alleen onverhandelbare namen buiten.
    bruikbaar = {}
    afgevallen = {"geen data": 0, "prijs": 0, "liquiditeit": 0,
                  "te weinig historie": 0, "trend niet omhoog": 0,
                  "onder EMA300 / te jong": 0, "chart te rommelig (barcode)": 0}
    for ticker in universe:
        try:
            df = all_data.get(ticker)
            if df is None:
                afgevallen["geen data"] += 1
                continue
            df = df.dropna()
            # 'multi' gebruikt een 252-daagse horizon, dus meer historie nodig
            min_momentum = (252 + MOMENTUM_SKIP + 10 if MOMENTUM_METHODE != "enkel"
                            else MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 30)
            min_historie = max(310 if GEBRUIK_EMA300_FILTER else 0, min_momentum)
            if len(df) < min_historie:
                afgevallen["te weinig historie"] += 1
                continue
            df = compute_indicators(df, spy_close=spy)
            row = df.iloc[-1]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("VOL_SMA20", np.nan)):
                afgevallen["geen data"] += 1
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                afgevallen["prijs"] += 1
                continue
            dagvolume = row["Close"] * row["VOL_SMA20"]
            minimum = MIN_DAGVOLUME_DOLLAR if GEBRUIK_MARKTWAARDE_FILTER else 5_000_000
            if dagvolume < minimum:
                afgevallen["liquiditeit"] += 1
                continue
            if GEBRUIK_TRENDFILTER:
                ema9, ema21 = row.get("EMA9", np.nan), row.get("EMA21", np.nan)
                if pd.isna(ema9) or pd.isna(ema21):
                    afgevallen["geen data"] += 1
                    continue
                if not (row["Close"] > ema21 and ema9 > ema21):
                    afgevallen["trend niet omhoog"] = afgevallen.get("trend niet omhoog", 0) + 1
                    continue
                if GEBRUIK_EMA300_FILTER:
                    ema300 = row.get("EMA300", np.nan)
                    if pd.isna(ema300) or row["Close"] <= ema300:
                        afgevallen["onder EMA300 / te jong"] = afgevallen.get("onder EMA300 / te jong", 0) + 1
                        continue
            if GEBRUIK_LEESBAARHEIDSFILTER:
                eff = row.get("EFFICIENCY", np.nan)
                if pd.isna(eff) or eff < MIN_EFFICIENCY:
                    afgevallen["chart te rommelig (barcode)"] = afgevallen.get("chart te rommelig (barcode)", 0) + 1
                    continue
            bruikbaar[ticker] = df
        except Exception:
            afgevallen["geen data"] += 1
            continue

    # --- marktwaarde-filter: alleen grote, bekende bedrijven ---
    # Toegepast NA de goedkope filters (die al het meeste wegfilteren) en VOOR
    # de ranking, zodat de sterkste 10% wordt bepaald BINNEN de grote bedrijven.
    # Zou dit na de ranking gebeuren, dan kunnen alle toppers kleine bedrijven
    # zijn en houd je niets over.
    if GEBRUIK_MARKTWAARDE_FILTER and bruikbaar:
        print(f"\nMarktwaarde ophalen voor {len(bruikbaar)} kandidaten "
              f"(minimum ${MIN_MARKTWAARDE/1e9:.0f} miljard)...")
        te_klein, onbekend = 0, 0
        for ticker in list(bruikbaar.keys()):
            try:
                mw = get_fundamentals(ticker).get("market_cap")
            except Exception:
                mw = None
            if mw is None:
                onbekend += 1
                del bruikbaar[ticker]     # onbekend = niet aantoonbaar groot
            elif mw < MIN_MARKTWAARDE:
                te_klein += 1
                del bruikbaar[ticker]
        afgevallen["marktwaarde te klein"] = te_klein
        afgevallen["marktwaarde onbekend"] = onbekend

    print(f"\n{len(bruikbaar)} tickers gaan de ranking in.")
    for reden, n in afgevallen.items():
        if n > 0:
            print(f"   afgevallen - {reden}: {n}")

    if len(bruikbaar) < 10:
        print("\nTe weinig tickers voor een zinvolle ranking.")
        if GEBRUIK_MARKTWAARDE_FILTER:
            print(f"Het marktwaarde-filter (min ${MIN_MARKTWAARDE/1e9:.0f} miljard) laat")
            print("vandaag te weinig aandelen door. Verlaag MIN_MARKTWAARDE bovenin")
            print("het script, of zet GEBRUIK_MARKTWAARDE_FILTER op False.")
        return

    ranking = (rangschik_universum(bruikbaar) if MOMENTUM_METHODE == "enkel"
               else rangschik_universum_v2(bruikbaar, MOMENTUM_METHODE))
    drempel = 100 - top_pct

    resultaten = []
    geweerd_earnings = []
    for ticker, info in ranking.items():
        if info["percentiel"] < drempel:
            continue
        df = bruikbaar[ticker]
        row = df.iloc[-1]

        # EARNINGS-BLACKOUT. Dit ontbrak in de ranking-scan (de oude drempel-
        # scan had het wel). Een gap na cijfers gaat dwars door je stop heen,
        # waardoor je hele risicoberekening niet meer klopt. Alleen gecheckt
        # voor kandidaten die al door de ranking komen, want het is een trage
        # losse netwerk-call per ticker.
        if EARNINGS_BLACKOUT_DAGEN > 0:
            dagen = get_next_earnings_gap_days(ticker)
            if dagen is not None and 0 <= dagen <= EARNINGS_BLACKOUT_DAGEN:
                geweerd_earnings.append((ticker, dagen))
                continue
        stop = compute_stop(row, row["Close"])
        risico = row["Close"] - stop
        if risico <= 0:
            continue
        aandelen = int((ACCOUNT_SIZE * RISK_PCT_PER_TRADE) / risico)
        aandelen = max(0, min(aandelen, int((ACCOUNT_SIZE * MAX_POSITION_PCT) / row["Close"])))
        sector = get_sector_etf(ticker)
        mw_waarde = None
        if GEBRUIK_MARKTWAARDE_FILTER:
            try:
                mw_waarde = get_fundamentals(ticker).get("market_cap")
            except Exception:
                pass
        resultaten.append({
            "Ticker": ticker, "Rang": info["percentiel"], "Mom_%": info["momentum"],
            "Mrkt_mld": round(mw_waarde / 1e9, 1) if mw_waarde else None,
            "Vol_mln": round(row["Close"] * row["VOL_SMA20"] / 1e6, 0),
            "Chart": round(float(row.get("EFFICIENCY", np.nan)), 2),
            "Koers": round(row["Close"], 2), "Stop": round(stop, 2),
            "Risico_%": round(risico / row["Close"] * 100, 1),
            "Aandelen": aandelen, "Sector": sector,
        })

    if geweerd_earnings:
        print(f"\n{len(geweerd_earnings)} kandidaten geweerd wegens naderende earnings:")
        for tk, d in geweerd_earnings[:8]:
            print(f"   {tk}: earnings over {d} dag(en)")

    if not resultaten:
        print("\nGeen kandidaten in het top-percentiel.")
        return

    out = pd.DataFrame(resultaten).sort_values("Rang", ascending=False)

    # Sectorspreiding: niet alles in dezelfde hoek. BELANGRIJK: tickers die
    # niet in SECTOR_ETF staan vallen terug op "SPY". Bij de brede NASDAQ-scan
    # is dat de meerderheid, waardoor de spreidingsregel ze allemaal als EEN
    # sector zou behandelen en er maar 2 zou tonen. Daarom geldt de limiet
    # alleen voor ECHT toegewezen sectoren, niet voor de SPY-restgroep.
    gekozen, per_sector = [], {}
    for _, r in out.iterrows():
        sec = r["Sector"]
        if sec != DEFAULT_SECTOR_ETF and per_sector.get(sec, 0) >= MAX_SIGNALS_PER_SECTOR:
            continue
        gekozen.append(r)
        per_sector[sec] = per_sector.get(sec, 0) + 1
        if len(gekozen) >= max_results:
            break
    eind = pd.DataFrame(gekozen)

    # portfolio heat: hoeveel posities passen er nog binnen het risicobudget?
    max_nieuw = min(MAX_GELIJKTIJDIGE_POSITIES,
                    int(MAX_PORTFOLIO_HEAT / RISK_PCT_PER_TRADE))
    reeds_open = 0
    try:
        pos = pd.read_csv(POSITIONS_FILE)
        reeds_open = int((pos["Status"] == "open").sum())
    except Exception:
        pass
    ruimte = max(0, max_nieuw - reeds_open)

    print("\n" + "=" * 78)
    print(f"STERKSTE {top_pct}% VAN HET UNIVERSUM")
    print("=" * 78)
    kolommen = ["Ticker", "Rang", "Mom_%", "Chart", "Koers", "Stop", "Risico_%", "Aandelen", "Sector"]
    if GEBRUIK_MARKTWAARDE_FILTER and "Mrkt_mld" in eind.columns:
        kolommen.insert(1, "Mrkt_mld")
        kolommen.insert(2, "Vol_mln")
    print(eind[kolommen].to_string(index=False))
    if GEBRUIK_MARKTWAARDE_FILTER:
        print("('Mrkt_mld' = marktwaarde in miljarden dollar,")
        print(" 'Vol_mln' = gemiddeld verhandeld bedrag per dag in miljoenen dollar)")
    print(f"\n{len(eind)} kandidaten van {len(out)} in het top-percentiel.")

    print("\n" + "=" * 78)
    print("WAAROM DEZE AANDELEN?")
    print("=" * 78)
    for _, r in eind.iterrows():
        tk = r["Ticker"]
        df_t = bruikbaar[tk]
        row_t = df_t.iloc[-1]
        info_t = ranking[tk]
        stop_t = compute_stop(row_t, row_t["Close"])
        regels, waarschuwingen = leg_keuze_uit(tk, row_t, info_t, df_t, stop_t)
        print(f"\n{tk}  (${row_t['Close']:.2f}, rang {info_t['percentiel']:.0f})")
        for regel in regels:
            print(f"   + {regel}")
        for w in waarschuwingen:
            print(f"   ! {w}")

    print("\n" + "-" * 78)
    print("RISICOBUDGET (portfolio heat)")
    print("-" * 78)
    print(f"  Max totaal open risico: {MAX_PORTFOLIO_HEAT*100:.0f}% van je account")
    print(f"  Bij {RISK_PCT_PER_TRADE*100:.0f}% per trade = maximaal {max_nieuw} posities tegelijk")
    print(f"  Je hebt nu {reeds_open} positie(s) open volgens {POSITIONS_FILE}")
    if ruimte == 0:
        print(f"\n  >> JE RISICOBUDGET IS VOL. Neem geen nieuwe posities tot er een")
        print(f"     positie sluit, hoe goed de kandidaten hierboven ook ogen.")
    elif ruimte < len(eind):
        print(f"\n  >> Er is ruimte voor {ruimte} nieuwe positie(s).")
        print(f"     Neem de bovenste {ruimte} uit de lijst (hoogste ranking) en sla de rest over.")
    else:
        print(f"\n  >> Er is ruimte voor alle {len(eind)} kandidaten.")

    extreem = eind[eind["Mom_%"] > 300]
    if len(extreem) > 0:
        print("\n" + "!" * 78)
        print("LET OP - EXTREEM MOMENTUM")
        print("!" * 78)
        for _, r in extreem.iterrows():
            print(f"  {r['Ticker']}: {r['Mom_%']:.0f}% in 6 maanden")
        print("Bij zulke bewegingen zit vaak een reverse split, overname of")
        print("speculatieve golf achter. Controleer de grafiek en het nieuws")
        print("voordat je hier iets mee doet - de scanner kan dat niet zien.")

    goedkoop = eind[eind["Koers"] < 5]
    if len(goedkoop) > 0:
        print("\nLET OP - lage koers (<$5): " + ", ".join(goedkoop["Ticker"]))
        print("Bij deze prijzen zijn de spreads relatief groot; je werkelijke")
        print("slippage ligt waarschijnlijk hoger dan de scanner aanneemt.")

    print("\n" + "=" * 78)
    print("HOE TE GEBRUIKEN")
    print("=" * 78)
    print("'Rang' = percentiel binnen het universum vandaag (100 = sterkste).")
    print("'Mom_%' = rendement over de meetperiode, exclusief de laatste week.")
    print(f"Max {MAX_HOLD_DAYS} dagen houden, stop zoals aangegeven, "
          f"{RISK_PCT_PER_TRADE*100:.0f}% risico per trade.")
    print()
    print("'Chart' = efficiency ratio: hoe rechtlijnig de koers beweegt.")
    print(f"   1.00 = kaarsrechte trend, {MIN_EFFICIENCY} = minimum, lager = barcode.")
    print()
    print("Gemeten over 48 maanden (6 walk-forward vensters):")
    print("   geen filters                   +0.45% per trade, win 50.5%")
    print("   + EMA9/21/300                  +0.85% per trade, win 51.0%")
    print("   + leesbaarheid (huidig)        +1.43% per trade, win 55.5%")
    print("Alle zes vensters positief - het meest consistente resultaat tot nu toe.")
    print()
    print("Prijs hiervan: je ziet aanzienlijk minder kandidaten (853 i.p.v. 2425")
    print("trades over 48 maanden). Dat is de bedoeling - kwaliteit boven aantal.")

    try:
        log = eind.copy()
        log.insert(0, "ScanDatum", datetime.now().strftime("%Y-%m-%d"))
        log.insert(1, "Methode", "ranking")
        header = not pd.io.common.file_exists(SCAN_LOG_FILE)
        log.to_csv(SCAN_LOG_FILE, mode="a", header=header, index=False)
        print(f"\nWeggeschreven naar {SCAN_LOG_FILE}.")
    except Exception as e:
        print(f"\nKon niet loggen ({e}) - de scan zelf is wel gelukt.")
    return eind


def scan_combi(min_score=55, max_results=25):
    """GECOMBINEERDE SCAN - herkent zowel aandelen die zich OPLADEN als
    aandelen die NU uitbreken, en beoordeelt beide op basis van wat onderzoek
    aanwijst als doorslaggevend:

      - kwaliteit van de basis (krappe basis ~51% slaging vs brede ~35%)
      - hoe vaak het weerstandsniveau getest is
      - volume-opdroging tijdens de basis, volume-piek bij de uitbraak
      - beslissende slotkoers i.p.v. een lont door het niveau
      - bevestiging door de weektrend
      - ruimte tot de volgende weerstand

    Aandelen die al te ver zijn doorgeschoten worden expliciet gemarkeerd als
    TE LAAT - dat was de gemeten zwakte van de oude scanner.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print(f"GECOMBINEERDE SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 74)
    print("Herkent zowel setups die zich OPLADEN als breakouts die NU gebeuren.")
    print("=" * 74)

    universe = get_nasdaq_universe(MAX_UNIVERSE_SIZE) if USE_FULL_NASDAQ_SCAN else list(WATCHLIST)
    print(f"\nUniversum: {len(universe)} tickers")

    spy = yf.download("SPY", period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]
    if not is_market_regime_bullish(spy):
        print("\nWAARSCHUWING: SPY onder zijn SMA50 - breakouts falen vaker in een")
        print("zwakke markt. De scan gaat door, wees extra kritisch.\n")

    all_data = {}
    n_chunks = (len(universe) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = universe[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=HIST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    all_data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    resultaten = []
    fase_telling = {"OPLADEN": 0, "BREEKT UIT": 0, "TE LAAT": 0, "VER WEG": 0, "onbekend": 0}

    for ticker in universe:
        try:
            df = all_data.get(ticker)
            if df is None:
                continue
            df = df.dropna()
            if len(df) < 60:
                continue
            df = compute_indicators(df, spy_close=spy)
            row = df.iloc[-1]
            if row[["ATR", "VOL_SMA20", "SMA50"]].isna().any():
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row["VOL_SMA20"] < 5_000_000:
                continue

            fase, afstand = bepaal_fase(df, row)
            fase_telling[fase] = fase_telling.get(fase, 0) + 1
            if fase in ("TE LAAT", "VER WEG", "onbekend"):
                continue

            basis = analyseer_basis_kwaliteit(df)

            if fase == "BREEKT UIT":
                score, redenen = scoor_breakout_kwaliteit(df, row, basis)
            else:  # OPLADEN
                k = detect_coiling_setup(df, row)
                score = k["score"]
                redenen = [f"volume {k.get('volume_dryup','?')}",
                           f"range {k.get('range_contraction','?')}",
                           k.get("positie", ""), k.get("trend", "")]
                if basis:
                    redenen.append(f"basis {basis['basis_kwaliteit']} ({basis['aantal_tests']}x getest)")

            if score < min_score:
                continue

            stop = compute_stop(row, row["Close"])
            risico = row["Close"] - stop
            aandelen = int((ACCOUNT_SIZE * RISK_PCT_PER_TRADE) / risico) if risico > 0 else 0
            aandelen = max(0, min(aandelen, int((ACCOUNT_SIZE * MAX_POSITION_PCT) / row["Close"])))
            pivot = row.get("HIGH20", np.nan)

            resultaten.append({
                "Ticker": ticker, "Fase": fase, "Score": score,
                "Koers": round(row["Close"], 2),
                "Niveau": round(pivot, 2) if not pd.isna(pivot) else None,
                "Afstand_%": round(afstand * 100, 1),
                "Stop": round(stop, 2), "Aandelen": aandelen,
                "_redenen": [r for r in redenen if r],
                "_basis": basis,
            })
        except Exception:
            continue

    print(f"\nFase-verdeling van het universum:")
    for f in ["OPLADEN", "BREEKT UIT", "TE LAAT", "VER WEG"]:
        print(f"   {f:12s} {fase_telling.get(f,0):5d}")
    print(f"   (TE LAAT = al te ver boven het niveau; die worden bewust overgeslagen)")

    if not resultaten:
        print(f"\nGeen kandidaten boven score {min_score}. Verlaag de drempel met --min-score.")
        return

    out = pd.DataFrame(resultaten).sort_values(["Fase", "Score"], ascending=[True, False]).head(max_results)

    for fase in ["BREEKT UIT", "OPLADEN"]:
        deel = out[out["Fase"] == fase]
        if len(deel) == 0:
            continue
        kop = "BREEKT NU UIT" if fase == "BREEKT UIT" else "LADEN OP (uitbraak moet nog komen)"
        print(f"\n{'=' * 74}\n{kop}\n{'=' * 74}")
        print(deel[["Ticker", "Score", "Koers", "Niveau", "Afstand_%", "Stop", "Aandelen"]].to_string(index=False))
        print()
        for _, r in deel.iterrows():
            print(f"  {r['Ticker']} (score {r['Score']}):")
            for reden in r["_redenen"]:
                print(f"      - {reden}")

    print("\n" + "=" * 74)
    print("HOE TE GEBRUIKEN:")
    print("  BREEKT UIT = het niveau is vandaag doorbroken. Score zegt hoe kansrijk")
    print("               op basis van basiskwaliteit, volume, slotkoers en weektrend.")
    print("  OPLADEN    = nog geen uitbraak. Zet op je watchlist en wacht tot de koers")
    print("               boven 'Niveau' sluit. Niet nu al kopen.")
    print()
    print("Onderzoek toont dat 50-70% van alle breakouts faalt, ook de mooie.")
    print("Gebruik altijd de stop, en beschouw dit als een gefilterde watchlist")
    print("- niet als een bewezen strategie. Deze modus is nog niet gebenchmarkt.")
    return out


def scan_coiling(min_score=60, max_results=20):
    """Zoekt aandelen die zich OPLADEN voor een uitbraak, i.p.v. aandelen die
    al gesprongen zijn. Toont per kandidaat in gewone taal WAAROM het een
    pre-breakout setup is, zodat je de grafiek zelf kunt beoordelen."""
    print(f"[versie {SCRIPT_VERSIE}]")
    print(f"PRE-BREAKOUT SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    print("Zoekt aandelen die SAMENDRUKKEN voor een uitbraak (volume droogt op,")
    print("range trekt samen, koers vlak onder de weerstand) - niet aandelen die")
    print("al gesprongen zijn. Dit is bewust het spiegelbeeld van de gewone scan.")
    print("=" * 70)

    universe = get_nasdaq_universe(MAX_UNIVERSE_SIZE) if USE_FULL_NASDAQ_SCAN else list(WATCHLIST)
    print(f"\nUniversum: {len(universe)} tickers")

    spy = yf.download("SPY", period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    all_data = {}
    n_chunks = (len(universe) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = universe[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=HIST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    all_data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    kandidaten = []
    for ticker in universe:
        try:
            df = all_data.get(ticker)
            if df is None:
                continue
            df = df.dropna()
            if len(df) < 60:
                continue
            df = compute_indicators(df, spy_close=spy)
            row = df.iloc[-1]
            if row[["ATR", "VOL_SMA20", "SMA50"]].isna().any():
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            # basale liquiditeitseis
            if row["Close"] * row["VOL_SMA20"] < 5_000_000:
                continue

            k = detect_coiling_setup(df, row)
            if k["score"] < min_score:
                continue

            pivot = row.get("HIGH20", np.nan)
            stop = compute_stop(row, row["Close"])
            risico_per_aandeel = row["Close"] - stop
            aandelen = int((ACCOUNT_SIZE * RISK_PCT_PER_TRADE) / risico_per_aandeel) if risico_per_aandeel > 0 else 0
            aandelen = min(aandelen, int((ACCOUNT_SIZE * MAX_POSITION_PCT) / row["Close"]))

            kandidaten.append({
                "Ticker": ticker, "Score": k["score"], "Koers": round(row["Close"], 2),
                "Uitbraak_bij": round(pivot, 2) if not pd.isna(pivot) else None,
                "Afstand_%": k.get("afstand_tot_pivot_pct"),
                "Stop": round(stop, 2), "Aandelen": max(aandelen, 0),
                "_kenmerken": k,
            })
        except Exception:
            continue

    if not kandidaten:
        print("\nGeen aandelen gevonden die zich momenteel opladen.")
        print(f"Verlaag min_score (nu {min_score}) als je bredere resultaten wilt.")
        return

    out = pd.DataFrame(kandidaten).sort_values("Score", ascending=False).head(max_results)

    print(f"\n{len(out)} aandelen die zich opladen voor een mogelijke uitbraak:\n")
    toon = out[["Ticker", "Score", "Koers", "Uitbraak_bij", "Afstand_%", "Stop", "Aandelen"]]
    print(toon.to_string(index=False))

    print("\n" + "=" * 70)
    print("WAAROM per kandidaat (zodat je de grafiek zelf kunt beoordelen):")
    print("=" * 70)
    for _, r in out.head(8).iterrows():
        k = r["_kenmerken"]
        print(f"\n{r['Ticker']}  (score {k['score']})")
        print(f"   Volume:    {k.get('volume_dryup','?')} (laatste 5d = {k.get('volume_dryup_ratio','?')}x het niveau ervoor)")
        print(f"   Range:     {k.get('range_contraction','?')} (samentrekking naar {k.get('range_contraction_ratio','?')}x)")
        print(f"   Positie:   {k.get('positie','?')}")
        print(f"   Trend:     {k.get('trend','?')}")
        if "bollinger" in k:
            print(f"   Bollinger: {k['bollinger']}")
        if "waarschuwing" in k:
            print(f"   LET OP:    {k['waarschuwing']}")
        if r["Uitbraak_bij"]:
            print(f"   -> Uitbraak bij een slot boven {r['Uitbraak_bij']}, stop op {r['Stop']}")

    print("\n" + "=" * 70)
    print("BELANGRIJK: dit zijn setups die zich OPLADEN, geen koopsignalen.")
    print("Een consolidatie kan net zo goed naar beneden breken. Wacht tot de")
    print("koers daadwerkelijk boven het uitbraakniveau sluit voordat je instapt.")
    print("Deze modus is nog NIET tegen de benchmark getest - behandel 'm als")
    print("een watchlist-generator, niet als een bewezen strategie.")
    return out


def scan_today(preset_name="balanced"):
    preset = PRESETS[preset_name]
    print(f"[versie {SCRIPT_VERSIE}]")
    print(f"Scan gestart: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  Preset: {preset_name.upper()}")

    universe = get_nasdaq_universe(MAX_UNIVERSE_SIZE) if USE_FULL_NASDAQ_SCAN else list(WATCHLIST)
    print(f"Universum: {len(universe)} tickers")
    print(f"Min. confidence: {preset['MIN_CONFIDENCE']}  |  Max signalen: {preset['MAX_SIGNALS_PER_DAY']}  "
          f"|  Max per sector: {MAX_SIGNALS_PER_SECTOR}")
    print(f"Account: {ACCOUNT_SIZE:,.0f}  |  Risico per trade: {RISK_PCT_PER_TRADE*100:.1f}% "
          f"({ACCOUNT_SIZE*RISK_PCT_PER_TRADE:,.0f})\n")

    spy = yf.download("SPY", period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    # --- marktregime: ALLEEN een waarschuwing, blokkeert de scan nooit meer ---
    # (eerder stopte de scan hier helemaal - dat bleek te rigide zonder bewezen nut)
    if not is_market_regime_bullish(spy):
        print("WAARSCHUWING: SPY sluit onder zijn eigen SMA50 - de bredere markt staat zwak.")
        print("Breakouts falen historisch vaker in zo'n markt, maar de scan gaat gewoon door.")
        print("Wees extra kritisch op de kandidaten hieronder.\n")

    # --- sector-ETF's ophalen (1x, gedeeld door alle tickers in dezelfde sector) ---
    unique_etfs = sorted(set(SECTOR_ETF.values()) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    print(f"Sector-ETF's ophalen ({len(unique_etfs)}: {', '.join(unique_etfs)})...")
    for etf in unique_etfs:
        try:
            s = yf.download(etf, period=HIST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            etf_data[etf] = s
        except Exception:
            etf_data[etf] = None

    all_data = {}
    n_chunks = (len(universe) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = universe[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks} ({len(batch)} tickers)...")
        try:
            batch_data = yf.download(batch, period=HIST_PERIOD, group_by="ticker",
                                      auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    all_data[t] = batch_data[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen door fout: {e}")

    # fase 1: goedkope technische pre-filter (geen fundamentals/earnings-calls)
    shortlist = []
    afgevallen = {"geen data": 0, "prijs buiten range": 0, "pump/dump-risico": 0,
                  "RVOL te laag": 0, "te ver boven pivot": 0, "trend te choppy": 0,
                  "module onder floor": 0, "confidence te laag": 0}
    for ticker in universe:
        try:
            df = all_data.get(ticker)
            if df is None:
                afgevallen["geen data"] += 1
                continue
            df = df.dropna()
            if len(df) < 60:
                afgevallen["geen data"] += 1
                continue
            sector_etf = get_sector_etf(ticker)
            df = compute_indicators(df, spy_close=spy)
            df = add_sector_rs(df, etf_data.get(sector_etf), spy)
            row = df.iloc[-1]
            if row[["RSI", "ATR", "VOL_SMA20", "SMA50"]].isna().any():
                afgevallen["geen data"] += 1
                continue
            price = row["Close"]
            if not (MIN_PRICE <= price <= MAX_PRICE):
                afgevallen["prijs buiten range"] += 1
                continue
            ok, _ = hard_filter_pump_dump(df, row, preset)
            if not ok:
                afgevallen["pump/dump-risico"] += 1
                continue
            ok, _ = hard_filter_rvol(row, preset)
            if not ok:
                afgevallen["RVOL te laag"] += 1
                continue
            ok, _ = hard_filter_extension(row, preset)
            if not ok:
                afgevallen["te ver boven pivot"] += 1
                continue
            ok, _, r2 = hard_filter_choppiness(df, preset)
            if not ok:
                afgevallen["trend te choppy"] += 1
                continue
            prelim_conf, prelim_sub = compute_confidence(df, row, r2, preset)
            if any(prelim_sub[m] < preset["MODULE_FLOOR"] for m in CORE_MODULES_WITH_FLOOR):
                afgevallen["module onder floor"] += 1
                continue
            if prelim_conf < preset["MIN_CONFIDENCE"] * 0.7:
                afgevallen["confidence te laag"] += 1
                continue
            shortlist.append(ticker)
        except Exception:
            afgevallen["geen data"] += 1
            continue

    print(f"\nTechnische voorselectie: {len(shortlist)} kandidaten (van {len(universe)})")
    print("Waar vielen de rest af? (hier zie je welke knop je moet draaien voor meer signalen)")
    for reden, aantal in sorted(afgevallen.items(), key=lambda x: -x[1]):
        if aantal > 0:
            knop = {
                "RVOL te laag": "  <- verlaag RVOL_MIN",
                "trend te choppy": "  <- verlaag TREND_R2_MIN",
                "confidence te laag": "  <- verlaag MIN_CONFIDENCE",
                "module onder floor": "  <- verlaag MODULE_FLOOR",
                "te ver boven pivot": "  <- verhoog MAX_EXTENSION",
                "prijs buiten range": "  <- pas MIN_PRICE / MAX_PRICE aan",
            }.get(reden, "")
            print(f"   {reden:24s} {aantal:5d}{knop}")
    print()

    results = []
    bijna = []
    for ticker in shortlist:
        try:
            sector_etf = get_sector_etf(ticker)
            df = compute_indicators(all_data[ticker].dropna(), spy_close=spy)
            df = add_sector_rs(df, etf_data.get(sector_etf), spy)
            fund = get_fundamentals(ticker)
            evald = evaluate_ticker_day(ticker, df, fund, preset, check_earnings=True)
            if evald is None:
                # net-niet-kandidaten registreren met een verlaagde drempel,
                # zodat de gebruiker ziet HOE dicht ze erbij zaten
                soepel = dict(preset)
                soepel["MIN_CONFIDENCE"] = 0
                soepel["MODULE_FLOOR"] = 0
                alt = evaluate_ticker_day(ticker, df, fund, soepel, check_earnings=False)
                if alt is not None:
                    bijna.append({"Ticker": ticker, "Confidence": alt["confidence"],
                                  "Koers": round(alt["row"]["Close"], 2)})
                continue

            row, confidence, sub_scores = evald["row"], evald["confidence"], evald["sub_scores"]
            close = row["Close"]
            stop = compute_stop(row, close)
            target = close + TARGET_ATR_MULT * row["ATR"]
            rr = (target - close) / (close - stop) if close > stop else float("nan")

            risk_per_share = close - stop
            risk_amount = ACCOUNT_SIZE * RISK_PCT_PER_TRADE
            shares_by_risk = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0
            shares_by_cap = int((ACCOUNT_SIZE * MAX_POSITION_PCT) / close) if close > 0 else 0
            shares = max(min(shares_by_risk, shares_by_cap), 0)

            results.append({
                "Ticker": ticker,
                "Sector": sector_etf,
                "Confidence": confidence,
                "Close": round(close, 2),
                "Stop": round(stop, 2),
                "Target": round(target, 2),
                "R:R": round(rr, 2),
                "Aandelen": shares,
                "Positie($)": round(shares * close, 2),
                "Risico($)": round(shares * risk_per_share, 2),
                "Trend": sub_scores["trend"],
                "Moment.": sub_scores["momentum"],
                "Volume": sub_scores["volume"],
                "Volat.": sub_scores["volatility"],
                "RS": sub_scores["rs"],
                "Catalyst": sub_scores["catalyst"],
                "Struct": sub_scores["structuur"],
            })
        except Exception as e:
            print(f"  [{ticker}] overgeslagen door fout: {e}")
            continue

    if not results:
        print("Geen kandidaten haalden de eindscore van "
              f"{preset['MIN_CONFIDENCE']}.")
        if bijna:
            bijna_df = pd.DataFrame(bijna).sort_values("Confidence", ascending=False).head(10)
            print(f"\nDe {len(bijna_df)} hoogst scorende kandidaten die het NET niet haalden:")
            print(bijna_df.to_string(index=False))
            hoogste = bijna_df["Confidence"].iloc[0]
            print(f"\nHoogste score vandaag: {hoogste}  (drempel staat op {preset['MIN_CONFIDENCE']})")
            if hoogste >= preset["MIN_CONFIDENCE"] - 15:
                print("-> Deze zaten er dichtbij. Draai 'run_sweep_conf.bat' om te meten")
                print("   welke drempel past bij je huidige RVOL-instelling.")
        else:
            print("Er kwam vandaag niets door de voorselectie - zie de tabel hierboven.")
        return

    # --- spreidingscontrole: max N signalen per sector, ook al scoren er meer ---
    all_ranked = pd.DataFrame(results).sort_values("Confidence", ascending=False)
    selected = []
    sector_counts = {}
    for _, r in all_ranked.iterrows():
        sec = r["Sector"]
        if sector_counts.get(sec, 0) >= preset.get("MAX_PER_SECTOR", MAX_SIGNALS_PER_SECTOR):
            continue
        selected.append(r)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
        if len(selected) >= preset["MAX_SIGNALS_PER_DAY"]:
            break
    out = pd.DataFrame(selected)

    n_dropped_by_sector = len(all_ranked) - len(out)
    print(out.to_string(index=False))
    print(f"\n{len(out)} signalen (max {preset['MAX_SIGNALS_PER_DAY']} voor preset '{preset_name}', "
          f"max {MAX_SIGNALS_PER_SECTOR} per sector).")
    if n_dropped_by_sector > 0:
        print(f"({n_dropped_by_sector} andere kandidaten met een hogere/lagere score niet getoond "
              f"om te veel gelijktijdige blootstelling aan dezelfde sector te voorkomen)")
    print("LET OP: confidence-score is een heuristische combinatie, geen garantie op winst.")
    print("Stop/target zijn exclusief slippage/kosten. Gebruik altijd de stop-loss.")

    _log_scan_results(out, preset_name)
    return out


def _log_scan_results(out, preset_name):
    """Schrijft de signalen van vandaag weg naar een lokaal CSV-logbestand,
    zodat je later kan vergelijken wat de scanner live aanraadde met wat
    er werkelijk gebeurde - de enige echte manier om de backtest-aannames
    te toetsen aan de realiteit."""
    try:
        log_entry = out.copy()
        log_entry.insert(0, "ScanDatum", datetime.now().strftime("%Y-%m-%d"))
        log_entry.insert(1, "Preset", preset_name)
        header = not pd.io.common.file_exists(SCAN_LOG_FILE)
        log_entry.to_csv(SCAN_LOG_FILE, mode="a", header=header, index=False)
        print(f"\nSignalen weggeschreven naar {SCAN_LOG_FILE} (voor latere vergelijking met de werkelijkheid).")
    except Exception as e:
        print(f"\nKon scan-log niet wegschrijven ({e}) - dit is niet kritiek, de scan zelf is wel gelukt.")


# ============================================================================
# BACKTEST (met train/test-split)
# ============================================================================

def run_random_entry_benchmark(price_data, fund_cache, signals_per_ticker, preset,
                                n_simulations=20, seed=7):
    """DE BELANGRIJKSTE TEST DIE ONTBRAK.

    Vraag: voegt de SELECTIE van de scanner iets toe, of komt het rendement
    volledig uit de exit-logica (trailing stop / partial exit) plus algemene
    marktdrift?

    Methode: neem exact evenveel trades per ticker als de scanner vond, maar
    kies de instapdagen WILLEKEURIG. Pas daarna precies dezelfde exit-regels,
    slippage en kosten toe. Herhaal dat n_simulations keer.

    Interpretatie:
      - scanner >> random  -> de selectiecriteria voegen aantoonbaar waarde toe
      - scanner ~= random  -> je rendement komt uit de exits/markt, niet uit de
                              selectie. Alle moeite in filters is dan verspild.
      - scanner << random  -> de filters selecteren actief slechtere momenten
    """
    rng = np.random.default_rng(seed)
    sim_means = []

    for sim in range(n_simulations):
        sim_returns = []
        for ticker, n_signals in signals_per_ticker.items():
            if n_signals == 0 or ticker not in price_data:
                continue
            df_full = price_data[ticker]
            fund = fund_cache.get(ticker, {})
            valid_range = range(55, len(df_full) - 1)
            if len(valid_range) < n_signals:
                continue
            chosen = rng.choice(list(valid_range), size=n_signals, replace=False)

            for i in chosen:
                row = df_full.iloc[i]
                if pd.isna(row.get("ATR", np.nan)):
                    continue
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                initial_stop = compute_stop(row, entry)
                ret_pct, outcome, _ = simulate_trailing_exit(
                    future, entry, row["ATR"], preset, initial_stop=initial_stop)
                if "stop" in outcome:
                    avg_vol = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                    slip = get_dynamic_slippage((avg_vol or 0) * entry)
                    ret_pct -= slip * 100
                ret_pct -= COMMISSION_PCT * 2 * 100
                sim_returns.append(ret_pct)

        if sim_returns:
            sim_means.append(np.mean(sim_returns))

    return sim_means


def vergelijk_met_kopen_en_vasthouden(tdf, spy, price_data, metrics):
    """DE ONTBREKENDE EINDVERGELIJKING.

    Alle vorige metingen vergeleken de scanner met andere manieren van traden.
    Maar de echte vraag voor iemand die z'n geld ergens moet parkeren is:
    verslaat dit gewoon SPY kopen en niks doen?

    Als het antwoord nee is, dan is alle moeite (schermtijd, stress, kosten,
    belasting op korte-termijnwinst) verspild, hoe elegant de strategie ook is.
    Dit is de vergelijking die de meeste hobbytraders nooit maken."""
    print("\n" + "=" * 62)
    print("EINDVERGELIJKING: was al dit werk beter dan niets doen?")
    print("=" * 62)

    # 1. SPY kopen en vasthouden over dezelfde periode
    spy_start, spy_eind = float(spy.iloc[0]), float(spy.iloc[-1])
    spy_rendement = (spy_eind / spy_start - 1) * 100
    jaren = len(spy) / 252
    spy_jaarlijks = ((spy_eind / spy_start) ** (1 / jaren) - 1) * 100 if jaren > 0 else 0

    # 2. de watchlist kopen en vasthouden (gelijk gewogen)
    wl_rendementen = []
    for ticker, df in price_data.items():
        try:
            if len(df) > 60:
                wl_rendementen.append((df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100)
        except Exception:
            continue
    wl_rendement = float(np.mean(wl_rendementen)) if wl_rendementen else float("nan")

    # 3. de strategie
    strategie_rendement = metrics["total_return"] if metrics else float("nan")

    print(f"\nPeriode: {jaren:.1f} jaar\n")
    print(f"  {'SPY kopen en vasthouden:':38s} {spy_rendement:+8.1f}%   ({spy_jaarlijks:+.1f}% per jaar)")
    if not np.isnan(wl_rendement):
        print(f"  {'Je watchlist kopen en vasthouden:':38s} {wl_rendement:+8.1f}%   (gelijk gewogen)")
    print(f"  {'De scanner-strategie:':38s} {strategie_rendement:+8.1f}%")
    if metrics:
        print(f"  {'   ... met een drawdown van':38s} {metrics['max_drawdown']:+8.1f}%")

    print()
    if not np.isnan(strategie_rendement):
        if strategie_rendement > spy_rendement:
            verschil = strategie_rendement - spy_rendement
            print(f"  -> De strategie versloeg SPY met {verschil:.1f} procentpunt.")
            print("     Weeg wel mee: uren schermtijd, transactiekosten, belasting op")
            print("     korte-termijnwinst, en het risico van geconcentreerde posities.")
        else:
            achterstand = spy_rendement - strategie_rendement
            print(f"  -> SPY kopen en niks doen was {achterstand:.1f} procentpunt BETER.")
            print("     Zonder schermtijd, zonder stress, met minder risico en lagere kosten.")
            print("     Dit is de belangrijkste uitkomst van de hele backtest: als een")
            print("     indexfonds je verslaat, is actief traden je tijd niet waard -")
            print("     hoe verfijnd de strategie ook is.")

    print("\n  (LET OP: deze periode was overwegend een stijgende markt. In een")
    print("   dalende markt presteert kopen-en-vasthouden juist slecht, terwijl een")
    print("   strategie met stops kapitaal kan beschermen. Eén periode is geen bewijs.)")


def compute_portfolio_metrics(tdf, risk_pct=RISK_PCT_PER_TRADE):
    """Portfolio-metrics i.p.v. alleen per-trade gemiddelden. Een hedgefonds
    kijkt hier als eerste naar: niet 'wat verdient een trade gemiddeld' maar
    'hoe ziet de kapitaalcurve eruit en hoe diep is de ergste terugval'.

    Aanname: elke trade riskeert risk_pct van het kapitaal, en het rendement
    schaalt met de verhouding rendement/stopafstand. Vereenvoudigd (geen
    gelijktijdige posities), maar geeft wel een beeld van pad en drawdown."""
    if len(tdf) < 5:
        return None
    df = tdf.sort_values("Datum").copy()
    # vereenvoudigde positieschaling: rendement per trade x risicofractie
    equity = [1.0]
    for r in df["Rendement_%"]:
        equity.append(equity[-1] * (1 + (r / 100) * (risk_pct / 0.05)))
    eq = pd.Series(equity[1:], index=df.index)
    total_return = (eq.iloc[-1] - 1) * 100
    running_max = eq.cummax()
    max_dd = ((eq / running_max - 1) * 100).min()
    per_trade = df["Rendement_%"]
    sharpe_like = per_trade.mean() / per_trade.std() if per_trade.std() > 0 else 0
    wins = per_trade[per_trade > 0].sum()
    losses = abs(per_trade[per_trade < 0].sum())
    profit_factor = wins / losses if losses > 0 else float("inf")
    return {
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe_like": sharpe_like,
        "profit_factor": profit_factor,
        "equity_end": eq.iloc[-1],
    }


# ============================================================================
# CROSS-SECTIONELE RANKING (relatieve i.p.v. absolute selectie)
# ============================================================================
# Onderzoeksbasis: Jegadeesh & Titman (1993) en de bredere momentum-literatuur.
# Fama en French noemden momentum de "premier anomaly" - het is een van de best
# gedocumenteerde rendementspatronen in de financiele wetenschap.
#
# Waarom dit fundamenteel anders is dan wat deze scanner tot nu toe deed:
#   ABSOLUUT (oud): "is RVOL > 0.8 en confidence > 60?"  -> vaste lat
#   RELATIEF (nieuw): "hoort dit bij de sterkste 10% van vandaag?" -> meebewegende lat
#
# Het probleem met vaste drempels is gedocumenteerd: wat een "winnaar" is,
# verschuift met de markt. In de internetbubbel had je 250% rendement nodig om
# in het bovenste deciel te vallen; in de crisis van 2008/09 was alles boven -5%
# al genoeg. Een vaste drempel laat in een sterke markt rommel door en in een
# zwakke markt het verkeerde - precies het patroon dat venster 6 liet zien.
#
# Twee details uit de literatuur die meegenomen zijn:
#   - SKIP-MONTH: de meest recente periode wordt overgeslagen bij het meten van
#     momentum, omdat daar een korte-termijn-omkeereffect in zit.
#   - TOP-N: kapitaal concentreren in de sterkste namen i.p.v. spreiden over
#     alles wat toevallig door een filter komt.

def bereken_momentum_score(df, lookback=MOMENTUM_LOOKBACK, skip=MOMENTUM_SKIP):
    """Momentum over 'lookback' dagen, met de laatste 'skip' dagen eruit.

    Die skip is geen detail: de meest recente dagen vertonen een omkeereffect
    (bid-ask bounce, korte-termijn-liquiditeit) dat een momentumportefeuille
    schaadt. Ze overslaan verbetert het resultaat volgens de literatuur
    merkbaar - en het sluit aan bij wat we in deze scanner zelf maten, namelijk
    dat instappen direct na een sprong slecht uitpakt."""
    if len(df) < lookback + skip + 1:
        return np.nan
    eind = df["Close"].iloc[-(skip + 1)]
    begin = df["Close"].iloc[-(lookback + skip + 1)]
    if begin <= 0:
        return np.nan
    return float((eind / begin - 1) * 100)


def bereken_samengesteld_momentum(df, methode="multi"):
    """SAMENGESTELDE MOMENTUM-SCORE.

    Het probleem met een enkel getal: twee aandelen met beide +80% over zes
    maanden kunnen totaal anders zijn opgebouwd. De een klom gestaag, de ander
    sprong 60% in een week en zat daarna stil. De huidige ranking ziet dat
    verschil niet - hij kijkt alleen naar begin- en eindpunt.

    Drie varianten:
      "enkel"    - huidige methode: alleen 126 dagen
      "multi"    - gemiddelde van 63, 126 en 252 dagen. Een aandeel moet op
                   meerdere horizonnen sterk zijn, niet alleen toevallig op een.
      "gewogen"  - zelfde drie horizonnen, maar de kortste weegt zwaarder
                   (50/30/20), omdat recente kracht meer zegt over de komende
                   week dan kracht van een jaar geleden.

    Alle varianten gebruiken dezelfde skip-periode (laatste week eruit) wegens
    het korte-termijn-omkeereffect.
    """
    if methode == "enkel":
        return bereken_momentum_score(df, MOMENTUM_LOOKBACK)

    horizonnen = [63, 126, 252]
    gewichten = {"multi": [1/3, 1/3, 1/3], "gewogen": [0.5, 0.3, 0.2]}[methode]

    scores = []
    for h in horizonnen:
        m = bereken_momentum_score(df, h)
        if np.isnan(m):
            return np.nan       # alle horizonnen nodig, anders niet vergelijkbaar
        scores.append(m)
    return float(sum(s * g for s, g in zip(scores, gewichten)))


def bereken_gerealiseerde_volatiliteit(df, lookback, skip=MOMENTUM_SKIP):
    """Gerealiseerde volatiliteit over dezelfde periode als de momentum-meting,
    op jaarbasis. Gebruikt exact hetzelfde venster (inclusief de skip), zodat
    teller en noemer over dezelfde dagen gaan."""
    if len(df) < lookback + skip + 2:
        return np.nan
    venster = df["Close"].iloc[-(lookback + skip + 1):-(skip + 1)] if skip > 0 \
        else df["Close"].iloc[-(lookback + 1):]
    rend = venster.pct_change().dropna()
    if len(rend) < 20 or rend.std() == 0:
        return np.nan
    return float(rend.std() * np.sqrt(252) * 100)


def bereken_risico_gecorrigeerd_momentum(df, methode="multi"):
    """RISICO-GECORRIGEERD MOMENTUM (Barroso & Santa-Clara-principe).

    Het probleem met ruw momentum: +60% behaald met 15% volatiliteit en +60%
    behaald met 60% volatiliteit krijgen dezelfde score. De literatuur toont
    echter dat aandelen met hoge gerealiseerde volatiliteit tijdens de
    meetperiode hun momentum-effect grotendeels verliezen - de stijging was
    ruis, geen trend.

    Onderbouwing: Barroso & Santa-Clara (2015) vonden dat risicobeheer van
    momentum de crashes vrijwel elimineert en de Sharpe-ratio bijna verdubbelt.
    Daniel & Moskowitz (2016), Fan e.a. (2018) en Dierkes & Krupski (2022)
    komen onafhankelijk tot dezelfde conclusie.

    Berekening: momentum gedeeld door de gerealiseerde volatiliteit over
    dezelfde periode. Dat is in feite een Sharpe-achtige maat per aandeel.

    Verschil met het bestaande leesbaarheidsfilter: dat is een ja/nee-drempel
    op 0.35 - alles erboven telt gelijk. Dit maakt er een glijdende schaal van,
    waarbij een aandeel met lage volatiliteit hoger rangschikt dan een even
    sterk gestegen aandeel dat wild heen en weer bewoog.
    """
    horizonnen = [63, 126, 252] if methode != "enkel" else [MOMENTUM_LOOKBACK]
    scores = []
    for h in horizonnen:
        m = bereken_momentum_score(df, h)
        v = bereken_gerealiseerde_volatiliteit(df, h)
        if np.isnan(m) or np.isnan(v) or v <= 0:
            return np.nan
        scores.append(m / v)          # rendement per eenheid risico
    return float(np.mean(scores))


def rangschik_universum_v3(alle_data, methode="multi"):
    """Rangschikt op RISICO-GECORRIGEERD momentum."""
    scores = {}
    for ticker, df in alle_data.items():
        try:
            m = bereken_risico_gecorrigeerd_momentum(df, methode)
            if not np.isnan(m):
                scores[ticker] = m
        except Exception:
            continue
    if len(scores) < 10:
        return {}
    serie = pd.Series(scores)
    percentielen = serie.rank(pct=True) * 100
    return {t: {"momentum": round(serie[t], 3), "percentiel": round(percentielen[t], 1)}
            for t in serie.index}


def rangschik_universum_v2(alle_data, methode="multi"):
    """Zoals rangschik_universum, maar met een samengestelde momentum-score."""
    scores = {}
    for ticker, df in alle_data.items():
        try:
            m = bereken_samengesteld_momentum(df, methode)
            if not np.isnan(m):
                scores[ticker] = m
        except Exception:
            continue
    if len(scores) < 10:
        return {}
    serie = pd.Series(scores)
    percentielen = serie.rank(pct=True) * 100
    return {t: {"momentum": round(serie[t], 1), "percentiel": round(percentielen[t], 1)}
            for t in serie.index}


def rangschik_universum(alle_data, spy=None, lookback=MOMENTUM_LOOKBACK):
    """Rangschikt het hele universum op momentum en geeft per ticker een
    percentiel terug (0-100, waarbij 100 = sterkste van het universum).

    Dit is de kern van de relatieve aanpak: een aandeel wordt niet beoordeeld
    tegen een vaste lat, maar tegen alle andere aandelen op datzelfde moment."""
    scores = {}
    for ticker, df in alle_data.items():
        try:
            m = bereken_momentum_score(df, lookback)
            if not np.isnan(m):
                scores[ticker] = m
        except Exception:
            continue
    if len(scores) < 10:
        return {}
    serie = pd.Series(scores)
    percentielen = serie.rank(pct=True) * 100
    return {t: {"momentum": round(serie[t], 1), "percentiel": round(percentielen[t], 1)}
            for t in serie.index}


def meet_marktregime(spy, tot_datum=None, lookback=126):
    """Beschrijft het marktregime op een bepaald moment met 5 kenmerken.
    Gebruikt ALLEEN data tot en met tot_datum - geen informatie uit de toekomst."""
    s = spy if tot_datum is None else spy[spy.index <= tot_datum]
    if len(s) < lookback:
        return None
    venster = s.iloc[-lookback:]
    dagrend = venster.pct_change().dropna()
    sma50 = s.rolling(50).mean()
    sma200 = s.rolling(200).mean()
    piek = venster.cummax()
    return {
        "rendement": float((venster.iloc[-1] / venster.iloc[0] - 1) * 100),
        "volatiliteit": float(dagrend.std() * (252 ** 0.5) * 100),
        "pct_boven_sma50": float((venster > sma50.reindex(venster.index)).mean() * 100),
        "max_drawdown": float(((venster / piek - 1) * 100).min()),
        "trend_sterkte": float(((s.iloc[-1] / sma200.iloc[-1] - 1) * 100)
                                if not pd.isna(sma200.iloc[-1]) else 0.0),
    }


def test_trendfilters(preset_name="balanced", top_pct=TOP_N_PERCENTIEL):
    """Test of een EMA21-eis bovenop de ranking helpt of kost.

    De vraag: een aandeel kan een sterk halfjaar hebben gehad en toch onder
    zijn EMA21 hangen omdat het de laatste weken terugvalt. Moet je die eruit
    filteren?

    Argument VOOR: het onderscheidt "was sterk" van "is nog steeds sterk".
    Argument TEGEN: de momentum-literatuur slaat de recente periode bewust
    over (skip-month) omdat daar een omkeereffect in zit. Een EMA21-eis werkt
    daar deels tegenin door juist recente kracht te vereisen.

    Vier varianten worden vergeleken over dezelfde walk-forward vensters:
      1. ranking kaal
      2. ranking + boven EMA21
      3. ranking + boven EMA9 EN EMA21 (strenger)
      4. ranking + EMA9 boven EMA21 (stijgende structuur, niet de koers zelf)
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print("TEST: helpt een EMA-filter bovenop de ranking?")
    print("=" * 78)
    print("Zelfde ranking, zelfde exits, zelfde kosten. Alleen een extra eis.\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}

    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 200:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue

    if len(voorbereid) < 15:
        print("Te weinig tickers met genoeg historie.")
        return

    def _boven(r, kolom):
        w = r.get(kolom, np.nan)
        return (not pd.isna(w)) and r["Close"] > w

    def _huidig(r):
        return (r["Close"] > r["EMA21"] and r["EMA9"] > r["EMA21"]
                and _boven(r, "EMA300"))

    def _leesbaar(r, drempel=0.35):
        e = r.get("EFFICIENCY", np.nan)
        return (not pd.isna(e)) and e >= drempel

    varianten = {
        "1. Geen extra filter":       lambda r: True,
        "2. Huidig (EMA9/21/300)":    _huidig,
        "3. Huidig + boven VWAP":     lambda r: _huidig(r) and bool(r.get("ABOVE_VWAP", False)),
        "4. Huidig + leesbaar":       lambda r: _huidig(r) and _leesbaar(r),
        "5. Huidig + VWAP + leesbaar": lambda r: (_huidig(r) and bool(r.get("ABOVE_VWAP", False))
                                                   and _leesbaar(r)),
        "6. Alleen leesbaar":         _leesbaar,
    }

    trades = {naam: [] for naam in varianten}

    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    start_idx = 200
    drempel = 100 - top_pct
    print(f"  {len(alle_dagen) - start_idx} handelsdagen doorlopen...")

    for di in range(start_idx, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {}
        for t, df in voorbereid.items():
            deel = df[df.index <= dag]
            if len(deel) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1:
                tot_nu[t] = deel
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)

        for ticker, deel in tot_nu.items():
            if deel.index[-1] != dag:
                continue
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            if i + 1 + MAX_HOLD_DAYS > len(df_full):
                continue
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA21", np.nan)):
                continue
            if pd.isna(row.get("SMA50", np.nan)):
                continue
            # EMA200/EMA300 mogen NaN zijn (jonge aandelen) - de _boven-helper
            # behandelt dat als "niet doorgelaten", wat het juiste gedrag is
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue

            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop = compute_stop(row, entry)
            r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100

            for naam, check in varianten.items():
                try:
                    if check(row):
                        trades[naam].append({"Datum": dag, "Rendement": r})
                except Exception:
                    continue

    print()
    print("=" * 78)
    print("RESULTAAT")
    print("=" * 78)
    print(f"{'Variant':<30}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 78)
    samenvatting = {}
    for naam, lijst in trades.items():
        if len(lijst) < 30:
            print(f"{naam:<30}{len(lijst):>9}   te weinig")
            continue
        tdf = pd.DataFrame(lijst)
        arr = tdf["Rendement"].values
        samenvatting[naam] = tdf
        print(f"{naam:<30}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}{np.median(arr):>10.2f}")

    if len(samenvatting) >= 2:
        print("\n" + "=" * 78)
        print("PER VENSTER")
        print("=" * 78)
        basis = samenvatting.get("1. Geen trendfilter")
        alle = pd.concat(samenvatting.values())
        start, eind = alle["Datum"].min(), alle["Datum"].max()
        lengte = (eind - start).days // 6
        kop = f"{'Venster':<9}" + "".join(f"{n.split('.')[0]:>10}" for n in samenvatting)
        print(kop)
        print("-" * 78)
        wint_vaker = {n: 0 for n in samenvatting}
        geldig = 0
        for v in range(6):
            v_start = start + pd.Timedelta(days=lengte*v)
            v_eind = v_start + pd.Timedelta(days=lengte)
            regel = f"{v+1:<9}"
            gemiddelden = {}
            ok = True
            for naam, tdf in samenvatting.items():
                deel = tdf[(tdf["Datum"] >= v_start) & (tdf["Datum"] < v_eind)]["Rendement"]
                if len(deel) < 10:
                    ok = False
                    break
                gemiddelden[naam] = deel.mean()
                regel += f"{deel.mean():>10.2f}"
            if not ok:
                continue
            geldig += 1
            beste = max(gemiddelden.items(), key=lambda x: x[1])[0]
            wint_vaker[beste] += 1
            print(regel)
        print("=" * 78)
        print("\nAantal vensters waarin elke variant de beste was:")
        for naam, n in sorted(wint_vaker.items(), key=lambda x: -x[1]):
            print(f"   {naam:<30} {n}/{geldig}")

        beste_totaal = max(samenvatting.items(), key=lambda x: x[1]["Rendement"].mean())
        print(f"\nHoogste gemiddelde: {beste_totaal[0]} "
              f"({beste_totaal[1]['Rendement'].mean():+.3f}% per trade)")
        if basis is not None:
            verschil = beste_totaal[1]["Rendement"].mean() - basis["Rendement"].mean()
            print(f"Verschil t.o.v. geen trendfilter: {verschil:+.3f} procentpunt")
            if beste_totaal[0] == "1. Geen trendfilter":
                print("\n-> Geen enkel trendfilter verbetert de ranking. Toevoegen zou")
                print("   het resultaat verslechteren - laat de scan zoals hij is.")
            elif wint_vaker[beste_totaal[0]] >= geldig * 0.6:
                print(f"\n-> {beste_totaal[0]} is beter EN wint in de meeste vensters.")
                print("   Dat rechtvaardigt het toevoegen aan de scan.")
            else:
                print(f"\n-> {beste_totaal[0]} heeft het hoogste gemiddelde, maar wint niet")
                print("   consistent per venster. Zwak bewijs - voorzichtig mee zijn.")
    return samenvatting


def vergelijk_ranking_vs_drempels(preset_name="balanced", top_pct=TOP_N_PERCENTIEL):
    """DE BESLISSENDE VERGELIJKING: relatieve ranking versus vaste drempels.

    Beide methodes krijgen dezelfde data, dezelfde exits, dezelfde kosten en
    dezelfde walk-forward vensters. Het enige verschil is HOE er geselecteerd
    wordt:
      A) drempels (huidig): RVOL > x, confidence > y  -> vaste lat
      B) ranking (nieuw):   hoort bij de sterkste top_pct% van vandaag

    Als B beter is over meerdere vensters, is dat een echte verbetering en geen
    toevalstreffer. Is B niet beter, dan blijft A staan - dan hebben we
    tenminste uitgesloten dat dit het probleem was.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print("RANKING versus DREMPELS")
    print("=" * 78)
    print("Zelfde data, zelfde exits, zelfde kosten. Alleen de SELECTIE verschilt.")
    print(f"  A) Drempels (huidig): RVOL >= {PRESETS[preset_name]['RVOL_MIN']}, "
          f"confidence >= {PRESETS[preset_name]['MIN_CONFIDENCE']}")
    print(f"  B) Ranking (nieuw):   sterkste {top_pct}% op 6-maands momentum\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 200:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            voorbereid[ticker] = df_full
        except Exception:
            continue

    if len(voorbereid) < 15:
        print("Te weinig tickers met genoeg historie voor een ranking-vergelijking.")
        return

    # gemeenschappelijke handelsdagen bepalen
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    start_idx = 200
    trades_drempel, trades_ranking = [], []

    print(f"  {len(alle_dagen) - start_idx} handelsdagen doorlopen voor beide methodes...")
    for di in range(start_idx, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]

        # --- momentum-ranking van het hele universum op DEZE dag ---
        tot_nu = {}
        for t, df in voorbereid.items():
            deel = df[df.index <= dag]
            if len(deel) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1:
                tot_nu[t] = deel
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        drempel_pct = 100 - top_pct

        for ticker, deel in tot_nu.items():
            if deel.index[-1] != dag:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            if i + 1 + MAX_HOLD_DAYS > len(df_full):
                continue
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)):
                continue
            fund = fund_cache.get(ticker, {})

            def voer_uit(lijst):
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    return
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                lijst.append({"Datum": dag, "Ticker": ticker, "Rendement": r})

            # A) huidige drempel-methode
            evald = evaluate_ticker_day(ticker, deel, fund, preset, check_earnings=False)
            if evald is not None:
                voer_uit(trades_drempel)

            # B) ranking-methode: alleen basisliquiditeit + top-percentiel
            info = ranking.get(ticker)
            if info and info["percentiel"] >= drempel_pct:
                prijs_ok = MIN_PRICE <= row["Close"] <= MAX_PRICE
                liq_ok = row["Close"] * row.get("VOL_SMA20", 0) >= 5_000_000
                if prijs_ok and liq_ok:
                    voer_uit(trades_ranking)

    print()
    print("=" * 78)
    print("RESULTAAT")
    print("=" * 78)
    resultaten = {}
    for naam, lijst in [("A) Drempels (huidig)", trades_drempel), ("B) Ranking (nieuw)", trades_ranking)]:
        if len(lijst) < 30:
            print(f"{naam}: te weinig trades ({len(lijst)})")
            continue
        tdf = pd.DataFrame(lijst)
        arr = tdf["Rendement"].values
        resultaten[naam] = tdf
        print(f"\n{naam}")
        print(f"   Trades: {len(arr)}   Gem: {arr.mean():+.3f}%   "
              f"Win rate: {(arr > 0).mean()*100:.1f}%   Mediaan: {np.median(arr):+.2f}%")

    if len(resultaten) == 2:
        # per walk-forward venster vergelijken
        print("\n" + "=" * 78)
        print("PER VENSTER (robuustheidscheck)")
        print("=" * 78)
        alle = pd.concat(resultaten.values())
        start, eind = alle["Datum"].min(), alle["Datum"].max()
        n_v = 6
        lengte = (eind - start).days // n_v
        print(f"{'Venster':<9}{'Periode':<26}{'Drempels':>12}{'Ranking':>12}{'Beter':>10}")
        print("-" * 78)
        ranking_wint = 0
        geldig = 0
        for v in range(n_v):
            v_start = start + pd.Timedelta(days=lengte * v)
            v_eind = v_start + pd.Timedelta(days=lengte)
            a = resultaten["A) Drempels (huidig)"]
            b = resultaten["B) Ranking (nieuw)"]
            a_deel = a[(a["Datum"] >= v_start) & (a["Datum"] < v_eind)]["Rendement"]
            b_deel = b[(b["Datum"] >= v_start) & (b["Datum"] < v_eind)]["Rendement"]
            if len(a_deel) < 10 or len(b_deel) < 10:
                continue
            geldig += 1
            winnaar = "ranking" if b_deel.mean() > a_deel.mean() else "drempels"
            if winnaar == "ranking":
                ranking_wint += 1
            print(f"{v+1:<9}{str(v_start.date())+' - '+str(v_eind.date()):<26}"
                  f"{a_deel.mean():>12.2f}{b_deel.mean():>12.2f}{winnaar:>10}")

        print("=" * 78)
        a_gem = resultaten["A) Drempels (huidig)"]["Rendement"].mean()
        b_gem = resultaten["B) Ranking (nieuw)"]["Rendement"].mean()
        print(f"\nRanking wint in {ranking_wint} van {geldig} vensters.")
        print(f"Totaal: drempels {a_gem:+.3f}%  vs  ranking {b_gem:+.3f}% per trade")
        print()
        if ranking_wint >= geldig * 0.7 and b_gem > a_gem:
            print("-> RANKING IS BETER, en consistent over de vensters heen.")
            print("   Dat rechtvaardigt overstappen: een relatieve lat beweegt mee met")
            print("   de markt, een vaste lat niet. Dit is precies waarom venster 6")
            print("   met vaste drempels faalde.")
        elif b_gem > a_gem:
            print("-> Ranking scoort hoger in totaal, maar niet consistent per venster.")
            print("   Dat is zwakker bewijs - mogelijk gedreven door een enkele periode.")
        else:
            print("-> Ranking is NIET beter dan de huidige drempels op deze data.")
            print("   Goed om te weten: dan was dat niet het probleem, en kun je de")
            print("   huidige instellingen houden.")
    return resultaten


def regime_monitor(preset_name="balanced"):
    """REGIME-MONITOR - vergelijkt het marktregime van de GOEDE walk-forward
    vensters met dat van het SLECHTE venster, en beoordeelt vervolgens waar de
    markt vandaag staat.

    De vraag die dit beantwoordt: was venster 6 (-1.45%) gewoon pech, of was de
    marktomgeving daar wezenlijk anders? En zo ja, lijkt vandaag daarop?

    Dit is geen voorspelling. Het is een waarschuwingslampje: als de huidige
    omstandigheden sterk lijken op de periode waarin de strategie faalde, is
    dat een reden om voorzichtiger te zijn - niet om te stoppen.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 76)
    print("REGIME-MONITOR")
    print("=" * 76)
    print("Vergelijkt de marktomgeving van goede vs. slechte periodes,")
    print("en beoordeelt waar de markt vandaag staat.\n")

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    # dezelfde venster-indeling als walk_forward_validatie
    start, eind = spy.index.min(), spy.index.max()
    totaal_dagen = (eind - start).days
    n_vensters = 6
    venster_lengte = totaal_dagen // (n_vensters + 1)

    print("Marktregime per venster (gemeten op het EINDE van elk venster):\n")
    print(f"{'Venster':<9}{'Einddatum':<13}{'Rend_%':>9}{'Vol_%':>8}{'>SMA50':>9}{'MaxDD':>9}{'vs200':>8}")
    print("-" * 76)
    regimes = []
    for v in range(n_vensters):
        test_eind = start + pd.Timedelta(days=venster_lengte * (v + 2) + 30)
        r = meet_marktregime(spy, tot_datum=test_eind)
        if r is None:
            continue
        regimes.append((v + 1, r))
        print(f"{v+1:<9}{str(test_eind.date()):<13}{r['rendement']:>9.1f}{r['volatiliteit']:>8.1f}"
              f"{r['pct_boven_sma50']:>9.0f}{r['max_drawdown']:>9.1f}{r['trend_sterkte']:>8.1f}")

    if len(regimes) < 6:
        print("\nNiet genoeg vensters om te vergelijken.")
        return

    goede = [r for v, r in regimes if v <= 5]
    slechte = regimes[5][1]

    print("\n" + "=" * 76)
    print("VERSCHIL: goede vensters (1-5) versus het slechte venster (6)")
    print("=" * 76)
    labels = {"rendement": "SPY-rendement (6mnd)", "volatiliteit": "Volatiliteit (jaarbasis)",
              "pct_boven_sma50": "% dagen boven SMA50", "max_drawdown": "Max drawdown",
              "trend_sterkte": "Afstand tot SMA200"}
    afwijkingen = {}
    for k, label in labels.items():
        gem_goed = float(np.mean([g[k] for g in goede]))
        spr_goed = float(np.std([g[k] for g in goede]))
        waarde_slecht = slechte[k]
        z = (waarde_slecht - gem_goed) / spr_goed if spr_goed > 0.01 else 0.0
        afwijkingen[k] = z
        merk = "  <-- sterk afwijkend" if abs(z) >= 1.5 else ""
        print(f"  {label:26s} goed: {gem_goed:>7.1f}   slecht: {waarde_slecht:>7.1f}   "
              f"(z={z:+.1f}){merk}")

    grootste = max(afwijkingen.items(), key=lambda x: abs(x[1]))
    print()
    if abs(grootste[1]) >= 1.5:
        print(f"-> Het slechte venster week het sterkst af op: {labels[grootste[0]]}.")
        print("   De marktomgeving was daar aantoonbaar anders. Dat maakt het")
        print("   waarschijnlijker dat het geen toeval was maar een regime dat")
        print("   niet bij deze strategie past.")
    else:
        print("-> Geen enkel kenmerk week sterk af. De marktomgeving van het slechte")
        print("   venster leek op die van de goede vensters. Dat wijst er eerder op")
        print("   dat het een normale verliesperiode was dan een regimewissel -")
        print("   reken dus op zulke periodes, ook als de markt er goed uitziet.")

    # waar staat de markt vandaag?
    nu = meet_marktregime(spy)
    print("\n" + "=" * 76)
    print("WAAR STAAT DE MARKT VANDAAG?")
    print("=" * 76)
    afstand_goed, afstand_slecht = 0.0, 0.0
    for k in labels:
        gem_goed = float(np.mean([g[k] for g in goede]))
        spr = float(np.std([g[k] for g in goede])) or 1.0
        afstand_goed += abs(nu[k] - gem_goed) / spr
        afstand_slecht += abs(nu[k] - slechte[k]) / spr
        print(f"  {labels[k]:26s} nu: {nu[k]:>7.1f}   (goed: {gem_goed:>6.1f}, slecht: {slechte[k]:>6.1f})")

    print()
    print(f"  Afstand tot 'goede' omgeving:   {afstand_goed:.1f}")
    print(f"  Afstand tot 'slechte' omgeving: {afstand_slecht:.1f}")
    print()
    if afstand_slecht < afstand_goed * 0.7:
        print("  -> De huidige markt lijkt MEER op de periode waarin de strategie faalde.")
        print("     Overweeg kleinere posities of even afwachten.")
    elif afstand_goed < afstand_slecht * 0.7:
        print("  -> De huidige markt lijkt MEER op de periodes waarin de strategie werkte.")
        print("     Dat is geen garantie, maar wel gunstiger dan omgekeerd.")
    else:
        print("  -> De huidige markt zit er tussenin. Geen duidelijk signaal;")
        print("     hou het bij je normale risicoregels.")

    print("\nLET OP: dit is een beschrijving van omstandigheden, geen voorspelling.")
    print("Vijf kenmerken op zes vensters is te weinig om een regel op te bouwen -")
    print("gebruik dit als context bij je eigen oordeel, niet als koop- of stopsignaal.")
    return {"nu": nu, "goede": goede, "slechte": slechte}


def simuleer_exit(future, entry, atr, initial_stop, methode, max_dagen=None):
    """Simuleert een trade met een specifieke exit-methode.
    Retourneert (rendement_pct, uitkomst, dagen_gehouden)."""
    max_dagen = max_dagen or MAX_HOLD_DAYS
    risico = entry - initial_stop
    if risico <= 0:
        return None
    stop = initial_stop
    partial_genomen = False
    partial_rend = 0.0
    fractie_open = 1.0
    hoogste = entry

    n = min(max_dagen, len(future))
    for d in range(n):
        dag = future.iloc[d]
        hoogste = max(hoogste, dag["High"])

        # 1. stop geraakt?
        if dag["Low"] <= stop:
            rest = (stop - entry) / entry * 100
            totaal = partial_rend + rest * fractie_open
            return totaal, ("stop_na_partial" if partial_genomen else "stop"), d + 1

        # 2. winstdoel bereikt? (alleen bij doel-methodes)
        if methode.get("doel_r"):
            doel = entry + methode["doel_r"] * risico
            if dag["High"] >= doel:
                rest = (doel - entry) / entry * 100
                totaal = partial_rend + rest * fractie_open
                return totaal, "doel", d + 1

        # 3. partial exit?
        if methode.get("partial_r") and not partial_genomen:
            niveau = entry + methode["partial_r"] * risico
            if dag["High"] >= niveau:
                fr = methode.get("partial_fractie", 0.5)
                partial_rend = (niveau - entry) / entry * 100 * fr
                fractie_open = 1 - fr
                partial_genomen = True
                if methode.get("breakeven_na_partial", True):
                    stop = max(stop, entry)
                # eventueel tweede doel voor de rest
                if methode.get("rest_doel_r"):
                    rest_doel = entry + methode["rest_doel_r"] * risico
                    if dag["High"] >= rest_doel:
                        rest = (rest_doel - entry) / entry * 100
                        return partial_rend + rest * fractie_open, "doel_na_partial", d + 1

        # 4. rest-doel (als partial al genomen is)
        if partial_genomen and methode.get("rest_doel_r"):
            rest_doel = entry + methode["rest_doel_r"] * risico
            if dag["High"] >= rest_doel:
                rest = (rest_doel - entry) / entry * 100
                return partial_rend + rest * fractie_open, "doel_na_partial", d + 1

        # 5. stop bijtrekken
        trail = methode.get("trail")
        if trail == "atr":
            mult = methode.get("trail_atr", 1.5)
            if not pd.isna(dag.get("ATR", np.nan)):
                stop = max(stop, dag["Close"] - mult * dag["ATR"])
        elif trail == "pct":
            pct = methode.get("trail_pct", 0.08)
            stop = max(stop, hoogste * (1 - pct))
        elif trail == "ema9":
            e = dag.get("EMA9", np.nan)
            if not pd.isna(e):
                stop = max(stop, float(e))
        elif trail == "ema21":
            e = dag.get("EMA21", np.nan)
            if not pd.isna(e):
                stop = max(stop, float(e))

    # tijdslimiet bereikt
    slot = future["Close"].iloc[n - 1]
    rest = (slot - entry) / entry * 100
    return partial_rend + rest * fractie_open, ("tijd_na_partial" if partial_genomen else "tijd"), n


EXIT_VARIANTEN = {
    "1. HUIDIG: 50%@1R + BE + ATR1.5 trail":
        {"partial_r": 1.0, "partial_fractie": 0.5, "breakeven_na_partial": True,
         "trail": "atr", "trail_atr": 1.5},
    "2. Alleen vaste stop (geen trail)":
        {},
    "3. ATR1.5 trail, geen partial":
        {"trail": "atr", "trail_atr": 1.5},
    "4. ATR3.0 trail, geen partial":
        {"trail": "atr", "trail_atr": 3.0},
    "5. Vast doel 2R":
        {"doel_r": 2.0},
    "6. Vast doel 3R":
        {"doel_r": 3.0},
    "7. 50%@1R, rest doel 2R":
        {"partial_r": 1.0, "partial_fractie": 0.5, "rest_doel_r": 2.0},
    "8. 50%@1.5R + BE + ATR3 trail":
        {"partial_r": 1.5, "partial_fractie": 0.5, "breakeven_na_partial": True,
         "trail": "atr", "trail_atr": 3.0},
    "9. Trail onder EMA9":
        {"trail": "ema9"},
    "10. Procentuele trail 8%":
        {"trail": "pct", "trail_pct": 0.08},
}


def _verzamel_basis(preset_name="balanced", min_historie=320):
    """Haalt data op en berekent indicatoren. Gedeeld door de sweeps hieronder,
    zodat het downloaden maar een keer hoeft."""
    active = list(WATCHLIST)
    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]
    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")
    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < min_historie:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue
    return voorbereid, fund_cache, spy


def _passeert_filters(row):
    """Alle harde filters van de huidige scan, op een rij."""
    if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA21", np.nan)):
        return False
    if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
        return False
    if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
        return False
    if GEBRUIK_TRENDFILTER:
        if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
            return False
        if GEBRUIK_EMA300_FILTER:
            e3 = row.get("EMA300", np.nan)
            if pd.isna(e3) or row["Close"] <= e3:
                return False
    if GEBRUIK_LEESBAARHEIDSFILTER:
        eff = row.get("EFFICIENCY", np.nan)
        if pd.isna(eff) or eff < MIN_EFFICIENCY:
            return False
    return True


def _toon_per_venster(frames, labels, titel):
    """Toont resultaten per walk-forward venster en telt wie er wint."""
    print("\n" + "-" * 84)
    print(f"PER VENSTER - {titel}")
    print("-" * 84)
    start = min(f["Datum"].min() for f in frames.values())
    eind = max(f["Datum"].max() for f in frames.values())
    lengte = (eind - start).days // 6
    # labels afkappen op 12 tekens zodat de koprij uitgelijnd blijft
    kop = "".join(f"{str(l)[:12]:>13}" for l in labels)
    print(f"{'Venster':<10}" + kop)
    print("-" * 84)
    wint = {l: 0 for l in labels}
    geldig = 0
    for v in range(6):
        vs = start + pd.Timedelta(days=lengte * v)
        ve = vs + pd.Timedelta(days=lengte)
        regel = f"{v+1:<10}"
        gems = {}
        ok = True
        for l in labels:
            sub = frames[l][(frames[l]["Datum"] >= vs) & (frames[l]["Datum"] < ve)]["Rendement"]
            if len(sub) < 8:
                ok = False
                break
            gems[l] = sub.mean()
            regel += f"{sub.mean():>13.2f}"
        if not ok:
            continue
        geldig += 1
        wint[max(gems.items(), key=lambda x: x[1])[0]] += 1
        print(regel)
    print("-" * 84)
    print("\nVensters gewonnen:")
    for l, n in sorted(wint.items(), key=lambda x: -x[1]):
        print(f"   {str(l):<14} {n}/{geldig}")
    return wint, geldig


def haal_vix(periode=None):
    """Haalt de VIX op. Retourneert None als dat niet lukt, zodat de rest
    van het script gewoon doordraait."""
    try:
        v = yf.download("^VIX", period=periode or BACKTEST_PERIOD,
                         auto_adjust=False, progress=False)["Close"]
        if isinstance(v, pd.DataFrame):
            v = v.iloc[:, 0]
        v = v.dropna()
        # yfinance geeft bij een mislukte download een LEGE Series terug in
        # plaats van een fout - zonder deze check zou het script doorgaan met
        # nul VIX-dagen en stilzwijgend verkeerde resultaten opleveren.
        if len(v) < 100:
            print(f"  VIX-data onvolledig ({len(v)} dagen, minimaal 100 nodig).")
            return None
        return v
    except Exception as e:
        print(f"  Kon VIX niet ophalen ({e}).")
        return None


def afstand_tot_rond_getal(prijs):
    """PSYCHOLOGISCHE NIVEAUS. Ronde getallen ($50, $100, $150) werken vaak als
    weerstand omdat er veel orders op liggen. Retourneert de afstand in procent
    tot het eerstvolgende ronde niveau BOVEN de koers - klein betekent dat je
    er vlak onder zit en snel op verkoopdruk kunt stuiten."""
    if prijs <= 0:
        return np.nan
    # stapgrootte schaalt mee met de prijs: onder $20 per $5, daarboven per $10,
    # boven $100 per $25. Zo blijft het niveau relevant in plaats van willekeurig.
    stap = 5 if prijs < 20 else (10 if prijs < 100 else 25)
    volgende = np.ceil(prijs / stap) * stap
    if volgende <= prijs:
        volgende += stap
    return float((volgende - prijs) / prijs * 100)


def bereken_sector_sterkte(sector_df, spy_df, lookback=63):
    """SECTOR-STERKTE. Jouw checklist zegt: bekijk de sector. Een sterk aandeel
    in een zwakke sector heeft het zwaarder dan hetzelfde aandeel in een sector
    die meeloopt. Meet het rendement van de sector-ETF t.o.v. SPY."""
    if sector_df is None or spy_df is None:
        return np.nan
    try:
        if len(sector_df) < lookback + 1 or len(spy_df) < lookback + 1:
            return np.nan
        s_rend = (sector_df.iloc[-1] / sector_df.iloc[-lookback - 1] - 1) * 100
        m_rend = (spy_df.iloc[-1] / spy_df.iloc[-lookback - 1] - 1) * 100
        return float(s_rend - m_rend)
    except Exception:
        return np.nan


def test_bevestiging_filters(preset_name="balanced"):
    """Test de resterende punten uit de checklist die nog niet gemeten zijn:

      A. RSI-bevestiging  - RSI boven 50 (momentum bevestigt de trend),
                            en apart: RSI niet boven 80 (niet uitgeput)
      B. MACD-bevestiging - MACD boven signaallijn, histogram groeit
      C. SECTOR-sterkte   - de sector van het aandeel verslaat SPY
      D. RONDE GETALLEN   - niet vlak onder een psychologisch niveau kopen

    Jouw uitgangspunt bij RSI en MACD is meegenomen: niet "RSI 70 = verkopen",
    maar RSI als bevestiging dat het momentum de trend ondersteunt.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("BEVESTIGINGSFILTERS: RSI / MACD / sector / ronde getallen")
    print("=" * 84)
    print("De resterende punten uit de checklist, elk los en gecombineerd.\n")

    preset = PRESETS[preset_name]
    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return

    # sector-ETF's ophalen voor de sectorsterkte
    print("  Sector-ETF's ophalen...")
    unieke = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in voorbereid)
                    | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unieke:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e.dropna()
        except Exception:
            etf_data[etf] = None
    print(f"  {len(voorbereid)} tickers klaar.\n")

    print("  Signalen verzamelen...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    exit_m = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    min_hist = 320

    signalen = []
    for di in range(min_hist, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {}
        for t, df in voorbereid.items():
            d = df[df.index <= dag]
            if len(d) >= min_hist and d.index[-1] == dag:
                tot_nu[t] = d
        if len(tot_nu) < 10:
            continue
        ranking = (rangschik_universum(tot_nu) if MOMENTUM_METHODE == "enkel"
                   else rangschik_universum_v2(tot_nu, MOMENTUM_METHODE))
        spy_tot = spy[spy.index <= dag]
        for ticker, deel in tot_nu.items():
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if not _passeert_filters(row):
                continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop = compute_stop(row, entry)
            uit = simuleer_exit(future, entry, row["ATR"], stop, exit_m, MAX_HOLD_DAYS)
            if uit is None:
                continue
            r, outcome, _ = uit
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100

            etf = etf_data.get(get_sector_etf(ticker))
            etf_tot = etf[etf.index <= dag] if etf is not None else None
            sector_rs = bereken_sector_sterkte(etf_tot, spy_tot)

            macd_hist = row.get("MACD_hist", np.nan)
            vorige_hist = df_full["MACD_hist"].iloc[i-1] if i > 0 else np.nan

            signalen.append({
                "Datum": dag, "Ticker": ticker, "Rendement": r,
                "RSI": float(row.get("RSI", np.nan)),
                "MACD_boven": bool(row.get("MACD", 0) > row.get("MACD_signal", 0)),
                "MACD_groeit": bool(not pd.isna(macd_hist) and not pd.isna(vorige_hist)
                                     and macd_hist > vorige_hist),
                "SectorRS": sector_rs if not np.isnan(sector_rs) else 0.0,
                "RondGetal": afstand_tot_rond_getal(entry),
            })

    if len(signalen) < 60:
        print(f"Te weinig signalen ({len(signalen)}).")
        return
    sdf = pd.DataFrame(signalen)
    print(f"  {len(sdf)} signalen.\n")

    print("=" * 84)
    print("HANGT ELK KENMERK SAMEN MET HET RENDEMENT?")
    print("=" * 84)
    for kolom, label, grenzen in [
            ("RSI", "RSI-niveau", [0, 40, 50, 60, 70, 80, 100]),
            ("SectorRS", "Sector t.o.v. SPY (%, 3mnd)", [-100, -5, 0, 5, 10, 100]),
            ("RondGetal", "Afstand tot rond getal (%)", [0, 1, 2, 5, 10, 100])]:
        sdf["_g"] = pd.cut(sdf[kolom], bins=grenzen)
        g = sdf.groupby("_g", observed=True)["Rendement"].agg(["size", "mean"]).round(2)
        g.columns = ["Trades", "Gem_%"]
        print(f"\n  {label}:")
        print("     " + g.to_string().replace("\n", "\n     "))
    for kolom, label in [("MACD_boven", "MACD boven signaallijn"),
                          ("MACD_groeit", "MACD-histogram groeit")]:
        met = sdf[sdf[kolom]]["Rendement"]
        zonder = sdf[~sdf[kolom]]["Rendement"]
        print(f"\n  {label}:")
        if len(met) > 20:
            print(f"     ja:  {met.mean():+.2f}%  ({len(met)} trades)")
        if len(zonder) > 20:
            print(f"     nee: {zonder.mean():+.2f}%  ({len(zonder)} trades)")
    sdf = sdf.drop(columns=["_g"])

    print("\n" + "=" * 84)
    print("VARIANTEN")
    print("=" * 84)
    varianten = {
        "1. Huidig (geen extra filter)": lambda d: d,
        "2. + RSI boven 50": lambda d: d[d["RSI"] >= 50],
        "3. + RSI tussen 50 en 80": lambda d: d[(d["RSI"] >= 50) & (d["RSI"] <= 80)],
        "4. + MACD boven signaal": lambda d: d[d["MACD_boven"]],
        "5. + MACD groeit": lambda d: d[d["MACD_groeit"]],
        "6. + sector verslaat SPY": lambda d: d[d["SectorRS"] > 0],
        "7. + minstens 2% tot rond getal": lambda d: d[d["RondGetal"] >= 2],
        "8. RSI 50-80 + MACD boven": lambda d: d[
            (d["RSI"] >= 50) & (d["RSI"] <= 80) & d["MACD_boven"]],
        "9. Alles samen": lambda d: d[
            (d["RSI"] >= 50) & (d["RSI"] <= 80) & d["MACD_boven"]
            & (d["SectorRS"] > 0) & (d["RondGetal"] >= 2)],
    }
    print(f"{'Variant':<38}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    frames = {}
    for naam, fn in varianten.items():
        deel = fn(sdf.copy())
        if len(deel) < 30:
            print(f"{naam:<38}{len(deel):>9}   te weinig")
            continue
        arr = deel["Rendement"].values
        frames[naam] = deel
        print(f"{naam:<38}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")

    if len(frames) >= 2:
        wint, geldig = _toon_per_venster(frames, list(frames.keys()), "bevestigingsfilters")
        basis = frames.get("1. Huidig (geen extra filter)")
        beste = max(frames.items(), key=lambda x: x[1]["Rendement"].mean())
        print(f"\nHoogste gemiddelde: {beste[0]} ({beste[1]['Rendement'].mean():+.3f}%)")
        if basis is not None:
            v = beste[1]["Rendement"].mean() - basis["Rendement"].mean()
            behoud = len(beste[1]) / len(basis) * 100
            print(f"Huidig: {basis['Rendement'].mean():+.3f}%  -> verschil {v:+.3f}pp")
            print(f"Je houdt {behoud:.0f}% van je trades over.")
            print()
            if beste[0] == "1. Huidig (geen extra filter)":
                print("-> Geen enkel bevestigingsfilter verbetert het resultaat.")
            elif v > 0.15 and wint.get(beste[0], 0) >= geldig * 0.5:
                print(f"-> {beste[0]} is BETER en consistent. Aan te raden.")
            elif v > 0.15:
                print("-> Hoger gemiddelde, maar niet consistent per venster. Zwak bewijs.")
            else:
                print("-> Verschil te klein om te vertrouwen.")
    return frames


def bereken_rr(df, row, stop):
    """RISK/REWARD op basis van de eerstvolgende weerstand als target.

    Jouw checklist stelt: zoek het volgende belangrijke weerstandsniveau en
    reken daarmee je R:R uit, in plaats van een willekeurig percentage te
    nemen. Minimaal ongeveer 1:2 als de setup dat toelaat.

    Retourneert (rr, target, haalbaar_in_dagen). 'haalbaar' beantwoordt de
    vraag uit punt 7 van je lijst: kan dit aandeel dat target uberhaupt
    binnen de houdperiode bereiken gegeven zijn dagelijkse beweging (ATR)?
    """
    entry = row["Close"]
    risico = entry - stop
    if risico <= 0:
        return np.nan, np.nan, np.nan

    ruimte = compute_overhead_resistance(df)
    if pd.isna(ruimte):
        # geen weerstand boven = vrije baan; neem 3x ATR als redelijk target
        target = entry + 3 * row["ATR"]
    else:
        target = entry * (1 + ruimte)

    rr = (target - entry) / risico
    # hoeveel dagen heeft het aandeel nodig bij zijn gemiddelde dagbeweging?
    atr = row["ATR"]
    dagen_nodig = (target - entry) / atr if atr > 0 else np.inf
    return float(rr), float(target), float(dagen_nodig)


def test_checklist_filters(preset_name="balanced"):
    """Test drie concepten uit de checklist die nog niet in de ranking-scan zaten:

      A. MARKTSTRUCTUUR - alleen aandelen met hogere toppen EN hogere bodems
      B. RUIMTE TOT WEERSTAND - minimaal x% ruimte voordat de eerstvolgende
         weerstand wordt geraakt
      C. RISK/REWARD - minimaal 1:2 tot de eerstvolgende weerstand
      D. HAALBAARHEID - kan het target binnen de houdperiode gehaald worden
         gegeven de dagelijkse beweging (ATR)?

    Elk wordt los en gecombineerd gemeten tegen de huidige opzet.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("CHECKLIST-FILTERS: marktstructuur / weerstand / R:R / haalbaarheid")
    print("=" * 84)
    print("Vier concepten die nog niet in de ranking-scan zaten.\n")

    preset = PRESETS[preset_name]
    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return
    print(f"  {len(voorbereid)} tickers klaar.\n")

    print("  Signalen verzamelen met alle kenmerken...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    exit_m = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    min_hist = 320

    signalen = []
    for di in range(min_hist, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {}
        for t, df in voorbereid.items():
            d = df[df.index <= dag]
            if len(d) >= min_hist and d.index[-1] == dag:
                tot_nu[t] = d
        if len(tot_nu) < 10:
            continue
        ranking = (rangschik_universum(tot_nu) if MOMENTUM_METHODE == "enkel"
                   else rangschik_universum_v2(tot_nu, MOMENTUM_METHODE))
        for ticker, deel in tot_nu.items():
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if not _passeert_filters(row):
                continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop = compute_stop(row, entry)
            uit = simuleer_exit(future, entry, row["ATR"], stop, exit_m, MAX_HOLD_DAYS)
            if uit is None:
                continue
            r, outcome, _ = uit
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100

            rr, target, dagen_nodig = bereken_rr(deel, row, stop)
            ruimte = compute_overhead_resistance(deel)
            signalen.append({
                "Datum": dag, "Ticker": ticker, "Rendement": r,
                "Structuur": bool(row.get("MARKET_STRUCTURE_UP", False)),
                "Ruimte": (100.0 if pd.isna(ruimte) else ruimte * 100),
                "RR": rr if not np.isnan(rr) else 0.0,
                "DagenNodig": dagen_nodig if not np.isnan(dagen_nodig) else 99,
            })

    if len(signalen) < 60:
        print(f"Te weinig signalen ({len(signalen)}).")
        return
    sdf = pd.DataFrame(signalen)
    print(f"  {len(sdf)} signalen.\n")

    # eerst: hangt elk kenmerk samen met het rendement?
    print("=" * 84)
    print("HANGT ELK KENMERK SAMEN MET HET RENDEMENT?")
    print("=" * 84)
    print(f"  Marktstructuur bullish: {sdf['Structuur'].mean()*100:.0f}% van de signalen")
    met = sdf[sdf["Structuur"]]["Rendement"]
    zonder = sdf[~sdf["Structuur"]]["Rendement"]
    if len(met) > 20 and len(zonder) > 20:
        print(f"     met HH/HL:  {met.mean():+.2f}%  ({len(met)} trades)")
        print(f"     zonder:     {zonder.mean():+.2f}%  ({len(zonder)} trades)")
    for kolom, label, grenzen in [
            ("Ruimte", "Ruimte tot weerstand (%)", [0, 3, 6, 10, 20, 1000]),
            ("RR", "Risk/reward", [0, 1, 2, 3, 5, 100]),
            ("DagenNodig", "Dagen nodig voor target", [0, 2, 3, 5, 8, 1000])]:
        sdf["_g"] = pd.cut(sdf[kolom], bins=grenzen)
        g = sdf.groupby("_g", observed=True)["Rendement"].agg(["size", "mean"]).round(2)
        g.columns = ["Trades", "Gem_%"]
        print(f"\n  {label}:")
        print("     " + g.to_string().replace("\n", "\n     "))
    sdf = sdf.drop(columns=["_g"])

    # varianten
    print("\n" + "=" * 84)
    print("VARIANTEN")
    print("=" * 84)
    varianten = {
        "1. Huidig (geen extra filter)": lambda d: d,
        "2. + marktstructuur HH/HL": lambda d: d[d["Structuur"]],
        "3. + minimaal 5% ruimte": lambda d: d[d["Ruimte"] >= 5],
        "4. + minimaal 8% ruimte": lambda d: d[d["Ruimte"] >= 8],
        "5. + R:R minimaal 2": lambda d: d[d["RR"] >= 2],
        "6. + R:R minimaal 3": lambda d: d[d["RR"] >= 3],
        "7. + target haalbaar (<=5 ATR-dagen)": lambda d: d[d["DagenNodig"] <= 5],
        "8. structuur + R:R>=2": lambda d: d[d["Structuur"] & (d["RR"] >= 2)],
        "9. structuur + R:R>=2 + haalbaar": lambda d: d[
            d["Structuur"] & (d["RR"] >= 2) & (d["DagenNodig"] <= 5)],
    }
    print(f"{'Variant':<40}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    frames = {}
    for naam, fn in varianten.items():
        deel = fn(sdf.copy())
        if len(deel) < 30:
            print(f"{naam:<40}{len(deel):>9}   te weinig")
            continue
        arr = deel["Rendement"].values
        frames[naam] = deel
        print(f"{naam:<40}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")

    if len(frames) >= 2:
        wint, geldig = _toon_per_venster(frames, list(frames.keys()), "checklist-filters")
        basis = frames.get("1. Huidig (geen extra filter)")
        beste = max(frames.items(), key=lambda x: x[1]["Rendement"].mean())
        print(f"\nHoogste gemiddelde: {beste[0]} ({beste[1]['Rendement'].mean():+.3f}%)")
        if basis is not None:
            v = beste[1]["Rendement"].mean() - basis["Rendement"].mean()
            print(f"Huidig: {basis['Rendement'].mean():+.3f}%  -> verschil {v:+.3f}pp")
            behoud = len(beste[1]) / len(basis) * 100
            print(f"Je houdt {behoud:.0f}% van je trades over ({len(beste[1])} van {len(basis)}).")
            print()
            if beste[0] == "1. Huidig (geen extra filter)":
                print("-> Geen enkel checklist-filter verbetert het resultaat. Niets aanpassen.")
            elif v > 0.15 and wint.get(beste[0], 0) >= geldig * 0.5:
                print(f"-> {beste[0]} is BETER en consistent. Aan te raden.")
            elif v > 0.15:
                print("-> Hoger gemiddelde, maar niet consistent per venster. Zwak bewijs.")
            else:
                print("-> Verschil te klein om te vertrouwen.")
    return frames


def test_momentum_methode(preset_name="balanced"):
    """Vergelijkt de ENKELVOUDIGE momentum-score met SAMENGESTELDE varianten.

    Aanleiding: de huidige ranking kijkt alleen naar 126 dagen. Twee aandelen
    met hetzelfde rendement over die periode kunnen totaal anders zijn
    opgebouwd - gestage klim versus een eenmalige sprong. Een samengestelde
    score over meerdere horizonnen ziet dat verschil wel.

    Getest wordt of dat onderscheid ook tot betere trades leidt. Alle overige
    filters en de exit blijven gelijk; alleen de rangschikking verschilt.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("MOMENTUM-METHODE: ruw versus RISICO-GECORRIGEERD")
    print("=" * 84)
    print("Zelfde filters, zelfde exit. Alleen de momentum-berekening verschilt.")
    print()
    print("Risico-gecorrigeerd = momentum gedeeld door de gerealiseerde volatiliteit")
    print("over dezelfde periode. Onderbouwing: Barroso & Santa-Clara (2015) vonden")
    print("dat dit momentum-crashes vrijwel elimineert en de Sharpe-ratio bijna")
    print("verdubbelt; Daniel & Moskowitz (2016) en anderen bevestigen dat.\n")

    preset = PRESETS[preset_name]
    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return
    print(f"  {len(voorbereid)} tickers klaar.\n")

    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    exit_m = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    # v3-varianten zijn risico-gecorrigeerd (momentum / volatiliteit)
    methodes = {"multi ruw (huidig)": ("v2", "multi"),
                "multi risico-gecorr": ("v3", "multi"),
                "enkel risico-gecorr": ("v3", "enkel"),
                "enkel ruw (oud)": ("v2", "enkel")}

    print("  Signalen verzamelen voor elke methode...")
    resultaten = {}
    for label, (variant, methode) in methodes.items():
        rends = []
        for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS):
            dag = alle_dagen[di]
            tot_nu = {}
            for t, df in voorbereid.items():
                d = df[df.index <= dag]
                # 252-daagse horizon vraagt meer historie dan de enkelvoudige
                if len(d) >= 260 and d.index[-1] == dag:
                    tot_nu[t] = d
            if len(tot_nu) < 10:
                continue
            if variant == "v3":
                ranking = rangschik_universum_v3(tot_nu, methode)
            elif methode == "enkel":
                ranking = rangschik_universum(tot_nu)
            else:
                ranking = rangschik_universum_v2(tot_nu, methode)
            for ticker in tot_nu:
                info = ranking.get(ticker)
                if not info or info["percentiel"] < drempel:
                    continue
                df_full = voorbereid[ticker]
                i = df_full.index.get_loc(dag)
                row = df_full.iloc[i]
                if not _passeert_filters(row):
                    continue
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                stop0 = compute_stop(row, entry)
                uit = simuleer_exit(future, entry, row["ATR"], stop0, exit_m, MAX_HOLD_DAYS)
                if uit is None:
                    continue
                r, outcome, _ = uit
                fund = fund_cache.get(ticker, {})
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append({"Datum": dag, "Ticker": ticker, "Rendement": r})
        if len(rends) >= 30:
            resultaten[label] = pd.DataFrame(rends)
            print(f"    {label}: {len(rends)} signalen")

    if len(resultaten) < 2:
        print("Te weinig resultaten om te vergelijken.")
        return

    print("\n" + "=" * 84)
    print("RESULTAAT")
    print("=" * 84)
    print(f"{'Methode':<32}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    for label, rd in resultaten.items():
        arr = rd["Rendement"].values
        print(f"{label:<32}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")

    wint, geldig = _toon_per_venster(resultaten, list(resultaten.keys()), "momentum-methode")

    beste = max(resultaten.items(), key=lambda x: x[1]["Rendement"].mean())
    huidig = resultaten.get("multi ruw (huidig)")
    print(f"\nHoogste gemiddelde: {beste[0]} ({beste[1]['Rendement'].mean():+.3f}%)")
    if huidig is not None:
        v = beste[1]["Rendement"].mean() - huidig["Rendement"].mean()
        print(f"Huidige methode: {huidig['Rendement'].mean():+.3f}%  -> verschil {v:+.3f}pp")
        print()
        if beste[0] == "multi ruw (huidig)":
            print("-> De huidige enkelvoudige score is de beste. Niets aanpassen.")
        elif v > 0.15 and wint.get(beste[0], 0) >= geldig * 0.5:
            print(f"-> {beste[0]} is BETER en wint in de meeste vensters.")
            print("   Aan te raden om over te stappen.")
        elif v > 0.15:
            print(f"-> {beste[0]} heeft een hoger gemiddelde, maar wint niet consistent.")
            print("   Zwak bewijs - voorzichtig mee zijn.")
        else:
            print("-> Verschil te klein om te vertrouwen. Huidige methode houden.")

    # overlap: kiezen de methodes dezelfde aandelen?
    if len(resultaten) >= 2:
        labels = list(resultaten.keys())
        a, b = resultaten[labels[0]], resultaten[labels[1]]
        set_a = set(zip(a["Datum"], a["Ticker"]))
        set_b = set(zip(b["Datum"], b["Ticker"]))
        overlap = len(set_a & set_b) / max(len(set_a | set_b), 1) * 100
        print(f"\nOverlap tussen '{labels[0]}' en '{labels[1]}': {overlap:.0f}% van de trades.")
        if overlap > 85:
            print("Zeer hoge overlap - de methodes selecteren vrijwel dezelfde aandelen,")
            print("dus een groot verschil in resultaat is onwaarschijnlijk.")
    return resultaten


def test_vix_regime(preset_name="balanced"):
    """TEST OF EEN VIX-REGIMEFILTER DE ZWAKKE PERIODES WEGNEEMT.

    Aanleiding: de walk-forward liet zien dat venster 2 en 6 negatief waren.
    De gangbare institutionele praktijk is een VIX-regimetabel: onder een
    rustige drempel normaal risico, daartussen half risico, en boven de
    bovenste drempel alleen A-setups of helemaal niet handelen.

    Dat is nooit op jouw data gemeten. Deze test doet dat, met zowel absolute
    drempels (VIX > 20, 25, 30) als een relatieve maat (VIX boven zijn eigen
    percentiel), plus een variant die de POSITIE HALVEERT in plaats van
    helemaal niet te handelen.

    Belangrijk: er wordt alleen gekeken naar de VIX-stand op de SIGNAALDAG.
    Geen informatie uit de toekomst.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("VIX-REGIME TEST")
    print("=" * 84)
    print("Helpt het om niet (of kleiner) te handelen bij hoge volatiliteit?\n")

    preset = PRESETS[preset_name]
    print("  VIX ophalen...")
    vix = haal_vix()
    if vix is None or len(vix) < 100:
        print("Geen VIX-data beschikbaar.")
        return
    print(f"  VIX-data: {len(vix)} dagen, bereik {vix.min():.1f} - {vix.max():.1f}, "
          f"mediaan {vix.median():.1f}\n")

    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return
    print(f"  {len(voorbereid)} tickers klaar.\n")

    print("  Signalen verzamelen...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    exit_m = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    signalen = []
    for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {}
        for t, df in voorbereid.items():
            d = df[df.index <= dag]
            if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag:
                tot_nu[t] = d
        if len(tot_nu) < 10:
            continue
        # VIX-stand op deze dag (alleen data tot en met vandaag)
        vix_tot = vix[vix.index <= dag]
        if len(vix_tot) < 60:
            continue
        vix_nu = float(vix_tot.iloc[-1])
        vix_pct = float((vix_tot.iloc[-1] > vix_tot.iloc[-252:]).mean() * 100) \
            if len(vix_tot) >= 60 else 50.0

        ranking = rangschik_universum(tot_nu)
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if not _passeert_filters(row):
                continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop0 = compute_stop(row, entry)
            uit = simuleer_exit(future, entry, row["ATR"], stop0, exit_m, MAX_HOLD_DAYS)
            if uit is None:
                continue
            r, outcome, _ = uit
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100
            signalen.append({"Datum": dag, "VIX": vix_nu, "VIX_pct": vix_pct,
                              "Rang": info["percentiel"], "Rendement": r})

    if len(signalen) < 50:
        print(f"Te weinig signalen ({len(signalen)}).")
        return
    sdf = pd.DataFrame(signalen)
    print(f"  {len(sdf)} signalen.\n")

    # eerst: hoe verhoudt het rendement zich tot de VIX-stand?
    print("=" * 84)
    print("RENDEMENT PER VIX-NIVEAU")
    print("=" * 84)
    sdf["VIX_groep"] = pd.cut(sdf["VIX"], bins=[0, 13, 14, 15, 16, 18, 20, 25, 100],
                               labels=["<13", "13-14", "14-15", "15-16",
                                       "16-18", "18-20", "20-25", ">25"])
    g = sdf.groupby("VIX_groep", observed=True).agg(
        Trades=("Rendement", "size"),
        Gem_pct=("Rendement", "mean"),
        Win_pct=("Rendement", lambda x: (x > 0).mean() * 100),
        Mediaan=("Rendement", "median")).round(2)
    print(g.to_string())

    corr = sdf["VIX"].corr(sdf["Rendement"])
    print(f"\nCorrelatie VIX <-> rendement: {corr:+.3f}")
    if corr < -0.05:
        print("Negatief: hogere VIX hangt samen met slechter rendement.")
    elif corr > 0.05:
        print("Positief: hogere VIX hangt samen met BETER rendement (onverwacht).")
    else:
        print("Vrijwel nul: de VIX-stand voorspelt het rendement niet.")

    # varianten testen
    print("\n" + "=" * 84)
    print("VARIANTEN")
    print("=" * 84)
    # LET OP: de eerste testronde bevatte alleen BOVENgrenzen. De tabel
    # "rendement per VIX-niveau" liet echter zien dat de ZWAKSTE resultaten
    # juist bij de LAAGSTE volatiliteit zaten (VIX < 15), niet bij de hoogste.
    # Vandaar dat hier ook ondergrenzen en banden worden getest - een omissie
    # in de oorspronkelijke opzet.
    varianten = {
        "1. Geen VIX-filter (huidig)": lambda d: d.assign(W=1.0),
        "2. Niet handelen bij VIX>25": lambda d: d[d["VIX"] <= 25].assign(W=1.0),
        "3. Niet handelen bij VIX<13": lambda d: d[d["VIX"] >= 13].assign(W=1.0),
        "4. Niet handelen bij VIX<15": lambda d: d[d["VIX"] >= 15].assign(W=1.0),
        "5. Niet handelen bij VIX<16": lambda d: d[d["VIX"] >= 16].assign(W=1.0),
        "6. Alleen band VIX 15-25": lambda d: d[(d["VIX"] >= 15) & (d["VIX"] <= 25)].assign(W=1.0),
        "7. Alleen band VIX 14-22": lambda d: d[(d["VIX"] >= 14) & (d["VIX"] <= 22)].assign(W=1.0),
        "8. Halve positie bij VIX<15": lambda d: d.assign(
            W=np.where(d["VIX"] < 15, 0.5, 1.0)),
        "9. Niet handelen bij VIX in laagste 20% (relatief)": lambda d: d[d["VIX_pct"] >= 20].assign(W=1.0),
    }
    print(f"{'Variant':<48}{'Trades':>8}{'Gewogen_%':>12}{'Win_%':>9}")
    print("-" * 84)
    frames = {}
    for naam, fn in varianten.items():
        deel = fn(sdf.copy())
        if len(deel) < 30:
            continue
        # gewogen rendement: een halve positie levert het halve rendement op
        gewogen = (deel["Rendement"] * deel["W"]).values
        frames[naam] = deel.assign(Gewogen=gewogen)
        print(f"{naam:<48}{len(deel):>8}{gewogen.mean():>12.3f}"
              f"{(gewogen > 0).mean()*100:>9.1f}")

    # per venster
    if len(frames) >= 2:
        print("\n" + "-" * 84)
        print("PER VENSTER (gewogen rendement)")
        print("-" * 84)
        start, eind = sdf["Datum"].min(), sdf["Datum"].max()
        lengte = (eind - start).days // 6
        namen = list(frames.keys())
        print(f"{'Venster':<10}" + "".join(f"{n.split('.')[0]:>10}" for n in namen))
        wint = {n: 0 for n in namen}
        geldig = 0
        for v in range(6):
            vs = start + pd.Timedelta(days=lengte*v)
            ve = vs + pd.Timedelta(days=lengte)
            regel = f"{v+1:<10}"
            gems = {}
            ok = True
            for n in namen:
                d = frames[n]
                sub = d[(d["Datum"] >= vs) & (d["Datum"] < ve)]["Gewogen"]
                if len(sub) < 5:
                    ok = False
                    break
                gems[n] = sub.mean()
                regel += f"{sub.mean():>10.2f}"
            if not ok:
                continue
            geldig += 1
            wint[max(gems.items(), key=lambda x: x[1])[0]] += 1
            print(regel)
        print("-" * 84)
        print("\nVensters gewonnen:")
        for n, k in sorted(wint.items(), key=lambda x: -x[1]):
            print(f"   {n:<50} {k}/{geldig}")

        basis = frames.get("1. Geen VIX-filter (huidig)")
        beste = max(frames.items(), key=lambda x: x[1]["Gewogen"].mean())
        print(f"\nHoogste gewogen rendement: {beste[0]} ({beste[1]['Gewogen'].mean():+.3f}%)")
        if basis is not None:
            v = beste[1]["Gewogen"].mean() - basis["Gewogen"].mean()
            print(f"Huidig (geen filter): {basis['Gewogen'].mean():+.3f}%  -> verschil {v:+.3f}pp")
            if v > 0.1 and wint.get(beste[0], 0) >= geldig * 0.5:
                print("\n-> Dit VIX-filter is BETER en consistent. Aan te raden.")
            elif v > 0.1:
                print("\n-> Hoger gemiddelde, maar niet consistent per venster. Zwak bewijs.")
            else:
                print("\n-> Geen verbetering. De VIX-stand helpt niet bij deze strategie.")
    return frames


def sweep_alles(preset_name="balanced"):
    """DRIE SWEEPS IN EEN RUN: houdperiode, stopbreedte en momentum-meetperiode.

    Alle drie draaien op dezelfde data en met dezelfde filters, zodat je in een
    keer ziet welke van de drie het meeste oplevert - en of ze elkaar niet
    tegenwerken. Elke sweep wordt per walk-forward venster beoordeeld, zodat
    een toevallige uitschieter niet als verbetering wordt aangezien.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("DRIEVOUDIGE SWEEP: houdperiode / stopbreedte / momentum-periode")
    print("=" * 84)
    print(f"Huidige instellingen: hold={MAX_HOLD_DAYS}d, stop={STOP_ATR_MULT}x ATR, "
          f"momentum={MOMENTUM_LOOKBACK}d\n")

    preset = PRESETS[preset_name]
    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return
    print(f"  {len(voorbereid)} tickers klaar.\n")

    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    huidige_exit = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]

    def bepaal_entries(lookback):
        """Entry-signalen bij een bepaalde momentum-meetperiode."""
        entries = []
        for di in range(320, len(alle_dagen) - 12):
            dag = alle_dagen[di]
            tot_nu = {}
            for t, df in voorbereid.items():
                d = df[df.index <= dag]
                if len(d) >= lookback + MOMENTUM_SKIP + 1 and d.index[-1] == dag:
                    tot_nu[t] = d
            if len(tot_nu) < 10:
                continue
            ranking = rangschik_universum(tot_nu, lookback=lookback)
            for ticker, deel in tot_nu.items():
                info = ranking.get(ticker)
                if not info or info["percentiel"] < drempel:
                    continue
                df_full = voorbereid[ticker]
                i = df_full.index.get_loc(dag)
                if not _passeert_filters(df_full.iloc[i]):
                    continue
                entries.append((ticker, dag, i))
        return entries

    def meet(entries, hold, stop_mult):
        """Rendement per trade bij een gegeven houdperiode en stopbreedte."""
        rends = []
        origineel = globals()["STOP_ATR_MULT"]
        globals()["STOP_ATR_MULT"] = stop_mult
        try:
            for ticker, dag, i in entries:
                df_full = voorbereid[ticker]
                if i + 1 + hold > len(df_full):
                    continue
                row = df_full.iloc[i]
                entry = row["Close"]
                stop0 = compute_stop(row, entry)
                future = df_full.iloc[i+1:i+1+hold]
                if len(future) == 0:
                    continue
                exit_m = dict(huidige_exit)
                exit_m["trail_atr"] = stop_mult
                uit = simuleer_exit(future, entry, row["ATR"], stop0, exit_m, hold)
                if uit is None:
                    continue
                r, outcome, _ = uit
                fund = fund_cache.get(ticker, {})
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append({"Datum": dag, "Rendement": r})
        finally:
            globals()["STOP_ATR_MULT"] = origineel
        return pd.DataFrame(rends) if len(rends) >= 30 else None

    # ---------- SWEEP 1: houdperiode ----------
    print("=" * 84)
    print("SWEEP 1 - HOUDPERIODE")
    print("=" * 84)
    print("  Entry-signalen bepalen...")
    basis_entries = bepaal_entries(MOMENTUM_LOOKBACK)
    print(f"  {len(basis_entries)} signalen.\n")
    print(f"{'Dagen':<10}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    frames1 = {}
    for hold in (3, 4, 5, 6, 7, 8, 10, 12):
        rd = meet(basis_entries, hold, STOP_ATR_MULT)
        if rd is None:
            continue
        arr = rd["Rendement"].values
        frames1[hold] = rd
        print(f"{hold:<10}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")
    if len(frames1) >= 2:
        wint1, geldig1 = _toon_per_venster(frames1, list(frames1.keys()), "houdperiode")
        beste1 = max(frames1.items(), key=lambda x: x[1]["Rendement"].mean())
        huidig1 = frames1.get(MAX_HOLD_DAYS)
        print(f"\nHoogste gemiddelde: {beste1[0]} dagen ({beste1[1]['Rendement'].mean():+.3f}%)")
        if huidig1 is not None:
            print(f"Huidige instelling: {MAX_HOLD_DAYS} dagen ({huidig1['Rendement'].mean():+.3f}%)")

    # ---------- SWEEP 2: stopbreedte ----------
    print("\n" + "=" * 84)
    print("SWEEP 2 - STOPBREEDTE (x ATR)")
    print("=" * 84)
    print(f"{'Stop':<10}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    frames2 = {}
    for mult in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        rd = meet(basis_entries, MAX_HOLD_DAYS, mult)
        if rd is None:
            continue
        arr = rd["Rendement"].values
        frames2[mult] = rd
        print(f"{mult:<10}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")
    if len(frames2) >= 2:
        wint2, geldig2 = _toon_per_venster(frames2, list(frames2.keys()), "stopbreedte")
        beste2 = max(frames2.items(), key=lambda x: x[1]["Rendement"].mean())
        huidig2 = frames2.get(STOP_ATR_MULT)
        print(f"\nHoogste gemiddelde: {beste2[0]}x ATR ({beste2[1]['Rendement'].mean():+.3f}%)")
        if huidig2 is not None:
            print(f"Huidige instelling: {STOP_ATR_MULT}x ATR ({huidig2['Rendement'].mean():+.3f}%)")

    # ---------- SWEEP 3: momentum-meetperiode ----------
    print("\n" + "=" * 84)
    print("SWEEP 3 - MOMENTUM-MEETPERIODE")
    print("=" * 84)
    print("Let op: dit verandert WELKE aandelen worden geselecteerd, niet alleen")
    print("hoe ze worden afgehandeld. Elke variant vraagt een nieuwe ranking.\n")
    print(f"{'Dagen':<10}{'~Maanden':<11}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    frames3 = {}
    for lb in (63, 126, 189, 252):
        ent = bepaal_entries(lb)
        if len(ent) < 30:
            print(f"{lb:<10}{lb/21:<11.0f}   te weinig signalen")
            continue
        rd = meet(ent, MAX_HOLD_DAYS, STOP_ATR_MULT)
        if rd is None:
            continue
        arr = rd["Rendement"].values
        frames3[lb] = rd
        print(f"{lb:<10}{lb/21:<11.0f}{len(arr):>9}{arr.mean():>10.3f}"
              f"{(arr>0).mean()*100:>9.1f}{np.median(arr):>10.2f}")
    if len(frames3) >= 2:
        wint3, geldig3 = _toon_per_venster(frames3, list(frames3.keys()), "momentum-periode")
        beste3 = max(frames3.items(), key=lambda x: x[1]["Rendement"].mean())
        huidig3 = frames3.get(MOMENTUM_LOOKBACK)
        print(f"\nHoogste gemiddelde: {beste3[0]} dagen ({beste3[1]['Rendement'].mean():+.3f}%)")
        if huidig3 is not None:
            print(f"Huidige instelling: {MOMENTUM_LOOKBACK} dagen ({huidig3['Rendement'].mean():+.3f}%)")

    print("\n" + "=" * 84)
    print("HOE TE LEZEN")
    print("=" * 84)
    print("Kijk NIET alleen naar het hoogste gemiddelde. Een instelling die maar in")
    print("1 van 6 vensters wint, is waarschijnlijk toeval. Zoek naar een BREED")
    print("gebied van goede waarden: als 6, 7 en 8 dagen allemaal beter zijn dan 5,")
    print("is dat betrouwbaarder dan een losse piek bij 7.")
    print()
    print("En let op de mediaan: een hoog gemiddelde met een negatieve mediaan")
    print("betekent dat je doorsnee trade verliest en je op uitschieters wacht.")
    return frames1, frames2, frames3


def test_eendags(preset_name="balanced"):
    """EENDAGS-STRATEGIE: kopen bij open, verkopen bij close, dezelfde dag.

    BELANGRIJKE BEPERKING: Yahoo Finance levert geen pre-market data. Deze test
    simuleert kopen tegen de OPENINGSKOERS, niet tegen een pre-market prijs.
    Als je in pre-market koopt tegen een afwijkende prijs, wijkt je werkelijke
    resultaat af van deze cijfers - en juist bij nieuwsgedreven aandelen (die
    zo'n strategie vaak selecteert) kan dat gat groot zijn.

    Getest worden drie varianten:
      A) open -> close, geen stop (volledige dagbeweging)
      B) open -> close, met stop-loss tijdens de dag
      C) ter vergelijking: de huidige meerdaagse strategie

    Ook meegenomen: de overnight-gap. Bij een meerdaagse strategie koop je op
    de CLOSE van de signaaldag; bij een eendagsstrategie koop je op de OPEN van
    de volgende dag. Het verschil daartussen is de gap - en die kan een groot
    deel van de beweging bevatten.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 80)
    print("EENDAGS-STRATEGIE TEST (open -> close)")
    print("=" * 80)
    print("LET OP: gesimuleerd vanaf de OPENINGSKOERS, niet pre-market.")
    print("Yahoo levert geen pre-market data - je werkelijke instap kan afwijken.\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 320:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return

    print("  Entry-signalen bepalen...")
    entries = []
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS - 1):
        dag = alle_dagen[di]
        tot_nu = {t: df[df.index <= dag] for t, df in voorbereid.items()}
        tot_nu = {t: d for t, d in tot_nu.items()
                  if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag}
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA21", np.nan)):
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue
            if GEBRUIK_TRENDFILTER:
                if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
                    continue
                if GEBRUIK_EMA300_FILTER:
                    e3 = row.get("EMA300", np.nan)
                    if pd.isna(e3) or row["Close"] <= e3:
                        continue
            if GEBRUIK_LEESBAARHEIDSFILTER:
                eff = row.get("EFFICIENCY", np.nan)
                if pd.isna(eff) or eff < MIN_EFFICIENCY:
                    continue
            entries.append((ticker, dag, i))

    if len(entries) < 50:
        print(f"Te weinig entries ({len(entries)}).")
        return
    print(f"  {len(entries)} entry-signalen.\n")

    resultaten = {"A. Eendags open->close (geen stop)": [],
                  "B. Eendags open->close (met stop)": [],
                  "C. Meerdaags (huidige methode)": [],
                  "gap": []}

    for ticker, dag, i in entries:
        df_full = voorbereid[ticker]
        if i + 1 + MAX_HOLD_DAYS > len(df_full):
            continue
        row = df_full.iloc[i]
        signaal_close = row["Close"]
        volgende = df_full.iloc[i + 1]
        open_prijs = volgende["Open"]
        if pd.isna(open_prijs) or open_prijs <= 0:
            continue

        fund = fund_cache.get(ticker, {})
        av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
        slip = get_dynamic_slippage((av or 0) * signaal_close)
        kosten = COMMISSION_PCT * 2 * 100

        # overnight gap: van de close van de signaaldag naar de open erna
        gap = (open_prijs - signaal_close) / signaal_close * 100
        resultaten["gap"].append({"Datum": dag, "Rendement": gap})

        # A) open -> close, geen stop
        rend_a = (volgende["Close"] - open_prijs) / open_prijs * 100 - kosten
        resultaten["A. Eendags open->close (geen stop)"].append(
            {"Datum": dag, "Rendement": rend_a})

        # B) open -> close, met stop tijdens de dag
        stop_b = open_prijs - STOP_ATR_MULT * row["ATR"]
        if volgende["Low"] <= stop_b:
            rend_b = (stop_b - open_prijs) / open_prijs * 100 - slip * 100 - kosten
        else:
            rend_b = (volgende["Close"] - open_prijs) / open_prijs * 100 - kosten
        resultaten["B. Eendags open->close (met stop)"].append(
            {"Datum": dag, "Rendement": rend_b})

        # C) huidige meerdaagse methode (koopt op de close van de signaaldag)
        stop0 = compute_stop(row, signaal_close)
        future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
        uit = simuleer_exit(future, signaal_close, row["ATR"], stop0,
                            EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"],
                            MAX_HOLD_DAYS)
        if uit:
            r, outcome, _ = uit
            if "stop" in outcome:
                r -= slip * 100
            r -= kosten
            resultaten["C. Meerdaags (huidige methode)"].append(
                {"Datum": dag, "Rendement": r})

    print("=" * 80)
    print("RESULTAAT")
    print("=" * 80)
    print(f"{'Strategie':<40}{'Trades':>8}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 80)
    frames = {}
    for naam in ["A. Eendags open->close (geen stop)", "B. Eendags open->close (met stop)",
                 "C. Meerdaags (huidige methode)"]:
        lijst = resultaten[naam]
        if len(lijst) < 30:
            continue
        rd = pd.DataFrame(lijst)
        arr = rd["Rendement"].values
        frames[naam] = rd
        print(f"{naam:<40}{len(arr):>8}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")

    gapd = pd.DataFrame(resultaten["gap"])
    print("-" * 80)
    print(f"{'Overnight gap (close -> volgende open)':<40}{len(gapd):>8}"
          f"{gapd['Rendement'].mean():>10.3f}{(gapd['Rendement']>0).mean()*100:>9.1f}"
          f"{gapd['Rendement'].median():>10.2f}")

    print("\n" + "=" * 80)
    print("WAT DIT BETEKENT")
    print("=" * 80)
    gap_gem = gapd["Rendement"].mean()
    if "A. Eendags open->close (geen stop)" in frames and "C. Meerdaags (huidige methode)" in frames:
        a = frames["A. Eendags open->close (geen stop)"]["Rendement"].mean()
        c = frames["C. Meerdaags (huidige methode)"]["Rendement"].mean()
        print(f"\nDe overnight gap is gemiddeld {gap_gem:+.3f}% per signaal.")
        if gap_gem > 0.2:
            print("Dat is aanzienlijk: een groot deel van de beweging gebeurt VOOR de open.")
            print("Wie in pre-market of op de open koopt, mist dat deel - het zit al in de prijs.")
        elif gap_gem < -0.2:
            print("Negatief: aandelen openen gemiddeld lager dan ze sloten.")
        else:
            print("Klein: de gap voegt weinig toe of af.")
        print(f"\nEendags (open->close): {a:+.3f}% per trade")
        print(f"Meerdaags (huidig):    {c:+.3f}% per trade")
        verschil = a - c
        print(f"Verschil:              {verschil:+.3f} procentpunt")
        print()
        if verschil > 0.2:
            print("-> De eendagsstrategie presteert BETER in deze test.")
        elif verschil < -0.2:
            print("-> De eendagsstrategie presteert SLECHTER. Het grootste deel van het")
            print("   rendement komt uit de dagen NA de eerste, niet uit de eerste dag zelf.")
        else:
            print("-> Vergelijkbaar. Maar let op het aantal trades: eendags betekent elke")
            print("   dag in- en uitstappen, dus veel meer transactiekosten en belasting.")

    # per venster
    if len(frames) >= 2:
        print("\n" + "-" * 80)
        print("PER VENSTER")
        print("-" * 80)
        start = min(f["Datum"].min() for f in frames.values())
        eind = max(f["Datum"].max() for f in frames.values())
        lengte = (eind - start).days // 6
        print(f"{'Venster':<10}" + "".join(f"{n.split('.')[0]:>12}" for n in frames))
        for v in range(6):
            vs = start + pd.Timedelta(days=lengte*v)
            ve = vs + pd.Timedelta(days=lengte)
            regel = f"{v+1:<10}"
            ok = True
            for naam, rd in frames.items():
                sub = rd[(rd["Datum"] >= vs) & (rd["Datum"] < ve)]["Rendement"]
                if len(sub) < 8:
                    ok = False
                    break
                regel += f"{sub.mean():>12.2f}"
            if ok:
                print(regel)

    print("\n" + "=" * 80)
    print("BELANGRIJKE KANTTEKENINGEN")
    print("=" * 80)
    print("1. Dit simuleert de OPENINGSKOERS, niet pre-market. Koop je eerder tegen")
    print("   een andere prijs, dan wijkt je resultaat af van deze cijfers.")
    print("2. Eendags handelen betekent elke dag transactiekosten. Bij een klein")
    print("   rendement per trade eet dat een groot deel op.")
    print("3. Bij een Amerikaanse broker met minder dan $25.000 geldt de PDT-regel:")
    print("   maximaal 3 daytrades per 5 werkdagen. Bij een Europese broker niet.")
    print("4. De openingskoers is het meest volatiele moment van de dag; je")
    print("   werkelijke fill wijkt daar vaker af dan bij een slotkoers.")
    return frames


def test_exits(preset_name="balanced", hold_varianten=(3, 4, 5)):
    """VERGELIJKT TIEN EXIT-METHODES op dezelfde entry-signalen.

    Onderzoek wijst uit dat de exit-methode 30-60% verschil kan maken op
    identieke entries - het is geen stijlkwestie maar bepalend voor het
    resultaat. Tegelijk laat datzelfde onderzoek zien dat trailing stops en
    winstdoelen in tests vaak NIET beter presteren dan simpele exits: ze
    kappen winnaars af.

    Jouw huidige exit (50% winst bij 1R, breakeven-stop, 1.5x ATR trail) is
    nooit tegen alternatieven gemeten. Deze test doet dat, per venster.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 82)
    print("EXIT-METHODE TEST")
    print("=" * 82)
    print("Zelfde entry-signalen, tien verschillende manieren om eruit te stappen.\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 320:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return

    # entries 1x bepalen - die zijn voor alle exit-methodes gelijk
    print("  Entry-signalen bepalen...")
    entries = []
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    for di in range(320, len(alle_dagen) - max(hold_varianten)):
        dag = alle_dagen[di]
        tot_nu = {t: df[df.index <= dag] for t, df in voorbereid.items()}
        tot_nu = {t: d for t, d in tot_nu.items()
                  if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag}
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA21", np.nan)):
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue
            if GEBRUIK_TRENDFILTER:
                if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
                    continue
                if GEBRUIK_EMA300_FILTER:
                    e3 = row.get("EMA300", np.nan)
                    if pd.isna(e3) or row["Close"] <= e3:
                        continue
            if GEBRUIK_LEESBAARHEIDSFILTER:
                eff = row.get("EFFICIENCY", np.nan)
                if pd.isna(eff) or eff < MIN_EFFICIENCY:
                    continue
            entries.append((ticker, dag, i))

    if len(entries) < 50:
        print(f"Te weinig entries ({len(entries)}).")
        return
    print(f"  {len(entries)} entry-signalen gevonden.\n")

    for max_hold in hold_varianten:
        print("=" * 82)
        print(f"RESULTAAT bij maximaal {max_hold} dagen houden")
        print("=" * 82)
        print(f"{'Exit-methode':<40}{'Trades':>8}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
        print("-" * 82)
        alle_res = {}
        for naam, methode in EXIT_VARIANTEN.items():
            rends = []
            for ticker, dag, i in entries:
                df_full = voorbereid[ticker]
                if i + 1 + max_hold > len(df_full):
                    continue
                row = df_full.iloc[i]
                entry = row["Close"]
                stop0 = compute_stop(row, entry)
                future = df_full.iloc[i+1:i+1+max_hold]
                if len(future) == 0:
                    continue
                uit = simuleer_exit(future, entry, row["ATR"], stop0, methode, max_hold)
                if uit is None:
                    continue
                r, outcome, _ = uit
                fund = fund_cache.get(ticker, {})
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append({"Datum": dag, "Rendement": r})
            if len(rends) < 30:
                continue
            rd = pd.DataFrame(rends)
            arr = rd["Rendement"].values
            alle_res[naam] = rd
            print(f"{naam:<40}{len(arr):>8}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}"
                  f"{np.median(arr):>10.2f}")

        if len(alle_res) >= 2:
            print("\n" + "-" * 82)
            print(f"PER VENSTER (bij {max_hold} dagen) - top 4 methodes")
            print("-" * 82)
            top4 = sorted(alle_res.items(), key=lambda x: -x[1]["Rendement"].mean())[:4]
            start = min(d["Datum"].min() for _, d in alle_res.items())
            eind = max(d["Datum"].max() for _, d in alle_res.items())
            lengte = (eind - start).days // 6
            print(f"{'Venster':<9}" + "".join(f"{n.split('.')[0]:>10}" for n, _ in top4))
            wint = {n: 0 for n, _ in top4}
            geldig = 0
            for v in range(6):
                vs = start + pd.Timedelta(days=lengte*v)
                ve = vs + pd.Timedelta(days=lengte)
                regel = f"{v+1:<9}"
                gems = {}
                ok = True
                for naam, rd in top4:
                    sub = rd[(rd["Datum"] >= vs) & (rd["Datum"] < ve)]["Rendement"]
                    if len(sub) < 8:
                        ok = False
                        break
                    gems[naam] = sub.mean()
                    regel += f"{sub.mean():>10.2f}"
                if not ok:
                    continue
                geldig += 1
                wint[max(gems.items(), key=lambda x: x[1])[0]] += 1
                print(regel)
            print("-" * 82)
            print("\nVensters gewonnen:")
            for naam, n in sorted(wint.items(), key=lambda x: -x[1]):
                print(f"   {naam:<45} {n}/{geldig}")
            beste = max(alle_res.items(), key=lambda x: x[1]["Rendement"].mean())
            huidig = alle_res.get("1. HUIDIG: 50%@1R + BE + ATR1.5 trail")
            print(f"\nHoogste gemiddelde: {beste[0]} ({beste[1]['Rendement'].mean():+.3f}%)")
            if huidig is not None:
                v = beste[1]["Rendement"].mean() - huidig["Rendement"].mean()
                print(f"Huidige methode: {huidig['Rendement'].mean():+.3f}%  "
                      f"-> verschil {v:+.3f} procentpunt per trade")
                if v > 0.1 and wint.get(beste[0], 0) >= geldig * 0.5:
                    print("\n-> Deze exit is BETER en consistent. Overstappen aan te raden.")
                elif v > 0.1:
                    print("\n-> Hoger gemiddelde, maar niet consistent per venster. Zwak bewijs.")
                else:
                    print("\n-> Geen duidelijke verbetering. Huidige exit houden.")
        print()
    return


def test_totaalscore(preset_name="balanced", top_n_per_dag=(3, 5, 10)):
    """Vergelijkt SORTEREN OP MOMENTUM met SORTEREN OP TOTAALSCORE.

    Beide methodes krijgen dezelfde kandidaten (dezelfde filters, hetzelfde
    top-percentiel). Het enige verschil is de VOLGORDE waarin ze gerangschikt
    worden, en dus welke je als eerste zou kopen als je maar een paar posities
    per dag kunt openen.

    Dat is precies de praktijksituatie: je portfolio heat laat 6 posities toe,
    de scan geeft er soms 10. Welke rangschikking kiest dan de beste?
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print("MOMENTUM-RANKING versus TOTAALSCORE")
    print("=" * 78)
    print("Zelfde kandidaten, andere volgorde. Welke rangschikking kiest beter?\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 320:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return

    print("  Signalen verzamelen met beide scores...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    signalen = []
    drempel = 100 - TOP_N_PERCENTIEL
    for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {t: df[df.index <= dag] for t, df in voorbereid.items()}
        tot_nu = {t: d for t, d in tot_nu.items()
                  if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag}
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            if i + 1 + MAX_HOLD_DAYS > len(df_full):
                continue
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA21", np.nan)):
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue
            if GEBRUIK_TRENDFILTER:
                if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
                    continue
                if GEBRUIK_EMA300_FILTER:
                    e3 = row.get("EMA300", np.nan)
                    if pd.isna(e3) or row["Close"] <= e3:
                        continue
            if GEBRUIK_LEESBAARHEIDSFILTER:
                eff = row.get("EFFICIENCY", np.nan)
                if pd.isna(eff) or eff < MIN_EFFICIENCY:
                    continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop = compute_stop(row, entry)
            r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset,
                                                    initial_stop=stop)
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100
            totaal, _ = bereken_totaalscore(row, info, stop)
            signalen.append({"Datum": dag, "Ticker": ticker, "Momentum": info["percentiel"],
                              "Totaal": totaal, "Rendement": r})

    if len(signalen) < 50:
        print(f"Te weinig signalen ({len(signalen)}).")
        return
    sdf = pd.DataFrame(signalen)
    per_dag = sdf.groupby("Datum").size()
    print(f"  {len(sdf)} signalen over {len(per_dag)} handelsdagen.")
    print(f"  Gemiddeld {per_dag.mean():.1f} kandidaten per dag "
          f"(mediaan {per_dag.median():.0f}, max {per_dag.max()}).")
    if per_dag.mean() < 4:
        print("\n  LET OP: gemiddeld minder dan 4 kandidaten per dag. De sorteervolgorde")
        print("  maakt dan nauwelijks verschil, want je neemt ze toch allemaal.")
        print("  Deze test is pas zinvol als er meer kandidaten zijn dan posities.")
    print()

    print("=" * 78)
    print("ALS JE MAAR N POSITIES PER DAG KUNT OPENEN, WELKE KIES JE?")
    print("=" * 78)
    print(f"{'Per dag':<10}{'Sorteermethode':<22}{'Trades':>9}{'Gem_%':>10}{'Win_%':>9}")
    print("-" * 78)
    vergelijk = {}
    for n in top_n_per_dag:
        for methode, kolom in [("momentum", "Momentum"), ("totaalscore", "Totaal")]:
            gekozen = (sdf.sort_values(["Datum", kolom], ascending=[True, False])
                          .groupby("Datum").head(n))
            arr = gekozen["Rendement"].values
            if len(arr) < 30:
                continue
            vergelijk[(n, methode)] = gekozen
            print(f"{n:<10}{methode:<22}{len(arr):>9}{arr.mean():>10.3f}{(arr>0).mean()*100:>9.1f}")
        print("-" * 78)

    print("\n" + "=" * 78)
    print("PER VENSTER (bij 5 posities per dag)")
    print("=" * 78)
    if (5, "momentum") in vergelijk and (5, "totaalscore") in vergelijk:
        a = vergelijk[(5, "momentum")]
        b = vergelijk[(5, "totaalscore")]
        start, eind = sdf["Datum"].min(), sdf["Datum"].max()
        lengte = (eind - start).days // 6
        print(f"{'Venster':<10}{'Momentum':>12}{'Totaalscore':>14}{'Beter':>14}")
        print("-" * 78)
        wint = 0
        geldig = 0
        for v in range(6):
            vs = start + pd.Timedelta(days=lengte*v)
            ve = vs + pd.Timedelta(days=lengte)
            am = a[(a["Datum"] >= vs) & (a["Datum"] < ve)]["Rendement"]
            bt = b[(b["Datum"] >= vs) & (b["Datum"] < ve)]["Rendement"]
            if len(am) < 8 or len(bt) < 8:
                continue
            geldig += 1
            beter = "totaalscore" if bt.mean() > am.mean() else "momentum"
            if beter == "totaalscore":
                wint += 1
            print(f"{v+1:<10}{am.mean():>12.2f}{bt.mean():>14.2f}{beter:>14}")
        print("=" * 78)
        print(f"\nTotaalscore wint in {wint} van {geldig} vensters.")
        verschil = b["Rendement"].mean() - a["Rendement"].mean()
        print(f"Verschil in gemiddelde: {verschil:+.3f} procentpunt per trade")
        print()
        if wint >= geldig * 0.6 and verschil > 0:
            print("-> TOTAALSCORE is beter EN consistent. Aan te raden als sorteermethode.")
        elif verschil > 0:
            print("-> Totaalscore scoort hoger, maar niet consistent per venster. Zwak bewijs.")
        else:
            print("-> Totaalscore is NIET beter. Momentum-ranking houden.")
    return vergelijk


def sweep_percentiel(preset_name="balanced", percentielen=(5, 10, 15, 20, 30, 40)):
    """Meet of een RUIMER top-percentiel loont of juist kost.

    De vraag: je ziet nu de sterkste 10%. Als je 20% neemt krijg je ongeveer
    twee keer zoveel kandidaten - maar wel de zwakkere helft erbij. Levert dat
    per saldo meer op, of verwatert het je resultaat?

    Wordt per walk-forward venster gemeten, zodat een toevallig gunstig
    percentiel niet als verbetering wordt aangezien.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print("PERCENTIEL-SWEEP: hoeveel van de top moet je nemen?")
    print("=" * 78)
    print("Ruimer = meer kandidaten, maar ook zwakkere. Wat is de balans?\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 320:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue

    if len(voorbereid) < 15:
        print("Te weinig tickers met genoeg historie.")
        return

    # signalen 1x verzamelen met hun percentiel, daarna per drempel filteren
    print("  Signalen verzamelen...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    signalen = []
    for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {t: df[df.index <= dag] for t, df in voorbereid.items()}
        tot_nu = {t: d for t, d in tot_nu.items()
                  if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag}
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            if i + 1 + MAX_HOLD_DAYS > len(df_full):
                continue
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)):
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue
            if GEBRUIK_TRENDFILTER:
                if pd.isna(row.get("EMA21", np.nan)):
                    continue
                if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
                    continue
                if GEBRUIK_EMA300_FILTER:
                    e300 = row.get("EMA300", np.nan)
                    if pd.isna(e300) or row["Close"] <= e300:
                        continue
            if GEBRUIK_LEESBAARHEIDSFILTER:
                eff = row.get("EFFICIENCY", np.nan)
                if pd.isna(eff) or eff < MIN_EFFICIENCY:
                    continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop = compute_stop(row, entry)
            r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset,
                                                    initial_stop=stop)
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100
            signalen.append({"Datum": dag, "Percentiel": info["percentiel"], "Rendement": r})

    if len(signalen) < 50:
        print(f"Te weinig signalen ({len(signalen)}).")
        return

    sdf = pd.DataFrame(signalen)
    print(f"  {len(sdf)} signalen verzameld.\n")

    print("=" * 78)
    print("RESULTAAT PER PERCENTIEL")
    print("=" * 78)
    print(f"{'Top %':<9}{'Trades':>9}{'Per jaar':>11}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 78)
    jaren = (sdf["Datum"].max() - sdf["Datum"].min()).days / 365.25
    resultaten = []
    for pct in percentielen:
        deel = sdf[sdf["Percentiel"] >= (100 - pct)]
        if len(deel) < 30:
            print(f"{pct:<9}{len(deel):>9}   te weinig")
            continue
        arr = deel["Rendement"].values
        resultaten.append({"pct": pct, "n": len(arr), "gem": arr.mean(),
                            "win": (arr > 0).mean()*100, "deel": deel})
        print(f"{pct:<9}{len(arr):>9}{len(arr)/jaren:>11.0f}{arr.mean():>10.3f}"
              f"{(arr>0).mean()*100:>9.1f}{np.median(arr):>10.2f}")

    if len(resultaten) < 2:
        return

    # per venster om toeval uit te sluiten
    print("\n" + "=" * 78)
    print("PER VENSTER")
    print("=" * 78)
    start, eind = sdf["Datum"].min(), sdf["Datum"].max()
    lengte = (eind - start).days // 6
    kop = f"{'Venster':<9}" + "".join(f"{str(r['pct'])+'%':>10}" for r in resultaten)
    print(kop)
    print("-" * 78)
    wint = {r["pct"]: 0 for r in resultaten}
    geldig = 0
    for v in range(6):
        v_start = start + pd.Timedelta(days=lengte*v)
        v_eind = v_start + pd.Timedelta(days=lengte)
        regel = f"{v+1:<9}"
        gems = {}
        ok = True
        for r in resultaten:
            d = r["deel"]
            sub = d[(d["Datum"] >= v_start) & (d["Datum"] < v_eind)]["Rendement"]
            if len(sub) < 8:
                ok = False
                break
            gems[r["pct"]] = sub.mean()
            regel += f"{sub.mean():>10.2f}"
        if not ok:
            continue
        geldig += 1
        wint[max(gems.items(), key=lambda x: x[1])[0]] += 1
        print(regel)
    print("=" * 78)
    print("\nAantal vensters waarin elk percentiel het beste was:")
    for pct, n in sorted(wint.items(), key=lambda x: -x[1]):
        print(f"   top {pct}%: {n}/{geldig}")

    beste = max(resultaten, key=lambda r: r["gem"])
    huidig = next((r for r in resultaten if r["pct"] == TOP_N_PERCENTIEL), None)
    print(f"\nHoogste gemiddelde: top {beste['pct']}% ({beste['gem']:+.3f}% per trade, "
          f"{beste['n']/jaren:.0f} trades/jaar)")
    if huidig:
        print(f"Huidige instelling: top {huidig['pct']}% ({huidig['gem']:+.3f}% per trade, "
              f"{huidig['n']/jaren:.0f} trades/jaar)")
        if beste["pct"] != huidig["pct"]:
            extra = beste["n"] - huidig["n"]
            print(f"\nOverstappen naar top {beste['pct']}% geeft {extra} extra trades "
                  f"en {beste['gem']-huidig['gem']:+.3f} procentpunt per trade.")
            if wint[beste["pct"]] >= geldig * 0.5:
                print("Dat wordt ondersteund door de vensters - aan te raden.")
            else:
                print("Maar dat wordt NIET consistent ondersteund per venster - voorzichtig.")
    print("\nPas TOP_N_PERCENTIEL bovenin het script aan om dit te wijzigen.")
    return resultaten


def portfolio_simulatie(preset_name="balanced", top_pct=TOP_N_PERCENTIEL,
                         heat_varianten=(0.02, 0.04, 0.06, 0.10, 0.20, 999)):
    """PORTFOLIO-SIMULATIE met beperkt kapitaal.

    Alle eerdere backtests rekenden trades LOS door: elk signaal werd
    uitgevoerd alsof er onbeperkt geld was. In werkelijkheid kun je met 1%
    risico per trade niet 15 posities tegelijk aanhouden - dan riskeer je 15%
    van je account op hetzelfde moment.

    Deze simulatie doet wat je echt zou doen: signalen op volgorde van
    ranking nemen totdat je risicobudget vol zit, en de rest laten lopen.
    Zo zie je:
      - hoeveel van de gevonden signalen je uberhaupt KUNT nemen
      - wat dat met je rendement doet
      - hoe diep je drawdown wordt bij verschillende risiconiveaus

    De variant 999 betekent 'geen limiet' - dat is hoe de oude backtests
    rekenden, en dient hier als vergelijkingspunt.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 78)
    print("PORTFOLIO-SIMULATIE: wat houd je over met beperkt kapitaal?")
    print("=" * 78)
    print(f"Risico per trade: {RISK_PCT_PER_TRADE*100:.1f}%  |  "
          f"Max houdperiode: {MAX_HOLD_DAYS} dagen\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    print("  Indicatoren berekenen...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 320:
                continue
            voorbereid[ticker] = compute_indicators(df_full, spy_close=spy)
        except Exception:
            continue

    if len(voorbereid) < 15:
        print("Te weinig tickers met genoeg historie.")
        return

    # alle signalen 1x verzamelen, met datum en ranking
    print("  Signalen verzamelen...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    signalen = []
    for di in range(320, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]
        tot_nu = {t: df[df.index <= dag] for t, df in voorbereid.items()}
        tot_nu = {t: d for t, d in tot_nu.items()
                  if len(d) >= MOMENTUM_LOOKBACK + MOMENTUM_SKIP + 1 and d.index[-1] == dag}
        if len(tot_nu) < 10:
            continue
        ranking = rangschik_universum(tot_nu)
        drempel = 100 - top_pct
        for ticker, deel in tot_nu.items():
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            if i + 1 + MAX_HOLD_DAYS > len(df_full):
                continue
            row = df_full.iloc[i]
            if pd.isna(row.get("ATR", np.nan)) or pd.isna(row.get("EMA300", np.nan)):
                continue
            if not (MIN_PRICE <= row["Close"] <= MAX_PRICE):
                continue
            if row["Close"] * row.get("VOL_SMA20", 0) < 5_000_000:
                continue
            if GEBRUIK_TRENDFILTER:
                if not (row["Close"] > row["EMA21"] and row["EMA9"] > row["EMA21"]):
                    continue
                if GEBRUIK_EMA300_FILTER and row["Close"] <= row["EMA300"]:
                    continue
            entry = row["Close"]
            stop = compute_stop(row, entry)
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            r, outcome, dagen = simulate_trailing_exit(future, entry, row["ATR"], preset,
                                                        initial_stop=stop)
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100
            signalen.append({"Datum": dag, "Ticker": ticker, "Rang": info["percentiel"],
                              "Rendement": r, "Dagen": dagen})

    if len(signalen) < 50:
        print(f"Te weinig signalen ({len(signalen)}).")
        return

    sdf = pd.DataFrame(signalen).sort_values(["Datum", "Rang"], ascending=[True, False])
    print(f"  {len(sdf)} signalen gevonden over de hele periode.\n")

    print("=" * 78)
    print("RESULTAAT PER RISICOLIMIET")
    print("=" * 78)
    print(f"{'Max heat':<12}{'Max pos':<10}{'Genomen':>10}{'Gemist':>10}"
          f"{'Eind kapitaal':>16}{'Max drawdown':>15}")
    print("-" * 78)

    resultaten = []
    for heat in heat_varianten:
        max_pos = int(heat / RISK_PCT_PER_TRADE) if heat < 999 else 9999
        kapitaal = 1.0
        equity_curve = [1.0]
        open_posities = []   # (sluitdatum, rendement)
        genomen = gemist = 0

        for dag, groep in sdf.groupby("Datum", sort=True):
            # eerst posities sluiten die aan hun eind zijn
            nog_open = []
            for sluit, rend in open_posities:
                if sluit <= dag:
                    kapitaal *= (1 + (rend / 100) * (RISK_PCT_PER_TRADE / 0.05))
                    equity_curve.append(kapitaal)
                else:
                    nog_open.append((sluit, rend))
            open_posities = nog_open

            # dan nieuwe signalen op volgorde van ranking
            for _, sig in groep.iterrows():
                if len(open_posities) >= max_pos:
                    gemist += 1
                    continue
                sluitdatum = dag + pd.Timedelta(days=int(sig["Dagen"]) + 2)
                open_posities.append((sluitdatum, sig["Rendement"]))
                genomen += 1

        # resterende posities afwikkelen
        for _, rend in open_posities:
            kapitaal *= (1 + (rend / 100) * (RISK_PCT_PER_TRADE / 0.05))
            equity_curve.append(kapitaal)

        eq = pd.Series(equity_curve)
        max_dd = ((eq / eq.cummax() - 1) * 100).min()
        label = "geen limiet" if heat >= 999 else f"{heat*100:.0f}%"
        pos_label = "onbeperkt" if heat >= 999 else str(max_pos)
        print(f"{label:<12}{pos_label:<10}{genomen:>10}{gemist:>10}"
              f"{kapitaal:>15.2f}x{max_dd:>14.1f}%")
        resultaten.append({"heat": heat, "kapitaal": kapitaal, "dd": max_dd,
                            "genomen": genomen, "gemist": gemist})

    print("=" * 78)
    rdf = pd.DataFrame(resultaten)
    beperkt = rdf[rdf["heat"] < 999]
    onbeperkt = rdf[rdf["heat"] >= 999]

    print("\n--- WAT DIT BETEKENT ---")
    if len(onbeperkt) > 0:
        o = onbeperkt.iloc[0]
        print(f"Zonder limiet (zoals de oude backtests rekenden): {o['kapitaal']:.2f}x "
              f"met {o['dd']:.1f}% drawdown - maar dat vereist onbeperkt kapitaal.")
    if len(beperkt) > 0:
        # beste risico-gecorrigeerde keuze: kapitaal per procent drawdown
        beperkt = beperkt.copy()
        beperkt["ratio"] = beperkt["kapitaal"] / beperkt["dd"].abs().replace(0, np.nan)
        beste = beperkt.sort_values("ratio", ascending=False).iloc[0]
        print(f"\nBeste verhouding rendement/drawdown: max heat {beste['heat']*100:.0f}% "
              f"({int(beste['heat']/RISK_PCT_PER_TRADE)} posities tegelijk)")
        print(f"   -> {beste['kapitaal']:.2f}x kapitaal, {beste['dd']:.1f}% drawdown")
        print(f"   -> {int(beste['genomen'])} trades genomen, {int(beste['gemist'])} gemist "
              f"omdat het budget vol zat")
        print(f"\nPas MAX_PORTFOLIO_HEAT aan bovenin het script naar {beste['heat']}.")
    print("\nLET OP: hogere heat geeft meer rendement maar ook diepere drawdowns.")
    print("Kies wat je psychologisch kunt volhouden - een strategie die je bij")
    print("de eerste tegenslag opgeeft, levert per definitie niets op.")
    return rdf


def walk_forward_actueel(preset_name="balanced", n_vensters=6, embargo_dagen=30):
    """WALK-FORWARD VALIDATIE VAN DE HUIDIGE CONFIGURATIE.

    Waarom deze functie er is naast walk_forward_validatie: die oude versie
    gebruikt evaluate_ticker_day, oftewel de DREMPEL-methode (RVOL, confidence).
    Die methode is vervangen door cross-sectionele ranking en wordt niet meer
    gebruikt in de scan. De oude walk-forward mat dus een strategie die je niet
    meer draait.

    Deze versie gebruikt precies wat de dagelijkse scan doet:
      - samengesteld momentum (3/6/12 maanden), sterkste TOP_N_PERCENTIEL%
      - trendfilters (EMA9>EMA21, koers boven EMA300)
      - leesbaarheidsfilter (efficiency >= MIN_EFFICIENCY)
      - VIX-venster (VIX_MINIMUM tot VIX_MAXIMUM)
      - de huidige exit (50%@1R, breakeven, ATR-trail, MAX_HOLD_DAYS)

    Elk venster test op data die strikt NA zijn trainingsperiode ligt, met een
    embargo ertussen. Dat geeft zes onafhankelijke metingen in plaats van een.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 84)
    print("WALK-FORWARD VALIDATIE - huidige configuratie")
    print("=" * 84)
    print("Actieve instellingen:")
    print(f"  Momentum:      {MOMENTUM_METHODE} (top {TOP_N_PERCENTIEL}%)")
    print(f"  Trendfilter:   {'aan' if GEBRUIK_TRENDFILTER else 'uit'}"
          f"{' + EMA300' if GEBRUIK_EMA300_FILTER else ''}")
    print(f"  Leesbaarheid:  {'aan' if GEBRUIK_LEESBAARHEIDSFILTER else 'uit'} "
          f"(min {MIN_EFFICIENCY})")
    print(f"  VIX-venster:   {'aan' if GEBRUIK_VIX_FILTER else 'uit'} "
          f"({VIX_MINIMUM:.0f} - {VIX_MAXIMUM:.0f})")
    print(f"  Houdperiode:   {MAX_HOLD_DAYS} dagen")
    print(f"  {n_vensters} vensters, {embargo_dagen} dagen embargo\n")

    preset = PRESETS[preset_name]
    voorbereid, fund_cache, spy = _verzamel_basis(preset_name)
    if len(voorbereid) < 15:
        print("Te weinig tickers.")
        return

    vix = haal_vix() if GEBRUIK_VIX_FILTER else None
    if GEBRUIK_VIX_FILTER and vix is None:
        print("  VIX niet beschikbaar - het VIX-venster wordt in deze test overgeslagen.")
    print(f"  {len(voorbereid)} tickers klaar.\n")

    print("  Signalen verzamelen...")
    alle_dagen = sorted(set().union(*[set(d.index) for d in voorbereid.values()]))
    drempel = 100 - TOP_N_PERCENTIEL
    exit_m = EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    min_hist = 320 if MOMENTUM_METHODE != "enkel" else 200

    trades = []
    n_vix_geblokkeerd = 0
    for di in range(min_hist, len(alle_dagen) - MAX_HOLD_DAYS):
        dag = alle_dagen[di]

        # VIX-venster: alleen data tot en met vandaag
        if vix is not None:
            vix_tot = vix[vix.index <= dag]
            if len(vix_tot) == 0:
                continue
            vix_nu = float(vix_tot.iloc[-1])
            if not (VIX_MINIMUM <= vix_nu <= VIX_MAXIMUM):
                n_vix_geblokkeerd += 1
                continue

        tot_nu = {}
        for t, df in voorbereid.items():
            d = df[df.index <= dag]
            if len(d) >= min_hist and d.index[-1] == dag:
                tot_nu[t] = d
        if len(tot_nu) < 10:
            continue

        ranking = (rangschik_universum(tot_nu) if MOMENTUM_METHODE == "enkel"
                   else rangschik_universum_v2(tot_nu, MOMENTUM_METHODE))
        for ticker in tot_nu:
            info = ranking.get(ticker)
            if not info or info["percentiel"] < drempel:
                continue
            df_full = voorbereid[ticker]
            i = df_full.index.get_loc(dag)
            row = df_full.iloc[i]
            if not _passeert_filters(row):
                continue
            entry = row["Close"]
            future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
            if len(future) == 0:
                continue
            stop0 = compute_stop(row, entry)
            uit = simuleer_exit(future, entry, row["ATR"], stop0, exit_m, MAX_HOLD_DAYS)
            if uit is None:
                continue
            r, outcome, _ = uit
            fund = fund_cache.get(ticker, {})
            if "stop" in outcome:
                av = fund.get("avg_volume") or row.get("VOL_SMA20", 0)
                r -= get_dynamic_slippage((av or 0) * entry) * 100
            r -= COMMISSION_PCT * 2 * 100
            trades.append({"Datum": dag, "Ticker": ticker, "Rendement": r})

    if len(trades) < 60:
        print(f"Te weinig trades ({len(trades)}) voor een zinvolle walk-forward.")
        return
    tdf = pd.DataFrame(trades).sort_values("Datum").reset_index(drop=True)
    if n_vix_geblokkeerd:
        print(f"  {n_vix_geblokkeerd} handelsdagen overgeslagen door het VIX-venster.")
    print(f"  {len(tdf)} trades over {tdf['Datum'].min().date()} t/m {tdf['Datum'].max().date()}\n")

    start, eind = tdf["Datum"].min(), tdf["Datum"].max()
    lengte = (eind - start).days // (n_vensters + 1)

    print("=" * 84)
    print("RESULTAAT PER VENSTER (elk test op data NA zijn trainingsperiode)")
    print("=" * 84)
    print(f"{'Venster':<9}{'Testperiode':<26}{'Trades':>8}{'Gem_%':>10}{'Win_%':>9}{'Mediaan':>10}")
    print("-" * 84)
    resultaten = []
    for v in range(n_vensters):
        train_eind = start + pd.Timedelta(days=lengte * (v + 1))
        test_start = train_eind + pd.Timedelta(days=embargo_dagen)
        test_eind = test_start + pd.Timedelta(days=lengte)
        deel = tdf[(tdf["Datum"] >= test_start) & (tdf["Datum"] < test_eind)]
        if len(deel) < 10:
            print(f"{v+1:<9}{'te weinig trades':<26}{len(deel):>8}")
            continue
        arr = deel["Rendement"].values
        resultaten.append({"venster": v+1, "gem": arr.mean(),
                            "win": (arr > 0).mean()*100, "n": len(arr)})
        print(f"{v+1:<9}{str(test_start.date())+' - '+str(test_eind.date()):<26}"
              f"{len(arr):>8}{arr.mean():>10.2f}{(arr>0).mean()*100:>9.1f}"
              f"{np.median(arr):>10.2f}")
    print("=" * 84)

    if not resultaten:
        print("Geen venster had genoeg trades.")
        return
    positief = sum(1 for r in resultaten if r["gem"] > 0)
    totaal = len(resultaten)
    gem = float(np.mean([r["gem"] for r in resultaten]))
    spreiding = float(np.std([r["gem"] for r in resultaten]))
    print(f"\nPositieve vensters: {positief} van {totaal}")
    print(f"Gemiddeld over de vensters: {gem:+.2f}%  (spreiding {spreiding:.2f})")
    print(f"Over alle trades samen: {tdf['Rendement'].mean():+.2f}% per trade, "
          f"win rate {(tdf['Rendement'] > 0).mean()*100:.1f}%")
    print()
    if positief == totaal:
        print("-> ALLE vensters positief. Sterkst mogelijke uitkomst met deze methode.")
    elif positief >= totaal * 0.7:
        print(f"-> {positief}/{totaal} positief. Redelijk robuust, maar reken op")
        print("   periodes van verlies.")
    else:
        print(f"-> Slechts {positief}/{totaal} positief. Dat is zwak - de goede")
        print("   resultaten leunen dan op een beperkt aantal periodes.")

    print("\nLET OP: survivorship bias. Tickers die zijn verdwenen (faillissement,")
    print("overname) zitten niet in de watchlist, dus verliezers ontbreken.")
    print("Academisch onderzoek schat de overschatting op 1-3% per jaar.")
    return resultaten


def walk_forward_validatie(preset_name="balanced", n_vensters=6, embargo_dagen=30):
    """WALK-FORWARD VALIDATIE - de methode die professionele quant-firma's
    gebruiken in plaats van een enkele train/test-split.

    Waarom dit nodig is, eerlijk gezegd: bij een enkele split kun je de
    testperiode besmetten. Kijk je naar het testresultaat, pas je iets aan en
    draai je opnieuw, dan is die testdata feitelijk trainingsdata geworden.
    Precies dat is in dit project gebeurd - de instellingen zijn meermaals
    bijgesteld nadat het TEST-cijfer bekend was.

    Walk-forward lost dat op met meerdere OPEENVOLGENDE vensters: elk venster
    test op data die strikt NA zijn trainingsperiode ligt. Je krijgt zo 6
    onafhankelijke metingen in plaats van 1. Werkt de strategie in 5 van de 6
    vensters, dan is dat robuust. Werkt hij in 2 van de 6, dan was het geluk.

    Er zit een embargo-periode tussen train en test, zodat indicatoren met een
    lange lookback geen informatie over de testperiode kunnen bevatten.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 76)
    print("WALK-FORWARD VALIDATIE")
    print("=" * 76)
    print(f"{n_vensters} opeenvolgende vensters, embargo van {embargo_dagen} dagen tussen")
    print("train en test. Elk venster test op data die er strikt NA ligt.\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Alle trades verzamelen (1x, met datum)...\n")
    trades = []
    n_gedelist = 0
    for ticker in active:
        try:
            if ticker not in data:
                n_gedelist += 1
                continue
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                n_gedelist += 1
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            fund = fund_cache[ticker]
            for i in range(55, len(df_full) - 1):
                evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                if evald is None:
                    continue
                row = evald["row"]
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row["VOL_SMA20"]
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                trades.append({"Datum": df_full.index[i], "Rendement": r, "Ticker": ticker})
        except Exception:
            continue

    if len(trades) < 100:
        print(f"Te weinig trades ({len(trades)}).")
        return

    tdf = pd.DataFrame(trades).sort_values("Datum").reset_index(drop=True)
    print(f"{len(tdf)} trades verzameld over {tdf['Datum'].min().date()} t/m {tdf['Datum'].max().date()}\n")

    # vensters bepalen op basis van kalendertijd
    start, eind = tdf["Datum"].min(), tdf["Datum"].max()
    totaal_dagen = (eind - start).days
    venster_lengte = totaal_dagen // (n_vensters + 1)

    print("=" * 76)
    print("RESULTAAT PER VENSTER (elk venster test op data NA zijn trainingsperiode)")
    print("=" * 76)
    print(f"{'Venster':<9}{'Testperiode':<26}{'Trades':>8}{'Gem_%':>9}{'Win_%':>8}")
    print("-" * 76)

    venster_resultaten = []
    for v in range(n_vensters):
        train_eind = start + pd.Timedelta(days=venster_lengte * (v + 1))
        test_start = train_eind + pd.Timedelta(days=embargo_dagen)
        test_eind = test_start + pd.Timedelta(days=venster_lengte)
        deel = tdf[(tdf["Datum"] >= test_start) & (tdf["Datum"] < test_eind)]
        if len(deel) < 15:
            print(f"{v+1:<9}{'te weinig trades':<26}{len(deel):>8}")
            continue
        gem = deel["Rendement"].mean()
        win = (deel["Rendement"] > 0).mean() * 100
        venster_resultaten.append({"venster": v + 1, "gem": gem, "win": win, "n": len(deel)})
        periode = f"{test_start.date()} - {test_eind.date()}"
        print(f"{v+1:<9}{periode:<26}{len(deel):>8}{gem:>9.2f}{win:>8.1f}")

    if not venster_resultaten:
        print("\nGeen enkel venster had genoeg trades.")
        return

    print("=" * 76)
    positief = sum(1 for r in venster_resultaten if r["gem"] > 0)
    totaal = len(venster_resultaten)
    gemiddelde = np.mean([r["gem"] for r in venster_resultaten])
    spreiding = np.std([r["gem"] for r in venster_resultaten])

    print(f"\nPositieve vensters: {positief} van {totaal}")
    print(f"Gemiddeld over alle vensters: {gemiddelde:+.2f}%  (spreiding {spreiding:.2f})")
    print()
    if positief == totaal:
        print("-> ALLE vensters positief. Dat is het sterkst mogelijke signaal met deze")
        print("   methode: de strategie werkte in elke afzonderlijke periode.")
    elif positief >= totaal * 0.7:
        print(f"-> {positief}/{totaal} vensters positief. Redelijk robuust, maar niet elke")
        print("   marktomgeving pakt goed uit. Reken op periodes van verlies.")
    elif positief >= totaal * 0.5:
        print(f"-> Slechts {positief}/{totaal} positief. Dat is dicht bij een muntworp.")
        print("   Een enkele gunstige testperiode kan eerdere resultaten hebben gekleurd.")
    else:
        print(f"-> Maar {positief}/{totaal} vensters positief. De strategie werkt niet")
        print("   consistent door de tijd heen. Eerdere positieve uitkomsten waren")
        print("   waarschijnlijk het gevolg van een gunstig gekozen testperiode.")

    if n_gedelist > 0:
        print()
        print("=" * 76)
        print("WAARSCHUWING: SURVIVORSHIP BIAS")
        print("=" * 76)
        print(f"{n_gedelist} tickers uit de watchlist hadden geen bruikbare data (gedelist,")
        print("overgenomen of hernoemd) en zijn overgeslagen. Je test dus alleen op")
        print("bedrijven die het OVERLEEFD hebben. Bedrijven die failliet gingen dragen")
        print("geen verliezen bij aan deze cijfers.")
        print("Academisch onderzoek schat dat dit rendementen met 1-3% per jaar overschat.")
        print("Het werkelijke resultaat ligt dus waarschijnlijk LAGER dan hierboven staat.")
    return venster_resultaten


def analyse_confidence_edge(preset_name="balanced"):
    """Meet of trades met een HOGERE confidence-score systematisch beter
    presteren - en of dat standhoudt op verse data.

    Waarom dit ertoe doet: als hoge scores echt beter zijn, kun je je kapitaal
    concentreren op die trades in plaats van alles gelijk te behandelen. Dat
    verhoogt het rendement zonder dat je meer risico per trade neemt.

    Cruciaal: het verband wordt apart gemeten op TRAIN en TEST. Een verband dat
    alleen in TRAIN bestaat is een toevalligheid; alleen als het in beide
    periodes dezelfde richting op wijst, is het bruikbaar.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 74)
    print("CONFIDENCE-EDGE ANALYSE")
    print("=" * 74)
    print("Verdienen hoog scorende trades een grotere positie?\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Trades verzamelen...\n")
    trades = []
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            fund = fund_cache[ticker]
            split = int(len(df_full) * TRAIN_TEST_SPLIT)
            for i in range(55, len(df_full) - 1):
                evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                if evald is None:
                    continue
                row = evald["row"]
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row["VOL_SMA20"]
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                trades.append({"Confidence": evald["confidence"], "Rendement": r,
                                "Periode": "TRAIN" if i < split else "TEST"})
        except Exception:
            continue

    if len(trades) < 100:
        print(f"Te weinig trades ({len(trades)}) voor een betrouwbare analyse.")
        return

    tdf = pd.DataFrame(trades)
    print(f"{len(tdf)} trades verzameld.\n")

    # in kwintielen verdelen per periode
    print("=" * 74)
    print("RENDEMENT PER CONFIDENCE-GROEP (kwintielen)")
    print("=" * 74)
    overzicht = []
    for periode in ["TRAIN", "TEST"]:
        deel = tdf[tdf["Periode"] == periode].copy()
        if len(deel) < 50:
            continue
        deel["Groep"] = pd.qcut(deel["Confidence"], 5,
                                 labels=["1 (laagst)", "2", "3", "4", "5 (hoogst)"], duplicates="drop")
        g = deel.groupby("Groep", observed=True).agg(
            Trades=("Rendement", "size"),
            Gem_pct=("Rendement", "mean"),
            Win_pct=("Rendement", lambda x: (x > 0).mean() * 100),
            Conf_min=("Confidence", "min"),
            Conf_max=("Confidence", "max"))
        g = g.round(2)
        print(f"\n[{periode}]")
        print(g.to_string())
        overzicht.append((periode, g))

    print("\n" + "=" * 74)
    print("CONCLUSIE")
    print("=" * 74)
    if len(overzicht) == 2:
        tr = overzicht[0][1]; te = overzicht[1][1]
        tr_stijgend = tr["Gem_pct"].iloc[-1] > tr["Gem_pct"].iloc[0]
        te_stijgend = te["Gem_pct"].iloc[-1] > te["Gem_pct"].iloc[0]
        tr_corr = tdf[tdf["Periode"] == "TRAIN"]["Confidence"].corr(
                  tdf[tdf["Periode"] == "TRAIN"]["Rendement"])
        te_corr = tdf[tdf["Periode"] == "TEST"]["Confidence"].corr(
                  tdf[tdf["Periode"] == "TEST"]["Rendement"])
        print(f"Correlatie confidence <-> rendement:  TRAIN {tr_corr:+.3f}   TEST {te_corr:+.3f}")
        print(f"Hoogste groep beter dan laagste:      TRAIN {'ja' if tr_stijgend else 'nee'}"
              f"        TEST {'ja' if te_stijgend else 'nee'}")
        print()
        if tr_stijgend and te_stijgend and te_corr > 0.02:
            besparing = te["Gem_pct"].iloc[-1] - te["Gem_pct"].mean()
            print("-> De confidence-score voorspelt het rendement in BEIDE periodes.")
            print("   Dat rechtvaardigt concentreren: neem alleen trades uit de hoogste")
            print("   groep(en), of geef die een groter deel van je risicobudget.")
            print(f"   Alleen de hoogste groep nemen levert in TEST {besparing:+.2f} procentpunt")
            print("   per trade extra op t.o.v. alle trades gelijk behandelen.")
            print(f"   Praktisch: verhoog MIN_CONFIDENCE naar ~{te.iloc[-1].name and int(te['Conf_min'].iloc[-1])}")
        elif tr_stijgend and not te_stijgend:
            print("-> Het verband bestaat WEL in TRAIN maar NIET in TEST.")
            print("   Dat is een klassiek overfitting-patroon: de score past goed op de")
            print("   data waarop hij is afgesteld, maar voorspelt niets op verse data.")
            print("   Concentreren op hoge scores is dan NIET te onderbouwen - behandel")
            print("   alle trades boven de drempel gelijk.")
        else:
            print("-> Geen consistent verband tussen confidence en rendement.")
            print("   Alle trades boven de drempel gelijk behandelen is dan de eerlijkste")
            print("   keuze. Een hogere score betekent in deze data niet 'betere trade'.")
    return tdf


def sweep_grid(preset_name="balanced",
                rvol_waarden=(0.5, 0.8, 1.2),
                conf_waarden=(60, 70, 75, 80),
                floor_waarden=(0, 20, 30, 40)):
    """GRID-SWEEP over de drie hoofdparameters tegelijk.

    Waarom samen en niet los: RVOL, MIN_CONFIDENCE en MODULE_FLOOR hangen
    onderling samen. Dat bleek toen het verlagen van RVOL alleen leidde tot NUL
    signalen, omdat MIN_CONFIDENCE nog op de oude waarde stond. Een parameter
    los optimaliseren kan dus een instelling opleveren die alleen goed werkt
    bij de oude waarde van de andere twee.

    Deze sweep berekent per combinatie het rendement EN de stabiliteit: hoe
    goed presteren de directe buren van een combinatie? Een resultaat dat
    instort zodra je een parameter iets verschuift, is bijna altijd toeval.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 76)
    print("GRID-SWEEP: RVOL x MIN_CONFIDENCE x MODULE_FLOOR")
    print("=" * 76)
    n_comb = len(rvol_waarden) * len(conf_waarden) * len(floor_waarden)
    print(f"{n_comb} combinaties worden getest. Dit duurt enkele minuten.\n")

    preset_basis = dict(PRESETS[preset_name])
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Data voorbereiden...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            voorbereid[ticker] = df_full
        except Exception:
            continue

    split_punt = {t: int(len(d) * TRAIN_TEST_SPLIT) for t, d in voorbereid.items()}
    resultaten = []
    teller = 0
    for rv in rvol_waarden:
        for conf in conf_waarden:
            for floor in floor_waarden:
                teller += 1
                preset = dict(preset_basis)
                preset.update({"RVOL_MIN": rv, "MIN_CONFIDENCE": conf, "MODULE_FLOOR": floor})
                train_r, test_r = [], []
                for ticker, df_full in voorbereid.items():
                    fund = fund_cache[ticker]
                    sp = split_punt[ticker]
                    for i in range(55, len(df_full) - 1):
                        evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                        if evald is None:
                            continue
                        row = evald["row"]
                        entry = row["Close"]
                        future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                        if len(future) == 0:
                            continue
                        stop = compute_stop(row, entry)
                        r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                        if "stop" in outcome:
                            av = fund.get("avg_volume") or row["VOL_SMA20"]
                            r -= get_dynamic_slippage((av or 0) * entry) * 100
                        r -= COMMISSION_PCT * 2 * 100
                        (train_r if i < sp else test_r).append(r)
                if len(train_r) >= 30 and len(test_r) >= 10:
                    tr, te = np.array(train_r), np.array(test_r)
                    resultaten.append({
                        "RVOL": rv, "CONF": conf, "FLOOR": floor,
                        "N_train": len(tr), "N_test": len(te),
                        "TRAIN_%": round(float(tr.mean()), 2),
                        "TEST_%": round(float(te.mean()), 2),
                        "Win_%": round(float((np.concatenate([tr, te]) > 0).mean() * 100), 1),
                    })
                print(f"   [{teller}/{n_comb}] RVOL {rv}, CONF {conf}, FLOOR {floor}", end="\r")

    print(" " * 60, end="\r")
    if not resultaten:
        print("Geen combinatie gaf genoeg trades.")
        return

    rdf = pd.DataFrame(resultaten)
    # alleen combinaties die op BEIDE periodes positief zijn, zijn interessant
    rdf["Beide_pos"] = (rdf["TRAIN_%"] > 0) & (rdf["TEST_%"] > 0)
    rdf["Verschil"] = (rdf["TRAIN_%"] - rdf["TEST_%"]).abs()

    print("=" * 76)
    print("TOP 15 op TEST-rendement (de periode die NIET gebruikt is om af te stellen)")
    print("=" * 76)
    print(rdf.sort_values("TEST_%", ascending=False).head(15).to_string(index=False))

    robuust = rdf[rdf["Beide_pos"] & (rdf["Verschil"] < 0.5)].sort_values("TEST_%", ascending=False)
    print("\n" + "=" * 76)
    print("ROBUUSTE COMBINATIES (positief in TRAIN EN TEST, en die twee liggen dicht bijeen)")
    print("=" * 76)
    if len(robuust) > 0:
        print(robuust.head(10).to_string(index=False))
        b = robuust.iloc[0]
        print(f"\nAanbevolen: RVOL_MIN={b['RVOL']}, MIN_CONFIDENCE={int(b['CONF'])}, MODULE_FLOOR={int(b['FLOOR'])}")
        print(f"   TRAIN {b['TRAIN_%']:+.2f}%  TEST {b['TEST_%']:+.2f}%  "
              f"({int(b['N_train'])}+{int(b['N_test'])} trades)")
        print("   Deze combinatie presteert vergelijkbaar op data die NIET is gebruikt")
        print("   om 'm te kiezen - dat is het belangrijkste teken tegen overfitting.")
    else:
        print("Geen enkele combinatie was positief in BEIDE periodes met een klein verschil.")
        print("Dat is een waarschuwing: de goede resultaten in TRAIN houden geen stand")
        print("op verse data. Wees dan voorzichtig met elke gekozen instelling.")

    print("\nLET OP: bij 48 combinaties op dezelfde data scoort er altijd wel eentje")
    print("goed puur door toeval. Kies daarom uit de ROBUUSTE lijst, niet uit de top-15.")
    return rdf


def sweep_confidence(preset_name="balanced", drempels=(50, 55, 60, 65, 70, 75, 80, 85, 90)):
    """CONFIDENCE-DREMPEL SWEEP - meet welke MIN_CONFIDENCE past bij de huidige
    RVOL-instelling.

    Waarom dit nodig is: MIN_CONFIDENCE en RVOL_MIN hangen samen. Toen RVOL op
    2.0 stond kwamen er weinig maar hoogscorende kandidaten door, en paste een
    drempel van 85. Met RVOL op 0.8 komen er meer maar lager-scorende kandidaten
    binnen - die stranden dan allemaal op diezelfde lat, met 0 signalen tot
    gevolg. Deze sweep meet welke drempel nu past.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 72)
    print("CONFIDENCE-DREMPEL SWEEP")
    print("=" * 72)
    print(f"Meet welke MIN_CONFIDENCE past bij RVOL_MIN = {PRESETS[preset_name]['RVOL_MIN']}\n")

    preset_basis = dict(PRESETS[preset_name])
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Data voorbereiden...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            voorbereid[ticker] = df_full
        except Exception:
            continue

    resultaten = []
    for drempel in drempels:
        preset = dict(preset_basis)
        preset["MIN_CONFIDENCE"] = drempel
        rends = []
        for ticker, df_full in voorbereid.items():
            fund = fund_cache[ticker]
            for i in range(55, len(df_full) - 1):
                evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                if evald is None:
                    continue
                row = evald["row"]
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row["VOL_SMA20"]
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append(r)
        if rends:
            arr = np.array(rends)
            per_jaar = len(arr) / (len(spy) / 252)
            resultaten.append({
                "MIN_CONF": drempel, "Signalen": len(arr),
                "Per_jaar": round(per_jaar, 0),
                "Gem_%": round(float(arr.mean()), 2),
                "WinRate_%": round(float((arr > 0).mean() * 100), 1),
            })
        print(f"   MIN_CONFIDENCE {drempel}: {len(rends)} signalen")

    if not resultaten:
        print("\nGeen resultaten - zelfs de laagste drempel gaf niets.")
        return

    rdf = pd.DataFrame(resultaten)
    print("\n" + "=" * 72)
    print("RESULTAAT")
    print("=" * 72)
    print(rdf.to_string(index=False))

    bruikbaar = rdf[rdf["Signalen"] >= 30]
    print()
    if len(bruikbaar) > 0:
        beste = bruikbaar.sort_values("Gem_%", ascending=False).iloc[0]
        print(f"Beste drempel met genoeg signalen (>=30): MIN_CONFIDENCE = {int(beste['MIN_CONF'])}")
        print(f"   -> {int(beste['Signalen'])} signalen ({beste['Per_jaar']:.0f} per jaar), "
              f"{beste['Gem_%']:+.2f}% per trade, win rate {beste['WinRate_%']}%")
        print(f"   Pas 'MIN_CONFIDENCE' aan in de {preset_name}-preset bovenin het script.")
    else:
        print("Geen enkele drempel gaf 30+ signalen - de andere filters zijn te streng.")
    print()
    print("Kijk of er een BREED gebied van bruikbare waarden is, niet naar een")
    print("losse piek. Een drempel die alleen bij exact een waarde goed werkt,")
    print("is bijna altijd toeval.")
    return rdf


def sweep_rvol(preset_name="balanced", rvol_waarden=(0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0)):
    """RVOL-SWEEP - test het effect van de volume-eis op zowel het AANTAL
    signalen als de KWALITEIT ervan.

    Waarom dit meer is dan een knop omdraaien: RVOL_MIN eist een volumePIEK,
    wat betekent dat het aandeel al gesprongen moet zijn voordat de scanner het
    ziet. De benchmark wees dat aan als het waarschijnlijke probleem - je koopt
    op lokale toppen. Als die diagnose klopt, zou een LAGERE RVOL-eis niet
    alleen meer signalen geven, maar ook BETERE.

    Als het resultaat vlak blijft of verslechtert bij lagere RVOL, dan is die
    diagnose onjuist en ligt de oorzaak ergens anders.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 72)
    print("RVOL-SWEEP: effect van de volume-eis op aantal EN kwaliteit")
    print("=" * 72)
    print("Test of een lagere volume-eis leidt tot meer EN betere signalen.\n")

    preset_basis = dict(PRESETS[preset_name])
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    print("  Data voorbereiden...\n")
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            voorbereid[ticker] = df_full
        except Exception:
            continue

    resultaten = []
    for rv in rvol_waarden:
        preset = dict(preset_basis)
        preset["RVOL_MIN"] = rv
        rends = []
        for ticker, df_full in voorbereid.items():
            fund = fund_cache[ticker]
            for i in range(55, len(df_full) - 1):
                evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                if evald is None:
                    continue
                row = evald["row"]
                entry = row["Close"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund.get("avg_volume") or row["VOL_SMA20"]
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append(r)
        if rends:
            arr = np.array(rends)
            resultaten.append({
                "RVOL_min": rv, "Signalen": len(arr),
                "Gem_%": round(float(arr.mean()), 2),
                "WinRate_%": round(float((arr > 0).mean() * 100), 1),
                "Mediaan_%": round(float(np.median(arr)), 2),
            })
        print(f"   RVOL >= {rv}: {len(rends)} signalen")

    if not resultaten:
        print("\nGeen resultaten.")
        return

    rdf = pd.DataFrame(resultaten)
    print("\n" + "=" * 72)
    print("RESULTAAT")
    print("=" * 72)
    print(rdf.to_string(index=False))

    print("\n--- Interpretatie ---")
    laag = rdf[rdf["RVOL_min"] <= 1.0]["Gem_%"].mean() if (rdf["RVOL_min"] <= 1.0).any() else np.nan
    hoog = rdf[rdf["RVOL_min"] >= 2.0]["Gem_%"].mean() if (rdf["RVOL_min"] >= 2.0).any() else np.nan
    if not np.isnan(laag) and not np.isnan(hoog):
        print(f"Lage volume-eis (<=1.0x):  gemiddeld {laag:+.2f}% per trade")
        print(f"Hoge volume-eis (>=2.0x):  gemiddeld {hoog:+.2f}% per trade")
        print()
        if laag > hoog + 0.3:
            print("-> Een LAGERE volume-eis presteert beter. Dat bevestigt de diagnose:")
            print("   het eisen van een volumepiek betekent te laat instappen.")
        elif hoog > laag + 0.3:
            print("-> Een HOGERE volume-eis presteert beter. De diagnose klopte dus niet;")
            print("   de volumepiek is juist nuttig en het probleem ligt elders.")
        else:
            print("-> Nauwelijks verschil. De volume-eis bepaalt vooral het AANTAL")
            print("   signalen, niet de kwaliteit. Kies 'm dus puur op hoeveel")
            print("   kandidaten je per dag wilt zien.")

    beste = rdf.sort_values("Gem_%", ascending=False).iloc[0]
    print(f"\nBeste waarde in deze test: RVOL_MIN = {beste['RVOL_min']} "
          f"({beste['Signalen']} signalen, {beste['Gem_%']:+.2f}% per trade)")
    print("Aanpassen kan bovenin het script bij de preset, of via RVOL_MIN in de preset-dict.")
    return rdf


def sweep_houdperiode(preset_name="balanced", periodes=(2, 3, 4, 5, 7, 10, 20, 40),
                       trail_multipliers=(1.0, 1.5, 2.0, 2.5, 3.0, 4.0)):
    """HOUDPERIODE-SWEEP - test dezelfde entries met verschillende houdperiodes
    en trailing-stop-breedtes.

    Waarom dit de enige overgebleven zinvolle test is: de eindvergelijking liet
    zien dat kopen-en-vasthouden de 3-daagse strategie met ~189 procentpunt
    versloeg op DEZELFDE aandelen. Het probleem zit dus niet in WELKE aandelen
    worden gekozen, maar in hoe snel ze worden losgelaten.

    Deze functie varieert alleen de houdperiode en de stopbreedte - geen nieuwe
    filters, geen extra indicatoren. Als er ergens een optimum ligt, komt het
    hier naar boven. Zo niet, dan is dat ook een duidelijk antwoord.
    """
    print(f"[versie {SCRIPT_VERSIE}]")
    print("=" * 70)
    print("HOUDPERIODE-SWEEP")
    print("=" * 70)
    print("Test dezelfde entries met verschillende houdperiodes en stopbreedtes.")
    print("Geen nieuwe filters - alleen de exit varieert.\n")

    preset = PRESETS[preset_name]
    active = list(WATCHLIST)

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    data = {}
    n_chunks = (len(active) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        print(f"  Koersdata ophalen: batch {c+1}/{n_chunks}...")
        try:
            bd = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                              auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = bd[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen: {e}")

    print("\n  Fundamentals ophalen...")
    fund_cache = {t: get_fundamentals(t) for t in active}

    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            e = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(e, pd.DataFrame):
                e = e.iloc[:, 0]
            etf_data[etf] = e
        except Exception:
            etf_data[etf] = None

    # 1x alle entry-signalen verzamelen (die veranderen niet per houdperiode)
    print("  Entry-signalen verzamelen...\n")
    signalen = []
    voorbereid = {}
    for ticker in active:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                continue
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(get_sector_etf(ticker)), spy)
            voorbereid[ticker] = df_full
            fund = fund_cache[ticker]
            for i in range(55, len(df_full) - 1):
                evald = evaluate_ticker_day(ticker, df_full.iloc[:i+1], fund, preset, check_earnings=False)
                if evald is not None:
                    signalen.append((ticker, i, evald["row"]))
        except Exception:
            continue

    if not signalen:
        print("Geen entry-signalen gevonden.")
        return
    print(f"  {len(signalen)} entry-signalen gevonden. Nu {len(periodes)*len(trail_multipliers)} varianten testen...\n")

    origineel_max = MAX_HOLD_DAYS
    origineel_trail = STOP_ATR_MULT
    resultaten = []

    for hold in periodes:
        for trail in trail_multipliers:
            globals()["MAX_HOLD_DAYS"] = hold
            globals()["STOP_ATR_MULT"] = trail
            rends = []
            for ticker, i, row in signalen:
                df_full = voorbereid[ticker]
                future = df_full.iloc[i+1:i+1+hold]
                if len(future) == 0:
                    continue
                entry = row["Close"]
                stop = compute_stop(row, entry)
                r, outcome, _ = simulate_trailing_exit(future, entry, row["ATR"], preset, initial_stop=stop)
                if "stop" in outcome:
                    av = fund_cache[ticker].get("avg_volume") or row["VOL_SMA20"]
                    r -= get_dynamic_slippage((av or 0) * entry) * 100
                r -= COMMISSION_PCT * 2 * 100
                rends.append(r)
            if rends:
                arr = np.array(rends)
                resultaten.append({
                    "Hold_dagen": hold, "Stop_ATR": trail, "Trades": len(arr),
                    "Gem_%": round(float(arr.mean()), 2),
                    "WinRate_%": round(float((arr > 0).mean() * 100), 1),
                    "Mediaan_%": round(float(np.median(arr)), 2),
                    "Totaal_%": round(float(((1 + arr / 100).prod() - 1) * 100), 1),
                })

    globals()["MAX_HOLD_DAYS"] = origineel_max
    globals()["STOP_ATR_MULT"] = origineel_trail

    rdf = pd.DataFrame(resultaten).sort_values("Gem_%", ascending=False)
    print("=" * 70)
    print("RESULTATEN - gesorteerd op gemiddeld rendement per trade")
    print("=" * 70)
    print(rdf.to_string(index=False))

    beste = rdf.iloc[0]
    kort = rdf[rdf["Hold_dagen"] <= 5]
    if len(kort) > 0:
        bk = kort.iloc[0]
        print()
        print("-" * 70)
        print(f"BESTE VARIANT BINNEN 5 DAGEN (jouw voorkeur):")
        print(f"   {int(bk['Hold_dagen'])} dagen houden met stop op {bk['Stop_ATR']}x ATR")
        print(f"   -> {bk['Gem_%']:+.2f}% per trade, win rate {bk['WinRate_%']}%, "
              f"totaal {bk['Totaal_%']:+.1f}%")
        print(f"   Zet MAX_HOLD_DAYS = {int(bk['Hold_dagen'])} en STOP_ATR_MULT = {bk['Stop_ATR']} "
              f"bovenin het script.")
        print("-" * 70)
    huidige = rdf[(rdf["Hold_dagen"] == 5) & (rdf["Stop_ATR"] == 1.5)]
    print()
    print(f"Beste variant: {int(beste['Hold_dagen'])} dagen houden met stop op "
          f"{beste['Stop_ATR']}x ATR -> {beste['Gem_%']:+.2f}% per trade "
          f"({beste['WinRate_%']}% win rate)")
    if len(huidige) > 0:
        h = huidige.iloc[0]
        print(f"Jouw huidige instelling (5 dagen, 1.5x ATR) -> {h['Gem_%']:+.2f}% per trade")
        verschil = beste["Gem_%"] - h["Gem_%"]
        print(f"Verschil: {verschil:+.2f} procentpunt per trade")

    print()
    print("LET OP: de beste variant is per definitie de best passende op DEZE data.")
    print("Kijk of er een BREED gebied van goede waarden is (bv. 20-60 dagen allemaal")
    print("positief) - dat is betrouwbaarder dan een losse uitschieter. Een enkele")
    print("piek tussen slechte buren is meestal toeval.")
    return rdf


def backtest(preset_name="balanced", regime_filter_override=None):
    preset = PRESETS[preset_name]
    if preset_name == "explosive":
        print("Explosive-preset: NASDAQ-brede lijst wordt opgehaald (dynamisch, net als de dagelijkse scan)...")
        active_watchlist = get_nasdaq_universe(EXPLOSIVE_BACKTEST_UNIVERSE_SIZE)
        if not active_watchlist:
            active_watchlist = list(EXPLOSIVE_WATCHLIST)
    else:
        active_watchlist = list(WATCHLIST)
    effective_regime_filter = USE_MARKET_REGIME_FILTER if regime_filter_override is None else regime_filter_override
    print(f"[versie {SCRIPT_VERSIE}]")
    print(f"Backtest gestart ({BACKTEST_PERIOD}, max hold={MAX_HOLD_DAYS}d met trailing-exit, preset={preset_name.upper()})")
    print(f"Stop-methode: {'structuur+ATR' if USE_STRUCTURE_STOP else 'ATR'}, "
          f"begrensd op max {MAX_STOP_PCT*100:.0f}% risico per trade")
    print(f"Watchlist: {len(active_watchlist)} tickers")
    print(f"Min. confidence: {preset['MIN_CONFIDENCE']}")
    print(f"Train/test-split: eerste {int(TRAIN_TEST_SPLIT*100)}% = TRAIN, "
          f"laatste {int((1-TRAIN_TEST_SPLIT)*100)}% = TEST")
    print(f"Marktregime-filter (ALLEEN deze backtest-run, niet de live scan): "
          f"{'AAN' if effective_regime_filter else 'UIT'}  |  "
          f"Variabele slippage: {[p for _, p in SLIPPAGE_TIERS]}")
    print("(earnings-filter wordt in de backtest overgeslagen - yfinance heeft geen")
    print(" betrouwbare historische earnings-kalender voor willekeurige datums in het verleden)")
    if preset_name == "explosive":
        print(f"LET OP: bij {len(active_watchlist)} tickers duurt het ophalen van fundamentals")
        print("(float, market cap) een stuk langer dan bij de andere presets - reken op enkele minuten extra.\n")
    else:
        print()

    spy = yf.download("SPY", period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
    if isinstance(spy, pd.DataFrame):
        spy = spy.iloc[:, 0]

    # koersdata in chunks ophalen - bij een groot universum (explosive) is
    # 1 enkele download-aanroep onbetrouwbaar/traag
    data = {}
    n_chunks = (len(active_watchlist) - 1) // DOWNLOAD_CHUNK_SIZE + 1
    for c in range(n_chunks):
        batch = active_watchlist[c * DOWNLOAD_CHUNK_SIZE:(c + 1) * DOWNLOAD_CHUNK_SIZE]
        if n_chunks > 1:
            print(f"  Koersdata ophalen: batch {c+1}/{n_chunks} ({len(batch)} tickers)...")
        try:
            batch_data = yf.download(batch, period=BACKTEST_PERIOD, group_by="ticker",
                                      auto_adjust=True, progress=False, threads=True)
            for t in batch:
                try:
                    data[t] = batch_data[t]
                except Exception:
                    pass
        except Exception as e:
            print(f"    Batch overgeslagen door fout: {e}")

    print(f"\nFundamentals ophalen voor {len(active_watchlist)} tickers (dit is de trage stap)...")
    fund_cache = {t: get_fundamentals(t) for t in active_watchlist}

    # sector-ETF's 1x ophalen voor de hele backtest-periode
    unique_etfs = sorted(set(SECTOR_ETF.get(t, DEFAULT_SECTOR_ETF) for t in active_watchlist) | {DEFAULT_SECTOR_ETF})
    etf_data = {}
    for etf in unique_etfs:
        try:
            s = yf.download(etf, period=BACKTEST_PERIOD, auto_adjust=True, progress=False)["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            etf_data[etf] = s
        except Exception:
            etf_data[etf] = None

    all_trades = []
    prepared_data = {}
    n_rows_checked = 0
    n_passed_filters = 0
    n_blocked_by_regime = 0
    tickers_with_data = 0

    for ticker in active_watchlist:
        try:
            df_full = data[ticker].dropna()
            if len(df_full) < 80:
                print(f"  [{ticker}] te weinig data, overgeslagen")
                continue
            tickers_with_data += 1
            sector_etf = get_sector_etf(ticker)
            df_full = compute_indicators(df_full, spy_close=spy)
            df_full = add_sector_rs(df_full, etf_data.get(sector_etf), spy)
            fund = fund_cache[ticker]
            split_index = int(len(df_full) * TRAIN_TEST_SPLIT)

            prepared_data[ticker] = df_full   # bewaren voor de random-entry benchmark

            for i in range(55, len(df_full) - 1):
                n_rows_checked += 1

                if effective_regime_filter and not is_market_regime_bullish(spy, as_of_index=i):
                    n_blocked_by_regime += 1
                    continue

                df_upto = df_full.iloc[:i+1]
                evald = evaluate_ticker_day(ticker, df_upto, fund, preset, check_earnings=False)
                if evald is None:
                    continue
                n_passed_filters += 1

                row = evald["row"]
                entry = row["Close"]
                atr_initial = row["ATR"]
                future = df_full.iloc[i+1:i+1+MAX_HOLD_DAYS]
                if len(future) == 0:
                    continue

                initial_stop = compute_stop(row, entry)
                ret_pct, outcome, days_held = simulate_trailing_exit(
                    future, entry, atr_initial, preset, initial_stop=initial_stop)

                # variabele slippage alleen toepassen als de trade via een stop eindigde
                if "stop" in outcome:
                    avg_vol = fund["avg_volume"] or row["VOL_SMA20"]
                    dollar_vol = (avg_vol or 0) * entry
                    slip = get_dynamic_slippage(dollar_vol)
                    ret_pct -= slip * 100

                ret_pct -= COMMISSION_PCT * 2 * 100

                all_trades.append({
                    "Ticker": ticker,
                    "Datum": df_full.index[i].strftime("%Y-%m-%d"),
                    "Confidence": evald["confidence"],
                    "Rendement_%": round(ret_pct, 2),
                    "Uitkomst": outcome,
                    "DagenGehouden": days_held,
                    "Periode": "TRAIN" if i < split_index else "TEST",
                    "mod_trend": evald["sub_scores"]["trend"],
                    "mod_momentum": evald["sub_scores"]["momentum"],
                    "mod_volume": evald["sub_scores"]["volume"],
                    "mod_volatility": evald["sub_scores"]["volatility"],
                    "mod_rs": evald["sub_scores"]["rs"],
                    "mod_catalyst": evald["sub_scores"]["catalyst"],
                    "mod_structuur": evald["sub_scores"]["structuur"],
                })
        except Exception as e:
            print(f"  [{ticker}] overgeslagen door fout: {e}")
            continue

    print(f"\n--- Diagnostiek ---")
    print(f"Tickers met genoeg data: {tickers_with_data}/{len(active_watchlist)}")
    print(f"Dag-rijen gecheckt: {n_rows_checked}")
    print(f"  - geblokkeerd door marktregime-filter: {n_blocked_by_regime}")
    print(f"  - door alle overige filters + confidence-drempel: {n_passed_filters}")

    if not all_trades:
        print("\nGeen trades gevonden. Probeer --preset aggressive voor een lagere drempel.")
        return

    tdf = pd.DataFrame(all_trades)

    def bootstrap_ci(returns, n_boot=2000, ci=0.90):
        """Bootstrap-onzekerheidsmarge op het gemiddelde rendement: hoeveel
        zou dit gemiddelde kunnen schommelen als we dezelfde trades met
        vervanging opnieuw zouden trekken? Bij weinig trades (zoals hier)
        is deze marge vaak verrassend breed - en dat is precies het punt:
        het laat zien hoeveel vertrouwen 1 los gemiddelde verdient."""
        if len(returns) < 10:
            return None, None
        rng = np.random.default_rng(42)
        returns = np.array(returns)
        means = [rng.choice(returns, size=len(returns), replace=True).mean() for _ in range(n_boot)]
        lo = np.percentile(means, (1 - ci) / 2 * 100)
        hi = np.percentile(means, (1 + ci) / 2 * 100)
        return lo, hi

    def print_summary(sub, label):
        if len(sub) == 0:
            print(f"\n[{label}] geen trades.")
            return
        win_rate = (sub["Rendement_%"] > 0).mean() * 100
        avg_ret = sub["Rendement_%"].mean()
        avg_days = sub["DagenGehouden"].mean()
        print(f"\n[{label}]")
        print(f"  Trades: {len(sub)}  |  Win rate: {win_rate:.1f}%  |  Gem. rendement: {avg_ret:.2f}%  "
              f"|  Gem. dagen gehouden: {avg_days:.1f}")
        print(f"  Beste: {sub['Rendement_%'].max():.2f}%  |  Slechtste: {sub['Rendement_%'].min():.2f}%")
        lo, hi = bootstrap_ci(sub["Rendement_%"].values)
        if lo is not None:
            print(f"  90%-onzekerheidsmarge op gem. rendement: [{lo:.2f}%, {hi:.2f}%] "
                  f"(bij <10 trades wordt dit niet getoond - te onbetrouwbaar)")

    print("\n" + "=" * 60)
    print(f"RESULTATEN - preset '{preset_name}'")
    print("=" * 60)

    # --- marktregime-diagnose: was TEST uberhaupt een vergelijkbare markt? ---
    # Dit helpt onderscheiden tussen 2 heel verschillende problemen:
    # (a) overfitting - de markt was vergelijkbaar, maar de strategie faalt toch
    # (b) regimeverschil - TEST was gewoon een structureel andere/moeilijkere markt
    spy_split_idx = int(len(spy) * TRAIN_TEST_SPLIT)
    spy_train, spy_test = spy.iloc[:spy_split_idx], spy.iloc[spy_split_idx:]

    def regime_stats(s):
        total_ret = (s.iloc[-1] / s.iloc[0] - 1) * 100
        daily_ret = s.pct_change().dropna()
        ann_vol = daily_ret.std() * (252 ** 0.5) * 100
        running_max = s.cummax()
        max_dd = ((s / running_max - 1) * 100).min()
        sma50 = s.rolling(50).mean()
        pct_bullish = (s > sma50).mean() * 100 if len(s) >= 50 else float("nan")
        return total_ret, ann_vol, max_dd, pct_bullish

    tr_ret, tr_vol, tr_dd, tr_bull = regime_stats(spy_train)
    te_ret, te_vol, te_dd, te_bull = regime_stats(spy_test)
    print("\n--- Marktregime TRAIN vs TEST (SPY, los van de strategie zelf) ---")
    print(f"                TRAIN        TEST")
    print(f"SPY-rendement:  {tr_ret:6.1f}%     {te_ret:6.1f}%")
    print(f"Volatiliteit:   {tr_vol:6.1f}%     {te_vol:6.1f}%  (jaarbasis)")
    print(f"Max drawdown:   {tr_dd:6.1f}%     {te_dd:6.1f}%")
    print(f"% dagen bullish:{tr_bull:6.1f}%     {te_bull:6.1f}%  (SPY boven eigen SMA50)")
    if abs(tr_ret - te_ret) > 15 or abs(tr_bull - te_bull) > 20:
        print("-> TRAIN en TEST waren duidelijk VERSCHILLENDE markt-regimes.")
        print("   Een deel van het prestatieverschil kan dus aan de markt liggen, niet (alleen) aan overfitting.")
    else:
        print("-> TRAIN en TEST waren een vergelijkbaar marktregime.")
        print("   Een groot prestatieverschil is dan MINDER te verklaren door de markt,")
        print("   en wijst sterker richting overfitting van de strategie zelf.")

    print_summary(tdf[tdf["Periode"] == "TRAIN"], "TRAIN")
    print_summary(tdf[tdf["Periode"] == "TEST"], "TEST (onafhankelijke check)")

    print("\nPer ticker (hele periode):")
    print(tdf.groupby("Ticker")["Rendement_%"].agg(["count", "mean"]).sort_values("mean", ascending=False).to_string())
    print("\nPer uitkomst-type:")
    print(tdf.groupby("Uitkomst")["Rendement_%"].agg(["count", "mean"]).to_string())

    # --- voorspelt confidence-score de rendementsgrootte? puur analyse, ---
    # --- verandert niets aan de strategie zelf, dus geen extra overfitting-risico ---
    print("\n--- Voorspelt confidence-score het rendement? ---")
    corr = tdf["Confidence"].corr(tdf["Rendement_%"])
    print(f"Correlatie confidence <-> rendement: {corr:.3f}  (range -1 tot +1, 0 = geen verband)")
    bins = [0, 70, 80, 90, 101]
    labels = ["<70", "70-80", "80-90", "90+"]
    tdf["ConfBin"] = pd.cut(tdf["Confidence"], bins=bins, labels=labels, include_lowest=True)
    conf_tab = tdf.groupby("ConfBin", observed=True)["Rendement_%"].agg(["count", "mean"])
    print(conf_tab.to_string())
    if corr > 0.15:
        print("\n-> Zwak-tot-redelijk positief verband: hogere confidence hangt samen met beter rendement.")
        print("   Zou een argument kunnen zijn voor confidence-gewogen positiegrootte.")
    elif corr < -0.15:
        print("\n-> Onverwacht: hogere confidence hangt samen met SLECHTER rendement in deze data.")
        print("   Niet meteen op vertrouwen bij een kleine steekproef per groep - eerst meer data verzamelen.")
    else:
        print("\n-> Geen duidelijk verband gevonden. Op basis van deze data is confidence-gewogen")
        print("   positiegrootte niet te onderbouwen - alle trades boven de drempel gelijk behandelen")
        print("   is dan net zo goed verdedigbaar.")

    # --- welke module voorspelt individueel het rendement? puur analyse, ---
    # --- verandert niets aan de strategie, geen extra overfitting-risico ---
    print("\n--- Welke module voorspelt het rendement individueel? ---")
    module_cols = {
        "trend": "mod_trend", "momentum": "mod_momentum", "volume": "mod_volume",
        "volatility": "mod_volatility", "rs": "mod_rs", "catalyst": "mod_catalyst",
        "structuur": "mod_structuur",
    }
    module_corrs = {}
    for name, col in module_cols.items():
        if col in tdf.columns and tdf[col].std() > 0:
            module_corrs[name] = tdf[col].corr(tdf["Rendement_%"])
    for name, c in sorted(module_corrs.items(), key=lambda x: -x[1]):
        print(f"  {name:12s}: correlatie = {c:+.3f}")
    weak = [n for n, c in module_corrs.items() if abs(c) < 0.05]
    if weak:
        print(f"\n-> Zwakste module(s) (|correlatie| < 0.05): {', '.join(weak)}.")
        print("   Draagt in deze data weinig bij aan het onderscheiden van goede vs. slechte trades.")
        print("   Overweeg het GEWICHT te verlagen i.p.v. nog een module toe te voegen -")
        print("   versimpelen verlaagt overfitting-risico, meer modules verhoogt het.")
    else:
        print("\n-> Geen module met verwaarloosbare correlatie gevonden - alle 6 dragen op zijn")
        print("   minst een beetje bij aan het onderscheid tussen trades in deze data.")

    # ==================================================================
    # DE KERNVRAAG: voegt de SELECTIE waarde toe, of komt alles uit de exits?
    # ==================================================================
    print("\n" + "=" * 62)
    print("BENCHMARK: scanner-selectie versus WILLEKEURIGE instapdagen")
    print("=" * 62)
    print("Zelfde aantal trades, zelfde exits, zelfde kosten - alleen de")
    print("instapmomenten zijn willekeurig gekozen. Draait 20 simulaties...")

    signals_per_ticker = tdf["Ticker"].value_counts().to_dict()
    sim_means = run_random_entry_benchmark(
        prepared_data, fund_cache, signals_per_ticker, preset, n_simulations=20)

    strategie_gem = tdf["Rendement_%"].mean()
    if len(sim_means) >= 5:
        rnd_gem = float(np.mean(sim_means))
        rnd_std = float(np.std(sim_means))
        rnd_lo, rnd_hi = float(np.percentile(sim_means, 5)), float(np.percentile(sim_means, 95))
        print(f"\n  Scanner-selectie:      {strategie_gem:+.2f}% per trade")
        print(f"  Willekeurige entries:  {rnd_gem:+.2f}% per trade "
              f"(spreiding over 20 simulaties: {rnd_lo:+.2f}% tot {rnd_hi:+.2f}%)")
        verschil = strategie_gem - rnd_gem
        z = verschil / rnd_std if rnd_std > 0 else 0
        print(f"  Verschil:              {verschil:+.2f} procentpunt  (z = {z:.2f})")
        print()
        if strategie_gem > rnd_hi:
            print("  -> De scanner presteert BETER dan willekeurig instappen, buiten de")
            print("     spreiding van de simulaties. Dat is een aanwijzing dat de")
            print("     selectiecriteria daadwerkelijk iets toevoegen.")
        elif strategie_gem < rnd_lo:
            print("  -> LET OP: de scanner presteert SLECHTER dan willekeurig instappen.")
            print("     De filters selecteren dan actief ongunstige momenten - dat is een")
            print("     sterker signaal dan een tegenvallend gemiddelde op zichzelf.")
        else:
            print("  -> De scanner is NIET te onderscheiden van willekeurig instappen.")
            print("     Het rendement komt dan vooral uit de exit-logica (trailing stop /")
            print("     partial exit) en marktdrift, niet uit de selectiecriteria.")
            print("     Verder sleutelen aan filters heeft dan weinig zin; de winst zit")
            print("     in het exit-mechanisme en in positiebeheer.")
    else:
        print("\n  Te weinig simulaties gelukt om te vergelijken.")

    # ==================================================================
    # PORTFOLIO-METRICS (wat een hedgefonds als eerste bekijkt)
    # ==================================================================
    metrics = compute_portfolio_metrics(tdf)
    if metrics:
        print("\n" + "=" * 62)
        print("PORTFOLIO-METRICS (i.p.v. alleen per-trade gemiddelden)")
        print("=" * 62)
        print(f"  Totaal rendement over de hele periode: {metrics['total_return']:+.1f}%")
        print(f"  Maximale drawdown (diepste terugval):  {metrics['max_drawdown']:.1f}%")
        print(f"  Profit factor (winst / verlies):       {metrics['profit_factor']:.2f}   "
              f"(>1.0 = winstgevend, >1.5 = solide)")
        print(f"  Sharpe-achtige ratio per trade:        {metrics['sharpe_like']:.2f}   "
              f"(>0.1 is al redelijk voor losse trades)")
        print()
        print("  (vereenvoudigd: gaat uit van 1 positie tegelijk, geen gelijktijdige")
        print("   trades - de echte drawdown kan afwijken als je meerdere posities aanhoudt)")

    vergelijk_met_kopen_en_vasthouden(tdf, spy, prepared_data, metrics)

    print("\nLET OP: historische resultaten zijn geen garantie voor de toekomst.")
    return tdf


if __name__ == "__main__":
    if "--test-trendfilter" in sys.argv or "--test-ema" in sys.argv:
        test_trendfilters()
        sys.exit(0)

    if "--rank-scan" in sys.argv:
        tp = TOP_N_PERCENTIEL
        if "--top" in sys.argv:
            i = sys.argv.index("--top")
            if i + 1 < len(sys.argv):
                tp = int(sys.argv[i + 1])
        scan_gevalideerd(top_pct=tp)
        sys.exit(0)

    if "--ranking" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        vergelijk_ranking_vs_drempels(pn)
        sys.exit(0)

    if "--regime" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        regime_monitor(pn)
        sys.exit(0)

    if "--test-bevestiging" in sys.argv:
        test_bevestiging_filters()
        sys.exit(0)

    if "--test-checklist" in sys.argv:
        test_checklist_filters()
        sys.exit(0)

    if "--test-momentum" in sys.argv:
        test_momentum_methode()
        sys.exit(0)

    if "--test-vix" in sys.argv:
        test_vix_regime()
        sys.exit(0)

    if "--sweep-alles" in sys.argv:
        sweep_alles()
        sys.exit(0)

    if "--test-eendags" in sys.argv:
        test_eendags()
        sys.exit(0)

    if "--test-exits" in sys.argv:
        test_exits()
        sys.exit(0)

    if "--test-totaalscore" in sys.argv:
        test_totaalscore()
        sys.exit(0)

    if "--sweep-pct" in sys.argv:
        sweep_percentiel()
        sys.exit(0)

    if "--portfolio" in sys.argv:
        portfolio_simulatie()
        sys.exit(0)

    if "--walkforward" in sys.argv:
        walk_forward_actueel()
        sys.exit(0)

    if "--walkforward-oud" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        walk_forward_validatie(pn)
        sys.exit(0)

    if "--conf-edge" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        analyse_confidence_edge(pn)
        sys.exit(0)

    if "--sweep-grid" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        sweep_grid(pn)
        sys.exit(0)

    if "--sweep-conf" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        sweep_confidence(pn)
        sys.exit(0)

    if "--sweep-rvol" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        sweep_rvol(pn)
        sys.exit(0)

    if "--sweep" in sys.argv:
        pn = "balanced"
        if "--preset" in sys.argv:
            i = sys.argv.index("--preset")
            if i + 1 < len(sys.argv):
                pn = sys.argv[i + 1]
        sweep_houdperiode(pn)
        sys.exit(0)

    if "--combi" in sys.argv:
        drempel = 55
        if "--min-score" in sys.argv:
            i = sys.argv.index("--min-score")
            if i + 1 < len(sys.argv):
                drempel = int(sys.argv[i + 1])
        scan_combi(min_score=drempel)
        sys.exit(0)

    if "--coiling" in sys.argv:
        drempel = 60
        if "--min-score" in sys.argv:
            i = sys.argv.index("--min-score")
            if i + 1 < len(sys.argv):
                drempel = int(sys.argv[i + 1])
        scan_coiling(min_score=drempel)
        sys.exit(0)

    if "--positions" in sys.argv:
        track_positions()
        sys.exit(0)

    if "--add-position" in sys.argv:
        idx = sys.argv.index("--add-position")
        try:
            ticker, price, shares = sys.argv[idx + 1], sys.argv[idx + 2], sys.argv[idx + 3]
            add_position(ticker.upper(), float(price), int(shares))
        except (IndexError, ValueError):
            print("Gebruik: python swing_scanner.py --add-position TICKER PRIJS AANTAL")
            print("Bijvoorbeeld: python swing_scanner.py --add-position SOUN 12.50 78")
        sys.exit(0)

    preset_name = "balanced"
    if "--preset" in sys.argv:
        idx = sys.argv.index("--preset")
        if idx + 1 < len(sys.argv):
            preset_name = sys.argv[idx + 1]
    if preset_name not in PRESETS:
        print(f"Onbekende preset '{preset_name}', gebruik: elite, conservative, balanced, meer, aggressive, of explosive")
        sys.exit(1)

    if "--backtest" in sys.argv:
        regime_override = True if "--regime-filter" in sys.argv else None
        backtest(preset_name, regime_filter_override=regime_override)
    else:
        scan_today(preset_name)
