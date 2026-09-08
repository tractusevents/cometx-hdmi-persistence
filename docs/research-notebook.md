> Anonymized historical notebook. Some earlier sections are superseded by the later live results. Tool/output paths in code spans describe the private research layout; see [reproduction](reproduce.md) for the public layout.

# Comet X RM4PE persistent HDMI investigation

Date: 2026-09-08. Initial phase: local static analysis, followed by authorized read-only KVM02 collection (`LIVE-2026-09-08.md`). The user subsequently authorized laboratory testing on KVM03 and recoverable KVM02 experiments. **Latest findings are in `LAB-2026-09-08.md`: the ff04 pause enables internal-register access; five HPA registers were changed and restored on KVM03; and the earlier pad-control interpretation is corrected below.** No firmware flash or boot modification has been performed.

## Evidence and confidence conventions

**Confirmed-static** means directly established by instruction bytes, constants, or structure layout, not verified electrically. **Inferred** means code supports the interpretation but a register specification or controlled observation is still needed. **Unknown** is deliberately unresolved. Function names for the MCU and stripped utility are analyst labels, except kernel names supplied by kallsyms.

Primary inputs:

| File | Bytes | SHA-256 |
|---|---:|---|
| `userdata/re/boot.img` | 33554432 | `8648d2e967301b979471b8d7e49ceac47c1774c5d1564b816a419ba0744a34af` |
| `userdata/re/running.dtb` | 69632 | `751eebe8733707f68ef8f0a6cce2957239c00a1b999181da7e299f3d9d0cfa41` |
| `gsv1127x_upgrade` | 18288 | `b283c95a8a0bcde8d7ed47d8e89cc6c061433c5f9fd915904c3d01c29eea2e69` |
| `gsv2705v1.1.bin` | 524288 | `8899203220fe5b5c8b41464e48ad662834d4ea8ed4ba1b8e2e1e77e0e0995ffc` |

## Kernel extraction

The boot partition is a **U-Boot FIT**, not an Android boot image. FDT magic is at offset 0, FIT tree length 0x600. External payload offsets are absolute `data-position` values:

| Payload | boot.img offset | Length | Compression |
|---|---:|---:|---|
| FDT | 0x800 | 0x10676 | none |
| ARM64 Image | 0x11000 | 0xfdc008 | none |
| Rockchip resource | 0xfed200 | 0x898600 | none |

Extracted kernel SHA-256 `4196c6137967eefe1389b53d1a13976713b20d0fcceb5618e25ba86cc29598f1` matches the FIT hash. `ARMd` Image magic appears at Image offset 0x38. Linux banner reports 6.1.141.

Address mapping: `Image_offset = kernel_VA - 0xffffffc008000000`; `boot_offset = Image_offset + 0x11000`. Instruction boundaries, kallsyms call targets, and literal strings agree with this mapping.

## GSV2705 kernel driver

All addresses below use VA prefix `ffffffc008`; offsets are relative to extracted Image. Full instruction evidence: `output/kernel-driver.asm`.

| Function | Image offset | Size |
|---|---:|---:|
| `hdmi_enable_show` | 0x5536a4 | 0x78 |
| `gsv2705_reset` | 0x55371c | 0x44 |
| `i2c_wr.constprop.0` | 0x553834 | 0xcc |
| `gsv2705_i2c_switch_channel` | 0x553900 | **0x70** |
| `channel_store` | 0x553970 | 0xac |
| `i2c_rd.constprop.0` | 0x553a1c | 0x94 |
| `gsv2705_read_firmware_version` | 0x553ab0 | 0x98 |
| `hdmi_enable_store` | 0x553b48 | 0xa8 |
| `hdmi_status_show` | 0x553bf0 | 0xe8 |
| `gsv2705_check_chip_id` | 0x553cd8 | 0x94 |
| `gsv2705_probe` | 0x554070 | 0x5d0 |

The earlier 0x1b0 switch-function estimate included `channel_store` and the read helper. The complete symbol map exposes both.

### Wire transactions — confirmed-static

