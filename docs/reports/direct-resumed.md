> Historical report, anonymized for publication. Historical tool/output names that are not linked refer to the private research workspace. Use the public [reproduction guide](../reproduce.md) and [evidence manifest](../../evidence/2026-09-08/manifest.json).

# Direct selector changes with MCU service resumed on each input

The user approved the next test after the paused-MCU D/C/B sequence retained Windows display state. This variant resumes the MCU while D and C remain physically selected, then returns to B. **Windows confirms no sampled display loss during the resumed-MCU D/C/B trial.** KVM02 completed at 16:28:08 UTC with exact restoration and normal B operation. Its five B masks and HPD-related feedback survived MCU service on D/C, and the same AOC display remained active in all 98 complete Windows samples before, during, and after the trial.

## Exact experiment

`tools/prepare_mux_resume_trial.py` derives the reviewed template from `prepare_mux_hold_trial.py` without executing its generation side effects. Generated scripts:

- `lab/12-direct-mux-b-resume.sh`, pinned KVM03 only, no attached sources.
- `prod-direct-mux-b-resume.sh`, KVM02 only, normal B selected/connected with HPD feedback high, C/D empty.
- Production runner: `tools/collect_ssh.py --direct-mux-b-resume`.

For D, C, then B: pause; write only 0001[6:4] using a read-derived value; verify selector, mode, five HPA masks, and B feedback; resume MCU; verify ffff=01 and heartbeat activity during a six-second hold; pause again and inspect all fields. Stop and restore on the first discrepancy. Paused reads collect all five mask values even if a prior mask or selector differs.

Normal ff05 switching commands are not issued during the sequence. Linux/MCU logical routing and USB stay B. The experiment tests whether normal MCU service tolerates a direct selector change; it does not validate firmware routing-object updates, full normal KVM switching, or video acquisition on empty D/C.

Original selector and masks are restored before final MCU resume. A separate Linux recovery is armed at 45 seconds and disarmed after verified recovery. KVM02 recovery checks normal B feedback; if needed, it performs the previously exercised ordinary empty-C -> B selection to resynchronize firmware state, then rechecks B. No firmware, EDID, boot, or persistent configuration changes are included.

## Source-free KVM03 result

Raw report: `../../evidence/2026-09-08/registers/lab-direct-resumed.json`, exit 0.

| UTC, 2026-09-08 | Event | Result after MCU service |
|---|---|---|
| 16:24:56 | Select D and resume | 0001=be; five masks 02; heartbeat 1f->b3 |
| 16:25:04 | Resume on C, selected at 16:25:03 | 0001=ae; five masks 02; heartbeat 1f->b2 |
| 16:25:11 | Select B and resume | 0001=9e; five masks 02; heartbeat 1e->b2 |
| 16:25:19..16:25:22 | Restore original bytes and original C | All five original zeros restored; normal MCU operation |
| 16:25:23 | Final completion | ffff=01, heartbeat 3e->5d, original C selected |

Mode 0000 stayed 40. Source-free 0314 stayed 88 as expected; no host display claim follows from this lab result. The spare's B HPA bits were established manually before the trial because no sources were attached.

## KVM02 readiness

Read-only check at 16:25:55 UTC: B/channel1, only B connected with [SELECTED] feedback, ffff=01, heartbeat bc->ca. Raw report `output/live-20260908T162555Z-mailbox-state.json`.

The user was asked to start `Watch-CometDisplay.ps1 -DurationSeconds 900`, keep its window open, and leave the KVM UI on B without manual switching. The user replied **READY** before the production experiment. Earlier Windows logs cannot establish behavior for this new test.

## KVM02 completed: MCU running on D and C

Raw report: `../../evidence/2026-09-08/registers/direct-resumed.json`, exit 0. All timestamps are UTC on 2026-09-08, with one-second precision.

| Phase | Select/resume request | Running verified | End of running hold | Paused state verified |
|---|---|---|---|---|
| D | 16:27:41 | 16:27:42 | 16:27:47 | 16:27:48 |
| C | 16:27:48 | 16:27:49 | 16:27:54 | 16:27:56 |
| B | 16:27:56 | 16:27:57 | 16:28:02 | 16:28:03 |

At each paused recheck, physical selector 0001 retained the requested value (be, ae, then 9e), mode 0000 stayed 40, all five HPA masks stayed 02, and 0314 stayed aa. Running ffff=01 was verified on each input. The running MCU published ff07=22 on D, C, and B; its heartbeat advanced 18->92, 19->94, and 0f->4f respectively. The Linux channel cache and MCU logical route remained B throughout; the printed B [SELECTED] label reflects HPD-related feedback rather than capture-route selection.

