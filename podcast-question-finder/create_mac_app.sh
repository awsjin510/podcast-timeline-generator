#!/bin/bash
# ============================================================
# 建立 macOS 桌面應用程式 — Podcast 時間軸產生器
# 執行方式：chmod +x create_mac_app.sh && ./create_mac_app.sh
# ============================================================

set -e

APP_NAME="Podcast時間軸產生器"
APP_DIR="$HOME/Desktop/${APP_NAME}.app"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🎬 建立桌面應用程式..."

# ── 建立 .app 結構 ──────────────────────
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# ── 建立啟動腳本 ────────────────────────
cat > "$APP_DIR/Contents/MacOS/launch.sh" << 'LAUNCH'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
PROJ_DIR="PLACEHOLDER_PROJ_DIR"

# 開啟 Terminal 執行
osascript -e "
tell application \"Terminal\"
    activate
    do script \"cd '$PROJ_DIR' && source venv/bin/activate 2>/dev/null; if [ -f .env ]; then source .env; fi; export ANTHROPIC_API_KEY=\\\"\$ANTHROPIC_API_KEY\\\"; python3 flask_app.py & sleep 2 && open http://localhost:5000\"
end tell
"
LAUNCH

# 替換專案路徑
sed -i '' "s|PLACEHOLDER_PROJ_DIR|${SCRIPT_DIR}|g" "$APP_DIR/Contents/MacOS/launch.sh"
chmod +x "$APP_DIR/Contents/MacOS/launch.sh"

# ── 建立 Info.plist ─────────────────────
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launch.sh</string>
    <key>CFBundleName</key>
    <string>Podcast時間軸產生器</string>
    <key>CFBundleDisplayName</key>
    <string>Podcast 時間軸產生器</string>
    <key>CFBundleIdentifier</key>
    <string>com.podcast.timeline-generator</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# ── 用 Python 產生圖示 ─────────────────
python3 << 'PYICON'
import struct, zlib, os, sys

def create_png(width, height, pixels):
    """Create a PNG file from RGBA pixel data."""
    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc

    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))

    raw = b''
    for y in range(height):
        raw += b'\x00'
        for x in range(width):
            idx = (y * width + x) * 4
            raw += bytes(pixels[idx:idx+4])

    idat = chunk(b'IDAT', zlib.compress(raw, 9))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend

def draw_icon(size):
    """Draw a podcast timeline icon."""
    pixels = [0] * (size * size * 4)

    def set_pixel(x, y, r, g, b, a=255):
        if 0 <= x < size and 0 <= y < size:
            idx = (y * size + x) * 4
            # Alpha blend
            old_a = pixels[idx+3]
            if old_a > 0 and a < 255:
                fa = a / 255.0
                pixels[idx]   = int(pixels[idx]   * (1-fa) + r * fa)
                pixels[idx+1] = int(pixels[idx+1] * (1-fa) + g * fa)
                pixels[idx+2] = int(pixels[idx+2] * (1-fa) + b * fa)
                pixels[idx+3] = min(255, old_a + a)
            else:
                pixels[idx] = r
                pixels[idx+1] = g
                pixels[idx+2] = b
                pixels[idx+3] = a

    def fill_circle(cx, cy, r, red, green, blue, alpha=255):
        for y in range(max(0, int(cy-r-1)), min(size, int(cy+r+2))):
            for x in range(max(0, int(cx-r-1)), min(size, int(cx+r+2))):
                dist = ((x - cx)**2 + (y - cy)**2) ** 0.5
                if dist <= r:
                    aa = alpha
                    if dist > r - 1.2:
                        aa = int(alpha * max(0, (r - dist) / 1.2))
                    set_pixel(x, y, red, green, blue, aa)

    def fill_rect(x1, y1, x2, y2, r, g, b, a=255):
        for y in range(max(0, int(y1)), min(size, int(y2))):
            for x in range(max(0, int(x1)), min(size, int(x2))):
                set_pixel(x, y, r, g, b, a)

    def fill_rounded_rect(x1, y1, x2, y2, radius, r, g, b, a=255):
        for y in range(max(0, int(y1)), min(size, int(y2))):
            for x in range(max(0, int(x1)), min(size, int(x2))):
                inside = True
                # Check corners
                corners = [
                    (x1 + radius, y1 + radius),
                    (x2 - radius, y1 + radius),
                    (x1 + radius, y2 - radius),
                    (x2 - radius, y2 - radius),
                ]
                for cx, cy in corners:
                    if ((x < x1 + radius or x > x2 - radius) and
                        (y < y1 + radius or y > y2 - radius)):
                        dx = x - cx if abs(x - cx) == min(abs(x - c[0]) for c in corners if abs(y - c[1]) == min(abs(y - cc[1]) for cc in corners)) else 0
                        pass
                # Simplified: just fill rect
                set_pixel(x, y, r, g, b, a)

    s = size
    pad = int(s * 0.08)

    # Background - dark rounded rectangle
    for y in range(size):
        for x in range(size):
            # Rounded corners
            r = s * 0.18
            in_rect = True
            corners = [(pad + r, pad + r), (s - pad - r, pad + r),
                       (pad + r, s - pad - r), (s - pad - r, s - pad - r)]
            if x < pad + r and y < pad + r:
                in_rect = ((x - (pad+r))**2 + (y - (pad+r))**2) <= r*r
            elif x > s - pad - r and y < pad + r:
                in_rect = ((x - (s-pad-r))**2 + (y - (pad+r))**2) <= r*r
            elif x < pad + r and y > s - pad - r:
                in_rect = ((x - (pad+r))**2 + (y - (s-pad-r))**2) <= r*r
            elif x > s - pad - r and y > s - pad - r:
                in_rect = ((x - (s-pad-r))**2 + (y - (s-pad-r))**2) <= r*r
            elif x < pad or x >= s - pad or y < pad or y >= s - pad:
                in_rect = False

            if in_rect:
                # Gradient background
                t = y / s
                bg_r = int(10 + t * 8)
                bg_g = int(10 + t * 6)
                bg_b = int(20 + t * 12)
                set_pixel(x, y, bg_r, bg_g, bg_b, 255)

    # Podcast microphone icon (center top)
    cx, cy = s * 0.5, s * 0.32
    mic_r = s * 0.13

    # Mic body (cyan)
    fill_circle(cx, cy, mic_r, 0, 200, 224)
    # Mic inner
    fill_circle(cx, cy, mic_r * 0.55, 15, 15, 30)

    # Mic stand
    stand_w = s * 0.03
    fill_rect(cx - stand_w/2, cy + mic_r * 0.6, cx + stand_w/2, cy + mic_r * 2.2, 0, 200, 224)

    # Mic base
    fill_rect(cx - s*0.08, cy + mic_r * 2.0, cx + s*0.08, cy + mic_r * 2.2 + s*0.02, 0, 200, 224)

    # Timeline bars (bottom section)
    bar_y_start = s * 0.62
    bar_h = s * 0.045
    bar_gap = s * 0.065
    bar_x = s * 0.18
    colors = [
        (0, 200, 224),    # cyan
        (224, 53, 122),   # pink
        (155, 69, 217),   # purple
        (0, 200, 224),    # cyan
    ]
    widths = [0.72, 0.55, 0.48, 0.62]

    for i, (color, w) in enumerate(zip(colors, widths)):
        by = bar_y_start + i * bar_gap
        # Timestamp dot
        fill_circle(bar_x - s*0.04, by + bar_h/2, s*0.018, *color)
        # Bar
        bx2 = bar_x + s * w
        fill_rect(bar_x, by, bx2, by + bar_h, *color, 200)
        # Glow effect (subtle)
        fill_rect(bar_x, by - 1, bx2, by + bar_h + 1, *color, 30)

    return pixels

