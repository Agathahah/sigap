"""Champion vs challenger on months the model never saw, plus a sensitivity table.

Champion   = today's rules (configs/rules.yaml) as a two-band policy: any rule hit -> review, else approve.
Challenger = the gate-passed model (models/current) with approve / review / decline bands whose thresholds are
             chosen on month 5 by cost under the review team's capacity and the automatic-decline guardrail
             (configs/business.yaml). The same model without the guardrail is shown as a reference arm.
Both are replayed on months 6-7. In a real bank this would be a live split (for example 90/10 of traffic for a
few weeks); here it is an offline replay, and the memo says so.

Sensitivity: every uncertain assumption is moved to its low and high value; the thresholds are re-chosen on
month 5 and both arms replayed again. If the recommendation flips under a plausible value, that goes in the memo.

Run:  make policy   -> reports/policy/champion_challenger_<variant>.csv, sensitivity_<variant>.csv,
                       <variant>_policy.json (also copied to models/current/policy.json for the API)
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from sigap import config
from sigap.policy.cost import APPROVE, REVIEW, cost_of_decisions, decide, optimize_policy

COST_KEYS = ("fraud_loss", "review_cost", "review_catch_rate", "good_decline_cost", "good_review_cost")


def compare_arms(y: np.ndarray, arms: dict[str, np.ndarray], costs: dict[str, float]) -> pd.DataFrame:
    """One row per arm (cost_of_decisions + "arm" first) and saving_vs_first = first arm's cost - this arm's."""
    rows = [{"arm": name, **cost_of_decisions(y, d, costs)} for name, d in arms.items()]
    df = pd.DataFrame(rows)
    df["saving_vs_first"] = df["total_cost"].iloc[0] - df["total_cost"]
    return df


def decline_cap(biz: dict) -> float | None:
    value = biz.get("max_decline_rate")
    return None if value is None else float(value)


def load_business() -> tuple[dict[str, float], float, dict]:
    biz = config.load_yaml("business")
    missing = [k for k in COST_KEYS if biz.get("costs", {}).get(k) is None] + (
        ["max_review_rate"] if biz.get("max_review_rate") is None else []
    )
    if missing:
        raise SystemExit(f"configs/business.yaml has no value for: {', '.join(missing)}")
    return {k: float(biz["costs"][k]) for k in COST_KEYS}, float(biz["max_review_rate"]), biz


def load_replay_data(slug: str) -> pd.DataFrame:
    """Months 5-7: calibrated score from models/current, label, age group and the champion's rule hit."""
    from sigap.rules.engine import apply_rules, load_rules, load_silver_with_labels
    from sigap.train.model import load_model

    model = load_model(config.MODELS / "current")
    months = (*config.VALID_MONTHS, *config.TEST_MONTHS)
    gold = config.GOLD / slug
    feats = pd.read_parquet(gold / "features.parquet")
    feats = feats[feats[config.MONTH].isin(months)].reset_index(drop=True)
    silver = load_silver_with_labels(slug)
    silver = silver[silver[config.MONTH].isin(months)]
    hits = apply_rules(silver, load_rules())["any_rule"]
    silver = silver.assign(rule_hit=hits.to_numpy())[[config.ID, config.LABEL, "rule_hit"]]
    df = feats[[config.ID, config.MONTH, "customer_age"]].merge(silver, on=config.ID, validate="one_to_one")
    df["score"] = model.score(feats.set_index(feats[config.ID]).loc[df[config.ID]].reset_index(drop=True))
    df.attrs["model_version"] = model.version
    return df


def arms_for(test: pd.DataFrame, policy: dict, uncapped: dict | None = None) -> dict[str, np.ndarray]:
    arms = {
        "champion_rules": np.where(test["rule_hit"], REVIEW, APPROVE),
        "challenger_model": decide(test["score"].to_numpy(), policy["t_review"], policy["t_decline"]),
    }
    if uncapped is not None:
        arms["challenger_no_decline_cap"] = decide(
            test["score"].to_numpy(), uncapped["t_review"], uncapped["t_decline"]
        )
    arms["approve_all"] = np.full(len(test), APPROVE)
    return arms


