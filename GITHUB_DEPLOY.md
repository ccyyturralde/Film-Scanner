# How to Deploy to GitHub

## Step 1: Create GitHub Repository

1. Go to https://github.com
2. Click "New repository"
3. Name it: `film-scanner`
4. Make it Public (for open source)
5. Do NOT initialize with README (we already have one)
6. Click "Create repository"

## Step 2: Push Code to GitHub

From your local machine (or Pi):

```bash
cd ~/film-scanner

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - 35mm film scanner"

# Add GitHub remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/film-scanner.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Step 3: Update Deploy Script

Edit `deploy.sh` and change this line:
```bash
REPO_URL="https://github.com/YOUR_USERNAME/film-scanner.git"
```

To your actual GitHub username.

Commit and push:
```bash
git add deploy.sh
git commit -m "Update deploy script with repo URL"
git push
```

## Step 4: Test Deployment on Raspberry Pi

On your Pi:

```bash
# One-command deploy
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/film-scanner/main/deploy.sh | bash
```

This will:
- Clone your repo
- Install dependencies
- Flash Arduino
- Set up everything

## Step 5: Daily Workflow

### On Your Dev Machine

Make changes, test, then:
```bash
git add .
git commit -m "Description of changes"
git push
```

### On Your Raspberry Pi

Pull and update:
```bash
cd ~/film-scanner
./update.sh
```

Or manually:
```bash
cd ~/film-scanner
git pull
python3 scanner_app.py
```

## Updating Just the Arduino

If you only changed Arduino code:

```bash
cd ~/film-scanner
arduino-cli compile --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno Arduino_Film_Scanner/Arduino_Film_Scanner.ino
```

## GitHub Actions (Optional Advanced)

You could set up GitHub Actions to:
- Auto-test code on push
- Build releases
- Create installers

But for now, the simple push/pull workflow is perfect.

## Branches (Optional)

For development:
```bash
# Create dev branch
git checkout -b dev

# Make changes
# ...

# Push dev branch
git push -u origin dev

# When ready, merge to main
git checkout main
git merge dev
git push
```

## Tags/Releases

When you have a stable version:
```bash
git tag -a v1.0.0 -m "First stable release"
git push origin v1.0.0
```

Then create a Release on GitHub with release notes.

## Sharing Your Project

Once on GitHub, others can install with:
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/film-scanner/main/deploy.sh | bash
```

## Security Note

Never commit:
- Passwords
- API keys
- Personal data
- Scan outputs

The `.gitignore` already excludes these.
