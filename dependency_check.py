#!/usr/bin/env python3
"""
Film Scanner - Dependency/Library Check
Verifies all required dependencies are installed and up-to-date.
Installs missing packages and updates outdated ones.

Usage:
    python3 dependency_check.py           # Check and fix all dependencies
    python3 dependency_check.py --check   # Check only, don't install
    python3 dependency_check.py --quiet   # Minimal output
"""

import subprocess
import sys
import os
import re
import shutil
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# Configuration
# ============================================================================

# Python packages required (package_name: minimum_version or None)
PYTHON_PACKAGES = {
    # Web Application
    "flask": "2.3.0",
    "flask-socketio": "5.3.0",
    "python-socketio": "5.9.0",
    
    # Hardware Communication
    "pyserial": "3.5",
    
    # Image Processing
    "pillow": "10.0.0",
    "opencv-python-headless": "4.8.0",
    "numpy": "1.24.0",
    
    # Touch Screen UI
    "pygame": "2.5.0",
    
    # System monitoring (for touchscreen stats)
    "psutil": "5.9.0",
}

# System packages required (Debian/Ubuntu apt packages)
SYSTEM_PACKAGES = [
    "python3-pip",
    "python3-serial",
    "python3-pygame",
    "git",
    "gphoto2",
    "screen",
    "curl",
    "libsdl2-dev",
    "libsdl2-image-dev",
    "libsdl2-ttf-dev",
    "libfreetype6-dev",
]

# Optional packages (nice to have but not required)
OPTIONAL_PYTHON_PACKAGES = {
    "psutil": "5.9.0",  # System stats monitoring
}


# ============================================================================
# Status Types
# ============================================================================

class Status(Enum):
    OK = "ok"
    MISSING = "missing"
    OUTDATED = "outdated"
    ERROR = "error"


@dataclass
class PackageStatus:
    name: str
    status: Status
    installed_version: Optional[str] = None
    required_version: Optional[str] = None
    message: str = ""


# ============================================================================
# Colors for Terminal Output
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color
    
    @classmethod
    def disable(cls):
        """Disable colors (for non-TTY output)."""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.CYAN = cls.BOLD = cls.NC = ''


# Disable colors if not a terminal
if not sys.stdout.isatty():
    Colors.disable()


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BLUE}{'=' * 50}{Colors.NC}")
    print(f"{Colors.BLUE}{Colors.BOLD}  {text}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 50}{Colors.NC}\n")


def print_status(name: str, status: Status, details: str = ""):
    """Print a status line with appropriate coloring."""
    if status == Status.OK:
        icon = f"{Colors.GREEN}✓{Colors.NC}"
        color = Colors.GREEN
    elif status == Status.MISSING:
        icon = f"{Colors.RED}✗{Colors.NC}"
        color = Colors.RED
    elif status == Status.OUTDATED:
        icon = f"{Colors.YELLOW}↑{Colors.NC}"
        color = Colors.YELLOW
    else:
        icon = f"{Colors.RED}?{Colors.NC}"
        color = Colors.RED
    
    detail_str = f" ({details})" if details else ""
    print(f"  {icon} {color}{name}{Colors.NC}{detail_str}")


# ============================================================================
# Version Comparison
# ============================================================================

def parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a version string into a tuple of integers."""
    if not version_str:
        return (0,)
    # Extract numeric parts only
    parts = re.findall(r'\d+', version_str)
    return tuple(int(p) for p in parts) if parts else (0,)


def version_compare(installed: str, required: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if installed < required, 0 if equal, 1 if installed > required
    """
    installed_parts = parse_version(installed)
    required_parts = parse_version(required)
    
    # Pad to equal length
    max_len = max(len(installed_parts), len(required_parts))
    installed_parts = installed_parts + (0,) * (max_len - len(installed_parts))
    required_parts = required_parts + (0,) * (max_len - len(required_parts))
    
    if installed_parts < required_parts:
        return -1
    elif installed_parts > required_parts:
        return 1
    return 0


