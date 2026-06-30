<#
.SYNOPSIS
    Builds LooperInstaller.exe — generates the icon and compiles the Inno Setup script.
.DESCRIPTION
    Run this from the installer\ directory (or any location — paths are resolved from
    the script's own location). Output: installer\Output\LooperInstaller.exe
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ── Step 1: Generate looper.ico ───────────────────────────────────────────────

Write-Host "Generating icon..."

# Find Python (prefer .venv in parent, fall back to system Python)
$parentVenvPy = Join-Path $ScriptDir "..\\.venv\\Scripts\\python.exe"
$parentVenvPy = [System.IO.Path]::GetFullPath($parentVenvPy)

if (Test-Path $parentVenvPy) {
    $pythonExe = $parentVenvPy
} else {
    # Try py launcher or system python
    try {
        $pythonExe = (& py -c "import sys; print(sys.executable)" 2>$null).Trim()
    } catch {
        $pythonExe = "python"
    }
}

# Ensure Pillow is available
& $pythonExe -c "from PIL import Image" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Pillow for icon generation..."
    & $pythonExe -m pip install pillow --quiet
}

& $pythonExe "assets\make_icon.py"
if (-not (Test-Path "assets\looper.ico")) {
    Write-Error "Icon generation failed. assets\looper.ico was not created."
    exit 1
}
Write-Host "Icon created: assets\looper.ico"

# ── Step 2: Ensure Inno Setup 6 is installed ─────────────────────────────────

$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
)
$isccPath = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $isccPath) {
    Write-Host "Inno Setup 6 not found. Installing via winget..."
    try {
        winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
    } catch {
        Write-Error "winget install failed. Please install Inno Setup 6 manually from https://jrsoftware.org/isinfo.php"
        exit 1
    }
    $isccPath = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $isccPath) {
        Write-Error "Inno Setup installed but ISCC.exe not found. Looked in: $($isccCandidates -join ', ')"
        exit 1
    }
}

Write-Host "Inno Setup: $isccPath"

# ── Step 3: Compile the installer ────────────────────────────────────────────

Write-Host "Compiling looper.iss..."
& $isccPath "looper.iss"

if ($LASTEXITCODE -ne 0) {
    Write-Error "ISCC compilation failed with exit code $LASTEXITCODE."
    exit 1
}

# ── Done ─────────────────────────────────────────────────────────────────────

$output = Join-Path $ScriptDir "Output\LooperInstaller.exe"
if (Test-Path $output) {
    $size = [math]::Round((Get-Item $output).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Build successful!"
    Write-Host "Output: $output ($size MB)"
} else {
    Write-Error "Build appeared to succeed but LooperInstaller.exe not found."
    exit 1
}