7-bit I2C address comes from the client (0x58 in the supplied device tree). The write helper always sends one message `[ff, low8(register), data_byte]`. The read helper sends a combined two-message transfer: write `[ff, low8(register)]`, repeated START, read one byte. No SMBus framing.

The channel table at Image offset **0xa276a0**, VA `ffffffc008a276a0`, consists of four 12-byte entries:

| channel/UI/physical | I2C write bytes | SEL0 | SEL1 |
|---|---|---:|---:|
| 0 / 1 / A | `ff 05 01` | 0 | 0 |
| 1 / 2 / B | `ff 05 02` | 1 | 0 |
| 2 / 3 / C | `ff 05 03` | 0 | 1 |
| 3 / 4 / D | `ff 05 04` | 1 | 1 |

```c
// Equivalent behavior; not a proposed patch.
channel_store(text) {
    n = kstrtoint(text, base=0);
    if (n < 0 || n > 3) return -EINVAL;
    gpiod_set_value(sel[0], table[n].sel0);
    gpiod_set_value(sel[1], table[n].sel1);
    switch_channel(n);
    log("Switch to channel %d", n);
    return count;
}
switch_channel(n) {
    mutex_lock(&lock);
    write_byte(0xff05, n + 1);
    cached_channel = n; // updated even if I2C transfer fails
    mutex_unlock(&lock);
}
```

`channel_show` returns this cached value, without reading the MCU. GPIO SEL changes occur before the switch helper's mutex. Read/write helpers log transfer failures but do not provide a reliable error path to the sysfs callers; several read destinations are not initialized. Treat sysfs results after an I2C error as unreliable.

### Status and enable

`hdmi_status_show` reads **ff07** once. For index i=0..3 it prints Connected iff `status & (1<<i)`; it adds `[SELECTED]` iff `status & (0x10<<i)`. These are independent tests. No cached-channel comparison is involved. The MCU derivation of the upper bits is examined below; the driver's text is not itself proof of their electrical meaning.

`hdmi_enable_show/store` calls `gpiod_get_value`/`gpiod_set_value` on the descriptor at private-structure offset 0x28. Store accepts only 0/1. Probe acquires it as `hdmi_en`, and its error text calls it **hdmi_5v_enable**. No I2C access or per-RX loop occurs. The live DT property is `<phandle 0x97, pin 8, flags 0>` (active high). Exact board wiring still requires a schematic.

Chip ID: read ff3d (low byte), then ff3c (high byte); require `0x2705`. Version: ff3e major, ff3f minor, cached at offsets 0xd0/0xd1. Reject combined version 0000 or ffff.

Probe allocates 0xd8 bytes, initializes a mutex, acquires power/reset/HDMI-enable/USB GPIOs, checks chip ID and version, and can reset and retry after failures (2-second waits). It creates 13 sysfs files, initializes channel/SEL=0, enables host power for port 0, writes ff05=01, waits 2 seconds, and enables the HDMI GPIO. No EDID or per-port HPD configuration appears in this driver's reachable operations.

Neighboring helpers include USB host power/channel, local-host selection, OTG status, and hub resets. They are not four HDMI HPD controls.

## Vendor utility

ARM64 little-endian stripped PIE, entry 0xd40, code/rodata VAs equal file offsets. `.eh_frame` still provides exact function boundaries (`output/upgrade-elf.txt` and `output/upgrade.asm`).

