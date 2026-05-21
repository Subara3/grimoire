# -*- coding: utf-8 -*-
"""
Grimoire (グリモワ) — 定型文＝呪文を綴じた魔導書
- フォルダ(タブ)で定型文を分類管理
- 行をクリック / Enter / 1〜9 でクリップボードにコピー（呪文の詠唱）
- 機密は鍵アイコン：クリックで開錠 → もう一度でコピー（誤コピー防止）
- ★でピン留め → よく使う定型文を上に固定・「よく使う」タブに集約
- 各行の右に鉛筆(編集)・ゴミ箱(削除)アイコン
- 検索ボックス（全フォルダ横断トグル）/ プレースホルダ展開 / コピー演出
- ↑↓で選択・Enterでコピー・Escで検索クリア/最小化（キーボード操作）
- グローバルホットキーでウィンドウを最前面に呼び出し
- データはすべてローカルの templates.json に保存（オフライン完結）

Python + Tkinter / 単一ファイル / PyInstaller で .exe 化可能
"""

import json
import os
import queue
import re
import sys
import threading
import time
import webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "Grimoire"
APP_TITLE = "Grimoire（グリモワ）"
APP_VERSION = "1.2.0"
AUTHOR = "Subara3"
AUTHOR_URL = "https://subara3.com"
MAX_FOLDERS = 10

# テーマカラーのプリセット（設定で選択可）
PRESET_COLORS = [
    ("ターコイズ（デフォルト）", "#84CCD8"),
    ("紫", "#7E57C2"),
    ("藍", "#3F51B5"),
    ("青", "#1E88E5"),
    ("青緑", "#00897B"),
    ("緑", "#43A047"),
    ("桃", "#D81B60"),
    ("橙", "#EF6C00"),
    ("灰", "#546E7A"),
]
DEFAULT_ACCENT = PRESET_COLORS[0][1]


# ---------------------------------------------------------------------------
# データの保存場所（exe/スクリプトと同じ場所 → ポータブル運用）
# ---------------------------------------------------------------------------
def base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DATA_FILE = os.path.join(base_dir(), "templates.json")


def resource_path(name: str) -> str:
    """同梱リソース（アイコン等）のパス。exe では _MEIPASS から解決。"""
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", base_dir()), name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def center_window(win, parent):
    """子ウィンドウを親ウィンドウの中央に配置する。"""
    win.update_idletasks()
    w = win.winfo_width() or win.winfo_reqwidth()
    h = win.winfo_height() or win.winfo_reqheight()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    except tk.TclError:
        return
    x = px + max((pw - w) // 2, 0)
    y = py + max((ph - h) // 2, 0)
    win.geometry(f"+{x}+{y}")


def _lum(hex_color):
    """色の相対輝度（0=黒, 1=白）。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def darken(hex_color, factor):
    """色を factor だけ黒方向へ寄せる。"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*(1-factor)):02x}{int(g*(1-factor)):02x}{int(b*(1-factor)):02x}"


def fg_on(accent):
    """アクセント色の上に置く文字色（明るい色には濃い文字）。"""
    return "#FFFFFF" if _lum(accent) < 0.6 else "#1F2D33"


def text_on_white(accent):
    """白背景に置くアクセント文字色（明るすぎる色は暗くして可読性確保）。"""
    return accent if _lum(accent) < 0.55 else darken(accent, 0.5)


def dialog_accent(parent):
    return getattr(parent, "ACCENT", DEFAULT_ACCENT)


def add_dialog_header(win, accent, title):
    """ダイアログ上部にアクセント色のタイトル帯を付ける。"""
    fg = fg_on(accent)
    bar = tk.Frame(win, bg=accent)
    bar.pack(fill="x")
    tk.Label(bar, text=title, bg=accent, fg=fg,
             font=("Yu Gothic UI", 12, "bold"), padx=14, pady=8).pack(anchor="w")


def primary_button(parent_widget, accent, text, command):
    """アクセント色の主ボタン（tk.Button で確実に着色）。"""
    fg = fg_on(accent)
    return tk.Button(parent_widget, text=text, command=command, bg=accent, fg=fg,
                     activebackground=accent, activeforeground=fg, relief="flat",
                     bd=0, padx=16, pady=5, cursor="hand2",
                     font=("Yu Gothic UI", 10, "bold"))


DEFAULT_DATA = {
    "settings": {"hotkey": "ctrl+alt+space", "accent": DEFAULT_ACCENT, "confirm_delete": True},
    "folders": [
        {
            "name": "メール定型",
            "items": [
                {"title": "書き出し", "body": "お世話になっております。", "secret": False},
                {"title": "名乗り", "body": "○○と申します。", "secret": False},
                {"title": "結び", "body": "何卒よろしくお願いいたします。", "secret": False},
                {"title": "了承", "body": "承知いたしました。", "secret": False},
                {"title": "お礼", "body": "ご対応いただきありがとうございます。", "secret": False},
            ],
        },
        {
            "name": "個人情報",
            "items": [
                {"title": "メールアドレス", "body": "example@example.com", "secret": True},
                {"title": "住所", "body": "〒000-0000 ○○県○○市○○町0-0-0", "secret": True},
            ],
        },
    ],
}


def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "folders" in data:
                s = data.setdefault("settings", {})
                s.setdefault("hotkey", "ctrl+alt+space")
                s.setdefault("accent", DEFAULT_ACCENT)
                s.setdefault("confirm_delete", True)
                for folder in data["folders"]:
                    for item in folder.get("items", []):
                        item.setdefault("secret", False)
                        item.setdefault("pinned", False)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(DEFAULT_DATA))


def item_label(item: dict) -> str:
    """一覧に表示するラベル。タイトルが無ければ本文の先頭を使う。"""
    title = item.get("title", "").strip()
    if title:
        return title
    body = item.get("body", "").strip()
    if not body:
        return "(空の定型文)"
    first = body.splitlines()[0]
    return (first[:24] + "…") if len(first) > 24 else first


def save_data(data: dict) -> bool:
    """templates.json へ保存。外部から消されていても保存先を作り直し、
    一時ファイル経由の原子的書き込みで途中破損を防ぐ。"""
    try:
        d = os.path.dirname(DATA_FILE)
        if d:
            os.makedirs(d, exist_ok=True)
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_FILE)   # 同一ドライブ内では原子的に置換
        return True
    except OSError as e:
        messagebox.showerror(APP_NAME, f"保存に失敗しました:\n{e}")
        return False


# ---------------------------------------------------------------------------
# グローバルホットキー (Windows / ctypes・追加ライブラリ不要)
# ---------------------------------------------------------------------------
MOD_MAP = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4,
           "win": 0x8, "super": 0x8, "cmd": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

SPECIAL_VK = {
    "space": 0x20, "tab": 0x09, "enter": 0x0D, "return": 0x0D,
    "esc": 0x1B, "escape": 0x1B, "capslock": 0x14, "insert": 0x2D,
    "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21,
    "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
}


def parse_hotkey(text: str):
    """'ctrl+alt+s' -> (modifiers, vk)。失敗時 (None, None)。"""
    if not text:
        return None, None
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    mods, key = 0, None
    for p in parts:
        if p in MOD_MAP:
            mods |= MOD_MAP[p]
        else:
            key = p
    vk = _key_to_vk(key)
    if vk is None or mods == 0:
        return None, None
    return mods, vk


def _key_to_vk(key):
    if not key:
        return None
    if len(key) == 1:
        return ord(key.upper())  # A-Z, 0-9
    if key in SPECIAL_VK:
        return SPECIAL_VK[key]
    if key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)
    return None


