"""Balance calculations and settlement suggestions."""


def expense_shares(expense: dict) -> dict:
    """Return the amount owed by each participant for an expense."""
    participants = expense["participant_ids"]
    if expense["split_type"] == "custom":
        return {peer_id: round(float(expense["custom_splits"].get(peer_id, 0)), 2) for peer_id in participants}

    share = round(float(expense["amount"]) / len(participants), 2)
    shares = {peer_id: share for peer_id in participants}
    rounding_gap = round(float(expense["amount"]) - sum(shares.values()), 2)
    if rounding_gap:
        shares[participants[0]] = round(shares[participants[0]] + rounding_gap, 2)
    return shares


def calculate_balances(peers: list, expenses: list, settlements: list) -> dict:
    """Calculate net balances where positive means the peer should receive money."""
    details = calculate_balance_details(peers, expenses, settlements)
    return {peer_id: values["net"] for peer_id, values in details.items()}


def calculate_balance_details(peers: list, expenses: list, settlements: list) -> dict:
    """Calculate paid, owed, settled, and net amounts for each peer."""
    details = {}
    for peer in peers:
        details[peer["id"]] = {
            "paid": 0.0,
            "share": 0.0,
            "settled_paid": 0.0,
            "settled_received": 0.0,
            "net": 0.0,
        }

    for expense in expenses:
        payer_id = expense["payer_id"]
        details[payer_id]["paid"] += round(float(expense["amount"]), 2)
        for peer_id, share in expense_shares(expense).items():
            details[peer_id]["share"] += round(float(share), 2)

    for settlement in settlements:
        amount = round(float(settlement["amount"]), 2)
        details[settlement["from_peer_id"]]["settled_paid"] += amount
        details[settlement["to_peer_id"]]["settled_received"] += amount

    for peer_id, values in details.items():
        values["paid"] = round(values["paid"], 2)
        values["share"] = round(values["share"], 2)
        values["settled_paid"] = round(values["settled_paid"], 2)
        values["settled_received"] = round(values["settled_received"], 2)
        values["net"] = round(
            values["paid"] - values["share"] + values["settled_paid"] - values["settled_received"],
            2,
        )

    return details


def generate_settlement_suggestions(balances: dict) -> list:
    """Suggest payments that settle outstanding balances with minimal steps."""
    debtors = sorted(
        [{"peer_id": peer_id, "amount": -amount} for peer_id, amount in balances.items() if amount < -0.005],
        key=lambda item: item["amount"],
        reverse=True,
    )
    creditors = sorted(
        [{"peer_id": peer_id, "amount": amount} for peer_id, amount in balances.items() if amount > 0.005],
        key=lambda item: item["amount"],
        reverse=True,
    )

    suggestions = []
    debtor_index = 0
    creditor_index = 0
    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor = debtors[debtor_index]
        creditor = creditors[creditor_index]
        amount = round(min(debtor["amount"], creditor["amount"]), 2)
        if amount > 0:
            suggestions.append(
                {"from_peer_id": debtor["peer_id"], "to_peer_id": creditor["peer_id"], "amount": amount}
            )
        debtor["amount"] = round(debtor["amount"] - amount, 2)
        creditor["amount"] = round(creditor["amount"] - amount, 2)
        if debtor["amount"] <= 0.005:
            debtor_index += 1
        if creditor["amount"] <= 0.005:
            creditor_index += 1

    return suggestions