# ============================================================================
# Python Package Management
# ============================================================================

def get_installed_python_packages() -> Dict[str, str]:
    """Get a dictionary of installed Python packages and their versions."""
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
                    # Normalize package name (pip uses lowercase with hyphens)
                    packages[name.lower().replace('_', '-')] = version
    except Exception as e:
        print(f"{Colors.RED}Error getting installed packages: {e}{Colors.NC}")
    return packages


def check_python_package(name: str, required_version: Optional[str], 
                         installed_packages: Dict[str, str]) -> PackageStatus:
    """Check if a Python package is installed and meets version requirements."""
    # Normalize package name
    normalized_name = name.lower().replace('_', '-')
    
    if normalized_name not in installed_packages:
        return PackageStatus(
            name=name,
            status=Status.MISSING,
            required_version=required_version,
            message="Not installed"
        )
    
    installed_version = installed_packages[normalized_name]
    
    if required_version:
        comparison = version_compare(installed_version, required_version)
        if comparison < 0:
            return PackageStatus(
                name=name,
                status=Status.OUTDATED,
                installed_version=installed_version,
                required_version=required_version,
                message=f"{installed_version} < {required_version}"
            )
    
    return PackageStatus(
        name=name,
        status=Status.OK,
        installed_version=installed_version,
        required_version=required_version,
        message=installed_version
    )


def install_python_package(name: str, version: Optional[str] = None, 
                           upgrade: bool = False) -> bool:
    """Install or upgrade a Python package."""
    try:
        cmd = [sys.executable, "-m", "pip", "install"]
        
        # Add --break-system-packages for newer pip on Debian/Ubuntu
        cmd.append("--break-system-packages")
        
        if upgrade:
            cmd.append("--upgrade")
        
        if version:
            cmd.append(f"{name}>={version}")
        else:
            cmd.append(name)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}  Timeout installing {name}{Colors.NC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}  Error installing {name}: {e}{Colors.NC}")
        return False


# ============================================================================
# System Package Management
# ============================================================================

def is_system_package_installed(package: str) -> bool:
    """Check if a system package is installed (Debian/Ubuntu)."""
    try:
        result = subprocess.run(
            ["dpkg", "-s", package],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except:
        return False


def install_system_packages(packages: List[str]) -> bool:
    """Install system packages using apt."""
    if not packages:
        return True
    
    try:
        # Update package list
        print(f"  {Colors.CYAN}Updating package list...{Colors.NC}")
        subprocess.run(["sudo", "apt", "update"], 
                      capture_output=True, timeout=120)
        
        # Install packages
        cmd = ["sudo", "apt", "install", "-y"] + packages
        result = subprocess.run(cmd, timeout=600)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"{Colors.RED}  Timeout installing system packages{Colors.NC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}  Error installing system packages: {e}{Colors.NC}")
        return False


# ============================================================================
# Hardware/Pi-Specific Checks
# ============================================================================