class HotkeyManager:
    """別スレッドで Windows のグローバルホットキーを待ち受ける。"""

    def __init__(self, on_trigger):
        self.on_trigger = on_trigger
        self._thread = None
        self._thread_id = None
        self.active_hotkey = None

    @property
    def available(self):
        return sys.platform == "win32"

    def start(self, hotkey_text):
        if not self.available:
            return False
        mods, vk = parse_hotkey(hotkey_text)
        if mods is None:
            return False
        self.stop()
        self._thread = threading.Thread(
            target=self._run, args=(mods, vk, hotkey_text), daemon=True
        )
        self._thread.start()
        return True

    def _run(self, mods, vk, hotkey_text):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            self.active_hotkey = None
            return
        self.active_hotkey = hotkey_text

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY:
                try:
                    self.on_trigger()
                except Exception:
                    pass
        user32.UnregisterHotKey(None, 1)
        self.active_hotkey = None

    def stop(self):
        if self._thread and self._thread_id and self.available:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None


# ---------------------------------------------------------------------------
# 常駐トレイアイコン (Windows / ctypes・追加ライブラリ不要)
# ---------------------------------------------------------------------------
class TrayIcon:
    """Shell_NotifyIcon を ctypes で叩く常駐トレイ。別スレッドで動かす。
    - 左クリック / ダブルクリック → on_show
    - 右クリック → 「表示 / 終了」メニュー
    失敗しても例外を出さず available=False に倒す（その場合 ×=終了 にする）。"""

    WM_TRAY = 0x0400 + 1          # WM_USER+1（トレイからのコールバック）
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
    WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
    TPM_RETURNCMD, TPM_RIGHTBUTTON = 0x0100, 0x0002
    ID_SHOW, ID_QUIT = 1, 2

    def __init__(self, icon_path, tooltip, on_show, on_quit):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_show = on_show
        self.on_quit = on_quit
        self._thread = None
        self._thread_id = None
        self._wndproc = None     # GC されないよう参照を保持
        self._nid = None
        self._ok = False

    @property
    def available(self):
        return sys.platform == "win32" and self._ok

    def start(self):
        if sys.platform != "win32":
            return False
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(ready,), daemon=True)
        self._thread.start()
        ready.wait(timeout=2.0)
        return self._ok

    def _run(self, ready):
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            ready.set()
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32
        self._thread_id = kernel32.GetCurrentThreadId()

        LRESULT = ctypes.c_ssize_t
        WNDPROCTYPE = ctypes.WINFUNCTYPE(
            LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.DefWindowProcW.restype = LRESULT
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.LoadImageW.restype = wintypes.HANDLE

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD), ("szInfo", wintypes.WCHAR * 256),
                ("uVersion", wintypes.UINT), ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD), ("guidItem", ctypes.c_byte * 16),
                ("hBalloonIcon", wintypes.HICON),
            ]

        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT), ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
            ]

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == self.WM_TRAY:
                ev = lparam & 0xFFFF
                if ev in (self.WM_LBUTTONUP, self.WM_LBUTTONDBLCLK):
                    self._safe(self.on_show)
                elif ev == self.WM_RBUTTONUP:
                    self._popup_menu(user32, hwnd)
                return 0
            if msg == 0x0002:        # WM_DESTROY
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROCTYPE(wndproc)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASS()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "GrimoireTrayWnd"
        user32.RegisterClassW(ctypes.byref(wc))     # 失敗(既存)でも続行
        hwnd = user32.CreateWindowExW(0, wc.lpszClassName, self.tooltip,
                                      0, 0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            ready.set()
            return

        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
        hicon = user32.LoadImageW(None, self.icon_path, IMAGE_ICON, 0, 0,
                                  LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            hicon = user32.LoadIconW(None, ctypes.c_wchar_p(32512))   # IDI_APPLICATION

        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        nid.uCallbackMessage = self.WM_TRAY
        nid.hIcon = hicon
        nid.szTip = self.tooltip
        self._nid = nid
        self._user32 = user32
        self._shell32 = shell32
        if not shell32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(nid)):
            ready.set()
            return

        self._ok = True
        ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        shell32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(nid))
        user32.DestroyWindow(hwnd)

    def _popup_menu(self, user32, hwnd):
        import ctypes
        from ctypes import wintypes
        hmenu = user32.CreatePopupMenu()
        user32.AppendMenuW(hmenu, 0, self.ID_SHOW, "表示")
        user32.AppendMenuW(hmenu, 0, self.ID_QUIT, "終了")
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        cmd = user32.TrackPopupMenu(
            hmenu, self.TPM_RETURNCMD | self.TPM_RIGHTBUTTON, pt.x, pt.y, 0, hwnd, None)
        user32.DestroyMenu(hmenu)
        if cmd == self.ID_SHOW:
            self._safe(self.on_show)
        elif cmd == self.ID_QUIT:
            self._safe(self.on_quit)

    @staticmethod
    def _safe(fn):
        try:
            fn()
        except Exception:
            pass

    def stop(self):
        if self._thread_id and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            if self._thread:
                self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None
        self._ok = False


# ---------------------------------------------------------------------------
# 定型文の追加 / 編集ダイアログ
# ---------------------------------------------------------------------------
class TemplateDialog(tk.Toplevel):
    def __init__(self, parent, title="定型文", item=None):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.resizable(True, True)
        self.result = None
        accent = dialog_accent(parent)
        add_dialog_header(self, accent, title)

        item = item or {"title": "", "body": "", "secret": False}

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="タイトル（省略可・空なら本文の先頭を表示）").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value=item["title"])
        title_entry = ttk.Entry(frm, textvariable=self.title_var, width=40)
        title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 10))

        ttk.Label(frm, text="本文（{{date}} {{time}} や {{宛名}} を使うとコピー時に展開）").grid(
            row=2, column=0, sticky="w")
        self.body_text = tk.Text(frm, width=46, height=12, wrap="word")
        self.body_text.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(2, 6))
        self.body_text.insert("1.0", item["body"])

        self.secret_var = tk.BooleanVar(value=item.get("secret", False))
        ttk.Checkbutton(
            frm, text="鍵をかける（機密：コピーは2クリック必要）",
            variable=self.secret_var,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 10))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="キャンセル", command=self._cancel).pack(side="left", padx=(0, 6))
        primary_button(btns, accent, "保存", self._ok).pack(side="left")

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        title_entry.focus_set()
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self, parent)
        self.grab_set()
        parent.wait_window(self)

    def _ok(self):
        title = self.title_var.get().strip()
        body = self.body_text.get("1.0", "end-1c")
        if not title and not body.strip():
            messagebox.showwarning(APP_NAME, "本文かタイトルのどちらかは入力してください。", parent=self)
            return
        self.result = {"title": title, "body": body, "secret": self.secret_var.get()}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# プレースホルダ入力ダイアログ（{{宛名}} など任意トークン）
