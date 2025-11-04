# Film Scanner - Multi-Version Setup Guide

This setup script clones all three branches of your Film-Scanner repository into separate directories. **Each directory uses its own deploy.sh and setup.sh files from that branch** - nothing gets overwritten.

## Repository Structure

**Repository:** https://github.com/ccyyturralde/Film-Scanner

**Branches:**
- `main` - Production/stable version
- `Testing` - Development/testing version  
- `web-mobile-version` - Web interface version

## What This Does

The setup script:
1. Clones each branch into its own directory
2. **Uses the deploy.sh and setup.sh files already in each branch**
3. Creates convenience wrapper scripts
4. **Does NOT create or overwrite any repository files**

This means:
- Each branch keeps its own deployment logic
- You manage deploy.sh and setup.sh in GitHub (version controlled)
- Updates to those scripts come from `git pull`, not from this setup script

## Quick Setup

**One-line setup command:**

```bash
bash <(curl -sL https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/main/setup_scanner_versions.sh)
```

Or download and run locally:

```bash
# Download the script
wget https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/main/setup_scanner_versions.sh

# Run it
bash setup_scanner_versions.sh
```

## Directory Structure

After setup, you'll have:

```
~/film-scanner-versions/
├── main/              # main branch - uses its own deploy.sh/setup.sh
│   ├── scanner_app_v2.py
│   ├── deploy.sh     # ← From main branch in GitHub
│   ├── setup.sh      # ← From main branch in GitHub
│   └── ...
│
├── testing/           # Testing branch - uses its own deploy.sh/setup.sh
│   ├── scanner_app_v2.py
│   ├── deploy.sh     # ← From Testing branch in GitHub
│   ├── setup.sh      # ← From Testing branch in GitHub
│   └── ...
│
├── web/               # web-mobile-version branch - uses its own deploy.sh/setup.sh
│   ├── scanner_web_app.py
│   ├── deploy.sh     # ← From web-mobile-version branch in GitHub
│   ├── setup.sh      # ← From web-mobile-version branch in GitHub
│   └── ...
│
├── deploy_all.sh      # Wrapper - calls each branch's deploy.sh
├── update_all.sh      # Git pull all branches
├── run_main.sh
├── run_testing.sh
└── run_web.sh
```

**Key Point:** The setup_scanner_versions.sh script should be **added to your main branch** on GitHub, so you can run it with curl.

## What to Add to Your GitHub Repository

### Step 1: Add setup_scanner_versions.sh to main branch

This is the master setup script that users will run first.

```bash
# In your local Film-Scanner repository
cd /path/to/Film-Scanner
git checkout main

# Copy the setup script (download from the outputs link)
cp /path/to/downloaded/setup_scanner_versions.sh .

# Commit and push
git add setup_scanner_versions.sh
git commit -m "Add multi-version setup script"
git push origin main
```

After this, users can run:
```bash
bash <(curl -sL https://raw.githubusercontent.com/ccyyturralde/Film-Scanner/main/setup_scanner_versions.sh)
```

### Step 2: Ensure each branch has its own deploy.sh

The setup script expects each branch to have its own deploy.sh file. Make sure they exist:

**Main branch:**
```bash
git checkout main
ls -la deploy.sh  # Should exist
git push origin main
```

**Testing branch:**
```bash
git checkout Testing
ls -la deploy.sh  # Should exist
git push origin Testing
```

**Web-mobile-version branch:**
```bash
git checkout web-mobile-version
ls -la deploy.sh  # Should exist
git push origin web-mobile-version
```

### Step 3: (Optional) Add this documentation

```bash
git checkout main
cp /path/to/MULTI_VERSION_SETUP.md .
git add MULTI_VERSION_SETUP.md
git commit -m "Add setup documentation"
git push origin main
```

## Usage

### Deploying (Updating from GitHub)

Deploy a specific version:
```bash
cd ~/film-scanner-versions/main
bash deploy.sh
```

Deploy all versions at once:
```bash
bash ~/film-scanner-versions/deploy_all.sh
```

### Running

Quick run scripts:
```bash
# Run main version
bash ~/film-scanner-versions/run_main.sh

# Run testing version
bash ~/film-scanner-versions/run_testing.sh

# Run web version
bash ~/film-scanner-versions/run_web.sh
```

