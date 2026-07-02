# Propagation bounds
MAX_HOPS: int = 3
HOP_DECAY: float = 0.7  # contribution multiplied by this per hop
EPSILON: float = 0.01  # stop expanding when the contribution is below this

# Transmission multipliers (would be learned from historical data)
STATIC_EDGE_WEIGHTS: dict[str, float] = {
    "subsidiary_of": 0.9,
    "ceo_of": 0.85,
    "owns": 0.9,
    "supplies_to": 0.6,
    "affiliated_with": 0.5,
    "located_in": 0.1,
    "attended_event_with": 0.05,
}


def transmission_factor(edge_type: str) -> tuple[float, str]:
    weight = STATIC_EDGE_WEIGHTS.get(edge_type, 0.1)
    return weight, edge_type


# Score threshold to risk band
RISK_BANDS: list[tuple[float, str]] = [
    (0.34, "low"),
    (0.67, "medium"),
    (1.01, "high"),
]


def risk_band(score: float) -> str:
    """Map a 0–1 risk score to low / medium / high."""
    for threshold, band in RISK_BANDS:
        if score < threshold:
            return band
    return "high"


BAND_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

# Alert when risk crosses into medium or higher
ALERT_MIN_BAND_RANK: int = 1
