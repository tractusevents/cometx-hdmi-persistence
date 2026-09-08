Subject: Comet X RM4PE: persistent fixed EDID/HPD required on all HDMI inputs — reproduction and engineering findings

Hello GL.iNet Support,

Please escalate this to the Comet X firmware team and, if necessary, GScoolink's GSV2705 engineering team.

I need a persistent monitor-emulation mode on the Comet X RM4PE. Every connected computer must continuously see the KVM as the same monitor, regardless of which input is selected for capture. I want one fixed EDID profile, for example with 1920×1080 at 60 Hz as the preferred timing, available on all four HDMI inputs.

Changing the selected input must not pulse HDMI HPD, change the EDID, remove/re-add the monitor in Windows, or cause display/window rearrangement. From each computer's display subsystem, KVM input selection should be invisible. Video capture and keyboard/mouse routing should follow the selected input without disturbing the other computers' display connections.

We have isolated the problem and demonstrated a reversible register-level proof of concept. We have not yet implemented a complete fixed-EDID solution; the steps below distinguish the requested firmware changes from the exact experiment that already worked.

Environment

- GL.iNet Comet X, model RM4PE; two identical units used for testing.
- Reported OS build: rm10-1.10.0beta2-26-gc33a82d9f5-dirty; Linux 6.1.141.
- GSV2705 HDMI switch: Linux I2C bus 3, 7-bit address 0x58; chip ID 0x2705, MCU version 1.1.
- Installed MCU image: gsv2705v1.1.bin, SHA-256 8899203220fe5b5c8b41464e48ad662834d4ea8ed4ba1b8e2e1e77e0e0995ffc. This identifies the installed file, not an independent readback of the active flash slot.
- Downstream GSV1127X capture bridge: I2C bus 1, address 0x58. These are separate devices.

How to reproduce the product defect

1. Connect a Windows computer to physical HDMI B / UI Port 2 / Linux channel 1. Leave C and D empty.
2. Select B normally. Windows detects the monitor.
3. Select C / UI Port 3 / Linux channel 2 normally. Windows loses the monitor even though HDMI B remains physically connected. The KVM still reports B as Connected.
4. Return to B. Windows detects the monitor again.

The normal Linux interface is `/sys/bus/i2c/devices/3-0058/channel`, using 0=A, 1=B, 2=C, 3=D. The driver sends the MCU mailbox command `0xff05 = channel + 1` and also updates the USB-selection GPIOs. The HPD loss occurs through the normal switching path.

Local analysis and temporary workaround I implemented

I investigated this using files copied from my own unit: the boot image, device tree, kernel symbol list, GSV2705 MCU image, vendor upgrade utility, and KVMD backend. I extracted and disassembled the ARM64 kernel's GSV2705 driver, then traced the corresponding routing and HPD routines in the embedded RISC-V MCU image. This let me identify the actual hardware operations behind the UI, rather than relying on the exposed `dummy=true` setting or logical EDID assignment.

The stock control path is effectively:

```text
Web/API input selection
  -> RM4PE backend writes the Linux channel attribute
  -> driver changes USB-selection GPIOs and writes ff05 = channel + 1
  -> MCU processes its normal routing/state-management path
  -> the deselected computer loses its monitor
```

I built local Python runners that send guarded shell scripts over root SSH to the KVM. Those scripts use `i2ctransfer` on bus 3 to control the GSV2705 directly. I first validated each new sequence on my second, source-free unit, then ran the bounded experiment on the unit with the Windows computer connected to B.

My temporary control path deliberately bypasses the stock channel/API operation during the D/C/B experiment:

```text
Keep Linux's selected-channel cache, MCU logical route, and USB on B
  -> request MCU wait state using ff04=5a; require ffff=00
  -> change only the physical video-selector field 0001[6:4]
  -> preserve B's existing five HPA mask values
  -> resume the existing MCU firmware using ff04=00
  -> hold on D or C with MCU service running, then inspect the state
```

In the first successful inactive-B experiment I explicitly set B's bit in the five masks (`2674`, `00bb`, `00b2`, `00b5`, `00b6`) after a normal switch had cleared them. In the later switching experiment I started with B working normally, preserved its existing `02` mask values, and changed only the video selector between holds. I did not continuously poll and reapply HPD after it dropped. The masks survived the observed running-MCU intervals without being rewritten during those holds.

