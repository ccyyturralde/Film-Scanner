#!/bin/bash
# Film Scanner - Health Check & Auto-Repair
# Quick wrapper script for health_check.py
#
# Usage:
#   ./scripts/health_check.sh          # Full check and repair
#   ./scripts/health_check.sh --check  # Check only, don't fix
#   ./scripts/health_check.sh --help   # Show help

set -e

# Find the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Run the health check
exec python3 "$PROJECT_DIR/health_check.py" "$@"

