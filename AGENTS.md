# Instructions for AI coding agents (Claude Code, Codex, …)

The user wants this dashboard running on **their** PC, showing **their** real data, then reshaped to their taste.
Talk to the user in their language. Keep answers short.

## Setting it up
1. Check what exists before wiring anything: OS, Python 3.9+, `nvidia-smi`, ComfyUI (default `http://127.0.0.1:8188`), Claude Code (`~/.claude/projects`), the Claude desktop app, Codex CLI, other local AI tools the user mentions.
2. Copy `config.example.json` → `config.json` and **delete the example entries the user doesn't have** (services, processes, `remote_pc`, `backup`). Set `context_window` to the model they use (200000 default, 1000000 for 1M-context models).
3. Run `python bridge.py`, open `http://127.0.0.1:8790/`, and check every panel against the source (e.g. `nvidia-smi`, the ComfyUI queue). Report what works, what shows `—`, and why.
4. Desktop icon (users expect it): on Windows create a desktop shortcut to `start.bat` (set its icon if you like), click it, and confirm the dashboard opens in an address-bar-free window. On other OSes build the equivalent launcher.
5. Ask before turning on opt-in sources: `claude_usage` (undocumented Anthropic endpoint using their own Claude Code login), ElevenLabs (needs `ELEVENLABS_API_KEY` in the environment).

## Hard rules
- **Never fake data.** Missing → `—` / "not configured". Old → `stale` with its age. No demo numbers in the shipped page.
- Keep the bridge bound to `127.0.0.1`, keep the Host / exact-Origin checks and the `index.html` + `assets/` allow-list.
- Monitoring stays read-only. The only action is opening a session the user clicked. Never submit ComfyUI jobs, restart services or kill processes while testing.
- Never put keys, tokens, personal paths or conversation text in tracked files. Personal settings go in `config.json` (git-ignored).
- Before editing, back up or commit. After editing, run `python -c "import ast;ast.parse(open('bridge.py',encoding='utf-8').read())"` and check the page in a browser.

## Desktop launcher (most users want this)
- `start.bat` (Windows) = start the bridge if `http://127.0.0.1:8790/` doesn't answer (pythonw, no console), then open Chrome/Edge with `--app=<url>` (no address bar). Desktop shortcut → the file; auto-start → a shortcut in `shell:startup`.
- **Chrome ignores `--window-position` when the user's normal Chrome is already running** — the new window joins that process. `start.bat` avoids this with its own `--user-data-dir` (`%LOCALAPPDATA%\AIControlCenterApp`). Keep it, or the window lands on the wrong monitor.
- Second monitor: set `WINPOS` to that monitor's top-left in Windows virtual-desktop coordinates (can be negative, e.g. `-1920,0`) and enable `FULLSCREEN`. Windows display scaling changes the numbers — check the monitor layout before guessing.
- macOS / Linux: same idea with `open -na "Google Chrome" --args --app=…` or `google-chrome --app=…`, and a login item / autostart entry.

## Things that are hard to find (read before guessing)
- **Context %** = last main-thread assistant `usage` in `~/.claude/projects/*/<session>.jsonl`: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, divided by `context_window`. Skip `"isSidechain": true`. Running sessions: `~/.claude/sessions/*.json` (`sessionId`, `pid`).
- **One-click open**: the Claude desktop app keeps `local_*.json` per conversation with `sessionId` (`local_…`), `cliSessionId` (= JSONL file name) and `title`. Open with `claude://code/continue?session=local_…`. On Windows (Store app) the folder is `%LOCALAPPDATA%\Claude-Data\claude_<package>\claude-code-sessions` — it **moved** in an app update (older: `%LOCALAPPDATA%\Packages\Claude_<package>\LocalCache\Roaming\Claude\claude-code-sessions`). If open stops working, search for the folder again. Details: `docs/HOW_IT_WORKS.md`.
- **ComfyUI job type** is guessed from node class names (`_KIND_WORDS` in `bridge.py`); add the user's custom nodes to `job_kinds` in `config.json`.
- **Windows process times**: convert `CreationDate` with `[DateTimeOffset]…ToUnixTimeSeconds()` — `Get-Date -UFormat %s` is off by the time-zone offset.
- **nvidia-smi** may print temperature as a decimal (`49.07`); parse numbers as float.

## Customizing
The user may ask for anything: new panels, different layout, colors, alerts, another OS. Keep it one HTML file unless they ask otherwise, keep it readable on a side monitor, and keep the rules above. Copy-paste ideas: `docs/AI_CUSTOMIZATION_PROMPTS.md`.