# Generate icon at 512x512
size = 512
pixels = draw_icon(size)
png_data = create_png(size, size, pixels)

# Also create 256x256
size2 = 256
pixels2 = draw_icon(size2)
png_data2 = create_png(size2, size2, pixels2)

# Save PNGs
icon_dir = os.path.expanduser("~/Desktop/icon_tmp")
os.makedirs(icon_dir, exist_ok=True)
with open(f"{icon_dir}/icon_512.png", "wb") as f:
    f.write(png_data)
with open(f"{icon_dir}/icon_256.png", "wb") as f:
    f.write(png_data2)

# Create 1024
size3 = 1024
pixels3 = draw_icon(size3)
png_data3 = create_png(size3, size3, pixels3)
with open(f"{icon_dir}/icon_1024.png", "wb") as f:
    f.write(png_data3)

print(f"PNG icons saved to {icon_dir}")
PYICON

# 用 macOS 內建工具轉換為 icns
ICON_TMP="$HOME/Desktop/icon_tmp"
ICONSET="$ICON_TMP/app.iconset"
mkdir -p "$ICONSET"

# 用 sips 產生各尺寸
sips -z 16 16     "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_16x16.png" > /dev/null 2>&1
sips -z 32 32     "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_16x16@2x.png" > /dev/null 2>&1
sips -z 32 32     "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_32x32.png" > /dev/null 2>&1
sips -z 64 64     "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_32x32@2x.png" > /dev/null 2>&1
sips -z 128 128   "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_128x128.png" > /dev/null 2>&1
sips -z 256 256   "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_128x128@2x.png" > /dev/null 2>&1
sips -z 256 256   "$ICON_TMP/icon_256.png" --out "$ICONSET/icon_256x256.png" > /dev/null 2>&1
sips -z 512 512   "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_256x256@2x.png" > /dev/null 2>&1
sips -z 512 512   "$ICON_TMP/icon_512.png" --out "$ICONSET/icon_512x512.png" > /dev/null 2>&1
cp "$ICON_TMP/icon_1024.png" "$ICONSET/icon_512x512@2x.png"

# 轉換成 icns
iconutil -c icns "$ICONSET" -o "$APP_DIR/Contents/Resources/app.icns"

# 清理暫存
rm -rf "$ICON_TMP"

echo ""
echo "=========================================="
echo " ✅ 應用程式已建立！"
echo " 📍 位置：桌面 / ${APP_NAME}.app"
echo " 🖱️  雙擊即可啟動"
echo "=========================================="
echo ""
echo "💡 提示：首次開啟可能需要右鍵 → 打開"
echo "   （因為不是 App Store 下載的應用程式）"