| Analyst label | VA/file offset | Role |
|---|---:|---|
| `transfer` | 0xe54 | `ioctl(fd, 0x707 /*I2C_RDWR*/, msgs)` |
| `write_regs` | 0xfec | 1/2-byte address prefix then data; one message |
| `read_regs` | 0x117c | 1/2-byte address prefix then repeated-start read |
| `open_bus` | 0x12b4 | opens supplied device O_RDWR |
| `packed_read` | 0x13f0 | unpack descriptor, call read_regs |
| `packed_write` | 0x1494 | unpack descriptor, call write_regs |
| `write_edid_256` | 0x1538 | mailbox ff19 plus ff40 staging |
| `check_chip_id` | 0x17ec | accept 6127 or 2705 |
| `read_version` | 0x18fc | ff3e, length 2 |
| `crc8` | 0x19f4 | 256-byte lookup table at 0x29c8 |
| `upgrade_handshake` | 0x1aa0 | ff22 magic; ff27 response |
| `write_upgrade_descriptor` | 0x1be4 | ff30 descriptor and ff2f CRC |
| `stage_flash_chunk` | 0x1cf8 | ff40, 64 bytes; ff80 CRC |
| `read_flash_ack` | 0x1da8 | ff2b |
| `send_flash_command` | 0x1ddc | ff2c |
| `wait_flash_ack` | 0x1e10 | up to 5000 iterations, 1 ms sleep |
| `flash_command_advance` | 0x1ef0 | send/wait/increment sequence by 0x10 |
| `identify_active_slot` | 0x1f40 | ff2d=0, then handshake |
| `flash_partition` | 0x1f9c | metadata, start, 64-byte chunks, finish |
| `main` | 0x21dc | option dispatch and A/B slot selection |

Packed descriptor: byte 0 is address high byte/page, byte 1 is I2C address, byte 2 is boolean use-16-bit-address, byte 3 is logical bus index. Default descriptor 0x000158ff means bus index 0, chip 0x58, 16-bit ffXX addresses. The utility's printed 'bus 1' is hardcoded text, not the passed Linux bus number. Some wrapper functions discard the actual I/O return status.

### EDID upload — decoded, not recommended for live use

Main reads at most 256 bytes into a zeroed buffer and calls the same EDID routine for either accepted chip ID. This is not a per-input API.

```text
write ff19 = 90
for chunk j=0..3:
    write ff40..ff7f = EDID[64*j : 64*(j+1)]
    write ff19 = 90+j
    poll ff19 until 02 (shared counter, >10000 polls abort)
write ff19 = 98
sleep 10ms
write ff19 = 01
sleep 10ms
write ff19 = 00
```

The transport is confirmed. No ff19 consumer was found in the inspected GSV2705 application mailbox service (0x2000abb4..0x2000b986). This is a bounded negative finding, not a proof that no indirect handler exists anywhere. The utility accepting a chip ID is insufficient evidence that its EDID command works on that chip. Do not redirect the downstream EDID upload to bus 3 on that basis.

### Flash protocol — static documentation only

Write ff22..ff25 = `29 81 56 41`. Poll ff27..ff2a after 20 ms sleeps (up to 100 times), expecting `97 86 69 51` (slot indication 0) or `97 86 69 52` (1). Main explicitly labels case 0 as write Partition B, case 1 as write Partition A.

Descriptor at ff30, 12 bytes: LE32 padded length, LE32 destination offset, bytes `01 00`, LE16 chip ID (2705 or 6127); write its CRC8 to ff2f. Data chunks are 64 bytes at ff40, CRC8 at ff80. Command byte ff2c combines a rolling high-nibble sequence and low-nibble operation: initial 9, chunks 6. Acknowledgment ff2b must be nonzero and have matching high nibble; the low nibble is not checked by this utility. Finish writes aa to ff22 and ff2d. Retry paths can restart the transfer.

CRC8 uses non-reflected polynomial 0x07, initial value zero, no final XOR. All 256 table entries at utility offset 0x29c8 match the generated polynomial table; the loop updates `crc = table[crc ^ byte]`.

Case 0 uses file[0x40000:] -> flash 0x40000, length 0x3f000. Case 1 uses file[0x1000:] -> flash 0x1000, length 0x3f000. No flashing script is supplied.

## MCU image and address model

Raw executable flash image, RV32 with compressed instructions, memory mapped at **0x20000000 + file offset**. The code contains AUIPC-relative references into this region and RAM around 0x80000000. Not an encrypted/compressed container.

| Region | Offset | Evidence |
|---|---:|---|
| Bootloader | 0..0xfff | reset JAL at 0, vector pointers, startup at 0x8c |
| Application A slot | 0x1000..0x3ffff | JAL at 0x1000 to 0x1092, vectors point into 0x2002xxxx |
| Application B slot | 0x40000..0x7efff | JAL at 0x40000, relocated vectors; corresponding strings +0x3f000 |
| Final sector | 0x7f000..0x7ffff | ff fill in supplied blob |

