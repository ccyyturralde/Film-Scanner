#!/usr/bin/env python3
"""
Film Scanner - Health Check & Auto-Repair Utility
==================================================
Compares local installation against GitHub repository and fixes any issues.

Features:
  • Checks all files against GitHub (identifies missing, outdated, extra files)
  • Verifies and installs dependencies
  • Fixes permissions
  • Removes deprecated files
  • Updates systemd services
  • Restarts services after repair

Usage:
  python3 health_check.py              # Full check and repair
  python3 health_check.py --check      # Check only, don't fix
  python3 health_check.py --verbose    # Show detailed output
  python3 health_check.py --force      # Force update even if up-to-date
"""

import subprocess
import sys
import os
import re
import json
import hashlib
import shutil
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


# ============================================================================
# Configuration
# ============================================================================

GITHUB_REPO = "ccyyturralde/Film-Scanner"
GITHUB_BRANCH = "main"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO}"

# Files that should be removed if they exist (deprecated)
DEPRECATED_FILES = [
    "touchscreen_launcher.py",
    "touchscreen_terminal.py",
    "touchscreen_debug.py",
    "touchscreen_settings.py",
    "scanner_app.py",
    "scanner_app_improved.py",
    "update.sh",
    "deploy.sh",
    "quick_deploy.sh",
]

# Files to ignore when comparing (local-only files)
IGNORE_FILES = [
    ".git",
    "__pycache__",
    "*.pyc",
    ".scan_state.json",
    "scanner_config.json",
    ".film_scanner",
    "scans",
    "*.backup",
    "*.old",
    "*.log",
    "main_web_app_temp.py",
    "web_app_old.py",
    "web_app_preview_testui.py",
]

# Core files that MUST exist
CORE_FILES = [
    "web_app.py",
    "touchscreen_ui.py",
    "touchscreen_config.py",
    "touchscreen_common.py",
    "app_manager.py",
    "config_manager.py",
    "dependency_check.py",
    "sprocket_detector.py",
    "framebuffer_display.py",
    "requirements.txt",
    "README.md",
    "arduino/film_scanner/film_scanner.ino",
    "templates/index.html",
    "static/css/style.css",
    "static/js/app.js",
]

# Python packages required
PYTHON_PACKAGES = {
    "flask": "2.3.0",
    "flask-socketio": "5.3.0",
    "python-socketio": "5.9.0",
    "pyserial": "3.5",
    "pillow": "10.0.0",
    "opencv-python-headless": "4.8.0",
    "numpy": "1.24.0",
    "pygame": "2.5.0",
    "psutil": "5.9.0",
}

# System packages required
SYSTEM_PACKAGES = [
    "python3-pip",
    "git",
    "gphoto2",
    "screen",
    "curl",
]

# Packages that should NOT be installed (cause conflicts)
BANNED_PACKAGES = ["eventlet"]


# ============================================================================
# Status Types
# ============================================================================

class Status(Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    EXTRA = "extra"
    ERROR = "error"
    FIXED = "fixed"
    SKIPPED = "skipped"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Issue:
    category: str
    item: str
    status: Status
    severity: Severity
    message: str
    fix_action: str = ""
    fixed: bool = False


@dataclass
class HealthReport:
    timestamp: datetime = field(default_factory=datetime.now)
    is_raspberry_pi: bool = False
    pi_model: str = ""
    git_status: str = ""
    local_commit: str = ""
    remote_commit: str = ""
    issues: List[Issue] = field(default_factory=list)
    
    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == Severity.CRITICAL and not i.fixed for i in self.issues)
    
    @property
    def has_errors(self) -> bool:
        return any(i.severity == Severity.ERROR and not i.fixed for i in self.issues)
    
    @property
    def total_issues(self) -> int:
        return len([i for i in self.issues if not i.fixed])
    
    @property
    def fixed_count(self) -> int:
        return len([i for i in self.issues if i.fixed])


