"""JSON file storage for the Finance Tracker App."""

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

FILES = {
    "peers": DATA_DIR / "peers.json",
    "groups": DATA_DIR / "groups.json",
    "expenses": DATA_DIR / "expenses.json",
    "settlements": DATA_DIR / "settlements.json",
}


SAMPLE_DATA = {
    "peers": [
        {"id": "peer_alex", "name": "Alex Rivera", "email": "alex@example.edu"},
        {"id": "peer_maya", "name": "Maya Chen", "email": "maya@example.edu"},
        {"id": "peer_jordan", "name": "Jordan Lee", "email": "jordan@example.edu"},
    ],
    "groups": [
        {"id": "group_roommates", "name": "Roommates", "peer_ids": ["peer_alex", "peer_maya", "peer_jordan"]},
        {"id": "group_lab", "name": "Lab Project", "peer_ids": ["peer_alex", "peer_maya"]},
    ],
    "expenses": [
        {
            "id": "expense_groceries",
            "amount": 72.60,
            "date": "2026-04-20",
            "description": "Shared groceries",
            "payer_id": "peer_alex",
            "participant_ids": ["peer_alex", "peer_maya", "peer_jordan"],
            "split_type": "equal",
            "custom_splits": {},
            "group_id": "group_roommates",
        },
        {
            "id": "expense_printing",
            "amount": 18.00,
            "date": "2026-04-22",
            "description": "Poster printing",
            "payer_id": "peer_maya",
            "participant_ids": ["peer_alex", "peer_maya"],
            "split_type": "custom",
            "custom_splits": {"peer_alex": 10.00, "peer_maya": 8.00},
            "group_id": "group_lab",
        },
    ],
    "settlements": [
        {
            "id": "settlement_sample",
            "from_peer_id": "peer_jordan",
            "to_peer_id": "peer_alex",
            "amount": 10.00,
            "date": "2026-04-25",
            "note": "Partial grocery payback",
        }
    ],
}


def ensure_data_files() -> None:
    """Create the data directory and seed missing JSON files."""
    DATA_DIR.mkdir(exist_ok=True)
    for key, path in FILES.items():
        if not path.exists():
            save_records(key, SAMPLE_DATA[key])


def load_records(name: str) -> list:
    """Load a list of records from a JSON data file."""
    ensure_data_files()
    path = FILES[name]
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_records(name: str, records: list) -> None:
    """Save a list of records to a JSON data file."""
    DATA_DIR.mkdir(exist_ok=True)
    path = FILES[name]
    with path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)


def load_all() -> dict:
    """Load every app collection from local JSON storage."""
    return {name: load_records(name) for name in FILES}
