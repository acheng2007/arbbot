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
    issues.extend(joint_settlement_issues(review, left, right))
    return tuple(issues)


def joint_settlement_issues(review, left, right):
    """Independent exceptional conditions need modeled joint payouts or exclusions."""
    issues = []
    states, policies = {}, {}
    for side, definition in (("left", left), ("right", right)):
        states[side] = {"normal_yes": (1, 0), "normal_no": (0, 1)}
        policies[side] = (
            {p.kind: p for p in definition.settlement_policies or ()} if definition else {}
        )
        for policy in policies[side].values():
            if policy.status == "modeled":
                for condition in policy.conditions:
                    states[side][f"{policy.kind}:{condition.id}"] = (
                        condition.yes_payout,
                        condition.no_payout,
                    )
    required = {(a, b) for a in states["left"] for b in states["right"] if ":" in a or ":" in b}
    cases = {}
    for case in review.joint_settlement_cases:
        key = case.left_state, case.right_state
        if key in cases:
            issues.append("duplicate_joint_settlement_case:" + ":".join(key))
        cases[key] = case
    scenarios = {scenario.name: scenario for scenario in review.scenarios}
    for key in sorted(required):
        case = cases.get(key)
        if case is None:
            issues.append("joint_settlement_case_uncovered:" + ":".join(key))
            continue
        if (case.scenario is None) == (case.exclusion_reason is None):
            issues.append("joint_settlement_case_ambiguous:" + ":".join(key))
            continue
        if case.scenario:
            scenario = scenarios.get(case.scenario)
            if (
                scenario is None
                or (scenario.left_yes, scenario.left_no) != states["left"][key[0]]
                or (scenario.right_yes, scenario.right_no) != states["right"][key[1]]
            ):
                issues.append("joint_settlement_payout_mismatch:" + ":".join(key))
        elif case.exclusion_reason:
            for side in ("left", "right"):
                cited = getattr(case, side + "_evidence_policies")
                needed = {state.split(":", 1)[0] for state in key if ":" in state}
                if not needed.issubset(cited):
                    issues.append("joint_exclusion_evidence_missing:" + side)
                for name in cited:
                    policy = policies[side].get(name)
                    if (
                        policy is None
                        or policy.status == "unknown"
                        or policy.evidence.source == "title"
                    ):
                        issues.append(f"joint_exclusion_evidence_invalid:{side}:{name}")
        else:
            issues.append("joint_settlement_case_unmodeled:" + ":".join(key))
    for key in sorted(cases.keys() - required):
        issues.append("joint_settlement_case_unknown:" + ":".join(key))
    return tuple(issues)
