<#
.SYNOPSIS
    Quick installer script for aws-auth on Windows.
.DESCRIPTION
    Downloads and installs the latest pre-compiled aws-auth.exe binary from GitHub Releases,
    adds it to the User PATH, and verifies installation.
    Can also install optional dependencies (AWS CLI, kubectl, Session Manager Plugin) via winget.
.EXAMPLE
    irm https://raw.githubusercontent.com/N0mansky/aws-auth/main/install.ps1 | iex
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\aws-auth",
    [string]$ReleaseTag = "latest",
    [switch]$SkipDeps
)

$ErrorActionPreference = "Stop"

Write-Host "`n⚡ AWS-Auth Windows Quick Installer" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor DarkGray

# 1. Install / Verify Dependencies via winget (if available and not skipped)
if (-not $SkipDeps -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "`n🔍 Checking prerequisites..." -ForegroundColor Yellow

    # AWS CLI
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS CLI via winget..." -ForegroundColor Gray
        winget install --id Amazon.AWSCLI -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS CLI is already installed" -ForegroundColor Green
    }

    # Session Manager Plugin
    if (-not (Get-Command session-manager-plugin -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS SSM Session Manager Plugin via winget..." -ForegroundColor Gray
        winget install --id Amazon.SessionManagerPlugin -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS SSM Session Manager Plugin is already installed" -ForegroundColor Green
    }

    # kubectl
    if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing kubectl via winget..." -ForegroundColor Gray
        winget install --id Kubernetes.kubectl -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ kubectl is already installed" -ForegroundColor Green
    }
}

# 2. Setup Destination Directory
$ResolvedInstallDir = if (-not [string]::IsNullOrWhiteSpace($InstallDir)) { $InstallDir } elseif ($env:LOCALAPPDATA) { "$env:LOCALAPPDATA\Programs\aws-auth" } else { "$env:USERPROFILE\.aws-auth\bin" }

if (-not (Test-Path -LiteralPath $ResolvedInstallDir)) {
    New-Item -ItemType Directory -Path $ResolvedInstallDir -Force | Out-Null
}

$ExePath = Join-Path $ResolvedInstallDir "aws-auth.exe"

# 3. Obtain Binary (Local dist/ or Download from GitHub)
$LocalDist = if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) { Join-Path $PSScriptRoot "dist\aws-auth.exe" } else { $null }
if ($LocalDist -and (Test-Path -LiteralPath $LocalDist)) {
    Write-Host "`n📂 Copying local build from dist\aws-auth.exe..." -ForegroundColor Yellow
    Copy-Item -Path $LocalDist -Destination $ExePath -Force
} else {
    $DownloadUrl = if ($ReleaseTag -eq "latest") {
        "https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-windows-amd64.exe"
    } else {
        "https://github.com/N0mansky/aws-auth/releases/download/$ReleaseTag/aws-auth-windows-amd64.exe"
    }

    Write-Host "`n⬇️  Downloading latest aws-auth binary from GitHub Releases..." -ForegroundColor Yellow
    Write-Host "   URL: $DownloadUrl" -ForegroundColor DarkGray
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ExePath -UseBasicParsing
}

# 4. Add to User PATH if not already present
$UserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($null -eq $UserPath -or $UserPath -notlike "*$ResolvedInstallDir*") {
    Write-Host "`n⚙️  Adding $ResolvedInstallDir to User PATH..." -ForegroundColor Yellow
    $NewPath = if ([string]::IsNullOrWhiteSpace($UserPath)) { $ResolvedInstallDir } else { "$UserPath;$ResolvedInstallDir" }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, [EnvironmentVariableTarget]::User)
}

# Update PATH in current PowerShell session
if ($env:Path -notlike "*$ResolvedInstallDir*") {
    $env:Path = "$env:Path;$ResolvedInstallDir"
}

# 5. Success Banner & Instructions
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 aws-auth installed successfully!" -ForegroundColor Green
Write-Host "   Binary Location: $ExePath" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`nTo get started:" -ForegroundColor Yellow
Write-Host "  1. Restart your terminal (PowerShell / Command Prompt / Windows Terminal)" -ForegroundColor White
Write-Host "  2. Run: aws-auth`n" -ForegroundColor Cyan