def per_10k(value: float, n: float) -> float:
    return value / n * 10_000 if n else 0.0


def sensitivity(
    valid: pd.DataFrame, test: pd.DataFrame, costs: dict, max_rate: float, ranges: dict, cap: float | None
) -> pd.DataFrame:
    rows = []
    for key, values in ranges.items():
        for label, value in zip(("low", "high"), values, strict=True):
            c, rate, dcap = dict(costs), max_rate, cap
            if key == "max_review_rate":
                rate = float(value)
            elif key == "max_decline_rate":
                dcap = float(value)
            else:
                c[key] = float(value)
            pol = optimize_policy(
                valid[config.LABEL].to_numpy(), valid["score"].to_numpy(), c, rate, max_decline_rate=dcap
            )
            cmp = compare_arms(test[config.LABEL].to_numpy(), arms_for(test, pol), c).set_index("arm")
            ch, champ = cmp.loc["challenger_model"], cmp.loc["champion_rules"]
            rows.append(
                {
                    "assumption": key,
                    "case": label,
                    "value": value,
                    "t_review": pol["t_review"],
                    "t_decline": pol["t_decline"],
                    "review_rate": ch["review_rate"],
                    "decline_rate": ch["decline"] / ch["n"],
                    "fraud_stopped_rate": ch["fraud_stopped_rate"],
                    "genuine_declined_per_10k": per_10k(ch["good_declined"], ch["n"]),
                    "challenger_cost_per_10k": per_10k(ch["total_cost"], ch["n"]),
                    "champion_cost_per_10k": per_10k(champ["total_cost"], champ["n"]),
                    "saving_per_10k": per_10k(champ["total_cost"] - ch["total_cost"], ch["n"]),
                    "challenger_cheaper": bool(ch["total_cost"] < champ["total_cost"]),
                }
            )
    return pd.DataFrame(rows)


def friction_by_age(test: pd.DataFrame, decisions: np.ndarray) -> dict[str, float]:
    """Share of GENUINE applicants not approved straight away, per age group."""
    good = test[config.LABEL].to_numpy() == 0
    old = test["customer_age"].to_numpy() >= 50
    held = decisions != APPROVE
    return {"<50": float(held[good & ~old].mean()), ">=50": float(held[good & old].mean())}


