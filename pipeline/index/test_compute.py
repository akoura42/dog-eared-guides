"""Golden-file tests for every band edge in the Dog-Eared Index (spec §7.1).

Run directly (python pipeline/index/test_compute.py) or via pytest.
"""

from compute import COMPONENTS, band_score, compute_composite

BY_KEY = {c["key"]: c for c in COMPONENTS}

# component -> [(value, expected score)] covering both sides of every edge.
GOLDEN = {
    "patio_share": [
        (0.50, 100), (0.4999, 80), (0.35, 80), (0.3499, 60), (0.25, 60),
        (0.2499, 40), (0.15, 40), (0.1499, 20), (0.05, 20), (0.0499, 0), (0.0, 0),
    ],
    "indoor_welcome": [
        (0.25, 100), (0.2499, 75), (0.15, 75), (0.1499, 50), (0.08, 50),
        (0.0799, 25), (0.03, 25), (0.0299, 0),
    ],
    "lodging_share": [
        (0.60, 100), (0.5999, 80), (0.45, 80), (0.4499, 60), (0.30, 60),
        (0.2999, 40), (0.15, 40), (0.1499, 20), (0.05, 20), (0.0499, 0),
    ],
    "trail_access": [
        (100, 100), (99.9, 85), (50, 85), (49.9, 70), (25, 70), (24.9, 50),
        (10, 50), (9.9, 30), (3, 30), (2.9, 15), (1, 15), (0.9, 0),
    ],
    "emergency_vet": [
        (15, 100), (16, 80), (30, 80), (31, 60), (45, 60), (46, 40),
        (60, 40), (61, 20), (90, 20), (91, 0),
    ],
    "heat_risk": [
        (5, 100), (6, 85), (15, 85), (16, 70), (30, 70), (31, 50),
        (60, 50), (61, 30), (100, 30), (101, 10),
    ],
    "water_access": [
        ("three-plus-yearround", 100), ("three-seasonal-or-two-yearround", 80),
        ("two-seasonal-or-one-yearround", 60), ("one-seasonal", 40),
        ("wading-only", 20), ("none", 0),
    ],
    "off_leash": [
        ("twenty-acres-or-beach", 100), ("five-to-twenty-acres", 75),
        ("one-to-five-acres", 50), ("fenced-run", 25), ("none", 0),
    ],
    "ordinance": [
        ([], 50),
        (["patio-permitted"], 70),
        (["patio-permitted", "voice-control-areas", "shoreline-open"], 100),
        # cap at 100 even though 50+20+15+15 = 100 exactly; add none beyond
        (["shoreline-yearround-ban"], 25),
        (["bsl"], 10),
        (["bsl", "shoreline-yearround-ban"], 0),  # floor at 0 (would be -15)
        (["patio-permitted", "shoreline-seasonal-ban"], 60),
    ],
}


def test_band_edges():
    for key, cases in GOLDEN.items():
        comp = BY_KEY[key]
        for value, expected in cases:
            got = band_score(comp, value)
            assert got == expected, f"{key}({value!r}) = {got}, expected {expected}"


def test_missing_is_missing():
    for comp in COMPONENTS:
        assert band_score(comp, None) is None


def test_publish_gate_and_renormalization():
    keys = [c["key"] for c in COMPONENTS]

    # 6 verified: no composite.
    scores = {k: (100 if i < 6 else None) for i, k in enumerate(keys)}
    c = compute_composite(scores)
    assert c["score"] is None and c["components_verified"] == 6

    # 7 verified: provisional, renormalized over available weights.
    scores = {k: (100 if i < 7 else None) for i, k in enumerate(keys)}
    c = compute_composite(scores)
    assert c["score"] == 100 and c["provisional"] is True

    # 9 verified, all 100: exactly 100, not provisional.
    scores = {k: 100 for k in keys}
    c = compute_composite(scores)
    assert c["score"] == 100 and c["provisional"] is False

    # Weighted mix: patio 100 (15), everything else 0 -> 15/100.
    scores = {k: 0 for k in keys}
    scores["patio_share"] = 100
    assert compute_composite(scores)["score"] == 15


if __name__ == "__main__":
    test_band_edges()
    test_missing_is_missing()
    test_publish_gate_and_renormalization()
    n = sum(len(v) for v in GOLDEN.values())
    print(f"ok — {n} band-edge cases + gate/renormalization checks passed")
