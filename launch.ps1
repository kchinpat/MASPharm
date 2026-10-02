param([switch]$SmokeTest, [string]$DataDir, [switch]$Usb, [switch]$TeamUsb, [switch]$Web)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskCandidates = @()
$taskVenv = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $taskVenv) { $taskCandidates += $taskVenv }
$taskBundled = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $taskBundled) { $taskCandidates += $taskBundled }
foreach ($taskCommand in @('py.exe', 'python.exe', 'python3.exe')) {
    $taskFound = Get-Command $taskCommand -ErrorAction SilentlyContinue
    if ($taskFound) { $taskCandidates += $taskFound.Source }
}
$taskPython = $null
foreach ($taskCandidate in $taskCandidates) {
    try {
        & $taskCandidate -B -c "import sys, tkinter, sqlite3; assert sys.version_info >= (3, 10); tkinter.Tcl()" 2>$null
        if ($LASTEXITCODE -eq 0) { $taskPython = $taskCandidate; break }
    } catch { }
}
if (-not $taskPython) {
    Write-Host 'Python 3.10 or later with Tcl/Tk is required. Install Python from python.org, then double-click this launcher again.'
    exit 1
}
$taskArgs = @('-B', '-m', 'pharm.app')
if ($Web) {
    if ($SmokeTest -or $Usb -or $TeamUsb) { throw 'The browser launcher starts simulation. Use python -m pharm.web --help for hardware options.' }
    $taskArgs = @('-B', '-m', 'pharm.web', '--open-browser')
    & $taskPython -B -c 'import pharm, flask' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Install requirements-web.txt with the selected Python before starting the browser UI.' }
}
if ($SmokeTest) { $taskArgs += '--smoke-test' }
if ($Usb) { $taskArgs += '--usb' }
if ($TeamUsb) { $taskArgs += '--team-usb' }
if ($DataDir) { $taskArgs += @('--data-dir', $DataDir) }
& $taskPython @taskArgs
exit $LASTEXITCODE
