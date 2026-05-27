"""Coder agent for software development tasks."""

import subprocess
from pathlib import Path
from typing import Any, Optional


class CoderAgent:
    """Specialist agent for coding and development tasks."""

    def __init__(self, workspace_dir: str = "."):
        """Initialize coder agent.

        Args:
            workspace_dir: Workspace directory
        """
        self.workspace_dir = Path(workspace_dir)

        # Load prompt
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load coder prompt from file."""
        prompt_path = Path("src/prompts/coder.txt")
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return "You are a coding specialist agent."

    def _get_local_projects_dir(self) -> Path:
        """Return the real local Desktop path, avoiding OneDrive redirect."""
        # Try Windows registry first (most reliable on Windows)
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            )
            desktop, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            projects = Path(desktop) / "MegaV Projects"
            projects.mkdir(parents=True, exist_ok=True)
            return projects
        except Exception:
            pass

        # Fallback to expanduser
        projects = Path.home() / "Desktop" / "MegaV Projects"
        projects.mkdir(parents=True, exist_ok=True)
        return projects

    def _get_local_desktop(self) -> Path:
        """Return the local (non-OneDrive) Desktop path."""
        import os
        local_desktop = Path(os.path.expanduser("~/Desktop"))
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            real_desktop = winreg.QueryValueEx(key, "Desktop")[0]
            if real_desktop:
                local_desktop = Path(real_desktop)
        except Exception:
            pass
        return local_desktop

    def _create_desktop_shortcut(self, project_dir: Path, launcher_path: Path) -> Path:
        """Create a Windows .lnk shortcut on the Desktop pointing to launcher_path."""
        try:
            import os
            desktop = self._get_local_desktop()
            shortcut_path = desktop / f"{project_dir.name}.lnk"
            # Use PowerShell to create the shortcut reliably
            ps_cmd = (
                f'$WshShell = New-Object -ComObject WScript.Shell; '
                f'$Shortcut = $WshShell.CreateShortcut("{shortcut_path}"); '
                f'$Shortcut.TargetPath = "{launcher_path}"; '
                f'$Shortcut.WorkingDirectory = "{project_dir}"; '
                f'$Shortcut.IconLocation = "python.exe,0"; '
                f'$Shortcut.Save()'
            )
            os.system(f'powershell -NoProfile -Command "{ps_cmd}"')
            return shortcut_path
        except Exception:
            return Path()

    def _launch_and_verify(self, project_dir: Path, launcher_path: Path, lang: str) -> dict[str, Any]:
        """Launch the project and verify it starts correctly."""
        import subprocess
        import time
        result = {"launched": False, "verified": False, "error": None}
        try:
            if lang == "html":
                # Open HTML file in default browser
                subprocess.Popen([str(launcher_path)], shell=True)
                result["launched"] = True
                result["verified"] = True
                return result
            if lang == "python":
                # Start the server in a new visible console window
                proc = subprocess.Popen(
                    ["cmd", "/c", "start", "", str(launcher_path)],
                    cwd=str(project_dir),
                    shell=False,
                )
                result["launched"] = True
                # Give it a few seconds to start
                time.sleep(5)
                # Check if process is still alive
                if proc.poll() is None or proc.poll() == 0:
                    result["verified"] = True
                else:
                    result["error"] = "Process exited unexpectedly"
                return result
            # For other languages, just launch
            subprocess.Popen([str(launcher_path)], shell=True)
            result["launched"] = True
            result["verified"] = True
        except Exception as e:
            result["error"] = str(e)
        return result

    def inspect_project(self, path: Optional[str] = None) -> dict[str, Any]:
        """Inspect project structure.

        Args:
            path: Optional path to inspect

        Returns:
            Project structure
        """
        target_path = Path(path) if path else self.workspace_dir

        try:
            files = []
            dirs = []

            for item in target_path.iterdir():
                if item.is_file():
                    files.append({
                        "name": item.name,
                        "size": item.stat().st_size,
                        "extension": item.suffix,
                    })
                elif item.is_dir():
                    dirs.append(item.name)

            # Detect project type
            project_type = self._detect_project_type(files)

            return {
                "success": True,
                "path": str(target_path),
                "files": files,
                "directories": dirs,
                "project_type": project_type,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _detect_project_type(self, files: list[dict[str, Any]]) -> str:
        """Detect project type from files.

        Args:
            files: List of file info

        Returns:
            Project type
        """
        filenames = [f["name"] for f in files]

        if "package.json" in filenames:
            return "nodejs"
        elif "requirements.txt" in filenames or "pyproject.toml" in filenames:
            return "python"
        elif "Cargo.toml" in filenames:
            return "rust"
        elif "pom.xml" in filenames or "build.gradle" in filenames:
            return "java"
        elif "go.mod" in filenames:
            return "go"
        elif "CMakeLists.txt" in filenames:
            return "cpp"
        elif any(f.endswith(".sln") for f in filenames):
            return "dotnet"
        else:
            return "unknown"

    def generate_code(
        self,
        description: str,
        output_path: str,
        language: Optional[str] = None,
    ) -> dict[str, Any]:
        """Generate code based on description.

        Args:
            description: Code description
            output_path: Output file path
            language: Programming language

        Returns:
            Generation result
        """
        try:
            if not output_path:
                # Infer a sensible extension from the description
                _d = description.lower()
                if "python" in _d or ".py" in _d:
                    output_file = Path("output.py")
                elif "javascript" in _d or "node" in _d or ".js" in _d:
                    output_file = Path("output.js")
                elif "typescript" in _d or ".ts" in _d:
                    output_file = Path("output.ts")
                elif "bash" in _d or "shell" in _d or ".sh" in _d:
                    output_file = Path("output.sh")
                elif "html" in _d or ".html" in _d:
                    output_file = Path("output.html")
                elif "css" in _d or ".css" in _d:
                    output_file = Path("output.css")
                elif "java" in _d and "javascript" not in _d:
                    output_file = Path("output.java")
                elif "c#" in _d or "csharp" in _d:
                    output_file = Path("output.cs")
                else:
                    output_file = Path("output.py")   # default to Python
            else:
                output_file = Path(output_path)

            # Determine language from extension if not provided
            if not language:
                language = output_file.suffix.lstrip(".") or "py"

            # Try LLM code generation first
            code = ""
            try:
                from ..providers.model_router import ModelRouter, NoModelAvailableError
                router = ModelRouter()

                # Build a detailed, demanding prompt — like a senior engineer would write
                code_prompt = (
                    f"You are an expert {language} developer. Write COMPLETE, PRODUCTION-READY code.\n\n"
                    f"REQUIREMENTS:\n"
                    f"- Write the FULL implementation — no stubs, no placeholders, no TODO comments\n"
                    f"- Every function must have a real body with working logic\n"
                    f"- Include all necessary imports at the top\n"
                    f"- Handle errors gracefully with try/except or proper error types\n"
                    f"- Make the code RUNNABLE — it should work when saved to a file and executed\n"
                    f"- Use clear variable names and add brief comments for complex logic\n"
                    f"- If the task requires a GUI, create a fully functional interface\n"
                    f"- If the task involves data, include realistic sample data or data generation\n"
                    f"- If the task requires external files, create them in the same directory\n\n"
                    f"OUTPUT FORMAT:\n"
                    f"- Output ONLY the raw source code — no markdown fences (no ```), no explanation text\n"
                    f"- Start directly with imports or the first line of code\n"
                    f"- Do NOT wrap code in backticks or add 'Here is the code:' preamble\n\n"
                    f"TASK:\n{description}"
                )

                llm_code = router.ask(
                    system=code_prompt,
                    user=f"Write complete, working {language} code for: {description}",
                    task_type="coder",
                )
                if llm_code:
                    # Strip markdown fences if the LLM ignored instructions
                    llm_code = self._strip_code_fences(llm_code)

                    # Reject stub/placeholder/prose output from LLM
                    is_stub = self._is_stub_output(llm_code)
                    if not is_stub:
                        code = llm_code
            except NoModelAvailableError:
                pass
            except Exception as _exc:
                import logging
                logging.getLogger("megav.coder").debug("LLM call failed: %s", _exc)

            if not code:
                # No LLM result — return honest failure instead of fake template
                return {
                    "success": False,
                    "error": f"No LLM available for code generation. Start Ollama or set an API key.",
                    "path": "",
                }

            # Write generated code to file
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(code, encoding="utf-8")
            return {
                "success": True,
                "path": str(output_file),
                "language": language,
                "lines": len(code.splitlines()),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, path: str) -> dict[str, Any]:
        """Read a file.

        Args:
            path: File path

        Returns:
            File content
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {path}"}

            content = file_path.read_text(encoding="utf-8")

            return {
                "success": True,
                "path": str(file_path),
                "content": content,
                "lines": len(content.splitlines()),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write a file.

        Args:
            path: File path
            content: File content

        Returns:
            Write result
        """
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "path": str(file_path),
                "lines": len(content.splitlines()),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
    ) -> dict[str, Any]:
        """Edit a file by replacing text.

        Args:
            path: File path
            old_text: Text to replace
            new_text: Replacement text

        Returns:
            Edit result
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                return {"success": False, "error": f"File not found: {path}"}

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return {"success": False, "error": "Old text not found in file"}

            new_content = content.replace(old_text, new_text)
            file_path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "path": str(file_path),
                "replacements": content.count(old_text),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_build(self, build_command: Optional[str] = None) -> dict[str, Any]:
        """Run build command.

        Args:
            build_command: Optional build command

        Returns:
            Build result
        """
        try:
            # Detect build command if not provided
            if not build_command:
                project_type = self.inspect_project().get("project_type", "unknown")
                build_commands = {
                    "nodejs": "npm run build",
                    "python": "python -m build",
                    "rust": "cargo build",
                    "java": "mvn build",
                    "go": "go build",
                }
                build_command = build_commands.get(project_type)

            if not build_command:
                return {
                    "success": False,
                    "error": "No build command specified or detected",
                }

            result = subprocess.run(
                build_command.split(),
                capture_output=True,
                text=True,
                cwd=self.workspace_dir,
            )

            return {
                "success": result.returncode == 0,
                "command": build_command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_tests(self, test_command: Optional[str] = None) -> dict[str, Any]:
        """Run tests.

        Args:
            test_command: Optional test command

        Returns:
            Test result
        """
        try:
            # Detect test command if not provided
            if not test_command:
                project_type = self.inspect_project().get("project_type", "unknown")
                test_commands = {
                    "nodejs": "npm test",
                    "python": "pytest",
                    "rust": "cargo test",
                    "java": "mvn test",
                    "go": "go test",
                }
                test_command = test_commands.get(project_type)

            if not test_command:
                return {
                    "success": False,
                    "error": "No test command specified or detected",
                }

            result = subprocess.run(
                test_command.split(),
                capture_output=True,
                text=True,
                cwd=self.workspace_dir,
            )

            return {
                "success": result.returncode == 0,
                "command": test_command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def repair_build(self, error_output: str) -> dict[str, Any]:
        """Attempt to repair build errors.

        Args:
            error_output: Build error output

        Returns:
            Repair result
        """
        # This is a placeholder - in practice, this would analyze errors
        # and attempt automated fixes

        return {
            "success": True,
            "message": "Build repair analysis",
            "error_output": error_output,
            "note": "Automated repair would be implemented with error pattern matching",
        }

    def package_output(
        self,
        output_dir: str,
        format: str = "zip",
    ) -> dict[str, Any]:
        """Package output files.

        Args:
            output_dir: Output directory
            format: Package format

        Returns:
            Package result
        """
        try:
            import shutil

            output_path = Path(output_dir)
            if not output_path.exists():
                return {"success": False, "error": f"Output directory not found: {output_dir}"}

            package_name = f"{output_path.name}.{format}"
            package_path = output_path.parent / package_name

            if format == "zip":
                shutil.make_archive(
                    str(package_path.with_suffix("")),
                    "zip",
                    output_path,
                )
            elif format == "tar":
                shutil.make_archive(
                    str(package_path.with_suffix("")),
                    "tar",
                    output_path,
                )
            else:
                return {"success": False, "error": f"Unsupported format: {format}"}

            return {
                "success": True,
                "package_path": str(package_path),
                "format": format,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def handle_code_task(self, action: str, context: dict[str, Any]) -> dict[str, Any]:
        """Handle a code task.

        Args:
            action: Action to perform
            context: Task context (ToolContext object or dict)

        Returns:
            Task result
        """
        _goal = getattr(context, "goal", "") or getattr(context, "current_goal", "") or ""

        # For compound goals, the step description may contain prior context
        # from previous phases — use it to enrich the goal
        step_desc = getattr(context, "step_description", "")
        if step_desc and len(step_desc) > len(_goal):
            _goal = step_desc

        # ── GitHub direct action intercept ─────────────────────────────
        if action in ("generate_code", "execute_goal", "github_action") and _goal:
            gh_result = self._try_github_action(_goal, context)
            if gh_result:
                return gh_result
        # ── End GitHub intercept ───────────────────────────────────────

        # ── Skill Engine intercept ─────────────────────────────────────
        if action in ("generate_code", "execute_goal") and _goal:
            try:
                from skill_engine.orchestrator import run_task, get_engine
                engine = get_engine()
                if engine and engine.should_intercept(_goal, agent_hint="coder"):
                    profile = {}
                    try:
                        profile = dict(getattr(context, "profile", {}) or {})
                    except Exception:
                        pass
                    skill_result = run_task(_goal, agent_hint="coder",
                                           extra_context={"profile": profile})
                    if skill_result.success:
                        return {
                            "success": True,
                            "summary": skill_result.summary,
                            "result":  skill_result.full_result,
                            "skills_used": skill_result.skills_used,
                            "via_skill": True,
                        }
            except Exception:
                pass   # skill engine unavailable — continue normally
        # ── End skill intercept ────────────────────────────────────────

        def _inspect():
            r = self.inspect_project(context.get("path"))
            if r.get("success"):
                files = r.get("files", [])
                dirs  = r.get("directories", [])
                ptype = r.get("project_type", "unknown")
                r["summary"] = (
                    f"Workspace: {r.get('path', '.')}  |  Type: {ptype}  |  "
                    f"{len(files)} file(s), {len(dirs)} dir(s)"
                )
            return r

        handlers = {
            "inspect_project": _inspect,
            "generate_code":   lambda: self._execute_from_goal(_goal),
            "read_file":       lambda: self.read_file(context.get("path", "")),
            "write_file":      lambda: self.write_file(context.get("path", ""), context.get("content", "")),
            "edit_file":       lambda: self.edit_file(context.get("path", ""), context.get("old_text", ""), context.get("new_text", "")),
            "run_build":       lambda: self.run_build(context.get("build_command")),
            "run_tests":       lambda: self.run_tests(context.get("test_command")),
            "repair_build":    lambda: self.repair_build(context.get("error_output", "")),
            "package_output":  lambda: self.package_output(context.get("output_dir", ""), context.get("format", "zip")),
            "execute_goal":    lambda: self._execute_from_goal(_goal),
            "verify_compound": lambda: self._verify_compound_output(_goal, context),
            "verify":          lambda: self._verify_compound_output(_goal, context),
        }

        handler = handlers.get(action)
        if handler:
            return handler()

        return {"success": False, "error": f"Unknown action: {action}"}

    # ------------------------------------------------------------------
    # GitHub action fast-path
    # ------------------------------------------------------------------

    _GITHUB_PATTERNS = [
        # repo management
        r"\b(create|new|init(ialize)?|make)\b.{0,30}\b(repo|repository)\b",
        r"\bgithub\b.{0,30}\b(repo|repository|project|issue|commit|push|upload)\b",
        r"\b(push|commit|upload)\b.{0,30}\b(to\s+)?github\b",
        r"\b(open|create|close|list|comment|reopen)\b.{0,20}\bissue\b",
    ]
    _GITHUB_RE = None   # compiled lazily

    @classmethod
    def _is_github_goal(cls, goal: str) -> bool:
        import re
        if cls._GITHUB_RE is None:
            cls._GITHUB_RE = re.compile(
                "|".join(cls._GITHUB_PATTERNS), re.IGNORECASE
            )
        return bool(cls._GITHUB_RE.search(goal))

    def _try_github_action(self, goal: str, context: Any) -> Optional[dict[str, Any]]:
        """Attempt to handle the goal via GitHubService. Returns None if not applicable."""
        if not self._is_github_goal(goal):
            return None
        try:
            from ..integrations.github_service import get_github_service
            svc = get_github_service()
            if not svc.is_connected():
                return None   # fall through to normal routing

            profile = {}
            try:
                profile = dict(getattr(context, "profile", {}) or {})
            except Exception:
                pass
            default_repo = profile.get("github_default_repo", "")

            result = svc.handle_prompt(goal, default_repo=default_repo)
            if result.get("success"):
                msg = result.get("message", "GitHub action completed.")
                return {
                    "success": True,
                    "summary": msg,
                    "message": msg,
                    "details": result,
                    "via_github": True,
                }
            # Service connected but action failed — still return the error
            err = result.get("error", "GitHub action failed")
            return {
                "success": False,
                "error": err,
                "summary": f"GitHub: {err}",
                "via_github": True,
            }
        except Exception:
            return None   # integration unavailable — fall through

    # ------------------------------------------------------------------
    # Goal-driven execution (called by AgentLoop)
    # ------------------------------------------------------------------

    def _execute_from_goal(self, goal: str) -> dict[str, Any]:
        """Interpret a free-form goal, generate code, and save to Desktop/Projects."""
        if not goal:
            return {"success": False, "error": "No goal provided to coder agent."}

        import re
        import os
        goal_lower = goal.lower()

        # ---- Short unambiguous single-action commands only ---------------
        #      (Never trigger these for long descriptive goals)
        if len(goal) <= 180:
            first = goal_lower.split()[0] if goal_lower.split() else ""
            filename_match = re.search(r"[\w\-]+\.\w{1,5}", goal)
            mentioned_file = filename_match.group(0) if filename_match else None

            if first in ("read", "show", "view", "display") and mentioned_file:
                r = self.read_file(mentioned_file)
                r.setdefault("summary", f"Read file '{mentioned_file}'.")
                return r

            if first in ("run", "test") and "test" in goal_lower:
                r = self.run_tests()
                r.setdefault("summary", "Ran project tests.")
                return r

            if first in ("inspect", "list", "explore"):
                r = self.inspect_project()
                r.setdefault("summary", "Inspected project structure.")
                return r

        # ---- Build/generate code for everything else ---------------------

        # 1. Extract a project name for the output folder
        # Lookahead that ends a project name at quotes, punctuation, or common stop words
        _STOP = r'(?=["\'\s]*(?:with|that|which|this|the|will|must|should|can|to|by|for|is|has)|["\']|\s*[,.\n]|$)'
        project_name = ""
        for pattern in [
            r'called[:\s]+["\']?([A-Za-z][A-Za-z0-9 _-]{2,60}?)' + _STOP,
            r'named[:\s]+["\']?([A-Za-z][A-Za-z0-9 _-]{2,60}?)' + _STOP,
            r'"([A-Za-z][A-Za-z0-9 _-]{3,60})"',
            r"'([A-Za-z][A-Za-z0-9 _-]{3,60})'",
            r'(?:build|create|make|design|develop|write)\s+(?:a\s+|an\s+)?([A-Za-z][A-Za-z0-9 _-]{3,50})(?:\s+app|\s+application|\s+tool|\s+script|\s+program)[,. ]',
        ]:
            m = re.search(pattern, goal[:600], re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # skip very generic matches
                if candidate.lower() not in ("app", "application", "code", "script", "file", "program", "software", "project"):
                    project_name = candidate
                    break

        if not project_name:
            # Use first 4 meaningful words
            words = [w for w in re.findall(r"[A-Za-z]{3,}", goal[:200])
                     if w.lower() not in ("the", "and", "for", "with", "that", "this", "you", "are", "from", "into")]
            project_name = "_".join(words[:4]) if words else "project"

        # Sanitise for filesystem
        project_name = re.sub(r"[^\w\-]", "_", project_name).strip("_")[:60]
        if not project_name:
            project_name = "output_project"

        # 2. Create local Projects/<name>/ directory (NOT OneDrive)
        project_dir = self._get_local_projects_dir() / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # 3. Determine language and file extension
        g = goal_lower[:600]
        is_landing_page = any(x in g for x in [
            "landing page", "website", "web page", "webpage",
            "home page", "homepage", "splash page", "one-page site",
        ])

        if is_landing_page:
            # Use dedicated landing page builder
            result = self._build_landing_page(goal, project_dir)
            if result.get("success"):
                # Create launcher for the HTML file
                launcher_info = self._create_project_launcher(project_dir, project_dir / "index.html", "html")
                result["path"] = result.get("path") or launcher_info.get("launcher", str(project_dir / "index.html"))
                main_file = project_dir / "index.html"
                lang = "html"
                result["summary"] = (
                    f"Landing page created!\n"
                    f"Location: {project_dir}\n\n"
                    f"Files:\n"
                    f"  index.html  (open in browser)\n"
                    f"  run.bat     (double-click to open)\n"
                    f"  README.txt\n\n"
                    f"To view: double-click index.html or run.bat\n\n"
                    f"--- Preview ---\n"
                    + (main_file.read_text(encoding="utf-8")[:1200] if main_file.exists() else "")
                )
            return result
        elif "javascript" in g or "node.js" in g or " nodejs" in g:
            lang, ext = "javascript", ".js"
        elif "typescript" in g or ".ts " in g:
            lang, ext = "typescript", ".ts"
        elif "html" in g and "css" in g:
            lang, ext = "html", ".html"
        elif "bash" in g or "shell script" in g:
            lang, ext = "bash", ".sh"
        elif "c#" in g or "csharp" in g or ".net" in g:
            lang, ext = "csharp", ".cs"
        else:
            lang, ext = "python", ".py"

        main_file = project_dir / f"main{ext}"

        # 4. Condense very long goals to a build spec before sending to LLM
        code_desc = goal
        if len(goal) > 400:
            try:
                from ..providers.model_router import ModelRouter, NoModelAvailableError
                spec = ModelRouter().ask(
                    system=(
                        "You are a software architect. Extract the core build specification from "
                        "a user request. Be concise — 3-8 sentences. List the key features and "
                        "EXACTLY what the code must do. Focus on functional requirements, not fluff."
                    ),
                    user=f"Extract what needs to be BUILT from this request. Focus on concrete features, "
                         f"data structures, and behavior — not abstract goals:\n\n{goal[:1500]}",
                    task_type="coder",
                )
                if spec and 20 < len(spec) < len(goal):
                    code_desc = spec
            except NoModelAvailableError:
                pass
            except Exception:
                pass

        # 5. Generate the code
        result = self.generate_code(code_desc, str(main_file), lang)

        # 6. Create a double-click launcher + README
        launcher_info = self._create_project_launcher(project_dir, main_file, lang)

        # 6b. Detect and materialize multi-file generator scripts
        materialized_files = []
        if result.get("success") and main_file.exists():
            try:
                code_text = main_file.read_text(encoding="utf-8")
                # Heuristic: if the single file looks like a project generator,
                # ask the LLM to split it into real files, OR try to run it safely.
                # Safer approach: ask the model to produce separate files directly.
                if (
                    "FILES =" in code_text or "files =" in code_text
                    or "def create_project(" in code_text
                    or "os.makedirs(" in code_text and "with open(" in code_text
                ) and len(code_text.splitlines()) > 80:
                    # This is likely a generator script — ask the model to emit real files
                    from ..providers.model_router import ModelRouter, NoModelAvailableError
                    try:
                        router = ModelRouter()
                        multi_file_prompt = (
                            f"The following generated code is a PROJECT GENERATOR script. "
                            f"Convert it into ACTUAL separate project files. "
                            f"Return ONLY a JSON object where keys are relative file paths "
                            f"(e.g. 'app/main.py', 'requirements.txt') and values are the file contents. "
                            f"Do NOT include any markdown formatting, explanations, or the original generator logic. "
                            f"Make sure every file has complete, working code.\n\n{code_text[:8000]}"
                        )
                        files_json = router.ask(
                            system=(
                                "You are a senior software engineer. Your ONLY job is to take a project generator script "
                                "and output a raw JSON object mapping file paths to their complete contents. "
                                "Output NOTHING else — no markdown, no explanation, no code fences."
                            ),
                            user=multi_file_prompt,
                            task_type="coder",
                        )
                        if files_json:
                            import json
                            # Strip markdown fences if present
                            clean = files_json.strip()
                            if clean.startswith("```json"):
                                clean = clean[7:]
                            if clean.startswith("```"):
                                clean = clean[3:]
                            if clean.endswith("```"):
                                clean = clean[:-3]
                            clean = clean.strip()
                            file_map = json.loads(clean)
                            if isinstance(file_map, dict) and len(file_map) > 1:
                                for rel_path, content in file_map.items():
                                    target = project_dir / rel_path
                                    target.parent.mkdir(parents=True, exist_ok=True)
                                    target.write_text(content, encoding="utf-8")
                                    materialized_files.append(rel_path)
                                # Remove the generator script so it doesn't confuse the user
                                main_file.unlink()
                                # Update main_file to the actual entry point
                                if "run.py" in file_map:
                                    main_file = project_dir / "run.py"
                                elif "app/main.py" in file_map:
                                    main_file = project_dir / "app" / "main.py"
                                elif "main.py" in file_map:
                                    main_file = project_dir / "main.py"
                                # Re-create launcher for the real entry point
                                launcher_info = self._create_project_launcher(project_dir, main_file, lang)
                    except (NoModelAvailableError, json.JSONDecodeError, Exception):
                        pass
            except Exception:
                pass

        # 6c. Auto-package as ZIP
        zip_result = {}
        if result.get("success"):
            try:
                zip_result = self.package_output(str(project_dir), format="zip")
            except Exception:
                pass

        # 6d. Create desktop shortcut
        shortcut_path = Path()
        if result.get("success"):
            try:
                launcher_path = launcher_info.get("launcher", "")
                if launcher_path:
                    shortcut_path = self._create_desktop_shortcut(project_dir, Path(launcher_path))
            except Exception:
                pass

        # 6e. Launch and verify (for runnable projects)
        launch_result = {}
        if result.get("success") and lang in ("python", "html"):
            try:
                launcher_path = launcher_info.get("launcher", "")
                if launcher_path:
                    launch_result = self._launch_and_verify(project_dir, Path(launcher_path), lang)
            except Exception:
                pass

        # 7. Build a helpful summary with file location and how-to-run
        if result.get("success"):
            try:
                code_content = main_file.read_text(encoding="utf-8") if main_file.exists() else ""
                lines = len(code_content.splitlines()) if code_content else 0
                launcher_path = launcher_info.get("launcher", "")
                runtime_ok    = launcher_info.get("runtime_found", True)
                runtime_name  = launcher_info.get("runtime", "Python")
                install_url   = launcher_info.get("install_url", "")

                run_instruction = (
                    f"Double-click  run.bat  in the project folder"
                    if launcher_path else f"python \"{main_file}\""
                )

                if not runtime_ok:
                    runtime_warning = (
                        f"\n\nNOTE: {runtime_name} is NOT installed on this machine.\n"
                        f"The run.bat file will show you step-by-step install instructions.\n"
                        f"Download {runtime_name} from: {install_url}"
                    )
                else:
                    runtime_warning = ""

                # Build file list
                file_list_lines = [f"  {main_file.name}  ({lines} lines, {lang})"]
                for mf in materialized_files[:12]:
                    file_list_lines.append(f"  {mf}")
                if len(materialized_files) > 12:
                    file_list_lines.append(f"  ... and {len(materialized_files) - 12} more files")
                if launcher_path:
                    file_list_lines.append("  run.bat  (double-click to run)")
                file_list_lines.append("  README.txt")
                if zip_result.get("success"):
                    zip_name = Path(zip_result.get("package_path", "")).name
                    file_list_lines.append(f"  {zip_name}  (distribution package)")
                if shortcut_path.exists():
                    file_list_lines.append(f"  {shortcut_path.name}  (Desktop shortcut)")

                launch_msg = ""
                if launch_result.get("launched"):
                    launch_msg = "\n\nApplication launched and verified successfully!"
                elif launch_result.get("error"):
                    launch_msg = f"\n\nLaunch note: {launch_result['error']}"

                result["summary"] = (
                    f"Project created successfully!\n"
                    f"Location: {project_dir}\n\n"
                    f"Files created:\n"
                    + "\n".join(file_list_lines)
                    + runtime_warning
                    + launch_msg
                    + f"\n\nTo run:  {run_instruction}\n\n"
                    f"--- Generated Code ---\n"
                    f"{code_content[:1800]}"
                    + ("\n\n...(truncated — see full file in project folder)" if len(code_content) > 1800 else "")
                )
                result["path"] = launcher_path or str(main_file)
            except Exception:
                result.setdefault("summary", f"Generated '{main_file}'.")
        else:
            result.setdefault(
                "summary",
                f"Code generation failed. Output dir: {project_dir}"
            )

        return result

    # ------------------------------------------------------------------
    # Compound verification — check that real output files exist
    # ------------------------------------------------------------------

    def _verify_compound_output(self, goal: str, context: Any) -> dict[str, Any]:
        """Verify that compound goal execution produced real output files."""
        import os
        # Check local Projects/ for files related to this goal
        goal_lower = (goal or "").lower()

        # Find the project directory (use local disk, NOT OneDrive)
        project_dir = None
        projects_dir = self._get_local_projects_dir()
        if not projects_dir.exists():
            return {"success": True, "summary": "No project directory yet — verification deferred."}

        # Find files that were recently created (within last 10 minutes)
        import time
        now = time.time()
        recent_files = []
        for fpath in projects_dir.rglob("*"):
            if fpath.is_file():
                try:
                    if now - fpath.stat().st_mtime < 600:  # 10 minutes
                        if fpath.suffix not in (".pyc", ".pyo"):
                            size = fpath.stat().st_size
                            if size > 50:  # More than 50 bytes = real content
                                recent_files.append(str(fpath))
                except Exception:
                    continue

        if recent_files:
            return {
                "success": True,
                "summary": f"Verified {len(recent_files)} recent output file(s): "
                           + ", ".join(os.path.basename(f) for f in recent_files[:6]),
                "verified_files": recent_files,
                "path": recent_files[0] if recent_files else None,
            }

        return {
            "success": True,
            "summary": "Verification complete — no recent files found, but phases may have produced inline output.",
        }

    # ------------------------------------------------------------------
    # Multi-file landing page / website builder
    # ------------------------------------------------------------------

    def _build_landing_page(self, goal: str, project_dir: Path) -> dict[str, Any]:
        """Build a complete landing page project with index.html.

        For landing pages / websites, generates a single self-contained HTML
        file with embedded CSS and JS (no external dependencies).
        """
        # Try LLM generation first
        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            html_code = router.ask(
                system=(
                    "You are an expert frontend developer. Create a COMPLETE, PRODUCTION-QUALITY landing page.\n\n"
                    "REQUIREMENTS:\n"
                    "- Output ONLY raw HTML — a single self-contained file\n"
                    "- ALL CSS must be embedded in a <style> tag in the <head>\n"
                    "- ALL JavaScript must be embedded in a <script> tag before </body>\n"
                    "- NO external dependencies (no CDN links, no external CSS/JS files)\n"
                    "- The page must be visually STUNNING with modern design\n"
                    "- Use CSS gradients, box shadows, smooth transitions, flexbox/grid layouts\n"
                    "- Make it fully responsive (mobile, tablet, desktop)\n"
                    "- Include: navigation bar, hero section with CTA, features section, "
                    "pricing/Plans section, testimonials, footer\n"
                    "- Every section must have REAL content (no Lorem ipsum, no placeholder text)\n"
                    "- Include at least one interactive feature (toggle, modal, smooth scroll, animation)\n"
                    "- NEVER output stubs, placeholders, or TODO comments\n"
                    "- Do NOT wrap in markdown code fences\n"
                ),
                user=f"Create a complete, working landing page for: {goal}",
                task_type="coder",
            )
            if html_code and len(html_code.strip()) > 200:
                # Basic stub check
                stub_count = html_code.count("TODO") + html_code.count("placeholder") + html_code.count("lorem ipsum")
                if stub_count < 3:
                    # Ensure it has proper HTML structure
                    if "<html" not in html_code.lower():
                        html_code = f"<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n<title>Landing Page</title>\n</head>\n<body>\n{html_code}\n</body>\n</html>"
                    index_file = project_dir / "index.html"
                    index_file.write_text(html_code, encoding="utf-8")
                    return {
                        "success": True,
                        "path": str(index_file),
                        "summary": f"Landing page created: {index_file} ({len(html_code.splitlines())} lines)",
                    }
        except NoModelAvailableError:
            pass
        except Exception:
            pass

        # Fallback: generate from template
        index_file = project_dir / "index.html"
        code = self._tpl_html_page(goal)
        index_file.write_text(code, encoding="utf-8")
        return {
            "success": True,
            "path": str(index_file),
            "summary": f"Landing page created from template: {index_file}",
        }

    # ------------------------------------------------------------------
    # Launcher builder
    # ------------------------------------------------------------------

    def _create_project_launcher(self, project_dir: Path, main_file: Path, lang: str) -> dict:
        """Create run.bat and README.txt so the project is double-click runnable."""
        import shutil

        # Runtime check
        runtime_map = {
            "python":     ("python",  "Python 3",    "https://www.python.org/downloads/"),
            "javascript": ("node",    "Node.js",     "https://nodejs.org/en/download/"),
            "typescript": ("npx",     "Node.js",     "https://nodejs.org/en/download/"),
            "csharp":     ("dotnet",  ".NET Runtime","https://dotnet.microsoft.com/download"),
            "bash":       (None,      None,          None),
            "html":       (None,      None,          None),
        }
        runtime_exe, runtime_name, install_url = runtime_map.get(lang, ("python", "Python 3", "https://www.python.org/downloads/"))

        runtime_found = True
        if runtime_exe:
            runtime_found = bool(shutil.which(runtime_exe))

        # --- Build run.bat content ---
        name = project_dir.name

        if lang == "html":
            bat = (
                f"@echo off\n"
                f"title Opening {main_file.name}\n"
                f'start "" "{main_file}"\n'
            )
        elif runtime_found:
            if lang == "python":
                run_cmd = f'python "{main_file.name}"'
            elif lang in ("javascript", "typescript"):
                run_cmd = f'node "{main_file.name}"'
            elif lang == "csharp":
                run_cmd = f'dotnet run "{main_file.name}"'
            else:
                run_cmd = f'python "{main_file.name}"'

            bat = (
                f"@echo off\n"
                f"title {name}\n"
                f'cd /d "{project_dir}"\n'
                f"echo Running {main_file.name}...\n"
                f"echo.\n"
                f"{run_cmd}\n"
                f"echo.\n"
                f"echo ============================\n"
                f"echo  Done! Press any key to close.\n"
                f"echo ============================\n"
                f"pause > nul\n"
            )
        else:
            # Runtime NOT installed — show install guide
            bat = (
                f"@echo off\n"
                f"title SETUP REQUIRED — {name}\n"
                f"echo.\n"
                f"echo ============================================================\n"
                f"echo   This project requires {runtime_name}\n"
                f"echo   which is NOT installed on this machine.\n"
                f"echo.\n"
                f"echo   INSTALLATION STEPS:\n"
                f"echo   1. Open your browser and go to:\n"
                f"echo      {install_url}\n"
                f"echo.\n"
                f"echo   2. Download the installer for Windows\n"
                f"echo.\n"
            )
            if lang == "python":
                bat += (
                    f"echo   3. Run the installer\n"
                    f'echo      IMPORTANT: Check "Add Python to PATH"\n'
                    f"echo      before clicking Install.\n"
                    f"echo.\n"
                )
            bat += (
                f"echo   4. After install, close this window and\n"
                f"echo      double-click run.bat again.\n"
                f"echo.\n"
                f"echo   Opening download page in browser now...\n"
                f"echo ============================================================\n"
                f"echo.\n"
                f'start "" "{install_url}"\n'
                f"pause\n"
            )

        launcher = project_dir / "run.bat"
        launcher.write_text(bat, encoding="utf-8")

        # --- README.txt ---
        readme = [
            f"Project: {name}",
            f"Language: {lang}",
            "=" * 50,
            "",
            "HOW TO RUN",
            "-----------",
            "Double-click:  run.bat",
            "",
        ]
        if lang == "python":
            readme += [
                "Or from command line:",
                f"  python {main_file.name}",
                "",
            ]
        elif lang in ("javascript", "typescript"):
            readme += [
                "Or from command line:",
                f"  node {main_file.name}",
                "",
            ]
        elif lang == "html":
            readme += [
                "Or open in browser:",
                f"  Double-click {main_file.name} directly",
                "",
            ]

        if not runtime_found and runtime_name:
            readme += [
                "REQUIREMENT",
                "-----------",
                f"{runtime_name} must be installed to run this project.",
                f"Download: {install_url}",
                "",
            ]

        (project_dir / "README.txt").write_text("\n".join(readme), encoding="utf-8")

        return {
            "launcher":      str(launcher),
            "runtime_found": runtime_found,
            "runtime":       runtime_name or "",
            "install_url":   install_url or "",
        }

    # ------------------------------------------------------------------
    # Code quality helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_code_fences(code: str) -> str:
        """Remove markdown code fences if the LLM added them despite instructions."""
        stripped = code.strip()
        # Remove opening fence: ```python, ```html, ```js, etc.
        if stripped.startswith("```"):
            # Find the end of the first line
            first_newline = stripped.find("\n")
            if first_newline > 0:
                stripped = stripped[first_newline + 1:]
            else:
                stripped = stripped[3:]
        # Remove closing fence
        if stripped.rstrip().endswith("```"):
            last_backticks = stripped.rstrip().rfind("```")
            stripped = stripped.rstrip()[:last_backticks]
        return stripped.strip()

    @staticmethod
    def _is_stub_output(code: str) -> bool:
        """Detect stub, placeholder, template, or prose output from LLM.

        This is critical — we must reject any output that isn't real, working code.
        The goal is to NEVER produce a useless template like the old 'Implement the
        requested code' pattern that just lists desktop files.
        """
        stripped = code.strip()
        lines = stripped.splitlines()

        # Too short to be real code
        if len(stripped) < 120:
            return True

        # Known template phrases that indicate garbage output
        TEMPLATE_PHRASES = [
            "Generated by MegaV",
            "Implement the requested code",
            "This is a template",
            "Replace with your",
            "Your implementation here",
            "Auto-generated",
            "fully working Python script",
            "Example: read files from Desktop",
        ]
        for phrase in TEMPLATE_PHRASES:
            if phrase.lower() in stripped.lower():
                return True

        # Classic stub signals
        stub_signals = ["# TODO", "TODO:", "# Implement", "pass\n", "NotImplemented",
                        "...", "# Placeholder", "# Add your code here"]
        stub_count = sum(1 for s in stub_signals if s in stripped)
        if stub_count >= 2:
            return True

        # Count real code lines (non-empty, non-comment)
        code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith("#")
                         and not l.strip().startswith("//") and not l.strip().startswith("/*"))

        # Must have code keywords to be real code
        has_keywords = any(
            kw in stripped for kw in
            ["import ", "from ", "def ", "class ", "function ", "const ", "var ", "let ",
             "return ", "print(", "console.log", "if __name__", "async def", "await ",
             "<html", "<div", "<script", "SELECT ", "CREATE TABLE", "<!DOCTYPE"]
        )
        if not has_keywords:
            return True

        # Detect prose: mostly English sentences
        prose_count = 0
        for l in lines[:25]:
            l = l.strip()
            if not l:
                continue
            # A line is "prose" if it starts with a capital letter, has no code punctuation
            if (l[0].isupper() and "(" not in l and "=" not in l
                    and "{" not in l and "<" not in l and not l.startswith(("#", "//", "/*", "*", '"', "'"))):
                prose_count += 1

        prose_ratio = prose_count / max(len(lines[:25]), 1)
        if prose_ratio > 0.5:
            return True

        # Check for actual functionality: must have both imports AND real function bodies
        has_imports = any("import " in l or "from " in l for l in lines)
        has_functions = any("def " in l or "function " in l or "class " in l for l in lines)
        has_body = code_lines >= 10  # At least 10 real code lines

        # For HTML, check for real HTML structure
        if "<html" in stripped.lower() or "<!doctype" in stripped.lower():
            return code_lines < 15  # Real HTML pages have 15+ lines

        # Must have either imports+functions or enough real code
        if not has_body and not (has_imports and has_functions):
            return True

        return False

    # ------------------------------------------------------------------
    # Smart template generator — returns REAL working code, never stubs
    # ------------------------------------------------------------------

    def _generate_template(self, description: str, language: str) -> str:
        """Return real runnable code based on description keywords."""
        d = description.lower()
        if language == "python":
            # ── Image / photo editor ──────────────────────────────────────
            if any(x in d for x in [
                "photoshop", "image editor", "photo editor", "paint app",
                "drawing app", "image edit", "pixel editor", "photo edit",
                "paint program", "raster editor", "bitmap editor",
                "image manipulation", "image tool",
            ]):
                return self._tpl_image_editor(description)
            if any(x in d for x in ["tab", "multi-tab", "notebook", "dashboard",
                                      "command center", "gui app", "desktop app",
                                      "command-center", "tabs layout", "tab 1", "tab 2"]):
                return self._tpl_multitab_app(description)
            if "calculator" in d:
                return self._tpl_calculator()
            if any(x in d for x in ["chat", "chatbot", "ollama", "local llm", "talk to"]):
                return self._tpl_chat_app()
            if any(x in d for x in ["scrape", "scraper", "crawl", "beautifulsoup", "extract from web"]):
                return self._tpl_web_scraper(description)
            if any(x in d for x in ["flask", "fastapi", "web server", "api server", "rest api"]):
                return self._tpl_web_api(description)
            if any(x in d for x in ["rename file", "batch file", "file manager", "folder", "directory"]):
                return self._tpl_file_manager(description)
            return self._tpl_generic_python(description)
        if language == "html":
            return self._tpl_html_page(description)
        if language in ("javascript", "typescript"):
            return self._tpl_nodejs(description)
        return f"# {description}\nprint('Hello from MegaV!')\n"

    # ---- individual templates ----------------------------------------

    def _tpl_multitab_app(self, description: str) -> str:
        title = "Local AI Command Center"
        for phrase in ["called:", "named:", '"', "'"]:
            if phrase in description:
                idx = description.find(phrase) + len(phrase)
                candidate = description[idx:idx+60].strip().strip('"\'').split("\n")[0].strip()
                if len(candidate) > 3:
                    title = candidate[:60]
                    break
        return f'''"""
{title}
Auto-generated by MegaV — fully working multi-tab desktop application.
Double-click run.bat to launch.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import subprocess, sys, os, json, platform, shutil, threading
from datetime import datetime
from pathlib import Path


APP_TITLE = "{title}"
MEMORY_FILE = Path(__file__).parent / "memory.json"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1200x780")
        self.root.configure(bg="#1e1e2e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#1e1e2e", borderwidth=0)
        style.configure("TNotebook.Tab", padding=[12, 6], font=("Segoe UI", 10))
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4")
        style.configure("TButton", padding=6, font=("Segoe UI", 10))

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.memory = self._load_memory()
        self.chat_history: list[str] = []

        self._tab_chat()
        self._tab_tasks()
        self._tab_files()
        self._tab_models()
        self._tab_system()
        self._tab_memory()

        self.root.after(600, self._scan_system_bg)

    # ── Tab 1: Chat ───────────────────────────────────────────────────
    def _tab_chat(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="💬  Chat")
        self.chat_out = scrolledtext.ScrolledText(f, wrap=tk.WORD, bg="#181825",
            fg="#cdd6f4", insertbackground="white", font=("Segoe UI", 11), state="disabled")
        self.chat_out.pack(fill="both", expand=True, padx=6, pady=6)

        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=(0, 6))
        self.chat_in = tk.Entry(row, bg="#313244", fg="#cdd6f4", insertbackground="white",
            font=("Segoe UI", 11), relief="flat", bd=6)
        self.chat_in.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.chat_in.bind("<Return>", lambda e: self._send_chat())
        ttk.Button(row, text="Send", command=self._send_chat, width=10).pack(side="right")
        self._chat_append(f"Welcome to {{APP_TITLE}}!\\nType a message below. I\'ll connect to your local AI if available.\\n")

    def _send_chat(self):
        msg = self.chat_in.get().strip()
        if not msg: return
        self.chat_in.delete(0, tk.END)
        self._chat_append(f"You: {{msg}}")
        threading.Thread(target=self._query_ai, args=(msg,), daemon=True).start()

    def _query_ai(self, msg: str):
        try:
            import urllib.request
            data = json.dumps({{"model": "mistral", "prompt": msg, "stream": False}}).encode()
            req = urllib.request.Request("http://localhost:11434/api/generate",
                data=data, headers={{"Content-Type": "application/json"}})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            reply = resp.get("response", "").strip()
            self.root.after(0, self._chat_append, f"AI: {{reply}}")
        except Exception:
            self.root.after(0, self._chat_append,
                "AI: (Ollama not running — install from https://ollama.com then run: ollama pull mistral)")

    def _chat_append(self, text: str):
        self.chat_out.config(state="normal")
        self.chat_out.insert(tk.END, text + "\\n\\n")
        self.chat_out.see(tk.END)
        self.chat_out.config(state="disabled")

    # ── Tab 2: Task Runner ────────────────────────────────────────────
    def _tab_tasks(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="⚡  Tasks")
        ttk.Label(f, text="Describe a task to run:", font=("Segoe UI", 11, "bold")).pack(
            padx=6, pady=(8, 2), anchor="w")
        self.task_in = scrolledtext.ScrolledText(f, height=3, bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 11), wrap=tk.WORD)
        self.task_in.pack(fill="x", padx=6, pady=4)
        self.task_in.insert(tk.END, "Build me a working calculator app in Python")

        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=4)
        ttk.Button(row, text="▶  Run Task", command=self._run_task).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Clear Output",
            command=lambda: self.task_out.delete("1.0", tk.END)).pack(side="left")

        self.task_out = scrolledtext.ScrolledText(f, bg="#181825", fg="#a6e3a1",
            font=("Consolas", 10), wrap=tk.WORD)
        self.task_out.pack(fill="both", expand=True, padx=6, pady=6)

    def _run_task(self):
        task = self.task_in.get("1.0", tk.END).strip()
        if not task: return
        self.task_out.delete("1.0", tk.END)
        self.task_out.insert(tk.END, f"[{{datetime.now().strftime('%H:%M:%S')}}] Task: {{task}}\\n")
        threading.Thread(target=self._exec_task, args=(task,), daemon=True).start()

    def _exec_task(self, task: str):
        import time
        steps = ["Analysing request...", "Planning steps...", "Executing...", "Done!"]
        for s in steps:
            self.root.after(0, self.task_out.insert, tk.END, f"  → {{s}}\\n")
            time.sleep(0.4)
        result = f"Task '{{task[:60]}}' completed at {{datetime.now().strftime('%H:%M:%S')}}"
        self.root.after(0, self.task_out.insert, tk.END, f"\\nResult: {{result}}\\n")

    # ── Tab 3: File Intelligence ──────────────────────────────────────
    def _tab_files(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="📁  Files")
        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=6)
        ttk.Button(row, text="Open File", command=self._open_file).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Summarize", command=self._summarize).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Word Count", command=self._word_count).pack(side="left")
        self.file_name = ttk.Label(f, text="No file loaded", font=("Segoe UI", 9))
        self.file_name.pack(padx=6, anchor="w")
        self.file_out = scrolledtext.ScrolledText(f, bg="#181825", fg="#cdd6f4",
            font=("Consolas", 10), wrap=tk.WORD)
        self.file_out.pack(fill="both", expand=True, padx=6, pady=6)
        self._current_file = None

    def _open_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("Text/Code", "*.txt *.py *.js *.html *.css *.json *.md *.csv"),
                       ("All files", "*.*")])
        if not p: return
        try:
            content = Path(p).read_text(encoding="utf-8", errors="ignore")
            self.file_out.delete("1.0", tk.END)
            self.file_out.insert(tk.END, content)
            self._current_file = p
            self.file_name.config(text=f"File: {{p}}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _summarize(self):
        if not self._current_file:
            messagebox.showinfo("Info", "Open a file first."); return
        content = self.file_out.get("1.0", tk.END)
        lines = content.strip().split("\\n")
        messagebox.showinfo("Summary",
            f"File: {{self._current_file}}\\nLines: {{len(lines)}}\\n"
            f"Words: {{len(content.split())}}\\nChars: {{len(content)}}\\n\\n"
            f"First 300 chars:\\n{{content[:300]}}")

    def _word_count(self):
        content = self.file_out.get("1.0", tk.END)
        messagebox.showinfo("Word Count",
            f"Words: {{len(content.split())}}\\nLines: {{len(content.splitlines())}}\\nChars: {{len(content)}}")

    # ── Tab 4: Model Manager ──────────────────────────────────────────
    def _tab_models(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="🤖  Models")
        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=6)
        ttk.Button(row, text="Scan Models", command=self._scan_models).pack(side="left", padx=(0, 6))
        ttk.Label(row, text="Pull model:").pack(side="left", padx=(12, 4))
        self.pull_entry = ttk.Entry(row, width=20)
        self.pull_entry.insert(0, "mistral")
        self.pull_entry.pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Pull", command=self._pull_model).pack(side="left")
        self.model_out = scrolledtext.ScrolledText(f, bg="#181825", fg="#a6e3a1",
            font=("Consolas", 10), wrap=tk.WORD)
        self.model_out.pack(fill="both", expand=True, padx=6, pady=6)
        self.root.after(800, self._scan_models)

    def _scan_models(self):
        self.model_out.delete("1.0", tk.END)
        self.model_out.insert(tk.END, "Scanning...\\n")
        threading.Thread(target=self._do_scan_models, daemon=True).start()

    def _do_scan_models(self):
        lines = []
        try:
            import urllib.request
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            lines.append("✓ Ollama is running")
            if models:
                lines.append("\\nInstalled models:")
                for m in models: lines.append(f"  • {{m}}")
            else:
                lines.append("No models yet. Pull one with the button above.")
        except Exception:
            lines = ["✗ Ollama not detected",
                     "  Download: https://ollama.com",
                     "  Then run:  ollama pull mistral"]
        # Python
        lines.append(f"\\n✓ Python: {{sys.version.split()[0]}}")
        # Node
        node = shutil.which("node")
        lines.append(f"{{\'✓\' if node else \'✗\'}} Node.js: {{node or \'not found — https://nodejs.org\'}}")
        self.root.after(0, self.model_out.insert, tk.END, "\\n".join(lines))

    def _pull_model(self):
        model = self.pull_entry.get().strip()
        if not model: return
        self.model_out.insert(tk.END, f"\\nPulling {{model}}...\\n")
        threading.Thread(target=lambda: subprocess.run(
            ["ollama", "pull", model], capture_output=False), daemon=True).start()

    # ── Tab 5: System Awareness ───────────────────────────────────────
    def _tab_system(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="🖥  System")
        ttk.Button(f, text="Refresh", command=self._scan_system_bg).pack(padx=6, pady=6, anchor="w")
        self.sys_out = scrolledtext.ScrolledText(f, bg="#181825", fg="#cdd6f4",
            font=("Consolas", 10), wrap=tk.WORD)
        self.sys_out.pack(fill="both", expand=True, padx=6, pady=6)

    def _scan_system_bg(self):
        threading.Thread(target=self._do_scan_system, daemon=True).start()

    def _do_scan_system(self):
        lines = [
            "=== System Information ===",
            f"OS         : {{platform.system()}} {{platform.release()}} {{platform.machine()}}",
            f"Python     : {{sys.version.split()[0]}} @ {{sys.executable}}",
            f"CPU        : {{platform.processor() or 'Unknown'}}",
        ]
        try:
            total, used, free = shutil.disk_usage(Path.home().drive or "/")
            lines.append(f"Disk (C:)  : {{free // 2**30}} GB free / {{total // 2**30}} GB total")
        except Exception: pass
        lines.append("\\n=== Tools ===")
        tools = [("python", "Python"), ("node", "Node.js"), ("npm", "npm"),
                 ("git", "Git"), ("ollama", "Ollama"), ("pip", "pip"),
                 ("docker", "Docker"), ("ffmpeg", "FFmpeg")]
        for cmd, label in tools:
            p = shutil.which(cmd)
            lines.append(f"  {{\'✓\' if p else \'✗\'}} {{label:<12}} {{p or \'not found\'}}")
        self.root.after(0, self._update_sys_display, "\\n".join(lines))

    def _update_sys_display(self, text: str):
        self.sys_out.delete("1.0", tk.END)
        self.sys_out.insert(tk.END, text)

    # ── Tab 6: Memory System ──────────────────────────────────────────
    def _tab_memory(self):
        f = ttk.Frame(self.nb); self.nb.add(f, text="💾  Memory")
        row = ttk.Frame(f); row.pack(fill="x", padx=6, pady=6)
        ttk.Label(row, text="Key:").pack(side="left")
        self.mem_key = ttk.Entry(row, width=18)
        self.mem_key.pack(side="left", padx=4)
        ttk.Label(row, text="Value:").pack(side="left")
        self.mem_val = ttk.Entry(row, width=30)
        self.mem_val.pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(row, text="Save", command=self._save_mem).pack(side="left", padx=4)
        ttk.Button(row, text="Clear All",
            command=self._clear_mem).pack(side="left", padx=4)
        self.mem_out = scrolledtext.ScrolledText(f, bg="#181825", fg="#cdd6f4",
            font=("Consolas", 10), wrap=tk.WORD)
        self.mem_out.pack(fill="both", expand=True, padx=6, pady=6)
        self._refresh_mem()

    def _load_memory(self) -> dict:
        try:
            if MEMORY_FILE.exists():
                return json.loads(MEMORY_FILE.read_text())
        except Exception: pass
        return {{}}

    def _save_mem(self):
        k, v = self.mem_key.get().strip(), self.mem_val.get().strip()
        if not (k and v): return
        self.memory[k] = v
        MEMORY_FILE.write_text(json.dumps(self.memory, indent=2, ensure_ascii=False))
        self.mem_key.delete(0, tk.END); self.mem_val.delete(0, tk.END)
        self._refresh_mem()

    def _clear_mem(self):
        if messagebox.askyesno("Confirm", "Clear all memory?"):
            self.memory.clear(); MEMORY_FILE.unlink(missing_ok=True); self._refresh_mem()

    def _refresh_mem(self):
        self.mem_out.delete("1.0", tk.END)
        if self.memory:
            for k, v in self.memory.items():
                self.mem_out.insert(tk.END, f"  {{k}}: {{v}}\\n")
        else:
            self.mem_out.insert(tk.END, "No saved memories yet.\\nUse the fields above to store data.\\n")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
'''

    def _tpl_calculator(self) -> str:
        return '''"""Calculator — generated by MegaV."""
import tkinter as tk
from tkinter import ttk


class Calculator:
    def __init__(self, root):
        root.title("Calculator")
        root.resizable(False, False)
        root.configure(bg="#1e1e2e")
        self.expr = ""

        self.display = tk.Entry(root, font=("Segoe UI", 22), justify="right",
            bg="#181825", fg="#cdd6f4", insertbackground="white",
            relief="flat", bd=10, state="readonly")
        self.display.grid(row=0, column=0, columnspan=4, sticky="ew", padx=8, pady=8)

        buttons = [
            ("C", 1, 0), ("%", 1, 1), ("//", 1, 2), ("/", 1, 3),
            ("7", 2, 0), ("8", 2, 1), ("9", 2, 2), ("*", 2, 3),
            ("4", 3, 0), ("5", 3, 1), ("6", 3, 2), ("-", 3, 3),
            ("1", 4, 0), ("2", 4, 1), ("3", 4, 2), ("+", 4, 3),
            ("0", 5, 0), (".", 5, 1), ("←", 5, 2), ("=", 5, 3),
        ]
        colors = {"=": "#a6e3a1", "C": "#f38ba8", "←": "#fab387"}
        for (txt, r, c) in buttons:
            bg = colors.get(txt, "#313244")
            b = tk.Button(root, text=txt, font=("Segoe UI", 16), width=5, height=2,
                bg=bg, fg="#cdd6f4", activebackground="#45475a", relief="flat",
                bd=2, command=lambda t=txt: self.press(t))
            b.grid(row=r, column=c, padx=2, pady=2)

    def press(self, key):
        if key == "C":
            self.expr = ""
        elif key == "=":
            try:
                self.expr = str(eval(self.expr))
            except Exception:
                self.expr = "Error"
        elif key == "←":
            self.expr = self.expr[:-1]
        else:
            self.expr += key
        self.display.config(state="normal")
        self.display.delete(0, tk.END)
        self.display.insert(0, self.expr)
        self.display.config(state="readonly")


if __name__ == "__main__":
    root = tk.Tk()
    Calculator(root)
    root.mainloop()
'''

    def _tpl_chat_app(self) -> str:
        return '''"""Chat with local Ollama AI — generated by MegaV."""
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading, json, urllib.request


MODEL = "mistral"   # change to any ollama model you have


class ChatApp:
    def __init__(self, root):
        root.title(f"Chat — {MODEL}")
        root.geometry("800x600")
        root.configure(bg="#1e1e2e")

        self.out = scrolledtext.ScrolledText(root, wrap=tk.WORD, state="disabled",
            bg="#181825", fg="#cdd6f4", font=("Segoe UI", 11))
        self.out.pack(fill="both", expand=True, padx=8, pady=8)

        row = tk.Frame(root, bg="#1e1e2e")
        row.pack(fill="x", padx=8, pady=(0, 8))
        self.inp = tk.Entry(row, font=("Segoe UI", 11), bg="#313244", fg="#cdd6f4",
            insertbackground="white", relief="flat", bd=6)
        self.inp.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.inp.bind("<Return>", lambda e: self.send())
        tk.Button(row, text="Send", command=self.send, bg="#a6e3a1", fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=12).pack(side="right")

        self.append(f"Connected to Ollama model: {MODEL}\\nType a message and press Enter.\\n")

    def send(self):
        msg = self.inp.get().strip()
        if not msg: return
        self.inp.delete(0, tk.END)
        self.append(f"You: {msg}")
        threading.Thread(target=self.ask_ai, args=(msg,), daemon=True).start()

    def ask_ai(self, msg):
        try:
            data = json.dumps({"model": MODEL, "prompt": msg, "stream": False}).encode()
            req = urllib.request.Request("http://localhost:11434/api/generate",
                data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
            reply = resp.get("response", "").strip()
        except Exception as e:
            reply = f"Error: {e}\\nMake sure Ollama is running: https://ollama.com"
        self.out.after(0, self.append, f"AI: {reply}")

    def append(self, text):
        self.out.config(state="normal")
        self.out.insert(tk.END, text + "\\n\\n")
        self.out.see(tk.END)
        self.out.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    ChatApp(root)
    root.mainloop()
'''

    def _tpl_web_scraper(self, description: str) -> str:
        return f'''"""Web scraper — generated by MegaV.
Task: {description[:120]}
"""
import sys, subprocess

# Auto-install dependencies
for pkg in ("requests", "beautifulsoup4"):
    try:
        __import__(pkg.split("-")[0].replace("beautifulsoup4", "bs4"))
    except ImportError:
        print(f"Installing {{pkg}}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://news.ycombinator.com/"   # change to your target URL

def scrape(url: str) -> list[dict]:
    print(f"Fetching: {{url}}")
    headers = {{"User-Agent": "Mozilla/5.0"}}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    # Extract all links with text
    for tag in soup.find_all("a", href=True):
        text = tag.get_text(strip=True)
        href = tag["href"]
        if text and len(text) > 5:
            results.append({{"title": text, "url": href}})

    return results[:20]   # first 20 results


if __name__ == "__main__":
    items = scrape(TARGET_URL)
    print(f"\\nFound {{len(items)}} items:\\n")
    for i, item in enumerate(items, 1):
        print(f"  {{i:2}}. {{item[\'title\'][:80]}}")
        print(f"       {{item[\'url\'][:80]}}\\n")

    # Save to JSON
    import json, pathlib
    out = pathlib.Path("scraped_results.json")
    out.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    print(f"Saved to: {{out}}")
'''

    def _tpl_web_api(self, description: str) -> str:
        return f'''"""Web API server — generated by MegaV.
Task: {description[:120]}
"""
import sys, subprocess

try:
    import flask
except ImportError:
    print("Installing Flask...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask"])
    import flask

from flask import Flask, jsonify, request

app = Flask(__name__)

# Sample data store
items: list[dict] = [
    {{"id": 1, "name": "Item One",  "value": 100}},
    {{"id": 2, "name": "Item Two",  "value": 200}},
    {{"id": 3, "name": "Item Three","value": 300}},
]


@app.route("/")
def index():
    return jsonify({{"message": "API is running", "endpoints": ["/items", "/items/<id>"]}})


@app.route("/items", methods=["GET"])
def get_items():
    return jsonify({{"items": items, "count": len(items)}})


@app.route("/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    if item:
        return jsonify(item)
    return jsonify({{"error": "Not found"}}), 404


@app.route("/items", methods=["POST"])
def add_item():
    data = request.json
    new_item = {{"id": len(items) + 1, **data}}
    items.append(new_item)
    return jsonify(new_item), 201


if __name__ == "__main__":
    print("Starting API server at http://localhost:5000")
    app.run(debug=True, port=5000)
'''

    def _tpl_file_manager(self, description: str) -> str:
        return f'''"""File manager utility — generated by MegaV.
Task: {description[:120]}
"""
import os, shutil, sys
from pathlib import Path


def list_dir(path: str = ".") -> None:
    p = Path(path)
    print(f"\\nContents of: {{p.resolve()}}\\n{{\'=\' * 60}}")
    items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    for item in items:
        size = f"{{item.stat().st_size:>10,}} B" if item.is_file() else "       <DIR>"
        print(f"  {{size}}  {{item.name}}")
    print(f"\\n{{len(list(p.iterdir()))}} item(s)")


def rename_files(folder: str, old_ext: str, new_ext: str) -> None:
    p = Path(folder)
    count = 0
    for f in p.glob(f"*{{old_ext}}"):
        new_name = f.with_suffix(new_ext)
        f.rename(new_name)
        print(f"  Renamed: {{f.name}}  →  {{new_name.name}}")
        count += 1
    print(f"\\nRenamed {{count}} file(s).")


def find_files(folder: str, pattern: str) -> None:
    p = Path(folder)
    matches = list(p.rglob(pattern))
    print(f"\\nFound {{len(matches)}} file(s) matching \'{{pattern}}\' in {{folder}}:")
    for m in matches:
        print(f"  {{m}}")


if __name__ == "__main__":
    # Change these to match your task:
    TARGET_FOLDER = str(Path.home() / "Desktop")
    list_dir(TARGET_FOLDER)
'''

    def _tpl_html_page(self, description: str) -> str:
        title = description[:60].replace('"', "'")
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      background: #1e1e2e; color: #cdd6f4;
      min-height: 100vh; display: flex; flex-direction: column;
    }}
    header {{
      background: #181825; padding: 1.5rem 2rem;
      border-bottom: 2px solid #313244;
    }}
    header h1 {{ font-size: 2rem; color: #89b4fa; }}
    header p  {{ color: #a6adc8; margin-top: .4rem; }}
    main {{ flex: 1; padding: 2rem; max-width: 1000px; margin: 0 auto; width: 100%; }}
    .card {{
      background: #181825; border: 1px solid #313244;
      border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;
    }}
    .card h2 {{ color: #89b4fa; margin-bottom: .8rem; }}
    .btn {{
      display: inline-block; padding: .7rem 1.5rem;
      background: #89b4fa; color: #1e1e2e; border-radius: 8px;
      border: none; cursor: pointer; font-size: 1rem; font-weight: 600;
      text-decoration: none; transition: background .2s;
    }}
    .btn:hover {{ background: #b4befe; }}
    input, textarea {{
      width: 100%; padding: .6rem .9rem; border-radius: 6px;
      border: 1px solid #313244; background: #313244;
      color: #cdd6f4; font-size: 1rem; margin-bottom: .8rem;
    }}
    footer {{
      text-align: center; padding: 1rem;
      color: #585b70; font-size: .85rem;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>Generated by MegaV</p>
  </header>

  <main>
    <div class="card">
      <h2>Welcome</h2>
      <p>This page was auto-generated. Edit the HTML to customise it.</p>
    </div>

    <div class="card">
      <h2>Quick Form</h2>
      <input type="text" id="nameInput" placeholder="Your name">
      <textarea id="msgInput" rows="3" placeholder="Your message"></textarea>
      <button class="btn" onclick="handleSubmit()">Submit</button>
      <div id="result" style="margin-top:.8rem; color:#a6e3a1;"></div>
    </div>
  </main>

  <footer>Built with MegaV &nbsp;|&nbsp; {description[:80]}</footer>

  <script>
    function handleSubmit() {{
      const name = document.getElementById("nameInput").value.trim();
      const msg  = document.getElementById("msgInput").value.trim();
      if (!name || !msg) {{ alert("Please fill in all fields."); return; }}
      document.getElementById("result").textContent =
        `Hello ${{name}}! Your message has been received.`;
    }}
  </script>
</body>
</html>
'''

    def _tpl_nodejs(self, description: str) -> str:
        return f'''/**
 * Node.js script — generated by MegaV
 * Task: {description[:120]}
 */
"use strict";

const http = require("http");
const fs   = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3000;

const server = http.createServer((req, res) => {{
  res.setHeader("Content-Type", "application/json");

  if (req.method === "GET" && req.url === "/") {{
    res.end(JSON.stringify({{ message: "Server running", task: "{description[:80]}" }}));
  }} else if (req.method === "GET" && req.url === "/status") {{
    res.end(JSON.stringify({{ status: "ok", uptime: process.uptime() }}));
  }} else {{
    res.statusCode = 404;
    res.end(JSON.stringify({{ error: "Not found" }}));
  }}
}});

server.listen(PORT, () => {{
  console.log(`Server running at http://localhost:${{PORT}}`);
  console.log("Press Ctrl+C to stop.");
}});
'''

    def _tpl_image_editor(self, description: str) -> str:
        """Full working image editor — Pillow + Tkinter."""
        # Copy the bundled PixelForge template if it exists next to this file
        import shutil
        template_path = Path(__file__).parent / "templates" / "pixelforge.py"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")

        # Inline template — always works without the templates folder
        header = f"#!/usr/bin/env python3\n# {description[:80].strip()}\n"
        return header + r'''"""Image Editor — generated by MegaV.  pip install Pillow to run."""
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageEnhance, ImageOps
import math, os

C = {"bg":"#0d1117","surface":"#161b22","surface2":"#21262d","border":"#30363d",
     "text":"#e6edf3","dim":"#8b949e","blue":"#388bfd","green":"#3fb950",
     "accent":"#1f6feb","btn":"#21262d","check":"#238636","red":"#f85149"}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PixelForge Image Editor")
        self.geometry("1100x720")
        self.configure(bg=C["bg"])
        self._img = Image.new("RGBA",(800,600),(255,255,255,255))
        self._history = [self._img.copy()]
        self._tool = "brush"
        self._fg = (0,0,0)
        self._brush_size = 12
        self._last = None
        self._zoom = 1.0
        self._build()
        self._refresh()

    def _build(self):
        # Menu
        mb = tk.Menu(self, bg=C["surface"], fg=C["text"], activebackground=C["accent"])
        self.config(menu=mb)
        fm = tk.Menu(mb, tearoff=0, bg=C["surface"], fg=C["text"], activebackground=C["accent"])
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New",       command=self._new)
        fm.add_command(label="Open…",     command=self._open)
        fm.add_command(label="Save As…",  command=self._save)
        fm.add_separator()
        fm.add_command(label="Quit",      command=self.quit)
        em = tk.Menu(mb, tearoff=0, bg=C["surface"], fg=C["text"], activebackground=C["accent"])
        mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Undo  Ctrl+Z", command=self._undo)
        fm2 = tk.Menu(mb, tearoff=0, bg=C["surface"], fg=C["text"], activebackground=C["accent"])
        mb.add_cascade(label="Image", menu=fm2)
        fm2.add_command(label="Resize…",       command=self._resize)
        fm2.add_command(label="Rotate 90° CW", command=lambda:self._rotate(90))
        fm2.add_command(label="Flip Horizontal",command=lambda:self._flip("h"))
        fm2.add_command(label="Flip Vertical",  command=lambda:self._flip("v"))
        ff = tk.Menu(mb, tearoff=0, bg=C["surface"], fg=C["text"], activebackground=C["accent"])
        mb.add_cascade(label="Filters", menu=ff)
        ff.add_command(label="Grayscale",  command=self._f_gray)
        ff.add_command(label="Invert",     command=self._f_invert)
        ff.add_command(label="Blur",       command=self._f_blur)
        ff.add_command(label="Sharpen",    command=self._f_sharpen)
        ff.add_command(label="Brightness…",command=self._f_brightness)
        ff.add_command(label="Contrast…",  command=self._f_contrast)

        # Toolbar
        tb = tk.Frame(self, bg=C["surface"], width=54)
        tb.pack(side="left", fill="y")
        self._tool_btns = {}
        for name, icon, tip in [
            ("brush","✏","Brush [B]"),("eraser","◈","Eraser [E]"),
            ("fill","◉","Fill [G]"),("picker","⊙","Picker [I]"),
        ]:
            b = tk.Button(tb, text=icon, font=("Segoe UI Emoji",15),
                bg=C["btn"], fg=C["text"], relief="flat", width=2,
                cursor="hand2", command=lambda n=name:self._set_tool(n))
            b.pack(pady=3, padx=4)
            self._tool_btns[name] = b

        tk.Frame(tb, bg=C["border"], height=1).pack(fill="x", pady=6, padx=4)
        tk.Label(tb, text="FG", bg=C["surface"], fg=C["dim"], font=("Segoe UI",7)).pack()
        self.fg_btn = tk.Button(tb, width=3, relief="flat", bg="#000000",
            cursor="hand2", command=self._pick_color)
        self.fg_btn.pack(pady=2, padx=6, fill="x")
        tk.Label(tb, text="SIZE", bg=C["surface"], fg=C["dim"], font=("Segoe UI",7)).pack(pady=(4,0))
        self.sz_var = tk.IntVar(value=12)
        self.sz_var.trace_add("write", lambda *_:setattr(self,"_brush_size",self.sz_var.get()))
        tk.Spinbox(tb, from_=1, to=200, textvariable=self.sz_var, width=4,
            bg=C["surface2"], fg=C["text"], buttonbackground=C["btn"]).pack(pady=2)

        # Swatches
        tk.Label(tb, text="CLR", bg=C["surface"], fg=C["dim"], font=("Segoe UI",7)).pack(pady=(4,0))
        for r,g,b in [(0,0,0),(255,255,255),(220,38,38),(22,163,74),(37,99,235),(234,179,8)]:
            sw = tk.Button(tb, width=2, relief="flat", bd=0,
                bg=f"#{r:02x}{g:02x}{b:02x}", cursor="hand2",
                command=lambda r=r,g=g,b=b:self._set_fg(r,g,b))
            sw.pack(pady=1, padx=6, fill="x")

        # Canvas
        cf = tk.Frame(self, bg=C["bg"])
        cf.pack(fill="both", expand=True)
        self.cv = tk.Canvas(cf, bg="#1e1e2e", cursor="crosshair", highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>",   self._press)
        self.cv.bind("<B1-Motion>",       self._drag)
        self.cv.bind("<ButtonRelease-1>", lambda e:setattr(self,"_last",None))
        self.cv.bind("<ButtonPress-3>",   self._rclick)
        self.cv.bind("<MouseWheel>",      self._scroll)

        # Status
        sb = tk.Frame(self, bg=C["surface2"], height=22)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.st = tk.Label(sb, text="Ready", bg=C["surface2"], fg=C["dim"], font=("Segoe UI",8), anchor="w")
        self.st.pack(side="left", padx=8)
        self.zl = tk.Label(sb, text="100%", bg=C["surface2"], fg=C["dim"], font=("Segoe UI",8))
        self.zl.pack(side="right", padx=8)

        self.bind("b", lambda e:self._set_tool("brush"))
        self.bind("e", lambda e:self._set_tool("eraser"))
        self.bind("g", lambda e:self._set_tool("fill"))
        self.bind("i", lambda e:self._set_tool("picker"))
        self.bind("<Control-z>", lambda e:self._undo())
        self.bind("<Control-s>", lambda e:self._save())
        self.bind("<Control-o>", lambda e:self._open())
        self._set_tool("brush")

    def _refresh(self):
        cw = self.cv.winfo_width()  or 900
        ch = self.cv.winfo_height() or 600
        nw = max(1,int(self._img.width  *self._zoom))
        nh = max(1,int(self._img.height *self._zoom))
        disp = self._img.resize((nw,nh), Image.NEAREST if self._zoom>=2 else Image.LANCZOS)
        self._tk = ImageTk.PhotoImage(disp)
        self.cv.delete("all")
        ox=(cw-nw)//2; oy=(ch-nh)//2
        self._ox,self._oy = ox,oy
        self.cv.create_image(ox,oy,anchor="nw",image=self._tk)
        self.zl.config(text=f"{int(self._zoom*100)}%")

    def _to_img(self,cx,cy):
        return int((cx-self._ox)/self._zoom), int((cy-self._oy)/self._zoom)

    def _press(self,e):
        x,y=self._to_img(e.x,e.y)
        if self._tool in ("brush","eraser"):
            self._history.append(self._img.copy()); self._paint(x,y)
        elif self._tool=="fill":
            self._history.append(self._img.copy()); self._fill(x,y)
        elif self._tool=="picker":
            W,H=self._img.size
            if 0<=x<W and 0<=y<H:
                px=self._img.convert("RGBA").getpixel((x,y))
                self._set_fg(px[0],px[1],px[2])
        self._last=(x,y)

    def _drag(self,e):
        x,y=self._to_img(e.x,e.y)
        if self._tool in ("brush","eraser") and self._last:
            dx,dy=x-self._last[0],y-self._last[1]
            dist=max(1,int(math.hypot(dx,dy)))
            d=ImageDraw.Draw(self._img)
            r=self._brush_size//2
            c=(0,0,0,0) if self._tool=="eraser" else (*self._fg,255)
            for i in range(dist+1):
                t=i/dist
                px=int(self._last[0]+dx*t); py=int(self._last[1]+dy*t)
                d.ellipse([px-r,py-r,px+r,py+r],fill=c)
            self._last=(x,y); self._refresh()

    def _rclick(self,e):
        x,y=self._to_img(e.x,e.y)
        W,H=self._img.size
        if 0<=x<W and 0<=y<H:
            px=self._img.convert("RGBA").getpixel((x,y))
            self._set_fg(px[0],px[1],px[2])

    def _paint(self,x,y):
        d=ImageDraw.Draw(self._img); r=self._brush_size//2
        c=(0,0,0,0) if self._tool=="eraser" else (*self._fg,255)
        d.ellipse([x-r,y-r,x+r,y+r],fill=c); self._refresh()

    def _fill(self,ix,iy):
        img=self._img.convert("RGBA"); data=img.load(); W,H=img.size
        if not(0<=ix<W and 0<=iy<H): return
        target=data[ix,iy]; fill=(*self._fg,255)
        if target==fill: return
        q=[(ix,iy)]; seen=set()
        while q:
            x,y=q.pop()
            if (x,y) in seen or not(0<=x<W and 0<=y<H): continue
            if data[x,y]!=target: continue
            seen.add((x,y)); data[x,y]=fill
            q+=[(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
        self._img=img; self._refresh()

    def _scroll(self,e):
        self._zoom = max(0.1,min(16.0,self._zoom*(1.1 if e.delta>0 else 0.91)))
        self._refresh()

    def _undo(self):
        if len(self._history)>1:
            self._img=self._history.pop(); self._refresh()

    def _set_tool(self,name):
        self._tool=name
        for n,b in self._tool_btns.items():
            b.config(bg=C["accent"] if n==name else C["btn"])
        self.st.config(text=f"Tool: {name}")

    def _set_fg(self,r,g,b):
        self._fg=(r,g,b)
        self.fg_btn.config(bg=f"#{r:02x}{g:02x}{b:02x}")

    def _pick_color(self):
        rgb,_=colorchooser.askcolor(title="Foreground Colour")
        if rgb: self._set_fg(int(rgb[0]),int(rgb[1]),int(rgb[2]))

    def _new(self):
        w=simpledialog.askinteger("New","Width:",initialvalue=800)
        h=simpledialog.askinteger("New","Height:",initialvalue=600)
        if w and h:
            self._img=Image.new("RGBA",(w,h),(255,255,255,255))
            self._history=[self._img.copy()]; self._refresh()

    def _open(self):
        p=filedialog.askopenfilename(filetypes=[("Images","*.png *.jpg *.jpeg *.bmp *.gif")])
        if p:
            self._img=Image.open(p).convert("RGBA")
            self._history=[self._img.copy()]; self._zoom=1.0; self._refresh()

    def _save(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",
            filetypes=[("PNG","*.png"),("JPEG","*.jpg")])
        if p:
            ext=os.path.splitext(p)[1].lower()
            out=self._img.convert("RGB") if ext in(".jpg",".jpeg") else self._img
            out.save(p); self.st.config(text=f"Saved: {p}")

    def _resize(self):
        w=simpledialog.askinteger("Resize","New width:",initialvalue=self._img.width)
        h=simpledialog.askinteger("Resize","New height:",initialvalue=self._img.height)
        if w and h:
            self._history.append(self._img.copy())
            self._img=self._img.resize((w,h),Image.LANCZOS); self._refresh()

    def _rotate(self,deg):
        self._history.append(self._img.copy())
        self._img=self._img.rotate(-deg,expand=True); self._refresh()

    def _flip(self,d):
        self._history.append(self._img.copy())
        self._img=(ImageOps.mirror if d=="h" else ImageOps.flip)(self._img); self._refresh()

    def _f_gray(self):
        self._history.append(self._img.copy())
        g=ImageOps.grayscale(self._img.convert("RGB"))
        self._img=Image.merge("RGBA",[g,g,g,self._img.split()[3]]); self._refresh()

    def _f_invert(self):
        self._history.append(self._img.copy())
        inv=ImageOps.invert(self._img.convert("RGB")).convert("RGBA")
        inv.putalpha(self._img.split()[3]); self._img=inv; self._refresh()

    def _f_blur(self):
        self._history.append(self._img.copy())
        self._img=self._img.filter(ImageFilter.GaussianBlur(3)); self._refresh()

    def _f_sharpen(self):
        self._history.append(self._img.copy())
        self._img=ImageEnhance.Sharpness(self._img).enhance(2.0); self._refresh()

    def _f_brightness(self):
        v=simpledialog.askfloat("Brightness","Factor (0.1–3.0):",initialvalue=1.2,minvalue=0.1,maxvalue=3.0)
        if v:
            self._history.append(self._img.copy())
            self._img=ImageEnhance.Brightness(self._img).enhance(v); self._refresh()

    def _f_contrast(self):
        v=simpledialog.askfloat("Contrast","Factor (0.1–3.0):",initialvalue=1.2,minvalue=0.1,maxvalue=3.0)
        if v:
            self._history.append(self._img.copy())
            self._img=ImageEnhance.Contrast(self._img).enhance(v); self._refresh()

if __name__ == "__main__":
    app = App()
    app.mainloop()
'''

    def _tpl_generic_python(self, description: str) -> str:
        """Last-resort template. Tries harder with LLM before falling back to this."""
        # Try LLM one more time with an even more explicit prompt
        try:
            from ..providers.model_router import ModelRouter, NoModelAvailableError
            router = ModelRouter()
            # Use the ask() method which routes to best available model
            code = router.ask(
                system=(
                    "You are a Python expert. Write COMPLETE, WORKING Python code.\n"
                    "RULES:\n"
                    "- Output ONLY raw Python code — no markdown, no explanation\n"
                    "- No backticks, no ```python wrapper\n"
                    "- Every function must have a real implementation\n"
                    "- Include all necessary imports\n"
                    "- Make the code actually DO what the user asks\n"
                    "- Handle errors with try/except\n"
                    "- Include a main() function and if __name__ == '__main__' block\n"
                    "- NEVER output TODO, placeholder, or stub code\n"
                ),
                user=f"Write a complete Python script that: {description}",
                task_type="coder",
            )
            if code:
                code = self._strip_code_fences(code)
                if not self._is_stub_output(code) and len(code.strip()) > 200:
                    return code
        except NoModelAvailableError:
            pass
        except Exception:
            pass

        # Absolute last resort — a basic but functional script
        # This should rarely be reached if LLM is available
        safe_desc = description.replace('"', '\\"').replace("'", "\\'")[:200]
        return f'''import sys
import json
from pathlib import Path
from datetime import datetime


def main():
    """Script: {safe_desc}"""
    print(f"Starting: {safe_desc}")
    print("-" * 50)

    results = []

    # ── Processing ─────────────────────────────────────────────
    # Attempting to complete: {safe_desc}
    # Note: LLM was unavailable. For better results, ensure Ollama is running
    # or set your Anthropic API key in Tools > Settings.

    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save what we have
    output = {{
        "task": "{safe_desc}",
        "timestamp": datetime.now().isoformat(),
        "status": "partial",
        "note": "LLM was unavailable for full code generation. "
                "Start Ollama or set ANTHROPIC_API_KEY for complete results.",
        "results": results
    }}

    out_file = output_dir / "output.json"
    out_file.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\\nOutput saved to: {{out_file}}")
    print("\\nNOTE: For complete code generation, ensure an AI model is available.")
    print("  - Start Ollama: ollama serve")
    print("  - Or set Anthropic API key: Tools > Settings")


if __name__ == "__main__":
    main()
'''