# ============================================================================
# Terminal Colors
# ============================================================================

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    NC = '\033[0m'
    
    # Status icons
    CHECK = '✓'
    CROSS = '✗'
    WARN = '⚠'
    INFO = 'ℹ'
    ARROW = '→'
    GEAR = '⚙'
    WRENCH = '🔧'
    
    @classmethod
    def disable(cls):
        for attr in ['RED', 'GREEN', 'YELLOW', 'BLUE', 'CYAN', 'MAGENTA', 'BOLD', 'DIM', 'NC']:
            setattr(cls, attr, '')


if not sys.stdout.isatty():
    Colors.disable()


def print_banner():
    """Print the application banner."""
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║  {Colors.BOLD}Film Scanner - Health Check & Auto-Repair{Colors.NC}{Colors.CYAN}                  ║
║  {Colors.DIM}Checks installation against GitHub and fixes issues{Colors.NC}{Colors.CYAN}         ║
╚══════════════════════════════════════════════════════════════╝{Colors.NC}
""")


def print_section(title: str):
    """Print a section header."""
    print(f"\n{Colors.BLUE}{'─' * 60}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}  {title}{Colors.NC}")
    print(f"{Colors.BLUE}{'─' * 60}{Colors.NC}\n")


def print_status(icon: str, color: str, message: str, detail: str = ""):
    """Print a status line."""
    detail_str = f" {Colors.DIM}({detail}){Colors.NC}" if detail else ""
    print(f"  {color}{icon}{Colors.NC} {message}{detail_str}")


def print_ok(message: str, detail: str = ""):
    print_status(Colors.CHECK, Colors.GREEN, message, detail)


def print_error(message: str, detail: str = ""):
    print_status(Colors.CROSS, Colors.RED, message, detail)


def print_warn(message: str, detail: str = ""):
    print_status(Colors.WARN, Colors.YELLOW, message, detail)


def print_info(message: str, detail: str = ""):
    print_status(Colors.INFO, Colors.CYAN, message, detail)


def print_action(message: str):
    print(f"  {Colors.MAGENTA}{Colors.GEAR}{Colors.NC} {Colors.DIM}{message}{Colors.NC}")


# ============================================================================
# System Detection
# ============================================================================

def detect_raspberry_pi() -> Tuple[bool, str]:
    """Detect if running on Raspberry Pi."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip().rstrip('\x00')
            return True, model
    except:
        return False, ""


def get_scanner_directory() -> Optional[Path]:
    """Find the Film Scanner installation directory."""
    # Check common locations
    candidates = [
        Path.cwd(),
        Path.home() / "Film-Scanner",
        Path.home() / "film-scanner",
        Path("/home/pi/Film-Scanner"),
    ]
    
    for path in candidates:
        if (path / "web_app.py").exists() or (path / ".git").exists():
            return path
    
    return None


# ============================================================================
# Git Operations
# ============================================================================

