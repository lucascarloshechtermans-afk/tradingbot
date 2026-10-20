"""Reproduce any PROGRESS.md row:

    python -m indicator_lab.run donchian_breakout '{"n": 20, "m": 20, "trail": 4.0}'
    python -m indicator_lab.run bh
    python -m indicator_lab.run best            # current best version, with robustness
"""
from __future__ import annotations

import json
import sys

from indicator_lab import evaluate as E
from indicator_lab import strategies as S


def main(argv: list[str]) -> None:
    name = argv[0] if argv else "best"
    if name == "bh":
        E.bh_report()
        return
    if name == "best":
        fn, params, keys = S.BEST
        E.report(f"BEST={fn.__name__}", fn, params)
        print(E.robustness(fn, params, keys).to_string(index=False))
        return
    params = json.loads(argv[1]) if len(argv) > 1 else {}
    E.report(name, getattr(S, name), params)


if __name__ == "__main__":
    main(sys.argv[1:])
