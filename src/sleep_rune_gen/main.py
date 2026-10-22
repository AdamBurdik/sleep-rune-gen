from __future__ import annotations

import argparse
import string
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLOR = (0x37, 0x36, 0x32)
SUPERSAMPLE = 4
REFERENCE_SIZE = 200

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKGROUND = PROJECT_ROOT / "assets" / "background.png"
DEFAULT_OUTPUT = PROJECT_ROOT / "output"
FONT_NAME = "SleepTokenRunes-Regular.ttf"


def resolve_font(path: str | None) -> Path:
    if path:
        font_path = Path(path)
        if not font_path.is_file():
            raise FileNotFoundError(f"Font not found: {font_path}")
        return font_path

    candidates = [
        PROJECT_ROOT / "assets" / FONT_NAME,
        Path.home() / ".local" / "share" / "fonts" / FONT_NAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Font not found. Tried: " + ", ".join(str(c) for c in candidates)
    )


def uniform_font_size(font_path: Path, letters: str, target: int) -> int:
    reference = ImageFont.truetype(str(font_path), REFERENCE_SIZE)
    largest = 0
    for letter in letters:
        left, top, right, bottom = reference.getbbox(letter)
        largest = max(largest, right - left, bottom - top)
    return max(1, round(REFERENCE_SIZE * target / largest))


def render_letter(
    background: Image.Image,
    font_path: Path,
    letter: str,
    size: int,
) -> Image.Image:
    width, height = background.size
    font = ImageFont.truetype(str(font_path), size * SUPERSAMPLE)

    left, top, right, bottom = font.getbbox(letter)
    x = width * SUPERSAMPLE / 2 - (left + right) / 2
    y = height * SUPERSAMPLE / 2 - (top + bottom) / 2

    mask = Image.new("L", (width * SUPERSAMPLE, height * SUPERSAMPLE), 0)
    ImageDraw.Draw(mask).text((x, y), letter, font=font, fill=255)
    mask = mask.resize((width, height), Image.Resampling.LANCZOS)

    glyph = Image.new("RGBA", (width, height), (*COLOR, 0))
    glyph.putalpha(mask)

    image = background.copy()
    image.alpha_composite(glyph)
    return image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Sleep Token rune letters.")
    parser.add_argument("--background", default=str(DEFAULT_BACKGROUND))
    parser.add_argument("--font", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--size",
        type=float,
        default=0.8,
        help="Fraction of the shorter image side the largest glyph occupies.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    background_path = Path(args.background)
    if not background_path.is_file():
        raise FileNotFoundError(f"Background not found: {background_path}")

    font_path = resolve_font(args.font)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    background = Image.open(background_path).convert("RGBA")
    letters = string.ascii_uppercase
    target = round(min(background.size) * args.size)
    size = uniform_font_size(font_path, letters, target)

    for letter in letters:
        image = render_letter(background, font_path, letter, size)
        image.save(output_dir / f"{letter}.png")
        print(f"{letter}.png")

    print(f"Generated {len(letters)} images in {output_dir}")


if __name__ == "__main__":
    main()