A startup establishes gp=0x80008860, sp=0x8000b000; copies flash[0x259cc:0x25da0] to RAM[0:0x3d4], and initialized data at 0x29878 to RAM 0x80008000..0x80008090. Subsequent BSS ends at 0x80009180. Raw disassembly includes data; only traced executable ranges are semantic evidence.

MCU wrappers 0x200011f6 (read) and 0x20001294 (write) resemble the utility's packed-address API. Actual implementations 0x20001526 / 0x20001498 access **0x30020000 | register_address** as memory-mapped bytes. Thus ff05 is internally 0x3002ff05. The MCU's packed slave byte b0 differs from Linux's 7-bit 58, but these local implementations ignore that slave byte.

Mailbox service starts **0x2000abb4**; callback wrapper 0x2000b988. ff05 read at callsite **0x2000ad34**. If nonzero, different from cached RAM[0x8000809c], and a Tx port was found, it indexes the port array in 0x64-byte strides and calls routing function **0x2001d0c8** (normal RX: third argument 2). The 'Routing Change Port%d=>TxA' string is referenced at 0x2000ae68. Cache updated at 0x2000aebc. This confirms ff05 as a high-level MCU routing request, not a direct HPD register.

Status publishing: lower ff07 bits are assembled from per-RX context byte at `*(port+0x1c)+0x0c`. Function 0x20016456 reads bit 1 of 0310/0314/0318/031c into this byte, and logs `Rx5V Loss` on a falling transition (string reference 0x20016514). Thus **Connected is the MCU's RX 5V detection**, not evidence of a host-visible monitor. Upper bits copy bit 5 of the same four registers, gated by each corresponding connection bit; ff07 write callsite 0x2000b1ca. Their interpretation as HPD-related pad feedback is **inferred**; their exact electrical meaning is unknown. They are not generated by comparing the selected-channel cache.

The application initializes physical RX port IDs 0,1,2,3 with SDK type 0 at callsites 0x2000ba7c, 0x2000ba94, 0x2000baac, 0x2000bac4; TxA has ID 4/type 6. Initialization initially connects RXA to TxA at 0x2000bb48. Port structures have stride **0x64 = 100 bytes**, not 64 decimal.

### Mailbox map

All addresses are 16-bit chip registers. Entries describe code, **not proposed writes**. Apart from the documented ID/version/status values, current hardware values have not been read during this investigation.

| Register | Decoded behavior | Confidence |
|---|---|---|
| ff04 | Heartbeat; value 5a enters polling loop writing ffff=0, then ffff=1 on exit; ordinary counter avoids 5a | Confirmed-static; do not pause production MCU |
| ff05 | 1..4 request RXA..RXD to TxA; cached comparison and SDK routing call | Confirmed-static |
| ff06 | Changes Tx FRL-mode field | Confirmed-static field update; not an HPD hold mode |
| ff07 | Low nibble RX5V; high nibble per-pad bit 5 gated by RX5V | Confirmed-static derivation; high-bit electrical label inferred |
| ff08 | aa sets current receiver's HPD-state field to 2 and clears command byte | Confirmed-static; disruptive |
| ff09 | a1 low power; a2 reset; a3 QSPI tri-state; a5/a6 flash protection; a7 flash-status query | Code/log correlation; unrelated to desired behavior |
| ff0c | Periodically published Tx status | Confirmed-static publication |
| ff10..18 | Selected RX timing/status bytes | Confirmed-static publication |
| ff19 | Utility uses it for EDID, but no handler found in this application mailbox service | Unresolved compatibility |
| ff1d | High nibble selects affected RXs; low nibble changes receiver state/policy fields | Confirmed-static; detailed below |
| ff1e..1f | Four per-RX nibbles change a context field and request an HPD toggle | Confirmed-static; likely HDCP policy, exact enum unresolved |
| ff22..3b, ff40..80 | Firmware-upgrade protocol described above; overlaps utility EDID staging | Confirmed utility transactions; not an EDID-safe scratch area |
| ff3c..3d | Chip ID, high then low byte | Confirmed-static Linux and utility |
| ff3e..3f | Version major/minor | Confirmed-static Linux and utility |

