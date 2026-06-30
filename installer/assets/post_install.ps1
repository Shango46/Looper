<#
.SYNOPSIS
    Post-install setup script called by the Looper installer.
    Installs Python 3.11 and Git if missing, creates a venv, installs
    pip packages, and sets up the Playwright browser engine.
#>
param([string]$InstallDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Write-Status([string]$msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] $msg"
}

function Download-File([string]$Url, [string]$Dest) {
    Write-Status "Downloading $(Split-Path $Dest -Leaf)..."
    $wc = New-Object System.Net.WebClient
    $wc.Headers.Add("User-Agent", "Looper-Installer/1.0")
    $wc.DownloadFile($Url, $Dest)
}

# ── Python 3.11 ──────────────────────────────────────────────────────────────

Write-Status "Checking for Python 3.11..."
$py311 = $null

# 1. Try the Python Launcher (py.exe) — most reliable on Windows
try {
    $v = & py -3.11 --version 2>&1
    if ($v -match "^Python 3\.11\.") {
        $py311 = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
        Write-Status "Found via Python Launcher: $py311"
    }
} catch {}

# 2. Try registry (user + system installs)
if (-not $py311) {
    $regPaths = @(
        "HKCU:\Software\Python\PythonCore\3.11\InstallPath",
        "HKLM:\Software\Python\PythonCore\3.11\InstallPath",
        "HKLM:\Software\WOW6432Node\Python\PythonCore\3.11\InstallPath"
    )
    foreach ($rp in $regPaths) {
        if (Test-Path $rp) {
            try {
                $dir = (Get-ItemProperty $rp -Name "(default)" -ErrorAction Stop)."(default)"
                $exe = Join-Path $dir "python.exe"
                if (Test-Path $exe) { $py311 = $exe; Write-Status "Found via registry: $py311"; break }
            } catch {}
        }
    }
}

# 3. Check common default install paths
if (-not $py311) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python311\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $py311 = $c; Write-Status "Found at: $py311"; break }
    }
}

# 4. Not found — download and install Python 3.11.9
if (-not $py311) {
    Write-Status "Python 3.11 not found. Downloading installer (~25 MB)..."
    $pyUrl  = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyExe  = "$env:TEMP\python-3.11.9-amd64.exe"
    Download-File $pyUrl $pyExe

    Write-Status "Installing Python 3.11 (user install, no admin required)..."
    $args = "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_launcher=1"
    Start-Process -FilePath $pyExe -ArgumentList $args -Wait -NoNewWindow
    Remove-Item $pyExe -Force -ErrorAction SilentlyContinue

    # Refresh env so py.exe or new python.exe are discoverable
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","Machine")

    # Try the launcher again
    try {
        $v = & py -3.11 --version 2>&1
        if ($v -match "^Python 3\.11\.") {
            $py311 = (& py -3.11 -c "import sys; print(sys.executable)").Trim()
        }
    } catch {}

    # Fall back to well-known default location
    if (-not $py311) {
        $py311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    }
}

if (-not (Test-Path $py311)) {
    Write-Status "ERROR: Could not locate python.exe after install attempt."
    exit 1
}
Write-Status "Using Python: $py311"

# ── Git ───────────────────────────────────────────────────────────────────────

Write-Status "Checking for Git..."
$gitOk = $false
try { $null = & git --version 2>&1; $gitOk = ($LASTEXITCODE -eq 0) } catch {}

if (-not $gitOk) {
    Write-Status "Git not found. Attempting install via winget..."
    $wingetOk = $false
    try {
        Start-Process "winget" -ArgumentList "install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements" -Wait -NoNewWindow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User")
        try { $null = & git --version 2>&1; $wingetOk = ($LASTEXITCODE -eq 0) } catch {}
    } catch {}

    if (-not $wingetOk) {
        Write-Status "winget unavailable or failed. Downloading Git installer (~60 MB)..."
        $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
        $gitExe = "$env:TEMP\git-installer.exe"
        Download-File $gitUrl $gitExe
        Write-Status "Installing Git..."
        Start-Process -FilePath $gitExe `
            -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /COMPONENTS=icons,ext\reg\shellhere,assoc,assoc_sh" `
            -Wait -NoNewWindow
        Remove-Item $gitExe -Force -ErrorAction SilentlyContinue
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User")
    }

    try { $null = & git --version 2>&1; Write-Status "Git installed successfully." } catch {
        Write-Status "WARNING: Git install may have failed. The update system requires Git."
    }
} else {
    Write-Status "Git already installed."
}

# ── Virtual environment ───────────────────────────────────────────────────────

Set-Location $InstallDir
$venvDir  = Join-Path $InstallDir ".venv"
$pip      = Join-Path $venvDir "Scripts\pip.exe"
$pythonVenv = Join-Path $venvDir "Scripts\python.exe"

Write-Status "Creating virtual environment..."
& $py311 -m venv $venvDir
if (-not (Test-Path $pythonVenv)) {
    Write-Status "ERROR: venv creation failed."
    exit 1
}

# ── pip install ───────────────────────────────────────────────────────────────

Write-Status "Upgrading pip..."
& $pythonVenv -m pip install --upgrade pip --quiet

Write-Status "Installing Looper dependencies (may take a few minutes)..."
& $pip install -r "$InstallDir\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Status "ERROR: pip install failed."
    exit 1
}

# ── Node.js ──────────────────────────────────────────────────────────────────

Write-Status "Checking for Node.js..."
$nodeOk = $false
try { $null = & node --version 2>&1; $nodeOk = ($LASTEXITCODE -eq 0) } catch {}

if (-not $nodeOk) {
    Write-Status "Node.js not found. Downloading LTS installer (~30 MB)..."
    $nodeUrl = "https://nodejs.org/dist/v20.18.3/node-v20.18.3-x64.msi"
    $nodeMsi = "$env:TEMP\node-installer.msi"
    Download-File $nodeUrl $nodeMsi
    Write-Status "Installing Node.js LTS..."
    Start-Process "msiexec.exe" -ArgumentList "/i `"$nodeMsi`" /quiet /norestart" -Wait -NoNewWindow
    Remove-Item $nodeMsi -Force -ErrorAction SilentlyContinue
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
    try { $null = & node --version 2>&1; Write-Status "Node.js installed." } catch {
        Write-Status "WARNING: Node.js install may have failed — n8n automations will be unavailable."
    }
} else {
    Write-Status "Node.js already installed."
}

# ── n8n ───────────────────────────────────────────────────────────────────────

Write-Status "Installing n8n (this may take a few minutes)..."
try {
    & npm install -g n8n --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Status "n8n installed."
    } else {
        Write-Status "WARNING: n8n install returned a non-zero exit code — automations may be unavailable."
    }
} catch {
    Write-Status "WARNING: n8n install failed — automations will be unavailable."
}

# ── Playwright / Chromium ─────────────────────────────────────────────────────

Write-Status "Installing browser automation engine (Playwright Chromium, ~150 MB)..."
try {
    & $pythonVenv -m playwright install chromium
    Write-Status "Playwright Chromium installed."
} catch {
    Write-Status "WARNING: Playwright install failed — browser automation may not work."
    Write-Status "You can retry later from Settings > Run Setup in the Looper web UI."
}

# ── Done ──────────────────────────────────────────────────────────────────────

Write-Status "Setup complete. Looper is ready."
exit 0
