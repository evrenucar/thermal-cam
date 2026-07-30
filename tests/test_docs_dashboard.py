#!/usr/bin/env python3
"""Contract tests for the public project dashboard."""

import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.current_link = None
        self.link_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.current_link = attrs.get("href")
            self.link_text = []

    def handle_data(self, data):
        if self.current_link is not None:
            self.link_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current_link is not None:
            self.links.append((self.current_link, " ".join("".join(self.link_text).split())))
            self.current_link = None
            self.link_text = []


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.parser = DashboardParser()
        cls.parser.feed(cls.html)
        cls.status = json.loads((DOCS / "status.json").read_text(encoding="utf-8"))

    def test_dashboard_has_core_sections(self):
        required = {"mission", "project-links", "current-work", "roadmap", "system"}
        self.assertTrue(required.issubset(self.parser.ids), required - self.parser.ids)

    def test_dashboard_links_to_emulator_status_and_important_files(self):
        hrefs = {href for href, _ in self.parser.links}
        expected = {
            "emulator.html",
            "status.html",
            "https://github.com/evrenucar/thermal-cam",
            "https://github.com/evrenucar/thermal-cam/blob/master/pi/main.py",
            "https://github.com/evrenucar/thermal-cam/blob/master/pi/lib/ext/printer.py",
            "https://github.com/evrenucar/thermal-cam/blob/master/pi/test_printer.py",
            "https://github.com/evrenucar/thermal-cam/blob/master/docs/PRODUCT.md",
            "https://github.com/evrenucar/thermal-cam/blob/master/docs/STATE.md",
        }
        self.assertTrue(expected.issubset(hrefs), expected - hrefs)

    def test_status_reflects_current_development(self):
        self.assertEqual(self.status["now"]["state"], "active")
        self.assertNotIn("Untrack ESP32 build output", {item["task"] for item in self.status["blocked"]})
        self.assertIn("Dither parity test", {item["task"] for item in self.status["done"]})

    def test_project_handoff_does_not_describe_retired_two_remote_flow(self):
        state = (ROOT / "docs" / "STATE.md").read_text(encoding="utf-8")
        rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("doodek/thermal-cam", state)
        self.assertNotIn("doodek/thermal-cam", rules)
        self.assertNotIn("Work happens on `feature/emulator-and-docs`", rules)
        self.assertIn("https://evrenucar.github.io/thermal-cam/", state)

    def test_dashboard_loads_live_status_data(self):
        self.assertIn('fetch("status.json', self.html)
        self.assertIn('id="current-task"', self.html)


if __name__ == "__main__":
    unittest.main()
