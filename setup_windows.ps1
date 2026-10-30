# setup_windows.ps1 -- one-shot environment setup for the mic-bridge project.
#
#   powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1              # DRY RUN, changes nothing
#   powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go          # runtime deps: adb + VB-Cable + venv
#   powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1 -Go -WithBuild   # also the APK build chain (~310 MB)
#
# Keep this file PURE ASCII: Windows PowerShell 5.1 reads BOM-less UTF-8 as GBK and mangles it.
# Nothing here is deleted. Downloads go to %TEMP%. Re-running is safe (everything is checked first).

param(
    [switch]$Go,
    [switch]$WithBuild,
    [switch]$Firewall
)

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolRoot = 'C:\android-build'

$VBCABLE_URL = 'https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip'
$JDK_URL     = 'https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip'
$BT_URL      = 'https://dl.google.com/android/repository/build-tools_r34-windows.zip'
$PLATFORM_URL= 'https://dl.google.com/android/repository/android-21_r02.zip'
$ADB_WINGET  = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe'

$results = @()
function Add-Result($name, $status, $note) {
    $script:results += [pscustomobject]@{ Item = $name; Status = $status; Note = $note }
    Write-Host ("[{0,-6}] {1} :: {2}" -f $status, $name, $note)
}
function Need-Go($name, $plan) {
    if ($Go) { return $true }
    Add-Result $name 'WOULD' $plan
    return $false
}
function Get-File($url, $dest) {
    Write-Host "  downloading $url"
    & curl.exe -sSL --connect-timeout 20 --max-time 3600 -o $dest $url
    return (Test-Path $dest)
}
function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host "=== mic-bridge environment setup ===" -ForegroundColor Cyan
Write-Host ("repo   : {0}" -f $RepoRoot)
Write-Host ("mode   : {0}{1}" -f ($(if ($Go) { 'APPLY' } else { 'DRY RUN (nothing will be installed)' })),
                                            $(if ($WithBuild) { ' +WithBuild' } else { '' }))
Write-Host ("admin  : {0}" -f (Test-Admin))

if ($Go -and -not (Test-Admin)) {
    Write-Host 'Driver install needs elevation. Re-launching self as administrator...' -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoProfile','-ExecutionPolicy','Bypass','-File', "`"$RepoRoot\setup_windows.ps1`"",
        '-Go') + $(if ($WithBuild) { @('-WithBuild') } else { @() })
    exit
}

# ---------- 0. baseline ----------
$os = Get-CimInstance Win32_OperatingSystem
Add-Result 'Windows' 'INFO' ("{0} build {1}, {2}" -f $os.Caption, $os.BuildNumber, $env:PROCESSOR_ARCHITECTURE)
if ($os.BuildNumber -lt 19041) {
    Add-Result 'Windows' 'WARN' 'Unverified on builds older than 19041 (project was validated on 22631).'
}
$wingetOk = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
Add-Result 'winget' $(if ($wingetOk) { 'OK' } else { 'FAIL' }) $(if ($wingetOk) { 'available' } else { 'not on PATH; install App Installer from the Store' })

# ---------- 1. adb ----------
$adb = $null
foreach ($c in @($ADB_WINGET, 'adb')) {
    if (-not $c) { continue }
    $p = if ($c -eq 'adb') { (Get-Command adb -ErrorAction SilentlyContinue).Source } else { $c }
    if ($p -and (Test-Path $p)) { $adb = $p; break }
}
if ($adb) {
    Add-Result 'adb' 'OK' ("present: {0}" -f $adb)
} elseif (Need-Go 'adb' 'winget install --id Google.PlatformTools') {
    winget install --id Google.PlatformTools --accept-package-agreements --accept-source-agreements --silent
    if (Test-Path $ADB_WINGET) { $adb = $ADB_WINGET; Add-Result 'adb' 'DONE' $adb }
    else { Add-Result 'adb' 'FAIL' 'installed but adb.exe not found at the expected winget path' }
}

