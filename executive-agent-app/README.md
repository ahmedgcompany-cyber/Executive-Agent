# MegaV

A local-first executive AI agent that codes, browses, automates your desktop, manages email, and runs your entire digital workflow — all from one interface.

## Overview

MegaV is built on the foundation of Clawd Code, transformed into a comprehensive local autonomous operator that can:

- **Code & Build**: Generate code, debug, test, and package applications
- **Browse & Automate**: Control web browsers, fill forms, extract data
- **Desktop Control**: Launch and control installed applications
- **Creative Software**: Interface with Photoshop, Illustrator, After Effects, Blender, AutoCAD
- **Email**: Connect Gmail/Outlook/IMAP, read, send, reply, smart inbox classification
- **CRM & Follow-ups**: Contact pipeline management, auto follow-up drafts, lead tracking
- **GitHub**: Create repos, manage issues, commit and push files
- **Social**: Post to LinkedIn, Twitter/X, Instagram; schedule content
- **Agency Library**: 184 specialist agent personalities across 14 domains (engineering, marketing, design, sales, testing, and more)
- **NEXUS Orchestration**: Multi-agent pipeline in three modes — Micro (1–5 days), Sprint (2–6 weeks), Full (12–24 weeks) — with Dev↔QA quality loops
- **Memory & Profiles**: Store your information for automated form filling
- **Workflows**: Record and replay successful procedures
- **Skills**: 51 registered skills including 13 Agency/NEXUS built-in skills + 100+ community skills

## Architecture

```
executive-agent-app/
├── src/
│   ├── agents/           # Specialist agents (10)
│   │   ├── commander_agent.py    # Task routing & orchestration
│   │   ├── coder_agent.py        # Software development
│   │   ├── browser_agent.py      # Web automation
│   │   ├── desktop_agent.py      # Desktop control
│   │   ├── job_agent.py          # Job applications + email integration
│   │   ├── sales_agent.py        # Sales research + CRM integration
│   │   ├── content_agent.py      # Content creation
│   │   ├── skill_agent.py        # Skill management
│   │   ├── social_agent.py       # Social media automation
│   │   └── memory_agent.py       # Memory operations
│   ├── tools_ext/        # Extended tools (10)
│   │   ├── browser_tools.py      # Playwright-based browser control
│   │   ├── form_tools.py         # Intelligent form filling
│   │   ├── desktop_tools.py      # Desktop automation
│   │   ├── vision_tools.py       # Screen analysis
│   │   ├── profile_tools.py      # Profile access
│   │   ├── workflow_tools.py     # Workflow recording
│   │   ├── skill_tools.py        # Skill management
│   │   ├── app_control_tools.py  # App-specific control
│   │   └── social_tools.py       # Social media posting
│   ├── memory/           # Memory storage
│   │   ├── profile_store.py      # User profiles
│   │   ├── workflow_store.py     # Workflow storage
│   │   └── project_store.py      # Project memory
│   ├── integrations/     # Services & app adapters
│   │   ├── credential_store.py   # Encrypted credential vault (Fernet/XOR)
│   │   ├── email_service.py      # IMAP/SMTP multi-account email
│   │   ├── crm_service.py        # Local JSON contact/lead CRM
│   │   ├── github_service.py     # GitHub API (repos, issues, commits)
│   │   ├── photoshop_adapter.py  # Adobe Photoshop
│   │   ├── illustrator_adapter.py# Adobe Illustrator
│   │   ├── aftereffects_adapter.py # Adobe After Effects
│   │   ├── autocad_adapter.py    # AutoCAD
│   │   ├── blender_adapter.py    # Blender
│   │   └── office_adapter.py     # Microsoft Office
│   ├── gui/              # GUI components (6)
│   │   ├── main_window.py        # Main window (6 tabs)
│   │   ├── chat_panel.py         # Chat interface
│   │   ├── task_panel.py         # Task management
│   │   ├── email_tab.py          # Email + Smart Inbox + CRM tab
│   │   ├── social_tab.py         # Social media tab
│   │   └── setup_wizard.py       # First-run setup wizard
│   ├── prompts/          # Agent prompts (9)
│   ├── cli.py            # CLI entry point
│   ├── repl.py           # Interactive REPL
│   └── main.py           # Main entry point
├── skill_engine/         # Skill Engine (9 modules)
│   ├── parser.py         # Skill discovery + 6 built-in email skills
│   ├── selector.py       # Intent matching + cross-system compound patterns
│   ├── executor.py       # Skill execution routing
│   ├── registry.py       # Skill registry
│   ├── orchestrator.py   # Multi-skill orchestration
│   └── schemas.py        # Skill data schemas
├── config/               # Configuration files
├── profiles/             # User data
│   ├── user_profile.json         # Contact info, skills, preferences
│   ├── job_answers.json          # Job application standard answers
│   ├── email_accounts.json       # Connected email accounts (metadata only)
│   ├── social_accounts.json      # Connected social accounts
│   └── github_credentials.json   # GitHub tokens
├── skills/               # Installed community skills (100+)
└── workflows/            # Saved automation workflows
```

## Installation

**Windows (recommended):** Double-click `Install Dependencies.bat` in the `Executive Agent` folder — it installs everything automatically.

```bash
# Manual install
cd executive-agent-app
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

### CLI Mode

```bash
# Start interactive CLI
python -m src.main

# Execute a single goal
python -m src.main --goal "Create a Python script that downloads images"

