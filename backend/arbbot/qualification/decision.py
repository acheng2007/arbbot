"""Pure qualification and conservative cross-product settlement construction."""

from itertools import product

from arbbot.domain import (
    CostPolicy,
    JointSettlementCase,
    Scenario,
    SettlementMapping,
    SettlementModel,
)
from arbbot.matching.contracts import compare_contracts
from arbbot.matching.settlement import settlement_issues


def decide(left, right, evidence, expires_at):
    a, b = evidence
    comparison = compare_contracts(left, right, a.definition, b.definition)
    reasons = [*a.blocked_reasons, *b.blocked_reasons, *comparison.issues]
    reasons.extend(
        f"contract_field_{d.status}:{d.field}"
        for d in comparison.differences
        if d.status != "equal"
    )
    for side, contract in (("left", a.definition), ("right", b.definition)):
        policies = {p.kind: p for p in contract.settlement_policies or ()}
        for kind in ("cancellation", "fallback", "ambiguous_resolution"):
            if kind not in policies or policies[kind].status == "unknown":
                reasons.append(f"{side}:unmodeled_policy:{kind}")
    left_policies = {p.kind: p for p in a.definition.settlement_policies or ()}
    right_policies = {p.kind: p for p in b.definition.settlement_policies or ()}
    policy_conflict = False
    for kind in sorted(left_policies.keys() & right_policies.keys()):
        left_policy, right_policy = left_policies[kind], right_policies[kind]
        if left_policy.model_dump(exclude={"evidence"}) != right_policy.model_dump(
            exclude={"evidence"}
        ):
            reasons.append("settlement_policy_different:" + kind)
            policy_conflict = True
    if reasons:
        status = (
            "incompatible"
            if comparison.status == "conflict"
            or policy_conflict
            or any(reason.startswith("document_event_contradiction:") for reason in reasons)
            else "incomplete"
        )
        return status, tuple(sorted(set(reasons))), comparison, None
    states = []
    for contract in (a.definition, b.definition):
        choices = {"normal_yes": (1, 0), "normal_no": (0, 1)}
        for policy in contract.settlement_policies:
            for condition in policy.conditions:
                choices[f"{policy.kind}:{condition.id}"] = (
                    condition.yes_payout,
                    condition.no_payout,
                )
        states.append(choices)
    scenarios = [
        Scenario(name="normal_yes", left_yes=1, left_no=0, right_yes=1, right_no=0),
        Scenario(name="normal_no", left_yes=0, left_no=1, right_yes=0, right_no=1),
    ]
    # No correlation between exceptional triggers is assumed, even if the two
    # policies use identical words. All mixed ordinary/exceptional states remain.
    cases, mappings = [], {}
    for x, y in product(*states):
        if ":" not in x and ":" not in y:
            continue
        name = f"joint_{len(cases)}"
        scenarios.append(
            Scenario(
                name=name,
                left_yes=states[0][x][0],
                left_no=states[0][x][1],
                right_yes=states[1][y][0],
                right_no=states[1][y][1],
            )
        )
        cases.append(JointSettlementCase(left_state=x, right_state=y, scenario=name))
        for side, state in (("left", x), ("right", y)):
            if ":" in state:
                policy, condition = state.split(":", 1)
                mappings.setdefault((side, policy, condition), []).append(name)
    costs = CostPolicy(
        fee_per_contract=0,
        fixed_fee=0,
        min_order_size=1,
        min_notional=0,
        cost_fx=1,
        payout_fx=1,
        evidence="USD unit payout; execution fees are required separately from public providers.",
    )
    model = SettlementModel(
        left_id=left.id,
        right_id=right.id,
        left_terms_hash=left.terms_hash,
        right_terms_hash=right.terms_hash,
        left_definition_hash=comparison.left_hash,
        right_definition_hash=comparison.right_hash,
        expires_at=expires_at,
        scenarios=tuple(scenarios),
        joint_settlement_cases=tuple(cases),
        settlement_mappings=tuple(
            SettlementMapping(side=s, policy=p, condition_id=c, scenarios=tuple(names))
            for (s, p, c), names in mappings.items()
        ),
        left_costs=costs,
        right_costs=costs,
    )
    issues = settlement_issues(model, a.definition, b.definition)
    return (
        ("incomplete", issues, comparison, None) if issues else ("qualified", (), comparison, model)
    )