# ---------- 2. VB-Cable virtual microphone ----------
$cable = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -like '*CABLE Output*' }
if ($cable) {
    Add-Result 'VB-Cable' 'OK' ("capture endpoint present: {0} (status {1})" -f $cable.Name, $cable.Status)
} elseif (Need-Go 'VB-Cable' ("download Pack45 and install driver (no reboot needed)")) {
    # NOTE: Pack43 (2015) ships only win7-era drivers and will NOT install on Win11. Use Pack45+.
    $tmp = Join-Path $env:TEMP 'micbridge_setup'
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    $zip = Join-Path $tmp 'vbc45.zip'
    if (-not (Get-File $VBCABLE_URL $zip)) { Add-Result 'VB-Cable' 'FAIL' 'download failed' }
    else {
        $dir = Join-Path $tmp 'vbc45'
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
        Expand-Archive -Path $zip -DestinationPath $dir -Force
        $exe = Join-Path $dir 'VBCABLE_Setup_x64.exe'
        if (-not (Test-Path $exe)) { Add-Result 'VB-Cable' 'FAIL' "VBCABLE_Setup_x64.exe missing in $dir" }
        else {
            Write-Host '  running vendor installer (a UAC prompt may appear)...'
            $p = Start-Process -FilePath $exe -WorkingDirectory $dir -Verb RunAs -PassThru
            $p | Wait-Process -Timeout 180 -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 3
            $cable = Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -like '*CABLE Output*' }
            if ($cable) { Add-Result 'VB-Cable' 'DONE' 'CABLE Output capture endpoint now exists' }
            else { Add-Result 'VB-Cable' 'FAIL' 'installer ran but no CABLE Output endpoint appeared; check Device Manager > ROOT\MEDIA' }
        }
    }
}

# ---------- 3. Python venv (sounddevice + numpy) ----------
$pyExe = $null
foreach ($c in @('python', 'py')) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $pyExe = $g.Source; break }
}
$venv = Join-Path $RepoRoot '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
if (Test-Path $venvPy) {
    Add-Result 'python' 'OK' ("venv present: {0}" -f $venvPy)
} elseif (-not $pyExe) {
    Add-Result 'python' 'FAIL' 'no python on PATH; install Python 3.10+ (project used 3.13)'
} elseif (Need-Go 'python' ("create {0} and pip install sounddevice numpy" -f $venv)) {
    & $pyExe -m venv $venv
    & $venvPy -m pip install -q --disable-pip-version-check sounddevice numpy
    $probe = & $venvPy -c "import sounddevice as sd, numpy as np; print('OK', len(sd.query_devices()))" 2>&1
    if ("$probe" -like 'OK*') { Add-Result 'python' 'DONE' $probe }
    else { Add-Result 'python' 'FAIL' "$probe" }
}

