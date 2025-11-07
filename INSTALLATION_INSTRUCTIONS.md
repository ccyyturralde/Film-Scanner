# One-Line Installation for Film Scanner Multi-Branch Setup

## Quick Install (Copy-Paste on Your Raspberry Pi)

### Step 1: Download the setup script
```bash
cd ~ && wget https://raw.githubusercontent.com/YOUR-REPO/setup_branch_directories.sh && chmod +x setup_branch_directories.sh
```

**OR if you have the file locally, copy it to your Pi:**

### Using SCP (from your computer):
```bash
scp setup_branch_directories.sh pi@raspberrypi.local:~/
```

### Using the transfer script (Windows):
```powershell
# From your Film-Scanner directory
.\transfer_to_pi.ps1
```

## Step 2: Run the setup
```bash
cd ~
./setup_branch_directories.sh
```

That's it! The script will:
1. ✅ Remove old `film-scanner-versions` directory (with confirmation)
2. ✅ Create new directory structure
3. ✅ Clone all 4 branches from GitHub:
   - `main`
   - `web-mobile-version`
   - `Testing`
   - `feature/remote-camera-server`
4. ✅ Create deployment scripts for each branch
5. ✅ Create management utilities
6. ✅ Generate comprehensive documentation

## What You'll Have After Setup

```
~/film-scanner-versions/
├── main/                           # ← Terminal version
├── web-mobile-version/            # ← Web interface
├── Testing/                       # ← Test branch
├── feature-remote-camera-server/  # ← Canon WiFi + Smart features
├── deploy_all.sh                  # ← Deploy all at once
├── switch_branch.sh               # ← Interactive switcher
└── README.md                      # ← Auto-generated guide
```

## Quick Start After Setup

### Deploy all branches:
```bash
cd ~/film-scanner-versions
./deploy_all.sh
```

### Use the main (terminal) version:
```bash
cd ~/film-scanner-versions/main
python3 scanner_app_v3\ test.py
```

### Use the web version:
```bash
cd ~/film-scanner-versions/web-mobile-version
python3 web_app.py
# Then open browser: http://raspberrypi.local:5000
```

### Use the Canon WiFi version:
```bash
cd ~/film-scanner-versions/feature-remote-camera-server
./launch_scanner.sh
```

### Interactive branch switcher:
```bash
cd ~/film-scanner-versions
./switch_branch.sh
```

## Manual Transfer Methods

### Method 1: USB Drive
1. Copy `setup_branch_directories.sh` to USB drive
2. Insert USB into Raspberry Pi
3. Mount and copy:
```bash
sudo mount /dev/sda1 /mnt/usb
cp /mnt/usb/setup_branch_directories.sh ~/
chmod +x ~/setup_branch_directories.sh
./setup_branch_directories.sh
```

### Method 2: Direct Edit on Pi
1. SSH into your Pi
2. Create the file:
```bash
nano ~/setup_branch_directories.sh
```
3. Paste the script content
4. Save (Ctrl+X, Y, Enter)
5. Make executable and run:
```bash
chmod +x ~/setup_branch_directories.sh
./setup_branch_directories.sh
```

### Method 3: Git Clone This Helper Repo (if you create one)
```bash
git clone [your-helper-repo-url]
cd [helper-repo]
chmod +x setup_branch_directories.sh
./setup_branch_directories.sh
```

## Troubleshooting

### "Permission denied" when running script
```bash
chmod +x setup_branch_directories.sh
./setup_branch_directories.sh
```

### "Command not found: wget"
```bash
# Install wget first
sudo apt update && sudo apt install -y wget

# Then try the download again
```

### Git clone fails
Make sure your repository is public or you have SSH keys set up:
```bash
# Check if you can access the repo
git ls-remote https://github.com/ccyyturralde/Film-Scanner.git
```

### Not enough disk space
Check available space:
```bash
df -h
```

Each branch needs ~100-200MB. Total needed: ~500MB-1GB

### Already have film-scanner directory
The script will handle this! It only affects `~/film-scanner-versions/` directory.
Your existing `~/film-scanner/` or `~/Film-Scanner/` will not be touched.

## Verify Installation

After setup completes, verify:
```bash
# Check directories exist
ls -la ~/film-scanner-versions/

# Check git status in each branch
cd ~/film-scanner-versions/main && git status
cd ~/film-scanner-versions/web-mobile-version && git status
cd ~/film-scanner-versions/Testing && git status
cd ~/film-scanner-versions/feature-remote-camera-server && git status

# Check deployment scripts exist
find ~/film-scanner-versions -name "deploy.sh" -type f
```

Expected output: Should show 4 deploy.sh files (one per branch)

## Next Steps

1. Read the generated README:
```bash
cat ~/film-scanner-versions/README.md
```

2. Read the Quick Reference guide:
```bash
cat ~/film-scanner-versions/../MULTI_BRANCH_QUICK_REFERENCE.md
```

3. Deploy your preferred branch:
```bash
cd ~/film-scanner-versions/[branch-name]
./deploy.sh
```

4. Start scanning! 🎞️

## Need Help?

- **Script Issues:** Check the output messages - they're descriptive
- **Branch-Specific Help:** Check the README in each branch directory
- **General Questions:** See MULTI_BRANCH_QUICK_REFERENCE.md

## Advanced: Customize Before Running

If you want to customize the script before running:
```bash
nano setup_branch_directories.sh

# Modify these variables:
# - BASE_DIR (default: ~/film-scanner-versions)
# - GITHUB_USER (already set to: ccyyturralde)
# - REPO_NAME (already set to: Film-Scanner)
```

---

**Repository:** https://github.com/ccyyturralde/Film-Scanner  
**Branches:** main, web-mobile-version, Testing, feature/remote-camera-server  
**Setup Time:** ~5-10 minutes (depending on network speed)