# ---------------------------------------------------------------------------
class PlaceholderDialog(tk.Toplevel):
    def __init__(self, parent, tokens):
        super().__init__(parent)
        self.transient(parent)
        self.title("プレースホルダの入力")
        self.resizable(False, False)
        self.result = None
        accent = dialog_accent(parent)
        add_dialog_header(self, accent, "プレースホルダの入力")

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="差し込む内容を入力してください").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self._vars = {}
        for i, tok in enumerate(tokens, start=1):
            ttk.Label(frm, text=f"{{{{{tok}}}}}").grid(row=i, column=0, sticky="e", padx=(0, 8), pady=3)
            var = tk.StringVar()
            ent = ttk.Entry(frm, textvariable=var, width=30)
            ent.grid(row=i, column=1, sticky="ew", pady=3)
            if i == 1:
                ent.focus_set()
            self._vars[tok] = var

        btns = ttk.Frame(frm)
        btns.grid(row=len(tokens) + 1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="キャンセル", command=self._cancel).pack(side="left", padx=(0, 6))
        primary_button(btns, accent, "OK", self._ok).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self, parent)
        self.grab_set()
        parent.wait_window(self)

    def _ok(self):
        self.result = {tok: var.get() for tok, var in self._vars.items()}
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# 設定ダイアログ（テーマカラー / ホットキー / 削除確認）
# ---------------------------------------------------------------------------
class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, accent, hotkey, confirm_delete):
        super().__init__(parent)
        self.transient(parent)
        self.title("設定")
        self.resizable(False, False)
        self.result = None
        accent = dialog_accent(parent)
        add_dialog_header(self, accent, "設定")

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="テーマカラー", font=("Yu Gothic UI", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self._names = [n for n, _ in PRESET_COLORS]
        self.color_var = tk.StringVar(
            value=next((n for n, c in PRESET_COLORS if c.lower() == accent.lower()), self._names[0]))
        combo = ttk.Combobox(frm, textvariable=self.color_var, values=self._names,
                             state="readonly", width=18)
        combo.grid(row=1, column=0, sticky="w")
        self.swatch = tk.Label(frm, width=4, bg=accent, relief="solid", borderwidth=1)
        self.swatch.grid(row=1, column=1, sticky="w", padx=8)
        combo.bind("<<ComboboxSelected>>", lambda e: self.swatch.config(bg=self._hex()))

        ttk.Label(frm, text="ホットキー（例: ctrl+alt+space, ctrl+f1）",
                  font=("Yu Gothic UI", 10, "bold")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(14, 4))
        self.hk_var = tk.StringVar(value=hotkey)
        ttk.Entry(frm, textvariable=self.hk_var, width=28).grid(
            row=3, column=0, columnspan=2, sticky="we")

        self.confirm_var = tk.BooleanVar(value=confirm_delete)
        ttk.Checkbutton(frm, text="削除の前に確認する", variable=self.confirm_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(14, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(btns, text="キャンセル", command=self._cancel).pack(side="left", padx=(0, 6))
        primary_button(btns, accent, "OK", self._ok).pack(side="left")

        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self, parent)
        self.grab_set()
        parent.wait_window(self)

    def _hex(self):
        return dict(PRESET_COLORS)[self.color_var.get()]

    def _ok(self):
        self.result = {
            "accent": self._hex(),
            "hotkey": self.hk_var.get().strip().lower(),
            "confirm_delete": self.confirm_var.get(),
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# 文字入力ダイアログ（テーマ反映）— フォルダ名変更など
# ---------------------------------------------------------------------------
class InputDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initial=""):
        super().__init__(parent)
        self.transient(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = None
        accent = dialog_accent(parent)
        add_dialog_header(self, accent, title)

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=prompt).pack(anchor="w", pady=(0, 6))
        self.var = tk.StringVar(value=initial)
        ent = ttk.Entry(frm, textvariable=self.var, width=30)
        ent.pack(fill="x")
        ent.focus_set()
        ent.select_range(0, "end")

        btns = ttk.Frame(frm)
        btns.pack(anchor="e", pady=(12, 0))
        ttk.Button(btns, text="キャンセル", command=self._cancel).pack(side="left", padx=(0, 6))
        primary_button(btns, accent, "OK", self._ok).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        center_window(self, parent)
        self.grab_set()
        parent.wait_window(self)

    def _ok(self):
        self.result = self.var.get().strip()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


# ---------------------------------------------------------------------------
# メインアプリ
# ---------------------------------------------------------------------------
class StamperApp(tk.Tk):
    ARM_TIMEOUT = 4.0          # 機密: 1回目から何秒以内に2回目をするか
    BG = "#F5F2FB"
    INK = "#3A2E5C"
    SUB = "#9A8FB0"
    ROW_BG = "#FFFFFF"
    SECRET_BG = "#FFF6EA"
    FAV_KEY = "fav"

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("560x650")
        self.minsize(470, 470)
        self.configure(bg=self.BG)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        self.data = load_data()
        # アクセント色（設定）から派生色を計算
        self.ACCENT = self.data.get("settings", {}).get("accent", DEFAULT_ACCENT)
        self._recolor_derived()

        self._armed = None
        self._armed_at = 0.0
        self._search = ""
        self._search_all = True    # 検索は常に全フォルダ横断（トグルは設けない）
        self._tip = None
        self._tip_after = None
        self._tab_menu_idx = None
        self._drag_from = None     # 行ドラッグ並び替えの掴み元（表示インデックス）
        self._reorderable = True   # 現在の表示が並び替え可能か
        self._current = 0          # 選択中フォルダの index
        self._fav = False          # 「よく使う」タブを表示中か
        self._tabdrag = None       # タブドラッグ状態
        self._tab_chips = []       # [(chip, key)] key は int か "fav"
        self._visible = []         # 現在表示中の [(fi, idx, item)]
        self._rows = []            # 現在表示中の行メタ [{frame, selbar, base}]
        self._sel = -1             # キーボード選択中の表示インデックス
        self._icons = self._load_icons()

        self._setup_style()

        self._hk_queue = queue.Queue()
        self.hotkeys = HotkeyManager(lambda: self._hk_queue.put(True))

        # 常駐トレイ（× で隠して常駐。クリック/メニューから復帰・終了）
        self._tray_queue = queue.Queue()
        self.tray = TrayIcon(resource_path("icon.ico"), APP_TITLE,
                             on_show=lambda: self._tray_queue.put("show"),
                             on_quit=lambda: self._tray_queue.put("quit"))

        self._tab_menu = tk.Menu(self, tearoff=0)
        self._tab_menu.add_command(label="フォルダを追加", command=self.add_folder)
        self._tab_menu.add_separator()
        self._tab_menu.add_command(label="名前を変更",
                                   command=lambda: self.rename_folder(self._tab_menu_idx))
        self._tab_menu.add_command(label="削除",
                                   command=lambda: self.delete_folder(self._tab_menu_idx))
        self._empty_tab_menu = tk.Menu(self, tearoff=0)
        self._empty_tab_menu.add_command(label="フォルダを追加", command=self.add_folder)

        self._build_menu()
        self._build_ui()
        self._bind_keys()
        self._render_tabbar()
        self._fill_rows()
        self._start_hotkey()
        self._tray_ok = self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._poll_events)
        self.after(100, lambda: self._search_entry.focus_set())

    # -- リソース・スタイル -------------------------------------------------
    def _load_icons(self):
        icons = {}
        for n in ("lock", "unlock", "gear", "edit", "delete", "search",
                  "blank", "grip", "star", "star_off"):
            try:
                icons[n] = tk.PhotoImage(file=resource_path(f"ui_{n}.png"))
            except Exception:
                icons[n] = None
        return icons

    def _recolor_derived(self):
        self.HOVER_BG = self._lighten(self.ACCENT, 0.80)
        self.ROW_BG_ALT = self._lighten(self.ACCENT, 0.96)
        self.ICON_HOVER = self._lighten(self.ACCENT, 0.72)
        self.TAB_STRIP = self._lighten(self.ACCENT, 0.90)

    @staticmethod
    def _tab_text(name, n=7):
        """タブ表示名。長い場合は … で省略（全名はデータに保持）。"""
        return name if len(name) <= n else name[:n] + "…"

    @staticmethod
    def _lighten(hex_color, factor):
        """色を factor（0=元色, 1=白）だけ白方向へ寄せる。"""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _setup_style(self):
        self._style = style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Yu Gothic UI", 10))

    def _apply_accent(self, color):
        self.ACCENT = color
        self._recolor_derived()
        for w in getattr(self, "_accent_widgets", []):
            try:
                w.config(bg=color)
            except tk.TclError:
                pass
        tw = text_on_white(color)
        for w in getattr(self, "_accent_fg_widgets", []):
            try:
                w.config(fg=tw)
            except tk.TclError:
                pass
        if getattr(self, "_status_bar", None) is not None:
            self._status_bar.config(bg=self._lighten(color, 0.85))
        self._render_tabbar()
        self._fill_rows()

    # -- メニューバー -------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self)

        fm = tk.Menu(menubar, tearoff=0)
        fm.add_command(label="フォルダを追加", command=self.add_folder)
        fm.add_command(label="フォルダ名を変更", command=lambda: self.rename_folder())
        fm.add_command(label="フォルダを削除", command=lambda: self.delete_folder())
        menubar.add_cascade(label="フォルダ", menu=fm)

        tm = tk.Menu(menubar, tearoff=0)
        tm.add_command(label="定型文を追加", command=self.add_item)
        tm.add_command(label="クリップボードから登録", command=self.add_from_clipboard)
        menubar.add_cascade(label="定型文", menu=tm)

        sm = tk.Menu(menubar, tearoff=0)
        sm.add_command(label="設定…", command=self.open_settings)
        menubar.add_cascade(label="設定", menu=sm)

        hm = tk.Menu(menubar, tearoff=0)
        hm.add_command(label="キーボード操作", command=self._shortcuts_help)
        hm.add_separator()
        hm.add_command(label=f"{AUTHOR} のサイト（{AUTHOR_URL}）",
                       command=lambda: webbrowser.open(AUTHOR_URL))
        hm.add_separator()
        hm.add_command(label="バージョン情報", command=self._about)
        menubar.add_cascade(label="ヘルプ", menu=hm)

        self.config(menu=menubar)

    def _make_chip(self, parent, text, command):
        """アクセント帯に置く白いボタン風ラベル。"""
        lbl = tk.Label(parent, text=text, bg="#FFFFFF", fg=text_on_white(self.ACCENT),
                       cursor="hand2", font=("Yu Gothic UI", 10, "bold"), padx=12, pady=6)
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>", lambda e: lbl.config(bg=self._lighten(self.ACCENT, 0.88)))
        lbl.bind("<Leave>", lambda e: lbl.config(bg="#FFFFFF"))
        self._accent_fg_widgets.append(lbl)
        return lbl

    def _shortcuts_help(self):
        win = tk.Toplevel(self)
        win.title("キーボード操作")
        win.resizable(False, False)
        win.transient(self)
        add_dialog_header(win, self.ACCENT, "キーボード操作")
        frm = ttk.Frame(win, padding=18)
        frm.pack(fill="both", expand=True)
        rows = [
            ("↑ / ↓", "選択する行を移動"),
            ("Enter", "選択中の行をコピー"),
            ("1 〜 9", "番号の行を即コピー（検索が空のとき）"),
            ("Esc", "検索を消す → もう一度で最小化"),
            ("ホットキー", "どこからでも最前面に呼び出し（設定で変更）"),
        ]
        for i, (k, v) in enumerate(rows):
            ttk.Label(frm, text=k, font=("Consolas", 10, "bold"), width=10).grid(
                row=i, column=0, sticky="w", pady=2)
            ttk.Label(frm, text=v).grid(row=i, column=1, sticky="w", pady=2)
        primary_button(frm, self.ACCENT, "閉じる", win.destroy).grid(
            row=len(rows), column=0, columnspan=2, sticky="e", pady=(14, 0))
        center_window(win, self)
        win.grab_set()

    def _about(self):
        win = tk.Toplevel(self)
        win.title("バージョン情報")
        win.resizable(False, False)
        win.transient(self)
        add_dialog_header(win, self.ACCENT, "バージョン情報")
        frm = ttk.Frame(win, padding=18)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=APP_TITLE, font=("Yu Gothic UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"v{APP_VERSION}", foreground=self.SUB).pack(anchor="w")
        ttk.Label(frm, text=f"作者: {AUTHOR}", font=("Yu Gothic UI", 10)).pack(
            anchor="w", pady=(10, 0))
        link = tk.Label(frm, text=AUTHOR_URL, fg="#1A0DAB", cursor="hand2",
                        font=("Yu Gothic UI", 10, "underline"))
        link.pack(anchor="w", pady=(2, 12))
        link.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_URL))
        primary_button(frm, self.ACCENT, "閉じる", win.destroy).pack(anchor="e")
        center_window(win, self)
        win.grab_set()

    def open_settings(self):
        s = self.data.setdefault("settings", {})
        dlg = SettingsDialog(self, self.ACCENT, s.get("hotkey", ""),
                             s.get("confirm_delete", True))
        if not dlg.result:
            return
        r = dlg.result
        if r["hotkey"]:
            mods, _ = parse_hotkey(r["hotkey"])
            if mods is None:
                messagebox.showwarning(APP_NAME, "ホットキーの形式が正しくありません（色などは保存します）。")
            else:
                s["hotkey"] = r["hotkey"]
                if self.hotkeys.available:
                    self.hotkeys.start(r["hotkey"])
        s["confirm_delete"] = r["confirm_delete"]
        s["accent"] = r["accent"]
        save_data(self.data)
        self._apply_accent(r["accent"])
        self.status.set("設定を更新しました")

    # -- UI構築 -------------------------------------------------------------
    def _build_ui(self):
        # ヘッダー＝ツールバー（アクセント帯）。名前はタイトルバーにあるので置かない。
        header = tk.Frame(self, bg=self.ACCENT)
        header.pack(fill="x")
        self._accent_widgets = [header]
        self._accent_fg_widgets = []

        # 左：意味のあるボタン（白いチップ）
        self._make_chip(header, "＋ 定型文を追加", self.add_item).pack(
            side="left", padx=(12, 6), pady=10)
        self._make_chip(header, "クリップボードから登録", self.add_from_clipboard).pack(
            side="left", pady=10)

        # 右：検索（大きめ・常に全フォルダ横断）。文字があれば ✕ で消せる。
        self._search_var = tk.StringVar()
        sframe = tk.Frame(header, bg="#FFFFFF")
        sframe.pack(side="right", padx=(6, 12), pady=10)
        sicon = self._icons.get("search")
        if sicon is not None:
            tk.Label(sframe, image=sicon, bg="#FFFFFF").pack(side="left", padx=(8, 0))
        self._search_entry = tk.Entry(sframe, textvariable=self._search_var, width=24,
                                      relief="flat", bg="#FFFFFF", font=("Yu Gothic UI", 11))
        self._search_entry.pack(side="left", padx=6, ipady=5)
        self._clear_btn = tk.Label(sframe, text="✕", bg="#FFFFFF", fg=self.SUB,
                                   cursor="hand2", font=("Yu Gothic UI", 10, "bold"), padx=2)
        self._clear_btn.bind("<Button-1>", lambda e: self._clear_search())
        self._clear_btn.bind("<Enter>", lambda e: self._clear_btn.config(fg=self.INK))
        self._clear_btn.bind("<Leave>", lambda e: self._clear_btn.config(fg=self.SUB))
        self._search_var.trace_add("write", lambda *a: self._on_search())

        # フォルダのタブ（自前タブバー：ドラッグ並び替え・折り返し・上線つき）
        self._tabbar = tk.Frame(self, bg=self.TAB_STRIP)
        self._tabbar.pack(fill="x", padx=8, pady=(8, 0))
        self._tabbar.bind("<Double-Button-1>", lambda e: self.add_folder())
        self._tabbar.bind("<Button-3>", self._on_tabbar_right)
        self._tabbar.bind("<Configure>", self._on_tabbar_configure)
        self._last_tabbar_w = 0

        # 定型文リスト（単一のスクロール領域。タブ選択で中身を入れ替える）
        content = tk.Frame(self, bg=self.ROW_BG)
        content.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._canvas, self._inner = self._make_scroller(content)

        # ステータスバー
        self.status = tk.StringVar(
            value="クリック / Enter でコピー ・ ↑↓ で選択 ・ 1〜9 で即コピー ・ Esc で隠す")
        self._status_bar = tk.Label(self, textvariable=self.status, anchor="w",
                                     bg=self._lighten(self.ACCENT, 0.85), fg=self.INK,
                                     font=("Yu Gothic UI", 9), padx=8, pady=3)
        self._status_bar.pack(fill="x", side="bottom")

    def _clear_search(self):
        self._search_var.set("")
        self._search_entry.focus_set()

    # -- キーボード操作 -----------------------------------------------------
    def _bind_keys(self):
        ent = self._search_entry
        ent.bind("<Up>", lambda e: self._key_nav(-1))
        ent.bind("<Down>", lambda e: self._key_nav(1))
        ent.bind("<Return>", lambda e: self._key_activate())
        ent.bind("<Escape>", lambda e: self._key_escape())
        ent.bind("<Key>", self._entry_digit)

        self.bind("<Up>", lambda e: self._key_nav(-1))
        self.bind("<Down>", lambda e: self._key_nav(1))
        self.bind("<Return>", lambda e: self._key_activate())
        self.bind("<Escape>", lambda e: self._key_escape())
        self.bind("<Key>", self._win_digit)

    def _entry_digit(self, event):
        # 検索が空のときだけ 1〜9 を「即コピー」に使う（入力させない）。
        if event.char in "123456789" and self._search.strip() == "":
            self._copy_index(int(event.char))
            return "break"
        return None

    def _win_digit(self, event):
        if (event.char in "123456789" and self._search.strip() == ""
                and self.focus_get() is not self._search_entry):
            self._copy_index(int(event.char))
            return "break"
        return None

    def _key_nav(self, d):
        if not self._visible:
            return "break"
        self._sel = (self._sel + d) % len(self._visible)
        self._paint_sel()
        self._ensure_visible(self._sel)
        return "break"

    def _key_activate(self):
        if 0 <= self._sel < len(self._visible):
            fi, idx, _ = self._visible[self._sel]
            self._row_click(fi, idx)
        return "break"

    def _key_escape(self):
        if self._search_var.get():
            self._search_var.set("")
        else:
            self.iconify()
        return "break"

    def _copy_index(self, n):
        i = n - 1
        if 0 <= i < len(self._visible):
            self._sel = i
            self._paint_sel()
            fi, idx, _ = self._visible[i]
            self._row_click(fi, idx)

    # -- 自前タブバー（フォルダ） -------------------------------------------
    def _has_pins(self):
        return any(it.get("pinned") for f in self.data["folders"] for it in f["items"])

    def _render_tabbar(self):
        if getattr(self, "_rendering", False):
            return
        self._rendering = True
        try:
            for w in self._tabbar.winfo_children():
                w.destroy()
            self._tab_chips = []
            self._tabbar.config(bg=self.TAB_STRIP)

            entries = []
            if self._has_pins():
                entries.append((self.FAV_KEY, None))
            for idx, folder in enumerate(self.data["folders"]):
                entries.append((idx, folder))

            created = []
            for key, folder in entries:
                created.append((self._make_tab_chip(key, folder), key))
            plus = self._make_plus_chip()
            self.update_idletasks()

            avail = self._tabbar.winfo_width()
            if avail <= 1:
                avail = max(self.winfo_width() - 16, 320)
            heights = [c.winfo_reqheight() for c, _ in created] + [plus.winfo_reqheight(), 28]
            rowh = max(heights) + 4
            gap, x, y = 3, 0, 0
            for chip, key in created:
                w = chip.winfo_reqwidth()
                if x > 0 and x + w > avail:
                    y += 1
                    x = 0
                chip.place(x=x, y=y * rowh)
                self._tab_chips.append((chip, key))
                x += w + gap
            pw = plus.winfo_reqwidth()
            if x > 0 and x + pw > avail:
                y += 1
                x = 0
            plus.place(x=x, y=y * rowh)
            self._tabbar.config(height=(y + 1) * rowh)
        finally:
            self._rendering = False

    def _is_selected_key(self, key):
        if key == self.FAV_KEY:
            return self._fav
        return (not self._fav) and key == self._current

    def _make_tab_chip(self, key, folder):
        sel = self._is_selected_key(key)
        strip = self.TAB_STRIP
        chip = tk.Frame(self._tabbar, bg=strip, cursor="hand2")
        top = tk.Frame(chip, bg=(self.ACCENT if sel else strip), height=3)
        top.pack(fill="x")
        lblbg = self.ROW_BG if sel else strip
        fg = text_on_white(self.ACCENT) if sel else self.SUB
        font = ("Yu Gothic UI", 10, "bold" if sel else "normal")
        if key == self.FAV_KEY:
            lbl = tk.Label(chip, text=" お気に入り", image=self._icons.get("star"),
                           compound="left", bg=lblbg, fg=fg, padx=12, pady=6, font=font)
        else:
            lbl = tk.Label(chip, text=self._tab_text(folder["name"]),
                           bg=lblbg, fg=fg, padx=14, pady=6, font=font)
        lbl.pack(fill="both", expand=True)

        for w in (chip, lbl):
            w.bind("<ButtonPress-1>", lambda e, k=key: self._tab_press(e, k))
            w.bind("<B1-Motion>", self._tab_motion)
            w.bind("<ButtonRelease-1>", self._tab_release)
            if key != self.FAV_KEY:
                w.bind("<Double-Button-1>", lambda e, k=key: self.rename_folder(k))
                w.bind("<Button-3>", lambda e, k=key: self._tab_context(e, k))
        if not sel:
            lbl.bind("<Enter>",
                     lambda e, l=lbl: l.config(bg=self._lighten(self.ACCENT, 0.82)), add="+")
            lbl.bind("<Leave>", lambda e, l=lbl: l.config(bg=strip), add="+")
        chip._lbl = lbl
        chip._top = top
        chip._key = key
        return chip

    def _make_plus_chip(self):
        plus = tk.Label(self._tabbar, text="＋", bg=self.TAB_STRIP,
                        fg=text_on_white(self.ACCENT), cursor="hand2",
                        font=("Yu Gothic UI", 13, "bold"), padx=8, pady=4)
        plus.bind("<Button-1>", lambda e: self.add_folder())
        plus.bind("<Enter>", lambda e: plus.config(bg=self._lighten(self.ACCENT, 0.78)))
        plus.bind("<Leave>", lambda e: plus.config(bg=self.TAB_STRIP))
        return plus

    def _restyle_tabs(self):
        """チップを破棄せず色だけ更新（破棄するとダブルクリックが消える）。"""
        strip = self.TAB_STRIP
        for chip, key in self._tab_chips:
            try:
                if not chip.winfo_exists():
                    continue
                sel = self._is_selected_key(key)
                chip._top.config(bg=self.ACCENT if sel else strip)
                chip._lbl.config(
                    bg=self.ROW_BG if sel else strip,
                    fg=text_on_white(self.ACCENT) if sel else self.SUB,
                    font=("Yu Gothic UI", 10, "bold" if sel else "normal"))
            except tk.TclError:
                continue

    def _select_key(self, key):
        if key == self.FAV_KEY:
            self._fav = True
        else:
            if key is None or key < 0 or key >= len(self.data["folders"]):
                return
            self._fav = False
            self._current = key
        self._disarm()
        self._restyle_tabs()
        self._fill_rows()

    def _on_tabbar_configure(self, event):
        if getattr(self, "_rendering", False):
            return
        if abs(event.width - self._last_tabbar_w) > 4:
            self._last_tabbar_w = event.width
            self._render_tabbar()

    def _on_tabbar_right(self, event):
        try:
            self._empty_tab_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._empty_tab_menu.grab_release()

    def _tab_context(self, event, idx):
        self._tab_menu_idx = idx
        try:
            self._tab_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._tab_menu.grab_release()

    def _tab_press(self, event, key):
        self._tabdrag = {"key": key, "x0": event.x_root, "moved": False}

    def _tab_motion(self, event):
        d = self._tabdrag
        if d and abs(event.x_root - d["x0"]) > 6:
            d["moved"] = True

    def _tab_release(self, event):
        d = self._tabdrag
        self._tabdrag = None
        if not d:
            return
        if not d["moved"]:
            self._select_key(d["key"])
            return
        if d["key"] == self.FAV_KEY:
            return
        target = self._tab_target_index(event.x_root, event.y_root)
        if target is None or target == d["key"]:
            return
        folders = self.data["folders"]
        f = folders.pop(d["key"])
        if target > d["key"]:
            target -= 1
        folders.insert(target, f)
        save_data(self.data)
        self._current = target
        self._fav = False
        self._render_tabbar()
        self._fill_rows()
        self.status.set(f"フォルダを並び替えました → {f['name']}")

    def _tab_target_index(self, x_root, y_root):
        for chip, key in self._tab_chips:
            if key == self.FAV_KEY:
                continue
            try:
                l = chip.winfo_rootx()
                t = chip.winfo_rooty()
                r = l + chip.winfo_width()
                b = t + chip.winfo_height()
            except tk.TclError:
                continue
            if l <= x_root < r and t <= y_root < b:
                return key
        return None

    def _make_scroller(self, parent):
        container = tk.Frame(parent, bg=self.ROW_BG)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=self.ROW_BG, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=self.ROW_BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def refresh_region(_=None):
            # 内容がビューより短いときは canvas の高さまで内部を広げ、
            # 余白への過剰スクロールを防ぐ。長いときは内容高でスクロール可能に。
            ch = canvas.winfo_height()
            need = inner.winfo_reqheight()
            canvas.itemconfigure(win, height=max(need, ch))
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(need, ch)))
            if need <= ch:                       # 収まるならスクロールバーを隠す
                sb.pack_forget()
                canvas.yview_moveto(0)
            elif not sb.winfo_ismapped():
                sb.pack(side="right", fill="y")

        inner.bind("<Configure>", refresh_region)
        canvas.bind("<Configure>",
                    lambda e: (canvas.itemconfigure(win, width=e.width), refresh_region()))

        def wheel(e):
            # 内容がビュー以下のときはスクロールしない
            if inner.winfo_reqheight() <= canvas.winfo_height():
                return
            canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        return canvas, inner

    # -- 表示する行の収集 ---------------------------------------------------
    def _collect_entries(self):
        q = self._search.strip().lower()
        if self._fav:
            entries = [(fi, idx, it)
                       for fi, f in enumerate(self.data["folders"])
                       for idx, it in enumerate(f["items"]) if it.get("pinned")]
        elif self._search_all and q:
            entries = [(fi, idx, it)
                       for fi, f in enumerate(self.data["folders"])
                       for idx, it in enumerate(f["items"])]
        else:
            fi = self._current_folder_index()
            if fi is None:
                return []
            entries = [(fi, idx, it)
                       for idx, it in enumerate(self.data["folders"][fi]["items"])]
        if q:
            entries = [e for e in entries
                       if q in item_label(e[2]).lower() or q in e[2].get("body", "").lower()]
        if not self._fav:
            # ピン留めを上へ（安定ソートで同グループ内の手動並びは維持）
            entries.sort(key=lambda e: 0 if e[2].get("pinned") else 1)
        return entries

    def _fill_rows(self, *_):
        if self._fav and not self._has_pins():
            self._fav = False
            self._restyle_tabs()
        canvas, inner = self._canvas, self._inner
        for w in inner.winfo_children():
            w.destroy()

        entries = self._collect_entries()
        self._visible = entries
        self._rows = []
        q = self._search.strip()
        show_folder = self._fav or (self._search_all and bool(q))
        badges = (q == "")
        self._reorderable = (not self._fav) and (not (self._search_all and q)) and (q == "")

        for j, (fi, idx, item) in enumerate(entries):
            badge = (j + 1) if (badges and j < 9) else None
            fname = self.data["folders"][fi]["name"] if show_folder else None
            self._make_row(inner, fi, idx, item, j, badge=badge, folder_name=fname)

        if not entries:
            if q:
                msg = "一致する定型文がありません"
            elif self._fav:
                msg = "お気に入りに登録した定型文がここに集まります（★で登録）"
            else:
                msg = "まだ定型文がありません（上の＋／ボタンから追加）"
            tk.Label(inner, text=msg, bg=self.ROW_BG, fg=self.SUB,
                     font=("Yu Gothic UI", 10), pady=24).pack(fill="x")

        self._sel = 0 if entries else -1
        self._paint_sel()
        canvas.yview_moveto(0)

    def _make_row(self, parent, fi, idx, item, rownum, badge=None, folder_name=None):
        secret = item.get("secret")
        pinned = item.get("pinned")
        base = self.SECRET_BG if secret else (self.ROW_BG if rownum % 2 == 0 else self.ROW_BG_ALT)
        row = tk.Frame(parent, bg=base)
        row.pack(fill="x", padx=6, pady=3)

        # キーボード選択を示す左端のバー（ホバーとは独立して着色しない）
        selbar = tk.Frame(row, bg=base, width=4)
        selbar.pack(side="left", fill="y")

        copy_targets = [row]    # クリックでコピーする領域
        recolor = [row]         # ホバー時に一緒に着色する領域（行全体）

        # 番号バッジ（検索が空のとき先頭9件）
        if badge is not None:
            bd = tk.Label(row, text=str(badge), bg=base, fg=text_on_white(self.ACCENT),
                          font=("Yu Gothic UI", 9, "bold"), width=2)
            bd.pack(side="left", padx=(4, 0), pady=8)
            copy_targets.append(bd)
            recolor.append(bd)

        # ドラッグ・グリップ（左端を摘んで並び替え）
        grip = tk.Label(row, bg=base, cursor="fleur")
        gimg = self._icons.get("grip")
        if gimg is not None:
            grip.config(image=gimg)
        else:
            grip.config(text="⋮", fg=self.SUB, font=("Yu Gothic UI", 12))
        grip.pack(side="left", padx=(4, 2), pady=8)
        grip.bind("<ButtonPress-1>", lambda e, j=rownum: self._drag_start(j))
        grip.bind("<B1-Motion>", self._drag_motion)
        grip.bind("<ButtonRelease-1>", self._drag_end)
        recolor.append(grip)

        # 鍵アイコン（機密のみ。開錠中は unlock）
        lk = tk.Label(row, bg=base)
        if secret:
            armed = self._armed == (fi, idx)
            img = self._icons.get("unlock" if armed else "lock")
            if img is not None:
                lk.config(image=img)
            else:
                lk.config(text="鍵", fg="#B8860B", font=("Yu Gothic UI", 10, "bold"))
        else:
            blank = self._icons.get("blank")
            if blank is not None:
                lk.config(image=blank)
        lk.pack(side="left", padx=(2, 4), pady=8)
        copy_targets.append(lk)
        recolor.append(lk)

        # 右側アクション（pack rightは右→左：delete→edit＝表示は edit, delete）
        del_lbl = self._icon_button(row, base, "delete",
                                    lambda e, f=fi, i=idx: self.delete_item(f, i), fallback="削除")
        edit_lbl = self._icon_button(row, base, "edit",
                                     lambda e, f=fi, i=idx: self.edit_item(f, i), fallback="編集")
        recolor += [del_lbl, edit_lbl]

        # タイトル行：★お気に入り ＋ タイトル（太字）／その下に本文の冒頭（薄字）
        title_text = item.get("title", "").strip()
        body = item.get("body", "")
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        line1 = title_text or first or "(空の定型文)"
        line2 = first if title_text else ""

        tarea = tk.Frame(row, bg=base)
        tarea.pack(side="left", fill="x", expand=True, pady=5)
        row1 = tk.Frame(tarea, bg=base)
        row1.pack(fill="x", anchor="w")

        star = tk.Label(row1, bg=base, cursor="hand2")
        simg = self._icons.get("star" if pinned else "star_off")
        if simg is not None:
            star.config(image=simg)
        else:
            star.config(text="★" if pinned else "☆",
                        fg="#C6921E" if pinned else self.SUB, font=("Yu Gothic UI", 11))
        star.pack(side="left", padx=(0, 5))
        star.bind("<Button-1>", lambda e, f=fi, i=idx: self._toggle_pin(f, i))

        title = tk.Label(row1, text=line1, bg=base, fg=self.INK,
                         font=("Yu Gothic UI", 11, "bold"), anchor="w")
        title.pack(side="left")
        copy_targets += [tarea, row1, title]
        recolor += [tarea, row1, title, star]

        sub_parts = []
        if folder_name:
            sub_parts.append(f"［{folder_name}］")
        if line2:
            sub_parts.append(line2 if len(line2) <= 42 else line2[:42] + "…")
        if sub_parts:
            sub = tk.Label(tarea, text=" ".join(sub_parts), bg=base, fg=self.SUB,
                           font=("Yu Gothic UI", 9), anchor="w")
            sub.pack(fill="x", anchor="w")
            copy_targets.append(sub)
            recolor.append(sub)

        for w in copy_targets:
            w.bind("<Button-1>", lambda e, f=fi, i=idx: self._row_click(f, i))

        self._wire_hover(row, recolor, grip, item, base)
        self._rows.append({"frame": row, "selbar": selbar, "base": base})
        return row

    def _icon_button(self, row, base, icon_name, command, fallback="", enabled=True):
        lbl = tk.Label(row, bg=base)
        img = self._icons.get(icon_name)
        if not enabled:
            blank = self._icons.get("blank")
            if blank is not None:
                lbl.config(image=blank)
            else:
                lbl.config(text="　", font=("Yu Gothic UI", 9))
            lbl.pack(side="right", padx=(2, 8), pady=8)
            return lbl
        lbl.config(cursor="hand2")
        if img is not None:
            lbl.config(image=img)
        else:
            lbl.config(text=fallback, fg=self.SUB, font=("Yu Gothic UI", 9))
        lbl.pack(side="right", padx=(2, 8), pady=8)
        lbl.bind("<Button-1>", command)
        return lbl

    # -- キーボード選択の描画 -----------------------------------------------
    def _paint_sel(self):
        for j, meta in enumerate(self._rows):
            try:
                meta["selbar"].config(bg=self.ACCENT if j == self._sel else meta["base"])
            except tk.TclError:
                pass

    def _ensure_visible(self, j):
        if not (0 <= j < len(self._rows)):
            return
        canvas = self._canvas
        inner = self._inner
        inner.update_idletasks()
        total = inner.winfo_height()
        ch = canvas.winfo_height()
        if total <= ch:
            return
        frame = self._rows[j]["frame"]
        y = frame.winfo_y()
        h = frame.winfo_height()
        top = canvas.canvasy(0)
        if y < top:
            canvas.yview_moveto(max(y - 4, 0) / total)
        elif y + h > top + ch:
            canvas.yview_moveto((y + h - ch + 4) / total)

    # -- ホバー（行全体を一様に着色＋全文ツールチップ） ----------------------
    def _wire_hover(self, row, recolor, grip, item, base):
        def enter(e):
            for w in recolor:
                try:
                    w.config(bg=self.HOVER_BG)
                except tk.TclError:
                    pass
            if e.widget is grip:        # ハンドル上ではヒントを出さない
                self._hide_tip()
            else:
                self._schedule_tip(item)

        def check_leave():
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
            inside = w is not None and (w is row or str(w).startswith(str(row) + "."))
            if not inside:
                for ww in recolor:
                    try:
                        ww.config(bg=base)
                    except tk.TclError:
                        pass
                self._hide_tip()

        def leave(e):
            self.after(1, check_leave)

        for w in recolor:
            w.bind("<Enter>", enter, add="+")
            w.bind("<Leave>", leave, add="+")

    def _schedule_tip(self, item):
        self._cancel_tip()
        body = item.get("body", "")
        text = body if body.strip() else "（本文なし）"
        self._tip_after = self.after(450, lambda: self._show_tip(text))

    def _show_tip(self, text):
        self._hide_tip()
        x, y = self.winfo_pointerxy()
        tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x + 16}+{y + 18}")
        tk.Label(tw, text=text, justify="left", anchor="w", background="#FFFBE6",
                 foreground="#222", relief="solid", borderwidth=1,
                 font=("Yu Gothic UI", 10), wraplength=380, padx=8, pady=6).pack()
        self._tip = tw

    def _cancel_tip(self):
        if self._tip_after:
            self.after_cancel(self._tip_after)
            self._tip_after = None

    def _hide_tip(self):
        self._cancel_tip()
        if self._tip:
            self._tip.destroy()
            self._tip = None

    # -- 現在フォルダ -------------------------------------------------------
    def _current_folder_index(self):
        if not self.data["folders"]:
            return None
        return max(0, min(self._current, len(self.data["folders"]) - 1))

    # -- クリック動作 -------------------------------------------------------
    def _row_click(self, fi, idx):
        item = self.data["folders"][fi]["items"][idx]
        if not item.get("secret"):
            self._do_copy(item)
            return
        now = time.time()
        if self._armed == (fi, idx) and (now - self._armed_at) <= self.ARM_TIMEOUT:
            self._do_copy(item)
            self._disarm()
            self._fill_rows()          # 再施錠表示
        else:
            self._armed = (fi, idx)
            self._armed_at = now
            self.status.set(f"鍵付き：もう一度クリック / Enter でコピー → {item_label(item)}")
            self._fill_rows()          # 開錠アイコンへ

    def _do_copy(self, item):
        text = self._expand_placeholders(item.get("body", ""))
        if text is None:
            return  # プレースホルダ入力がキャンセルされた
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.status.set(f"コピーしました → {item_label(item)}")
        self._toast("コピー！")

    def _expand_placeholders(self, body):
        tokens = re.findall(r"\{\{(.+?)\}\}", body)
        if not tokens:
            return body
        now = datetime.now()
        builtin = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "datetime": now.strftime("%Y-%m-%d %H:%M"),
        }
        values = dict(builtin)
        custom = [t for t in dict.fromkeys(tokens) if t.lower() not in builtin]
        if custom:
            dlg = PlaceholderDialog(self, custom)
            if dlg.result is None:
                return None
            values.update(dlg.result)

        def sub(m):
            key = m.group(1)
            if key in values:
                return values[key]
            return values.get(key.lower(), m.group(0))

        return re.sub(r"\{\{(.+?)\}\}", sub, body)

    def _toast(self, text):
        x, y = self.winfo_pointerxy()
        tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.configure(bg=self.ACCENT)
        tk.Label(tw, text=text, bg=self.ACCENT, fg=fg_on(self.ACCENT),
                 font=("Yu Gothic UI", 10, "bold"), padx=12, pady=6).pack()
        tw.wm_geometry(f"+{x + 12}+{y - 36}")
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.after(700, tw.destroy)

    def _disarm(self):
        self._armed = None
        self._armed_at = 0.0

    # -- 検索 ---------------------------------------------------------------
    def _on_search(self):
        self._search = self._search_var.get()
        if self._search:
            if not self._clear_btn.winfo_ismapped():
                self._clear_btn.pack(side="left", padx=(0, 6))
        else:
            self._clear_btn.pack_forget()
        self._fill_rows()

    # -- ホットキー ---------------------------------------------------------
    def _start_hotkey(self):
        hk = self.data.get("settings", {}).get("hotkey", "")
        if not self.hotkeys.available:
            return
        ok = self.hotkeys.start(hk)
        if not ok and hk:
            self.status.set(f"ホットキー「{hk}」を登録できませんでした（他アプリと競合の可能性）")

    def _poll_events(self):
        try:
            while True:
                self._hk_queue.get_nowait()
                self._summon()
        except queue.Empty:
            pass
        try:
            while True:
                cmd = self._tray_queue.get_nowait()
                if cmd == "show":
                    self._summon()
                elif cmd == "quit":
                    self._quit()
                    return
        except queue.Empty:
            pass
        self.after(120, self._poll_events)

    def _on_close(self):
        # × はトレイに隠す（トレイが使えないときだけ終了）
        if getattr(self, "_tray_ok", False) and self.tray.available:
            self.withdraw()
            if not getattr(self, "_told_tray", False):
                self._told_tray = True
                self.status.set("トレイに常駐しました（アイコンのクリック / ホットキーで再表示）")
        else:
            self._quit()

    def _quit(self):
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        self.destroy()

    def _summon(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(250, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self._search_entry.focus_set()
        self._search_entry.select_range(0, "end")

    # -- フォルダ操作 -------------------------------------------------------
    def add_folder(self):
        if len(self.data["folders"]) >= MAX_FOLDERS:
            messagebox.showinfo(APP_NAME, f"フォルダは最大{MAX_FOLDERS}個までです。")
            return
        # 既定名「新しいフォルダ」。重複したら（1）（2）…と採番（プロンプト無し）
        base = "新しいフォルダ"
        existing = {f["name"] for f in self.data["folders"]}
        name, i = base, 1
        while name in existing:
            name = f"{base}（{i}）"
            i += 1
        self.data["folders"].append({"name": name, "items": []})
        save_data(self.data)
        self._fav = False
        self._current = len(self.data["folders"]) - 1
        self._render_tabbar()
        self._fill_rows()
        self.status.set(f"「{name}」を追加（タブをダブルクリックで名前変更）")

    def rename_folder(self, idx=None):
        if idx is None or idx == self.FAV_KEY:
            idx = self._current_folder_index()
        if idx is None:
            return
        old = self.data["folders"][idx]["name"]
        dlg = InputDialog(self, "フォルダ名を変更", "新しいフォルダ名", old)
        name = dlg.result
        if not name:
            return
        self.data["folders"][idx]["name"] = name
        save_data(self.data)
        self._render_tabbar()

    def delete_folder(self, idx=None):
        if idx is None or idx == self.FAV_KEY:
            idx = self._current_folder_index()
        if idx is None:
            return
        if len(self.data["folders"]) <= 1:
            messagebox.showinfo(APP_NAME, "フォルダは最低一個必要です。")
            return
        name = self.data["folders"][idx]["name"]
        if not messagebox.askyesno(APP_NAME, f"フォルダ「{name}」を中の定型文ごと削除しますか？"):
            return
        del self.data["folders"][idx]
        if self._current >= len(self.data["folders"]):
            self._current = len(self.data["folders"]) - 1
        save_data(self.data)
        self._fav = False
        self._render_tabbar()
        self._fill_rows()

    # -- 定型文操作 ---------------------------------------------------------
    def add_item(self):
        fi = self._current_folder_index()
        if fi is None:
            messagebox.showinfo(APP_NAME, "先にフォルダを作成してください。")
            return
        dlg = TemplateDialog(self, title="定型文を追加")
        if dlg.result:
            dlg.result.setdefault("pinned", False)
            self.data["folders"][fi]["items"].append(dlg.result)
            save_data(self.data)
            self._fav = False
            self._restyle_tabs()
            self._fill_rows()
            self.status.set(f"追加しました → {item_label(dlg.result)}")

    def add_from_clipboard(self):
        fi = self._current_folder_index()
        if fi is None:
            messagebox.showinfo(APP_NAME, "先にフォルダを作成してください。")
            return
        try:
            text = self.clipboard_get()
        except tk.TclError:
            text = ""
        if not text.strip():
            messagebox.showinfo(APP_NAME, "クリップボードが空です。")
            return
        dlg = TemplateDialog(self, title="クリップボードから登録",
                             item={"title": "", "body": text, "secret": False})
        if dlg.result:
            dlg.result.setdefault("pinned", False)
            self.data["folders"][fi]["items"].append(dlg.result)
            save_data(self.data)
            self._fav = False
            self._restyle_tabs()
            self._fill_rows()
            self.status.set(f"登録しました → {item_label(dlg.result)}")

    def edit_item(self, fi, idx):
        item = self.data["folders"][fi]["items"][idx]
        dlg = TemplateDialog(self, title="定型文を編集", item=item)
        if dlg.result:
            dlg.result["pinned"] = item.get("pinned", False)
            self.data["folders"][fi]["items"][idx] = dlg.result
            save_data(self.data)
            self._fill_rows()
            self.status.set(f"更新しました → {item_label(dlg.result)}")

    def _toggle_pin(self, fi, idx):
        item = self.data["folders"][fi]["items"][idx]
        item["pinned"] = not item.get("pinned")
        save_data(self.data)
        self._render_tabbar()        # 「よく使う」タブの出現/消滅に追従
        self._fill_rows()
        self.status.set(
            ("お気に入りに追加 → " if item["pinned"] else "お気に入りから外しました → ")
            + item_label(item))

    # -- ドラッグ並び替え（表示インデックスで操作） --------------------------
    def _drag_start(self, vj):
        if not self._reorderable:
            self._drag_from = None
            self.status.set("並び替えは通常表示（検索なし・このフォルダ）のときだけできます")
            return
        self._drag_from = vj

    def _drag_motion(self, event):
        if self._drag_from is None:
            return
        t = self._row_target_index(event.y_root)
        if t is not None and 0 <= t < len(self._visible):
            self.status.set(f"ここへ移動 → {item_label(self._visible[t][2])}")

    def _drag_end(self, event):
        if self._drag_from is None:
            return
        fj = self._drag_from
        self._drag_from = None
        tj = self._row_target_index(event.y_root)
        if tj is None or tj == fj:
            self._fill_rows()
            return
        fi = self._visible[fj][0]
        items = self.data["folders"][fi]["items"]
        order = [v[1] for v in self._visible]   # data index を表示順に
        moved = order.pop(fj)
        if tj > fj:
            tj -= 1
        order.insert(tj, moved)
        items[:] = [items[k] for k in order]
        save_data(self.data)
        self._fill_rows()
        self.status.set("並び替えました")

    def _row_target_index(self, y_root):
        rows = self._rows
        for j, meta in enumerate(rows):
            try:
                top = meta["frame"].winfo_rooty()
                bot = top + meta["frame"].winfo_height()
            except tk.TclError:
                continue
            if top <= y_root < bot:
                return j
        if rows:
            try:
                if y_root < rows[0]["frame"].winfo_rooty():
                    return 0
            except tk.TclError:
                pass
            return len(rows) - 1
        return None

    def delete_item(self, fi, idx):
        title = item_label(self.data["folders"][fi]["items"][idx])
        if self.data.get("settings", {}).get("confirm_delete", True):
            if not messagebox.askyesno(APP_NAME, f"「{title}」を削除しますか？"):
                return
        del self.data["folders"][fi]["items"][idx]
        save_data(self.data)
        self._disarm()
        self._render_tabbar()        # ピン留めが消えた場合に「よく使う」タブを更新
        self._fill_rows()
        self.status.set(f"削除しました → {title}")

    def destroy(self):
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        super().destroy()


def main():
    app = StamperApp()
    app.mainloop()


if __name__ == "__main__":
    main()