# Show help
python -m src.main --help
```

### GUI Mode

```bash
# Start GUI application
python -m src.main --gui
```

### REPL Mode

```bash
# Start interactive REPL
python -m src.repl
```

## Configuration

Edit the configuration files in `config/`:

- `settings.yaml` - General application settings
- `models.yaml` - LLM provider configuration
- `permissions.yaml` - Permission settings
- `apps.yaml` - Application paths and settings
- `skills.yaml` - Skill system configuration

## Profile Setup

Edit your profile in `profiles/user_profile.json`:

```json
{
  "name": "Your Name",
  "location": "Your Location",
  "emails": ["your@email.com"],
  "phones": ["+1234567890"],
  "linkedin": "https://linkedin.com/in/yourprofile",
  "job_titles": ["Developer", "Designer"],
  "writing_style": "professional"
}
```

Edit job application answers in `profiles/job_answers.json`.

## Agents

### Commander Agent
Routes tasks to the appropriate specialist agent based on the goal.

### Coder Agent
Handles software development tasks:
- Code generation
- File operations
- Build and test execution
- Debugging

### Browser Agent
Handles web automation:
- Navigate websites
- Fill forms
- Upload files
- Extract data

### Desktop Agent
Handles desktop application control:
- Launch applications
- Control UI elements
- Send keyboard shortcuts
- Capture screenshots

### Job Agent
Handles job applications:
- Match job requirements
- Fill application forms
- Generate cover letters
- Select resume variants

### Content Agent
Handles content creation:
- YouTube descriptions
- Social media posts
- Marketing copy
- Outreach emails

### Sales Agent
Handles sales tasks:
- Market research
- Lead structuring
- Outreach drafting
- Competitor analysis

### Skill Agent
Manages skill lifecycle:
- Search skills
- Download and install
- Update registry
- Enable/disable skills

### Memory Agent
Manages memory operations:
- Profile access
- Workflow retrieval
- Project notes
- Task history

## Tools

### Browser Tools
- `browser_open` - Open browser and navigate to URL
- `browser_click` - Click element
- `browser_type` - Type text into input
- `browser_select` - Select dropdown option
- `browser_upload` - Upload file
- `browser_screenshot` - Take screenshot
- `browser_extract_fields` - Extract form fields

### Desktop Tools
- `launch_application` - Launch app
- `focus_window` - Focus window
- `list_controls` - List UI controls
- `click_control` - Click control
- `type_into_control` - Type into control
- `send_hotkey` - Send keyboard shortcut
- `capture_window` - Capture window screenshot

### Vision Tools
- `capture_screen_region` - Capture screen area
- `compare_screens` - Compare screenshots
- `locate_visual_target` - Find image on screen
- `wait_for_visual_target` - Wait for image

### Profile Tools
- `load_user_profile` - Load profile data
- `get_profile_field` - Get specific field
- `get_job_answer` - Get job answer
- `get_default_resume` - Get resume path

### Workflow Tools
- `start_workflow_recording` - Start recording
- `record_workflow_step` - Record step
- `save_workflow` - Save workflow
- `load_workflow` - Load workflow
- `replay_workflow` - Replay workflow

### Skill Tools
- `search_skill_sources` - Search for skills
- `download_skill` - Download skill
- `install_skill` - Install skill
- `list_skills` - List installed skills
- `uninstall_skill` - Remove skill

## Application Adapters

### Photoshop Adapter
- `open_file` - Open image
- `save_document` - Save document
- `export_document` - Export to format
- `run_action` - Run Photoshop action
- `remove_background` - Remove background
- `resize_image` - Resize image

### Illustrator Adapter
- `open_file` - Open document
- `save_document` - Save document
- `export_document` - Export to format
- `export_social_pack` - Export social media sizes
- `trace_image` - Trace raster to vector

### After Effects Adapter
- `open_file` - Open project
- `render_queue` - Add to render queue
- `render_reel` - Render multiple compositions
- `export_frame` - Export single frame

### Blender Adapter
- `launch` - Launch Blender
- `run_script` - Run Python script
- `render` - Render scene
- `batch_render` - Batch render files
- `export_model` - Export 3D model

### AutoCAD Adapter
- `open_file` - Open drawing
- `save_document` - Save document
- `export_pdf` - Export to PDF
- `plot_drawing` - Plot drawing
- `run_script` - Run AutoCAD script

### Office Adapter
- `open_word_document` - Open Word doc
- `export_word_to_pdf` - Export to PDF
- `open_excel_workbook` - Open Excel file
- `create_excel_chart` - Create chart
- `open_powerpoint_presentation` - Open presentation
- `export_powerpoint_to_pdf` - Export to PDF

## Workflow Recording

Record successful workflows for later replay:

```python
# Start recording
workflow_tools.start_workflow_recording("job_apply_linkedin", "jobs")

# Record steps
workflow_tools.record_workflow_step("browser_open", {"url": "https://linkedin.com/jobs"})
workflow_tools.record_workflow_step("fill_form", {"use_profile": True})

# Save workflow
workflow_tools.save_workflow()

# Replay later
workflow_tools.replay_workflow("job_apply_linkedin", "jobs")
```

## Skill System

Skills are reusable capabilities that can be installed:

```python
# Search for skills
skill_tools.search_skill_sources("job_apply")

# Download and install
skill_tools.download_skill("https://skills.example.com/job_apply.zip")
skill_tools.install_skill("skills/quarantine/job_apply.zip")

# List installed skills
skill_tools.list_skills()

# Use skill
commander.execute_goal("Use job_apply skill for LinkedIn", context)
```

## Development

```bash
# Run tests
pytest tests/

# Format code
black src/
isort src/

# Type check
mypy src/
```

## License

MIT License - See LICENSE file

## Acknowledgments

Built on the foundation of Clawd Code, a Python reimplementation of Claude Code.
