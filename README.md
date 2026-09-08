# Comet X HDMI persistence investigation

Research and reproducible experiments for **GL.iNet Comet X RM4PE** persistent
HDMI monitor presence. The goal is a fixed EDID, such as 1920×1080 at 60 Hz,
available on every input, with HPD retained on connected sources while capture
and keyboard/mouse selection change.

**This is a research repository, not a finished firmware fix.** No firmware is
flashed by these tools. The recorded tests used the existing EDID on one
connected Windows source; fixed-EDID programming for all four inputs, capture
between multiple active sources, and long-term operation remain unverified.

## What we established

| Experiment | Result | Limit |
|---|---|---|
| Normal input switching | Deselection removes the Windows monitor; manually asserted HPA masks are cleared by ordinary switching on the spare | A one-time boot write is insufficient |
| Assert B's five HPA mask bits while C stays selected | Windows rediscovers its monitor; masks survive MCU resume | Temporary inactive-source retention, existing EDID |
| Direct B → D → C → B selection with MCU paused | All 240 Windows samples retain one active monitor | MCU stayed paused until return to B |
| Direct B → D → C → B, resuming MCU on every input | All 98 complete Windows samples retain the same monitor; masks and selector survive each running hold | D/C were empty; UI/USB/MCU logical route stayed B |

The last test showed “no signal” in the KVM browser on empty D/C while mouse
input still reached B, observed through Parsec. The hardware selector and USB
route can therefore be investigated separately. Capturing a second connected
source is the next decisive check.

The measurements are sampled Windows display state and chip feedback, not
proof of continuously high electrical HPD or a fresh EDID read over DDC.

## Start here

- [Findings and register map](docs/findings.md)
- [Reproduce evidence and offline analysis](docs/reproduce.md)
- [Live experiment procedure and recovery limits](docs/experiments.md)
- [Windows display logger](windows/README.md)
- [Detailed research notebook](docs/research-notebook.md)
- [GL.iNet support email draft](docs/support-email.md)
- [Evidence provenance and anonymization](docs/provenance.md)
- [Implementation goals and acceptance tests](docs/roadmap.md)

## Replay the published evidence

Python 3.11 or later is sufficient; no network or hardware access is needed:

```sh
python tools/correlate.py evidence/2026-09-08/windows/direct-resumed.jsonl evidence/2026-09-08/registers/direct-resumed.json
python -m unittest discover -s tests -v
python tools/check_publication.py
```

Offline disassembly/emulation additionally needs the dependencies in
`requirements-offline.txt` and your own firmware artifacts. The repository
contains no vendor binaries or bundled Python packages.

Live experiments default to **preview only** and require `--execute`, a known
SSH host key, SSH key authentication, an explicit expected hostname, and a
matching source-connection profile. Read the live guide before running them.
They can interrupt a display. Do not treat them as a boot service or install
them on an unattended production KVM.

## Tested platform

- Comet X RM4PE, GSV2705 ID `2705`, MCU version `1.1`.
- Reported build `rm10-1.10.0beta2-26-gc33a82d9f5-dirty`, Linux `6.1.141`.
- GSV2705 on I2C bus 3 at 7-bit address `0x58`; separate downstream GSV1127X on bus 1.
- One connected Windows source; NVIDIA GeForce RTX 5060; existing AOC3202 / 32G2WG8 EDID.
- Recorded trials: September 8, 2026. All evidence timestamps are UTC.

Do not apply these register values to another model or MCU version without
new analysis. Register names used here are analytical labels unless stated
otherwise. See [LICENSE](LICENSE) and [NOTICE](NOTICE.md).
