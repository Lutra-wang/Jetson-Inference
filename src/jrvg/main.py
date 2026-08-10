import argparse
import time

from .config import apply_runtime_overrides, load_config
from .detector import create_detector
from .policy import TargetTrackingPolicy
from .transport import JsonTransport


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Jetson Robot Vision Gateway")
    parser.add_argument("--config", default=None, help="Path to JSON config")
    parser.add_argument("--backend", choices=["mock", "jetson"], default=None)
    parser.add_argument("--camera", default=None, help="Camera URI, reserved for Jetson backend")
    parser.add_argument("--network", default=None, help="jetson-inference network name")
    parser.add_argument("--threshold", type=float, default=None, help="Detection confidence threshold")
    parser.add_argument("--width", type=int, default=None, help="Camera width used for policy metadata")
    parser.add_argument("--height", type=int, default=None, help="Camera height used for policy metadata")
    parser.add_argument("--fps", type=int, default=None, help="Camera FPS used for metadata")
    parser.add_argument("--frames", type=int, default=0, help="Stop after N frames; 0 means forever")
    parser.add_argument("--period", type=float, default=0.1, help="Mock loop period in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    apply_runtime_overrides(
        config,
        backend=args.backend,
        camera=args.camera,
        network=args.network,
        threshold=args.threshold,
        width=args.width,
        height=args.height,
        fps=args.fps,
    )
    selected_backend = str(config["detector"].get("backend", "mock"))

    detector = create_detector(config, selected_backend)
    policy = TargetTrackingPolicy(config)
    transport = JsonTransport(config)

    frame_id = 0
    while args.frames <= 0 or frame_id < args.frames:
        perception = detector.detect(frame=None, frame_id=frame_id)
        decision = policy.update(perception)
        transport.publish(perception, decision)
        frame_id += 1
        if selected_backend == "mock":
            time.sleep(args.period)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
