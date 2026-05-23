# -*- coding: utf-8 -*-
"""Grimoire の純粋ロジックに対するユニットテスト（GUIを起動しない）。

実行: プロジェクト直下で  python -m unittest discover -s tests -v
GUI（Tk）は生成しないので、ディスプレイの無い CI でも通る。
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import stamper  # noqa: E402


class TestColor(unittest.TestCase):
    def test_lum_bounds(self):
        self.assertAlmostEqual(stamper._lum("#000000"), 0.0, places=3)
        self.assertAlmostEqual(stamper._lum("#FFFFFF"), 1.0, places=3)

    def test_fg_on_contrast(self):
        # 暗いアクセント → 白文字、明るいアクセント → 濃い文字
        self.assertEqual(stamper.fg_on("#1A1A1A"), "#FFFFFF")
        self.assertEqual(stamper.fg_on("#84CCD8"), "#1A1A1A")

    def test_darken_reduces(self):
        out = stamper.darken("#FFFFFF", 0.5)
        r = int(out[1:3], 16)
        self.assertLess(r, 255)
        self.assertEqual(stamper.darken("#FFFFFF", 0.0), "#ffffff")

    def test_text_on_white(self):
        # 十分濃い色はそのまま、明るすぎる色は暗く（=入力と変わる）
        self.assertEqual(stamper.text_on_white("#1E88E5"), "#1E88E5")
        self.assertNotEqual(stamper.text_on_white("#84CCD8").lower(), "#84ccd8")

    def test_lighten_staticmethod(self):
        self.assertEqual(stamper.StamperApp._lighten("#000000", 1.0), "#ffffff")
        self.assertEqual(stamper.StamperApp._lighten("#808080", 0.0), "#808080")

    def test_tab_text_truncates(self):
        self.assertEqual(stamper.StamperApp._tab_text("短い"), "短い")
        long = stamper.StamperApp._tab_text("あ" * 20, n=8)
        self.assertTrue(long.endswith("…"))
        self.assertEqual(len(long), 9)


class TestHotkey(unittest.TestCase):
    def test_parse_combo(self):
        mods, vk = stamper.parse_hotkey("ctrl+alt+space")
        self.assertEqual(mods, 0x2 | 0x1)
        self.assertEqual(vk, 0x20)

    def test_parse_function_key(self):
        mods, vk = stamper.parse_hotkey("ctrl+f1")
        self.assertEqual(mods, 0x2)
        self.assertEqual(vk, 0x70)

    def test_parse_requires_modifier(self):
        self.assertEqual(stamper.parse_hotkey("a"), (None, None))

    def test_parse_requires_key(self):
        self.assertEqual(stamper.parse_hotkey("ctrl+"), (None, None))

    def test_parse_empty(self):
        self.assertEqual(stamper.parse_hotkey(""), (None, None))

    def test_key_to_vk(self):
        self.assertEqual(stamper._key_to_vk("a"), ord("A"))
        self.assertEqual(stamper._key_to_vk("space"), 0x20)
        self.assertEqual(stamper._key_to_vk("f5"), 0x74)
        self.assertIsNone(stamper._key_to_vk("zzz"))
        self.assertIsNone(stamper._key_to_vk(""))


class TestItemLabel(unittest.TestCase):
    def test_title_wins(self):
        self.assertEqual(stamper.item_label({"title": "件名", "body": "x"}), "件名")

    def test_body_first_line(self):
        self.assertEqual(stamper.item_label({"title": "", "body": "一行目\n二行目"}), "一行目")

    def test_body_truncates(self):
        out = stamper.item_label({"title": "", "body": "あ" * 40})
        self.assertTrue(out.endswith("…"))
        self.assertEqual(len(out), 25)

    def test_empty(self):
        self.assertEqual(stamper.item_label({"title": "", "body": ""}), "(空の定型文)")


class TestPlaceholders(unittest.TestCase):
    def test_builtin_values(self):
        v = stamper.builtin_values(datetime(2026, 5, 22, 14, 30))
        self.assertEqual(v["date"], "2026-05-22")
        self.assertEqual(v["time"], "14:30")
        self.assertEqual(v["datetime"], "2026-05-22 14:30")

    def test_custom_tokens_excludes_builtin_and_dedups(self):
        toks = stamper.custom_tokens("{{date}} {{宛名}} {{宛名}} {{Time}} {{金額}}")
        self.assertEqual(toks, ["宛名", "金額"])

    def test_custom_tokens_none(self):
        self.assertEqual(stamper.custom_tokens("プレーンな文"), [])

    def test_expand_known_and_unknown(self):
        out = stamper.expand_tokens("{{a}}と{{b}}", {"a": "X"})
        self.assertEqual(out, "Xと{{b}}")  # 未知トークンはそのまま残す

    def test_expand_case_insensitive_fallback(self):
        out = stamper.expand_tokens("{{Date}}", {"date": "2026-05-22"})
        self.assertEqual(out, "2026-05-22")


class TestDataIO(unittest.TestCase):
    def setUp(self):
        self._orig = stamper.DATA_FILE
        self._dir = tempfile.mkdtemp()
        stamper.DATA_FILE = os.path.join(self._dir, "sub", "templates.json")

    def tearDown(self):
        stamper.DATA_FILE = self._orig
        for root, dirs, files in os.walk(self._dir, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(self._dir)

    def test_load_default_when_missing(self):
        data = stamper.load_data()
        self.assertIn("folders", data)
        self.assertGreater(len(data["folders"]), 0)
        # DEFAULT_DATA の独立コピーであること（同一参照でない）
        self.assertIsNot(data, stamper.DEFAULT_DATA)

    def test_save_then_load_roundtrip(self):
        data = {"settings": {"hotkey": "ctrl+alt+x"},
                "folders": [{"name": "テスト", "items": [
                    {"title": "t", "body": "b"}]}]}
        self.assertTrue(stamper.save_data(data))
        self.assertTrue(os.path.exists(stamper.DATA_FILE))
        loaded = stamper.load_data()
        self.assertEqual(loaded["folders"][0]["name"], "テスト")
        # 既定フィールドが補完される
        item = loaded["folders"][0]["items"][0]
        self.assertIn("secret", item)
        self.assertIn("pinned", item)
        self.assertIn("used", item)
        self.assertIn("paste_back", loaded["settings"])
        self.assertIn("window_w", loaded["settings"])
        self.assertIn("window_h", loaded["settings"])

    def test_save_no_leftover_tmp(self):
        stamper.save_data({"folders": [{"name": "a", "items": []}]})
        self.assertFalse(os.path.exists(stamper.DATA_FILE + ".tmp"))

    def test_load_corrupt_falls_back(self):
        os.makedirs(os.path.dirname(stamper.DATA_FILE), exist_ok=True)
        with open(stamper.DATA_FILE, "w", encoding="utf-8") as f:
            f.write("{{{ this is not json")
        data = stamper.load_data()
        self.assertIn("folders", data)
        self.assertGreater(len(data["folders"]), 0)


class TestAutostartHelpers(unittest.TestCase):
    """自動起動はスタートアップフォルダの .lnk で実装。
    set/get の実体（実際の .lnk 作成）はテストしない（ユーザーのフォルダを汚染するため）。
    ここではパス計算と availability の純粋ロジックだけを確認する。"""

    def test_not_available_in_dev(self):
        # .py から実行（frozen=False）のときは自動起動を提供しない
        self.assertFalse(stamper.autostart_available())

    def test_shortcut_path_ends_with_app_name(self):
        p = stamper._shortcut_path()
        self.assertTrue(p.endswith(stamper.APP_NAME + ".lnk"))

    def test_startup_dir_contains_startup(self):
        d = stamper._startup_dir()
        self.assertIn("Startup", d)

    def test_ps_quote_doubles_single_quotes(self):
        self.assertEqual(stamper._ps_quote("a'b'c"), "a''b''c")
        self.assertEqual(stamper._ps_quote("normal"), "normal")


class TestDefaultData(unittest.TestCase):
    def test_serializable_and_structure(self):
        s = json.dumps(stamper.DEFAULT_DATA, ensure_ascii=False)
        self.assertIn("folders", json.loads(s))
        settings = stamper.DEFAULT_DATA["settings"]
        for key in ("hotkey", "accent", "confirm_delete", "paste_back",
                    "window_w", "window_h", "autostart"):
            self.assertIn(key, settings)
        for folder in stamper.DEFAULT_DATA["folders"]:
            self.assertIn("name", folder)
            self.assertIsInstance(folder["items"], list)

    def test_default_accent_is_preset(self):
        presets = {c.lower() for _, c in stamper.PRESET_COLORS}
        self.assertIn(stamper.DEFAULT_ACCENT.lower(), presets)


if __name__ == "__main__":
    unittest.main(verbosity=2)
