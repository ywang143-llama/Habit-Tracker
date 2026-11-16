"""The tray icon artwork, drawn at runtime so there are no extra assets."""

from __future__ import annotations

from PIL import Image, ImageDraw


def build_icon_image(size: int = 64) -> Image.Image:
    """Render a rounded blue tile with a white check mark."""
    render = 8
    pixels = max(size * render, 64)
    image = Image.new("RGBA", (pixels, pixels), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    inset = pixels * 0.045
    draw.rounded_rectangle(
        (inset, inset, pixels - inset, pixels - inset),
        radius=pixels * 0.24,
        fill=(91, 141, 239, 255),
    )

    width = max(int(pixels * 0.095), 2)
    points = [
        (pixels * 0.27, pixels * 0.53),
        (pixels * 0.44, pixels * 0.70),
        (pixels * 0.75, pixels * 0.33),
    ]
    draw.line(points, fill=(255, 255, 255, 255), width=width, joint="curve")
    for point in (points[0], points[-1]):
        draw.ellipse(
            (
                point[0] - width / 2,
                point[1] - width / 2,
                point[0] + width / 2,
                point[1] + width / 2,
            ),
            fill=(255, 255, 255, 255),
        )

    return image.resize((size, size), Image.LANCZOS)
