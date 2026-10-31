# Prompts to make it yours

Open this folder in **Claude Code** or **Codex** (recommended) and paste one of these. Change the words to what you actually want — design, layout, adding or removing panels is all fair game.

Before starting, keep a backup or commit your current files. Replace `<...>` with your preference, use one request at a time, and ask your AI to report the files changed and what it actually verified. Use only data sources you control; do not paste API keys or private conversation logs into a prompt.

### Fit it to my PC
```text
Read index.html and bridge.py in this folder. Look at what is actually installed on my machine
(GPU, local AI tools, ports in use, Claude/Codex setup) and adapt the bridge so every panel shows real data.
Panels for things I don't have should be removed, not faked. Keep it read-only and bound to 127.0.0.1.
Keep the existing explicit session-open action separate from monitoring. Preserve Host/Origin protections.
Explain which readings are measured, estimated, manual, or unavailable, and show their age.
```

### Change the look
```text
Redesign index.html in a <describe a style> look. Keep all the data and behaviour,
keep it one HTML file, and keep it readable from across the room.
```

### Add a panel
```text
Add a panel to index.html for <service / tool>. Collect the data in bridge.py
(read-only, local only, no new pip packages if possible). Show "—" when it is not available.
```

### Remove / rearrange
```text
Remove the <panel> and move the Claude Code sessions to the left column, bigger.
Make the layout still fit a 1360x1300 window.
```

### Change alerts
```text
Turn a session card red at 70% instead of 80%, and play a short sound once when a session crosses it.
Also make GPU temperature red from 80°C.
```

### Another OS
```text
Make bridge.py work on <macOS / Linux>: find where Claude Code and the Claude desktop app keep their
session files on this OS, and open sessions with the right command. Test it and tell me what works.
```

### Make it readable on my monitor
```text
Fit index.html to my <width> x <height> CSS-pixel browser viewport at <OS scaling>%.
Keep important values readable at my usual viewing distance. Show every panel without clipping,
and preserve proportional scaling in smaller windows. Verify long titles and missing-value messages.
```

### Connect my ComfyUI workflows accurately
```text
Read bridge.py and a sanitized example of my <workflow type>. Explain how job type, filename and MP
are detected. Handle linked width/height inputs where possible and show unknown values as —.
Label elapsed time from first observation honestly. Do not include failed or cancelled jobs in
successful-duration estimates, and show the sample count behind typical time. Do not submit jobs.
```

### Find stale data and startup problems
```text
Review index.html and bridge.py with synthetic data only. Check status failure while GPU still
responds, GPU failure while status responds, missing readings, and both Codex rate-limit windows.
Show stale panels separately from live ones, remove expired numbers or mark their age, and report
the exact reproduction steps. Do not start or restart my existing AI services for this test.
```

**Before you trust the numbers:** ask your AI to compare a few values with the source (e.g. `nvidia-smi`, the Claude app's own usage view) and to check that no key or token ended up in a file you might commit.
