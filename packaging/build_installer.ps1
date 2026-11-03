# build_installer.ps1 -- build the per-user (no admin) Windows installer.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1 -Version 0.7.1 -Sign
#
# Pipeline:
#   1. PyInstaller (onedir, no UPX)  -> dist\windows\Jiushouji-Mic\
#   2. Inno Setup 6/7                -> dist\windows\mic-bridge-setup-peruser-<ver>.exe
#   3. optional code signing (signtool) when a certificate is configured.
#
# Nothing is installed on this machine. Output stays under dist\windows so it never
# mixes with the Android artifacts in dist\ or release\.
#
# Keep this file PURE ASCII: Windows PowerShell 5.1 reads BOM-less UTF-8 as GBK.

param(
    [string]$Version = "0.7.1",
    [string]$Python = "",
    [switch]$SkipExe,
    [switch]$Sign
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$DistWin = Join-Path $Repo "dist\windows"
$Work = Join-Path $Repo "build_tmp"
$AppsDir = Join-Path $DistWin "Jiushouji-Mic"
$AppExe = Join-Path $AppsDir "mic-bridge-receiver.exe"

if (-not $Python) {
    $venvPy = Join-Path $Repo ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { $Python = $venvPy }
    else {
        $g = Get-Command python -ErrorAction SilentlyContinue
        if ($g) { $Python = $g.Source } else { throw "no python found; pass -Python <path>" }
    }
}
Write-Host ("python : {0}" -f $Python)
Write-Host ("repo   : {0}" -f $Repo)
Write-Host ("out    : {0}" -f $DistWin)

# ---------- 1. PyInstaller (onedir) ----------
if (-not $SkipExe) {
    Write-Host "`n[1/3] PyInstaller onedir build" -ForegroundColor Cyan
    & $Python -m PyInstaller --noconfirm --clean --log-level WARN `
        --distpath $DistWin --workpath $Work `
        (Join-Path $PSScriptRoot "mic_bridge_receiver.spec")
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
}
if (-not (Test-Path $AppExe)) { throw "missing $AppExe" }

$vi = (Get-Item $AppExe).VersionInfo
Write-Host ("exe    : {0}" -f $AppExe)
Write-Host ("         {0} {1} / file {2}" -f $vi.ProductName, $vi.ProductVersion, $vi.FileVersion)

# ---------- 2. Inno Setup ----------
Write-Host "`n[2/3] Inno Setup compile" -ForegroundColor Cyan
$isccCandidates = @()
if ($env:INNO_SETUP_HOME) { $isccCandidates += (Join-Path $env:INNO_SETUP_HOME "ISCC.exe") }
$isccCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
$isccCandidates += (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe")
$isccCandidates += "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$isccCandidates += "C:\Program Files\Inno Setup 6\ISCC.exe"
$isccCandidates += "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
$isccCandidates += "C:\Program Files\Inno Setup 7\ISCC.exe"
$iscc = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
    $g = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($g) { $iscc = $g.Source }
}
if (-not $iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6/7 or set INNO_SETUP_HOME."
}
Write-Host ("iscc   : {0}" -f $iscc)

& $iscc "/DAppVersion=$Version" (Join-Path $PSScriptRoot "mic-bridge.iss")
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with exit code $LASTEXITCODE" }

$Setup = Join-Path $DistWin ("mic-bridge-setup-peruser-{0}.exe" -f $Version)
if (-not (Test-Path $Setup)) { throw "missing $Setup" }

# ---------- 3. optional signing ----------
Write-Host "`n[3/3] code signing" -ForegroundColor Cyan
$signTool = $null
$kits = "C:\Program Files (x86)\Windows Kits\10\bin"
if (Test-Path $kits) {
    $signTool = Get-ChildItem $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $Sign) {
    Write-Host "  skipped (-Sign not set). Unsigned builds may still be flagged by AV; see README.md (Windows install / autostart section)" -ForegroundColor Yellow
}
elseif (-not $signTool) {
    Write-Warning "signtool.exe not found; skipping signing"
}
elseif (-not ($env:MICBRIDGE_PFX -or $env:MICBRIDGE_SIGN_THUMBPRINT)) {
    Write-Warning "no certificate configured (set MICBRIDGE_PFX + MICBRIDGE_PFX_PASS, or MICBRIDGE_SIGN_THUMBPRINT); skipping signing"
}
else {
    $files = @($AppExe, $Setup)
    foreach ($f in $files) {
        $args = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256")
        if ($env:MICBRIDGE_PFX) { $args += @("/f", $env:MICBRIDGE_PFX) }
        if ($env:MICBRIDGE_PFX_PASS) { $args += @("/p", $env:MICBRIDGE_PFX_PASS) }
        if ($env:MICBRIDGE_SIGN_THUMBPRINT) { $args += @("/sha1", $env:MICBRIDGE_SIGN_THUMBPRINT) }
        $args += $f
        & $signTool @args
        if ($LASTEXITCODE -ne 0) { throw "signtool failed on $f" }
    }
    Write-Host "  signed: $($files -join ', ')"
}

# ---------- summary ----------
Write-Host "`n=== artifacts ===" -ForegroundColor Cyan
foreach ($f in @($AppExe, $Setup)) {
    $i = Get-Item $f
    $h = (Get-FileHash $f -Algorithm SHA256).Hash
    Write-Host ("{0}`n  {1:N1} MB  sha256 {2}" -f $i.FullName, ($i.Length / 1MB), $h)
}
Write-Host "`nInstall (per-user, no UAC):  `"$Setup`""
Write-Host "Silent verify (temp dir, no shortcuts/autostart): `"$Setup`" /VERYSILENT /SUPPRESSMSGBOXES /NOICONS /MERGETASKS=`"!autostart,!desktopicon`" /DIR=`"$env:TEMP\micbridge-test`""
Write-Host "Uninstall (removes the temp copy):              `"$env:TEMP\micbridge-test\unins000.exe`" /VERYSILENT"
