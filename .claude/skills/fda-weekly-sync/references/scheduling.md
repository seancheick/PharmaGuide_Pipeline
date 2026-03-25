# Scheduling the FDA Weekly Sync

## How the Automation Works

```
Weekly schedule trigger
     ↓
Shell script runs fda_weekly_sync.py (fetches FDA data, generates report)
     ↓
Shell script invokes Claude Code in headless mode: claude -p "/fda-weekly-sync"
     ↓
Claude reads the report, enriches entries, writes to banned_recalled_ingredients.json
     ↓
Script commits the changes with an automated message
```

---

## Option 1: macOS — launchd (Recommended)

Create a wrapper shell script first:

```bash
# File: scripts/run_fda_sync.sh
#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"  # adjust if using system python
LOG_FILE="${PROJECT_DIR}/scripts/fda_sync.log"

echo "=== FDA Sync $(date) ===" >> "$LOG_FILE"

# Step 1: Generate FDA report
"$VENV_PYTHON" "${PROJECT_DIR}/scripts/api_audit/fda_weekly_sync.py" --days 7 >> "$LOG_FILE" 2>&1

# Step 2: Claude reviews report and updates JSON
# Requires claude CLI to be installed and authenticated
claude --dangerously-skip-permissions -p "/fda-weekly-sync" >> "$LOG_FILE" 2>&1

# Step 3: Commit changes
cd "$PROJECT_DIR"
git add scripts/data/banned_recalled_ingredients.json
git diff --cached --quiet || git commit -m "chore(fda-sync): weekly regulatory update $(date +%Y-%m-%d)"

echo "=== Done ===" >> "$LOG_FILE"
```

Make it executable:
```bash
chmod +x scripts/run_fda_sync.sh
```

Create the launchd plist:
```xml
<!-- File: ~/Library/LaunchAgents/com.dsld.fda-weekly-sync.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dsld.fda-weekly-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/YOUR_USERNAME/path/to/dsld_clean/scripts/run_fda_sync.sh</string>
    </array>

    <!-- Run every Monday at 9:00 AM -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/fda_sync_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/fda_sync_stderr.log</string>

    <!-- Run on next opportunity if machine was asleep during scheduled time -->
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

Load it:
```bash
# Replace with your actual path
launchctl load ~/Library/LaunchAgents/com.dsld.fda-weekly-sync.plist

# Verify it's loaded
launchctl list | grep dsld

# Test run immediately
launchctl start com.dsld.fda-weekly-sync

# Unload (to stop scheduling)
launchctl unload ~/Library/LaunchAgents/com.dsld.fda-weekly-sync.plist
```

---

## Option 2: Linux / WSL — cron

```bash
# Edit crontab
crontab -e

# Add this line: Run every Monday at 9 AM
0 9 * * 1 /bin/bash /path/to/dsld_clean/scripts/run_fda_sync.sh >> /path/to/dsld_clean/scripts/fda_sync.log 2>&1
```

---

## Option 3: GitHub Actions (Cloud, no local machine required)

```yaml
# File: .github/workflows/fda-weekly-sync.yml
name: FDA Weekly Regulatory Sync

on:
  schedule:
    # Every Monday at 9:00 AM UTC
    - cron: '0 9 * * 1'
  workflow_dispatch:  # Allow manual trigger from GitHub UI

jobs:
  fda-sync:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # Needed to commit changes

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install requests

      - name: Run FDA sync script
        run: |
          python scripts/api_audit/fda_weekly_sync.py --days 7

      - name: Run Claude Code review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          # Install Claude Code CLI
          npm install -g @anthropic-ai/claude-code
          # Run the skill headlessly
          claude --dangerously-skip-permissions -p "/fda-weekly-sync"

      - name: Commit changes
        run: |
          git config user.name "FDA Sync Bot"
          git config user.email "bot@noreply.github.com"
          git add scripts/data/banned_recalled_ingredients.json
          git diff --cached --quiet || git commit -m "chore(fda-sync): weekly regulatory update $(date +%Y-%m-%d)"
          git push
```

Add your Anthropic API key in GitHub: Settings → Secrets → `ANTHROPIC_API_KEY`

---

## Manual Trigger (No Scheduling)

For on-demand runs:

```bash
# Step 1: Generate FDA report
python scripts/api_audit/fda_weekly_sync.py --days 7

# Step 2: Open Claude Code and invoke the skill
# In Claude Code terminal:
/fda-weekly-sync

# Or for a broader lookback window (e.g., first run ever):
python scripts/api_audit/fda_weekly_sync.py --days 30
```

---

## Monitoring & Logs

- Sync reports are saved to `scripts/fda_sync_report_YYYYMMDD.json`
- Shell logs at `scripts/fda_sync.log`
- Git history shows every sync run and what changed

To see recent sync history:
```bash
git log --oneline --grep="fda-sync"
```

---

## Installing Dependencies

```bash
pip install requests
```

No other dependencies beyond the Python standard library. The `requests` package is the only external dependency for the FDA sync script.

---

## FDA API Key (Optional — Increases Rate Limits)

Register free at: https://open.fda.gov/apis/authentication/

```bash
# Add to your shell profile or .env
export FDA_API_KEY="your-key-here"
```

The sync script automatically picks it up (add this to `fda_weekly_sync.py` if needed):
```python
api_key = os.environ.get("FDA_API_KEY")
if api_key:
    params["api_key"] = api_key
```
