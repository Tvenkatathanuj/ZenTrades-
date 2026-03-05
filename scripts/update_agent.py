"""
Agent Update Pipeline.

Takes onboarding data and updates an existing v1 account memo and agent spec 
to produce v2 versions with full changelog.
"""

import os
import json
import copy
import logging
import argparse
from pathlib import Path
from datetime import datetime

from utils import (
    generate_account_id, get_account_dir, save_json, load_json,
    compute_diff, get_latest_version, get_next_version,
    OUTPUTS_DIR, CHANGELOG_DIR
)
from extract_memo import extract_account_memo, RuleBasedExtractor
from generate_agent_spec import generate_agent_spec, save_agent_spec

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def merge_memos(v1_memo: dict, onboarding_memo: dict) -> dict:
    """
    Merge onboarding data into existing v1 memo to produce v2.
    
    Rules:
    - Onboarding data OVERRIDES v1 data for fields that are explicitly provided
    - Empty/null onboarding fields do NOT override existing v1 data
    - Lists are merged (union), not replaced, unless the onboarding explicitly redefines them
    - questions_or_unknowns is recalculated based on what's now known
    
    Args:
        v1_memo: Original demo-derived account memo
        onboarding_memo: Onboarding-extracted account memo
    
    Returns:
        Merged v2 memo
    """
    v2_memo = copy.deepcopy(v1_memo)
    v2_memo["version"] = "v2"
    v2_memo["source_type"] = "onboarding"
    
    # Fields that should be overridden if onboarding provides them
    override_fields = [
        "company_name", "business_type", "office_address",
        "after_hours_flow_summary", "office_hours_flow_summary", "notes"
    ]
    
    for field in override_fields:
        onboarding_val = onboarding_memo.get(field)
        if onboarding_val and str(onboarding_val).strip():
            v2_memo[field] = onboarding_val
    
    # Business hours - override sub-fields if provided
    ob_hours = onboarding_memo.get("business_hours", {})
    for sub_field in ["days", "start", "end", "timezone"]:
        if ob_hours.get(sub_field) and str(ob_hours[sub_field]).strip():
            v2_memo["business_hours"][sub_field] = ob_hours[sub_field]
    
    # Services - merge (union)
    v1_services = set(v1_memo.get("services_supported", []))
    ob_services = set(onboarding_memo.get("services_supported", []))
    if ob_services:
        v2_memo["services_supported"] = sorted(list(v1_services | ob_services))
    
    # Emergency definitions - merge
    v1_emergencies = set(v1_memo.get("emergency_definition", []))
    ob_emergencies = set(onboarding_memo.get("emergency_definition", []))
    if ob_emergencies:
        v2_memo["emergency_definition"] = sorted(list(v1_emergencies | ob_emergencies))
    
    # Emergency routing - override if onboarding provides contacts
    ob_routing = onboarding_memo.get("emergency_routing_rules", {})
    if ob_routing.get("who_to_call"):
        v2_memo["emergency_routing_rules"]["who_to_call"] = ob_routing["who_to_call"]
    if ob_routing.get("call_order"):
        v2_memo["emergency_routing_rules"]["call_order"] = ob_routing["call_order"]
    if ob_routing.get("fallback") and str(ob_routing["fallback"]).strip():
        v2_memo["emergency_routing_rules"]["fallback"] = ob_routing["fallback"]
    
    # Non-emergency routing - override if provided
    ob_ne_routing = onboarding_memo.get("non_emergency_routing_rules", {})
    if ob_ne_routing.get("during_hours") and str(ob_ne_routing["during_hours"]).strip():
        v2_memo["non_emergency_routing_rules"]["during_hours"] = ob_ne_routing["during_hours"]
    if ob_ne_routing.get("after_hours") and str(ob_ne_routing["after_hours"]).strip():
        v2_memo["non_emergency_routing_rules"]["after_hours"] = ob_ne_routing["after_hours"]
    
    # Call transfer rules - override if provided
    ob_transfer = onboarding_memo.get("call_transfer_rules", {})
    if ob_transfer.get("timeout_seconds") is not None:
        v2_memo["call_transfer_rules"]["timeout_seconds"] = ob_transfer["timeout_seconds"]
    if ob_transfer.get("max_retries") is not None:
        v2_memo["call_transfer_rules"]["max_retries"] = ob_transfer["max_retries"]
    if ob_transfer.get("failure_message") and str(ob_transfer["failure_message"]).strip():
        v2_memo["call_transfer_rules"]["failure_message"] = ob_transfer["failure_message"]
    
    # Integration constraints - merge
    v1_constraints = set(v1_memo.get("integration_constraints", []))
    ob_constraints = set(onboarding_memo.get("integration_constraints", []))
    if ob_constraints:
        v2_memo["integration_constraints"] = sorted(list(v1_constraints | ob_constraints))
    
    # Recalculate questions_or_unknowns
    # Remove unknowns that are now answered
    remaining_unknowns = []
    for unknown in v1_memo.get("questions_or_unknowns", []):
        unknown_lower = unknown.lower()
        resolved = False
        
        if "business hours" in unknown_lower and v2_memo["business_hours"].get("start"):
            resolved = True
        elif "timezone" in unknown_lower and v2_memo["business_hours"].get("timezone"):
            resolved = True
        elif "address" in unknown_lower and v2_memo.get("office_address"):
            resolved = True
        elif "emergency" in unknown_lower and v2_memo.get("emergency_definition"):
            resolved = True
        elif "services" in unknown_lower and v2_memo.get("services_supported"):
            resolved = True
        
        if not resolved:
            remaining_unknowns.append(unknown)
    
    # Add new unknowns from onboarding
    for unknown in onboarding_memo.get("questions_or_unknowns", []):
        if unknown not in remaining_unknowns:
            remaining_unknowns.append(unknown)
    
    v2_memo["questions_or_unknowns"] = remaining_unknowns
    
    # Regenerate flow summaries with updated data
    extractor = RuleBasedExtractor()
    v2_memo["office_hours_flow_summary"] = extractor._generate_office_hours_summary(v2_memo)
    v2_memo["after_hours_flow_summary"] = extractor._generate_after_hours_summary(v2_memo)
    
    # Preserve account_id
    v2_memo["account_id"] = v1_memo["account_id"]
    
    return v2_memo


