"""Entirely fictional data, never an ejobplan schema or a policy reference."""

import numpy as np
import pandas as pd

from jobplan_poc.features import extract_features


DEFAULT_SEED = 42
REFERENCE_DATE = pd.Timestamp("2026-02-01")
TEST_START = pd.Timestamp("2025-09-01")
LABEL_HORIZON_DAYS = 30
SPECIALTIES = ("General medicine", "Surgery", "Psychiatry", "Radiology")
STAGES = ("Draft", "Awaiting review", "Returned for clarification")


def generate_plans(n: int = 800, seed: int = DEFAULT_SEED, missing_rate: float = 0.04) -> pd.DataFrame:
    if isinstance(n, bool) or not isinstance(n, int) or n < 2:
        raise ValueError("n must be an integer of at least 2.")
    if not 0 <= missing_rate <= 1:
        raise ValueError("missing_rate must be between 0 and 1.")
    rng = np.random.default_rng(seed)
    snapshots = pd.date_range("2024-01-01", "2025-12-31", periods=n).normalize()
    records = []
    for index, snapshot in enumerate(snapshots):
        specialty_index = int(rng.integers(len(SPECIALTIES)))
        previous_wte = float(rng.choice([0.5, 0.6, 0.8, 1.0]))
        current_wte = previous_wte if rng.random() < 0.85 else float(rng.choice([0.5, 0.6, 0.8, 1.0]))
        previous_total = float(np.clip(rng.normal(10, 1.2), 6, 14) * previous_wte)
        normalised_change = rng.normal(0, 1.2) + (rng.normal(0, 2.4) if rng.random() < 0.2 else 0)
        current_total = float(max(4, previous_total / previous_wte + normalised_change) * current_wte)
        previous_direct_mix = float(np.clip(rng.normal([0.72, 0.78, 0.65, 0.8][specialty_index], 0.06), 0.45, 0.9))
        current_direct_mix = float(np.clip(previous_direct_mix + rng.normal(0, 0.07), 0.35, 0.95))
        record = {
            "plan_id": f"FIC-{index + 1:05d}",
            "entity_id": f"PERSON-{index + 1:05d}",
            "specialty": SPECIALTIES[specialty_index],
            "working_pattern": "Full-time" if current_wte == 1 else "Less than full-time",
            "workflow_stage": str(rng.choice(STAGES)),
            "snapshot_date": snapshot,
            "workflow_started_date": snapshot - pd.Timedelta(int(min(rng.gamma(2, 32), 240)), unit="D"),
            "review_due_date": snapshot + pd.Timedelta(int(rng.integers(-100, 121)), unit="D"),
            "current_wte": current_wte,
            "previous_wte": previous_wte,
            "completeness_percent": float(np.round(np.clip(100 - rng.gamma(1.3, 9), 25, 100), 1)),
        }
        for prefix, total, mix in [
            ("current", current_total, current_direct_mix),
            ("previous", previous_total, previous_direct_mix),
        ]:
            total = round(total, 2)
            direct = round(total * mix, 2)
            supporting = round((total - direct) * 0.8, 2)
            record.update({
                f"{prefix}_total_pa": total,
                f"{prefix}_direct_care_pa": direct,
                f"{prefix}_supporting_pa": supporting,
                f"{prefix}_other_pa": round(total - direct - supporting, 2),
            })
        result = extract_features(record)
        if result.values is None:
            raise RuntimeError(f"Generator produced invalid complete input: {result.errors}")
        features = result.values
        # Latent context and a Bernoulli draw make this distinct from baseline threshold labels.
        latent_context = rng.normal(0, 0.8)
        logit = (
            -2.4
            + 0.35 * features["activity_change_per_wte"]
            + 0.018 * features["direct_care_mix_change_pp"]
            + 0.005 * features["workflow_age_days"]
            + 0.012 * features["overdue_days"]
            + 0.025 * features["incompleteness_percent"]
            + latent_context
        )
        record["material_amendment"] = int(rng.random() < 1 / (1 + np.exp(-logit)))
        record["outcome_observed_date"] = snapshot + pd.Timedelta(LABEL_HORIZON_DAYS, unit="D")
        records.append(record)
    frame = pd.DataFrame(records)
    # Missingness is applied after label generation so changing it does not change the target.
    missing_rows = rng.random(n) < missing_rate
    frame.loc[missing_rows, "previous_total_pa"] = np.nan
    return frame
