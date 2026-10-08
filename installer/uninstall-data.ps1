param([ValidateSet('CurrentUser','AllUsers')][string]$Scope = 'CurrentUser')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-StatTrackerDataTargets([string]$LocalRoot, [string]$RoamingRoot) {
    # These names come from storage.py and the shipped executable's VERSIONINFO.
    foreach ($pair in @(@($LocalRoot, 'Stat Tracker'), @($LocalRoot, 'Your Company\Stat Tracker'), @($RoamingRoot, 'Your Company\Stat Tracker'))) {
        $base = [IO.Path]::GetFullPath($pair[0]).TrimEnd('\')
        $target = [IO.Path]::GetFullPath((Join-Path $base $pair[1]))
        if (-not $target.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid app-data target.' }
        [pscustomobject]@{ Base=$base; Path=$target }
    }
}

function Remove-StatTrackerDataTarget($Target) {
    $base = [IO.Path]::GetFullPath($Target.Base).TrimEnd('\')
    $full = [IO.Path]::GetFullPath($Target.Path).TrimEnd('\')
    $allowed = @((Join-Path $base 'Stat Tracker'), (Join-Path $base 'Your Company\Stat Tracker'))
    if ($full -notin $allowed -or -not $full.StartsWith($base + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing a target outside Stat Tracker data.' }
    if (-not (Test-Path -LiteralPath $full)) { return }
    # Refuse junctions/symlinks anywhere in the path or subtree; never follow them.
    $current = Get-Item -LiteralPath $full -Force
    if (-not $current.PSIsContainer) { throw 'Expected an app-data directory.' }
    while ($null -ne $current) {
        if ($current.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked path retained: $full" }
        $current = $current.Parent
    }
    $pending = New-Object 'System.Collections.Generic.Queue[string]'
    $pending.Enqueue($full)
    while ($pending.Count -gt 0) {
        foreach ($child in Get-ChildItem -LiteralPath $pending.Dequeue() -Force) {
            if ($child.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked app-data content retained: $full" }
            if ($child.PSIsContainer) { $pending.Enqueue($child.FullName) }
        }
    }
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction Stop
}

function Invoke-StatTrackerDataCleanup([string]$Mode) {
    $roots = @()
    if ($Mode -eq 'CurrentUser') {
        $roots += @{Local=[Environment]::GetFolderPath('LocalApplicationData'); Roaming=[Environment]::GetFolderPath('ApplicationData')}
    } else {
        foreach ($profile in Get-ChildItem 'Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList') {
            if ($profile.PSChildName -notmatch '^S-1-(5-21|12-1)-') { continue }
            $homeDir = [Environment]::ExpandEnvironmentVariables((Get-ItemProperty -LiteralPath $profile.PSPath).ProfileImagePath)
            if (-not [IO.Path]::IsPathRooted($homeDir)) { continue }
            $localDir = Join-Path $homeDir 'AppData\Local'
            $roamingDir = Join-Path $homeDir 'AppData\Roaming'
            # Respect redirected folders when this user's registry hive is loaded.
            $shellKey = 'Registry::HKEY_USERS\' + $profile.PSChildName + '\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
            if (Test-Path -LiteralPath $shellKey) {
                $shell = Get-ItemProperty -LiteralPath $shellKey
                foreach ($mapping in @(@('Local AppData','local'), @('AppData','roaming'))) {
                    $property = $shell.PSObject.Properties[$mapping[0]]
                    if ($null -ne $property) {
                        $value = ([string]$property.Value).Replace('%USERPROFILE%', $homeDir)
                        if ($value -notmatch '%' -and [IO.Path]::IsPathRooted($value)) {
                            if ($mapping[1] -eq 'local') { $localDir=$value } else { $roamingDir=$value }
                        }
                    }
                }
            }
            $roots += @{Local=$localDir; Roaming=$roamingDir}
        }
    }
    $failed = @()
    foreach ($root in $roots) {
        foreach ($target in Get-StatTrackerDataTargets $root.Local $root.Roaming) {
            try { Remove-StatTrackerDataTarget $target }
            catch { $failed += $_.Exception.Message }
        }
    }
    if ($failed.Count) { throw ($failed -join [Environment]::NewLine) }
}

# Dot-sourcing exposes the same path/cleanup functions to isolated fixture tests.
if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-StatTrackerDataCleanup $Scope; exit 0 }
    catch { Write-Error $_ -ErrorAction Continue; exit 1 }
}
