#!/usr/bin/env python3
"""
generate_gui_icons.py
Generates crisp, high-contrast 40x40 PNG icons for the robotic arm GUI buttons:
- rotate_left.png
- rotate_right.png
- down.png
- up.png
- retract.png
- extend.png
"""

import os
import math
import zlib
import struct
from pathlib import Path

def create_png(width, height, rgba_data):
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    raw = b''.join(b'\x00' + rgba_data[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')

def new_canvas(w=40, h=40):
    return bytearray([0] * (w * h * 4))

def set_pixel(buf, w, h, x, y, r, g, b, a=255):
    if 0 <= x < w and 0 <= y < h:
        idx = (int(y) * w + int(x)) * 4
        # Alpha blending
        alpha = a / 255.0
        buf[idx] = int(r * alpha + buf[idx] * (1 - alpha))
        buf[idx + 1] = int(g * alpha + buf[idx + 1] * (1 - alpha))
        buf[idx + 2] = int(b * alpha + buf[idx + 2] * (1 - alpha))
        buf[idx + 3] = max(buf[idx + 3], a)

def draw_aa_disc(buf, w, h, cx, cy, radius, r, g, b, a=255):
    for y in range(max(0, int(cy - radius - 1)), min(h, int(cy + radius + 2))):
        for x in range(max(0, int(cx - radius - 1)), min(w, int(cx + radius + 2))):
            d = math.hypot(x - cx, y - cy)
            if d <= radius - 0.5:
                set_pixel(buf, w, h, x, y, r, g, b, a)
            elif d <= radius + 0.5:
                cov = 0.5 - (d - radius)
                set_pixel(buf, w, h, x, y, r, g, b, int(a * cov))

def draw_thick_line(buf, w, h, x0, y0, x1, y1, width, r, g, b, a=255):
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        draw_aa_disc(buf, w, h, x0, y0, width / 2.0, r, g, b, a)
        return
    steps = max(int(length * 2), 2)
    radius = width / 2.0
    for s in range(steps + 1):
        t = s / steps
        cx = x0 + t * (x1 - x0)
        cy = y0 + t * (y1 - y0)
        draw_aa_disc(buf, w, h, cx, cy, radius, r, g, b, a)

def draw_filled_triangle(buf, w, h, p1, p2, p3, r, g, b, a=255):
    # Bounding box
    min_x = max(0, int(min(p1[0], p2[0], p3[0]) - 1))
    max_x = min(w, int(max(p1[0], p2[0], p3[0]) + 2))
    min_y = max(0, int(min(p1[1], p2[1], p3[1]) - 1))
    max_y = min(h, int(max(p1[1], p2[1], p3[1]) + 2))

    def sign(p, a, b):
        return (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])

    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            pt = (x + 0.5, y + 0.5)
            d1 = sign(pt, p1, p2)
            d2 = sign(pt, p2, p3)
            d3 = sign(pt, p3, p1)
            has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
            has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
            if not (has_neg and has_pos):
                set_pixel(buf, w, h, x, y, r, g, b, a)

# Accent Cyan: #00d9ff = (0, 217, 255)
# Accent White: #ffffff = (255, 255, 255)
CYAN = (0, 217, 255)
WHITE = (255, 255, 255)

def make_down_icon(w=40, h=40):
    buf = new_canvas(w, h)
    # Shaft
    draw_thick_line(buf, w, h, 20, 6, 20, 22, 5.5, *CYAN)
    # Arrow head pointing down
    draw_filled_triangle(buf, w, h, (8, 20), (32, 20), (20, 34), *CYAN)
    # Inner accent
    draw_thick_line(buf, w, h, 20, 8, 20, 22, 2.0, *WHITE)
    return buf

def make_up_icon(w=40, h=40):
    buf = new_canvas(w, h)
    # Shaft
    draw_thick_line(buf, w, h, 20, 34, 20, 18, 5.5, *CYAN)
    # Arrow head pointing up
    draw_filled_triangle(buf, w, h, (8, 20), (32, 20), (20, 6), *CYAN)
    # Inner accent
    draw_thick_line(buf, w, h, 20, 32, 20, 18, 2.0, *WHITE)
    return buf

def make_rotate_left_icon(w=40, h=40):
    buf = new_canvas(w, h)
    cx, cy = 20, 20
    radius = 12.0
    # CCW Arc from -40 deg to 210 deg
    start_rad = math.radians(-30)
    end_rad = math.radians(220)
    steps = 45
    for i in range(steps):
        t0 = start_rad + (end_rad - start_rad) * (i / steps)
        t1 = start_rad + (end_rad - start_rad) * ((i + 1) / steps)
        x0 = cx + radius * math.cos(t0)
        y0 = cy - radius * math.sin(t0)
        x1 = cx + radius * math.cos(t1)
        y1 = cy - radius * math.sin(t1)
        draw_thick_line(buf, w, h, x0, y0, x1, y1, 4.0, *CYAN)
    # Arrowhead at end of arc pointing CCW (down/left)
    ax = cx + radius * math.cos(end_rad)
    ay = cy - radius * math.sin(end_rad)
    draw_filled_triangle(buf, w, h, (ax - 2, ay - 9), (ax + 9, ay - 2), (ax - 7, ay + 6), *CYAN)
    return buf

def make_rotate_right_icon(w=40, h=40):
    buf = new_canvas(w, h)
    cx, cy = 20, 20
    radius = 12.0
    # CW Arc
    start_rad = math.radians(210)
    end_rad = math.radians(-40)
    steps = 45
    for i in range(steps):
        t0 = start_rad + (end_rad - start_rad) * (i / steps)
        t1 = start_rad + (end_rad - start_rad) * ((i + 1) / steps)
        x0 = cx + radius * math.cos(t0)
        y0 = cy - radius * math.sin(t0)
        x1 = cx + radius * math.cos(t1)
        y1 = cy - radius * math.sin(t1)
        draw_thick_line(buf, w, h, x0, y0, x1, y1, 4.0, *CYAN)
    # Arrowhead pointing CW (down/right)
    ax = cx + radius * math.cos(end_rad)
    ay = cy - radius * math.sin(end_rad)
    draw_filled_triangle(buf, w, h, (ax + 2, ay - 9), (ax - 9, ay - 2), (ax + 7, ay + 6), *CYAN)
    return buf

def make_retract_icon(w=40, h=40):
    buf = new_canvas(w, h)
    # Shaft bending from right towards left
    draw_thick_line(buf, w, h, 33, 27, 23, 20, 5.0, *CYAN)
    draw_thick_line(buf, w, h, 23, 20, 16, 20, 5.0, *CYAN)
    # Arrowhead pointing left
    draw_filled_triangle(buf, w, h, (18, 9), (18, 31), (6, 20), *CYAN)
    return buf

def make_extend_icon(w=40, h=40):
    buf = new_canvas(w, h)
    # Shaft extending towards right
    draw_thick_line(buf, w, h, 7, 27, 17, 20, 5.0, *CYAN)
    draw_thick_line(buf, w, h, 17, 20, 24, 20, 5.0, *CYAN)
    # Arrowhead pointing right
    draw_filled_triangle(buf, w, h, (22, 9), (22, 31), (34, 20), *CYAN)
    return buf

def main():
    icons_dir = Path(__file__).resolve().parent.parent / "GUI_ROBOTIC_ARM" / "robotic_arm" / "robotic_arm" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    icons = {
        "down.png": make_down_icon(),
        "up.png": make_up_icon(),
        "rotate_left.png": make_rotate_left_icon(),
        "rotate_right.png": make_rotate_right_icon(),
        "retract.png": make_retract_icon(),
        "extend.png": make_extend_icon(),
    }

    for name, data in icons.items():
        png_path = icons_dir / name
        png_path.write_bytes(create_png(40, 40, data))
        print(f"Generated {png_path} ({len(png_path.read_bytes())} bytes)")

if __name__ == "__main__":
    main()
