#!/usr/bin/env python3
"""Parity tests between the browser dither and Pillow's device pipeline."""

import json
import subprocess
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DITHER_JS = ROOT / "docs" / "dither.js"
EMULATOR = ROOT / "docs" / "emulator.html"


def pil_bits(values, width, height):
    image = Image.new("L", (width, height))
    image.putdata(values)
    converted = image.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    pixels = (
        converted.get_flattened_data()
        if hasattr(converted, "get_flattened_data")
        else converted.getdata()
    )
    return [1 if value else 0 for value in pixels]


def js_bits(values, width, height):
    program = (
        f"const d=require({json.dumps(str(DITHER_JS))});"
        f"console.log(JSON.stringify(Array.from(d.dither({json.dumps(values)},{width},{height}))));"
    )
    result = subprocess.run(
        ["node", "-e", program], text=True, capture_output=True, check=True
    )
    return json.loads(result.stdout)


class DitherParityTests(unittest.TestCase):
    def test_emulator_uses_shared_dither_module(self):
        html = EMULATOR.read_text(encoding="utf-8")
        self.assertIn('<script src="dither.js"></script>', html)

    def test_uniform_and_edge_patterns_match_pillow(self):
        patterns = [
            (8, 8, [0] * 64),
            (8, 8, [255] * 64),
            (8, 8, [127, 128] * 32),
            (8, 8, [x * 4 for _ in range(8) for x in range(8)]),
            (8, 8, [255 if (x + y) % 2 else 0 for y in range(8) for x in range(8)]),
        ]
        for width, height, values in patterns:
            with self.subTest(values=values[:8]):
                self.assertEqual(js_bits(values, width, height), pil_bits(values, width, height))


if __name__ == "__main__":
    unittest.main()
