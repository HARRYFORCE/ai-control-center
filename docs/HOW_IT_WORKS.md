# How the two quickest features work

These are the two core session features. The implementation below describes this package, not a supported API contract from Claude. Ask your coding AI to check it against your installed app version before adapting it.

## 1. Context % per Claude Code session

This package looks for Claude Code conversation records under:

```
~/.claude/projects/<project-folder>/<session-id>.jsonl
```

When a main-thread assistant record includes a `usage` block, the bridge estimates the last request's input context as:

```
input_tokens + cache_read_input_tokens + cache_creation_input_tokens
```

of the **last main-thread assistant reply** (skip lines with `"isSidechain": true` — those are sub-agents).
Divide by the context-window size you configured (`context_window`, 200,000 by default) to get an estimate. Set the denominator to the model and mode you actually use; one global setting will not correctly represent a mixture of different window sizes. This is the last recorded input usage, not a measurement of the app's current internal state or its remaining capacity. It excludes that reply's output and may lag behind edits or compaction until a new usage record appears.

`bridge.py` → `context_used()` reads only the tail of each file and caches by file size, so it is cheap to poll every few seconds.

To filter running sessions, the bridge reads `~/.claude/sessions/*.json` (`sessionId`, `pid`) when that folder is available. Without it, recent JSONL activity is a fallback and does not prove a session is open. The defaults show at most 8 sessions whose records changed in the last 12 hours; an open but long-idle session may be hidden. Missing usage should show `—`.

The card warns at the raw estimate `>= context_alert_pct` (80 by default); its visible number is rounded. A displayed `80%` can therefore still be just below the warning threshold.

## 2. Click a card → open that conversation in the Claude desktop app

The bridge searches the desktop session files used in the author's tested Windows setup for:

- `sessionId` — like `local_xxxxxxxx-…` (the desktop app's id)
- `cliSessionId` — the Claude Code session id, i.e. the JSONL file name above
- `title` — the name you see in the app

So the mapping is *JSONL file name → `cliSessionId` → `sessionId`*, and the app opens it with a deep link:

```
claude://code/continue?session=local_xxxxxxxx-...
```

On Windows (Store version) the files are under
`%LOCALAPPDATA%\Claude-Data\claude_<package>\claude-code-sessions\…\local_*.json`
(older versions: `%LOCALAPPDATA%\Packages\Claude_<package>\LocalCache\Roaming\Claude\claude-code-sessions`). The location has moved between app versions — if one-click open stops working after an app update, ask your AI to find the folder again.

`bridge.py` → `desktop_sessions()` / `open_session()`. The dashboard sends only the JSONL session id; the bridge looks up the desktop id itself and accepts only ids that match `local_[A-Za-z0-9-]+`.

The same mapping supplies card titles. This is an app-dependent deep link, not a guarantee that arbitrary Claude conversations or every OS are supported. The session-opening recording uses the author's personal build; a fresh public-package click still needs checking.

## Verify your adaptation

1. Compare one card's raw input-token sum with the configured denominator and show the source-record age.
2. Check no-record, closed-process, and mixed-model cases using synthetic files rather than publishing real conversations.
3. Click a known mapped card only when you want the app to open. Reject unknown IDs.
4. Stop or disconnect the data source in a test environment: stale readings must lose their live appearance. The shipped UI drops the status feed after 10 s and the GPU feed after 5 s, and marks usage older than 15 min as stale — keep that behaviour when you change it.
