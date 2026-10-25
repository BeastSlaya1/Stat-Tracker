. "$PSScriptRoot\..\installer\uninstall-data.ps1"
$fixture = Join-Path $PSScriptRoot '..\build\uninstall-fixture'
$fixture = [IO.Path]::GetFullPath($fixture)
$baseWorkspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\build')).TrimEnd('\')
if (-not $fixture.StartsWith($baseWorkspace + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Fixture outside build directory.' }
New-Item -ItemType Directory -Force -Path $fixture | Out-Null
foreach ($who in @('user-one','user-two')) {
    $local = Join-Path $fixture "$who\AppData\Local"
    $roaming = Join-Path $fixture "$who\AppData\Roaming"
    $targets = @(Get-StatTrackerDataTargets $local $roaming)
    if ($targets.Count -ne 3) { throw 'Expected only the three app data locations.' }
    foreach ($target in $targets) {
        New-Item -ItemType Directory -Force -Path (Join-Path $target.Path 'nested') | Out-Null
        Set-Content -LiteralPath (Join-Path $target.Path 'nested\saved-game.json') -Value '{}'
    }
    $other = Join-Path $local 'Other App'
    New-Item -ItemType Directory -Force -Path $other | Out-Null
    Set-Content -LiteralPath (Join-Path $other 'keep.txt') -Value 'Keep'
    foreach ($target in $targets) { Remove-StatTrackerDataTarget $target }
    foreach ($target in $targets) { if (Test-Path -LiteralPath $target.Path) { throw 'App data not removed.' } }
    if (-not (Test-Path -LiteralPath (Join-Path $other 'keep.txt'))) { throw 'Unrelated data changed.' }
    $refused=$false
    try { Remove-StatTrackerDataTarget ([pscustomobject]@{Base=$local;Path=$other}) } catch { $refused=$true }
    if (-not $refused) { throw 'Unexpected target accepted.' }
    $refused=$false
    try { Remove-StatTrackerDataTarget ([pscustomobject]@{Base=$local;Path=$fixture}) } catch { $refused=$true }
    if (-not $refused) { throw 'Parent directory accepted.' }
}
Write-Output 'Uninstall cleanup passed: exact app folders removed; unrelated folders and parent paths protected.'

$linkBase=Join-Path $fixture 'linked\Local'
New-Item -ItemType Directory -Force -Path $linkBase | Out-Null
$link=Join-Path $linkBase 'Stat Tracker'
$unrelated=Join-Path $fixture 'user-one\AppData\Local\Other App'
if (-not (Test-Path -LiteralPath $link)) { New-Item -ItemType Junction -Path $link -Target $unrelated | Out-Null }
$refused=$false
try { Remove-StatTrackerDataTarget ([pscustomobject]@{Base=$linkBase;Path=$link}) } catch { $refused=$true }
if (-not $refused -or -not (Test-Path -LiteralPath (Join-Path $unrelated 'keep.txt'))) { throw 'Linked directory was not protected.' }
Write-Output 'Junction protection passed.'
