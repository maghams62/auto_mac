#!/bin/bash

# Script to create macOS .icns icon from a 1024x1024 PNG
# Usage: ./create-icon.sh input.png

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <input-png-1024x1024>"
    exit 1
fi

INPUT_PNG="$1"

if [ ! -f "$INPUT_PNG" ]; then
    echo "Error: Input file '$INPUT_PNG' not found"
    exit 1
fi

# Check if input is 1024x1024
WIDTH=$(sips -g pixelWidth "$INPUT_PNG" | tail -n1 | awk '{print $2}')
HEIGHT=$(sips -g pixelHeight "$INPUT_PNG" | tail -n1 | awk '{print $2}')

if [ "$WIDTH" != "1024" ] || [ "$HEIGHT" != "1024" ]; then
    echo "Warning: Input image is ${WIDTH}x${HEIGHT}, should be 1024x1024"
    echo "Resizing to 1024x1024..."
    sips -z 1024 1024 "$INPUT_PNG" --out temp_1024.png
    INPUT_PNG="temp_1024.png"
fi

# Create iconset directory
ICONSET_DIR="assets/icon.iconset"
mkdir -p "$ICONSET_DIR"

# Generate all required sizes
echo "Generating icon sizes..."

# Standard sizes
sips -z 16 16     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png"
sips -z 32 32     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32.png"
sips -z 64 64     "$INPUT_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png"
sips -z 128 128   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png"
sips -z 256 256   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png"
sips -z 512 512   "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512.png"
sips -z 1024 1024 "$INPUT_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png"

# Convert to .icns
echo "Creating .icns file..."
iconutil -c icns "$ICONSET_DIR" -o "assets/icon.icns"

# Cleanup
rm -rf "$ICONSET_DIR"
if [ -f "temp_1024.png" ]; then
    rm temp_1024.png
fi

echo "✅ Icon created: assets/icon.icns"
echo ""
echo "Next steps:"
echo "1. Update electron-builder.json to use .icns:"
echo '   "mac": { "icon": "assets/icon.icns" }'
echo "2. Rebuild the app: npm run dist:mac"
