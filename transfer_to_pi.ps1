# Transfer Film Scanner to Raspberry Pi
# PowerShell script for Windows users

param(
    [string]$PiAddress = "raspberrypi.local",
    [string]$PiUser = "pi"
)

Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Film Scanner - Transfer to Raspberry Pi" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Get current directory
$SourceDir = $PSScriptRoot
Write-Host "Source directory: $SourceDir" -ForegroundColor Blue
Write-Host "Target Pi: $PiUser@$PiAddress" -ForegroundColor Blue
Write-Host ""

# Check if scp is available
$scpPath = Get-Command scp -ErrorAction SilentlyContinue

if (-not $scpPath) {
    Write-Host "❌ Error: scp not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "1. Install OpenSSH Client (Windows 10/11):" -ForegroundColor Yellow
    Write-Host "   Settings → Apps → Optional Features → Add OpenSSH Client" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2. Use WinSCP (GUI tool):" -ForegroundColor Yellow
    Write-Host "   Download from: https://winscp.net/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "3. Copy files to USB drive manually" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

Write-Host "✓ OpenSSH found" -ForegroundColor Green
Write-Host ""

# Test connection to Pi
Write-Host "Testing connection to Pi..." -ForegroundColor Blue
$pingResult = Test-Connection -ComputerName $PiAddress -Count 1 -Quiet

if (-not $pingResult) {
    Write-Host "⚠️  Warning: Cannot ping $PiAddress" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please enter Pi IP address manually (or press Enter to try anyway):"
    $manualIP = Read-Host "Pi IP address"
    if ($manualIP) {
        $PiAddress = $manualIP
    }
    Write-Host ""
}

# Files to transfer
$FilesToTransfer = @(
    "web_app.py",
    "requirements.txt",
    "setup_pi.sh",
    "templates",
    "static",
    "README_WEB_APP.md",
    "QUICKSTART.md",
    "RASPBERRY_PI_SETUP.md",
    "LIVE_PREVIEW_FEATURE.md",
    "quick_install.txt"
)

Write-Host "Files to transfer:" -ForegroundColor Blue
foreach ($file in $FilesToTransfer) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  $file (not found)" -ForegroundColor Yellow
    }
}
Write-Host ""

# Confirm transfer
Write-Host "Ready to transfer files to Pi. Continue? (Y/N)" -ForegroundColor Yellow
$confirm = Read-Host
if ($confirm -ne "Y" -and $confirm -ne "y") {
    Write-Host "Transfer cancelled." -ForegroundColor Red
    exit 0
}
Write-Host ""

# Create remote directory
Write-Host "Creating remote directory..." -ForegroundColor Blue
ssh "$PiUser@$PiAddress" "mkdir -p ~/Scanner-Web"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to create remote directory" -ForegroundColor Red
    Write-Host "Check:" -ForegroundColor Yellow
    Write-Host "  1. Pi is powered on and connected to network" -ForegroundColor Yellow
    Write-Host "  2. SSH is enabled on Pi (sudo raspi-config)" -ForegroundColor Yellow
    Write-Host "  3. Correct username (default: pi)" -ForegroundColor Yellow
    Write-Host "  4. Correct address ($PiAddress)" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ Remote directory created" -ForegroundColor Green
Write-Host ""

# Transfer files
Write-Host "Transferring files..." -ForegroundColor Blue
Write-Host "(This may take a minute...)" -ForegroundColor Blue
Write-Host ""

foreach ($file in $FilesToTransfer) {
    if (Test-Path $file) {
        Write-Host "Copying $file..." -ForegroundColor Cyan
        scp -r "$file" "$PiUser@$PiAddress`:~/Scanner-Web/"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $file transferred" -ForegroundColor Green
        } else {
            Write-Host "  ❌ Failed to transfer $file" -ForegroundColor Red
        }
    }
}
Write-Host ""

# Make setup script executable
Write-Host "Making setup script executable..." -ForegroundColor Blue
ssh "$PiUser@$PiAddress" "chmod +x ~/Scanner-Web/setup_pi.sh"
Write-Host "✓ Setup script is executable" -ForegroundColor Green
Write-Host ""

# Success message
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✓ Transfer Complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "Files transferred to: $PiUser@$PiAddress`:~/Scanner-Web/" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. SSH to your Pi:" -ForegroundColor White
Write-Host "   ssh $PiUser@$PiAddress" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Run setup script:" -ForegroundColor White
Write-Host "   cd ~/Scanner-Web" -ForegroundColor Cyan
Write-Host "   ./setup_pi.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or run setup automatically now? (Y/N)" -ForegroundColor Yellow
$runSetup = Read-Host

if ($runSetup -eq "Y" -or $runSetup -eq "y") {
    Write-Host ""
    Write-Host "Running setup on Pi..." -ForegroundColor Blue
    Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan
    ssh -t "$PiUser@$PiAddress" "cd ~/Scanner-Web && ./setup_pi.sh"
    Write-Host ""
    Write-Host "Setup complete! Check output above for access URL." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Setup not run. SSH to Pi and run it manually when ready." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════" -ForegroundColor Cyan

