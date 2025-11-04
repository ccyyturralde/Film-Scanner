#!/bin/bash
# Film Scanner Launcher Script
# Easy way to launch either web or CLI version

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "   FILM SCANNER LAUNCHER"
echo "============================================================"
echo ""
echo "Which version would you like to run?"
echo ""
echo "  1. Web Application (Browser interface)"
echo "  2. CLI Application (Terminal interface)"
echo "  3. View Configuration"
echo "  4. Reset Configuration"
echo "  5. Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "Starting Web Application..."
        echo ""
        python3 web_app.py
        ;;
    2)
        echo ""
        echo "Starting CLI Application..."
        echo ""
        python3 "scanner_app_v3 test.py"
        ;;
    3)
        echo ""
        echo "=== WEB APP CONFIGURATION ==="
        python3 web_app.py --config
        echo ""
        echo "=== CLI APP CONFIGURATION ==="
        python3 "scanner_app_v3 test.py" --config
        echo ""
        read -p "Press ENTER to exit..."
        ;;
    4)
        echo ""
        read -p "Are you sure you want to reset configuration? (y/n): " confirm
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            python3 web_app.py --reset
            echo ""
            echo "✓ Configuration reset complete"
            echo "Next time you launch, setup will run automatically."
        else
            echo "Reset cancelled"
        fi
        echo ""
        read -p "Press ENTER to exit..."
        ;;
    5)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

