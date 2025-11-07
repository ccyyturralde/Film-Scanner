# Film Scanner - Multi-Branch Setup Quick Reference

## Your Four Branches

### 🎯 main
**Purpose:** Stable main version  
**Features:** Core scanning functionality, terminal interface  
**Best For:** Production use, reliable scanning  

### 🌐 web-mobile-version
**Purpose:** Web-based control  
**Features:** Browser interface, mobile support, remote access  
**Best For:** Controlling scanner from phone/tablet  

### 🧪 Testing
**Purpose:** Development and testing  
**Features:** Experimental features, may be unstable  
**Best For:** Testing new features before they reach main  

### 📡 feature/remote-camera-server
**Purpose:** Advanced Canon WiFi integration  
**Features:**
- Canon R100 WiFi support with 10 FPS live view
- Canon Camera Control API (CCAPI)
- Auto-discovery of Pi on network
- Smart startup configuration
- Web interface with WebSocket updates

**Best For:** Canon R100 users wanting WiFi live view  

## Directory Structure After Setup

```
~/film-scanner-versions/
├── main/                           # Stable version
│   ├── scanner_app_v3 test.py
│   ├── deploy.sh                  # Auto-generated
│   └── setup.sh                   # Original from repo
│
├── web-mobile-version/            # Web interface
│   ├── web_app.py
│   ├── deploy.sh                  # Auto-generated
│   ├── setup_pi.sh                # Original from repo
│   └── requirements.txt
│
├── Testing/                       # Test branch
│   ├── deploy.sh                  # Auto-generated
│   └── ...
│
├── feature-remote-camera-server/  # Canon WiFi
│   ├── web_app.py
│   ├── scanner_app_v3 test.py
│   ├── deploy.sh                  # Auto-generated
│   ├── setup.sh                   # Original from repo
│   ├── launch_scanner.sh          # Original from repo
│   └── CANON_WIFI_QUICKSTART.md
│
├── deploy_all.sh                  # Deploy all branches
├── switch_branch.sh               # Interactive switcher
└── README.md                      # This guide
```

## Quick Commands

### Initial Setup
```bash
# On your Raspberry Pi
cd ~
# Copy setup_branch_directories.sh to your Pi
chmod +x setup_branch_directories.sh
./setup_branch_directories.sh
```

### Deploy All Branches
```bash
cd ~/film-scanner-versions
./deploy_all.sh
```

### Deploy Specific Branch
```bash
cd ~/film-scanner-versions/main
./deploy.sh
```

### Interactive Branch Management
```bash
cd ~/film-scanner-versions
./switch_branch.sh
```

### Run a Specific Branch

**Main (Terminal):**
```bash
cd ~/film-scanner-versions/main
python3 scanner_app_v3\ test.py
```

**Web Version:**
```bash
cd ~/film-scanner-versions/web-mobile-version
python3 web_app.py
# Open browser to: http://raspberrypi.local:5000
```

**Canon WiFi Version:**
```bash
cd ~/film-scanner-versions/feature-remote-camera-server
./launch_scanner.sh  # Interactive launcher
# Or directly:
python3 web_app.py
```

### Update a Branch from GitHub
```bash
cd ~/film-scanner-versions/[branch-name]
git pull origin [branch-name]
```

## Deployment Scripts Explained

Each branch gets an auto-generated `deploy.sh` that:
1. Pulls latest changes from GitHub
2. Looks for branch-specific deployment scripts:
   - `setup_pi.sh` (web-mobile-version)
   - `setup.sh` (main, feature branches)
3. Installs Python dependencies from `requirements.txt`
4. Runs any setup scripts automatically

### Manual Deployment Steps

If you want to deploy manually:

**For main:**
```bash
cd ~/film-scanner-versions/main
git pull origin main
bash setup.sh  # If it exists
```

**For web-mobile-version:**
```bash
cd ~/film-scanner-versions/web-mobile-version
git pull origin web-mobile-version
bash setup_pi.sh
# Follow the on-screen prompts
```

**For feature/remote-camera-server:**
```bash
cd ~/film-scanner-versions/feature-remote-camera-server
git pull origin feature/remote-camera-server
bash setup.sh
# For Canon WiFi setup, see CANON_WIFI_QUICKSTART.md
```

## Switching Between Branches

### Method 1: Use Different Directories
Each branch is completely isolated - just `cd` into the one you want:
```bash
cd ~/film-scanner-versions/main
python3 scanner_app_v3\ test.py
```

### Method 2: Use the Interactive Switcher
```bash
cd ~/film-scanner-versions
./switch_branch.sh
# Follow the menu prompts
```

