> Historical report, anonymized for publication. Historical tool/output names that are not linked refer to the private research workspace. Use the public [reproduction guide](../reproduce.md) and [evidence manifest](../../evidence/2026-09-08/manifest.json).

# Direct D -> C -> B video-selector trial

The user requested switching to D while keeping B alive, then C, then B. **The Windows log confirms no sampled display loss through this direct-selector sequence and subsequent MCU resume on B.** All 240 samples from 16:11:00.066 through 16:12:59.782 UTC show one active monitor and `changed=false`. KVM02's five B HPA masks and current source/HPD-related feedback also remained unchanged at every register sample. The MCU was paused throughout D/C selection; this does not establish retention during ordinary firmware-managed switching.

## What was switched

The firmware's type-0 RX routing path at 0x20012738..0x20012750 writes the physical receiver ID to 0001 bits 6:4. Its following instructions clear 0000 bit 7 and set bit 6. Live baseline 0000 was already 40; it was checked and left unchanged. Only the selector field was changed for the trial: 9e (B), be (D), ae (C), then 9e (B), preserving all other bits.

The MCU stayed paused via ff04=5a / ffff=00 while D and C were selected. This avoided the normal ff05 routing handler and its HPA-clearing operations. Linux's cached channel, MCU routing objects, and USB selection stayed on B. Thus the UI continued to show B. This experiment tests direct selector changes with B's host-facing state retained; it does not establish a complete supported switch path or video acquisition on D/C, which were empty. Normal MCU operation while remaining on D/C has not been tested.

## Preparation and safeguards

- `tools/prepare_mux_hold_trial.py` generates `lab/11-direct-mux-b-hold.sh` and `prod-direct-mux-b-hold.sh` from one template.
- Source-free KVM03 validation completed at 16:11:26 UTC. The spare normally switched from its initial C to B, then used manually established B mask bits for the direct D/C/B sequence. Exact register restoration and return to original C succeeded.
- The user confirmed a fresh Windows logger was READY before KVM02 execution. A 900-second run was requested; the received log metadata says 300 seconds, which still covers this trial if the full file is available.
- KVM02 required model rm4pe, MCU version 1.1 / ID 2705, B selected with normal HPD feedback, and C/D empty. Paused reads also required physical selector B, mode 40, B's five mask bits set, and current B source/HPD-related feedback high.
- Exact selector and mask bytes were saved before changes. A separate Linux recovery was armed for 45 seconds; successful restoration disarmed it. Recovery restores the selector before resuming the MCU. Failed cleanup permits an independent retry; a lock prevents simultaneous recovery writers.
- No EDID, firmware, persistent configuration, or USB writes occurred on KVM02. The existing selected-B masks were left untouched during the selector sequence; recovery wrote back their identical saved values.

## KVM02 observations

All timestamps are UTC on 2026-09-08, with one-second precision.

| Time | Phase | 0001 | B feedback 0314 | Five HPA masks |
|---|---|---|---|---|
| 16:11:38 | Paused baseline B | 9e | aa | all 02 |
| 16:11:38 | Direct select D | be | aa | all 02 |
| 16:11:44 | End D hold | be | aa | all 02 |
| 16:11:44 | Direct select C | ae | aa | all 02 |
| 16:11:51 | End C hold | ae | aa | all 02 |
| 16:11:51 | Direct select B | 9e | aa | all 02 |
| 16:11:57 | End B hold; restore begins | 9e | aa | all 02 |
| 16:11:58 | Resume MCU | restored 9e | — | restored all 02 |
| 16:12:00 | Restoration verified | — | — | — |
| 16:12:01 | Final check | — | ff07-derived B Connected [SELECTED] | — |

Final ffff=01, heartbeat advanced 19->26, and Linux channel remained 1/B. Exit status 0. Internal register sampling is not an electrical HPD measurement and can miss brief transients. Because ff07 is MCU-published, it was not used as a live measurement during the pause; 0314 was read directly.

The first host-confirmed five-mask trial established inactive-B monitor recovery. This new trial instead starts with B already active and preserves its settings while changing only the direct selector. The new Windows log independently confirms the monitor remained active in every sample across the 16:11:38..16:11:51 D/C interval and the 16:11:58 MCU resume.

## Windows result: no sampled display loss

The compact extract supplied by the user contains 240 complete records, covering 16:11:00.0664055 through 16:12:59.7822775 UTC. Every record has `active_gdi_monitors=1` and `changed=false`. Sample spacing ranges from 0.500005 to 0.502994 seconds, with no missing-time gap around the switches or resume.

| Phase, using KVM UTC boundaries | Windows samples | Active monitors in every sample | Recorded changes |
|---|---:|---:|---:|
| D selected, MCU paused, 16:11:38..16:11:44 | 12 | 1 | 0 |
| C selected, MCU paused, 16:11:44..16:11:51 | 14 | 1 | 0 |
| B selected, MCU paused, 16:11:51..16:11:57 | 12 | 1 | 0 |
| Restore, 16:11:57..16:11:58 | 2 | 1 | 0 |
| MCU resumed through end of log, 16:11:58..16:12:59.782 | 124 | 1 | 0 |

The compact extract omits monitor identities and WMI records; the earlier baseline identified the AOC display on this host. The logger's `changed` field reports changes in its sampled display state. Neither it nor a 500 ms sampling interval proves uninterrupted electrical HPD, and a fresh DDC read was not measured. The two device clocks were not independently calibrated. This establishes no observed Windows display loss during the requested bounded selector sequence, with ample samples before and after it.

This first run resumed only after returning to B. The subsequent [running-MCU follow-up](direct-resumed.md) also retained B's masks and Windows monitor state during six-second MCU service holds on D and C. Normal routing changes previously cleared the masks on KVM03; normal switching is therefore still not a demonstrated persistent solution. D and C were empty, so video acquisition on those inputs also remains untested.

## Raw evidence

- `../../evidence/2026-09-08/registers/lab-direct-paused.json`
- `../../evidence/2026-09-08/registers/direct-paused.json`
- `output/SOURCE-B-monitor-direct-mux-compact-20260908.jsonl` (19,198 bytes, SHA-256 `a7b1d442fbf53219b6ff564abf4d473bd6e4674759f3e8f10fa3d5b82de7ddef`)
- `output/windows-direct-mux-correlation-20260908T161136.json`
- Parser: `tools/analyze_direct_mux_trial.py PATH_TO_COMPACT_LOG`
- Runner: `tools/collect_ssh.py --direct-mux-b-hold`

Raw reports include script hashes and full remote output. The Windows extract supplies host-side evidence beyond the source-free spare and production register checks. This log analysis made no hardware changes.

## First Windows paste does not cover the test

The user initially supplied a paste starting at 16:10:06.184 UTC. It is truncated at 102,399 bytes, with 98 complete samples ending at 16:10:55.059 and one incomplete final line. All complete samples show one active AOC monitor, but **every sample precedes the 16:11:36 trial start**. A second paste was byte-for-byte identical. Those pastes alone provide no Windows continuity evidence during the selector changes. The subsequent compact extract above resolves the result without a hardware repeat.

Preserved evidence: `output/SOURCE-B-monitor-20260908T161006-pasted.jsonl`, SHA-256 `b471f132fdde0f0f61f219e012d1eaa10f0903be9f7ba7d2d5c8ad1953305d3e`. Coverage report: `output/windows-direct-mux-paste-coverage-20260908T161006.json`.
