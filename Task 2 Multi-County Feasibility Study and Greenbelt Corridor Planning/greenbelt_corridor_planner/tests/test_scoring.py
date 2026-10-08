import numpy as np
import pandas as pd

from seeds_cds import scoring
from seeds_cds.gee_layers import auc


def test_normalize_range_and_direction():
    raw = pd.DataFrame({"forest": [0.1, 0.5, 0.9], "dist_road": [10.0, 1.0, 0.1], "arc_need": [1, 0.4, 0.1],
                        "dist_trail": [5.0, 1.0, 0.0]})
    n = scoring.normalize(raw)
    assert np.allclose(n["forest_cover"], [0.0, 0.5, 1.0])
    assert np.allclose(n["road_proximity"], [0.0, 0.5, 1.0])   # closer = higher
    assert np.allclose(n["trail_proximity"], [0.0, 0.5, 1.0])
    assert n["arc_need"].tolist() == [1, 0.4, 0.1]              # absolute, not ranked


def test_composite_signed_minmax():
    norm = pd.DataFrame({"a": [0.0, 1.0, 0.5], "b": [1.0, 0.0, 0.5]})
    p = scoring.composite(norm, {"a": 1, "b": -1})
    assert p.tolist() == [0.0, 1.0, 0.5]


def test_auc():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([0, 1], [0.5, 0.5]) == 0.5
