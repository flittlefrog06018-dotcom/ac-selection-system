#!/usr/bin/env bash
# exit on error
set -o errexit

echo "=== Step 1: Installing Python Backend Dependencies ==="
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "=== Step 2: Building Frontend Single Page App ==="
cd frontend
npm install
npm run build
cd ..

echo "=== Step 3: Copying Frontend Assets to Backend Static Directory ==="
mkdir -p backend/static
cp -r frontend/dist/* backend/static/

echo "=== Build Completed Successfully! ==="
