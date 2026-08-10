import math
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Tuple

from .model import Detection, PerceptionFrame


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: Any, frame_id: int) -> PerceptionFrame:
        raise NotImplementedError

    def set_visualization_enabled(self, enabled: bool) -> None:
        return None

    def latest_frame(self) -> Optional[Any]:
        return None


class MockDetector(Detector):
    """Deterministic detector used before Jetson hardware is ready."""

    def __init__(self, width: int = 640, height: int = 480, target_class: str = "person") -> None:
        self.width = width
        self.height = height
        self.target_class = target_class
        self._last_ts = time.time()

    def detect(self, frame: Any, frame_id: int) -> PerceptionFrame:
        now = time.time()
        dt = max(now - self._last_ts, 1e-6)
        self._last_ts = now

        phase = frame_id / 18.0
        box_w = int(self.width * 0.22)
        box_h = int(self.height * (0.38 + 0.06 * math.sin(phase * 0.7)))
        cx = int(self.width * (0.5 + 0.34 * math.sin(phase)))
        cy = int(self.height * 0.55)

        left = max(0, cx - box_w // 2)
        top = max(0, cy - box_h // 2)
        right = min(self.width - 1, cx + box_w // 2)
        bottom = min(self.height - 1, cy + box_h // 2)
        area_ratio = ((right - left) * (bottom - top)) / float(self.width * self.height)

        detections = []
        if frame_id % 40 < 34:
            detections.append(
                Detection(
                    class_name=self.target_class,
                    confidence=0.82,
                    bbox=(left, top, right, bottom),
                    center=(cx, cy),
                    area_ratio=area_ratio,
                )
            )

        return PerceptionFrame(
            ts=now,
            frame_id=frame_id,
            fps=1.0 / dt,
            width=self.width,
            height=self.height,
            detections=detections,
        )


class JetsonInferenceDetector(Detector):
    """Wrapper around dusty-nv/jetson-inference detectNet.

    This class imports Jetson-specific modules lazily so local development can
    still run without Jetson hardware or TensorRT installed.
    """

    def __init__(
        self,
        camera_uri: str = "/dev/video0",
        network: str = "ssd-mobilenet-v2",
        threshold: float = 0.5,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        codec: Optional[str] = None,
    ) -> None:
        try:
            import jetson.inference  # type: ignore
            import jetson.utils  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "jetson-inference is not installed. Build dusty-nv/jetson-inference "
                "on Jetson, or run with --backend mock first."
            ) from exc

        self.camera_uri = camera_uri
        self._jetson_inference = jetson.inference
        self._jetson_utils = jetson.utils
        self.net = jetson.inference.detectNet(network, threshold=threshold)
        options = {
            "width": width,
            "height": height,
            "framerate": fps,
        }
        if codec:
            options["codec"] = codec
        try:
            self.input = jetson.utils.videoSource(camera_uri, options=options)
        except TypeError:
            argv = [
                "jrvg",
                "--input-width={0}".format(width),
                "--input-height={0}".format(height),
                "--input-rate={0}".format(fps),
            ]
            if codec:
                argv.append("--input-codec={0}".format(codec))
            self.input = jetson.utils.videoSource(camera_uri, argv=argv)
        self.width = width
        self.height = height
        self.fps = fps
        self.codec = codec
        self._last_ts = time.time()
        self._visualization_enabled = False
        self._latest_frame: Optional[Any] = None

    def set_visualization_enabled(self, enabled: bool) -> None:
        self._visualization_enabled = enabled

    def latest_frame(self) -> Optional[Any]:
        return self._latest_frame

    def detect(self, frame: Any, frame_id: int) -> PerceptionFrame:
        if frame is None:
            frame = self.input.Capture()
            if frame is None:
                raise RuntimeError(f"failed to capture a frame from {self.camera_uri}")

        now = time.time()
        dt = max(now - self._last_ts, 1e-6)
        self._last_ts = now

        width, height = self._frame_size(frame)
        try:
            raw_detections = self.net.Detect(frame, overlay="none")
        except TypeError:
            raw_detections = self.net.Detect(frame)
        detections = []
        for item in raw_detections:
            left = int(item.Left)
            top = int(item.Top)
            right = int(item.Right)
            bottom = int(item.Bottom)
            cx = int(item.Center[0])
            cy = int(item.Center[1])
            area_ratio = ((right - left) * (bottom - top)) / float(width * height)
            class_name = self.net.GetClassDesc(item.ClassID)
            detections.append(
                Detection(
                    class_name=class_name,
                    confidence=float(item.Confidence),
                    bbox=(left, top, right, bottom),
                    center=(cx, cy),
                    area_ratio=area_ratio,
                )
            )

        if self._visualization_enabled:
            self._latest_frame = self._copy_frame(frame)

        return PerceptionFrame(
            ts=now,
            frame_id=frame_id,
            fps=1.0 / dt,
            width=width,
            height=height,
            detections=detections,
        )

    def _frame_size(self, frame: Any) -> Tuple[int, int]:
        width = getattr(frame, "width", None)
        height = getattr(frame, "height", None)
        if width is not None and height is not None:
            return int(width), int(height)

        shape = getattr(frame, "shape", None)
        if shape is not None and len(shape) >= 2:
            return int(shape[1]), int(shape[0])

        return self.width, self.height

    def _copy_frame(self, frame: Any) -> Optional[Any]:
        try:
            array = self._jetson_utils.cudaToNumpy(frame)
        except Exception:
            return None
        try:
            return array.copy()
        except AttributeError:
            return None


def create_detector(config: dict, backend: Optional[str] = None) -> Detector:
    camera_cfg = config["camera"]
    detector_cfg = config["detector"]
    selected = backend or detector_cfg.get("backend", "mock")

    if selected == "mock":
        return MockDetector(
            width=int(camera_cfg.get("width", 640)),
            height=int(camera_cfg.get("height", 480)),
            target_class=str(detector_cfg.get("target_class", "person")),
        )

    if selected == "jetson":
        return JetsonInferenceDetector(
            camera_uri=str(camera_cfg.get("uri", "/dev/video0")),
            network=str(detector_cfg.get("network", "ssd-mobilenet-v2")),
            threshold=float(detector_cfg.get("threshold", 0.5)),
            width=int(camera_cfg.get("width", 640)),
            height=int(camera_cfg.get("height", 480)),
            fps=int(camera_cfg.get("fps", 30)),
            codec=camera_cfg.get("codec"),
        )

    raise ValueError(f"Unsupported detector backend: {selected}")


def frame_size(config: dict) -> Tuple[int, int]:
    camera_cfg = config["camera"]
    return int(camera_cfg.get("width", 640)), int(camera_cfg.get("height", 480))
