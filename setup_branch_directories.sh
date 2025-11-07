#!/bin/bash
# Film Scanner - Branch Directory Setup Script
# Creates separate directories for each branch with deployment scripts

set -e

echo "═══════════════════════════════════════════════════════"
echo "  Film Scanner - Multi-Branch Directory Setup"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "This script will set up separate directories for each branch:"
echo ""
echo "  • main                        - Main/stable version"
echo "  • web-mobile-version          - Web interface with mobile support"
echo "  • Testing                     - Testing/development branch"
echo "  • feature/remote-camera-server - Canon WiFi + remote features"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
GITHUB_USER="ccyyturralde"
REPO_NAME="Film-Scanner"
BASE_DIR="$HOME/film-scanner-versions"

REPO_URL="https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo -e "${BLUE}Repository: ${REPO_URL}${NC}"
echo -e "${BLUE}Base Directory: ${BASE_DIR}${NC}"
echo ""

# Step 1: Remove existing film-scanner-versions directory
if [ -d "$BASE_DIR" ]; then
    echo -e "${YELLOW}⚠️  Existing film-scanner-versions directory found${NC}"
    echo -e "${YELLOW}This will DELETE all contents in: ${BASE_DIR}${NC}"
    echo ""
    read -p "Continue? (y/n): " -r confirm
    echo ""
    
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    
    echo -e "${BLUE}🗑️  Removing existing directory...${NC}"
    rm -rf "$BASE_DIR"
    echo -e "${GREEN}✓ Removed${NC}"
    echo ""
fi

# Step 2: Create base directory
echo -e "${BLUE}📁 Creating base directory...${NC}"
mkdir -p "$BASE_DIR"
cd "$BASE_DIR"
echo -e "${GREEN}✓ Created: ${BASE_DIR}${NC}"
echo ""

# Step 3: Clone repository to get branch list
echo -e "${BLUE}🔍 Fetching repository information...${NC}"
TEMP_CLONE="$BASE_DIR/.temp_repo"
git clone --bare "$REPO_URL" "$TEMP_CLONE" 2>/dev/null || {
    echo -e "${RED}❌ Failed to clone repository${NC}"
    echo "Please check:"
    echo "  - GitHub username is correct"
    echo "  - Repository name is correct: $REPO_NAME"
    echo "  - Repository is public or you have access"
    exit 1
}

# Get list of branches (excluding HEAD)
cd "$TEMP_CLONE"
BRANCHES=$(git branch -r | grep -v HEAD | sed 's/.*origin\///' | sort)
BRANCH_COUNT=$(echo "$BRANCHES" | wc -l)

echo -e "${GREEN}✓ Found ${BRANCH_COUNT} branches:${NC}"
echo "$BRANCHES" | sed 's/^/  - /'
echo ""

# Clean up temp clone
rm -rf "$TEMP_CLONE"

# Step 4: Clone each branch into its own directory
echo -e "${BLUE}📦 Setting up branch directories...${NC}"
echo ""

for branch in $BRANCHES; do
    # Sanitize branch name for directory (replace / with -)
    DIR_NAME=$(echo "$branch" | tr '/' '-')
    BRANCH_DIR="$BASE_DIR/$DIR_NAME"
    
    echo -e "${BLUE}Setting up branch: ${branch}${NC}"
    echo "  Directory: $BRANCH_DIR"
    
    # Clone the specific branch
    git clone --single-branch --branch "$branch" "$REPO_URL" "$BRANCH_DIR"
    
    cd "$BRANCH_DIR"
    
    # Create deployment script for this branch
    cat > deploy.sh << EOF
#!/bin/bash
# Deployment script for branch: $branch
# Generated automatically by setup_branch_directories.sh

set -e

echo "═══════════════════════════════════════════════════════"
echo "  Deploying Film Scanner - Branch: $branch"
echo "═══════════════════════════════════════════════════════"
echo ""

# Update from GitHub
echo "📥 Pulling latest changes from $branch..."
git pull origin $branch

# Check if setup_pi.sh exists
if [ -f "setup_pi.sh" ]; then
    echo ""
    echo "🔧 Found setup_pi.sh - Running setup..."
    chmod +x setup_pi.sh
    ./setup_pi.sh
elif [ -f "requirements.txt" ]; then
    echo ""
    echo "📦 Installing Python dependencies..."
    pip3 install -r requirements.txt
fi

# Check for specific deployment instructions
if [ -f "DEPLOY.md" ] || [ -f "DEPLOYMENT.md" ]; then
    echo ""
    echo "📖 Deployment documentation found. Please review:"
    echo "  - DEPLOY.md or DEPLOYMENT.md"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✓ Deployment Complete!"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Branch: $branch"
echo "Directory: $BRANCH_DIR"
echo ""
EOF

    chmod +x deploy.sh
    
    echo -e "${GREEN}  ✓ Created deploy.sh${NC}"
    echo ""
done

# Step 5: Create master deployment script
echo -e "${BLUE}📝 Creating master deployment script...${NC}"

cat > "$BASE_DIR/deploy_all.sh" << 'EOF'
#!/bin/bash
# Master deployment script - deploys all branches

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "═══════════════════════════════════════════════════════"
echo "  Film Scanner - Deploy All Branches"
echo "═══════════════════════════════════════════════════════"
echo ""

for dir in */; do
    if [ -f "${dir}deploy.sh" ]; then
        echo "Deploying: $dir"
        cd "$dir"
        ./deploy.sh
        cd "$SCRIPT_DIR"
        echo ""
    fi
done

echo "✓ All branches deployed!"
EOF

