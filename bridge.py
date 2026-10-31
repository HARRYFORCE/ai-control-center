#!/usr/bin/env python3
"""AI Control Center - local bridge.

A small, read-only local server that collects the numbers the dashboard shows
and serves index.html. Python 3.9+ standard library only. Binds to 127.0.0.1.

What it reads (each part is optional and fails independently):
  - Claude Code sessions      ~/.claude/projects/*/*.jsonl  (context window usage)
  - live Claude Code sessions ~/.claude/sessions/*.json     (which sessions are still open)
  - Claude desktop titles     Claude desktop app session list (Windows; used for titles + one-click open)
  - NVIDIA GPU                `nvidia-smi` (utilization, temperature, VRAM)
  - System RAM                Windows API / /proc/meminfo
  - ComfyUI                   HTTP /queue on the configured URL
  - Codex usage               `codex app-server` -> account/rateLimits/read   (if the Codex CLI is installed)
  - Claude plan usage         OPT-IN, see config "claude_usage" (uses your own local Claude Code login)
  - ElevenLabs                OPT-IN, needs ELEVENLABS_API_KEY in the environment
  - Custom services           simple HTTP health checks from config "services"

Nothing is sent anywhere except the optional usage lookups listed above, which go
only to the service that owns the account (Anthropic / OpenAI Codex CLI / ElevenLabs).

Run:  python bridge.py            then open http://127.0.0.1:8790/
"""
import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
IS_WIN = platform.system() == "Windows"
NO_WINDOW = 0x08000000 if IS_WIN else 0

DEFAULTS = {
    "port": 8790,
    "context_window": 200000,          # tokens; set 1000000 if you use a 1M-context model
    "context_alert_pct": 80,           # session card turns red at or above this
    "session_max_age_hours": 12,       # sessions untouched for longer are hidden
    "max_sessions": 8,
    "comfyui_url": "http://127.0.0.1:8188",
    "claude_usage": False,             # opt-in: read plan usage with your local Claude Code login
    "claude_usage_file": "",           # or: read it from a JSON file another tool already writes
    "codex_usage": True,
    "elevenlabs": True,                # only used when ELEVENLABS_API_KEY is set
    "services": [],                    # [{"name": "My API", "url": "http://127.0.0.1:5000/health"}]
    "comfyui_mem_warn_gb": 32,         # ComfyUI process memory: amber / red (long-running ComfyUI tends to grow)
    "comfyui_mem_bad_gb": 38,
    "commit_margin_gb": 40,            # warn when Windows commit charge gets this close to the commit limit
    "pagefile_warn_gb": 10,
    # extra words that mark a ComfyUI node as producing video / image / upscale (built-in names are already known)
    "job_kinds": {"video": [], "image": [], "upscale": []},
    # watch local processes: kind "service" = should be running, kind "job" = shown in the queue panel while running
    "processes": [
        {"name": "Topaz upscale", "kind": "job", "process": "ffmpeg", "cmd_contains": "tvai"}
    ],
    "remote_pc": None,                 # {"name": "Render PC", "host": "192.168.0.20", "port": 22}
    "backup": None,                    # {"name": "Cloud backup", "path": "D:/backup/last.log", "max_age_hours": 26}
    "session_aliases": {},             # {"real title": "shown title"} e.g. for screenshots
    "links": {"suno": "https://suno.com/", "elevenlabs": "https://elevenlabs.io/app/home"},
}


def load_config():
    cfg = dict(DEFAULTS)
    p = HERE / "config.json"
    if p.exists():
        try:
            cfg.update(json.loads(p.read_text("utf-8-sig")))   # -sig: tolerate a BOM (Windows editors add one)
        except ValueError as e:
            print(f"config.json ignored: {e}", file=sys.stderr)
    if os.environ.get("CLAUDE_CONTEXT_WINDOW"):
        cfg["context_window"] = int(os.environ["CLAUDE_CONTEXT_WINDOW"])
    return cfg


CFG = load_config()


