> Historical report, anonymized for publication. Historical tool/output names that are not linked refer to the private research workspace. Use the public [reproduction guide](../reproduce.md) and [evidence manifest](../../evidence/2026-09-08/manifest.json).

# Windows confirms the inactive-B HPD trial worked

The local monitor logger from `SOURCE-B` confirms that Windows recognized the same AOC display again while KVM02 still routed HDMI C to capture. The earlier Parsec observations were insufficient to determine this; they must not be treated as failed HPD trials.

## Correlated timeline

Times are UTC on 2026-09-08. KVM phase timestamps have one-second precision; Windows samples have approximately half-second spacing. The clocks were not separately calibrated, but the ordinary disconnect aligns with the C-selection request and recovery occurs about 17 seconds before the return to B.

| Time | Evidence |
|---|---|
| Before 16:00:18 | Windows reports one active monitor: `AOC3202`, WMI name `32G2WG8`. KVM02 selects B. |
| 16:00:18 | KVM requests normal B->C selection. |
| 16:00:18.551 | Windows reports zero monitors; WMI also returns an empty list without error. |
| 16:00:23 | All five B HPA bits have been set and verified while C remains selected. |
| 16:00:23.101 | Windows reports one active `AOC3202` monitor again. WMI identifies the same active `32G2WG8` instance at 16:00:23.115. |
| 16:00:26 | MCU resumes normal service with the temporary masks still applied. |
| 16:00:26.193–16:00:38.715 | All 26 Windows samples report the AOC monitor active during resumed MCU operation and continued C selection. |
| 16:00:39 | Saved-register restoration begins. |
| 16:00:40 | KVM requests normal return to B. |
| Through 16:00:45.726 | Windows continues to report the same active monitor. KVM confirms B selected, normal MCU heartbeat, and successful restoration. |

The approximate observed absent interval was 4.55 seconds. That interval includes the deliberate initial normal switch away from B, before the temporary assertion. It is not a disconnect caused by enabling the override.

## What this establishes

- The five-register runtime override can make this Windows host detect a monitor on **unselected HDMI B**.
- Windows detection survives MCU resume: keeping the MCU paused is unnecessary for the observed 12-second normal-service hold.
- The monitor identity agrees with the valid AOC EDID previously read from the GSV2705's RAM. This test does not prove a fresh DDC read; Windows/WMI can use cached identification.
- The Parsec session dropping does not imply that the monitor remained absent. Its recovery was recorded locally while remote observation was unavailable.

This is not yet the requested persistent solution. The separate source-free KVM03 channel-cycle test established that ordinary port changes clear manually asserted HPA masks. A one-time boot command would therefore be insufficient. A solution must retain the necessary host-facing state during routing changes, then be tested with attached sources and fresh EDID reads. Reasserting after a disconnection does not meet uninterrupted-retention requirements.

No short drop was sampled during restoration and return to B. Those events were close together, and sampling was approximately 500 ms, so this is not proof that the electrical HPD signal stayed continuously high through restoration.

## Evidence completeness and reproduction

The pasted attachment is 102,399 bytes and ends in the middle of its final JSON line. It contains 100 complete samples, three WMI identity records, and the start record; no completion record. Complete samples cover 15:59:55.546 through 16:00:45.726, which includes the entire hardware trial and its return to B. No gap between complete samples exceeds 1.1 seconds. Only the incomplete final line was excluded; no missing data inside the trial interval was interpolated.

- Preserved paste: `output/SOURCE-B-monitor-20260908T155955-pasted.jsonl`
- Paste SHA-256: `55a8417940710249b43812ac5ff58102a03f6be9a7982bbf0d8474cdd7e50bb2`
- KVM raw trial: `../../evidence/2026-09-08/registers/inactive-b-hpa.json`
- Parsed correlation: `output/windows-kvm-trial-correlation-20260908T160018.json`
- Parser: `tools/analyze_windows_trial.py PATH_TO_PASTED_LOG`

This analysis made no hardware changes. KVM02 was left on B by the completed trial.
