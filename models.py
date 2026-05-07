"""Data models and validation helpers for the Finance Tracker App."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a short readable id for persisted records."""
    return f"{prefix}_{uuid4().hex[:8]}"


def parse_date(value: str) -> str:
    """Validate and normalize a date string in YYYY-MM-DD format."""
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc
    return parsed.isoformat()


@dataclass
class Peer:
    """A person who can pay for or participate in expenses."""
    name: str
    email: str = ""
    id: str = field(default_factory=lambda: new_id("peer"))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "email": self.email}


@dataclass
class Group:
    """A named group of peers, such as roommates or classmates."""
    name: str
    peer_ids: List[str]
    id: str = field(default_factory=lambda: new_id("group"))

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "peer_ids": self.peer_ids}


@dataclass
class Expense:
    """An expense paid by one peer and split across participants."""
    amount: float
    date: str
    description: str
    payer_id: str
    participant_ids: List[str]
    split_type: str = "equal"
    custom_splits: Dict[str, float] = field(default_factory=dict)
    group_id: str = ""
    id: str = field(default_factory=lambda: new_id("expense"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "amount": self.amount,
            "date": self.date,
            "description": self.description,
            "payer_id": self.payer_id,
            "participant_ids": self.participant_ids,
            "split_type": self.split_type,
            "custom_splits": self.custom_splits,
            "group_id": self.group_id,
        }


@dataclass
class Settlement:
    """A payment from one peer to another that reduces balances."""
    from_peer_id: str
    to_peer_id: str
    amount: float
    date: str
    note: str = ""
    id: str = field(default_factory=lambda: new_id("settlement"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_peer_id": self.from_peer_id,
            "to_peer_id": self.to_peer_id,
            "amount": self.amount,
            "date": self.date,
            "note": self.note,
        }


def validate_expense(data: dict, peers: List[dict], groups: List[dict]) -> dict:
    """Validate expense inputs and return normalized values."""
    peer_ids = {peer["id"] for peer in peers}
    group_ids = {group["id"] for group in groups}

    try:
        amount = round(float(data.get("amount", 0)), 2)
    except (TypeError, ValueError) as exc:
        raise ValueError("Amount must be a number.") from exc

    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")

    normalized_date = parse_date(data.get("date", ""))
    description = data.get("description", "").strip()
    if not description:
        raise ValueError("Description is required.")

    payer_id = data.get("payer_id", "")
    if payer_id not in peer_ids:
        raise ValueError("Choose a valid payer.")

    participant_ids = list(dict.fromkeys(data.get("participant_ids", [])))
    if not participant_ids:
        raise ValueError("Choose at least one participant.")
    if any(peer_id not in peer_ids for peer_id in participant_ids):
        raise ValueError("Every participant must be a valid peer.")

    group_id = data.get("group_id", "")
    if group_id and group_id not in group_ids:
        raise ValueError("Choose a valid group.")

    split_type = data.get("split_type", "equal")
    if split_type not in {"equal", "custom"}:
        raise ValueError("Split type must be equal or custom.")

    custom_splits = {}
    if split_type == "custom":
        raw_splits = data.get("custom_splits", {})
        for peer_id in participant_ids:
            try:
                value = round(float(raw_splits.get(peer_id, 0)), 2)
            except (TypeError, ValueError) as exc:
                raise ValueError("Custom split amounts must be numbers.") from exc
            if value < 0:
                raise ValueError("Custom split amounts cannot be negative.")
            custom_splits[peer_id] = value

        if round(sum(custom_splits.values()), 2) != amount:
            raise ValueError("Custom split amounts must add up to the total amount.")

    return {
        "amount": amount,
        "date": normalized_date,
        "description": description,
        "payer_id": payer_id,
        "participant_ids": participant_ids,
        "split_type": split_type,
        "custom_splits": custom_splits,
        "group_id": group_id,
    }
