import json
import socket
from typing import Optional

from .model import PerceptionFrame, PolicyOutput


class JsonTransport:
    def __init__(self, config: dict) -> None:
        transport_cfg = config["transport"]
        self.mode = str(transport_cfg.get("mode", "stdout"))
        self.udp_host = str(transport_cfg.get("udp_host", "127.0.0.1"))
        self.udp_port = int(transport_cfg.get("udp_port", 8765))
        self._sock: Optional[socket.socket] = None

        if self.mode == "udp":
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def publish(self, frame: PerceptionFrame, policy: PolicyOutput) -> None:
        payload = {
            "perception": frame.to_dict(),
            "policy": policy.to_dict(),
        }
        line = json.dumps(payload, ensure_ascii=False)

        if self.mode == "stdout":
            print(line, flush=True)
            return

        if self.mode == "udp":
            assert self._sock is not None
            self._sock.sendto(line.encode("utf-8"), (self.udp_host, self.udp_port))
            return

        raise ValueError(f"Unsupported transport mode: {self.mode}")
