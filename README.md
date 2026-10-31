# AI Control Center

English · [한국어](README.ko.md)

**Your AI workspace, your rules.**
A local dashboard for people who make AI video and images on their own PC and work across several Claude Code sessions — ComfyUI jobs, GPU / VRAM / RAM, per-session context estimates and Claude / Codex usage on one screen. **One HTML page + a small Python bridge**, meant to be reshaped with Claude or Codex.

![AI Control Center dashboard](assets/demo.gif)

*Real readings from the author's PC (session names replaced with English aliases). One session really is at 80% context, so its card is red at the default threshold. The ComfyUI queue happens to be idle here; see the next recording for a running job.*

![Click a session card to open it in Claude](assets/demo-session-open.gif)

*The author's own Korean-language build: a ComfyUI job starts (type, resolution, elapsed, ETA), then one click on a session card opens that conversation in the Claude app. Private list entries are blurred. [MP4 with sound](assets/demo-session-open.mp4)*

---

## Install it with your AI (recommended)

Give the repository to a coding AI that can access files and run tools on your PC (e.g. **Claude Code** or **Codex**) and paste:

```text
Install https://github.com/HARRYFORCE/ai-control-center on my PC. Read the project instructions,
connect the features my setup supports, and run it. Tell me which items you couldn't connect and why.
Finally, make a desktop icon that opens it in a window without an address bar.
I'll change the design and panels to my taste afterwards.
```

When it's done you start it from **one desktop icon**: a click opens the control center in its own window without an address bar (the bridge starts by itself when needed).

That is the intended way to use it. Then keep asking — design, layout, which panels exist, what they show, how they warn you: **vibe-code it into your own control center** (Claude and Codex recommended). Nothing here is precious.

> What matters is access: the AI needs a tool that can read files and run commands on your PC. Logins, API keys and choices like which services to enable are still up to you.

## What's on the screen

| Panel | What it is |
|---|---|
| **Claude Code sessions** | Context estimate from each session's last recorded usage (up to 8 recent sessions). Red at **80%** (configurable). |
| **One-click open** | Click a card → that conversation opens in the Claude desktop app (Windows, tested in the author's setup). |
| **What ComfyUI is making** | Video / image / upscale, output name, MP, elapsed time and an ETA from your past successful runs. |
| GPU · VRAM · temperature · RAM | Live, 10-minute GPU graph, amber → red warnings; virtual-memory warning only when it gets dangerous. |
| ComfyUI memory · local jobs | ComfyUI process memory and uptime; background jobs such as a Topaz upscale. |
| Usage | Claude plan (opt-in) and cloud credit, Codex (both windows), ElevenLabs (with your key), Suno as a manual note. |
| Your stuff | HTTP health checks, local processes, a render PC's reachability, the last backup time. |
| Clock · boot sound | Big clock for a side monitor; a short start-up chime (`localStorage.setItem("acc.bootSound","0")` turns it off). |

Missing or old data shows `—` or `stale`, never invented numbers.

## Keep it on your desktop like a control room

On Windows, double-click **`start.bat`**: it starts the bridge (only if it isn't running yet) and opens the dashboard in its own window without an address bar. Put a shortcut to it on your desktop, or in `shell:startup` to open it every time Windows starts. Window position, size and full screen are three lines at the top of the file.

Or let your AI do it:

```text
Make AI Control Center a desktop icon. One click should start the bridge and open the dashboard
full screen on my second monitor in a window without an address bar. Also start it when Windows starts.
```

## Manual start

```bash
python bridge.py        # Python 3.9+, no extra packages on Windows
```

Open **http://127.0.0.1:8790/**. Settings: copy `config.example.json` to `config.json`. Built on **Windows 11 + NVIDIA + Claude desktop app**; other systems need adapting (your AI can do it).

More: [AI prompts](docs/AI_CUSTOMIZATION_PROMPTS.md) · [How session context % and one-click open work](docs/HOW_IT_WORKS.md) · [Release / security checks](docs/SECURITY_RELEASE_CHECKLIST.md)

## Privacy

- Runs on your PC. The bridge listens on `127.0.0.1` only and serves just the page, `assets/` and its JSON; requests with another Host or Origin are refused.
- Network calls happen only for what you enable: your service checks, Codex usage via the Codex CLI, ElevenLabs with your key, and Claude plan usage (off by default, undocumented endpoint, may break).
- `config.json` is git-ignored — it holds your paths and names. Never commit keys or tokens.

Unofficial personal project, not affiliated with Anthropic, OpenAI, NVIDIA, ComfyUI, ElevenLabs or Suno.

## License

MIT © HARRYFORCE — see [LICENSE](LICENSE).
