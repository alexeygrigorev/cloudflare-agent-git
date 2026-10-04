"""Read-only aggregate cost evidence and fail-closed optional-cloud admission.
No billing changes or service termination. Costs supplied as decimal strings;
missing service coverage never establishes that the account stays within budget.
"""
from decimal import Decimal, InvalidOperation
import json, sys
BUDGET = Decimal("5.00")
def assess(evidence):
    services = evidence.get("services", [])
    known = Decimal("0")
    unknown = []
    names = set()
    for row in services:
        name = row["service"]
        if name in names:
            raise ValueError("duplicate service evidence")
        names.add(name)
        value = row.get("month_to_date_usd")
        if value is None:
            unknown.append(name)
            continue
        if isinstance(value, bool):
            raise ValueError("invalid amount")
        try:
            amount = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("invalid amount") from exc
        if not amount.is_finite() or amount < 0:
            raise ValueError("invalid amount")
        known += amount
    complete = evidence.get("complete_account_coverage") is True and bool(services) and not unknown
    status = "over_budget" if known > BUDGET else "known_within_budget" if complete else "unknown"
    return {"schema_version":1,"budget_total_usd":str(BUDGET),
        "known_month_to_date_usd":str(known),"coverage_complete":complete,
        "unknown_services":unknown,"budget_status":status,
        "configured_base_plan_usd":"5.00","base_plan_consumes_total_budget":True,
        "optional_cloud_admission":"deny","cloud_agent_deployment":"deny",
        "reason":"Human total budget includes current base; no new paid services/Workers agents. Incomplete billing remains unknown.",
        "default_execution":"existing Hetzner/user computers", "billing_mutated":False}
if __name__ == "__main__":
    print(json.dumps(assess(json.load(sys.stdin)), indent=2))
