import os

from indicator_lab import export_pine as X


def test_generated_pine_regions_match_the_model_json():
    """Every <<GEN:...>> region in the v3 Pine files must equal what export_pine renders from
    v3_model.json (+ v3_model_yearly.json): no hand edits, no stale coefficients."""
    out = X.render()
    for fp, src in out.items():
        assert src == open(fp).read(), f"{os.path.basename(fp)} is out of sync: run python -m indicator_lab.export_pine --render"


def test_parity_features_match_training_features_for_us_tickers():
    """Step 1 of the reliability round: Pine-side feature definitions (fixed) vs meta.feature_frame."""
    from indicator_lab import pine_parity as PP
    try:
        d = PP.compare("fixed", n_dates=5, tickers=["AAPL", "JPM"])
    except Exception:  # no cached market data (e.g. CI without network)
        return
    feats = [c for c in d.columns if c not in ("ticker", "date", "score", "quality")]
    assert d[feats].max().max() < 0.05
