"""Settlement gates shared by review writes, matching and evaluation."""


def payout_issues(review):
    if review is None:
        return ("settlement_payouts_unreviewed",)
    issues = []
    for scenario in review.scenarios:
        if scenario.left_no is None or scenario.right_no is None:
            issues.append(f"explicit_settlement_payouts_required:{scenario.name}")
        elif (
            scenario.left_yes + scenario.left_no != 1 or scenario.right_yes + scenario.right_no != 1
        ):
            # Check again at the execution boundary, including models assembled
            # internally with model_copy (which does not validate updates).
            issues.append(f"unsupported_noncomplementary_payouts:{scenario.name}")
    return tuple(issues)


def settlement_issues(review, left, right):
    issues = list(payout_issues(review))
    if review is None:
        return tuple(issues)
    scenarios = {scenario.name: scenario for scenario in review.scenarios}
    mappings = {}
    for mapping in review.settlement_mappings:
        key = mapping.side, mapping.policy, mapping.condition_id
        if key in mappings:
            issues.append("duplicate_settlement_mapping:" + ":".join(key))
        mappings[key] = mapping
    required = set()
    for side, definition in (("left", left), ("right", right)):
        policies = {p.kind: p for p in definition.settlement_policies or ()} if definition else {}
        for kind in ("cancellation", "fallback", "ambiguous_resolution"):
            policy = policies.get(kind)
            if policy is None or policy.status == "unknown":
                issues.append(f"{side}:settlement_policy_unmodeled:{kind}")
                continue
            for condition in policy.conditions:
                key = side, kind, condition.id
                required.add(key)
                mapping = mappings.get(key)
                if mapping is None:
                    issues.append("settlement_condition_uncovered:" + ":".join(key))
                    continue
                for name in mapping.scenarios:
                    scenario = scenarios.get(name)
                    if scenario is None:
                        issues.append(f"settlement_scenario_missing:{name}")
                    elif (
                        getattr(scenario, f"{side}_yes") != condition.yes_payout
                        or getattr(scenario, f"{side}_no") != condition.no_payout
                    ):
                        issues.append(f"settlement_condition_payout_mismatch:{side}:{kind}:{name}")
    for key in sorted(mappings.keys() - required):
        issues.append("settlement_condition_unknown:" + ":".join(key))
    return tuple(issues)
