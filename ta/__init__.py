"""Technical-analysis engine (price, volume and volatility only).

Modules are small and independently testable; `ta.engine.analyze()` combines
them into one explainable `TechnicalReport` per ticker. No module here does
risk management, position sizing or portfolio logic.

Look-ahead rule used everywhere: a function given a frame uses only the rows
in that frame, and a swing point only counts from the bar on which it became
knowable (`Swing.known_at`), never from the bar it occurred on.
"""
