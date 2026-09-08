# Log Windows display state locally

Run this read-only logger in the connected Windows computer's interactive
desktop session before an experiment:

```powershell
powershell.exe -NoProfile -File .\Watch-CometDisplay.ps1 -DurationSeconds 900
```

Wait for READY and keep the process open. Its JSONL file is written beside
the script unless `-OutputPath` is supplied. GDI sampling is approximately
500 ms; WMI identity is queried on state changes. Records are flushed so a
Parsec disconnection does not itself stop collection. Signing out or stopping
the process does stop it.

The logger does not change display modes, EDID, registry settings, or KVM
configuration. It records monitor identifiers; keep raw logs private until
anonymized. The published evidence demonstrates both full and compact logs.

For a compact extract, run the following in the log directory and adjust the
UTC minute filter to your trial. This avoids truncation in chat paste fields:

```powershell
$log = Get-ChildItem .\monitor-state-*.jsonl |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
Get-Content -LiteralPath $log.FullName | ForEach-Object {
    $r = $_ | ConvertFrom-Json
    if ($r.type -eq 'sample' -and $r.utc -match '^2026-09-08T16:(27|28):') {
        $r | Select-Object utc,active_gdi_monitors,changed | ConvertTo-Json -Compress
    }
}
```

The first `changed=true` sample is initialization, not proof of a display
transition. Neither GDI nor WMI demonstrates a fresh DDC read; approximately
500 ms samples can miss short transitions. Preserve zeros, errors, gaps, and
the full trial interval when reporting results.

API references: [EnumDisplayDevicesW](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumdisplaydevicesw),
[DISPLAY_DEVICEW](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-display_devicew),
[WmiMonitorID](https://learn.microsoft.com/en-us/windows/win32/wmicoreprov/wmimonitorid).
