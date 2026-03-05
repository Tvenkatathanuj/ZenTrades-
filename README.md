# Clara Answers Automation Pipeline

A zero-cost, end-to-end automation pipeline that converts demo call transcripts into preliminary Retell AI agent configurations (v1), then updates them with onboarding data to produce confirmed, production-ready agent specs (v2) — with full versioning, changelogs, and diff views.

## Demo Video

[Watch the Loom walkthrough](https://www.loom.com/share/e0318a8539b14cb9bd04f7ce25664716)

---

## Architecture & Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CLARA ANSWERS PIPELINE                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐     ┌──────────────┐     ┌────────────────┐        │
│  │ Demo Call    │────▶│ Transcribe   │────▶│ Extract Memo   │        │
│  │ Recording    │     │ (Whisper)    │     │ (Rule/LLM)     │        │
│  └─────────────┘     └──────────────┘     └───────┬────────┘        │
│                                                    │                 │
│  ┌─────────────┐                          ┌───────▼────────┐        │
│  │ Transcript   │─────────────────────────▶│ Account Memo   │        │
│  │ (.txt/.json) │                          │ (v1 JSON)      │        │
│  └─────────────┘                          └───────┬────────┘        │
│                                                    │                 │
│                                           ┌───────▼────────┐        │
│                   PIPELINE A              │ Agent Spec     │        │
│                   (Demo → v1)             │ Generator      │        │
│                                           └───────┬────────┘        │
│                                                    │                 │
│                                    ┌───────────────┼──────────┐     │
│                                    ▼               ▼          ▼     │
│                              ┌──────────┐  ┌──────────┐ ┌────────┐ │
│                              │ v1 Memo  │  │ v1 Agent │ │ Task   │ │
│                              │ JSON     │  │ Spec     │ │ Board  │ │
│                              └──────────┘  └──────────┘ └────────┘ │
│                                    │               │                │
│ ═══════════════════════════════════╪═══════════════╪════════════════│
│                                    │               │                │
│                   PIPELINE B       │               │                │
│                   (Onboarding → v2)│               │                │
│                                    ▼               ▼                │
│  ┌─────────────┐           ┌──────────────────────────┐            │
│  │ Onboarding  │──────────▶│ Merge v1 + Onboarding    │            │
│  │ Call/Form   │           │ → v2 Memo + Agent Spec   │            │
│  └─────────────┘           └──────────┬───────────────┘            │
│                                       │                             │
│                        ┌──────────────┼──────────────┐             │
│                        ▼              ▼              ▼             │
│                  ┌──────────┐  ┌──────────┐  ┌────────────┐       │
│                  │ v2 Memo  │  │ v2 Agent │  │ Changelog  │       │
│                  │ JSON     │  │ Spec     │  │ (MD+JSON)  │       │
│                  └──────────┘  └──────────┘  └────────────┘       │
│                        │                                           │
│                        ▼                                           │
│                  ┌────────────┐                                    │
│                  │ Diff       │                                    │
│                  │ Viewer     │                                    │
│                  │ (HTML)     │                                    │
│                  └────────────┘                                    │
│                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
clara-answers-pipeline/
├── README.md                          # This file
├── docker-compose.yml                 # Docker setup for n8n + Ollama
├── Dockerfile                         # Pipeline runner container
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variables template
├── .gitignore                         # Git ignore rules
├── pipeline.log                       # Run logs (auto-generated)
│
├── scripts/                           # Core pipeline scripts
│   ├── __init__.py                    # Package marker
│   ├── transcribe.py                  # Whisper-based audio transcription
│   ├── extract_memo.py                # Account memo extraction (rule-based + LLM)
│   ├── generate_agent_spec.py         # Retell agent spec generation
│   ├── update_agent.py                # v1 → v2 update pipeline
│   ├── batch_process.py               # Batch runner for all files + diff generation
│   ├── task_tracker.py                # Local task board (Asana alternative)
│   ├── diff_viewer.py                 # HTML diff viewer generator
│   └── utils.py                       # Shared utilities
│
├── workflows/                         # n8n workflow exports
│   └── clara_pipeline.json            # Main automation workflow
│
├── templates/                         # Templates and schemas
│   ├── agent_prompt_template.txt      # Agent system prompt template
│   └── memo_schema.json               # Account memo JSON schema
│
├── data/                              # Input data directory
│   ├── demo_calls/                    # Demo call transcripts (.txt)
│   └── onboarding_calls/             # Onboarding call transcripts (.txt)
│
├── outputs/                           # Generated outputs
│   ├── accounts/                      # Per-account outputs
│   │   └── <account_id>/
│   │       ├── v1/                    # Demo-derived (preliminary)
│   │       │   ├── account_memo.json
│   │       │   ├── agent_spec.json
│   │       │   ├── system_prompt.txt
│   │       │   └── raw_transcript.txt
│   │       └── v2/                    # Onboarding-updated (confirmed)
│   │           ├── account_memo.json
│   │           ├── agent_spec.json
│   │           ├── system_prompt.txt
│   │           ├── onboarding_extraction.json
│   │           ├── changelog.json
│   │           ├── changelog.md
│   │           └── diff_viewer.html
│   ├── task_board.json                # Task tracking board
│   └── batch_results_<timestamp>.json # Batch run results
│
└── changelog/                         # Global changelog directory
    └── <account_id>_v1_to_v2.md
```

---

## How to Run Locally

### Prerequisites

- **Python 3.10+**
- **ffmpeg** (only needed if processing audio files)
- **Docker** (optional — only for n8n workflow engine)

### Quick Start (Python Scripts)

```bash
# 1. Clone the repository
git clone <repo-url>
cd clara-answers-pipeline

# 2. Install dependencies
pip install -r requirements.txt

# 3. Place your dataset files
#    - Demo call transcripts (.txt) → data/demo_calls/
#    - Onboarding call transcripts (.txt) → data/onboarding_calls/

# 4. Run the full pipeline (zero-cost, no LLM)
cd scripts
python batch_process.py --no-llm

# 5. View outputs
ls ../outputs/accounts/
```

**That's it.** The pipeline processes all 10 files (5 demo + 5 onboarding), generates v1 and v2 for each account, produces changelogs, diff viewers, and a task board — all in under 2 seconds.

### With Docker (n8n + Full Stack)

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Start services
docker-compose up -d

# 3. Access n8n UI at http://localhost:5678 (login: admin / clarapipeline)

# 4. Import workflow: Settings → Import from File → workflows/clara_pipeline.json

# 5. Run pipeline via Docker
docker-compose run pipeline python scripts/batch_process.py --no-llm
```

### With Local LLM (Ollama — Optional)

```bash
# 1. Install Ollama: https://ollama.ai
# 2. Pull a model
ollama pull llama3.2

# 3. Run pipeline with LLM extraction (auto-detected)
cd scripts
python batch_process.py
```

If Ollama is unavailable, the pipeline automatically falls back to rule-based extraction.

---

## How to Plug in Dataset Files

### Transcript Files (Preferred)
Place `.txt` or `.json` transcript files in the appropriate directories:

```
data/
├── demo_calls/
│   ├── apex_fire_protection_demo.txt
│   ├── coastal_sprinkler_demo.txt
│   ├── guardian_mechanical_demo.txt
│   ├── patriot_alarm_demo.txt
│   └── summit_electrical_demo.txt
└── onboarding_calls/
    ├── apex_fire_protection_onboarding.txt
    ├── coastal_sprinkler_onboarding.txt
    ├── guardian_mechanical_onboarding.txt
    ├── patriot_alarm_onboarding.txt
    └── summit_electrical_onboarding.txt
```

**Matching:** Demo and onboarding files are matched by company name extracted from the transcript, then by filename heuristics, then by sort-order position as a fallback.

### Audio Files
If you have audio recordings instead of transcripts:

```bash
# Transcribe a single file
python scripts/transcribe.py path/to/recording.m4a -o transcript.json

# Batch transcribe a directory
python scripts/transcribe.py data/demo_calls/ --batch
```

Requires: `pip install openai-whisper` and `ffmpeg` installed on the system.

---

## Included Dataset & Results

The pipeline ships with 5 pre-loaded demo/onboarding transcript pairs:

| Account | Business Type | Timezone | v1 → v2 Changes |
|---------|--------------|----------|-----------------|
| Apex Fire Protection | Fire Protection | Central | 17 |
| Coastal Sprinkler and Fire | Sprinkler | Eastern | 18 |
| Guardian Mechanical | Mechanical | Central | 18 |
| Patriot Alarm and Security | Security/Alarm | Eastern | 16 |
| Summit Electric | Electrical | Mountain | 14 |

All outputs are pre-generated in `outputs/accounts/`. Re-run the pipeline at any time to regenerate.

---

## Individual Script Usage

### Extract Account Memo
```bash
python scripts/extract_memo.py data/demo_calls/company.txt -t demo --no-llm
```

### Generate Agent Spec
```bash
python scripts/generate_agent_spec.py outputs/accounts/<id>/v1/account_memo.json
```

### Update Agent (v1 → v2)
```bash
python scripts/update_agent.py <account_id> data/onboarding_calls/company.txt --no-llm
```

### Generate Diff Viewer
```bash
python scripts/diff_viewer.py --all
# or for a specific account:
python scripts/diff_viewer.py --account <account_id>
```

### View Task Board
```bash
python scripts/task_tracker.py
```

---

## Where Outputs Are Stored

| Output | Location |
|--------|----------|
| Account Memos (v1) | `outputs/accounts/<id>/v1/account_memo.json` |
| Account Memos (v2) | `outputs/accounts/<id>/v2/account_memo.json` |
| Agent Specs (v1) | `outputs/accounts/<id>/v1/agent_spec.json` |
| Agent Specs (v2) | `outputs/accounts/<id>/v2/agent_spec.json` |
| System Prompts | `outputs/accounts/<id>/<version>/system_prompt.txt` |
| Changelogs (per account) | `outputs/accounts/<id>/v2/changelog.md` + `.json` |
| Diff Viewers (HTML) | `outputs/accounts/<id>/v2/diff_viewer.html` |
| Raw Transcripts | `outputs/accounts/<id>/v1/raw_transcript.txt` |
| Onboarding Extraction | `outputs/accounts/<id>/v2/onboarding_extraction.json` |
| Task Board | `outputs/task_board.json` |
| Batch Results | `outputs/batch_results_<timestamp>.json` |
| Global Changelogs | `changelog/<account_id>_v1_to_v2.md` |
| Pipeline Log | `pipeline.log` |

---

## Retell Setup Instructions

### Creating a Retell Account
1. Go to [https://www.retellai.com](https://www.retellai.com)
2. Sign up for a free account
3. Navigate to Dashboard → API Keys

### Importing Agent Spec into Retell
Since Retell's free tier may not support programmatic agent creation:

1. Open `outputs/accounts/<id>/v2/agent_spec.json` (or `v1` for the preliminary draft)
2. In Retell Dashboard, create a new agent
3. Copy the contents of `system_prompt.txt` into the agent's prompt field
4. Configure voice settings:
   - Voice: Rachel (or your preference)
   - Language: en-US
5. Set up function/tool definitions per the `tool_invocation_placeholders` section in the spec
6. For v2: repeat with the updated `v2/system_prompt.txt`

### API Integration (if available on free tier)
```bash
# Set your Retell API key
export RETELL_API_KEY=your_key_here

# The agent spec JSON is designed to be compatible with Retell's API schema
# POST to https://api.retellai.com/create-agent with the spec
```

---

## n8n Workflow Setup

### Importing the Workflow
1. Start n8n: `docker-compose up n8n`
2. Open http://localhost:5678
3. Go to **Workflows** → **Import from File**
4. Select `workflows/clara_pipeline.json`
5. The workflow includes:
   - **Webhook trigger** (`POST /webhook/clara-ingest`)
   - **Manual trigger** (for testing)
   - **Route by call type** (demo vs onboarding)
   - **Extract memo** (rule-based extraction)
   - **Generate agent spec**
   - **Store outputs**
   - **Create task item**

### Triggering the Workflow
```bash
# Via webhook
curl -X POST http://localhost:5678/webhook/clara-ingest \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Thank you for calling ABC Fire Protection...",
    "call_type": "demo",
    "file_name": "abc_demo.txt"
  }'
```

---

## Extraction Methods

### Rule-Based (Default, Zero-Cost)
Uses regex patterns and heuristic rules to extract:
- Company name and business type
- Business hours, days, and timezone (with word-boundary matching to avoid false positives)
- Services offered
- Emergency definitions (with artifact filtering)
- Routing rules, contacts, and fallback logic
- Call transfer timeouts and retry configuration
- Integration constraints (e.g., ServiceTrade rules)

**Pros:** Zero-cost, deterministic, fast, no external dependencies
**Cons:** May miss unconventional phrasing

### LLM-Based (Optional, via Ollama)
Uses a local LLM (e.g., Llama 3.2) for more intelligent extraction.

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama3.2

# Pipeline auto-detects Ollama and uses it
python scripts/batch_process.py  # uses LLM automatically
```

**Pros:** Better at understanding context and nuance
**Cons:** Requires ~4GB disk for model, slower processing

**Fallback:** If Ollama is not available or LLM output is unparseable, the pipeline automatically falls back to rule-based extraction using the original transcript.

---

## Known Limitations

1. **Rule-based extraction** may miss unconventional phrasing or highly complex routing descriptions
2. **Company name detection** relies on capitalization patterns and keyword matching; names without industry keywords may need manual correction
3. **Account matching** between demo and onboarding files uses company name heuristic + filename matching; explicitly named files provide the most reliable matching
4. **Whisper transcription** requires ffmpeg and significant CPU/RAM; only needed if processing raw audio files
5. **n8n workflow** is a simplified orchestration; the full Python pipeline offers more robust extraction and error handling
6. **No live Retell API integration** — outputs are Retell-compatible JSON specs for manual import

---

## What I Would Improve with Production Access

1. **Retell API Integration** — Direct programmatic agent creation and updates via Retell's API
2. **Asana/Linear Integration** — Real task tracking with assignees, due dates, and notifications
3. **Database Backend** — PostgreSQL/Supabase for proper data persistence and querying
4. **Webhook-Driven Pipeline** — Real-time processing triggered by incoming recordings
5. **Fine-Tuned LLM** — Custom extraction model trained on Clara's specific vocabulary and patterns
6. **Confidence Scoring** — Per-field confidence scores on extracted data
7. **Human-in-the-Loop** — Review UI for flagged low-confidence extractions
8. **Automated Testing** — Integration tests with mock transcripts to catch regressions
9. **Multi-Tenant Support** — Proper authentication and isolation for different operators
10. **Monitoring & Alerts** — Pipeline health dashboard, failure notifications

---

## Zero-Cost Compliance

| Component | Cost | License |
|-----------|------|---------|
| Python scripts | Free | — |
| Whisper (transcription) | Free, runs locally | MIT |
| Ollama (LLM, optional) | Free, runs locally | MIT |
| n8n (orchestration) | Free, self-hosted via Docker | Apache 2.0 |
| Storage | Local JSON files | — |
| Task Tracking | Local JSON-based board | — |

**No paid APIs, subscriptions, or credits used.**

---

## Idempotency & Reliability

- **Deterministic:** Running the pipeline twice on the same data produces identical outputs
- **Stable IDs:** Account IDs are derived from company name via MD5 hashing — always consistent
- **Cached transcriptions:** Already-transcribed audio is reused automatically
- **Per-file error recovery:** Individual file failures do not halt the batch; remaining files continue processing
- **Comprehensive logging:** All operations logged to `pipeline.log` and batch results JSON
- **Graceful fallback:** LLM extraction falls back to rule-based if Ollama is unavailable or returns unparseable output

---

*Built for the Clara Answers Intern Assignment — Zero-Cost Automation Pipeline*
