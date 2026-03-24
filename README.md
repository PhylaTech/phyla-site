# Phyla Technologies
Landing page for [phylatech.com](https://phylatech.com).

## SVG to PNG Conversion

The `svg_to_png.py` script converts SVG files to PNG at a specified DPI.

### Dependencies

Requires Python 3 and the following:

```bash
# System library (macOS)
brew install cairo

# Python packages
pip install cairosvg pillow
```

### Usage

```bash
python3 svg_to_png.py input.svg              # 300 DPI (default)
python3 svg_to_png.py input.svg -d 150       # custom DPI
python3 svg_to_png.py input.svg -o out.png   # custom output path
```