def main() -> None:
    slug = config.VARIANT.lower().replace(" ", "_")
    costs, max_rate, biz = load_business()
    df = load_replay_data(slug)
    valid = df[df[config.MONTH].isin(config.VALID_MONTHS)]
    test = df[df[config.MONTH].isin(config.TEST_MONTHS)].reset_index(drop=True)

    cap = decline_cap(biz)
    yv, pv = valid[config.LABEL].to_numpy(), valid["score"].to_numpy()
    policy = optimize_policy(yv, pv, costs, max_rate, max_decline_rate=cap)
    uncapped = optimize_policy(yv, pv, costs, max_rate) if cap is not None else None
    arms = arms_for(test, policy, uncapped)
    table = compare_arms(test[config.LABEL].to_numpy(), arms, costs)
    per_day = float(biz.get("applications_per_day") or 0)
    per_analyst = float(biz.get("reviews_per_analyst_per_day") or 0)
    table["over_capacity"] = table["review_rate"] > max_rate
    table["analysts_needed"] = np.ceil(table["review_rate"] * per_day / per_analyst) if per_analyst else np.nan
    table["cost_per_10k"] = table["total_cost"] / table["n"] * 10_000
    table["saving_per_day"] = table["saving_vs_first"] / table["n"] * per_day

    sens = sensitivity(valid, test, costs, max_rate, biz.get("sensitivity", {}), cap)
    out = config.REPORTS / "policy"
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / f"champion_challenger_{slug}.csv", index=False)
    sens.to_csv(out / f"sensitivity_{slug}.csv", index=False)
    pol = {
        "t_review": policy["t_review"],
        "t_decline": None if np.isinf(policy["t_decline"]) else policy["t_decline"],
        "chosen_on": f"month {config.VALID_MONTHS[0]}",
        "max_review_rate": max_rate,
        "max_decline_rate": cap,
        "costs": costs,
        "model_version": df.attrs["model_version"],
    }
    (out / f"{slug}_policy.json").write_text(json.dumps(pol, indent=2), encoding="utf-8")
    (config.MODELS / "current" / "policy.json").write_text(json.dumps(pol, indent=2), encoding="utf-8")

    rp = lambda v: f"Rp {v / 1e6:,.1f} jt"  # noqa: E731
    td = "never" if np.isinf(policy["t_decline"]) else f"{policy['t_decline']:.4f}"
    cap_txt = "no limit" if cap is None else f"at most {cap:.1%} declined automatically"
    print(f"model {df.attrs['model_version']}; capacity {max_rate:.0%} reviewed per day; {cap_txt}")
    print(f"\nbands chosen on month 5: review if score >= {policy['t_review']:.4f}, decline if score >= {td}")
    print(
        f"  month 5: review {policy['review_rate']:.2%}, decline {policy['decline'] / policy['n']:.2%}, "
        f"fraud stopped {policy['fraud_stopped_rate']:.1%}"
    )
    print(f"\nreplay on months 6-7 ({len(test):,} applications, fraud {test[config.LABEL].mean():.2%}):")
    show = pd.DataFrame(
        {
            "arm": table["arm"],
            "review_%": (100 * table["review_rate"]).round(2),
            "decline_%": (100 * table["decline"] / table["n"]).round(2),
            "fraud_stopped_%": (100 * table["fraud_stopped_rate"]).round(1),
            "genuine_declined_per_10k": (table["good_declined"] / table["n"] * 10_000).round(0),
            "cost_per_10k": table["cost_per_10k"].map(rp),
            "saving_per_day": table["saving_per_day"].map(rp),
            "analysts": table["analysts_needed"],
            "over_capacity": table["over_capacity"],
        }
    )
    print(show.to_string(index=False))
    ch = table.set_index("arm").loc["challenger_model"]
    print(
        f"\ncost split, challenger per 10k: fraud loss {rp(per_10k(ch['fraud_loss_cost'], ch['n']))}, "
        f"reviews {rp(per_10k(ch['review_ops_cost'], ch['n']))}, friction {rp(per_10k(ch['friction_cost'], ch['n']))}"
    )
    for arm in [a for a in arms if a != "approve_all"]:
        f = friction_by_age(test, arms[arm])
        print(f"genuine applicants held (review or decline), {arm}: <50 {f['<50']:.2%}, 50+ {f['>=50']:.2%}")

    print("\nsensitivity (thresholds re-chosen on month 5, replayed on months 6-7):")
    s = sens.assign(
        review_pct=(100 * sens["review_rate"]).round(2),
        decline_pct=(100 * sens["decline_rate"]).round(2),
        stopped_pct=(100 * sens["fraud_stopped_rate"]).round(1),
        genuine_declined=sens["genuine_declined_per_10k"].round(0),
        saving=sens["saving_per_10k"].map(rp),
    )[
        [
            "assumption",
            "case",
            "value",
            "review_pct",
            "decline_pct",
            "genuine_declined",
            "stopped_pct",
            "saving",
            "challenger_cheaper",
        ]
    ]
    print(s.to_string(index=False))
    flips = sens.loc[~sens["challenger_cheaper"], ["assumption", "case"]].to_records(index=False).tolist()
    print("\nrecommendation flips under: " + (", ".join(f"{a} {c}" for a, c in flips) if flips else "none"))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
