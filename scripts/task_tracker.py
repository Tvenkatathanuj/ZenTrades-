"""
Task Tracker Integration.

Creates and updates tracking items for each account processed.
Uses a local JSON-based task board (zero-cost alternative to Asana).
Optionally integrates with GitHub Issues if a repo is configured.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

from utils import save_json, load_json, BASE_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TASKS_FILE = BASE_DIR / "outputs" / "task_board.json"


class TaskTracker:
    """
    Local JSON-based task tracker.
    Acts as a zero-cost alternative to Asana/Trello.
    """

    def __init__(self, tasks_file: str = None):
        self.tasks_file = Path(tasks_file) if tasks_file else TASKS_FILE
        self.tasks = self._load_tasks()

    def _load_tasks(self) -> dict:
        """Load existing tasks or initialize empty board."""
        if self.tasks_file.exists():
            return load_json(self.tasks_file)
        return {
            "board_name": "Clara Answers - Agent Onboarding",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "columns": {
                "backlog": [],
                "in_progress": [],
                "review": [],
                "done": []
            },
            "tasks": {}
        }

    def _save_tasks(self):
        """Persist tasks to disk."""
        save_json(self.tasks, self.tasks_file)

    def create_task(self, task_id: str, title: str, description: str = "",
                    status: str = "backlog", metadata: dict = None) -> dict:
        """
        Create a new task or update existing one (idempotent).
        
        Args:
            task_id: Unique task identifier (typically account_id + version)
            title: Task title
            description: Task description
            status: Task status column
            metadata: Additional metadata
        
        Returns:
            Task dictionary
        """
        now = datetime.utcnow().isoformat() + "Z"
        
        if task_id in self.tasks["tasks"]:
            # Update existing task
            task = self.tasks["tasks"][task_id]
            old_status = task["status"]
            task["title"] = title
            task["description"] = description
            task["status"] = status
            task["metadata"] = metadata or task.get("metadata", {})
            task["updated_at"] = now
            task["history"].append({
                "action": "updated",
                "from_status": old_status,
                "to_status": status,
                "timestamp": now
            })
            
            # Move between columns
            if old_status != status:
                if task_id in self.tasks["columns"].get(old_status, []):
                    self.tasks["columns"][old_status].remove(task_id)
                if status not in self.tasks["columns"]:
                    self.tasks["columns"][status] = []
                if task_id not in self.tasks["columns"][status]:
                    self.tasks["columns"][status].append(task_id)
            
            logger.info(f"Task updated: {task_id} ({old_status} -> {status})")
        else:
            # Create new task
            task = {
                "task_id": task_id,
                "title": title,
                "description": description,
                "status": status,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now,
                "history": [{
                    "action": "created",
                    "to_status": status,
                    "timestamp": now
                }]
            }
            self.tasks["tasks"][task_id] = task
            
            if status not in self.tasks["columns"]:
                self.tasks["columns"][status] = []
            self.tasks["columns"][status].append(task_id)
            
            logger.info(f"Task created: {task_id}")

        self._save_tasks()
        return task

    def get_task(self, task_id: str) -> dict:
        """Get a task by ID."""
        return self.tasks["tasks"].get(task_id)

    def list_tasks(self, status: str = None) -> list:
        """List tasks, optionally filtered by status."""
        if status:
            task_ids = self.tasks["columns"].get(status, [])
            return [self.tasks["tasks"][tid] for tid in task_ids if tid in self.tasks["tasks"]]
        return list(self.tasks["tasks"].values())

    def get_board_summary(self) -> dict:
        """Get board summary with counts per column."""
        return {
            column: len(task_ids)
            for column, task_ids in self.tasks["columns"].items()
        }


def create_task_for_account(account_id: str, memo: dict, version: str) -> dict:
    """
    Create or update a task for a specific account.
    
    Args:
        account_id: Account ID
        memo: Account memo dictionary
        version: Current version (v1, v2)
    
    Returns:
        Task dictionary
    """
    tracker = TaskTracker()
    
    company = memo.get("company_name", "Unknown Company")
    unknowns_count = len(memo.get("questions_or_unknowns", []))
    services_count = len(memo.get("services_supported", []))
    
    if version == "v1":
        task_id = f"setup_{account_id}"
        title = f"[v1] Setup Agent - {company}"
        description = (
            f"Demo call processed. Preliminary agent created.\n"
            f"Services: {services_count}\n"
            f"Open questions: {unknowns_count}\n"
            f"Status: Awaiting onboarding call"
        )
        status = "in_progress"
    elif version == "v2":
        task_id = f"setup_{account_id}"
        title = f"[v2] Agent Updated - {company}"
        description = (
            f"Onboarding call processed. Agent updated to v2.\n"
            f"Services: {services_count}\n"
            f"Remaining questions: {unknowns_count}\n"
            f"Status: Ready for review"
        )
        status = "review" if unknowns_count == 0 else "in_progress"
    else:
        task_id = f"setup_{account_id}_{version}"
        title = f"[{version}] Agent Update - {company}"
        description = f"Agent updated to {version}."
        status = "review"
    
    metadata = {
        "account_id": account_id,
        "company_name": company,
        "version": version,
        "unknowns_count": unknowns_count,
        "services_count": services_count,
        "business_hours_configured": bool(memo.get("business_hours", {}).get("start")),
        "emergency_rules_configured": bool(memo.get("emergency_definition")),
    }
    
    task = tracker.create_task(task_id, title, description, status, metadata)
    return {
        "task_id": task_id,
        "title": title,
        "status": status,
        "tracker": "local_json",
        "file": str(TASKS_FILE)
    }


if __name__ == "__main__":
    # Demo usage
    tracker = TaskTracker()
    
    # Show board summary
    summary = tracker.get_board_summary()
    print("\nTask Board Summary:")
    print("-" * 30)
    for column, count in summary.items():
        print(f"  {column}: {count}")
    
    all_tasks = tracker.list_tasks()
    if all_tasks:
        print(f"\nAll Tasks ({len(all_tasks)}):")
        for task in all_tasks:
            print(f"  [{task['status']}] {task['title']}")
