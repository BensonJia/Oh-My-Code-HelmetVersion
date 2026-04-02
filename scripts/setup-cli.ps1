Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LocalBin = Join-Path $HOME ".local\bin"

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return ,@("py", "-3")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return ,@("python")
    }
    throw "Python was not found. Install Python 3.9+ first."
}

function Invoke-Python {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $Python = Get-PythonCommand
    if ($Python.Length -gt 1) {
        & $Python[0] $Python[1..($Python.Length - 1)] @Arguments
    } else {
        & $Python[0] @Arguments
    }
}

Write-Host "[setup-cli] Installing editable package from: $RootDir"
Push-Location $RootDir
try {
    # Equivalent to: pip install -e ".[dev]"
    Invoke-Python -Arguments @("-m", "pip", "install", "-e", ".[dev]")
} finally {
    Pop-Location
}

$ScriptsDir = Invoke-Python -Arguments @(
    "-c",
    "import sysconfig; print(sysconfig.get_path('scripts'))"
) | Select-Object -First 1

if (-not $ScriptsDir) {
    throw "Could not determine Python scripts directory."
}

New-Item -ItemType Directory -Force -Path $LocalBin | Out-Null

$CmdShim = Join-Path $LocalBin "ohmycode.cmd"
$PsShim = Join-Path $LocalBin "ohmycode.ps1"

$CmdContent = @"
@echo off
"$ScriptsDir\ohmycode.exe" %*
"@
Set-Content -Path $CmdShim -Value $CmdContent -Encoding ASCII

$PsContent = @"
& "$ScriptsDir\ohmycode.exe" @args
"@
Set-Content -Path $PsShim -Value $PsContent -Encoding ASCII

$CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = @()
if ($CurrentUserPath) {
    $PathParts = $CurrentUserPath.Split(";") | Where-Object { $_ }
}

foreach ($Candidate in @($LocalBin, $ScriptsDir)) {
    if ($PathParts -notcontains $Candidate) {
        $PathParts += $Candidate
        Write-Host "[setup-cli] Added PATH entry: $Candidate"
    } else {
        Write-Host "[setup-cli] PATH entry already present: $Candidate"
    }
}

$UpdatedUserPath = ($PathParts | Select-Object -Unique) -join ";"
[Environment]::SetEnvironmentVariable("Path", $UpdatedUserPath, "User")
$env:Path = ($UpdatedUserPath + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine"))

Write-Host "[setup-cli] Verifying CLI wiring..."
Invoke-Python -Arguments @("-m", "pip", "show", "ohmycode")
& $CmdShim --help | Out-Null
Write-Host "[setup-cli] OK: use 'ohmycode' to start."
