#!/usr/bin/env python3
"""Feedback-driven contracts for orientation and shutter interaction."""

import json
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMULATOR = ROOT / "docs" / "emulator.html"
SHUTTER = ROOT / "docs" / "shutter.js"


class EmulatorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.by_id = {}
        self.scripts = []
        self.options = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.by_id[attrs["id"]] = attrs
        if tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        if tag == "option":
            self.options.append(attrs)


class EmulatorFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = EMULATOR.read_text(encoding="utf-8")
        cls.parser = EmulatorParser()
        cls.parser.feed(cls.html)

    def test_panel_is_landscape(self):
        panel = self.parser.by_id["panel"]
        self.assertEqual((panel["width"], panel["height"]), ("264", "176"))
        self.assertIn("const PANEL_W = 264, PANEL_H = 176", self.html)

    def test_webcam_orientation_defaults_to_zero_degrees(self):
        zero_option = next(option for option in self.parser.options if option.get("value") == "0")
        ninety_option = next(option for option in self.parser.options if option.get("value") == "90")
        self.assertIn("selected", zero_option)
        self.assertNotIn("selected", ninety_option)

    def test_shutter_gesture_module_and_instructions_are_present(self):
        self.assertIn("shutter.js", self.parser.scripts)
        self.assertIn("Tap to capture", self.html)
        self.assertIn("Hold to print", self.html)

    def test_idle_screen_has_camera_graphic_renderer(self):
        self.assertIn("function drawWelcomeScreen()", self.html)
        self.assertIn("START CAMERA", self.html)

    def test_shutter_tap_and_hold_are_distinct(self):
        script = f"""
const s=require({json.dumps(str(SHUTTER))});
const events=[];
const g=s.createShutterGesture({{
  holdMs:25,
  onTap:()=>events.push('tap'),
  onHold:()=>events.push('hold')
}});
(async()=>{{
  g.press();
  await new Promise(r=>setTimeout(r,5));
  g.release();
  g.press();
  await new Promise(r=>setTimeout(r,40));
  g.release();
  console.log(JSON.stringify(events));
}})();
"""
        result = subprocess.run(["node", "-e", script], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), ["tap", "hold"])


if __name__ == "__main__":
    unittest.main()
