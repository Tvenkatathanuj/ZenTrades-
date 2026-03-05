"""
Shared utilities for the Clara Answers Pipeline.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Base directories
BASE_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "accounts"
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
CHANGELOG_DIR = BASE_DIR / "changelog"


def generate_account_id(company_name: str) -> str:
    """
    Generate a deterministic account_id from company name.
    This ensures idempotency - same company always gets the same ID.
    """
    normalized = company_name.strip().lower().replace(" ", "_")
    # Use first 8 chars of hash for uniqueness + readable prefix
    hash_suffix = hashlib.md5(normalized.encode()).hexdigest()[:8]
    # Create readable prefix from company name
    prefix = "".join(c for c in normalized if c.isalnum() or c == "_")[:20]
    return f"acct_{prefix}_{hash_suffix}"


def get_account_dir(account_id: str, version: str = "v1") -> Path:
    """Get the output directory for a specific account and version."""
    path = OUTPUTS_DIR / account_id / version
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(data: dict, filepath: str | Path) -> None:
    """Save data as formatted JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved: {filepath}")


def load_json(filepath: str | Path) -> dict:
    """Load JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_template(template_name: str) -> str:
    """Load a template file from templates directory."""
    template_path = TEMPLATES_DIR / template_name
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def create_processing_log(account_id: str, pipeline: str, status: str, details: dict = None) -> dict:
    """Create a structured processing log entry."""
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "account_id": account_id,
        "pipeline": pipeline,
        "status": status,
        "details": details or {}
    }


def detect_call_type(transcript: str) -> str:
    """
    Heuristically detect whether a transcript is a demo call or onboarding call.
    
    Returns: 'demo' or 'onboarding'
    """
    transcript_lower = transcript.lower()
    
    # Onboarding indicators
    onboarding_signals = [
        "onboarding", "setup", "configure", "configuration",
        "business hours are", "our hours are", "we open at",
        "emergency means", "after hours", "transfer to",
        "our timezone", "our address is", "here's how we handle",
        "dispatch", "on-call", "routing",
        "let me walk you through", "let me go through",
        "servicetrade", "service trade",
    ]
    
    # Demo indicators  
    demo_signals = [
        "demo", "demonstration", "show you", "let me show",
        "how clara works", "how this works", "example",
        "try it out", "test call", "interested in",
        "pain point", "currently handling", "problems with",
        "would like to see", "curious about",
    ]
    
    onboarding_score = sum(1 for s in onboarding_signals if s in transcript_lower)
    demo_score = sum(1 for s in demo_signals if s in transcript_lower)
    
    return "onboarding" if onboarding_score > demo_score else "demo"


def find_matching_account(company_name: str) -> str | None:
    """
    Find an existing account by company name (fuzzy match).
    Returns account_id if found, None otherwise.
    """
    if not OUTPUTS_DIR.exists():
        return None
    
    target_id = generate_account_id(company_name)
    
    for account_dir in OUTPUTS_DIR.iterdir():
        if account_dir.is_dir() and account_dir.name == target_id:
            return target_id
    
    return None


def get_latest_version(account_id: str) -> str | None:
    """Get the latest version directory for an account."""
    account_dir = OUTPUTS_DIR / account_id
    if not account_dir.exists():
        return None
    
    versions = sorted(
        [d.name for d in account_dir.iterdir() if d.is_dir() and d.name.startswith("v")],
        key=lambda x: int(x[1:]) if x[1:].isdigit() else 0
    )
    
    return versions[-1] if versions else None


def get_next_version(account_id: str) -> str:
    """Get the next version string for an account."""
    latest = get_latest_version(account_id)
    if latest is None:
        return "v1"
    current_num = int(latest[1:]) if latest[1:].isdigit() else 1
    return f"v{current_num + 1}"


def compute_diff(old_data: dict, new_data: dict, path: str = "") -> list:
    """
    Compute differences between two dictionaries.
    Returns list of change records.
    """
    changes = []
    
    all_keys = set(list(old_data.keys()) + list(new_data.keys()))
    
    for key in sorted(all_keys):
        current_path = f"{path}.{key}" if path else key
        old_val = old_data.get(key)
        new_val = new_data.get(key)
        
        if key not in old_data:
            changes.append({
                "field": current_path,
                "action": "added",
                "old_value": None,
                "new_value": new_val
            })
        elif key not in new_data:
            changes.append({
                "field": current_path,
                "action": "removed",
                "old_value": old_val,
                "new_value": None
            })
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            changes.extend(compute_diff(old_val, new_val, current_path))
        elif old_val != new_val:
            changes.append({
                "field": current_path,
                "action": "modified",
                "old_value": old_val,
                "new_value": new_val
            })
    
    return changes
