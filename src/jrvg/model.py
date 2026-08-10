from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple


BBox = Tuple[int, int, int, int]
Point = Tuple[int, int]


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: BBox
    center: Point
    area_ratio: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PerceptionFrame:
    ts: float
    frame_id: int
    fps: float
    width: int
    height: int
    detections: List[Detection]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["detections"] = [item.to_dict() for item in self.detections]
        return data


@dataclass
class VelocityCommand:
    linear_x: float
    angular_z: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PolicyOutput:
    state: str
    target: Optional[str]
    cmd: VelocityCommand
    reason: str

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "target": self.target,
            "cmd": self.cmd.to_dict(),
            "reason": self.reason,
        }
