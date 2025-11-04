# Film Scanner Multi-Version Setup - Quick Start

## Key Points

✅ **Uses YOUR existing deploy.sh files** from each branch  
✅ **Does NOT overwrite** any repository files  
✅ **Version controlled** - manage deploy.sh in GitHub  
✅ **Three separate directories** for main, testing, and web  

## What You Need to Do

### 1. Download These Files
- [setup_scanner_versions.sh](computer:///mnt/user-data/outputs/setup_scanner_versions.sh)
- [MULTI_VERSION_SETUP.md](computer:///mnt/user-data/outputs/MULTI_VERSION_SETUP.md)

### 2. Add to Your GitHub Repository

```bash
# Clone your repo (if you don't have it locally)
git clone https://github.com/ccyyturralde/Film-Scanner.git
cd Film-Scanner

# Switch to main branch
git checkout main

# Copy the downloaded files
cp ~/Downloads/setup_scanner_versions.sh .
cp ~/Downloads/MULTI_VERSION_SETUP.md .

# Commit and push
git add setup_scanner_versions.sh MULTI_VERSION_SETUP.md
git commit -m "Add multi-version setup and documentation"
git push origin main
```

### 3. Verify Each Branch Has deploy.sh

```bash
# Check main branch
git checkout main
ls -la deploy.sh

# Check Testing branch
git checkout Testing
ls -la deploy.sh

# Check web-mobile-version branch
git checkout web-mobile-version
ls -la deploy.sh
```

If any branch is missing deploy.sh, create one or copy from another branch.

### 4. Run on Your Raspberry Pi

Once added to GitHub, run on your Pi:

```bash
bash <(curl -sL https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/main/setup_scanner_versions.sh)
```

Or download and run locally:

```bash
wget https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/main/setup_scanner_versions.sh
bash setup_scanner_versions.sh
```

## How It Works

```
setup_scanner_versions.sh
    ↓
Clones three branches into separate directories
    ↓
~/film-scanner-versions/
├── main/        ← Uses deploy.sh from main branch
├── testing/     ← Uses deploy.sh from Testing branch
├── web/         ← Uses deploy.sh from web-mobile-version branch
└── Wrapper scripts (deploy_all.sh, etc.)
```

## Directory Structure After Setup

```
~/film-scanner-versions/
├── main/
│   ├── scanner_app_v2.py
│   ├── deploy.sh          ← From main branch (YOUR file)
│   ├── setup.sh           ← From main branch (YOUR file)
│   └── (all other files from main branch)
│
├── testing/
│   ├── scanner_app_v2.py
│   ├── deploy.sh          ← From Testing branch (YOUR file)
│   ├── setup.sh           ← From Testing branch (YOUR file)
│   └── (all other files from Testing branch)
│
├── web/
│   ├── scanner_web_app.py
│   ├── deploy.sh          ← From web-mobile-version branch (YOUR file)
│   ├── setup.sh           ← From web-mobile-version branch (YOUR file)
│   └── (all other files from web-mobile-version branch)
│
└── Convenience scripts:
    ├── deploy_all.sh      ← Calls each branch's deploy.sh
    ├── update_all.sh      ← Git pull all three branches
    ├── run_main.sh
    ├── run_testing.sh
    └── run_web.sh
```

## Common Commands

```bash
# Deploy a specific version (uses its own deploy.sh)
cd ~/film-scanner-versions/main && bash deploy.sh

# Deploy all versions
bash ~/film-scanner-versions/deploy_all.sh

# Update all from GitHub
bash ~/film-scanner-versions/update_all.sh

# Run a version
bash ~/film-scanner-versions/run_main.sh
```

## Example deploy.sh for Each Branch

If a branch doesn't have deploy.sh, here's a template:

```bash
#!/bin/bash
# Deploy script for [BRANCH_NAME]

set -e

echo "==================================="
echo "Deploying [BRANCH_NAME] Version"
echo "==================================="

cd "$(dirname "$0")"

echo "Pulling latest changes..."
git pull

echo "Installing dependencies..."
pip3 install --break-system-packages -r requirements.txt

# Add any branch-specific setup here
# For web branch, you might add:
# pip3 install --break-system-packages flask

echo ""
echo "✓ Deployment complete!"
echo ""
```

## What Makes This Different

❌ **OLD approach:** Creates new deploy.sh files, overwrites your existing ones  
✅ **NEW approach:** Uses existing deploy.sh from each branch, respects your files  

This means:
- You control deployment logic in GitHub
- Each branch can have different deployment steps
- Changes to deploy.sh are version controlled
- No manual script management on the Pi