Or run manually:
```bash
# Main version
cd ~/film-scanner-versions/main
python3 scanner_app_v2.py

# Testing version
cd ~/film-scanner-versions/testing
python3 scanner_app_v2.py

# Web version
cd ~/film-scanner-versions/web
python3 scanner_web_app.py  # or scanner_app_v2.py
```

## Version Details

### Main Version
- **Purpose**: Stable production use
- **Branch**: `main` (or `master`)
- **Updates**: Only stable releases
- **Use for**: Actual film scanning

### Testing Version
- **Purpose**: Development and testing
- **Branch**: `testing` or `main`
- **Updates**: Frequent, may be unstable
- **Use for**: Testing new features

### Web Version
- **Purpose**: Browser-based interface
- **Branch**: `web` or `main`
- **Updates**: Web-specific features
- **Use for**: Remote control via browser
- **Extra**: Includes Flask for web server

## Customization

### Current Configuration

The script is pre-configured for your repository:
- **Repository:** https://github.com/ccyyturralde/Film-Scanner.git
- **Main branch:** `main`
- **Testing branch:** `Testing`
- **Web branch:** `web-mobile-version`

### Changing Branch Names

If you rename branches in the future, edit `setup_scanner_versions.sh`:

```bash
GITHUB_BRANCH_MAIN="main"
GITHUB_BRANCH_TESTING="Testing"
GITHUB_BRANCH_WEB="web-mobile-version"
```

### Adding More Versions

To add another version (e.g., "experimental"):

```bash
cd ~/film-scanner-versions
git clone https://github.com/YOUR_USERNAME/film-scanner.git experimental
cd experimental

# Create deploy script
cat > deploy.sh << 'EOF'
#!/bin/bash
set -e
cd "$(dirname "$0")"
git pull
pip3 install --break-system-packages -r requirements.txt
echo "✓ Experimental version deployed!"
EOF

chmod +x deploy.sh
```

## GitHub Repository Setup

Your repository uses **one repository with multiple branches**:

```
https://github.com/ccyyturralde/Film-Scanner/
├── main branch              → Production code
├── Testing branch           → Development code
└── web-mobile-version branch → Web interface code
```

Each branch contains the appropriate version of your scanner app.

## Workflow Example

1. **Development**: Work in testing version
   ```bash
   cd ~/film-scanner-versions/testing
   # Make changes, test
   git add .
   git commit -m "Add new feature"
   git push origin Testing
   ```

2. **Deploy to other machines**: On your Pi
   ```bash
   cd ~/film-scanner-versions/testing
   bash deploy.sh
   ```

3. **Promote to production**: When stable
   ```bash
   # On GitHub: Create PR from Testing → main
   # Or via command line:
   git checkout main
   git merge Testing
   git push origin main
   
   # Deploy on Pi
   cd ~/film-scanner-versions/main
   bash deploy.sh
   ```

## Web Version Setup

If you want to create a web interface:

1. Install Flask in web version:
   ```bash
   cd ~/film-scanner-versions/web
   pip3 install --break-system-packages flask
   ```

2. Create `scanner_web_app.py` (basic example):
   ```python
   from flask import Flask, render_template, request
   app = Flask(__name__)
   
   @app.route('/')
   def index():
       return render_template('index.html')
   
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=5000)
   ```

3. Access from browser:
   ```
   http://raspberrypi.local:5000
   ```

## Troubleshooting

### GitHub authentication

If using private repository (currently this is public):
```bash
# Setup SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"
cat ~/.ssh/id_ed25519.pub  # Add to GitHub

# Or use personal access token
git clone https://YOUR_TOKEN@github.com/ccyyturralde/Film-Scanner.git
```

### Permission issues
```bash
chmod +x ~/film-scanner-versions/*/deploy.sh
chmod +x ~/film-scanner-versions/*.sh
```

### Python packages
```bash
# If pip install fails, try:
pip3 install --break-system-packages --user pyserial
```

## Tips

- **Version control**: Each directory is a separate git clone
- **Isolated testing**: Test in `testing/` without affecting `main/`
- **Easy rollback**: Keep `main/` stable, experiment in `testing/`
- **Remote access**: Use `web/` for browser-based control
- **Auto-update**: Create cron jobs to run deploy scripts

## Auto-Update with Cron

To automatically pull updates daily:

```bash
# Edit crontab
crontab -e

# Add line (runs at 3 AM daily)
0 3 * * * bash /home/pi/film-scanner-versions/deploy_all.sh >> /home/pi/deploy.log 2>&1
```
