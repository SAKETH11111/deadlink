from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "deadlink" / "core"

FORBIDDEN_ROOT_IMPORTS = {
    "asyncio",
    "datetime",
    "http",
    "pathlib",
    "random",
    "requests",
    "socket",
    "subprocess",
    "sys",
    "time",
    "urllib",
}

FORBIDDEN_NAMES = {
    "cflib",
    "mavsdk",
    "pymavlink",
    "rclpy",
    "rosbag2_py",
}


def test_core_has_no_io_wall_clock_network_web_or_vehicle_imports() -> None:
    offenders: list[str] = []

    for path in sorted(CORE.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]

            for name in names:
                root = name.split(".")[0]
                if root in FORBIDDEN_ROOT_IMPORTS or root in FORBIDDEN_NAMES:
                    offenders.append(f"{path.relative_to(ROOT)} imports {name}")

    assert offenders == []
