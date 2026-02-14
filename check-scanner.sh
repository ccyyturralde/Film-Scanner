#!/bin/bash
# Quick network check for scanner Pi - run in Terminal: bash check-scanner.sh
PI=192.168.86.41
echo "=== Ping $PI ==="
ping -c 2 $PI 2>&1
echo ""
echo "=== Port 22 (SSH) ==="
nc -zv -w 3 $PI 22 2>&1
echo ""
echo "=== Port 5000 (app) ==="
nc -zv -w 3 $PI 5000 2>&1
echo ""
echo "=== Route to $PI ==="
route -n get $PI 2>&1 | head -15
echo ""
echo "=== SSH attempt ==="
ssh -o ConnectTimeout=5 -o BatchMode=yes scanner@$PI exit 2>&1
