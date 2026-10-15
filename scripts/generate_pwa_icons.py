import os, math
from PIL import Image, ImageDraw, ImageFont

def create_pwa_icon(size: int, is_maskable: bool = False, output_path: str = ""):
    # High-res canvas with dark background
    img = Image.new("RGBA", (size, size), (7, 7, 9, 255))
    draw = ImageDraw.Draw(img)

    # Calculate dimensions
    # For maskable icons, content must be inside 80% safe zone (10% padding on all sides)
    scale = 0.75 if is_maskable else 0.88
    center = size / 2
    radius = (size * scale) / 2

    # Draw ambient purple glow circle
    glow_layers = 15
    for i in range(glow_layers, 0, -1):
        r = radius + (i * size * 0.015)
        alpha = int(12 * (1 - i / glow_layers))
        draw.ellipse(
            [center - r, center - r, center + r, center + r],
            fill=(134, 59, 255, alpha)
        )

    # Draw rounded background badge with gradient simulation
    badge_rect = [
        center - radius,
        center - radius,
        center + radius,
        center + radius
    ]
    # Draw badge base
    corner_r = int(radius * 0.4)
    draw.rounded_rectangle(badge_rect, radius=corner_r, fill=(18, 16, 28, 255), outline=(134, 59, 255, 180), width=int(size * 0.02))

    # Inner emblem: Download Arrow / Lightning Hybrid in neon violet & cyan
    arrow_w = size * 0.35 * (0.85 if is_maskable else 1.0)
    top_y = center - arrow_w * 0.65
    bottom_y = center + arrow_w * 0.65

    # Gradient-like lines for futuristic download arrow
    # Main down arrow head
    arrow_pts = [
        (center - arrow_w * 0.5, center + arrow_w * 0.1),
        (center, bottom_y),
        (center + arrow_w * 0.5, center + arrow_w * 0.1),
        (center + arrow_w * 0.22, center + arrow_w * 0.1),
        (center + arrow_w * 0.22, top_y),
        (center - arrow_w * 0.22, top_y),
        (center - arrow_w * 0.22, center + arrow_w * 0.1),
    ]
    # Draw shadow
    shadow_pts = [(x + size * 0.01, y + size * 0.01) for x, y in arrow_pts]
    draw.polygon(shadow_pts, fill=(80, 20, 160, 120))
    # Draw main arrow with electric purple/cyan
    draw.polygon(arrow_pts, fill=(134, 59, 255, 255))

    # Inner neon highlight
    inner_pts = [
        (center - arrow_w * 0.3, center + arrow_w * 0.15),
        (center, bottom_y - size * 0.04),
        (center + arrow_w * 0.3, center + arrow_w * 0.15),
        (center + arrow_w * 0.12, center + arrow_w * 0.15),
        (center + arrow_w * 0.12, top_y + size * 0.04),
        (center - arrow_w * 0.12, top_y + size * 0.04),
        (center - arrow_w * 0.12, center + arrow_w * 0.15),
    ]
    draw.polygon(inner_pts, fill=(195, 140, 255, 255))

    # Underline tray / speed bar
    bar_y = bottom_y + size * 0.05
    bar_h = size * 0.035
    bar_w = arrow_w * 0.9
    draw.rounded_rectangle(
        [center - bar_w / 2, bar_y, center + bar_w / 2, bar_y + bar_h],
        radius=int(bar_h / 2),
        fill=(71, 191, 255, 255)  # Cyan accent from brand
    )

    # Save PNG
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"Generated: {output_path} ({size}x{size})")

if __name__ == "__main__":
    public_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))
    create_pwa_icon(192, is_maskable=False, output_path=os.path.join(public_dir, "pwa-192x192.png"))
    create_pwa_icon(512, is_maskable=False, output_path=os.path.join(public_dir, "pwa-512x512.png"))
    create_pwa_icon(512, is_maskable=True, output_path=os.path.join(public_dir, "pwa-maskable-512x512.png"))
    create_pwa_icon(180, is_maskable=False, output_path=os.path.join(public_dir, "apple-touch-icon.png"))
