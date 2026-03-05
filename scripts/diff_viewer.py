"""
Diff Viewer - Generates visual diff reports between v1 and v2 account data.
Produces both HTML and markdown diff views.
"""

import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

from utils import load_json, compute_diff, get_account_dir, OUTPUTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_html_diff(v1_memo: dict, v2_memo: dict, v1_spec: dict, v2_spec: dict) -> str:
    """Generate an HTML diff viewer page."""
    company = v2_memo.get("company_name", v1_memo.get("company_name", "Unknown"))
    account_id = v1_memo.get("account_id", "")
    memo_changes = compute_diff(v1_memo, v2_memo)
    
    changes_html = ""
    for change in memo_changes:
        field = change["field"]
        action = change["action"]
        
        if action == "modified":
            old_val = json.dumps(change["old_value"], indent=2) if not isinstance(change["old_value"], str) else change["old_value"]
            new_val = json.dumps(change["new_value"], indent=2) if not isinstance(change["new_value"], str) else change["new_value"]
            changes_html += f"""
            <tr class="modified">
                <td><span class="badge badge-modified">MODIFIED</span></td>
                <td><code>{field}</code></td>
                <td class="old-value"><pre>{old_val}</pre></td>
                <td class="new-value"><pre>{new_val}</pre></td>
            </tr>"""
        elif action == "added":
            new_val = json.dumps(change["new_value"], indent=2) if not isinstance(change["new_value"], str) else change["new_value"]
            changes_html += f"""
            <tr class="added">
                <td><span class="badge badge-added">ADDED</span></td>
                <td><code>{field}</code></td>
                <td class="old-value">-</td>
                <td class="new-value"><pre>{new_val}</pre></td>
            </tr>"""
        elif action == "removed":
            old_val = json.dumps(change["old_value"], indent=2) if not isinstance(change["old_value"], str) else change["old_value"]
            changes_html += f"""
            <tr class="removed">
                <td><span class="badge badge-removed">REMOVED</span></td>
                <td><code>{field}</code></td>
                <td class="old-value"><pre>{old_val}</pre></td>
                <td class="new-value">-</td>
            </tr>"""

    # Resolved unknowns
    v1_unknowns = set(v1_memo.get("questions_or_unknowns", []))
    v2_unknowns = set(v2_memo.get("questions_or_unknowns", []))
    resolved = v1_unknowns - v2_unknowns
    still_open = v2_unknowns
    
    resolved_html = ""
    for item in sorted(resolved):
        resolved_html += f'<li class="resolved">&#10004; {item}</li>'
    for item in sorted(still_open):
        resolved_html += f'<li class="open">&#10067; {item}</li>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Clara Answers - Diff Viewer: {company}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #1a1a2e; margin-bottom: 5px; }}
        .subtitle {{ color: #666; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card h2 {{ color: #1a1a2e; margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .stat {{ background: white; border-radius: 8px; padding: 15px 20px; flex: 1; box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
        .stat .number {{ font-size: 2em; font-weight: bold; color: #1a1a2e; }}
        .stat .label {{ color: #666; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #1a1a2e; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
        tr:hover {{ background: #f8f9fa; }}
        .badge {{ padding: 3px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; color: white; }}
        .badge-modified {{ background: #f0ad4e; }}
        .badge-added {{ background: #5cb85c; }}
        .badge-removed {{ background: #d9534f; }}
        pre {{ background: #f8f9fa; padding: 5px; border-radius: 4px; font-size: 0.85em; white-space: pre-wrap; word-break: break-word; max-width: 300px; }}
        .old-value pre {{ background: #ffeef0; }}
        .new-value pre {{ background: #e6ffed; }}
        .resolved {{ color: #28a745; margin: 5px 0; }}
        .open {{ color: #dc3545; margin: 5px 0; }}
        ul {{ list-style: none; padding: 0; }}
        .version-label {{ display: inline-block; padding: 5px 15px; border-radius: 20px; font-weight: bold; }}
        .v1-label {{ background: #ffeef0; color: #d9534f; }}
        .v2-label {{ background: #e6ffed; color: #28a745; }}
        .prompt-diff {{ display: flex; gap: 20px; }}
        .prompt-col {{ flex: 1; }}
        .prompt-col pre {{ max-width: none; padding: 15px; font-size: 0.8em; max-height: 400px; overflow-y: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Clara Answers - Diff Viewer</h1>
        <p class="subtitle">{company} | Account: {account_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
        
        <div class="stats">
            <div class="stat">
                <div class="number">{len(memo_changes)}</div>
                <div class="label">Total Changes</div>
            </div>
            <div class="stat">
                <div class="number">{len([c for c in memo_changes if c['action'] == 'modified'])}</div>
                <div class="label">Modified</div>
            </div>
            <div class="stat">
                <div class="number">{len([c for c in memo_changes if c['action'] == 'added'])}</div>
                <div class="label">Added</div>
            </div>
            <div class="stat">
                <div class="number">{len(resolved)}</div>
                <div class="label">Unknowns Resolved</div>
            </div>
        </div>

        <div class="card">
            <h2>
                <span class="version-label v1-label">v1 (Demo)</span>
                &rarr; 
                <span class="version-label v2-label">v2 (Onboarding)</span>
                Account Memo Changes
            </h2>
            <table>
                <thead>
                    <tr>
                        <th width="100">Action</th>
                        <th width="200">Field</th>
                        <th>v1 Value</th>
                        <th>v2 Value</th>
                    </tr>
                </thead>
                <tbody>
                    {changes_html}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h2>Questions &amp; Unknowns Status</h2>
            <ul>
                {resolved_html if resolved_html else '<li>No unknowns tracked</li>'}
            </ul>
        </div>

        <div class="card">
            <h2>System Prompt Comparison</h2>
            <div class="prompt-diff">
                <div class="prompt-col">
                    <h3><span class="version-label v1-label">v1 Prompt</span></h3>
                    <pre>{v1_spec.get('system_prompt', 'N/A')[:2000]}{'...' if len(v1_spec.get('system_prompt', '')) > 2000 else ''}</pre>
                </div>
                <div class="prompt-col">
                    <h3><span class="version-label v2-label">v2 Prompt</span></h3>
                    <pre>{v2_spec.get('system_prompt', 'N/A')[:2000]}{'...' if len(v2_spec.get('system_prompt', '')) > 2000 else ''}</pre>
                </div>
            </div>
        </div>

        <div class="card" style="text-align:center; color:#666; font-size:0.85em;">
            Generated by Clara Answers Pipeline | Zero-Cost Automation
        </div>
    </div>
</body>
</html>"""
    return html


def generate_diff_for_account(account_id: str) -> str:
    """Generate diff view for a specific account."""
    v1_dir = get_account_dir(account_id, "v1")
    v2_dir = get_account_dir(account_id, "v2")
    
    v1_memo = load_json(v1_dir / "account_memo.json") if (v1_dir / "account_memo.json").exists() else {}
    v2_memo = load_json(v2_dir / "account_memo.json") if (v2_dir / "account_memo.json").exists() else {}
    v1_spec = load_json(v1_dir / "agent_spec.json") if (v1_dir / "agent_spec.json").exists() else {}
    v2_spec = load_json(v2_dir / "agent_spec.json") if (v2_dir / "agent_spec.json").exists() else {}
    
    html = generate_html_diff(v1_memo, v2_memo, v1_spec, v2_spec)
    
    output_path = v2_dir / "diff_viewer.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Diff viewer saved to: {output_path}")
    return str(output_path)


def generate_all_diffs() -> int:
    """Generate diff viewers for all accounts that have both v1 and v2. Returns count of diffs generated."""
    if not OUTPUTS_DIR.exists():
        logger.warning("No outputs directory found")
        return 0
    
    count = 0
    for account_dir in sorted(OUTPUTS_DIR.iterdir()):
        if account_dir.is_dir():
            v1_exists = (account_dir / "v1" / "account_memo.json").exists()
            v2_exists = (account_dir / "v2" / "account_memo.json").exists()
            
            if v1_exists and v2_exists:
                try:
                    path = generate_diff_for_account(account_dir.name)
                    logger.info(f"[OK] Diff generated for: {account_dir.name}")
                    count += 1
                except Exception as e:
                    logger.error(f"[FAIL] Failed for {account_dir.name}: {e}")
            elif v1_exists:
                logger.info(f"  Skipping {account_dir.name}: only v1 exists (awaiting onboarding)")
    
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate diff viewers for account versions")
    parser.add_argument("--account", help="Specific account ID to generate diff for")
    parser.add_argument("--all", action="store_true", help="Generate diffs for all accounts")
    
    args = parser.parse_args()
    
    if args.account:
        path = generate_diff_for_account(args.account)
        print(f"Diff viewer: {path}")
    else:
        generate_all_diffs()
