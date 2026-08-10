import json
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.json"


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_runtime_overrides(
    config: Dict[str, Any],
    backend: Optional[str] = None,
    camera: Optional[str] = None,
    network: Optional[str] = None,
    threshold: Optional[float] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    fps: Optional[int] = None,
) -> Dict[str, Any]:
    """Apply CLI overrides in one place so runtime mode stays consistent."""
    camera_cfg = config.setdefault("camera", {})
    detector_cfg = config.setdefault("detector", {})

    if backend is not None:
        detector_cfg["backend"] = backend
    if camera is not None:
        camera_cfg["uri"] = camera
    if network is not None:
        detector_cfg["network"] = network
    if threshold is not None:
        detector_cfg["threshold"] = threshold
    if width is not None:
        camera_cfg["width"] = width
    if height is not None:
        camera_cfg["height"] = height
    if fps is not None:
        camera_cfg["fps"] = fps

    return config
