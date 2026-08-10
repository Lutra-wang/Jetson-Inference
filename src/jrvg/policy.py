from typing import Optional

from .model import Detection, PerceptionFrame, PolicyOutput, VelocityCommand


class TargetTrackingPolicy:
    def __init__(self, config: dict) -> None:
        policy_cfg = config["policy"]
        self.target_class = str(policy_cfg.get("target_class", "person"))
        self.center_deadband = float(policy_cfg.get("center_deadband", 0.12))
        self.max_linear_x = float(policy_cfg.get("max_linear_x", 0.18))
        self.max_angular_z = float(policy_cfg.get("max_angular_z", 0.6))
        self.stop_area_ratio = float(policy_cfg.get("stop_area_ratio", 0.32))
        self.lost_frames_to_stop = int(policy_cfg.get("lost_frames_to_stop", 6))
        self._lost_frames = 0

    def update(self, frame: PerceptionFrame) -> PolicyOutput:
        target = self._select_target(frame)

        if target is None:
            self._lost_frames += 1
            state = "LOST" if self._lost_frames < self.lost_frames_to_stop else "STOP"
            return PolicyOutput(
                state=state,
                target=None,
                cmd=VelocityCommand(linear_x=0.0, angular_z=0.0),
                reason=f"target missing for {self._lost_frames} frames",
            )

        self._lost_frames = 0

        if target.area_ratio >= self.stop_area_ratio:
            return PolicyOutput(
                state="STOP",
                target=target.class_name,
                cmd=VelocityCommand(linear_x=0.0, angular_z=0.0),
                reason="target area exceeds stop threshold",
            )

        error_x = (target.center[0] - frame.width / 2.0) / (frame.width / 2.0)
        angular_z = 0.0 if abs(error_x) < self.center_deadband else -error_x * self.max_angular_z
        linear_x = self.max_linear_x * max(0.0, 1.0 - target.area_ratio / self.stop_area_ratio)

        return PolicyOutput(
            state="TRACKING",
            target=target.class_name,
            cmd=VelocityCommand(
                linear_x=round(linear_x, 3),
                angular_z=round(angular_z, 3),
            ),
            reason="target tracked",
        )

    def _select_target(self, frame: PerceptionFrame) -> Optional[Detection]:
        candidates = [item for item in frame.detections if item.class_name == self.target_class]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.confidence)