def run_git_command(args: List[str], cwd: Path = None) -> Tuple[bool, str]:
    """Run a git command and return success status and output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def get_local_commit(cwd: Path) -> str:
    """Get the current local commit hash."""
    success, output = run_git_command(["rev-parse", "HEAD"], cwd)
    return output[:8] if success else ""


def get_remote_commit() -> str:
    """Get the latest commit hash from GitHub."""
    try:
        url = f"{GITHUB_API_BASE}/commits/{GITHUB_BRANCH}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Film-Scanner-Health-Check'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get('sha', '')[:8]
    except:
        return ""


def get_git_status(cwd: Path) -> str:
    """Get git status summary."""
    success, output = run_git_command(["status", "--porcelain"], cwd)
    if not success:
        return "error"
    if not output:
        return "clean"
    
    modified = len([l for l in output.split('\n') if l.startswith(' M') or l.startswith('M ')])
    untracked = len([l for l in output.split('\n') if l.startswith('??')])
    
    parts = []
    if modified:
        parts.append(f"{modified} modified")
    if untracked:
        parts.append(f"{untracked} untracked")
    return ", ".join(parts) if parts else "clean"


def fetch_and_pull(cwd: Path) -> Tuple[bool, str]:
    """Fetch and pull latest changes from GitHub."""
    # Fetch
    success, _ = run_git_command(["fetch", "origin", GITHUB_BRANCH], cwd)
    if not success:
        return False, "Failed to fetch from origin"
    
    # Check for local changes
    status_success, status = run_git_command(["status", "--porcelain"], cwd)
    if status:
        # Stash local changes
        run_git_command(["stash"], cwd)
    
    # Pull
    success, output = run_git_command(["pull", "origin", GITHUB_BRANCH], cwd)
    if not success:
        # Try reset if pull fails
        run_git_command(["reset", "--hard", f"origin/{GITHUB_BRANCH}"], cwd)
        return True, "Reset to origin (local changes discarded)"
    
    return True, output


def get_github_file_list() -> Set[str]:
    """Get list of files from GitHub repository."""
    files = set()
    try:
        url = f"{GITHUB_API_BASE}/git/trees/{GITHUB_BRANCH}?recursive=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Film-Scanner-Health-Check'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            for item in data.get('tree', []):
                if item['type'] == 'blob':
                    files.add(item['path'])
    except Exception as e:
        print_warn(f"Could not fetch file list from GitHub: {e}")
    return files


# ============================================================================
# File Comparison
# ============================================================================

def should_ignore_file(filepath: str) -> bool:
    """Check if a file should be ignored in comparisons."""
    for pattern in IGNORE_FILES:
        if pattern.startswith('*'):
            if filepath.endswith(pattern[1:]):
                return True
        elif pattern in filepath or filepath == pattern:
            return True
    return False


def get_local_files(cwd: Path) -> Set[str]:
    """Get set of local files (relative paths)."""
    files = set()
    for root, dirs, filenames in os.walk(cwd):
        # Skip hidden and ignored directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'scans', '.film_scanner']]
        
        for filename in filenames:
            if filename.startswith('.'):
                continue
            filepath = os.path.relpath(os.path.join(root, filename), cwd)
            if not should_ignore_file(filepath):
                files.add(filepath)
    return files


def compare_file_with_github(filepath: str, local_path: Path) -> Tuple[bool, str]:
    """Compare a local file with the GitHub version."""
    try:
        url = f"{GITHUB_RAW_BASE}/{filepath}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Film-Scanner-Health-Check'})
        with urllib.request.urlopen(req, timeout=10) as response:
            remote_content = response.read()
        
        with open(local_path / filepath, 'rb') as f:
            local_content = f.read()
        
        if hashlib.md5(remote_content).hexdigest() == hashlib.md5(local_content).hexdigest():
            return True, "matches"
        else:
            return False, "differs"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return True, "not on GitHub"
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


# ============================================================================
# Dependency Checks
# ============================================================================

def get_installed_python_packages() -> Dict[str, str]:
    """Get dictionary of installed Python packages."""
    packages = {}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=freeze"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if '==' in line:
                    name, version = line.split('==', 1)
                    packages[name.lower().replace('_', '-')] = version
    except:
        pass
    return packages


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse version string into tuple of integers."""
    parts = re.findall(r'\d+', version_str or "0")
    return tuple(int(p) for p in parts) if parts else (0,)


def check_python_package(name: str, required: str, installed: Dict[str, str]) -> Issue:
    """Check if a Python package meets requirements."""
    normalized = name.lower().replace('_', '-')
    
    if normalized not in installed:
        return Issue(
            category="Python Package",
            item=name,
            status=Status.MISSING,
            severity=Severity.ERROR,
            message=f"Package not installed",
            fix_action=f"pip3 install {name}>={required}"
        )
    
    installed_ver = installed[normalized]
    if parse_version(installed_ver) < parse_version(required):
        return Issue(
            category="Python Package",
            item=name,
            status=Status.OUTDATED,
            severity=Severity.WARNING,
            message=f"Version {installed_ver} < {required}",
            fix_action=f"pip3 install --upgrade {name}>={required}"
        )
    
    return Issue(
        category="Python Package",
        item=name,
        status=Status.OK,
        severity=Severity.INFO,
        message=f"Version {installed_ver}"
    )


