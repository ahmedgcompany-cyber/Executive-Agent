"""Blender adapter."""

import subprocess
from pathlib import Path
from typing import Any, Optional


class BlenderAdapter:
    """Adapter for Blender automation."""

    def __init__(self, blender_path: Optional[str] = None):
        """Initialize Blender adapter.

        Args:
            blender_path: Path to Blender executable
        """
        self.blender_path = blender_path or "blender"
        self._python_available = False
        self._try_import()

    def _try_import(self) -> None:
        """Try to import bpy (if running inside Blender)."""
        try:
            import bpy
            self._python_available = True
        except ImportError:
            self._python_available = False

    def is_available(self) -> bool:
        """Check if Blender is available.

        Returns:
            True if Blender can be controlled
        """
        try:
            result = subprocess.run(
                [self.blender_path, "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def launch(self, file_path: Optional[str] = None) -> dict[str, Any]:
        """Launch Blender.

        Args:
            file_path: Optional file to open

        Returns:
            Launch result
        """
        try:
            cmd = [self.blender_path]
            if file_path:
                cmd.append(file_path)

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            return {
                "success": True,
                "pid": process.pid,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def run_script(self, script_path: str, blend_file: Optional[str] = None) -> dict[str, Any]:
        """Run a Python script in Blender.

        Args:
            script_path: Path to Python script
            blend_file: Optional blend file to open first

        Returns:
            Script execution result
        """
        try:
            cmd = [self.blender_path, "--background"]

            if blend_file:
                cmd.append(blend_file)

            cmd.extend(["--python", script_path])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def render(
        self,
        blend_file: str,
        output_path: str,
        frame: Optional[int] = None,
    ) -> dict[str, Any]:
        """Render a blend file.

        Args:
            blend_file: Path to blend file
            output_path: Output path
            frame: Optional frame to render (renders all if None)

        Returns:
            Render result
        """
        try:
            cmd = [
                self.blender_path,
                "--background",
                blend_file,
                "--render-output", output_path,
            ]

            if frame is not None:
                cmd.extend(["--render-frame", str(frame)])
            else:
                cmd.append("--render-anim")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            return {
                "success": result.returncode == 0,
                "output_path": output_path,
                "stdout": result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def batch_render(
        self,
        blend_files: list[str],
        output_dir: str,
    ) -> dict[str, Any]:
        """Batch render multiple blend files.

        Args:
            blend_files: List of blend file paths
            output_dir: Output directory

        Returns:
            Batch render result
        """
        results = []

        for blend_file in blend_files:
            filename = Path(blend_file).stem
            output_path = str(Path(output_dir) / f"{filename}.png")

            result = self.render(blend_file, output_path)
            results.append({
                "file": blend_file,
                "result": result,
            })

        successful = sum(1 for r in results if r["result"].get("success"))

        return {
            "success": successful == len(results),
            "total": len(results),
            "successful": successful,
            "results": results,
        }

    def export_model(
        self,
        blend_file: str,
        output_path: str,
        format: str = "fbx",
    ) -> dict[str, Any]:
        """Export a model from a blend file.

        Args:
            blend_file: Path to blend file
            output_path: Export path
            format: Export format

        Returns:
            Export result
        """
        # Create export script
        export_script = f"""
import bpy

# Export based on format
if "{format}" == "fbx":
    bpy.ops.export_scene.fbx(filepath="{output_path}")
elif "{format}" == "obj":
    bpy.ops.export_scene.obj(filepath="{output_path}")
elif "{format}" == "gltf":
    bpy.ops.export_scene.gltf(filepath="{output_path}")
else:
    print(f"Unsupported format: {format}")
"""

        script_path = f"/tmp/blender_export_{id(blend_file)}.py"
        with open(script_path, "w") as f:
            f.write(export_script)

        return self.run_script(script_path, blend_file)