Restoration began at 16:28:03, restored exact selector 9e and five original 02 masks, and resumed the MCU at 16:28:05. Restoration was verified at 16:28:07. Final completion at 16:28:08 showed ffff=01, heartbeat 1c->29, channel B, and B Connected [SELECTED]. The recovery fallback through ordinary C->B was unnecessary, and the independent recovery was disarmed.

This establishes that the MCU does not necessarily clear B's masks or undo the direct selector during the observed running holds, even with B's source connected. The accompanying Windows log confirms no sampled display loss during those holds. It does not establish a fresh DDC read, electrical HPD continuity, long-term retention, or capture on another connected input. D/C were empty. The existing normal switching path is still known to clear masks on KVM03; this direct route does not synchronize the full MCU routing state or USB/UI selection.

## Windows confirmation

The user supplied the fresh SOURCE-B log. All 98 complete samples from 16:27:22.7186927 through 16:28:11.5702237 UTC show one active monitor and an identical full GDI display state. The only `changed=true` record is the initial baseline sample at logger startup; no later change is recorded. WMI identifies the active AOC3202 display as 32G2WG8, matching the earlier trials. Its maximum sample gap was 0.776461 seconds at startup; no gap exceeded 1.1 seconds.

| Recorded KVM interval, UTC | Windows samples | Active monitor count in every sample | Display-state changes |
|---|---:|---:|---:|
| D resume request to pause request, 16:27:41..16:27:47 | 12 | 1 | 0 |
| C resume request to pause request, 16:27:48..16:27:54 | 12 | 1 | 0 |
| B resume request to pause request, 16:27:56..16:28:02 | 12 | 1 | 0 |
| Entire trial, 16:27:39..16:28:08 | 58 | 1 | 0 |
| Restoration, 16:28:03..16:28:07 | 8 | 1 | 0 |
| After trial, 16:28:08..16:28:11.570 | 8 | 1 | 0 |

The paste again stops at 102,399 bytes and truncates its final JSON line. This time the complete records cover the entire hardware trial and restoration, so no extra log extract is needed. The incomplete line was excluded. The logger metadata specifies 300 seconds despite the requested 900; the shorter duration still encompassed the test. Phase comparisons use second-resolution KVM timestamps, and device clocks were not independently calibrated. Approximately 500 ms sampling does not exclude very short electrical or Windows transitions.

Evidence: `output/SOURCE-B-monitor-20260908T162722-pasted.jsonl`, SHA-256 `97b21b9203d65e06654aaf0712ee024b0df397216e539b756645c2735bab5018`. Parsed correlation: `output/windows-mux-resume-correlation-20260908T162739.json`. Reproduce with `tools/analyze_mux_resume_trial.py PATH_TO_PASTED_LOG`. Analyzing the log made no additional hardware changes.

This removes the requirement to keep the MCU paused throughout the observed holds. Brief pauses were still used to change and inspect the selector. The next unresolved work is longer-duration retention and video capture with another source attached, followed by a switching implementation that accounts for firmware, UI, and USB state. No persistent workaround has been installed.

## User observation and custom-control implications

The user reported that mouse input through the KVM web UI continued to reach B while the UI considered B selected. The user then clarified that B's response was observed through Parsec and the KVM web browser showed **no signal**, despite retaining its B selection label. This is consistent with direct video selection of empty D/C while USB and the Linux channel cache remain on B, and adds an independent capture observation to the register readbacks. It still does not establish successful video acquisition from a different connected source, because D/C were empty.

A custom Linux control service/UI backend is now a plausible direction, potentially with a small kernel interface change to separate USB selection from the ordinary ff05 routing command. The existing channel_store couples SEL GPIO writes to that command; simply calling the stock channel endpoint would re-enter the known mask-clearing path. No replacement MCU firmware is required for the demonstrated register experiments. Replacing MCU firmware remains a separate, larger proposal.

Before claiming functional or fast switching, test capture acquisition between two attached sources, persistent display state on the inactive source, longer holds, and coordinated USB routing. The unchanged MCU routing objects could matter for receiver initialization and video acquisition, even though direct selector values and B's display state survived these holds. Switching latency has not been measured; the scripts intentionally included sleeps for observation.
