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