`ff1d` is read at **0x2000b5e6**; handler instructions are 0x2000b5f0..0x2000b738. Field names below are descriptive analyst labels; offsets and stores are the evidence:

```c
uint8_t v = read8(0xff1d);
for (unsigned i = 0; i < 4; ++i) {
    Port *p = ports + i; // 0x64-byte structures
    if (p->type != 0 && p->type != 1) continue;
    if (!(v & (0x10 << i))) continue;
    Rx *r = *(p + 0x1c);
    if (v & (1 << i)) {
        r->byte_at_00 = 0;
        if (r->u32_at_08 == 0) r->u32_at_08 = 4;
    } else {
        r->byte_at_00 = 1;
        if (r->u32_at_10 == 1) r->u32_at_08 = 0;
        else r->u32_at_14 = 0;
    }
}
```

For RXB, high-nibble bit 0x20 selects the receiver and low bit 0x02 selects the first branch. This is **not a verified force-HPD-high command**. It writes persistent RAM fields and is serviced repeatedly. Restoring an old ff1d value of zero merely stops applying the command; it does not undo RAM transitions. Therefore a save-byte/write/restore-byte sequence is not a dependable rollback.

Further static correlation: RX plug service `0x2001dfbe` reads this context byte at `0x2001e04c`; if nonzero, it resets RX processing and calls `hpd_down` at `0x2001e072`. This supports a receiver-disable policy interpretation for nonzero context byte 0. Clearing the byte permits ordinary state-machine operation, including the downstream-ready requirement; it is not evidence of persistent HPD. Separate direct HPA-disable calls exist at `0x2000d79c` and `0x2000e08c`, outside `rx_hpd_service`.

`ff1e/ff1f` are read together at 0x2000b74c. Nibble order is A=ff1e[3:0], B=ff1e[7:4], C=ff1f[3:0], D=ff1f[7:4]. Zero means no update. Values 1,2,3,4 map to context `*(port+0x24)` word 0 values 0,1,3,4. On a change, `*(port+0x1c)` word 0x10 becomes 5, which the HPD state machine interprets as a toggle request. The context is used by HDCP code; calling these nibbles an HPD retention mode would overstate the evidence.

### HPD state machine and HPA hardware operations

| Analyst label | MCU VA | File offset | Evidence |
|---|---:|---:|---|
| `rx_hpd_service` | 0x2001fc94 | 0x1fc94 | HPD toggle/forced-low strings and state dispatch |
| `rx_hpd_down` | 0x2001fc14 | 0x1fc14 | Calls power-down path, clears HPD-state word |
| `rx_hpd_up` | 0x2001fc64 | 0x1fc64 | Calls power-up path, sets HPD-state word 1 |
| `port_power_down` | 0x2000fe22 | 0x0fe22 | Calls disable HPA and additional RX configuration |
| `port_power_up` | 0x2000fde6 | 0x0fde6 | Calls enable HPA |
| `disable_rx_hpa` | 0x20015f3e | 0x15f3e | Log text; register writes; synthetic execution |
| `enable_rx_hpa` | 0x20016236 | 0x16236 | Log text; register writes; synthetic execution |
| `read_rx_5v` | 0x20016456 | 0x16456 | Pad bit 1 and RX5V loss log |
| `walk_downstream` | 0x20020902 | 0x20902 | Enumerates connections for HPD readiness check |

Condensed control flow of 0x2001fc94 (all offsets relative to RX context at `*(port+0x1c)`):

