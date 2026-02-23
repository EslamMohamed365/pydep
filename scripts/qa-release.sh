#!/bin/bash
# QA Verification Script for PyDep Release
set -e

echo "========================================="
echo "PyDep Release QA Verification"
echo "========================================="

ERRORS=0

echo -n "Checking standalone binary... "
[ -x "dist/pydep" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking Debian package... "
[ -f "dist/pydep_0.1.0_amd64.deb" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking RPM package... "
[ -f "dist/pydep-0.1.0-1.x86_64.rpm" ] || [ -f "dist/pydep-0.1.0-1.x86_64.tar.gz" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking Arch package... "
[ -f "dist/pydep-0.1.0-1-x86_64.pkg.tar.zst" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking build scripts... "
[ -x "scripts/build-deb.sh" ] && [ -x "scripts/build-rpm.sh" ] && [ -x "scripts/build-arch.sh" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking GitHub workflow... "
[ -f ".github/workflows/release.yml" ] && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo -n "Checking README docs... "
grep -q "Debian/Ubuntu" README.md && grep -q "Fedora" README.md && grep -q "Arch Linux" README.md && echo "✓ PASS" || { echo "✗ FAIL"; ERRORS=$((ERRORS+1)); }

echo "========================================="
[ $ERRORS -eq 0 ] && echo "✓ All checks passed!" || echo "✗ $ERRORS checks failed!"
exit $ERRORS
