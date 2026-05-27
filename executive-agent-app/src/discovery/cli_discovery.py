"""
Scans the system for installed CLIs that MegaV can use,
and reports missing ones with install instructions.
"""

import os
import shutil

USEFUL_CLIS = {
    "stripe":    {"why": "Stripe CLI (payment management)",   "install": "winget install Stripe.StripeCLI"},
    "gh":        {"why": "GitHub CLI",                       "install": "winget install GitHub.cli"},
    "ffmpeg":    {"why": "Video/audio processing",           "install": "winget install ffmpeg"},
    "magick":    {"why": "ImageMagick image editing",        "install": "winget install ImageMagick.Q16-HDRI"},
    "pandoc":    {"why": "Document format conversion",       "install": "winget install JohnMacFarlane.Pandoc"},
    "yt-dlp":    {"why": "YouTube download",                 "install": "pip install yt-dlp"},
    "whisper":   {"why": "Audio transcription",              "install": "pip install openai-whisper"},
    "ollama":    {"why": "Local AI models (offline)",        "install": "winget install Ollama.Ollama"},
    "rclone":    {"why": "Cloud storage sync",               "install": "winget install Rclone.Rclone"},
    "tesseract": {"why": "OCR — text from images",           "install": "winget install UB-Mannheim.TesseractOCR"},
    "node":      {"why": "Run MCP servers and JS scripts",   "install": "winget install OpenJS.NodeJS.LTS"},
    "bun":       {"why": "Fast Node.js alternative for MCP", "install": "npm install -g bun"},
    "7z":        {"why": "Archive/compress files",           "install": "winget install 7zip.7zip"},
}

# Known fallback paths for tools that may not be on PATH
_FALLBACK_PATHS = {
    "7z": [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ],
    "tesseract": [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ],
    "magick": [
        r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe",
        r"C:\Program Files\ImageMagick\magick.exe",
    ],
    "stripe": [
        r"C:\Program Files\Stripe\stripe.exe",
        os.path.expanduser(r"~\AppData\Local\stripe\stripe.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Stripe\stripe.exe"),
    ],
}


def _find_cli(name: str) -> str | None:
    """Return path to CLI or None. Checks PATH first, then known fallback locations."""
    found = shutil.which(name)
    if found:
        return found
    for path in _FALLBACK_PATHS.get(name, []):
        if os.path.isfile(path):
            return path
    return None


class CLIDiscovery:

    def scan_installed(self) -> dict:
        return {name: _find_cli(name) for name in USEFUL_CLIS if _find_cli(name)}

    def report_missing(self) -> list:
        installed = self.scan_installed()
        return [
            {"name": n, "why": info["why"], "install": info["install"]}
            for n, info in USEFUL_CLIS.items()
            if n not in installed
        ]

    def full_report(self) -> dict:
        installed = self.scan_installed()
        return {
            "installed":    list(installed.keys()),
            "missing":      self.report_missing(),
            "coverage_pct": round(len(installed) / len(USEFUL_CLIS) * 100),
        }

    def print_report(self) -> None:
        r = self.full_report()
        print(f"\n-- CLI Discovery Report ({r['coverage_pct']}% coverage) --")
        print(f"Installed ({len(r['installed'])}): {', '.join(r['installed'])}")
        print(f"\nMissing ({len(r['missing'])}):")
        for m in r["missing"]:
            print(f"  [X] {m['name']:<12} {m['why']}")
            print(f"             Install: {m['install']}")