```c
if (r->u32_at_10 == 5) {
    log("RxHPD Toggled");
    rx_hpd_down(p); // resets +0x10 to zero
}
if (r->u32_at_08 == 4 || r->u32_at_08 == 5) {
    if (r->u32_at_10 == 0 && r->u32_at_14 > 29) {
        bool ready = false;
        for (Port *tx : downstream_connections(p)) {
            if ((tx->type == 6 || tx->type == 7) &&
                (*(tx+0x20))->u32_at_10 == 5) ready = true;
        }
        if (ready) { rx_hpd_up(p); r->u32_at_08 = 5; }
    }
} else if (r->u32_at_10 == 1 || r->u32_at_10 == 2) {
    log("RxHPD Forced LOW");
    rx_hpd_down(p);
} else if (r->u32_at_10 == 3) {
    rx_hpd_up(p);
}
```

The ordinary assertion path requires a ready downstream connection. **Inference:** this supports the observed loss of a monitor on an unselected RX. It does not by itself prove the entire disconnect sequence or exclude another independent mode elsewhere. The field value 3 provides a separate upward path in this function, but no exposed mailbox control that safely maintains it has been established.

Enable/disable HPA selects a bit `1 << physical_input` for IDs 0..3 (also SDK IDs 40..43). It sets/clears the corresponding bit of **2674**, reads **00bb[3:0]**, and computes a new low-nibble mask by setting/clearing that same port bit. If the mask changed, it copies the new low nibble to **00bb, 00b2, 00b5, 00b6**, preserving each upper nibble. These are confirmed register effects; individual register names such as DDC-enable remain **unknown** without a register map.

The routines also manipulate shared receiver-core registers when `port.byte_at_5c == 0`: enable touches 20d7 and conditionally 00be; disable touches 20d9, 2b1c, 20f7/20f9, 20d7/20de, and 00be. The condition's interpretation as shared-core assignment is inferred. Power-down additionally calls 0x2001a9a8 with argument zero. Thus these functions do more than change one HPD pin, and a Linux raw write would bypass their software bookkeeping.

Offline Unicorn execution of both HPA routines for IDs 0..3 confirms the mask transformations and preservation of upper nibbles: **8 synthetic cases passed**. Example: initial 00bb=a1, 00b2=b1, 00b5=c1, 00b6=d1; enabling RXB changes them to a3,b3,c3,d3 and sets 2674 bit 1. These are synthetic inputs, not production readings. Complete ordered accesses: `output/offline-hpa-emulation.json`.

### Selected-input event/status maintenance (corrected after lab testing)

Application initialization at 0x2000bb50 writes `[0c,0c]` to 0310/11, 0314/15, 0318/19, 031c/1d; it also writes 0338=0c, 035b=0c, 0301=80. The application loop at 0x2000bbfa calls SDK processing and the update service, then performs:

```c
unsigned mux = (read8(0x0001) >> 4) & 7;
if (mux < 4) {
    unsigned reg = 0x0310 + 4*mux;
    if ((read8(reg) & 0x99) != 0x88) write8(reg, 0xcc);
}
```

RXB read/write callsites are 0x2000bc86 / 0x2000bcb2. This is a selected-input-specific register operation, but **lab testing corrects the earlier pad-drive interpretation**: writing 0314=0c changes 09 to 08, acknowledging bit 0 through bit 2. SDK code similarly reads event bits 0/4 and acknowledges through bits 2/6. Bits 1/5 are current status and bits 3/7 appear to be control/enables. The main loop is consistent with event acknowledgment/enable maintenance, not a proven HPD drive override. Do not treat 0314=cc as a force-HPD command.

### EDID RAM and DDC limits

`write_rx_edid_ram` at **0x20019ef8**, file offset **0x19ef8**, length 0x110, selects RAM by **SDK port type**, not physical input ID:

```c
if (p->type != 0 && p->type != 1) return -3;
masked_write(0x267a, mask=0x03, shift=0, value=p->type);
masked_write(0x267a, mask=0x70, shift=4, value=0);
write_bytes(0x1000, edid, 256);
if (length > 256) {
    masked_write(0x267a, mask=0x70, shift=4, value=1);
    write_bytes(0x1000, edid+256, 256);
}
```

