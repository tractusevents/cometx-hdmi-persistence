# Bring your own firmware artifacts

Place locally obtained files here, or point `COMETX_INPUTS` to a directory
containing them:

| Filename | Purpose |
|---|---|
| `boot.img` | Supplied U-Boot FIT / kernel image |
| `running.dtb` | Running device-tree dump |
| `kallsyms.txt` | Symbol list matching the kernel |
| `gsv2705v1.1.bin` | GSV2705 MCU image |
| `gsv1127x_upgrade` | Vendor ELF utility for offline analysis |

Known hashes are in [expected-sha256.json](expected-sha256.json). No input
binaries are included. Keep these files private unless their redistribution
terms permit publication. This folder ignores everything except this README
and the hash manifest.
