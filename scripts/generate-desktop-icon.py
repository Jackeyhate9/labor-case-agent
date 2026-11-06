"""Generate deterministic desktop icons from the checked-in workspace image."""

from pathlib import Path

from PIL import Image, ImageEnhance


root = Path(__file__).resolve().parents[1]
source = root / "docs" / "images" / "labor-case-workspace.png"
target_dir = root / "apps" / "desktop" / "src-tauri" / "icons"
target_dir.mkdir(parents=True, exist_ok=True)

with Image.open(source) as original:
    image = original.convert("RGBA")
    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    square = image.crop((left, top, left + side, top + side))
    square = ImageEnhance.Contrast(square).enhance(1.08)
    square.save(target_dir / "icon.png", format="PNG", optimize=True)
    square.save(
        target_dir / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
