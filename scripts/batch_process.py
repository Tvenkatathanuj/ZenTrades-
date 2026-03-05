"""
Batch Processor - Runs the full pipeline on all dataset files.

Processes:
1. All demo call transcripts → v1 account memos + agent specs
2. All onboarding call transcripts → v2 updates + changelogs
3. Generates a summary report

Designed to be idempotent - running twice produces the same results.
"""

import os
import sys
import json
import logging
import argparse
import traceback
from pathlib import Path
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    generate_account_id, get_account_dir, save_json, load_json,
    detect_call_type, get_latest_version, OUTPUTS_DIR, BASE_DIR
)
from transcribe import load_transcript, transcribe_file
from extract_memo import extract_account_memo
from generate_agent_spec import generate_agent_spec, save_agent_spec
from update_agent import update_agent, merge_memos, generate_changelog, generate_changelog_markdown
from task_tracker import create_task_for_account, TaskTracker
from diff_viewer import generate_all_diffs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "pipeline.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


class PipelineRunner:
    """Runs the full Clara Answers automation pipeline."""

    def __init__(self, data_dir: str = None, use_llm: bool = True, 
                 whisper_model: str = "base"):
        self.data_dir = Path(data_dir) if data_dir else BASE_DIR / "data"
        self.demo_dir = self.data_dir / "demo_calls"
        self.onboarding_dir = self.data_dir / "onboarding_calls"
        self.use_llm = use_llm
        self.whisper_model = whisper_model
        self.results = {
            "run_id": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            "started_at": datetime.utcnow().isoformat() + "Z",
            "completed_at": None,
            "pipeline_a_results": [],
            "pipeline_b_results": [],
            "errors": [],
            "summary": {}
        }
        self.task_tracker = TaskTracker()

    def run(self) -> dict:
        """
        Run the complete pipeline end-to-end.
        
        Returns:
            Results summary dictionary
        """
        logger.info("=" * 60)
        logger.info("CLARA ANSWERS PIPELINE - BATCH RUN")
        logger.info(f"Run ID: {self.results['run_id']}")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"LLM enabled: {self.use_llm}")
        logger.info("=" * 60)

        # Phase 1: Pipeline A - Demo Calls -> v1
        logger.info("\n--- PIPELINE A: Demo Calls -> v1 Agents ---")
        self._run_pipeline_a()

        # Phase 2: Pipeline B - Onboarding Calls -> v2
        logger.info("\n--- PIPELINE B: Onboarding Calls -> v2 Updates ---")
        self._run_pipeline_b()

        # Phase 2.5: Generate diff viewers for all accounts with v1 and v2
        logger.info("\n--- Generating Diff Viewers ---")
        try:
            diff_count = generate_all_diffs()
            logger.info(f"Generated {diff_count} diff viewer(s)")
        except Exception as e:
            logger.warning(f"Diff viewer generation skipped: {e}")

        # Phase 3: Generate summary
        self._generate_summary()

        self.results["completed_at"] = datetime.utcnow().isoformat() + "Z"

        # Save results
        results_path = BASE_DIR / "outputs" / f"batch_results_{self.results['run_id']}.json"
        save_json(self.results, results_path)
        logger.info(f"\nResults saved to: {results_path}")

        self._print_summary()
        return self.results

    def _get_transcript_files(self, directory: Path) -> list:
        """Get all transcript/audio files from a directory."""
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            return []

        transcript_exts = {".txt", ".json"}
        audio_exts = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac"}

        files = []
        for f in sorted(directory.iterdir()):
            if f.is_file() and f.suffix.lower() in (transcript_exts | audio_exts):
                files.append(f)

        return files

    def _load_or_transcribe(self, file_path: Path) -> str:
        """Load transcript text, transcribing audio if necessary."""
        transcript_exts = {".txt", ".json"}
        
        if file_path.suffix.lower() in transcript_exts:
            logger.info(f"Loading transcript: {file_path.name}")
            return load_transcript(str(file_path))
        else:
            logger.info(f"Transcribing audio: {file_path.name}")
            transcript_path = file_path.parent / f"{file_path.stem}_transcript.json"
            
            # Check if already transcribed (idempotency)
            if transcript_path.exists():
                logger.info(f"Using cached transcription: {transcript_path.name}")
                return load_transcript(str(transcript_path))
            
            try:
                return transcribe_file(str(file_path), str(transcript_path), self.whisper_model)
            except Exception as e:
                logger.error(f"Transcription failed for {file_path.name}: {e}")
                raise

    def _run_pipeline_a(self):
        """Pipeline A: Process demo calls to generate v1 assets."""
        files = self._get_transcript_files(self.demo_dir)
        
        if not files:
            logger.warning(f"No demo call files found in {self.demo_dir}")
            logger.info("Place demo call transcripts (.txt/.json) or audio files in the demo_calls directory")
            return

        logger.info(f"Found {len(files)} demo call file(s)")

        for i, file_path in enumerate(files, 1):
            logger.info(f"\n[{i}/{len(files)}] Processing demo call: {file_path.name}")
            
            result = {
                "file": file_path.name,
                "status": "pending",
                "account_id": None,
                "company_name": None,
                "outputs": {}
            }

            try:
                # Step 1: Get transcript text
                transcript = self._load_or_transcribe(file_path)
                
                if not transcript or len(transcript.strip()) < 20:
                    raise ValueError("Transcript is empty or too short")

                # Step 2: Extract account memo
                logger.info("  Extracting account memo...")
                memo = extract_account_memo(transcript, "demo", self.use_llm)
                
                # Ensure we have an account_id
                if not memo.get("account_id"):
                    # Use filename as fallback for company identification
                    fallback_name = file_path.stem.replace("_", " ").replace("-", " ").title()
                    memo["company_name"] = memo.get("company_name") or fallback_name
                    memo["account_id"] = generate_account_id(memo["company_name"])
                
                account_id = memo["account_id"]
                result["account_id"] = account_id
                result["company_name"] = memo.get("company_name", "")

                # Step 3: Save account memo
                v1_dir = get_account_dir(account_id, "v1")
                memo_path = v1_dir / "account_memo.json"
                save_json(memo, memo_path)
                result["outputs"]["account_memo"] = str(memo_path)

                # Save raw transcript for reference
                raw_path = v1_dir / "raw_transcript.txt"
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(transcript)

                # Step 4: Generate agent spec
                logger.info("  Generating agent spec...")
                spec = generate_agent_spec(memo, "v1")
                spec_path = save_agent_spec(spec, account_id, "v1")
                result["outputs"]["agent_spec"] = str(spec_path)

                # Step 5: Create task tracker item
                try:
                    task = create_task_for_account(account_id, memo, "v1")
                    result["outputs"]["task"] = task
                except Exception as e:
                    logger.warning(f"  Task creation skipped: {e}")

                result["status"] = "success"
                logger.info(f"  [OK] v1 generated for {memo.get('company_name', account_id)}")
                logger.info(f"    Services: {len(memo.get('services_supported', []))}")
                logger.info(f"    Unknowns: {len(memo.get('questions_or_unknowns', []))}")

            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                self.results["errors"].append({
                    "pipeline": "A",
                    "file": file_path.name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                logger.error(f"  [FAIL] Failed: {e}")

            self.results["pipeline_a_results"].append(result)

    def _run_pipeline_b(self):
        """Pipeline B: Process onboarding calls to generate v2 updates."""
        files = self._get_transcript_files(self.onboarding_dir)
        
        if not files:
            logger.warning(f"No onboarding call files found in {self.onboarding_dir}")
            logger.info("Place onboarding call transcripts in the onboarding_calls directory")
            return

        logger.info(f"Found {len(files)} onboarding call file(s)")

        # Build map of existing accounts for matching
        existing_accounts = self._get_existing_accounts()
        logger.info(f"Existing v1 accounts: {len(existing_accounts)}")

        for i, file_path in enumerate(files, 1):
            logger.info(f"\n[{i}/{len(files)}] Processing onboarding call: {file_path.name}")
            
            result = {
                "file": file_path.name,
                "status": "pending",
                "account_id": None,
                "company_name": None,
                "changes_count": 0,
                "outputs": {}
            }

            try:
                # Step 1: Get transcript text
                transcript = self._load_or_transcribe(file_path)
                
                if not transcript or len(transcript.strip()) < 20:
                    raise ValueError("Transcript is empty or too short")

                # Step 2: Extract onboarding data
                logger.info("  Extracting onboarding data...")
                onboarding_memo = extract_account_memo(transcript, "onboarding", self.use_llm)

                # Step 3: Match to existing account
                account_id = self._match_account(onboarding_memo, existing_accounts, file_path)
                
                if not account_id:
                    # Create new account if no match found
                    if not onboarding_memo.get("account_id"):
                        fallback_name = file_path.stem.replace("_", " ").replace("-", " ").title()
                        onboarding_memo["company_name"] = onboarding_memo.get("company_name") or fallback_name
                        onboarding_memo["account_id"] = generate_account_id(onboarding_memo["company_name"])
                    account_id = onboarding_memo["account_id"]
                    logger.warning(f"  No matching v1 account found. Creating fresh for: {account_id}")
                    
                    # Save as v1 first, then create v2
                    v1_dir = get_account_dir(account_id, "v1")
                    save_json(onboarding_memo, v1_dir / "account_memo.json")
                    spec = generate_agent_spec(onboarding_memo, "v1")
                    save_agent_spec(spec, account_id, "v1")

                result["account_id"] = account_id

                # Step 4: Run update pipeline
                logger.info(f"  Updating account: {account_id}")
                update_result = update_agent(account_id, transcript, self.use_llm)
                
                result["company_name"] = update_result.get("company_name", "")
                result["changes_count"] = update_result.get("total_changes", 0)
                result["outputs"] = update_result

                # Step 5: Update task tracker
                try:
                    v2_memo = load_json(update_result["v2_memo_path"])
                    task = create_task_for_account(account_id, v2_memo, "v2")
                    result["outputs"]["task"] = task
                except Exception as e:
                    logger.warning(f"  Task update skipped: {e}")

                result["status"] = "success"
                logger.info(f"  [OK] v2 generated for {result['company_name']}")
                logger.info(f"    Changes: {result['changes_count']}")
                logger.info(f"    Resolved unknowns: {update_result.get('resolved_unknowns', 0)}")

            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
                self.results["errors"].append({
                    "pipeline": "B",
                    "file": file_path.name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
                logger.error(f"  [FAIL] Failed: {e}")

            self.results["pipeline_b_results"].append(result)

    def _get_existing_accounts(self) -> dict:
        """Get map of existing accounts with their v1 memos."""
        accounts = {}
        if OUTPUTS_DIR.exists():
            for account_dir in OUTPUTS_DIR.iterdir():
                if account_dir.is_dir():
                    v1_memo_path = account_dir / "v1" / "account_memo.json"
                    if v1_memo_path.exists():
                        try:
                            memo = load_json(v1_memo_path)
                            accounts[account_dir.name] = memo
                        except Exception:
                            pass
        return accounts

    def _match_account(self, onboarding_memo: dict, existing_accounts: dict, file_path: Path) -> str:
        """
        Match an onboarding transcript to an existing account.
        Uses company name matching and filename heuristics.
        """
        # Try direct account_id match
        ob_company = onboarding_memo.get("company_name", "")
        if ob_company:
            ob_id = generate_account_id(ob_company)
            if ob_id in existing_accounts:
                return ob_id

        # Try filename-based matching
        filename_lower = file_path.stem.lower().replace("_", " ").replace("-", " ")
        
        for account_id, memo in existing_accounts.items():
            company_lower = memo.get("company_name", "").lower()
            # Check if filename contains company name or vice versa
            if company_lower and (company_lower in filename_lower or filename_lower in company_lower):
                return account_id

        # Try fuzzy matching on company names
        if ob_company:
            ob_words = set(ob_company.lower().split())
            best_match = None
            best_score = 0
            
            for account_id, memo in existing_accounts.items():
                existing_words = set(memo.get("company_name", "").lower().split())
                if existing_words:
                    overlap = len(ob_words & existing_words) / max(len(ob_words), len(existing_words))
                    if overlap > best_score and overlap > 0.3:
                        best_score = overlap
                        best_match = account_id
            
            if best_match:
                return best_match

        # Use positional matching as last resort (demo file 1 matches onboarding file 1)
        demo_files = self._get_transcript_files(self.demo_dir)
        onboarding_files = self._get_transcript_files(self.onboarding_dir)
        
        if file_path in onboarding_files:
            idx = onboarding_files.index(file_path)
            account_ids = list(existing_accounts.keys())
            if idx < len(account_ids):
                logger.info(f"  Using positional matching: onboarding #{idx+1} -> account {account_ids[idx]}")
                return account_ids[idx]

        return None

    def _generate_summary(self):
        """Generate a summary of the batch run."""
        a_success = sum(1 for r in self.results["pipeline_a_results"] if r["status"] == "success")
        a_total = len(self.results["pipeline_a_results"])
        b_success = sum(1 for r in self.results["pipeline_b_results"] if r["status"] == "success")
        b_total = len(self.results["pipeline_b_results"])

        self.results["summary"] = {
            "pipeline_a": {
                "total": a_total,
                "success": a_success,
                "failed": a_total - a_success
            },
            "pipeline_b": {
                "total": b_total,
                "success": b_success,
                "failed": b_total - b_success
            },
            "total_accounts": len(set(
                r.get("account_id") for r in self.results["pipeline_a_results"] + self.results["pipeline_b_results"]
                if r.get("account_id")
            )),
            "total_errors": len(self.results["errors"])
        }

    def _print_summary(self):
        """Print a nice summary to console."""
        s = self.results["summary"]
        print("\n" + "=" * 60)
        print("PIPELINE RUN COMPLETE")
        print("=" * 60)
        print(f"Pipeline A (Demo -> v1):       {s['pipeline_a']['success']}/{s['pipeline_a']['total']} successful")
        print(f"Pipeline B (Onboarding -> v2): {s['pipeline_b']['success']}/{s['pipeline_b']['total']} successful")
        print(f"Total accounts:               {s['total_accounts']}")
        print(f"Total errors:                 {s['total_errors']}")
        
        if self.results["errors"]:
            print("\nErrors:")
            for err in self.results["errors"]:
                print(f"  [{err['pipeline']}] {err['file']}: {err['error']}")
        
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Clara Answers Pipeline batch processing")
    parser.add_argument("-d", "--data-dir", help="Data directory containing demo_calls/ and onboarding_calls/")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM, use rule-based extraction only")
    parser.add_argument("-m", "--whisper-model", default="base", help="Whisper model size")
    args = parser.parse_args()
    
    runner = PipelineRunner(
        data_dir=args.data_dir,
        use_llm=not args.no_llm,
        whisper_model=args.whisper_model
    )
    
    results = runner.run()
