"""Skill management tools."""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import urllib.request


class SkillTools:
    """Tools for managing skills lifecycle."""

    def __init__(self, skills_dir: str = "skills"):
        """Initialize skill tools.

        Args:
            skills_dir: Skills directory path
        """
        self.skills_dir = Path(skills_dir)
        self.installed_dir = self.skills_dir / "installed"
        self.quarantine_dir = self.skills_dir / "quarantine"
        self.manifests_dir = self.skills_dir / "manifests"
        self.registry_path = self.skills_dir / "registry.json"

        # Ensure directories exist
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

        # Load registry
        self.registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        """Load skill registry."""
        if self.registry_path.exists():
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"version": "1.0.0", "skills": []}

    def _save_registry(self) -> None:
        """Save skill registry."""
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def search_skill_sources(self, query: str, source: str = "all") -> dict[str, Any]:
        """Search for skills in configured sources.

        Args:
            query: Search query
            source: Source to search (all, local, community, official)

        Returns:
            Search results
        """
        # This is a placeholder implementation
        # In a real implementation, this would query remote sources

        # Search local manifests
        local_results = []
        for manifest_file in self.manifests_dir.glob("*.json"):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    if query.lower() in manifest.get("name", "").lower() or \
                       query.lower() in manifest.get("description", "").lower():
                        local_results.append(manifest)
            except Exception:
                continue

        return {
            "success": True,
            "query": query,
            "source": source,
            "results": local_results,
            "count": len(local_results),
        }

    def download_skill(self, url: str, name: Optional[str] = None) -> dict[str, Any]:
        """Download a skill from URL.

        Args:
            url: Skill download URL
            name: Optional name for the skill

        Returns:
            Download result
        """
        try:
            # Parse URL to get filename
            parsed = urlparse(url)
            filename = name or Path(parsed.path).name or "skill.zip"

            if not filename.endswith(".zip"):
                filename += ".zip"

            # Download to quarantine
            quarantine_path = self.quarantine_dir / filename

            urllib.request.urlretrieve(url, quarantine_path)

            return {
                "success": True,
                "path": str(quarantine_path),
                "filename": filename,
                "status": "quarantined",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def quarantine_skill(self, skill_path: str) -> dict[str, Any]:
        """Move a skill to quarantine.

        Args:
            skill_path: Path to skill file

        Returns:
            Quarantine result
        """
        try:
            source = Path(skill_path)
            if not source.exists():
                return {
                    "success": False,
                    "error": f"Skill not found: {skill_path}",
                }

            dest = self.quarantine_dir / source.name
            shutil.move(str(source), str(dest))

            return {
                "success": True,
                "path": str(dest),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def inspect_skill_manifest(self, skill_path: str) -> dict[str, Any]:
        """Inspect a skill's manifest.

        Args:
            skill_path: Path to skill file or directory

        Returns:
            Manifest data
        """
        try:
            path = Path(skill_path)

            # If it's a zip file, extract and inspect
            if path.suffix == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    manifest_names = [n for n in zf.namelist() if n.endswith("manifest.json")]
                    if not manifest_names:
                        return {
                            "success": False,
                            "error": "No manifest found in skill package",
                        }

                    manifest_content = zf.read(manifest_names[0])
                    manifest = json.loads(manifest_content)
            else:
                # Look for manifest.json in directory
                manifest_path = path / "manifest.json"
                if not manifest_path.exists():
                    return {
                        "success": False,
                        "error": "No manifest found",
                    }

                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)

            return {
                "success": True,
                "manifest": manifest,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def validate_skill(self, skill_path: str) -> dict[str, Any]:
        """Validate a skill package.

        Args:
            skill_path: Path to skill file

        Returns:
            Validation result
        """
        try:
            path = Path(skill_path)

            # Inspect manifest
            inspection = self.inspect_skill_manifest(skill_path)
            if not inspection.get("success"):
                return inspection

            manifest = inspection.get("manifest", {})

            # Check required fields
            required_fields = ["name", "version", "description", "entry_point"]
            missing_fields = [f for f in required_fields if f not in manifest]

            if missing_fields:
                return {
                    "success": False,
                    "error": f"Missing required fields: {missing_fields}",
                }

            # Check dependencies (placeholder)
            dependencies = manifest.get("dependencies", [])

            return {
                "success": True,
                "valid": True,
                "name": manifest.get("name"),
                "version": manifest.get("version"),
                "dependencies": dependencies,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def install_skill(self, skill_path: str) -> dict[str, Any]:
        """Install a skill from quarantine.

        Args:
            skill_path: Path to skill in quarantine

        Returns:
            Install result
        """
        try:
            path = Path(skill_path)

            # Validate first
            validation = self.validate_skill(skill_path)
            if not validation.get("success"):
                return validation

            manifest = self.inspect_skill_manifest(skill_path).get("manifest", {})
            skill_name = manifest.get("name", path.stem)

            # Create install directory
            install_dir = self.installed_dir / skill_name
            install_dir.mkdir(exist_ok=True)

            # Extract or copy
            if path.suffix == ".zip":
                with zipfile.ZipFile(path, "r") as zf:
                    zf.extractall(install_dir)
            else:
                shutil.copytree(path, install_dir, dirs_exist_ok=True)

            # Update registry
            skill_entry = {
                "name": skill_name,
                "version": manifest.get("version", "1.0.0"),
                "description": manifest.get("description", ""),
                "path": str(install_dir),
                "entry_point": manifest.get("entry_point", ""),
                "tags": manifest.get("tags", []),
                "status": "installed",
            }

            # Remove existing entry if present
            self.registry["skills"] = [
                s for s in self.registry["skills"] if s["name"] != skill_name
            ]
            self.registry["skills"].append(skill_entry)
            self._save_registry()

            # Remove from quarantine
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()

            return {
                "success": True,
                "name": skill_name,
                "path": str(install_dir),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def update_skill_registry(self) -> dict[str, Any]:
        """Update the skill registry (check for updates, etc.).

        Returns:
            Update result
        """
        try:
            # This is a placeholder for update logic
            # In a real implementation, this would check remote sources

            return {
                "success": True,
                "message": "Registry update completed",
                "skills_count": len(self.registry.get("skills", [])),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def disable_skill(self, name: str) -> dict[str, Any]:
        """Disable a skill.

        Args:
            name: Skill name

        Returns:
            Disable result
        """
        try:
            for skill in self.registry.get("skills", []):
                if skill["name"] == name:
                    skill["status"] = "disabled"
                    self._save_registry()
                    return {
                        "success": True,
                        "name": name,
                        "status": "disabled",
                    }

            return {
                "success": False,
                "error": f"Skill not found: {name}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def enable_skill(self, name: str) -> dict[str, Any]:
        """Enable a disabled skill.

        Args:
            name: Skill name

        Returns:
            Enable result
        """
        try:
            for skill in self.registry.get("skills", []):
                if skill["name"] == name:
                    skill["status"] = "installed"
                    self._save_registry()
                    return {
                        "success": True,
                        "name": name,
                        "status": "enabled",
                    }

            return {
                "success": False,
                "error": f"Skill not found: {name}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def uninstall_skill(self, name: str) -> dict[str, Any]:
        """Uninstall a skill.

        Args:
            name: Skill name

        Returns:
            Uninstall result
        """
        try:
            skill_entry = None
            for skill in self.registry.get("skills", []):
                if skill["name"] == name:
                    skill_entry = skill
                    break

            if not skill_entry:
                return {
                    "success": False,
                    "error": f"Skill not found: {name}",
                }

            # Remove files
            skill_path = Path(skill_entry.get("path", ""))
            if skill_path.exists():
                shutil.rmtree(skill_path)

            # Update registry
            self.registry["skills"] = [
                s for s in self.registry["skills"] if s["name"] != name
            ]
            self._save_registry()

            return {
                "success": True,
                "name": name,
                "message": "Skill uninstalled",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def list_skills(self, status: Optional[str] = None) -> dict[str, Any]:
        """List all skills.

        Args:
            status: Optional status filter

        Returns:
            List of skills
        """
        skills = self.registry.get("skills", [])

        if status:
            skills = [s for s in skills if s.get("status") == status]

        return {
            "success": True,
            "skills": skills,
            "count": len(skills),
        }

    def get_skill_info(self, name: str) -> dict[str, Any]:
        """Get detailed info about a skill.

        Args:
            name: Skill name

        Returns:
            Skill info
        """
        for skill in self.registry.get("skills", []):
            if skill["name"] == name:
                return {
                    "success": True,
                    "skill": skill,
                }

        return {
            "success": False,
            "error": f"Skill not found: {name}",
        }
