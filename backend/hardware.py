"""Work out what local model this machine can actually run.

The failure this exists to prevent: a model that does not fit in RAM still
loads and still answers, it just pages to disk and slows by roughly a hundred
times, so every request times out and the app silently falls back to its
dumber deterministic path. Picking the model by hand is guesswork, so we
measure the machine and recommend a size that fits.

Stdlib only -- psutil is not a dependency and this must never be the reason a
launch fails, so every probe is best-effort and returns None on any error.
"""
from __future__ import annotations

import platform
import shutil
import subprocess

# Candidate models, smallest first. `size_gb` is the download; `needs_gb` is the
# free RAM the weights plus a working context want at run time.
MODELS = [
    {
        "name": "llama3.2:1b",
        "label": "Llama 3.2 1B",
        "size_gb": 1.3,
        "needs_gb": 2.5,
        "quality": "basic",
        "note": "Reads contact details, experience and skills. Fast enough on any laptop.",
    },
    {
        "name": "llama3.2:3b",
        "label": "Llama 3.2 3B",
        "size_gb": 2.0,
        "needs_gb": 5.0,
        "quality": "good",
        "note": "Noticeably better at bullets and job titles. Wants ~8 GB free.",
    },
    {
        "name": "llama3.1:8b",
        "label": "Llama 3.1 8B",
        "size_gb": 4.9,
        "needs_gb": 10.0,
        "quality": "best",
        "note": "Best wording, but needs real headroom or a GPU.",
    },
]

# A dedicated GPU with this much VRAM lets us step up one tier: the weights sit
# in VRAM instead of competing with everything else for system RAM.
_GPU_TIER_GB = 6.0


def _total_ram_gb() -> float | None:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MemoryStatusEx()
            stat.dwLength = ctypes.sizeof(MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            return stat.ullTotalPhys / (1024 ** 3)
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) / (1024 ** 2)  # kB -> GiB
            return None
        if system == "Darwin":
            out = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5,
            )
            return int(out.stdout.strip()) / (1024 ** 3)
    except Exception:
        return None
    return None


def _free_ram_gb() -> float | None:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MemoryStatusEx()
            stat.dwLength = ctypes.sizeof(MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            return stat.ullAvailPhys / (1024 ** 3)
        if system == "Linux":
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) / (1024 ** 2)
            return None
        if system == "Darwin":
            # No cheap MemAvailable equivalent; total is the honest signal here.
            return None
    except Exception:
        return None
    return None


def _gpu() -> tuple[str | None, float | None]:
    """Return (gpu_name, vram_gb). Best-effort and often (None, None)."""
    system = platform.system()
    try:
        if shutil.which("nvidia-smi"):
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8,
            )
            line = (out.stdout or "").strip().splitlines()
            if line:
                name, _, mem = line[0].partition(",")
                return name.strip(), float(mem.strip()) / 1024  # MiB -> GiB
        if system == "Darwin" and platform.machine() == "arm64":
            # Apple Silicon shares system memory with the GPU, so RAM is the
            # real constraint and there is no separate VRAM figure to report.
            return "Apple Silicon (unified memory)", None
        if system == "Windows":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController | "
                 "Select-Object -First 1 Name).Name"],
                capture_output=True, text=True, timeout=15,
            )
            name = (out.stdout or "").strip()
            if name:
                return name, None
    except Exception:
        return None, None
    return None, None


def _is_integrated(gpu_name: str | None) -> bool:
    if not gpu_name:
        return True
    low = gpu_name.lower()
    return any(w in low for w in ("intel", "uhd", "iris", "vega", "radeon graphics"))


def specs() -> dict:
    total = _total_ram_gb()
    free = _free_ram_gb()
    gpu_name, vram = _gpu()
    return {
        "os": f"{platform.system()} {platform.release()}".strip(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_cores": _cpu_cores(),
        "ram_total_gb": round(total, 1) if total else None,
        "ram_free_gb": round(free, 1) if free else None,
        "gpu": gpu_name,
        "vram_gb": round(vram, 1) if vram else None,
        "gpu_accelerated": bool(vram and vram >= _GPU_TIER_GB),
    }


def _cpu_cores() -> int | None:
    try:
        return __import__("os").cpu_count()
    except Exception:
        return None


def recommend() -> dict:
    """Measure the machine and pick a model, with a plain reason and a warning
    about the sizes that would not work here."""
    sp = specs()
    total = sp["ram_total_gb"]
    free = sp["ram_free_gb"]
    vram = sp["vram_gb"]

    # A real GPU carries the weights, so judge against VRAM. Otherwise judge
    # against RAM -- and against total, not free, since free swings minute to
    # minute and we are picking something the user keeps.
    if vram and vram >= _GPU_TIER_GB:
        budget = vram
        basis = f"{vram:.0f} GB of VRAM on {sp['gpu']}"
    elif total:
        # Leave room for the OS, the browser and this app.
        budget = max(0.0, total - 4.0)
        basis = f"{total:.0f} GB of system RAM"
    else:
        budget = 0.0
        basis = "an unknown amount of memory"

    fits = [m for m in MODELS if m["needs_gb"] <= budget]
    chosen = fits[-1] if fits else MODELS[0]
    too_big = [m for m in MODELS if m["needs_gb"] > budget]

    if not total and not vram:
        reason = (
            "We could not read this machine's memory, so we picked the smallest "
            "model. It runs anywhere."
        )
    elif not fits:
        reason = (
            f"With {basis} there is not enough headroom for a larger model, so "
            f"we picked the smallest one."
        )
    else:
        reason = f"With {basis}, {chosen['label']} is the largest model that fits comfortably."

    warning = ""
    if too_big:
        names = ", ".join(m["label"] for m in too_big)
        warning = (
            f"{names} would not work well here. A model that does not fit in "
            "memory still installs and still answers, but it pages to disk and "
            "runs about a hundred times slower -- slow enough that every request "
            "times out and the app quietly falls back to its basic reader."
        )
    if free is not None and total and free < 2.5:
        warning += (
            f" Only {free:.1f} GB of your {total:.0f} GB is free right now, so "
            "close a few apps before setting up."
        )
    if sp["gpu"] and _is_integrated(sp["gpu"]) and not sp["gpu_accelerated"]:
        warning += (
            f" {sp['gpu']} is integrated graphics, which Ollama cannot use, so "
            "everything runs on the CPU."
        )

    return {
        "specs": sp,
        "recommended": chosen,
        "options": [
            {**m, "fits": m["needs_gb"] <= budget} for m in MODELS
        ],
        "reason": reason,
        "warning": warning.strip(),
    }