### Method 3: Create Aliases
Add to `~/.bashrc`:
```bash
alias scanner-main='cd ~/film-scanner-versions/main && python3 "scanner_app_v3 test.py"'
alias scanner-web='cd ~/film-scanner-versions/web-mobile-version && python3 web_app.py'
alias scanner-wifi='cd ~/film-scanner-versions/feature-remote-camera-server && ./launch_scanner.sh'
alias scanner-test='cd ~/film-scanner-versions/Testing && python3 scanner_app_v3\ test.py'
```

Then just run: `scanner-web`

## Which Branch Should I Use?

### Choose **main** if:
- You want the most stable, tested version
- You prefer terminal/SSH interface
- You don't need remote access
- You want minimal dependencies

### Choose **web-mobile-version** if:
- You want to control from your phone/tablet
- You prefer a visual web interface
- You want multiple people to view progress
- You're comfortable with web apps

### Choose **Testing** if:
- You want to test new features
- You're helping with development
- You're okay with potential bugs
- You want bleeding-edge updates

### Choose **feature/remote-camera-server** if:
- You have a Canon R100 (or compatible)
- You want WiFi live view at 10 FPS
- You want the best of web interface + Canon features
- You want auto-discovery of your Pi
- You need Smart Startup configuration

## Troubleshooting

### "Arduino not found"
Only one application can use the Arduino at a time. Check:
```bash
ps aux | grep scanner
ps aux | grep python
# Kill any running scanner processes
kill [PID]
```

### Port Permission Issues
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Web Version Not Accessible
```bash
# Find your Pi's IP
hostname -I

# Check if web server is running
ps aux | grep web_app

# Access from browser using IP
http://192.168.1.XXX:5000
```

### Branch-Specific Issues

**Canon WiFi (feature/remote-camera-server):**
- See `CANON_WIFI_QUICKSTART.md` in the branch directory
- Check camera is in Remote Control mode
- Verify Pi and camera on same network

**Web Version:**
- See `SETUP_README.md` in branch directory
- Check Flask dependencies installed
- Verify port 5000 not blocked by firewall

## Keeping Branches Updated

### Update All Branches
```bash
cd ~/film-scanner-versions

for dir in */; do
    if [ -d "$dir/.git" ]; then
        echo "Updating $dir..."
        cd "$dir"
        git pull
        cd ..
    fi
done
```

### Update Single Branch
```bash
cd ~/film-scanner-versions/main
git pull origin main
./deploy.sh  # Re-run deployment if needed
```

## Configuration Files

Each branch maintains its own configuration:

```
~/film-scanner-versions/
├── main/
│   └── scans/                    # Scan data
├── web-mobile-version/
│   ├── scans/                    # Separate scan data
│   └── .film_scanner/            # Config (if Smart Startup used)
└── feature-remote-camera-server/
    ├── scans/                    # Separate scan data
    └── .film_scanner/            # Config (Smart Startup)
```

**Note:** Scan data is NOT shared between branches by default.

To share scan data across branches, use symlinks:
```bash
mkdir -p ~/scans-shared
cd ~/film-scanner-versions/main
ln -s ~/scans-shared scans
cd ~/film-scanner-versions/web-mobile-version
ln -s ~/scans-shared scans
```

## Advanced: Custom Deployment

Each branch's `deploy.sh` can be customized. Example:

```bash
cd ~/film-scanner-versions/main
nano deploy.sh

# Add custom deployment steps:
# - Install additional packages
# - Run custom setup scripts
# - Configure environment variables
# - Set up systemd services
```

## Cleanup

To remove all branches and start fresh:
```bash
rm -rf ~/film-scanner-versions
# Then re-run setup_branch_directories.sh
```

To remove a specific branch:
```bash
rm -rf ~/film-scanner-versions/Testing
```

## Getting Help

- **Main Branch:** See `README.md` in main/
- **Web Version:** See `README_WEB_APP.md` and `SETUP_README.md`
- **Canon WiFi:** See `CANON_WIFI_QUICKSTART.md` and `CANON_R100_WIFI_SETUP.md`
- **Smart Startup:** See `SMART_STARTUP_README.md`

## Summary

✅ **Setup Once:** Run `setup_branch_directories.sh`  
✅ **Deploy All:** Run `deploy_all.sh`  
✅ **Use Any Branch:** Just `cd` into its directory  
✅ **Switch Easy:** Use `switch_branch.sh` or aliases  
✅ **Update Easy:** `git pull` in any branch directory  

---

**Created:** $(date)  
**Repository:** https://github.com/ccyyturralde/Film-Scanner  
**Branches:** 4 (main, web-mobile-version, Testing, feature/remote-camera-server)