def check_raspberry_pi() -> Tuple[bool, str]:
    """Check if running on a Raspberry Pi."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
            return True, model
    except:
        return False, "Not a Raspberry Pi"


def check_gphoto2() -> PackageStatus:
    """Check if gphoto2 is installed and working."""
    if shutil.which("gphoto2"):
        try:
            result = subprocess.run(
                ["gphoto2", "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                # Extract version from output
                version_match = re.search(r'gphoto2\s+([\d.]+)', result.stdout)
                version = version_match.group(1) if version_match else "installed"
                return PackageStatus("gphoto2", Status.OK, version, message=version)
        except:
            pass
    return PackageStatus("gphoto2", Status.MISSING, message="Not installed")


def check_arduino_cli() -> PackageStatus:
    """Check if Arduino CLI is installed."""
    if shutil.which("arduino-cli"):
        try:
            result = subprocess.run(
                ["arduino-cli", "version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                version_match = re.search(r'Version:\s*([\d.]+)', result.stdout)
                version = version_match.group(1) if version_match else "installed"
                return PackageStatus("arduino-cli", Status.OK, version, message=version)
        except:
            pass
    return PackageStatus("arduino-cli", Status.MISSING, message="Not installed (optional)")


def check_serial_permissions() -> PackageStatus:
    """Check if user has serial port permissions."""
    import grp
    import pwd
    
    try:
        username = pwd.getpwuid(os.getuid()).pw_name
        groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        # Also check primary group
        primary_gid = pwd.getpwuid(os.getuid()).pw_gid
        primary_group = grp.getgrgid(primary_gid).gr_name
        groups.append(primary_group)
        
        if 'dialout' in groups:
            return PackageStatus("dialout group", Status.OK, message="User in dialout group")
        else:
            return PackageStatus("dialout group", Status.MISSING, 
                               message="User not in dialout group")
    except Exception as e:
        return PackageStatus("dialout group", Status.ERROR, message=str(e))


# ============================================================================
# Main Check Functions
# ============================================================================

def check_all_dependencies(quiet: bool = False) -> Tuple[List[PackageStatus], List[PackageStatus], List[PackageStatus]]:
    """
    Check all dependencies.
    Returns: (python_results, system_results, tool_results)
    """
    python_results = []
    system_results = []
    tool_results = []
    
    # Check Python packages
    if not quiet:
        print_header("Python Packages")
    
    installed_packages = get_installed_python_packages()
    
    for package, version in PYTHON_PACKAGES.items():
        status = check_python_package(package, version, installed_packages)
        python_results.append(status)
        if not quiet:
            print_status(package, status.status, status.message)
    
    # Check system packages
    if not quiet:
        print_header("System Packages")
    
    for package in SYSTEM_PACKAGES:
        if is_system_package_installed(package):
            status = PackageStatus(package, Status.OK, message="Installed")
        else:
            status = PackageStatus(package, Status.MISSING, message="Not installed")
        system_results.append(status)
        if not quiet:
            print_status(package, status.status, status.message)
    
    # Check tools and permissions
    if not quiet:
        print_header("Tools & Permissions")
    
    tool_results.append(check_gphoto2())
    tool_results.append(check_arduino_cli())
    tool_results.append(check_serial_permissions())
    
    if not quiet:
        for result in tool_results:
            print_status(result.name, result.status, result.message)
    
    return python_results, system_results, tool_results


def fix_dependencies(python_results: List[PackageStatus], 
                     system_results: List[PackageStatus],
                     quiet: bool = False) -> Tuple[int, int]:
    """
    Install missing and update outdated dependencies.
    Returns: (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0
    
    # Fix Python packages
    python_to_fix = [p for p in python_results if p.status in [Status.MISSING, Status.OUTDATED]]
    
    if python_to_fix:
        if not quiet:
            print_header("Installing/Updating Python Packages")
        
        for pkg in python_to_fix:
            if not quiet:
                action = "Updating" if pkg.status == Status.OUTDATED else "Installing"
                print(f"  {Colors.CYAN}{action} {pkg.name}...{Colors.NC}")
            
            upgrade = pkg.status == Status.OUTDATED
            if install_python_package(pkg.name, pkg.required_version, upgrade):
                if not quiet:
                    print(f"    {Colors.GREEN}✓ Success{Colors.NC}")
                success_count += 1
            else:
                if not quiet:
                    print(f"    {Colors.RED}✗ Failed{Colors.NC}")
                failure_count += 1
    
    # Fix system packages
    system_to_fix = [p.name for p in system_results if p.status == Status.MISSING]
    
    if system_to_fix:
        if not quiet:
            print_header("Installing System Packages")
            print(f"  {Colors.CYAN}Packages: {', '.join(system_to_fix)}{Colors.NC}")
        
        if install_system_packages(system_to_fix):
            if not quiet:
                print(f"  {Colors.GREEN}✓ System packages installed{Colors.NC}")
            success_count += len(system_to_fix)
        else:
            if not quiet:
                print(f"  {Colors.RED}✗ Some packages failed to install{Colors.NC}")
            failure_count += len(system_to_fix)
    
    return success_count, failure_count


def print_summary(python_results: List[PackageStatus],
                  system_results: List[PackageStatus],
                  tool_results: List[PackageStatus]):
    """Print a summary of the dependency check."""
    print_header("Summary")
    
    all_results = python_results + system_results + tool_results
    
    ok_count = sum(1 for r in all_results if r.status == Status.OK)
    missing_count = sum(1 for r in all_results if r.status == Status.MISSING)
    outdated_count = sum(1 for r in all_results if r.status == Status.OUTDATED)
    
    total = len(all_results)
    
    print(f"  Total packages checked: {total}")
    print(f"  {Colors.GREEN}✓ OK:{Colors.NC} {ok_count}")
    
    if missing_count > 0:
        print(f"  {Colors.RED}✗ Missing:{Colors.NC} {missing_count}")
    if outdated_count > 0:
        print(f"  {Colors.YELLOW}↑ Outdated:{Colors.NC} {outdated_count}")
    
    if missing_count == 0 and outdated_count == 0:
        print(f"\n  {Colors.GREEN}{Colors.BOLD}All dependencies are satisfied!{Colors.NC}")
        return True
    else:
        print(f"\n  {Colors.YELLOW}Some dependencies need attention.{Colors.NC}")
        return False


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for dependency check."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Film Scanner - Dependency/Library Check',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 dependency_check.py           # Check and fix all dependencies
  python3 dependency_check.py --check   # Check only, don't install
  python3 dependency_check.py --quiet   # Minimal output
        """
    )
    parser.add_argument('--check', action='store_true',
                       help='Check only, do not install/update')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Minimal output')
    
    args = parser.parse_args()
    
    # Header
    if not args.quiet:
        print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 50}{Colors.NC}")
        print(f"{Colors.BLUE}{Colors.BOLD}  Film Scanner - Dependency Check{Colors.NC}")
        print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 50}{Colors.NC}")
        
        # Check if on Raspberry Pi
        is_pi, pi_model = check_raspberry_pi()
        if is_pi:
            print(f"\n  {Colors.GREEN}✓ Running on: {pi_model}{Colors.NC}")
        else:
            print(f"\n  {Colors.YELLOW}ℹ Not running on Raspberry Pi{Colors.NC}")
    
    # Run checks
    python_results, system_results, tool_results = check_all_dependencies(args.quiet)
    
    # Count issues
    all_results = python_results + system_results
    issues = sum(1 for r in all_results if r.status in [Status.MISSING, Status.OUTDATED])
    
    if issues > 0 and not args.check:
        # Fix issues
        success, failures = fix_dependencies(python_results, system_results, args.quiet)
        
        # Re-check after fixes
        if not args.quiet:
            print_header("Re-checking Dependencies")
        python_results, system_results, tool_results = check_all_dependencies(args.quiet)
    
    # Print summary
    if not args.quiet:
        all_ok = print_summary(python_results, system_results, tool_results)
        
        # Check serial permissions
        serial_status = next((r for r in tool_results if r.name == "dialout group"), None)
        if serial_status and serial_status.status == Status.MISSING:
            print(f"\n  {Colors.YELLOW}⚠ To fix serial permissions, run:{Colors.NC}")
            print(f"    sudo usermod -a -G dialout $USER")
            print(f"    {Colors.CYAN}(Then log out and log back in){Colors.NC}")
    
    # Exit code
    final_issues = sum(1 for r in python_results + system_results 
                       if r.status in [Status.MISSING, Status.OUTDATED])
    sys.exit(0 if final_issues == 0 else 1)


if __name__ == '__main__':
    main()