The function's own log calls these EDID RAM1/RAM2. Both writes use address window **1000..10ff**; register 267a supplies the bank. **Four synthetic cases passed**, covering 256/512-byte writes, different physical IDs, and SDK types 0/1; the complete selector and data-write order is in `output/offline-edid-emulation.json`. The real RAM bank hardware is not emulated; synthetic MMIO only records CPU accesses.

The four actual input objects are initialized with type 0, so this function alone does **not** supply four independently indexed EDID memories. A shared fixed EDID could still meet the objective if all four DDC interfaces could serve it concurrently. Neither that DDC routing mode nor a host-side configure command is yet established.

Further trace: RX EDID application at `0x20021ae0` calls `0x20019ef8`, `0x2001a008`, and `0x2001a596` in sequence. The last routine sets 2677 bit 2, writes the physical-input bit of 267d to the SDK type (0/1), then sets the input's 2674 bit. This is strong code evidence for per-input RAM-bank assignment via 267d, separate from capture routing. Eight synthetic paths validate the write sequence. **Live caveat:** on KVM03, 2677 reads 00 immediately after writing 04 while the MCU is paused; it is not demonstrated to be a persistent enable. KVM02 also reads 2677=00 and 267d=00 with B selected normally. The sampled EDID setup registers and RAM contents are identical when B is unselected; further register changes are not yet justified. Exact details and raw reports are in `LAB-2026-09-08.md`.

There are downstream EDID processing and copy paths. The console branch at 0x2000c734 references `Copy Downstream EDID!`, changes the copy/filter state, and schedules receiver EDID processing. This is not a discovered Linux mailbox API. The `readRXDDCUpdInfo` / `readRXDDCUpdData` strings near 0x20022950..0x20022a56 belong to the firmware-update transport and should not be assumed to mean host monitor EDID service.

The apparent EDID header at file **0x298e0**, repeated at **0x688e0**, is only the standard eight-byte magic in initialized data. Following bytes are other small constants and upgrade/chip/version data, not an established complete EDID. No usable fixed EDID should be extracted from that position.

