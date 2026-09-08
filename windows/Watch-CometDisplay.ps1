#Requires -Version 5.1
<#
Read-only display-state logger. Run in TR2's interactive Windows desktop session.
It keeps writing locally if the Parsec connection drops. It does not set display
modes, install drivers, alter EDID, contact the KVM, or change system settings.
GDI/WMI report Windows state, not a measurement of HPD voltage or a fresh DDC read.
#>
[CmdletBinding()]
param(
    [ValidateRange(1,3600)][int]$DurationSeconds = 300,
    [ValidateRange(100,5000)][int]$IntervalMilliseconds = 500,
    [string]$OutputPath
)
$ErrorActionPreference = 'Stop'
if (-not $OutputPath) {
    $OutputPath = Join-Path $PSScriptRoot ("monitor-state-{0}-{1}.jsonl" -f $env:COMPUTERNAME, (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (Test-Path -LiteralPath $OutputPath) { throw "Refusing to overwrite existing log: $OutputPath" }

if (-not ('CometDisplayProbe.Native' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
namespace CometDisplayProbe {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public struct DisplayDevice {
        public uint cb;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string DeviceName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceString;
        public uint StateFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceID;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string DeviceKey;
    }
    public sealed class DisplayRow {
        public string Kind;
        public string Adapter;
        public string Name;
        public string Description;
        public string InterfaceId;
        public uint StateFlags;
        public bool Active;
    }
    public static class Native {
        [DllImport("user32.dll", CharSet=CharSet.Unicode, ExactSpelling=true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool EnumDisplayDevicesW(string device, uint index, ref DisplayDevice result, uint flags);
        private static DisplayDevice Empty() {
            DisplayDevice result = new DisplayDevice();
            result.cb = (uint)Marshal.SizeOf(typeof(DisplayDevice));
            return result;
        }
        public static DisplayRow[] Snapshot() {
            List<DisplayRow> rows = new List<DisplayRow>();
            for (uint i=0; ; i++) {
                DisplayDevice adapter = Empty();
                if (!EnumDisplayDevicesW(null, i, ref adapter, 0)) break;
                bool attached = (adapter.StateFlags & 1) != 0;
                rows.Add(new DisplayRow { Kind="adapter", Adapter=adapter.DeviceName,
                    Name=adapter.DeviceName, Description=adapter.DeviceString,
                    InterfaceId=null, StateFlags=adapter.StateFlags, Active=attached });
                for (uint j=0; ; j++) {
                    DisplayDevice monitor = Empty();
                    if (!EnumDisplayDevicesW(adapter.DeviceName, j, ref monitor, 1)) break;
                    rows.Add(new DisplayRow { Kind="monitor", Adapter=adapter.DeviceName,
                        Name=monitor.DeviceName, Description=monitor.DeviceString,
                        InterfaceId=monitor.DeviceID, StateFlags=monitor.StateFlags,
                        Active=attached && ((monitor.StateFlags & 1) != 0) });
                }
            }
            return rows.ToArray();
        }
    }
}
'@
}

function Convert-MonitorText($Values) {
    return -join @($Values | Where-Object { $_ -ne 0 } | ForEach-Object { [char]$_ })
}
function Write-Record($Record) {
    $writer.WriteLine(($Record | ConvertTo-Json -Depth 8 -Compress))
    $writer.Flush()
}
function Write-MonitorIdentity {
    $began = [DateTime]::UtcNow.ToString('o')
    try {
        $monitors = @(Get-CimInstance -Namespace root\wmi -ClassName WmiMonitorID -OperationTimeoutSec 2 | ForEach-Object {
            [ordered]@{
                instance = $_.InstanceName
                active = [bool]$_.Active
                manufacturer = Convert-MonitorText $_.ManufacturerName
                product = Convert-MonitorText $_.ProductCodeID
                name = Convert-MonitorText $_.UserFriendlyName
            }
        })
        Write-Record ([ordered]@{type='wmi_identity'; started_utc=$began; utc=[DateTime]::UtcNow.ToString('o'); monitors=$monitors; error=$null})
    } catch {
        Write-Record ([ordered]@{type='wmi_identity'; started_utc=$began; utc=[DateTime]::UtcNow.ToString('o'); monitors=@(); error=$_.Exception.Message})
    }
}

$stream = [IO.File]::Open($OutputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
$timer = [Diagnostics.Stopwatch]::StartNew()
$samples = 0
$previous = $null
try {
    Write-Record ([ordered]@{type='start'; utc=[DateTime]::UtcNow.ToString('o'); computer=$env:COMPUTERNAME; session_id=(Get-Process -Id $PID).SessionId; duration_seconds=$DurationSeconds; interval_ms=$IntervalMilliseconds; purpose='Windows GDI state and WMI identity; no fresh DDC or electrical measurement'})
    Write-Host "READY: Recording display state locally for $DurationSeconds seconds."
    Write-Host "Log: $OutputPath"
    Write-Host 'Keep this PowerShell process open. Parsec may disconnect; this log stays on the PC.'
    while ($timer.Elapsed.TotalSeconds -lt $DurationSeconds) {
        $rows = @([CometDisplayProbe.Native]::Snapshot())
        $signature = ConvertTo-Json -InputObject $rows -Depth 4 -Compress
        $changed = $signature -cne $previous
        $active = @($rows | Where-Object { $_.Kind -eq 'monitor' -and $_.Active }).Count
        Write-Record ([ordered]@{type='sample'; utc=[DateTime]::UtcNow.ToString('o'); elapsed_ms=$timer.ElapsedMilliseconds; changed=$changed; active_gdi_monitors=$active; displays=$rows})
        $samples++
        if ($changed) {
            Write-Host ("{0}  Active GDI monitors: {1}" -f [DateTime]::UtcNow.ToString('HH:mm:ss.fff'), $active)
            Write-MonitorIdentity
        }
        $previous = $signature
        Start-Sleep -Milliseconds $IntervalMilliseconds
    }
    Write-Record ([ordered]@{type='complete'; utc=[DateTime]::UtcNow.ToString('o'); samples=$samples; elapsed_ms=$timer.ElapsedMilliseconds})
} finally {
    $writer.Dispose()
    $timer.Stop()
}
Write-Host "Finished. Log saved to: $OutputPath"
