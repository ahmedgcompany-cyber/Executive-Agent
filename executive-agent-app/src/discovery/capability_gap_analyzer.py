"""
Watches task failure history and suggests tools that would fix recurring gaps.
"""

import json
from pathlib import Path
from collections import Counter

TASK_LOG = Path.home() / ".megav" / "task_log.jsonl"

GAP_SUGGESTIONS = {
    "screenshot":  "vision_tools already installed — check VisionTools.capture()",
    "ocr":         "pip install pytesseract + install Tesseract CLI",
    "transcribe":  "pip install openai-whisper",
    "pdf":         "pip install PyMuPDF",
    "video":       "install ffmpeg: winget install ffmpeg",
    "github":      "install gh CLI: winget install GitHub.cli",
    "payment":     "pip install stripe + add STRIPE_API_KEY to config",
    "linkedin":    "LinkedIn API credentials needed in credential_store",
    "database":    "pip install sqlalchemy",
    "docker":      "install Docker Desktop",
    "word":        "pip install python-docx",
    "excel":       "pip install openpyxl",
    "image edit":  "winget install ImageMagick.Q16-HDRI",
    "local model": "install Ollama: winget install Ollama.Ollama",
}


class CapabilityGapAnalyzer:

    def analyze_failures(self) -> dict:
        if not TASK_LOG.exists():
            return {"gaps": [], "total_failures": 0}
        failures = []
        for line in TASK_LOG.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if not e.get("success"):
                    failures.append(e.get("action", "").lower())
            except Exception:
                pass
        hits = Counter()
        for action in failures:
            for kw in GAP_SUGGESTIONS:
                if kw in action:
                    hits[kw] += 1
        gaps = [
            {"pattern": kw, "occurrences": n, "suggestion": GAP_SUGGESTIONS[kw]}
            for kw, n in hits.most_common()
        ]
        return {"total_failures": len(failures), "gaps": gaps}

    def generate_report(self) -> str:
        data = self.analyze_failures()
        if not data["gaps"]:
            return f"No capability gaps found. ({data['total_failures']} tasks analyzed)"
        lines = [f"Capability Gap Report — {data['total_failures']} failed tasks\n"]
        for g in data["gaps"]:
            lines.append(f"  [{g['occurrences']}x] '{g['pattern']}' tasks failing")
            lines.append(f"         Fix: {g['suggestion']}\n")
        return "\n".join(lines)