# ---------- 4. optional: APK build chain ----------
if ($WithBuild) {
    # HARD RULE: the toolchain must live on a PURE ASCII path.
    # aapt2 cannot stat files under non-ASCII dirs (E:/github... style folders) and reports
    # "Failed to stat file '...android.jar': No such file or directory" even when the file exists.
    New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null
    $jdkDir = Join-Path $ToolRoot 'jdk17'
    # build-tools_r34-windows.zip unpacks to a folder literally named 'android-14'
    $btDir  = Join-Path $ToolRoot 'android-14'
    # android-21_r02.zip unpacks to a folder literally named 'android-5.0.1'
    $platDir= Join-Path $ToolRoot 'android-5.0.1'

    foreach ($item in @(
        @{ n='jdk17';      p=(Join-Path $jdkDir 'bin\javac.exe');    url=$JDK_URL;      leaf='jdk17' },
        @{ n='build-tools';p=(Join-Path $btDir  'aapt2.exe');        url=$BT_URL;       leaf='android-14' },
        @{ n='platform21'; p=(Join-Path $platDir 'android.jar');     url=$PLATFORM_URL; leaf='android-5.0.1' })) {
        if (Test-Path $item.p) {
            Add-Result $item.n 'OK' $item.p
        } elseif (Need-Go $item.n ("download+unpack {0} into {1}" -f $item.leaf, $ToolRoot)) {
            $z = Join-Path $env:TEMP ("micbridge_{0}.zip" -f $item.leaf)
            if (-not (Get-File $item.url $z)) { Add-Result $item.n 'FAIL' 'download failed'; continue }
            $stage = Join-Path $env:TEMP ("micbridge_stage_{0}" -f $item.leaf)
            if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
            Expand-Archive -Path $z -DestinationPath $stage -Force
            $src = Get-ChildItem $stage -Directory | Select-Object -First 1
            if (-not $src) { Add-Result $item.n 'FAIL' 'no folder inside the zip'; continue }
            $dst = Join-Path $ToolRoot $item.leaf
            if (Test-Path $dst) {
                # Never delete: an incomplete toolchain dir gets moved aside instead.
                $bak = "$dst.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
                Rename-Item $dst $bak
                Write-Host "  moved existing $(Split-Path $dst -Leaf) aside to $(Split-Path $bak -Leaf)"
            }
            Move-Item $src.FullName $dst
            if (Test-Path $item.p) { Add-Result $item.n 'DONE' $item.p }
            else { Add-Result $item.n 'FAIL' ("expected {0} after unpack" -f $item.p) }
        }
    }
}

# ---------- 5. optional: firewall rule for WiFi mode ----------
# Without this, the tablet's inbound TCP:5005 is dropped by Windows and the receiver
# just sits printing "waiting for device" forever.
$fwName = 'mic-bridge-receiver-5005'
$fwExists = $false
netsh advfirewall firewall show rule name=$fwName > $null 2>&1
if ($LASTEXITCODE -eq 0) { $fwExists = $true }
if ($Firewall) {
    if ($fwExists) {
        Add-Result 'firewall' 'OK' "rule '$fwName' already present"
    } elseif (Need-Go 'firewall' ("add inbound allow rule TCP:5005 (private profile) named $fwName")) {
        netsh advfirewall firewall add rule name=$fwName dir=in action=allow protocol=TCP localport=5005 profile=private enable=yes | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Add-Result 'firewall' 'DONE' 'inbound TCP:5005 allowed (private profile only)'
        } else {
            Add-Result 'firewall' 'FAIL' "netsh exit $LASTEXITCODE - run this script from an elevated prompt"
        }
    }
} elseif ($fwExists) {
    Add-Result 'firewall' 'OK' "rule '$fwName' already present"
}

# ---------- summary ----------
Write-Host ''
Write-Host '=== summary ===' -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-String -Width 160 | Write-Host

Write-Host '=== the only steps a script cannot do (Android security model) ===' -ForegroundColor Cyan
@'
  1. On the tablet: Settings > Developer options > USB debugging = ON
     (no Developer options? Settings > About tablet, tap "Build number" 7 times)
  2. Plug in a DATA cable (charge-only cables will never enumerate adb).
  3. When the tablet shows "Allow USB debugging?", tap ALLOW and tick
     "Always allow from this computer".
     Note: 'adb devices' showing 'offline' does NOT mean "waiting for your tap" --
     the dialog is not shown in that state. Toggle USB debugging off/on to recover.
'@ | Write-Host

Write-Host '=== then ===' -ForegroundColor Cyan
@'
  adb install -r release\mic-bridge-0.3.2.apk
  .venv\Scripts\python.exe pc_receiver.py
  adb shell am start -n com.zcstudy.micbridge/.MainActivity --ez auto true
  Set "CABLE Output" as the Windows default recording device
  (Settings > System > Sound > Input). CapsWriter then needs zero code changes.

  Verify with:  bash run_selftest.sh
  Pass/fail criteria: AGENTS.md section 4. Acceptance numbers: the docs/ folder.
  Reminder: 'am start --ez' only accepts true/false. "1" parses as FALSE.
'@ | Write-Host