I also wrote a read-only PowerShell logger on the Windows computer, using `EnumDisplayDevicesW` approximately every 500 ms and `WmiMonitorID` on state changes. It flushed timestamped records to a local file so a Parsec or NDI interruption could not hide a later display recovery. I correlated those records with UTC phase markers from the KVM scripts. During the latest test, Windows retained the same display throughout, the KVM web viewer showed “no signal” while the selector addressed empty D/C, and mouse input from the web UI still reached B, observed through Parsec. The UI's B label remained unchanged because I had intentionally bypassed its normal bookkeeping.

This was a temporary Linux-side controller for the existing hardware. I did not replace the MCU firmware, modify the kernel or boot configuration, program new EDID bytes, or install a Windows EDID override as part of these experiments. The scripts restored the saved register values and normal B operation at the end. No permanent replacement switching service has been installed. The precise sequence and measured results follow below.

Requested firmware implementation

1. Add a persistent fixed-EDID / keep-monitor-connected mode. Store a valid EDID with stable manufacturer/product/serial information, valid block checksums, and 1920×1080@60 as the preferred timing. Changing the selected input must never rewrite or replace this profile.
2. During initialization, load that profile into the GSV2705's source-facing EDID storage and configure all four input DDC interfaces to serve it independently of capture selection. Use the documented GScoolink SDK/bank-assignment sequence, and complete initialization before asserting HPD. Programming only the downstream GSV1127X is insufficient to satisfy this requirement.
3. Keep HPD asserted for every connected source in this mode, including sources on unselected inputs. Keep the EDID/DDC resources required by those sources available. Deselecting an input must not run its HPD-down path, clear its HPA masks, disable its EDID/DDC access, or power down a shared resource needed for monitor emulation.
4. Separate capture routing from display-presence policy. On each input change, update the video selector and the necessary receiver/transmitter firmware state without withdrawing HPD or changing EDID on any connected input. Coordinate keyboard/mouse routing and the UI's selected-port state with this operation. Our direct-selector experiment deliberately bypassed that bookkeeping and is not a complete shipping implementation.
5. Make the mode apply to all normal switching paths: web UI, API, and physical controls where supported. Persist the chosen EDID/mode across reboot and initialize it on every input. The RM4PE backend must actually implement this behavior; its currently exposed `dummy` and EDID-assignment interfaces do not provide it. In the examined backend, `Chain.set_edids`, `Chain.set_dummies`, `Device.request_set_edid`, and `Device.request_set_dummy` are no-ops.
6. Prevent the clears during switching. Do not implement this as a background task that reasserts HPD after a disconnect, or just a one-time write at boot: both fail the requirement that the client continuously retain its display.

Exact experiment that already worked

The following is the measured sequence on the identified hardware/MCU version, intended for your engineering reproduction. The executed scripts checked model/chip/version and initial state, saved original values, and armed an independent 45-second Linux recovery process before any changes. Recovery restores the original selector and masks, resumes the MCU, and verifies normal B operation. The MCU pause loop itself has no local timeout.

All register addresses below are 16-bit addresses on I2C bus 3, 7-bit address 0x58. The transaction formats are:

```text
Read:  i2ctransfer -f -y 3 w2@0x58 HI LO r1
Write: i2ctransfer -f -y 3 w3@0x58 HI LO VALUE
```

1. Start with B selected and its Windows display active, C/D empty. After arming recovery, write `ff04=5a`, wait one second, and require `ffff=00`. This puts the MCU's ordinary management loop into a wait state and makes the internal registers accessible. Reads made during normal `ffff=01` operation had returned misleading zeros on these internal pages.
2. Read and save `0001`, `2674`, `00bb`, `00b2`, `00b5`, and `00b6`. Our baseline was `0001=9e`, all five other registers `02`. Read `0000=40` and `0314=aa`. Do not substitute assumed values for the saved bytes on another unit.
3. Change only the physical video-selector field, `0001[6:4]`, to D. The general operation is `new = (saved_0001 & 0x8f) | (channel << 4)`; for this baseline D was `0001=be`. Leave the existing five B mask values unchanged. Leave `0000` unchanged; its baseline mode was already `40`.
4. Verify the selector and five masks, then write `ff04=00` to resume the MCU. After one second, verify `ffff=01`. Hold for approximately six seconds in total and verify the heartbeat advances. The running MCU reported `ff07=22`.
5. Pause again with `ff04=5a`, wait one second, and verify `ffff=00`. Read the selector, mode, five masks, and B feedback. On our unit these remained `0001=be`, `0000=40`, masks all `02`, and `0314=aa`. Stop and restore on any unexpected change.
6. Repeat steps 3–5 for C (`0001=ae`), then B (`0001=9e`), resuming normal MCU service for each hold. The expected selector and B mask/feedback values survived every hold.
7. While paused, restore the exact saved selector and all five saved masks, verify the readbacks, and write `ff04=00`. Verify `ffff=01`, advancing heartbeat, and normal B status before disarming recovery.

