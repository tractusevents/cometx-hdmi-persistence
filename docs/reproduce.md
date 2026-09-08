# Reproduce the analysis

## Published evidence, no hardware or dependencies

From the repository root, with Python 3.11 or later:

```sh
python tools/correlate.py evidence/2026-09-08/windows/inactive-b-hpa.jsonl evidence/2026-09-08/registers/inactive-b-hpa.json
python tools/correlate.py evidence/2026-09-08/windows/direct-paused.jsonl evidence/2026-09-08/registers/direct-paused.json
python tools/correlate.py evidence/2026-09-08/windows/direct-resumed.jsonl evidence/2026-09-08/registers/direct-resumed.json
python -m unittest discover -s tests -v
python tools/check_publication.py
```

Use `--output output/report.json` to save a correlation. The parser accepts
full logger records and compact `utc/active_gdi_monitors/changed` records.
It reports phase coverage and sample gaps. A malformed interior line or
non-increasing sample time is an error; only an incomplete terminal JSON
line can be excluded explicitly.

Expected results: inactive-B sample count 100, monitor count 1→0→1;
direct-paused sample count 240, always 1; direct-resumed sample count 98,
always 1. UTC clocks were not independently calibrated. These data establish
sampled OS state, not fresh DDC reads or electrical continuity.

## Offline firmware analysis

Supply the five files listed in [inputs/README](../inputs/README.md). The
defaults are `inputs/` for local inputs and `output/` for generated files;
both data directories are excluded from Git.

```sh
python -m venv .venv
# Activate your virtual environment, then:
python -m pip install -r requirements-offline.txt
python tools/offline/analyze.py extract kernel utility firmware
python tools/offline/emulate_rv.py
python tools/offline/emulate_edid_route.py
python tools/offline/verify.py
python tools/offline/rv.py 12640 127c4
```

With no offsets, `rv.py` generates annotated first-slot disassembly and
cross-references. Its annotations are conservative local hints, not full
control-flow analysis. Full disassemblies are generated locally and are not
included in the public repository.

To use files outside the checkout, set `COMETX_INPUTS` and optionally
`COMETX_OUTPUT`. For example, in PowerShell:

```powershell
$env:COMETX_INPUTS = 'D:\my-comet-artifacts'
$env:COMETX_OUTPUT = 'D:\my-comet-analysis'
python tools/offline/analyze.py extract kernel utility firmware
```

The tools are specific to the recorded binary layout. `verify.py` checks
known hashes, FIT payloads, instruction/data layout, and synthetic trace
counts; a different firmware image is a new research target, not a supported
drop-in substitute.

The Unicorn harness executes RV32 instructions against synthetic RAM/MMIO.
It proves instruction effects for the supplied cases. It is not a hardware
HDMI/DDC emulator and cannot establish electrical behavior or timing.
