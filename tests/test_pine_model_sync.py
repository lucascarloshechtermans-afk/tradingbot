import os

from indicator_lab import export_pine as X


def test_generated_pine_regions_match_the_model_json():
    """Every <<GEN:...>> region in the v3 Pine files must equal what export_pine renders from
    v3_model.json (+ v3_model_yearly.json): no hand edits, no stale coefficients."""
    out = X.render()
    for fp, src in out.items():
        assert src == X._read(fp), f"{os.path.basename(fp)} is out of sync: run python -m indicator_lab.export_pine --render"


def test_parity_features_match_training_features_for_us_tickers():
    """Step 1 of the reliability round: Pine-side feature definitions (fixed) vs meta.feature_frame."""
    import pytest

    from indicator_lab import data
    from indicator_lab import pine_parity as PP
    if not all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in ("AAPL", "JPM", "SPY")):
        pytest.skip("no cached market data (e.g. CI without network)")
    d = PP.compare("fixed", n_dates=5, tickers=["AAPL", "JPM"])
    feats = [c for c in d.columns if c not in ("ticker", "date", "score", "quality")]
    assert d[feats].max().max() < 0.05


def test_generated_model_expressions_equal_the_json_fits():
    """Evaluate the generated Pine score expressions (final + one per walk-forward year) in Python with
    random feature values and compare with the logistic score computed straight from the JSON."""
    import numpy as np
    final, yearly = X._load()
    lines = X.model_block(final, yearly).splitlines()
    rng = np.random.default_rng(3)
    # realistic feature values (|z| of a few units), so 6-decimal rounding in the Pine code stays negligible
    vals = {X.VAR[f]: mu + sd * rng.normal() for f, mu, sd in zip(final["feats"], final["mu"], final["sd"])}
    env = {**vals, "f_z": lambda x, mu, sd: (x - mu) / sd}

    def ref(fit):
        return fit["b"] + sum(w * (vals[X.VAR[f]] - mu) / sd
                              for f, mu, sd, w in zip(final["feats"], fit["mu"], fit["sd"], fit["w"]) if w != 0)

    is_line = next(ln for ln in lines if ln.startswith("scoreIs = "))
    assert abs(eval(is_line.split("=", 1)[1], {}, env) - ref(final)) < 1e-4
    if yearly:
        arms = {int(ln.split("=>")[0]): ln.split("=>", 1)[1] for ln in lines
                if ln.startswith("    20") and "f_z(" in ln}
        assert sorted(arms) == [f["year"] for f in yearly["fits"]]
        for fit in yearly["fits"]:
            assert abs(eval(arms[fit["year"]], {}, env) - ref(fit)) < 1e-4, fit["year"]
