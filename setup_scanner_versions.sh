#!/bin/bash
# Film Scanner - Multi-Version Setup Script
# Clones all three branches and uses their existing deploy.sh files
# Does NOT overwrite any files - uses what's in each branch

set -e

# Configuration - Your Film Scanner Repository
GITHUB_REPO="https://github.com/ccyyturralde/Film-Scanner.git"
GITHUB_BRANCH_MAIN="main"
GITHUB_BRANCH_TESTING="Testing"
GITHUB_BRANCH_WEB="web-mobile-version"
BASE_DIR="$HOME/film-scanner-versions"

echo "==========================================="
echo "Film Scanner - Multi-Version Setup"
echo "==========================================="
echo ""
echo "Repository: $GITHUB_REPO"
echo ""
echo "This will create three directories:"
echo "  📁 $BASE_DIR/main          (branch: $GITHUB_BRANCH_MAIN)"
echo "  📁 $BASE_DIR/testing       (branch: $GITHUB_BRANCH_TESTING)"
echo "  📁 $BASE_DIR/web           (branch: $GITHUB_BRANCH_WEB)"
echo ""
echo "Each directory will use its own deploy.sh and setup.sh"
echo "from the respective branch. No files will be overwritten."
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Create base directory
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"

#===========================================
# MAIN VERSION
#===========================================
echo ""
echo "========================================="
echo "Setting up MAIN version..."
echo "========================================="
if [ ! -d "main" ]; then
    echo "  Cloning '$GITHUB_BRANCH_MAIN' branch..."
    git clone -b "$GITHUB_BRANCH_MAIN" "$GITHUB_REPO" main
    echo "  ✓ Cloned main branch"
else
    echo "  Directory exists, pulling latest..."
    cd main && git pull && cd ..
    echo "  ✓ Updated main"
fi

# Check what scripts exist in main branch
echo ""
echo "Files in main branch:"
if [ -f "main/deploy.sh" ]; then
    chmod +x main/deploy.sh
    echo "  ✓ deploy.sh (from repository)"
else
    echo "  ✗ No deploy.sh found"
fi

if [ -f "main/setup.sh" ]; then
    chmod +x main/setup.sh
    echo "  ✓ setup.sh (from repository)"
else
    echo "  ✗ No setup.sh found"
fi

#===========================================
# TESTING VERSION
#===========================================
echo ""
echo "========================================="
echo "Setting up TESTING version..."
echo "========================================="
if [ ! -d "testing" ]; then
    echo "  Cloning '$GITHUB_BRANCH_TESTING' branch..."
    git clone -b "$GITHUB_BRANCH_TESTING" "$GITHUB_REPO" testing
    echo "  ✓ Cloned Testing branch"
else
    echo "  Directory exists, pulling latest..."
    cd testing && git pull && cd ..
    echo "  ✓ Updated testing"
fi

# Check what scripts exist in testing branch
echo ""
echo "Files in testing branch:"
if [ -f "testing/deploy.sh" ]; then
    chmod +x testing/deploy.sh
    echo "  ✓ deploy.sh (from repository)"
else
    echo "  ✗ No deploy.sh found"
fi

if [ -f "testing/setup.sh" ]; then
    chmod +x testing/setup.sh
    echo "  ✓ setup.sh (from repository)"
else
    echo "  ✗ No setup.sh found"
fi

#===========================================
# WEB VERSION
#===========================================
echo ""
echo "========================================="
echo "Setting up WEB version..."
echo "========================================="
if [ ! -d "web" ]; then
    echo "  Cloning '$GITHUB_BRANCH_WEB' branch..."
    git clone -b "$GITHUB_BRANCH_WEB" "$GITHUB_REPO" web
    echo "  ✓ Cloned web-mobile-version branch"
else
    echo "  Directory exists, pulling latest..."
    cd web && git pull && cd ..
    echo "  ✓ Updated web"
fi

# Check what scripts exist in web branch
echo ""
echo "Files in web branch:"
if [ -f "web/deploy.sh" ]; then
    chmod +x web/deploy.sh
    echo "  ✓ deploy.sh (from repository)"
else
    echo "  ✗ No deploy.sh found"
fi

if [ -f "web/setup.sh" ]; then
    chmod +x web/setup.sh
    echo "  ✓ setup.sh (from repository)"
else
    echo "  ✗ No setup.sh found"
fi

#===========================================
# Create wrapper scripts for convenience
#===========================================
echo ""
echo "========================================="
echo "Creating convenience scripts..."
echo "========================================="

# Deploy all versions at once
cat > "$BASE_DIR/deploy_all.sh" << 'EOF'
#!/bin/bash
# Deploy ALL versions at once

set -e
BASE_DIR="$HOME/film-scanner-versions"

echo "==========================================="
echo "Deploying ALL Scanner Versions"
echo "==========================================="
echo ""

