"""Vision-based tools for screen analysis and UI detection."""

import time
from pathlib import Path
from typing import Any, Optional


class VisionTools:
    """Screen vision and image analysis tools."""

    def __init__(self):
        """Initialize vision tools."""
        self._pyautogui = None
        self._cv2 = None
        self._numpy = None

    def _ensure_pyautogui(self) -> Any:
        """Ensure pyautogui is imported."""
        if self._pyautogui is None:
            try:
                import pyautogui
                self._pyautogui = pyautogui
            except ImportError:
                raise ImportError("pyautogui not installed")
        return self._pyautogui

    def _ensure_cv2(self) -> Any:
        """Ensure opencv is imported."""
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
            except ImportError:
                raise ImportError("opencv-python not installed. Run: pip install opencv-python")
        return self._cv2

    def _ensure_numpy(self) -> Any:
        """Ensure numpy is imported."""
        if self._numpy is None:
            try:
                import numpy as np
                self._numpy = np
            except ImportError:
                raise ImportError("numpy not installed")
        return self._numpy

    def capture_screen_region(
        self,
        left: int = 0,
        top: int = 0,
        width: Optional[int] = None,
        height: Optional[int] = None,
        output_path: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture a region of the screen.

        Args:
            left: Left coordinate
            top: Top coordinate
            width: Region width (full screen if None)
            height: Region height (full screen if None)
            output_path: Optional path to save screenshot

        Returns:
            Screenshot result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            if width is None or height is None:
                screenshot = pyautogui.screenshot()
            else:
                screenshot = pyautogui.screenshot(region=(left, top, width, height))

            if output_path is None:
                output_path = f"screen_capture_{int(time.time())}.png"

            screenshot.save(output_path)

            return {
                "success": True,
                "path": output_path,
                "size": screenshot.size,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_ui_text(self, text: str, confidence: float = 0.8) -> dict[str, Any]:
        """Find text on screen using OCR.

        Args:
            text: Text to find
            confidence: Matching confidence threshold

        Returns:
            Find result with location
        """
        try:
            # This would require pytesseract or similar
            # For now, return a placeholder implementation
            return {
                "success": False,
                "error": "OCR not implemented. Install pytesseract for text detection.",
                "note": "Consider using easyocr or pytesseract for OCR capabilities",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def compare_screens(
        self,
        screenshot1_path: str,
        screenshot2_path: str,
        threshold: float = 0.95,
    ) -> dict[str, Any]:
        """Compare two screenshots for differences.

        Args:
            screenshot1_path: Path to first screenshot
            screenshot2_path: Path to second screenshot
            threshold: Similarity threshold

        Returns:
            Comparison result
        """
        try:
            cv2 = self._ensure_cv2()
            np = self._ensure_numpy()

            # Load images
            img1 = cv2.imread(screenshot1_path)
            img2 = cv2.imread(screenshot2_path)

            if img1 is None or img2 is None:
                return {"success": False, "error": "Could not load one or both images"}

            # Resize to same size if needed
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

            # Calculate difference
            diff = cv2.absdiff(img1, img2)
            gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

            # Threshold
            _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

            # Calculate similarity
            non_zero = np.count_nonzero(thresh)
            total = thresh.size
            similarity = 1 - (non_zero / total)

            # Find contours of differences
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            diff_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                diff_regions.append({"x": x, "y": y, "width": w, "height": h})

            return {
                "success": True,
                "similarity": similarity,
                "is_similar": similarity >= threshold,
                "different_regions": diff_regions,
                "diff_count": len(diff_regions),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def locate_visual_target(
        self,
        target_image_path: str,
        confidence: float = 0.9,
    ) -> dict[str, Any]:
        """Locate a target image on screen.

        Args:
            target_image_path: Path to target image
            confidence: Matching confidence

        Returns:
            Location result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            location = pyautogui.locateOnScreen(target_image_path, confidence=confidence)

            if location:
                return {
                    "success": True,
                    "found": True,
                    "left": location.left,
                    "top": location.top,
                    "width": location.width,
                    "height": location.height,
                    "center": (location.left + location.width // 2, location.top + location.height // 2),
                }
            else:
                return {
                    "success": True,
                    "found": False,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def click_visual_target(
        self,
        target_image_path: str,
        confidence: float = 0.9,
    ) -> dict[str, Any]:
        """Click on a visual target on screen.

        Args:
            target_image_path: Path to target image
            confidence: Matching confidence

        Returns:
            Click result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            location = pyautogui.locateOnScreen(target_image_path, confidence=confidence)

            if location:
                center = pyautogui.center(location)
                pyautogui.click(center)
                return {
                    "success": True,
                    "clicked": True,
                    "location": {"x": center.x, "y": center.y},
                }
            else:
                return {
                    "success": False,
                    "clicked": False,
                    "error": "Target not found on screen",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def detect_ui_state(self, region: Optional[tuple[int, int, int, int]] = None) -> dict[str, Any]:
        """Detect UI state from screen capture.

        Args:
            region: Optional region (left, top, width, height)

        Returns:
            UI state analysis
        """
        try:
            pyautogui = self._ensure_pyautogui()

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            # Basic analysis (placeholder for more sophisticated detection)
            width, height = screenshot.size

            return {
                "success": True,
                "screen_size": {"width": width, "height": height},
                "region": region,
                "note": "Basic UI state detection. Extend with ML models for more analysis.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def wait_for_visual_target(
        self,
        target_image_path: str,
        timeout: float = 10.0,
        confidence: float = 0.9,
    ) -> dict[str, Any]:
        """Wait for a visual target to appear.

        Args:
            target_image_path: Path to target image
            timeout: Maximum wait time in seconds
            confidence: Matching confidence

        Returns:
            Wait result
        """
        try:
            pyautogui = self._ensure_pyautogui()

            start_time = time.time()
            while time.time() - start_time < timeout:
                location = pyautogui.locateOnScreen(target_image_path, confidence=confidence)
                if location:
                    return {
                        "success": True,
                        "found": True,
                        "wait_time": time.time() - start_time,
                        "location": {
                            "left": location.left,
                            "top": location.top,
                            "width": location.width,
                            "height": location.height,
                        },
                    }
                time.sleep(0.5)

            return {
                "success": False,
                "found": False,
                "error": f"Target not found within {timeout} seconds",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
