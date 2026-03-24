#!/usr/bin/env python3
"""Convert an SVG file to a PNG at a specified DPI."""

import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Convert SVG to PNG")
    parser.add_argument("input", help="Path to input SVG file")
    parser.add_argument("-o", "--output", help="Path to output PNG file (default: same name with .png)")
    parser.add_argument("-d", "--dpi", type=int, default=300, help="Output DPI (default: 300)")
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.splitext(args.input)[0] + ".png"

    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

    import cairosvg
    from PIL import Image
    import io

    scale = args.dpi / 96.0
    png_data = cairosvg.svg2png(url=args.input, scale=scale, dpi=args.dpi)

    img = Image.open(io.BytesIO(png_data))
    img.save(args.output, dpi=(args.dpi, args.dpi))

    print(f"{args.output} — {img.size[0]}x{img.size[1]}px @ {args.dpi} DPI")

if __name__ == "__main__":
    main()
