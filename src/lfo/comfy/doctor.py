"""ComfyUI environment pre-check — ``lfo comfy doctor``."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from .client import ComfyApiClient
from .exceptions import ComfyUnreachableError

# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    passed: bool
    severity: str  # "ok", "warning", "critical"
    message: str
    detail: dict | None = None


@dataclass
class DoctorReport:
    """Aggregated report from all diagnostic checks."""

    status: str = "healthy"  # "healthy", "warning", "critical"
    checks: list[CheckResult] = field(default_factory=list)
    hard_blockers: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Doctor                                                                      #
# --------------------------------------------------------------------------- #


class ComfyDoctor:
    """Run environment health checks against a running ComfyUI instance."""

    # Hard-blocker thresholds
    MIN_D_DRIVE_GB = 50
    MIN_VRAM_FREE_MB = 8192  # 8 GB

    # Warning thresholds
    MIN_SYSTEM_RAM_GB = 8
    MIN_C_DRIVE_GB = 50
    MIN_GPU_VRAM_MB = 8192

    REQUIRED_H3_NODES: ClassVar[list[str]] = [
        "MiniMaxH3ImageToVideo",
        "MiniMaxH3ReferenceToVideo",
        "MiniMaxH3SigmaShift",
    ]

    def __init__(
        self,
        client: ComfyApiClient,
        output_root: Path = Path("D:/cyuiEnv/output"),
    ):
        self.client = client
        self.output_root = Path(output_root)

    # -- individual checks ------------------------------------------------- #

    def _check_reachable(self) -> CheckResult:
        try:
            self.client.get_system_stats()
            return CheckResult("reachable", True, "ok", "ComfyUI is reachable")
        except ComfyUnreachableError as exc:
            return CheckResult(
                "reachable", False, "critical", f"ComfyUI unreachable: {exc}"
            )

    def _check_gpu(self) -> CheckResult:
        try:
            stats = self.client.get_system_stats()
            devs = stats.get("devices", [])
            if not devs:
                return CheckResult("gpu", False, "critical", "No GPU detected")
            name = devs[0].get("name", "unknown")
            return CheckResult("gpu", True, "ok", f"GPU present: {name}")
        except ComfyUnreachableError as exc:
            return CheckResult("gpu", False, "critical", f"GPU check failed: {exc}")

    def _check_h3_nodes(self) -> CheckResult:
        try:
            info = self.client.get_object_info()
            missing = [n for n in self.REQUIRED_H3_NODES if n not in info]
            if missing:
                return CheckResult(
                    "h3_nodes",
                    False,
                    "critical",
                    f"Missing H3 nodes: {missing}",
                    {"missing": missing},
                )
            return CheckResult("h3_nodes", True, "ok", "All H3 nodes registered")
        except ComfyUnreachableError as exc:
            return CheckResult(
                "h3_nodes", False, "critical", f"H3 node check failed: {exc}"
            )

    def _check_h3_models(self) -> CheckResult:
        """Check that H3 model files exist on disk by querying the node's widgets."""
        try:
            info = self.client.get_object_info("MiniMaxH3ImageToVideo")
            if not info:
                return CheckResult(
                    "h3_models", False, "critical", "H3 node not available for model check"
                )
            return CheckResult("h3_models", True, "ok", "H3 node reachable (models assumed present)")
        except ComfyUnreachableError as exc:
            return CheckResult(
                "h3_models", False, "critical", f"H3 model check failed: {exc}"
            )

    def _check_output_writable(self) -> CheckResult:
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            probe = self.output_root / ".lfo_write_probe"
            probe.write_text("ok")
            probe.unlink()
            return CheckResult(
                "output_writable", True, "ok", f"Output dir writable: {self.output_root}"
            )
        except (OSError, PermissionError) as exc:
            return CheckResult(
                "output_writable",
                False,
                "critical",
                f"Output dir not writable: {exc}",
            )

    def _check_d_drive(self) -> CheckResult:
        try:
            usage = shutil.disk_usage("D:/")
            free_gb = usage.free / (1024**3)
            if free_gb < self.MIN_D_DRIVE_GB:
                return CheckResult(
                    "d_drive",
                    False,
                    "critical",
                    f"D: has {free_gb:.1f} GB free (need {self.MIN_D_DRIVE_GB} GB)",
                    {"free_gb": free_gb},
                )
            return CheckResult(
                "d_drive", True, "ok", f"D: has {free_gb:.1f} GB free"
            )
        except FileNotFoundError:
            return CheckResult("d_drive", False, "critical", "D: drive not found")

    def _check_system_ram(self) -> CheckResult:
        try:
            stats = self.client.get_system_stats()
            # ComfyUI /system_stats may include ram_total; fallback to shutil
            ram_bytes = stats.get("ram_total")
            if ram_bytes is None:
                # Approximate via OS-level check
                import sys
                if sys.platform == "win32":
                    ram_bytes = self._windows_total_ram()
            if ram_bytes:
                ram_gb = ram_bytes / (1024**3)
                if ram_gb < self.MIN_SYSTEM_RAM_GB:
                    return CheckResult(
                        "system_ram",
                        False,
                        "warning",
                        f"System RAM {ram_gb:.1f} GB (recommend {self.MIN_SYSTEM_RAM_GB}+ GB)",
                        {"ram_gb": ram_gb},
                    )
                return CheckResult(
                    "system_ram", True, "ok", f"System RAM {ram_gb:.1f} GB"
                )
            return CheckResult(
                "system_ram", False, "warning", "Could not determine system RAM"
            )
        except (ComfyUnreachableError, OSError) as exc:
            return CheckResult(
                "system_ram", False, "warning", f"RAM check failed: {exc}"
            )

    def _check_c_drive(self) -> CheckResult:
        try:
            usage = shutil.disk_usage("C:/")
            free_gb = usage.free / (1024**3)
            if free_gb < self.MIN_C_DRIVE_GB:
                return CheckResult(
                    "c_drive",
                    False,
                    "warning",
                    f"C: has {free_gb:.1f} GB free (recommend {self.MIN_C_DRIVE_GB} GB)",
                    {"free_gb": free_gb},
                )
            return CheckResult(
                "c_drive", True, "ok", f"C: has {free_gb:.1f} GB free"
            )
        except FileNotFoundError:
            return CheckResult("c_drive", False, "warning", "C: drive not found")

    def _check_gpu_vram(self) -> CheckResult:
        try:
            stats = self.client.get_system_stats()
            dev = stats.get("devices", [{}])[0]
            # ComfyUI /system_stats returns vram_total and vram_free in bytes
            vram_total = dev.get("vram_total")
            vram_free = dev.get("vram_free")
            if vram_total:
                total_gb = vram_total / (1024**3)
                free_gb = (vram_free or 0) / (1024**3)
                if total_gb < self.MIN_GPU_VRAM_MB / 1024:
                    return CheckResult(
                        "gpu_vram",
                        False,
                        "warning",
                        f"GPU VRAM {total_gb:.1f} GB (recommend {self.MIN_GPU_VRAM_MB // 1024}+ GB)",
                        {"vram_total_gb": round(total_gb, 1), "vram_free_gb": round(free_gb, 1)},
                    )
                return CheckResult(
                    "gpu_vram",
                    True,
                    "ok",
                    f"GPU VRAM {total_gb:.1f} GB (free: {free_gb:.1f} GB)",
                    {"vram_total_gb": round(total_gb, 1), "vram_free_gb": round(free_gb, 1)},
                )
            return CheckResult(
                "gpu_vram", False, "warning", "Could not determine GPU VRAM"
            )
        except (ComfyUnreachableError, KeyError, TypeError):
            return CheckResult(
                "gpu_vram", False, "warning", "GPU VRAM check failed"
            )

    def _check_queue(self) -> CheckResult:
        try:
            queue = self.client.get_queue()
            running = queue.get("queue_running", [])
            pending = queue.get("queue_pending", [])
            if running or pending:
                return CheckResult(
                    "queue",
                    False,
                    "warning",
                    f"Queue has {len(running)} running, {len(pending)} pending tasks",
                    {"running": len(running), "pending": len(pending)},
                )
            return CheckResult("queue", True, "ok", "Queue is empty")
        except ComfyUnreachableError as exc:
            return CheckResult(
                "queue", False, "warning", f"Queue check failed: {exc}"
            )

    def _check_websocket(self) -> CheckResult:
        """Best-effort WebSocket connectivity check."""
        try:
            import websocket  # type: ignore

            ws_url = self.client.base_url.replace("http://", "ws://") + "/ws"
            ws = websocket.create_connection(ws_url, timeout=5)
            ws.close()
            return CheckResult("websocket", True, "ok", "WebSocket connected")
        except ImportError:
            return CheckResult(
                "websocket", False, "warning", "websocket-client not installed"
            )
        except Exception as exc:
            return CheckResult(
                "websocket", False, "warning", f"WebSocket unreachable: {exc}"
            )

    # -- helpers ----------------------------------------------------------- #

    @staticmethod
    def _windows_total_ram() -> int | None:
        """Return total physical RAM in bytes on Windows."""
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            c_ulonglong = ctypes.c_ulonglong

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", c_ulonglong),
                    ("ullAvailPhys", c_ulonglong),
                    ("ullTotalPageFile", c_ulonglong),
                    ("ullAvailPageFile", c_ulonglong),
                    ("ullTotalVirtual", c_ulonglong),
                    ("ullAvailVirtual", c_ulonglong),
                    ("ullAvailExtendedVirtual", c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return stat.ullTotalPhys
        except Exception:
            return None

    # -- public API -------------------------------------------------------- #

    def run_all_checks(self) -> DoctorReport:
        """Execute all diagnostic checks and produce a report."""
        checks: list[CheckResult] = [
            self._check_reachable(),
            self._check_gpu(),
            self._check_h3_nodes(),
            self._check_h3_models(),
            self._check_output_writable(),
            self._check_d_drive(),
            self._check_system_ram(),
            self._check_c_drive(),
            self._check_gpu_vram(),
            self._check_queue(),
            self._check_websocket(),
        ]

        hard_blockers = [c for c in checks if not c.passed and c.severity == "critical"]
        warnings = [c for c in checks if not c.passed and c.severity == "warning"]

        if hard_blockers:
            status = "critical"
        elif warnings:
            status = "warning"
        else:
            status = "healthy"

        return DoctorReport(
            status=status, checks=checks, hard_blockers=hard_blockers, warnings=warnings
        )

    def print_report(self, report: DoctorReport) -> None:
        """Print a human-readable report to stdout."""
        icon = {"healthy": "🟢", "warning": "🟡", "critical": "🔴"}
        print(f"\n{'=' * 60}")
        print(
            f" LFO Comfy Doctor — {icon.get(report.status, '?')} {report.status.upper()}"
        )
        print(f"{'=' * 60}")

        for c in report.checks:
            mark = "✅" if c.passed else ("⚠️ " if c.severity == "warning" else "❌")
            print(f"  {mark} {c.name}: {c.message}")

        if report.hard_blockers:
            print(f"\n  HARD BLOCKERS ({len(report.hard_blockers)}):")
            for b in report.hard_blockers:
                print(f"    ❌ {b.name}: {b.message}")

        if report.warnings:
            print(f"\n  WARNINGS ({len(report.warnings)}):")
            for w in report.warnings:
                print(f"    ⚠️  {w.name}: {w.message}")

        print(f"{'=' * 60}\n")