def generate_changelog(v1_memo: dict, v2_memo: dict, v1_spec: dict, v2_spec: dict) -> dict:
    """
    Generate a comprehensive changelog between v1 and v2.
    
    Returns:
        Changelog dictionary
    """
    memo_changes = compute_diff(v1_memo, v2_memo)
    
    # Categorize changes
    categorized = {
        "summary": "",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "account_id": v1_memo.get("account_id", ""),
        "company_name": v2_memo.get("company_name", v1_memo.get("company_name", "")),
        "from_version": "v1",
        "to_version": "v2",
        "total_changes": len(memo_changes),
        "changes_by_category": {
            "business_info": [],
            "hours_and_schedule": [],
            "services": [],
            "emergency_config": [],
            "routing_rules": [],
            "transfer_config": [],
            "integration": [],
            "other": []
        },
        "resolved_unknowns": [],
        "new_unknowns": [],
        "all_changes": memo_changes
    }
    
    # Categorize each change
    for change in memo_changes:
        field = change["field"]
        
        if "company_name" in field or "business_type" in field or "office_address" in field:
            categorized["changes_by_category"]["business_info"].append(change)
        elif "business_hours" in field:
            categorized["changes_by_category"]["hours_and_schedule"].append(change)
        elif "services" in field:
            categorized["changes_by_category"]["services"].append(change)
        elif "emergency" in field:
            categorized["changes_by_category"]["emergency_config"].append(change)
        elif "routing" in field:
            categorized["changes_by_category"]["routing_rules"].append(change)
        elif "transfer" in field:
            categorized["changes_by_category"]["transfer_config"].append(change)
        elif "integration" in field:
            categorized["changes_by_category"]["integration"].append(change)
        else:
            categorized["changes_by_category"]["other"].append(change)
    
    # Track resolved unknowns
    v1_unknowns = set(v1_memo.get("questions_or_unknowns", []))
    v2_unknowns = set(v2_memo.get("questions_or_unknowns", []))
    categorized["resolved_unknowns"] = sorted(list(v1_unknowns - v2_unknowns))
    categorized["new_unknowns"] = sorted(list(v2_unknowns - v1_unknowns))
    
    # Generate summary
    summary_parts = []
    for category, changes in categorized["changes_by_category"].items():
        if changes:
            summary_parts.append(f"{category.replace('_', ' ').title()}: {len(changes)} change(s)")
    
    categorized["summary"] = f"v1 -> v2 update: {len(memo_changes)} total changes. " + "; ".join(summary_parts)
    
    return categorized


def generate_changelog_markdown(changelog: dict) -> str:
    """Generate a human-readable markdown changelog."""
    md = f"""# Changelog: {changelog['company_name']}
## {changelog['from_version']} -> {changelog['to_version']}

**Account ID:** {changelog['account_id']}  
**Date:** {changelog['timestamp']}  
**Total Changes:** {changelog['total_changes']}

---

## Summary
{changelog['summary']}

---

## Changes by Category

"""
    
    for category, changes in changelog["changes_by_category"].items():
        if changes:
            md += f"### {category.replace('_', ' ').title()}\n\n"
            for change in changes:
                action = change["action"].upper()
                field = change["field"]
                if change["action"] == "modified":
                    old_val = json.dumps(change["old_value"]) if not isinstance(change["old_value"], str) else change["old_value"]
                    new_val = json.dumps(change["new_value"]) if not isinstance(change["new_value"], str) else change["new_value"]
                    md += f"- **[{action}]** `{field}`\n"
                    md += f"  - Before: {old_val}\n"
                    md += f"  - After: {new_val}\n"
                elif change["action"] == "added":
                    new_val = json.dumps(change["new_value"]) if not isinstance(change["new_value"], str) else change["new_value"]
                    md += f"- **[{action}]** `{field}`: {new_val}\n"
                elif change["action"] == "removed":
                    md += f"- **[{action}]** `{field}`\n"
                md += "\n"
    
    if changelog["resolved_unknowns"]:
        md += "## Resolved Unknowns\n\n"
        for item in changelog["resolved_unknowns"]:
            md += f"- [OK] {item}\n"
        md += "\n"
    
    if changelog["new_unknowns"]:
        md += "## New Unknowns\n\n"
        for item in changelog["new_unknowns"]:
            md += f"- ? {item}\n"
        md += "\n"
    
    md += "---\n*Generated by Clara Answers Pipeline*\n"
    
    return md