chmod +x "$BASE_DIR/deploy_all.sh"
echo -e "${GREEN}✓ Created deploy_all.sh${NC}"
echo ""

# Step 6: Create branch switcher script
echo -e "${BLUE}📝 Creating branch switcher script...${NC}"

cat > "$BASE_DIR/switch_branch.sh" << 'EOF'
#!/bin/bash
# Interactive branch switcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Film Scanner - Branch Switcher"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Available branches:"
echo ""

i=1
declare -a dirs
for dir in */; do
    if [ -d "$dir" ] && [ "$dir" != ".temp_repo/" ]; then
        echo "  $i. ${dir%/}"
        dirs[$i]="$dir"
        ((i++))
    fi
done

echo ""
read -p "Select branch (1-$((i-1))): " choice

if [ -n "${dirs[$choice]}" ]; then
    selected="${dirs[$choice]}"
    echo ""
    echo "Selected: ${selected%/}"
    echo ""
    echo "Actions:"
    echo "  1. Open directory in terminal"
    echo "  2. Deploy/Update this branch"
    echo "  3. Show branch info"
    echo "  4. Cancel"
    echo ""
    read -p "Choose action (1-4): " action
    
    case $action in
        1)
            cd "$selected"
            echo ""
            echo "Now in: $(pwd)"
            echo "Type 'exit' to return to previous directory"
            bash
            ;;
        2)
            cd "$selected"
            if [ -f "deploy.sh" ]; then
                ./deploy.sh
            else
                echo "No deploy.sh found"
            fi
            ;;
        3)
            cd "$selected"
            echo ""
            echo "Branch: $(git branch --show-current)"
            echo "Last commit: $(git log -1 --oneline)"
            echo "Status: $(git status -s | wc -l) changed files"
            echo ""
            ;;
        4)
            echo "Cancelled"
            ;;
    esac
else
    echo "Invalid selection"
fi
EOF

chmod +x "$BASE_DIR/switch_branch.sh"
echo -e "${GREEN}✓ Created switch_branch.sh${NC}"
echo ""

# Step 7: Create README
cat > "$BASE_DIR/README.md" << EOF
# Film Scanner - Multi-Branch Setup

This directory contains separate installations of each branch of the film-scanner repository.

## Directory Structure

\`\`\`
film-scanner-versions/
$(for branch in $BRANCHES; do
    DIR_NAME=$(echo "$branch" | tr '/' '-')
    echo "├── $DIR_NAME/          # Branch: $branch"
done)
├── deploy_all.sh       # Deploy all branches
├── switch_branch.sh    # Interactive branch switcher
└── README.md          # This file
\`\`\`

## Branch Directories

Each branch has its own isolated directory with a deployment script.

### main
**Branch:** main  
**Description:** Stable main version with core scanning features  
**Deploy:**
\`\`\`bash
cd ~/film-scanner-versions/main
./deploy.sh
\`\`\`

### web-mobile-version
**Branch:** web-mobile-version  
**Description:** Web interface with mobile browser support for remote control  
**Deploy:**
\`\`\`bash
cd ~/film-scanner-versions/web-mobile-version
./deploy.sh
\`\`\`

### Testing
**Branch:** Testing  
**Description:** Testing and development branch with experimental features  
**Deploy:**
\`\`\`bash
cd ~/film-scanner-versions/Testing
./deploy.sh
\`\`\`

### feature-remote-camera-server
**Branch:** feature/remote-camera-server  
**Description:** Canon R100 WiFi support with 10 FPS live view + Smart Startup  
**Special Features:**
- Canon Camera Control API (CCAPI) WiFi integration
- 10 FPS live view via Canon WiFi
- Auto-discover Pi IP on network
- Web interface with real-time updates

**Deploy:**
\`\`\`bash
cd ~/film-scanner-versions/feature-remote-camera-server
./deploy.sh
\`\`\`


## Quick Commands

### Deploy All Branches
\`\`\`bash
cd ~/film-scanner-versions
./deploy_all.sh
\`\`\`

### Deploy Specific Branch
\`\`\`bash
cd ~/film-scanner-versions/[branch-name]
./deploy.sh
\`\`\`

### Interactive Branch Switcher
\`\`\`bash
cd ~/film-scanner-versions
./switch_branch.sh
\`\`\`

### Update a Branch
\`\`\`bash
cd ~/film-scanner-versions/[branch-name]
git pull
\`\`\`

### Switch Between Branches
\`\`\`bash
# Enter a branch directory
cd ~/film-scanner-versions/[branch-name]

# Run the application
python3 web_app.py  # or other main script
\`\`\`

## Branch Information

Created: $(date)
Repository: $REPO_URL
Total Branches: $BRANCH_COUNT

---
Generated by setup_branch_directories.sh
EOF

echo -e "${GREEN}✓ Created README.md${NC}"
echo ""

# Final summary
echo "═══════════════════════════════════════════════════════"
echo -e "${GREEN}✓ Setup Complete!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "📍 Base directory: $BASE_DIR"
echo "📦 Branches installed: $BRANCH_COUNT"
echo ""
echo "Next steps:"
echo ""
echo "1. Deploy all branches:"
echo "   cd $BASE_DIR"
echo "   ./deploy_all.sh"
echo ""
echo "2. Or deploy a specific branch:"
echo "   cd $BASE_DIR/[branch-name]"
echo "   ./deploy.sh"
echo ""
echo "3. Use the interactive switcher:"
echo "   cd $BASE_DIR"
echo "   ./switch_branch.sh"
echo ""
echo "4. Read the README:"
echo "   cat $BASE_DIR/README.md"
echo ""
echo "═══════════════════════════════════════════════════════"