This is the actual sequence from the September 8, 2026 test. D select/resume occurred at 16:27:41 UTC, C at 16:27:48, and B at 16:27:56. Restoration completed at 16:28:07, with final normal-operation checks at 16:28:08.

Windows logging showed the same active AOC3202 / 32G2WG8 display in every complete sample: 98 samples total, including 58 during the trial, with no display-state changes after the initial logger baseline. The MCU was running while D and C remained selected. The KVM browser showed “no signal” on the empty inputs; mouse input still reached B, confirmed through Parsec, because USB and the UI's cached selection were deliberately left on B.

In a separate trial, selecting C normally first cleared B's five mask bits and removed the Windows display. Pausing and setting bit 1 with `register |= 0x02` in `2674`, `00bb`, `00b2`, `00b5`, and `00b6` restored Windows display detection while C remained selected; the masks survived MCU resume. Conversely, ordinary channel changes on the source-free second unit cleared manually asserted masks. These results support addressing the firmware's disconnect policy rather than treating the hardware as inherently unable to retain an inactive source's monitor.

Useful locations in the supplied MCU image

These are analyst-assigned function names from the installed binary, not claimed official SDK symbols. VAs use image base 0x20000000; subtract that base for offsets in the analyzed first application slot.

- Normal `ff05` handler calls routing code at `0x2001d0c8`.
- Type-0 physical selector write: `0x20012738..0x20012750`, setting `0001[6:4]`. Following writes configure `0000[7:6]=01`.
- RX HPD service: `0x2001fc94`; down/up paths: `0x2001fc14` / `0x2001fc64`.
- HPA disable/enable: `0x20015f3e` / `0x20016236`. These manipulate the per-input bit in `2674` and the low-nibble masks in `00bb`, `00b2`, `00b5`, and `00b6`. Preserve unrelated bits. Direct disable calls also occur at `0x2000d79c` and `0x2000e08c`, so changing only the main HPD service may be insufficient. These paths also touch shared receiver resources; please review their SDK-level effects.
- RX EDID application: `0x20021ae0`; RAM writer: `0x20019ef8`; setup routines: `0x2001a008` and `0x2001a596`. The writer uses selector `267a` and RAM window `1000..10ff`. The setup touches `2677`, `267d`, and `2674`. We have not validated a complete fixed-EDID programming sequence. In particular, `2677` bit 2 did not retain a written 1 on the spare, so it must not be assumed to be an ordinary persistent enable bit.

Acceptance tests for the fix

1. Connect computers to all four inputs. Each must discover the same configured EDID profile even if it has never been selected for capture. Independently read EDID through every source's DDC path; do not rely only on cached Windows monitor identification.
2. Repeatedly switch A/B/C/D through every supported control path. All computers must retain their monitor continuously, with byte-identical EDID and no HPD-low pulse caused by selection. Verify HPD electrically as well as logging OS display state.
3. Confirm that the selected computer's live video is actually captured, and that keyboard/mouse routing and the UI agree with that selection. Test with two or more simultaneously active sources; our successful direct-selector trials used empty D/C and therefore do not prove this part.
4. Test extended operation and source boot/wake/connection while that source remains unselected. After a KVM reboot, the saved fixed-EDID mode must initialize correctly on all inputs.

No EDID bytes or firmware were changed in the successful retention tests. Those tests used the unit's existing AOC EDID, not a newly programmed 1080p60 profile. Windows sampling was approximately 500 ms, so it does not exclude shorter electrical pulses. Please treat the findings as a demonstrated control path and a precise basis for a supported firmware fix, rather than a complete verified workaround for all four inputs.

Please confirm whether you can implement this persistent EDID/HPD mode and provide a test firmware build. If a suitable GSV2705 mode already exists, please provide its supported initialization and switching sequence. I can provide the guarded test scripts, register traces, and Windows display logs to your engineering team.

Thank you,
Comet X user
