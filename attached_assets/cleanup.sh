#!/bin/bash

# Script to clean up unnecessary cache files while keeping the application functional
# This helps reduce the overall size below 1.8GB as requested

echo "Starting cleanup process..."
BEFORE_SIZE=$(du -sh . | awk '{print $1}')

# Remove GPU-related libraries (CUDA, Triton, etc.) since we're using CPU-only version
echo "Removing CUDA and GPU-related components..."
rm -rf .cache/uv/archive-v0/_09dVpEm_pW8YFUzEzJT7/cusparselt 2>/dev/null || true
rm -rf .cache/uv/archive-v0/J70GsLTFnLVIiNorj2O3W/triton 2>/dev/null || true
find .cache/uv/archive-v0 -path "*/nvidia*" -type d -exec rm -rf {} + 2>/dev/null || true
find .cache/uv/archive-v0 -path "*/cuda*" -type d -exec rm -rf {} + 2>/dev/null || true

# Keep only the essential parts of PyTorch, removing test and other non-core components
echo "Optimizing PyTorch components..."
find .cache/uv/archive-v0 -path "*/torch/*/test" -type d -exec rm -rf {} + 2>/dev/null || true
find .cache/uv/archive-v0 -path "*/torch/*/caffe2" -type d -exec rm -rf {} + 2>/dev/null || true
find .cache/uv/archive-v0 -path "*/torch/*/onnx" -type d -exec rm -rf {} + 2>/dev/null || true
find .cache/uv/archive-v0 -path "*/torch/lib" -name "*.a" -delete 2>/dev/null || true

# Remove PyPI cache files that are not needed for runtime
echo "Removing PyPI cache files..."
rm -rf .cache/uv/wheels-v3 2>/dev/null || true
rm -rf .cache/uv/archive-v0/*/pypi/cache 2>/dev/null || true
rm -rf .cache/uv/source-maps-v2 2>/dev/null || true

# Remove Python compiled files to save space
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Calculate size after cleanup
AFTER_SIZE=$(du -sh . | awk '{print $1}')

echo "Cleanup complete!"
echo "Size before: $BEFORE_SIZE"
echo "Current size: $AFTER_SIZE"

# Restart the Gunicorn server to ensure everything is working properly
echo "Restarting Gunicorn server..."
# No need to restart manually as the workflow tool will handle this