# Deploy main
if [ -f "$BASE_DIR/main/deploy.sh" ]; then
    echo "1/3 - MAIN VERSION"
    cd "$BASE_DIR/main" && bash deploy.sh
    echo ""
else
    echo "1/3 - MAIN VERSION: No deploy.sh found"
    echo ""
fi

# Deploy testing
if [ -f "$BASE_DIR/testing/deploy.sh" ]; then
    echo "2/3 - TESTING VERSION"
    cd "$BASE_DIR/testing" && bash deploy.sh
    echo ""
else
    echo "2/3 - TESTING VERSION: No deploy.sh found"
    echo ""
fi

# Deploy web
if [ -f "$BASE_DIR/web/deploy.sh" ]; then
    echo "3/3 - WEB VERSION"
    cd "$BASE_DIR/web" && bash deploy.sh
    echo ""
else
    echo "3/3 - WEB VERSION: No deploy.sh found"
    echo ""
fi

echo "==========================================="
echo "✓ All versions processed!"
echo "==========================================="
EOF

chmod +x "$BASE_DIR/deploy_all.sh"
echo "  ✓ Created deploy_all.sh"

# Update all from git
cat > "$BASE_DIR/update_all.sh" << 'EOF'
#!/bin/bash
# Pull latest changes from GitHub for all versions

set -e
BASE_DIR="$HOME/film-scanner-versions"

echo "==========================================="
echo "Updating ALL Versions from GitHub"
echo "==========================================="
echo ""

echo "1/3 - Updating MAIN..."
cd "$BASE_DIR/main" && git pull
echo ""

echo "2/3 - Updating TESTING..."
cd "$BASE_DIR/testing" && git pull
echo ""

echo "3/3 - Updating WEB..."
cd "$BASE_DIR/web" && git pull
echo ""

echo "==========================================="
echo "✓ All versions updated!"
echo "==========================================="
EOF

chmod +x "$BASE_DIR/update_all.sh"
echo "  ✓ Created update_all.sh"

# Quick run scripts
cat > "$BASE_DIR/run_main.sh" << 'EOF'
#!/bin/bash
cd "$HOME/film-scanner-versions/main"
python3 scanner_app_v2.py
EOF
chmod +x "$BASE_DIR/run_main.sh"
echo "  ✓ Created run_main.sh"

cat > "$BASE_DIR/run_testing.sh" << 'EOF'
#!/bin/bash
cd "$HOME/film-scanner-versions/testing"
python3 scanner_app_v2.py
EOF
chmod +x "$BASE_DIR/run_testing.sh"
echo "  ✓ Created run_testing.sh"

cat > "$BASE_DIR/run_web.sh" << 'EOF'
#!/bin/bash
cd "$HOME/film-scanner-versions/web"
# Try to find the web app file
if [ -f "scanner_web_app.py" ]; then
    python3 scanner_web_app.py
elif [ -f "web_app.py" ]; then
    python3 web_app.py
elif [ -f "app.py" ]; then
    python3 app.py
else
    python3 scanner_app_v2.py
fi
EOF
chmod +x "$BASE_DIR/run_web.sh"
echo "  ✓ Created run_web.sh"

#===========================================
# Summary
#===========================================
echo ""
echo "==========================================="
echo "✓ Setup Complete!"
echo "==========================================="
echo ""
echo "Directory structure:"
echo "  $BASE_DIR/"
echo "  ├── main/           ($GITHUB_BRANCH_MAIN branch)"
echo "  ├── testing/        ($GITHUB_BRANCH_TESTING branch)"
echo "  ├── web/            ($GITHUB_BRANCH_WEB branch)"
echo "  ├── deploy_all.sh   (Deploy all versions)"
echo "  ├── update_all.sh   (Pull from GitHub)"
echo "  ├── run_main.sh"
echo "  ├── run_testing.sh"
echo "  └── run_web.sh"
echo ""
echo "Repository: $GITHUB_REPO"
echo "Branches:"
echo "  • Main:    $GITHUB_BRANCH_MAIN"
echo "  • Testing: $GITHUB_BRANCH_TESTING"
echo "  • Web:     $GITHUB_BRANCH_WEB"
echo ""
echo "Usage:"
echo ""
echo "Deploy a specific version (uses its own deploy.sh):"
echo "  cd $BASE_DIR/main && bash deploy.sh"
echo "  cd $BASE_DIR/testing && bash deploy.sh"
echo "  cd $BASE_DIR/web && bash deploy.sh"
echo ""
echo "Deploy all versions at once:"
echo "  bash $BASE_DIR/deploy_all.sh"
echo ""
echo "Update from GitHub:"
echo "  bash $BASE_DIR/update_all.sh"
echo ""
echo "Quick run:"
echo "  bash $BASE_DIR/run_main.sh"
echo "  bash $BASE_DIR/run_testing.sh"
echo "  bash $BASE_DIR/run_web.sh"
echo ""
echo "Each branch uses its own deploy.sh and setup.sh files."
echo "No repository files were overwritten."
echo ""