A vendor-authored [GSV2705 product brief mirrored by Onway](https://www.onwaytech.com/static/upload/file/20230506/1683336562635202.pdf) describes embedded RISC-V control, mailbox operation, and 512-byte EDID storage. That supports the architecture, but supplies no register definitions or guarantee of simultaneous EDID service on all four inputs.

## Live experiments and decision

**Running-MCU follow-up:** after source-free KVM03 validation and the user's logger READY confirmation, KVM02 completed direct D/C/B selection with six seconds of MCU service on each input at 16:27:39..16:28:08 UTC. Each paused recheck retained selector be/ae/9e, mode 40, five B masks 02, and 0314=aa. During running holds ffff=01, heartbeat advanced, and ff07=22. Exact original B values were restored and normal operation verified. Windows now confirms no sampled display loss: all 98 complete samples have the same active AOC monitor and identical GDI display state; no changes occur after logger initialization, including the 58 trial samples. The truncated paste still covers restoration and several subsequent seconds. Full normal mailbox switching, other-source capture, and long-term retention remain unvalidated. See [reports/direct-resumed.md](reports/direct-resumed.md).

**Direct selector trial:** the type-0 RX path at 0x20012738..0x20012750 selects physical input through 0001[6:4]; following writes put 0000[7:6] in mode 01. With live 0000=40 already established, source-free KVM03 and then KVM02 accepted 0001 values be (D), ae (C), and 9e (B) while the MCU remained paused. On KVM02 all five B masks stayed 02 and 0314 stayed aa at every sample; exact restoration and normal MCU resume succeeded. Linux/MCU logical channel and USB remained B. The compact Windows log now confirms no sampled display loss: all 240 records from 16:11:00.066..16:12:59.782 report one active monitor and changed=false, with maximum spacing 0.503 seconds. This includes D/C selection and MCU resume after return to B. It does not validate the full normal routing path, normal MCU service while D/C remain selected, or electrical HPD continuity. See [reports/direct-paused.md](reports/direct-paused.md).

**Later laboratory update:** internal access through ff04=5a/ffff=00 is now demonstrated on both devices, with successful resume. The specifically approved KVM02 five-mask trial changed unselected B's 0314 from 9a to ba and ff07 from 02 to 22 while channel C remained selected. The masks persisted across MCU resume, and all saved values were restored exactly. **Local Windows logging confirms temporary inactive-B monitor detection:** the AOC monitor returned at 16:00:23.101 UTC while C remained selected and stayed active through MCU resume and the 12-second normal-service hold. KVM02 returned to B at 16:00:40. See [reports/inactive-b-hpa.md](reports/inactive-b-hpa.md). Earlier NDI/Parsec observations are not confirmed negative results. This is not a persistent fix: KVM03 channel-cycle testing shows normal routing changes clear the masks. Fresh DDC reads and uninterrupted electrical HPD remain unverified. KVM03 also accepts the decoded EDID setup sequence, but 2677 bit 2 does not retain a written 1; its semantics remain unresolved. See `LAB-2026-09-08.md` for hardware evidence. The following paragraphs are historical records of the earlier read-only phase, whose access limitation has now been resolved.

**2026-09-08 live update:** `kvm-connected` was selecting channel 2 / HDMI C, with only B connected, throughout all four SSH sessions. ff05=03, ff07=02, ID=2705, version=1.1; installed firmware/utility hashes match the analyzed copies. All nine attempted non-ff-page reads returned zero, including 0314 despite persistent B source detection. Their external visibility is therefore unvalidated; do not interpret those zeros as physical HPD state or use them as rollback values. No additional non-ff-page probes were made.

The MCU heartbeat ff04 advanced 36->55 over approximately one second, and ffff read 01. The firmware writes ffff=00 while it is held in its ff04=5a loop, and ffff=01 during normal service. **New inference:** this may arbitrate access to internal registers, explaining the zero results. Its actual gate semantics and pause side effects are unknown; no pause/gate write was attempted. The maintained collector now reads only seven ff-page ID/version/channel/status/policy bytes. Full evidence and exact callsites are in `LIVE-2026-09-08.md`.

Exact current commands and interpretation are in **`EXPERIMENTS.md`**. The initial read-only snapshot has been collected, with C left selected. Resolve the external register-access protocol before another HPA/pad snapshot or runtime configuration trial. No new configuration write is recommended for the production unit.

No defensible reversible RXB write is ready yet. In particular, restoring ff1d does not undo state transitions, HPA operations span shared registers, the selected-pad loop can interfere with direct overrides, and simultaneous DDC access remains unresolved. These are findings from the code, not generic precautionary objections.

The next decision depends first on the host-facing access protocol and ffff semantics, then on authoritative RXB pad/mask values and register definitions for 0310..031f, 00b2/00b5/00b6/00bb, 2674 and 267a. A runtime workaround remains possible, but **neither a userspace workaround nor a small kernel patch is proven**. No firmware modification or flashing is proposed.

## Reproducibility and verification

`tools/analyze.py` extracts and disassembles local copies; `tools/rv.py` adds RV32 relative branch targets and local address hints; `tools/emulate_rv.py` runs selected CPU routines with synthetic RAM/MMIO and a stub logger. They contain no hardware access. Dependencies are installed under `tools/python_libs` and listed in `tools/requirements.txt`.

Kernel/utility comments are conservative straight-line address hints. RISC-V comments use limited constant propagation, not complete control-flow analysis; AUIPC intermediate values may coincidentally point into unrelated strings. Treat only final resolved references, instruction bytes, and manually traced control flow as evidence. Linear firmware output includes data and RAM-code storage and is not a list of executable functions.

Validation includes original/duplicate SHA-256 comparisons, FIT payload hash matching, ARM64 Image magic and symbol alignment, utility FDE boundaries, and 12 bounded synthetic executions of HPA/EDID routines. The original collection script passed `bash -n` and successfully ran on the KVM; its results exposed the non-mailbox visibility limitation. The revised collector removes those reads. Results are recorded in `output/verification.txt` and the live reports. None of these checks substitutes for electrical HPD or host DDC/EDID validation. Matching the installed firmware file does not prove that every byte of the active MCU flash slot matches it.