def get_json(url, timeout=3, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ------------------------------------------------------------------ GPU (nvidia-smi, 1 s)
GPU = {"util": None, "temp": None, "vram_used": None, "vram_total": None, "t": 0}
GPU_HIST = []   # [(epoch, util)] every 5 s, last 10 minutes


def _num(s):
    try:
        return float(s)
    except ValueError:
        return None


def gpu_loop():
    exe = shutil.which("nvidia-smi")
    if not exe:
        return
    while True:
        try:
            pr = subprocess.Popen([exe, "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total",
                                   "--format=csv,noheader,nounits", "-lms", "1000"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, creationflags=NO_WINDOW)
            for line in pr.stdout:
                v = [_num(x.strip()) for x in line.split(",")[:4]]   # first GPU only
                if len(v) == 4 and None not in v:
                    now = time.time()
                    GPU.update(util=round(v[0]), temp=round(v[1]), vram_used=v[2] / 1024, vram_total=v[3] / 1024, t=now)
                    if not GPU_HIST or now - GPU_HIST[-1][0] >= 5:
                        GPU_HIST.append((now, round(v[0])))
                        del GPU_HIST[:-120]
        except Exception as e:  # noqa: BLE001
            print("nvidia-smi:", e, file=sys.stderr)
        time.sleep(5)


def ram():
    try:
        if IS_WIN:
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                           [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "aev")]
            m = MS(); m.dwLength = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            tot = m.tp / 1024 ** 3
            return {"total_gb": round(tot, 1), "used_gb": round(tot - m.ap / 1024 ** 3, 1), "pct": int(m.dwMemoryLoad)}
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1); info[k] = int(v.split()[0])
        tot, av = info["MemTotal"] / 1024 ** 2, info["MemAvailable"] / 1024 ** 2
        return {"total_gb": round(tot, 1), "used_gb": round(tot - av, 1), "pct": round((tot - av) / tot * 100)}
    except Exception:  # noqa: BLE001  (macOS etc.: not implemented)
        return None


