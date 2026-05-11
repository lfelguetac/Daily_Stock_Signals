#!/bin/bash
set -e

echo "Building Lambda packages..."

for func in extract transform analyze load notify; do
  echo "Packaging $func..."
  cd functions/$func

  if [ -f requirements.txt ]; then
    pip install -r requirements.txt -t . --upgrade --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.12 --implementation cp 2>/dev/null
  fi

  zip -r ../../infra/$func.zip . -x "*.pyc" "__pycache__/*" "*.zip" 2>/dev/null
  cd ../..
done

echo "Build complete."
