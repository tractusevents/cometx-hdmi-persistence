# Findings and register map

The supplied Linux driver writes `ff05 = channel + 1` for normal switching.
Its `channel_store` also updates SEL GPIOs used for USB routing. The MCU's
normal routing/state-management path can remove monitor presence on the old
input. The backend's `dummy` and EDID-assignment methods examined in this
build are no-ops; the UI's settings alone do not implement persistence.

The direct selector experiments bypass that normal command. They preserve
B's existing host-facing state while changing the video-selector field,
then let MCU service run during each hold. They do **not** synchronize the
MCU's routing objects, USB destination, or UI channel cache.

## Observed controls

All addresses below are on **I2C bus 3, 7-bit address 0x58**, for the tested
GSV2705 version. Bus 1 at the same address is the separate capture bridge.

| Address | Evidence / use | Important limit |
|---|---|---|
| `ff04` | Heartbeat; writing `5a` enters the decoded wait loop, writing `00` resumes | Wait loop has no local timeout |
| `ffff` | Read `00` while paused, `01` while normally running | No direct write is needed |
| `ff05` | Normal routing request, 1=A through 4=D | Normal switching clears manually asserted masks |
| `0001[6:4]` | Physical type-0 RX selector: 0=A, 1=B, 2=C, 3=D | Full MCU routing bookkeeping is separate |
| `0000[7:6]` | Type-0 path uses `01`; observed full byte `40` | Checked and left unchanged in direct trials |
| `2674`, `00bb`, `00b2`, `00b5`, `00b6` | HPA routines manipulate per-input bits; B is bit 1 | Individual register functions are not all documented; preserve unrelated bits |
| `0310 + 4*input` | Bit 1: source 5V state; bit 5: HPD-related feedback | Feedback is not a voltage measurement |
| `ff07` | Low nibble: source presence; upper nibble: corresponding feedback | Driver's `[SELECTED]` label is feedback, not a route comparison |
| `267a`, `1000..10ff` | Banked EDID storage selector and data window in decoded RAM writer | Shared-bank/all-input DDC behavior is not fully validated |
| `267d` | Per-input bank assignment in decoded setup | Not needed or written in successful connected-source trials |
| `2677` bit 2 | Written by decoded EDID setup | Read back 0 after writing 1 on spare; not proven to be a persistent enable |

Normal non-mailbox reads initially returned misleading zeros. The later
guarded pause/read/resume experiments established internal-register access.
Never use those early zeros as a restoration baseline.

## The three useful results

1. [Inactive-B HPA assertion](reports/inactive-b-hpa.md): after normal B→C
   selection removed the Windows display, setting B's bit in five masks
   restored it while C stayed selected. MCU resume did not immediately undo
   the masks.
2. [Direct selection with MCU paused](reports/direct-paused.md): B→D→C→B
   retained an active Windows display in all 240 samples over two minutes.
3. [Direct selection with MCU resumed](reports/direct-resumed.md): same
   selector sequence, six-second running holds on D/C/B, 98 complete Windows
   samples retaining identical display state. All 58 trial samples were
   unchanged; the first logger sample was only an initial baseline.

The stock channel-cycle test on the source-free spare cleared manually set
masks. Periodically restoring them after a disconnect does not meet the
continuous-presence requirement.

## Code locations

Offsets below use the installed MCU image with base `0x20000000`, first
application slot. Names are analyst labels, not official SDK symbols.

| Role | MCU virtual address |
|---|---|
| Mailbox service | `2000abb4` |
| Routing function called by ff05 handler | `2001d0c8` |
| Type-0 selector write | `20012738..20012750` |
| HPD service / down / up | `2001fc94` / `2001fc14` / `2001fc64` |
| HPA disable / enable | `20015f3e` / `20016236` |
| Other direct disable calls | `2000d79c`, `2000e08c` |
| EDID application / RAM writer | `20021ae0` / `20019ef8` |
| EDID setup routines | `2001a008`, `2001a596` |

The HPA/power-down paths also touch shared receiver resources. A shipping
implementation must preserve those needed for DDC/monitor emulation and
maintain valid software state; suppressing one register write is not yet a
demonstrated fix. See the [notebook](research-notebook.md) for details.