# ------------------------------------------------------------------ processes, ComfyUI memory, virtual memory (every 15 s)
SYS = {"procs": [], "listen": {}, "pagefile_gb": None, "commit": None, "t": 0}
_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$p = Get-CimInstance Win32_Process | ForEach-Object { [pscustomobject]@{pid=$_.ProcessId; name=$_.Name; cmd=$_.CommandLine; mem=$_.PrivatePageCount; start=if($_.CreationDate){([DateTimeOffset]$_.CreationDate).ToUnixTimeSeconds()}else{$null}} }
$l = @{}; Get-NetTCPConnection -State Listen | ForEach-Object { $l["$($_.LocalPort)"] = $_.OwningProcess }
$pf = (Get-CimInstance Win32_PageFileUsage | Measure-Object CurrentUsage -Sum).Sum
@{procs=$p; listen=$l; pagefile_mb=$pf} | ConvertTo-Json -Depth 3 -Compress
"""


def _commit():
    """Windows commit charge (used / limit, GB) - what actually runs out first when big models load."""
    if not IS_WIN:
        return None
    class PI(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in ("ct", "cl", "cp", "pt", "pa", "sc", "kt", "kp", "knp", "ps")] + \
                   [(n, ctypes.c_ulong) for n in ("hc", "pc", "tc")]
    pi = PI(); pi.cb = ctypes.sizeof(PI)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
        return None
    g = pi.ps / 1024 ** 3
    return {"used_gb": round(pi.ct * g, 1), "limit_gb": round(pi.cl * g, 1)}


def sys_loop():
    while True:
        try:
            if IS_WIN:
                out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=40, creationflags=NO_WINDOW).stdout
                j = json.loads(out or "{}")
                procs = j.get("procs") or []
                SYS.update(procs=procs if isinstance(procs, list) else [procs], listen={int(k): v for k, v in (j.get("listen") or {}).items()},
                           pagefile_gb=round((j.get("pagefile_mb") or 0) / 1024, 1), commit=_commit(), t=time.time())
            else:
                try:
                    import psutil  # optional on macOS / Linux
                    SYS.update(procs=[{"pid": p.pid, "name": p.info["name"], "cmd": " ".join(p.info["cmdline"] or []),
                                       "mem": p.info["memory_info"].rss if p.info["memory_info"] else None, "start": int(p.info["create_time"] or 0)}
                                      for p in psutil.process_iter(["name", "cmdline", "memory_info", "create_time"])],
                               listen={c.laddr.port: c.pid for c in psutil.net_connections("tcp") if c.status == "LISTEN" and c.pid}, t=time.time())
                except ImportError:
                    pass
        except Exception as e:  # noqa: BLE001
            print("process scan:", e, file=sys.stderr)
        time.sleep(15)


def _match(p, rule):
    name = (p.get("name") or "").lower()
    if rule.get("process") and rule["process"].lower() not in name:
        return False
    return not rule.get("cmd_contains") or rule["cmd_contains"].lower() in (p.get("cmd") or "").lower()


def processes():
    if not SYS["t"]:
        return None
    out = []
    for r in CFG.get("processes") or []:
        hits = [p for p in SYS["procs"] if _match(p, r)]
        out.append({"name": r.get("name") or r.get("process"), "kind": r.get("kind", "service"), "running": bool(hits), "count": len(hits),
                    "since": min((p["start"] for p in hits if p.get("start")), default=None)})
    return out


def comfyui_process():
    if not SYS["t"]:
        return None
    try:
        port = int(urllib.parse.urlsplit(CFG.get("comfyui_url") or "").port or 8188)
    except ValueError:
        return None
    pid = SYS["listen"].get(port)
    p = next((x for x in SYS["procs"] if x.get("pid") == pid), None)
    if not p:
        return None
    mem = round((p.get("mem") or 0) / 1024 ** 3, 1)
    return {"mem_gb": mem, "started": p.get("start"), "warn_gb": CFG["comfyui_mem_warn_gb"], "bad_gb": CFG["comfyui_mem_bad_gb"]}


def vmem():
    c = SYS.get("commit") or _commit()
    if not c:
        return None
    risk = c["used_gb"] >= c["limit_gb"] - CFG["commit_margin_gb"] or (SYS.get("pagefile_gb") or 0) >= CFG["pagefile_warn_gb"]
    return dict(c, pagefile_gb=SYS.get("pagefile_gb"), risk=risk)


def remote_pc():
    r = CFG.get("remote_pc")
    if not r:
        return None
    import socket
    t0 = time.time()
    try:
        with socket.create_connection((r["host"], int(r.get("port") or 22)), timeout=1.5):
            ok = True
    except OSError:
        ok = False
    return {"name": r.get("name") or r["host"], "ok": ok, "ms": round((time.time() - t0) * 1000) if ok else None}


def backup():
    b = CFG.get("backup")
    if not b:
        return None
    p = Path(b["path"]).expanduser()
    if not p.exists():
        return {"name": b.get("name") or "Backup", "ok": False, "last": None, "error": "path not found"}
    last = p.stat().st_mtime
    return {"name": b.get("name") or "Backup", "last": int(last), "ok": time.time() - last < float(b.get("max_age_hours") or 26) * 3600}


# ------------------------------------------------------------------ Claude Code sessions
def _pid_alive(pid):
    if IS_WIN:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code)); ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259   # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def live_session_ids():
    """Session ids of Claude Code processes that are still running (None if this info is not available)."""
    root = HOME / ".claude" / "sessions"
    if not root.is_dir():
        return None
    ids = set()
    for p in root.glob("*.json"):
        try:
            d = json.loads(p.read_text("utf-8"))
            if d.get("sessionId") and (not d.get("pid") or _pid_alive(d["pid"])):
                ids.add(d["sessionId"])
        except Exception:  # noqa: BLE001
            continue
    return ids


def desktop_sessions():
    """Claude desktop app session list: {cli_session_id: {"id": "local_...", "title": ...}}.
    Verified on Windows (Store app). The folder moved in an app update, so several places are tried."""
    roots = []
    la, ad = Path(os.environ.get("LOCALAPPDATA", "")), Path(os.environ.get("APPDATA", ""))
    roots += [p / "claude-code-sessions" for p in (la / "Claude-Data").glob("claude_*")] if la.name else []
    roots += [p / "LocalCache" / "Roaming" / "Claude" / "claude-code-sessions" for p in (la / "Packages").glob("Claude_*")] if la.name else []
    roots += [ad / "Claude" / "claude-code-sessions", HOME / "Library" / "Application Support" / "Claude" / "claude-code-sessions"]
    out = {}
    for root in roots:
        files = list(root.glob("*/*/local_*.json")) if root.is_dir() else []
        for p in files:
            try:
                d = json.loads(p.read_text("utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if d.get("isArchived") or not d.get("sessionId"):
                continue
            row = {"id": d["sessionId"], "title": d.get("title") or ""}
            for cli in [d.get("cliSessionId")] + list(d.get("priorCliSessionIds") or []):
                if cli:
                    out[cli] = row
        if out:
            break
    return out


_CTX = {}


def context_used(path):
    """Tokens in the context window = input + cache_read + cache_creation of the last main-thread assistant reply."""
    size = path.stat().st_size
    hit = _CTX.get(str(path))
    if hit and hit[0] == size:
        return hit[1]
    used, model = None, None
    for tail in (1 << 20, 4 << 20):
        with open(path, "rb") as f:
            f.seek(max(0, size - tail))
            lines = f.read().decode("utf-8", "replace").splitlines()
        for line in reversed(lines):
            if '"assistant"' not in line or '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("isSidechain") or d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if u:
                used = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                model = msg.get("model")
                break
        if used is not None or size <= tail:
            break
    _CTX[str(path)] = (size, (used, model))
    return used, model


def sessions():
    root = HOME / ".claude" / "projects"
    if not root.is_dir():
        return {"ok": False, "error": "~/.claude/projects not found", "items": []}
    now, max_age = time.time(), CFG["session_max_age_hours"] * 3600
    live = live_session_ids()
    desk = desktop_sessions()
    files = [p for p in root.glob("*/*.jsonl") if now - p.stat().st_mtime < max_age]
    if live is not None:
        files = [p for p in files if p.stem in live]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    items, win = [], CFG["context_window"]
    for p in files[: CFG["max_sessions"]]:
        try:
            used, model = context_used(p)
        except OSError:
            used, model = None, None
        d = desk.get(p.stem)
        title = (d or {}).get("title") or p.parent.name.split("-")[-1] or p.stem[:8]
        title = CFG["session_aliases"].get(title, title)
        age = now - p.stat().st_mtime
        items.append({
            "key": p.stem,                         # used only to ask the bridge to open it
            "title": title,
            "ctx_pct": round(used * 100 / win, 1) if used else None,
            "ctx_used": used, "model": model,
            "state": "working" if age < 120 else "idle",
            "age_sec": int(age),
            "openable": bool(d),
        })
    return {"ok": True, "window": win, "alert_pct": CFG["context_alert_pct"], "live_filter": live is not None, "items": items}


def open_session(key):
    """Open the Claude desktop conversation that belongs to a Claude Code session (claude:// deep link)."""
    d = desktop_sessions().get(str(key))
    if not d or not re.fullmatch(r"local_[A-Za-z0-9-]{1,64}", d["id"]):
        raise ValueError("No Claude desktop conversation found for this session")
    url = f"claude://code/continue?session={d['id']}"
    if IS_WIN:
        os.startfile(url)  # noqa: S606
    else:
        subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", url])
    return {"ok": True}


# ------------------------------------------------------------------ usage (slow, cached in a background loop)
USAGE = {"claude": None, "codex": None, "elevenlabs": None, "checked_at": None}


def codex_usage():
    exe = shutil.which("codex") or shutil.which("codex.cmd")
    if not exe:
        return {"ok": False, "error": "codex CLI not found"}
    proc = subprocess.Popen([exe, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", creationflags=NO_WINDOW)
    lines = []
    threading.Thread(target=lambda: [lines.append(x) for x in proc.stdout], daemon=True).start()
    try:
        def send(o):
            proc.stdin.write(json.dumps(o) + "\n"); proc.stdin.flush()
        send({"method": "initialize", "id": 1, "params": {"clientInfo": {"name": "ai-control-center", "title": "AI Control Center", "version": "0.1"}}})
        time.sleep(1.5)
        send({"method": "initialized"})
        send({"method": "account/rateLimits/read", "id": 2})
        for _ in range(40):
            time.sleep(0.25)
            for x in list(lines):
                try:
                    o = json.loads(x)
                except ValueError:
                    continue
                if o.get("id") == 2 and "result" in o:
                    r = o["result"]
                    rl = ((r.get("rateLimitsByLimitId") or {}).get("codex")) or r.get("rateLimits") or {}
                    conv = lambda w: {"used_percent": w.get("usedPercent"), "window_minutes": w.get("windowDurationMins"), "resets_at": w.get("resetsAt")} if w else None
                    return {"ok": True, "plan": rl.get("planType"), "primary": conv(rl.get("primary")), "secondary": conv(rl.get("secondary"))}
        return {"ok": False, "error": "no answer from codex app-server"}
    finally:
        proc.kill()


def claude_usage_from_file(path):
    """Read plan usage that another local tool already exports (so two tools don't poll the same endpoint).
    Accepts {"windows": [{"label", "percent"|"percentUsed", "resets_at"|"resetsAt"}]}."""
    o = json.loads(Path(path).expanduser().read_text("utf-8-sig"))
    ws = []
    for w in o.get("windows") or []:
        lab = str(w.get("label") or "")
        pct = w.get("percent", w.get("percentUsed"))
        if pct is None:
            continue
        ws.append({"label": "week" if "week" in lab.lower() else "5h" if ("5" in lab or "session" in lab.lower()) else lab,
                   "percent": round(pct), "resets_at": w.get("resets_at", w.get("resetsAt"))})
    cr = next((c for c in o.get("credits") or [] if c.get("limit")), None)
    credit = {"remaining": cr.get("remaining", cr["limit"] - (cr.get("used") or 0)), "limit": cr["limit"], "resets_at": cr.get("resets_at", cr.get("resetsAt"))} if cr else None
    return {"ok": bool(ws), "windows": ws, "credit": credit, "source": "file", **({} if ws else {"error": "no usage windows in file"})}


def claude_usage():
    """OPT-IN. Same endpoint Claude Code uses for /usage. Undocumented - may change or stop working.
    The token is read from your own local Claude Code login and sent only to api.anthropic.com."""
    if CFG.get("claude_usage_file"):
        return claude_usage_from_file(CFG["claude_usage_file"])
    tok = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if not tok:
        for p in (HOME / ".claude" / ".credentials.json", HOME / ".config" / "claude" / ".credentials.json"):
            if p.exists():
                try:
                    o = json.loads(p.read_text("utf-8"))
                    tok = ((o.get("claudeAiOauth") or o).get("accessToken") or "").strip()
                except ValueError:
                    pass
            if tok:
                break
    if not tok:
        return {"ok": False, "error": "no local Claude Code login found"}
    j = get_json("https://api.anthropic.com/api/oauth/usage", timeout=8,
                 headers={"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20", "User-Agent": "ai-control-center/0.1"})
    def win(n, label):
        if not isinstance(n, dict) or n.get("utilization") is None:
            return None
        return {"label": label, "percent": round(n["utilization"]), "resets_at": n.get("resets_at")}
    windows = [w for w in (win(j.get("five_hour"), "5h"), win(j.get("seven_day"), "week")) if w]
    credit = None   # cloud-session credit: the block that carries limit_dollars (its key name is not stable)
    for k, v in j.items():
        if isinstance(v, dict) and isinstance(v.get("limit_dollars"), (int, float)) and v["limit_dollars"] > 0 and k != "extra_usage":
            credit = {"remaining": v.get("remaining_dollars", v["limit_dollars"] - (v.get("used_dollars") or 0)), "limit": v["limit_dollars"], "resets_at": v.get("resets_at")}
            break
    return {"ok": True, "windows": windows, "credit": credit}


def elevenlabs_usage():
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        return None
    j = get_json("https://api.elevenlabs.io/v1/user/subscription", timeout=8, headers={"xi-api-key": key})
    return {"ok": True, "tier": j.get("tier"), "used": j.get("character_count"), "limit": j.get("character_limit"),
            "reset_at": j.get("next_character_count_reset_unix")}


def usage_loop():
    while True:
        for name, enabled, fn in (("codex", CFG["codex_usage"], codex_usage), ("claude", CFG["claude_usage"], claude_usage),
                                  ("elevenlabs", CFG["elevenlabs"], elevenlabs_usage)):
            if not enabled:
                USAGE[name] = None
                continue
            try:
                r = fn()
                USAGE[name] = dict(r, at=int(time.time())) if r else r   # "at" = when this value was last read successfully
            except Exception as e:  # noqa: BLE001
                prev = USAGE.get(name) or {}
                USAGE[name] = dict(prev, ok=False, error=str(e)[:120])   # keeps the old "at" so the page can show it as stale
        USAGE["checked_at"] = int(time.time())
        time.sleep(180)   # the usage endpoints rate-limit; 3 minutes is plenty


# ------------------------------------------------------------------ ComfyUI + custom services
_JOB_START = {}


def comfyui():
    base = (CFG.get("comfyui_url") or "").rstrip("/")
    if not base:
        return None
    try:
        q = get_json(base + "/queue", timeout=2)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": type(e).__name__}
    run, pend = q.get("queue_running") or [], q.get("queue_pending") or []
    now = time.time()
    ids = {str(it[1]): it for it in run if len(it) > 2}
    for k in list(_JOB_START):            # finished jobs -> remember how long they took (per kind) for "typical" / ETA
        if k not in ids:
            started, kind = _JOB_START.pop(k)
            if now - started > 5 and _finished_ok(base, k):   # only successful jobs count toward "typical"
                _DUR.setdefault(kind, []).append(now - started); del _DUR[kind][:-10]
                _save_durations()
    job = None
    for k, it in ids.items():
        info = _job_info(it[2])
        _JOB_START.setdefault(k, (now, info["kind"]))
        d = sorted(_DUR.get(info["kind"]) or [])
        job = dict(info, started=_JOB_START[k][0], typical_sec=round(d[len(d) // 2]) if d else None, samples=len(d))
    return {"ok": True, "running": len(run), "pending": len(pend), "job": job, "process": comfyui_process()}


def _finished_ok(base, prompt_id):
    try:
        h = get_json(f"{base}/history/{prompt_id}", timeout=2).get(prompt_id) or {}
        return (h.get("status") or {}).get("status_str") == "success"
    except Exception:  # noqa: BLE001
        return False


_JOB_START, _DUR = {}, {}
_DUR_FILE = HERE / ".job_durations.json"
try:
    _DUR.update(json.loads(_DUR_FILE.read_text("utf-8")))
except (OSError, ValueError):
    pass


def _save_durations():
    try:
        _DUR_FILE.write_text(json.dumps(_DUR), "utf-8")
    except OSError:
        pass


_KIND_WORDS = {   # node class names -> what the job produces (extend with config "job_kinds")
    "video": ["savevideo", "createvideo", "videocombine", "saveanimated", "savewebm", "wan", "hunyuanvideo", "ltxv", "cogvideo", "animatediff", "i2v", "t2v"],
    "upscale": ["upscale", "seedvr", "esrgan", "supir"],
    "image": ["saveimage", "previewimage"],
}


def _job_info(prompt):
    """Read a queued ComfyUI workflow: what kind of output, a name (filename_prefix), and the resolution in megapixels."""
    nodes = prompt.values() if isinstance(prompt, dict) else []
    classes = [str(n.get("class_type") or "").lower() for n in nodes if isinstance(n, dict)]
    kind = "other"
    for k in ("video", "upscale", "image"):   # order matters: a video workflow often also has SaveImage
        words = _KIND_WORDS[k] + [w.lower() for w in (CFG.get("job_kinds") or {}).get(k, [])]
        if any(w in c for c in classes for w in words):
            if k == "upscale" and any("sampler" in c for c in classes):
                continue                       # a sampler means it generates; the upscaler is just a step
            kind = k
            break
    name, mp = None, None
    for n in nodes:
        inp = n.get("inputs") or {} if isinstance(n, dict) else {}
        if not name and isinstance(inp.get("filename_prefix"), str):
            name = inp["filename_prefix"].replace("\\", "/").split("/")[-1][:40]
        w, h = inp.get("width"), inp.get("height")
        if isinstance(w, (int, float)) and isinstance(h, (int, float)) and w * h > (mp or 0) * 1e6:
            mp = round(w * h / 1e6, 1)
    return {"kind": kind, "name": name, "mp": mp}


def services():
    out = []
    for s in CFG.get("services") or []:
        t0 = time.time()
        try:
            with urllib.request.urlopen(s["url"], timeout=2) as r:
                ok = 200 <= r.status < 400
        except Exception:  # noqa: BLE001
            ok = False
        out.append({"name": s.get("name") or s["url"], "ok": ok, "ms": round((time.time() - t0) * 1000)})
    return out


def status():
    return {"ts": int(time.time()), "sessions": sessions(), "comfyui": comfyui(), "services": services(),
            "processes": processes(), "vmem": vmem(), "remote_pc": remote_pc(), "backup": backup(),
            "ram": ram(), "usage": USAGE, "links": CFG.get("links") or {}}


def gpu_now():
    fresh = GPU["t"] and time.time() - GPU["t"] < 5
    return {"available": bool(GPU["t"]), "fresh": bool(fresh), "util": GPU["util"] if fresh else None, "temp": GPU["temp"] if fresh else None,
            "vram_used": GPU["vram_used"], "vram_total": GPU["vram_total"], "hist": [[int(t), u] for t, u in GPU_HIST], "ram": ram()}


# ------------------------------------------------------------------ HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(HERE), **k)

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _allowed(self, path):
        if path in ("/", "/index.html"):
            return True
        if path.startswith("/assets/") and ".." not in path:   # images / sounds used by the page
            p = (HERE / urllib.parse.unquote(path.lstrip("/"))).resolve()
            return (HERE / "assets").resolve() in p.parents and p.is_file()
        return False

    def _host_ok(self):
        """Reject requests whose Host is not this loopback server (blocks DNS-rebinding pages from reading the JSON)."""
        port = self.server.server_address[1]
        return (self.headers.get("Host") or "").lower() in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_HEAD(self):   # same rule as GET - the base class would otherwise serve any file in the folder
        if not self._host_ok():
            return self.send_error(403)
        if self._allowed(self.path.split("?")[0]):
            return super().do_HEAD()
        self.send_error(404)

    def do_GET(self):
        if not self._host_ok():
            return self.send_error(403)
        path = self.path.split("?")[0]
        if path == "/api/status":
            return self._send(status())
        if path == "/api/gpu":
            return self._send(gpu_now())
        if self._allowed(path):
            return super().do_GET()
        self.send_error(404)   # only index.html and assets/ are served - no directory browsing

    def do_POST(self):
        if self.path.split("?")[0] != "/api/open-session":
            return self.send_error(404)
        # accept only same-origin requests from the dashboard itself: right Host, and Origin exactly this server
        port = self.server.server_address[1]
        if not self._host_ok() or (self.headers.get("Origin") or "") not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
            return self._send({"error": "forbidden"}, 403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            self._send(open_session(body.get("key")))
        except Exception as e:  # noqa: BLE001
            self._send({"error": str(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description="AI Control Center local bridge")
    ap.add_argument("--port", type=int, default=CFG["port"])
    ap.add_argument("--once", action="store_true", help="print one status snapshot and exit")
    a = ap.parse_args()
    if a.once:
        USAGE.update(codex=codex_usage() if CFG["codex_usage"] else None)
        print(json.dumps(status(), ensure_ascii=False, indent=1))
        return
    threading.Thread(target=gpu_loop, daemon=True).start()
    threading.Thread(target=usage_loop, daemon=True).start()
    threading.Thread(target=sys_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"AI Control Center: http://127.0.0.1:{a.port}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
