# Release checks

This is a review checklist, not a security certification. Recheck after adapting the collectors.

## Findings from the 2026-10-31 review

- [x] Host and exact Origin are enforced. Every GET/HEAD must carry `Host: 127.0.0.1:<port>` or `localhost:<port>` (other Hosts → 403); session-open also needs `Origin` equal to this server, port included (another loopback port or no Origin → 403). Tested with direct HTTP requests.
- [x] Status and GPU freshness are tracked separately (10 s / 5 s). When a feed expires its numbers, graph and session cards are cleared and the badge says `partial` or `bridge not responding`. Usage values keep the time they were last read and show `stale` after failure or after 15 min. Tested by killing the bridge with the page open.
- [x] Both Codex rate-limit windows are shown when the CLI reports two.
- [x] Typical ComfyUI time counts only jobs that ComfyUI's history reports as `success`, and shows the sample count.
- [x] The public package's session-card click opens the conversation in the Claude app (owner checked on 2026-10-31).
## Source and assets

- [ ] Exclude personal config, environment files, credentials, logs, backups and runtime caches from the actual upload and Git history. Check `.env.*` and backup-name variants as well as `.env`.
- [ ] Confirm no unexpected analytics or network destination was added. Document default-enabled Codex lookups and environment-key-triggered ElevenLabs requests.
- [ ] Keep `127.0.0.1` binding and avoid public proxies or port forwarding.
- [ ] Review GIF and MP4 independently: subtitles and frame timings may differ. Check transition frames, not only whole-second samples.
- [ ] Listen to the MP4 audio before release; a visual inspection cannot clear spoken private information.
- [ ] Record asset authorship and redistribution permission. The supplied brief attributes `assets/sfx/boot.wav` to the project team's director; this review did not independently establish its provenance.

The owner explicitly approved the work-role labels visible in the session-opening demo on 2026-10-31. Those labels are not a masking requirement. Sampled conversation content was empty or cleared; no sensitive body text was found in those samples.

## Honesty and clean-start checks

- [ ] Test a clean folder with no config and state the required Python, NVIDIA tools, CLI login and desktop-app dependencies.
- [ ] Keep context percentages labeled as last-recorded input estimates. Check missing usage and different context-window sizes.
- [ ] Label ComfyUI elapsed time from first observation, and treat typical time / ETA as estimates with limited samples.
- [ ] Explain that a reachable remote TCP port is not remote GPU monitoring, and a recent backup marker is not an integrity check.
- [x] The main GIF now shows a real session at 80% with the default threshold (no override).

Do not mark a check complete just because it appears in documentation. Use observable results from the package being released.