def update_agent(account_id: str, onboarding_transcript: str, use_llm: bool = True) -> dict:
    """
    Full update pipeline: take onboarding data and produce v2 of everything.
    
    Args:
        account_id: Account ID to update
        onboarding_transcript: Onboarding call transcript text
        use_llm: Whether to use LLM for extraction
    
    Returns:
        dict with paths to all generated files
    """
    logger.info(f"Starting update pipeline for account: {account_id}")
    
    # 1. Load existing v1 data
    v1_dir = get_account_dir(account_id, "v1")
    v1_memo_path = v1_dir / "account_memo.json"
    v1_spec_path = v1_dir / "agent_spec.json"
    
    if not v1_memo_path.exists():
        raise FileNotFoundError(f"v1 account memo not found: {v1_memo_path}")
    
    v1_memo = load_json(v1_memo_path)
    v1_spec = load_json(v1_spec_path) if v1_spec_path.exists() else {}
    
    logger.info(f"Loaded v1 data for {v1_memo.get('company_name', 'Unknown')}")
    
    # 2. Extract onboarding data
    onboarding_memo = extract_account_memo(onboarding_transcript, "onboarding", use_llm)
    logger.info("Extracted onboarding data")
    
    # 3. Merge memos
    v2_memo = merge_memos(v1_memo, onboarding_memo)
    logger.info("Merged v1 + onboarding -> v2")
    
    # 4. Generate v2 agent spec
    v2_spec = generate_agent_spec(v2_memo, "v2")
    logger.info("Generated v2 agent spec")
    
    # 5. Generate changelog
    changelog = generate_changelog(v1_memo, v2_memo, v1_spec, v2_spec)
    changelog_md = generate_changelog_markdown(changelog)
    logger.info(f"Generated changelog: {changelog['total_changes']} changes")
    
    # 6. Save all outputs
    v2_dir = get_account_dir(account_id, "v2")
    
    save_json(v2_memo, v2_dir / "account_memo.json")
    save_agent_spec(v2_spec, account_id, "v2")
    save_json(changelog, v2_dir / "changelog.json")
    
    changelog_md_path = v2_dir / "changelog.md"
    with open(changelog_md_path, "w", encoding="utf-8") as f:
        f.write(changelog_md)
    logger.info(f"Changelog saved to: {changelog_md_path}")
    
    # Also save to global changelog directory
    global_changelog_path = CHANGELOG_DIR / f"{account_id}_v1_to_v2.md"
    with open(global_changelog_path, "w", encoding="utf-8") as f:
        f.write(changelog_md)
    
    # Save the raw onboarding extraction for reference
    save_json(onboarding_memo, v2_dir / "onboarding_extraction.json")
    
    result = {
        "account_id": account_id,
        "company_name": v2_memo.get("company_name", ""),
        "v2_memo_path": str(v2_dir / "account_memo.json"),
        "v2_spec_path": str(v2_dir / "agent_spec.json"),
        "changelog_json_path": str(v2_dir / "changelog.json"),
        "changelog_md_path": str(changelog_md_path),
        "total_changes": changelog["total_changes"],
        "resolved_unknowns": len(changelog["resolved_unknowns"]),
        "remaining_unknowns": len(v2_memo.get("questions_or_unknowns", [])),
    }
    
    logger.info(f"[OK] Update complete for {account_id}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update agent with onboarding data")
    parser.add_argument("account_id", help="Account ID to update")
    parser.add_argument("transcript", help="Path to onboarding transcript file")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM, use rule-based only")
    
    args = parser.parse_args()
    
    from transcribe import load_transcript
    transcript_text = load_transcript(args.transcript)
    
    result = update_agent(args.account_id, transcript_text, use_llm=not args.no_llm)
    
    print(f"\n[OK] Agent updated successfully!")
    print(f"  Account: {result['company_name']}")
    print(f"  Changes: {result['total_changes']}")
    print(f"  Resolved unknowns: {result['resolved_unknowns']}")
    print(f"  Remaining unknowns: {result['remaining_unknowns']}")