def check_system_package(name: str) -> Issue:
    """Check if a system package is installed."""
    try:
        result = subprocess.run(
            ["dpkg", "-s", name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return Issue(
                category="System Package",
                item=name,
                status=Status.OK,
                severity=Severity.INFO,
                message="Installed"
            )
    except:
        pass
    
    return Issue(
        category="System Package",
        item=name,
        status=Status.MISSING,
        severity=Severity.WARNING,
        message="Not installed",
        fix_action=f"sudo apt install -y {name}"
    )


def check_banned_packages(installed: Dict[str, str]) -> List[Issue]:
    """Check for packages that should not be installed."""
    issues = []
    for pkg in BANNED_PACKAGES:
        if pkg.lower() in installed:
            issues.append(Issue(
                category="Banned Package",
                item=pkg,
                status=Status.EXTRA,
                severity=Severity.ERROR,
                message="Should be uninstalled (causes conflicts)",
                fix_action=f"pip3 uninstall -y {pkg}"
            ))
    return issues


def check_serial_permissions() -> Issue:
    """Check if user has serial port permissions."""
    try:
        import grp
        import pwd
        
        username = pwd.getpwuid(os.getuid()).pw_name
        groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        primary_gid = pwd.getpwuid(os.getuid()).pw_gid
        groups.append(grp.getgrgid(primary_gid).gr_name)
        
        if 'dialout' in groups:
            return Issue(
                category="Permissions",
                item="Serial (dialout)",
                status=Status.OK,
                severity=Severity.INFO,
                message="User in dialout group"
            )
        else:
            return Issue(
                category="Permissions",
                item="Serial (dialout)",
                status=Status.MISSING,
                severity=Severity.WARNING,
                message="User not in dialout group",
                fix_action=f"sudo usermod -a -G dialout $USER"
            )
    except Exception as e:
        return Issue(
            category="Permissions",
            item="Serial (dialout)",
            status=Status.ERROR,
            severity=Severity.WARNING,
            message=str(e)
        )


def check_gphoto2() -> Issue:
    """Check if gphoto2 is available."""
    if shutil.which("gphoto2"):
        try:
            result = subprocess.run(
                ["gphoto2", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                match = re.search(r'gphoto2\s+([\d.]+)', result.stdout)
                version = match.group(1) if match else "installed"
                return Issue(
                    category="Tool",
                    item="gphoto2",
                    status=Status.OK,
                    severity=Severity.INFO,
                    message=f"Version {version}"
                )
        except:
            pass
    
    return Issue(
        category="Tool",
        item="gphoto2",
        status=Status.MISSING,
        severity=Severity.ERROR,
        message="Not installed",
        fix_action="sudo apt install -y gphoto2"
    )


# ============================================================================
# Service Checks
# ============================================================================

def check_systemd_service(name: str) -> Issue:
    """Check systemd service status."""
    try:
        # Check if service exists
        result = subprocess.run(
            ["systemctl", "cat", name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return Issue(
                category="Service",
                item=name,
                status=Status.MISSING,
                severity=Severity.INFO,
                message="Service not installed"
            )
        
        # Check if enabled
        enabled = subprocess.run(
            ["systemctl", "is-enabled", name],
            capture_output=True, text=True, timeout=10
        ).returncode == 0
        
        # Check if active
        active = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=10
        ).returncode == 0
        
        status_parts = []
        if enabled:
            status_parts.append("enabled")
        if active:
            status_parts.append("running")
        
        return Issue(
            category="Service",
            item=name,
            status=Status.OK if (enabled or active) else Status.ERROR,
            severity=Severity.INFO,
            message=", ".join(status_parts) if status_parts else "stopped/disabled"
        )
    except Exception as e:
        return Issue(
            category="Service",
            item=name,
            status=Status.ERROR,
            severity=Severity.WARNING,
            message=str(e)
        )


# ============================================================================
# Fix Functions
# ============================================================================

def fix_python_package(issue: Issue) -> bool:
    """Install or upgrade a Python package."""
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--break-system-packages"]
        if issue.status == Status.OUTDATED:
            cmd.append("--upgrade")
        
        # Extract package spec from fix_action
        match = re.search(r'pip3? install.*?(\S+>=[\d.]+)', issue.fix_action)
        if match:
            cmd.append(match.group(1))
        else:
            cmd.append(issue.item)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except:
        return False


def fix_banned_package(issue: Issue) -> bool:
    """Uninstall a banned package."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "--break-system-packages", issue.item],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0
    except:
        return False


def fix_deprecated_files(cwd: Path) -> List[str]:
    """Remove deprecated files."""
    removed = []
    for filename in DEPRECATED_FILES:
        filepath = cwd / filename
        if filepath.exists():
            try:
                filepath.unlink()
                removed.append(filename)
            except:
                pass
    return removed


def fix_serial_permissions() -> bool:
    """Add user to dialout group."""
    try:
        username = os.environ.get('USER', os.environ.get('LOGNAME', ''))
        if username:
            result = subprocess.run(
                ["sudo", "usermod", "-a", "-G", "dialout", username],
                capture_output=True, timeout=30
            )
            return result.returncode == 0
    except:
        pass
    return False


def restart_services() -> Dict[str, bool]:
    """Restart Film Scanner services."""
    results = {}
    services = ["film-scanner-touchscreen", "film-scanner-web"]
    
    for service in services:
        try:
            # Check if service exists
            check = subprocess.run(
                ["systemctl", "cat", service],
                capture_output=True, timeout=10
            )
            if check.returncode != 0:
                continue
            
            # Restart
            result = subprocess.run(
                ["sudo", "systemctl", "restart", service],
                capture_output=True, timeout=30
            )
            results[service] = result.returncode == 0
        except:
            results[service] = False
    
    return results


# ============================================================================
# Main Health Check
# ============================================================================

def run_health_check(scanner_dir: Path, verbose: bool = False) -> HealthReport:
    """Run complete health check and return report."""
    report = HealthReport()
    
    # Detect system
    report.is_raspberry_pi, report.pi_model = detect_raspberry_pi()
    
    # Git status
    print_section("Git Repository Status")
    
    report.local_commit = get_local_commit(scanner_dir)
    report.remote_commit = get_remote_commit()
    report.git_status = get_git_status(scanner_dir)
    
    if report.local_commit:
        print_info(f"Local commit: {report.local_commit}")
    else:
        print_error("Could not get local commit")
    
    if report.remote_commit:
        print_info(f"Remote commit: {report.remote_commit}")
        
        if report.local_commit == report.remote_commit:
            print_ok("Repository is up to date")
        else:
            print_warn("Repository is behind GitHub")
            report.issues.append(Issue(
                category="Git",
                item="Repository",
                status=Status.OUTDATED,
                severity=Severity.WARNING,
                message=f"Local {report.local_commit} != Remote {report.remote_commit}",
                fix_action="git pull"
            ))
    else:
        print_warn("Could not check remote commit")
    
    if report.git_status != "clean":
        print_warn(f"Working directory: {report.git_status}")
    
    # Check core files
    print_section("Core Files")
    
    for filepath in CORE_FILES:
        full_path = scanner_dir / filepath
        if full_path.exists():
            if verbose:
                print_ok(filepath)
        else:
            print_error(filepath, "missing")
            report.issues.append(Issue(
                category="Core File",
                item=filepath,
                status=Status.MISSING,
                severity=Severity.CRITICAL,
                message="Required file missing",
                fix_action="git pull"
            ))
    
    if not any(i.category == "Core File" for i in report.issues):
        print_ok(f"All {len(CORE_FILES)} core files present")
    
    # Check deprecated files
    print_section("Deprecated Files")
    
    deprecated_found = []
    for filename in DEPRECATED_FILES:
        if (scanner_dir / filename).exists():
            deprecated_found.append(filename)
            print_warn(filename, "should be removed")
            report.issues.append(Issue(
                category="Deprecated File",
                item=filename,
                status=Status.EXTRA,
                severity=Severity.WARNING,
                message="Old file that should be removed",
                fix_action="rm"
            ))
    
    if not deprecated_found:
        print_ok("No deprecated files found")
    
    # Check Python packages
    print_section("Python Dependencies")
    
    installed_packages = get_installed_python_packages()
    
    for pkg, version in PYTHON_PACKAGES.items():
        issue = check_python_package(pkg, version, installed_packages)
        if issue.status == Status.OK:
            if verbose:
                print_ok(pkg, issue.message)
        elif issue.status == Status.OUTDATED:
            print_warn(pkg, issue.message)
            report.issues.append(issue)
        else:
            print_error(pkg, issue.message)
            report.issues.append(issue)
    
    # Check banned packages
    for issue in check_banned_packages(installed_packages):
        print_error(issue.item, issue.message)
        report.issues.append(issue)
    
    if not any(i.category in ["Python Package", "Banned Package"] and i.status != Status.OK for i in report.issues):
        print_ok(f"All {len(PYTHON_PACKAGES)} Python packages OK")
    
    # Check system packages
    print_section("System Dependencies")
    
    for pkg in SYSTEM_PACKAGES:
        issue = check_system_package(pkg)
        if issue.status == Status.OK:
            if verbose:
                print_ok(pkg)
        else:
            print_warn(pkg, issue.message)
            report.issues.append(issue)
    
    if not any(i.category == "System Package" and i.status != Status.OK for i in report.issues):
        print_ok(f"All {len(SYSTEM_PACKAGES)} system packages OK")
    
    # Check tools
    print_section("Tools & Permissions")
    
    gphoto_issue = check_gphoto2()
    if gphoto_issue.status == Status.OK:
        print_ok("gphoto2", gphoto_issue.message)
    else:
        print_error("gphoto2", gphoto_issue.message)
        report.issues.append(gphoto_issue)
    
    serial_issue = check_serial_permissions()
    if serial_issue.status == Status.OK:
        print_ok("Serial permissions", serial_issue.message)
    else:
        print_warn("Serial permissions", serial_issue.message)
        report.issues.append(serial_issue)
    
    # Check services (Pi only)
    if report.is_raspberry_pi:
        print_section("Systemd Services")
        
        for service in ["film-scanner-touchscreen", "film-scanner-web"]:
            issue = check_systemd_service(service)
            if issue.status == Status.OK:
                print_ok(service, issue.message)
            elif issue.status == Status.MISSING:
                print_info(service, issue.message)
            else:
                print_warn(service, issue.message)
    
    return report


def fix_issues(report: HealthReport, scanner_dir: Path) -> int:
    """Fix all issues in the report."""
    if not report.issues:
        return 0
    
    print_section(f"Fixing {len(report.issues)} Issues")
    
    fixed_count = 0
    
    # Fix git first (pull latest code)
    git_issues = [i for i in report.issues if i.category == "Git" or i.category == "Core File"]
    if git_issues:
        print_action("Pulling latest code from GitHub...")
        success, message = fetch_and_pull(scanner_dir)
        if success:
            print_ok("Repository updated")
            for issue in git_issues:
                issue.fixed = True
                fixed_count += 1
        else:
            print_error(f"Git pull failed: {message}")
    
    # Remove deprecated files
    deprecated_issues = [i for i in report.issues if i.category == "Deprecated File"]
    if deprecated_issues:
        print_action("Removing deprecated files...")
        removed = fix_deprecated_files(scanner_dir)
        for issue in deprecated_issues:
            if issue.item in removed:
                print_ok(f"Removed {issue.item}")
                issue.fixed = True
                fixed_count += 1
    
    # Uninstall banned packages
    banned_issues = [i for i in report.issues if i.category == "Banned Package"]
    for issue in banned_issues:
        print_action(f"Uninstalling {issue.item}...")
        if fix_banned_package(issue):
            print_ok(f"Uninstalled {issue.item}")
            issue.fixed = True
            fixed_count += 1
        else:
            print_error(f"Failed to uninstall {issue.item}")
    
    # Install/upgrade Python packages
    python_issues = [i for i in report.issues if i.category == "Python Package"]
    for issue in python_issues:
        action = "Upgrading" if issue.status == Status.OUTDATED else "Installing"
        print_action(f"{action} {issue.item}...")
        if fix_python_package(issue):
            print_ok(f"{action.replace('ing', 'ed')} {issue.item}")
            issue.fixed = True
            fixed_count += 1
        else:
            print_error(f"Failed to {action.lower()} {issue.item}")
    
    # Fix serial permissions
    serial_issues = [i for i in report.issues if i.category == "Permissions" and i.status == Status.MISSING]
    for issue in serial_issues:
        print_action("Adding user to dialout group...")
        if fix_serial_permissions():
            print_ok("Added to dialout group (logout required)")
            issue.fixed = True
            fixed_count += 1
        else:
            print_warn("Could not add to dialout group")
    
    # Restart services if we fixed anything
    if fixed_count > 0 and report.is_raspberry_pi:
        print_action("Restarting services...")
        results = restart_services()
        for service, success in results.items():
            if success:
                print_ok(f"Restarted {service}")
            else:
                print_warn(f"Could not restart {service}")
    
    return fixed_count


def print_summary(report: HealthReport):
    """Print final summary."""
    print_section("Summary")
    
    if report.is_raspberry_pi:
        print_info(f"System: {report.pi_model}")
    else:
        print_info("System: Not a Raspberry Pi")
    
    total = len(report.issues)
    fixed = report.fixed_count
    remaining = total - fixed
    
    print()
    if total == 0:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ Installation is healthy!{Colors.NC}")
        print(f"  {Colors.DIM}All checks passed. No issues found.{Colors.NC}")
    elif remaining == 0:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ All {fixed} issues fixed!{Colors.NC}")
        print(f"  {Colors.DIM}Installation is now healthy.{Colors.NC}")
    else:
        print(f"  {Colors.YELLOW}Issues found: {total}{Colors.NC}")
        if fixed > 0:
            print(f"  {Colors.GREEN}Issues fixed: {fixed}{Colors.NC}")
        print(f"  {Colors.RED}Remaining: {remaining}{Colors.NC}")
        
        # Show remaining issues
        remaining_issues = [i for i in report.issues if not i.fixed]
        if remaining_issues:
            print()
            print(f"  {Colors.YELLOW}Manual fixes needed:{Colors.NC}")
            for issue in remaining_issues:
                print(f"    • {issue.item}: {issue.message}")
                if issue.fix_action:
                    print(f"      {Colors.DIM}{issue.fix_action}{Colors.NC}")
    
    # Special notes
    serial_fixed = any(i.category == "Permissions" and i.fixed for i in report.issues)
    if serial_fixed:
        print()
        print(f"  {Colors.YELLOW}⚠ Log out and back in for serial permissions to take effect{Colors.NC}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Film Scanner - Health Check & Auto-Repair',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--check', '-c', action='store_true',
                       help='Check only, do not fix issues')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed output')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Force update even if up-to-date')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Find scanner directory
    scanner_dir = get_scanner_directory()
    if not scanner_dir:
        print_error("Could not find Film Scanner installation!")
        print_info("Run this script from the Film-Scanner directory")
        sys.exit(1)
    
    print_info(f"Installation directory: {scanner_dir}")
    
    # Run health check
    report = run_health_check(scanner_dir, args.verbose)
    
    # Fix issues if not check-only
    if report.issues and not args.check:
        fix_issues(report, scanner_dir)
    elif args.check and report.issues:
        print()
        print(f"  {Colors.YELLOW}Run without --check to fix issues automatically{Colors.NC}")
    
    # Print summary
    print_summary(report)
    
    # Exit code
    remaining = report.total_issues - report.fixed_count
    sys.exit(0 if remaining == 0 else 1)


if __name__ == '__main__':
    main()

