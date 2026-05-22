# -*- coding: utf-8 -*-
"""
Grimoire (グリモワ) — 定型文＝呪文を綴じた魔導書
- フォルダ(タブ)で定型文を分類管理
- 行をクリック / Enter / 1〜9 でクリップボードにコピー（呪文の詠唱）
- 機密は鍵アイコン：クリックで開錠 → もう一度でコピー（誤コピー防止）
- ★でお気に入り → 上に固定・「お気に入り」タブに集約
- 各カードに編集（鉛筆）・削除（ゴミ箱）。ホバーで操作と番号が出る
- 検索ボックス（全フォルダ横断）/ プレースホルダ展開 / コピー演出
- ↑↓で選択・Enterでコピー・Escで検索クリア/最小化（キーボード操作）
- グローバルホットキーでウィンドウを最前面に呼び出し・トレイ常駐
- データはすべてローカルの templates.json に保存（オフライン完結）

デザインは「札 / Notebook」エディトリアル系（紙＝paper・墨＝ink・極細罫）。
本文（貼り付ける文章）が主役。Python + Tkinter / 単一ファイル / PyInstaller で .exe 化可能
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
APP_VERSION = "1.3.0"
AUTHOR = "Subara3"
AUTHOR_URL = "https://subara3.com"
MAX_FOLDERS = 10

F_UI = "Yu Gothic UI"
F_MONO = "Consolas"

# テーマカラーのプリセット（設定で選択可）。アクセントは「強調」だけに使う。
PRESET_COLORS = [
    ("ターコイズ（デフォルト）", "#84CCD8"),
    ("墨（モノクロ）", "#1A1A1A"),
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
    return "#FFFFFF" if _lum(accent) < 0.6 else "#1A1A1A"


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
             font=(F_UI, 12, "bold"), padx=14, pady=8).pack(anchor="w")


def primary_button(parent_widget, accent, text, command):
    """アクセント色の主ボタン（tk.Button で確実に着色）。"""
    fg = fg_on(accent)
    return tk.Button(parent_widget, text=text, command=command, bg=accent, fg=fg,
                     activebackground=accent, activeforeground=fg, relief="flat",
                     bd=0, padx=16, pady=5, cursor="hand2",
                     font=(F_UI, 10, "bold"))


DEFAULT_DATA = {
    "settings": {"hotkey": "ctrl+alt+space", "accent": DEFAULT_ACCENT,
                 "confirm_delete": True, "paste_back": True},
    "folders": [
        {
            "name": "挨拶・書き出し",
            "items": [
                {"title": "はじめまして", "body": "はじめまして。〇〇と申します。", "secret": False},
            ],
        },
        {
            "name": "受注・お見積り",
            "items": [
                {"title": "納期・料金の連絡", "body": "ご依頼ありがとうございます。納期は{{納期}}頃、料金は{{金額}}を予定しております。", "secret": False},
            ],
        },
        {
            "name": "進捗・納品",
            "items": [
                {"title": "完成・納品", "body": "完成いたしました。データをお送りしますので、ご確認ください。", "secret": False},
            ],
        },
        {
            "name": "お断り・調整",
            "items": [
                {"title": "今回は見送り", "body": "申し訳ございませんが、今回はお受けすることが難しい状況です。またの機会によろしくお願いいたします。", "secret": False},
            ],
        },
        {
            "name": "お礼・締め",
            "items": [
                {"title": "またの機会に", "body": "また機会がありましたらよろしくお願いいたします。", "secret": False},
            ],
        },
        {
            "name": "個人情報",
            "items": [
                {"title": "メールアドレス", "body": "example@example.com", "secret": True},
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
                s.setdefault("paste_back", True)
                for folder in data["folders"]:
                    for item in folder.get("items", []):
                        item.setdefault("secret", False)
                        item.setdefault("pinned", False)
                        item.setdefault("used", 0)
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return json.loads(json.dumps(DEFAULT_DATA))


def item_label(item: dict) -> str:
    """ステータス等に使う短いラベル。タイトルが無ければ本文の先頭。"""
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
    def __init__(self, parent, accent, hotkey, confirm_delete, paste_back=True):
        super().__init__(parent)
        self.transient(parent)
        self.title("設定")
        self.resizable(False, False)
        self.result = None
        accent = dialog_accent(parent)
        add_dialog_header(self, accent, "設定")

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="テーマカラー（強調色）", font=(F_UI, 10, "bold")).grid(
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
                  font=(F_UI, 10, "bold")).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(14, 4))
        self.hk_var = tk.StringVar(value=hotkey)
        ttk.Entry(frm, textvariable=self.hk_var, width=28).grid(
            row=3, column=0, columnspan=2, sticky="we")

        self.paste_var = tk.BooleanVar(value=paste_back)
        ttk.Checkbutton(
            frm, text="コピー後、呼び出す前のアプリへ自動で貼り付ける（直接貼り付け）",
            variable=self.paste_var).grid(row=4, column=0, columnspan=2, sticky="w", pady=(14, 0))

        self.confirm_var = tk.BooleanVar(value=confirm_delete)
        ttk.Checkbutton(frm, text="削除の前に確認する", variable=self.confirm_var).grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", pady=(16, 0))
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
            "paste_back": self.paste_var.get(),
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
    # エディトリアル（紙 / 墨 / 罫）パレット
    PAPER = "#FBFAF7"
    PAPER2 = "#F6F4EF"
    PAGE = "#F0EEE9"
    WHITE = "#FFFFFF"
    INK = "#1A1A1A"
    INK2 = "#4A4A4A"
    INK3 = "#8A8A8A"
    INK4 = "#B8B6B1"
    LINE = "#E4E2DD"
    LINE2 = "#F3F2EF"
    KBD_BD = "#E3E1DC"
    WARN = "#B14A3A"
    SECRET_BG = "#FCF7EF"
    FAV_KEY = "fav"

    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("580x680")
        self.minsize(480, 480)
        self.configure(bg=self.PAGE)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        self.data = load_data()
        self.ACCENT = self.data.get("settings", {}).get("accent", DEFAULT_ACCENT)
        self._recolor_derived()

        self._armed = None
        self._armed_at = 0.0
        self._search = ""
        self._search_all = True    # 検索は常に全フォルダ横断
        self._tab_menu_idx = None
        self._drag_from = None     # 行ドラッグの掴み元（表示インデックス）
        self._drag_moved = False
        self._drop_line = None
        self._reorderable = True
        self._current = 0
        self._fav = False
        self._prev_hwnd = None     # 直接貼り付け先（呼び出し前に前面だったウィンドウ）
        self._own_hwnd = None
        self._tabdrag = None
        self._tab_chips = []
        self._visible = []         # [(fi, idx, item)]
        self._rows = []            # [card meta dict]
        self._sel = -1
        self._icons = self._load_icons()

        self._setup_style()

        self._hk_queue = queue.Queue()
        self.hotkeys = HotkeyManager(lambda: self._hk_queue.put(True))
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
        self.ACC = self.ACCENT
        self.ACC_FG = fg_on(self.ACCENT)

    @staticmethod
    def _tab_text(name, n=8):
        return name if len(name) <= n else name[:n] + "…"

    @staticmethod
    def _lighten(hex_color, factor):
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
        style.configure("TButton", font=(F_UI, 10))
        # スクロールバーを地味な紙色に
        style.configure("Vertical.TScrollbar", background=self.PAPER2,
                        troughcolor=self.PAPER, bordercolor=self.PAPER,
                        arrowcolor=self.INK3, relief="flat")

    def _apply_accent(self, color):
        self.ACCENT = color
        self._recolor_derived()
        self._render_tabbar()
        self._fill_rows()
        self._draw_fab()

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

    def _shortcuts_help(self):
        win = tk.Toplevel(self)
        win.title("キーボード操作")
        win.resizable(False, False)
        win.transient(self)
        add_dialog_header(win, self.ACCENT, "キーボード操作")
        frm = ttk.Frame(win, padding=18)
        frm.pack(fill="both", expand=True)
        rows = [
            ("↑ / ↓", "選択するカードを移動"),
            ("Enter", "選択中のカードをコピー"),
            ("1 〜 9", "番号のカードを即コピー（検索が空のとき）"),
            ("Esc", "検索を消す → もう一度で最小化"),
            ("ホットキー", "どこからでも最前面に呼び出し（設定で変更）"),
        ]
        for i, (k, v) in enumerate(rows):
            ttk.Label(frm, text=k, font=(F_MONO, 10, "bold"), width=10).grid(
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
        ttk.Label(frm, text=APP_TITLE, font=(F_UI, 14, "bold")).pack(anchor="w")
        ttk.Label(frm, text=f"v{APP_VERSION}", foreground=self.INK3).pack(anchor="w")
        ttk.Label(frm, text=f"作者: {AUTHOR}", font=(F_UI, 10)).pack(anchor="w", pady=(10, 0))
        link = tk.Label(frm, text=AUTHOR_URL, fg="#1A0DAB", cursor="hand2",
                        font=(F_UI, 10, "underline"))
        link.pack(anchor="w", pady=(2, 12))
        link.bind("<Button-1>", lambda e: webbrowser.open(AUTHOR_URL))
        primary_button(frm, self.ACCENT, "閉じる", win.destroy).pack(anchor="e")
        center_window(win, self)
        win.grab_set()

    def open_settings(self):
        s = self.data.setdefault("settings", {})
        dlg = SettingsDialog(self, self.ACCENT, s.get("hotkey", ""),
                             s.get("confirm_delete", True), s.get("paste_back", True))
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
        s["paste_back"] = r["paste_back"]
        s["accent"] = r["accent"]
        save_data(self.data)
        self._apply_accent(r["accent"])
        self.status.set("設定を更新しました")

    # -- UI構築 -------------------------------------------------------------
    def _build_ui(self):
        # ヘッダー：タブ（左・折り返し）＋検索（右）
        header = tk.Frame(self, bg=self.PAPER)
        header.pack(fill="x")

        self._search_var = tk.StringVar()
        sframe = tk.Frame(header, bg=self.LINE2)
        sframe.pack(side="right", padx=14, pady=10)
        sicon = self._icons.get("search")
        if sicon is not None:
            tk.Label(sframe, image=sicon, bg=self.LINE2).pack(side="left", padx=(8, 0))
        self._search_entry = tk.Entry(sframe, textvariable=self._search_var, width=20,
                                      relief="flat", bg=self.LINE2, fg=self.INK,
                                      insertbackground=self.INK, font=(F_UI, 11))
        self._search_entry.pack(side="left", padx=6, ipady=5)
        self._clear_btn = tk.Label(sframe, text="✕", bg=self.LINE2, fg=self.INK3,
                                   cursor="hand2", font=(F_UI, 10, "bold"), padx=4)
        self._clear_btn.bind("<Button-1>", lambda e: self._clear_search())
        self._clear_btn.bind("<Enter>", lambda e: self._clear_btn.config(fg=self.INK))
        self._clear_btn.bind("<Leave>", lambda e: self._clear_btn.config(fg=self.INK3))
        self._search_entry.bind("<FocusIn>", lambda e: self._search_focus(True))
        self._search_entry.bind("<FocusOut>", lambda e: self._search_focus(False))
        self._search_var.trace_add("write", lambda *a: self._on_search())

        # タブ領域：[◁][タブ（1行・はみ出すと横スクロール）][▷][＋]
        tabwrap = tk.Frame(header, bg=self.PAPER)
        tabwrap.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=8)
        self._tabwrap = tabwrap
        self._tab_larr = tk.Label(tabwrap, text="◁", bg=self.PAPER, fg=self.INK3,
                                  cursor="hand2", font=(F_UI, 11), padx=5)
        self._tab_larr.bind("<Button-1>", lambda e: self._scroll_tabs(-1))
        self._tab_rarr = tk.Label(tabwrap, text="▷", bg=self.PAPER, fg=self.INK3,
                                  cursor="hand2", font=(F_UI, 11), padx=5)
        self._tab_rarr.bind("<Button-1>", lambda e: self._scroll_tabs(1))
        self._tab_plus = self._make_plus_chip(tabwrap)
        self._tab_plus.pack(side="right")
        self._tabbar = tk.Frame(tabwrap, bg=self.PAPER, height=30)
        self._tabbar.pack(side="left", fill="x", expand=True)
        self._tabbar.pack_propagate(False)
        self._tabbar.bind("<Double-Button-1>", lambda e: self.add_folder())
        self._tabbar.bind("<Button-3>", self._on_tabbar_right)
        self._tabbar.bind("<Configure>", self._on_tabbar_configure)
        self._last_tabbar_w = 0
        self._tab_offset = 0
        self._tab_layout = []
        self._tab_total = 0

        tk.Frame(self, bg=self.LINE, height=1).pack(fill="x")

        # メタ行：フォルダ名・件数・並び替えヒント
        meta = tk.Frame(self, bg=self.PAPER)
        meta.pack(fill="x")
        self._meta_name = tk.Label(meta, bg=self.PAPER, fg=self.INK2,
                                   font=(F_UI, 10, "bold"))
        self._meta_name.pack(side="left", padx=(18, 8), pady=(8, 6))
        self._meta_count = tk.Label(meta, bg=self.PAPER, fg=self.INK3, font=(F_UI, 9))
        self._meta_count.pack(side="left", pady=(8, 6))
        self._meta_hint = tk.Label(meta, bg=self.PAPER, fg=self.INK4, font=(F_UI, 9),
                                   text="⠿  ドラッグで並び替え")
        self._meta_hint.pack(side="right", padx=(8, 18), pady=(8, 6))

        # 本文リスト（カード）
        content = tk.Frame(self, bg=self.PAPER)
        content.pack(fill="both", expand=True)
        self._content = content
        self._canvas, self._inner = self._make_scroller(content)

        # 追加 FAB（右下に浮かべる丸ボタン）
        self._fab = tk.Canvas(content, width=46, height=46, highlightthickness=0,
                              bg=self.PAPER, cursor="hand2")
        self._fab.place(relx=1.0, rely=1.0, x=-22, y=-18, anchor="se")
        self._fab.bind("<Button-1>", lambda e: self.add_item())
        self._fab.bind("<Enter>", lambda e: self._draw_fab(True))
        self._fab.bind("<Leave>", lambda e: self._draw_fab(False))
        self._draw_fab()

        # ステータスバー（kbd ヒント＋直近メッセージ）
        tk.Frame(self, bg=self.LINE, height=1).pack(side="bottom", fill="x")
        sb = tk.Frame(self, bg=self.PAPER2)
        sb.pack(side="bottom", fill="x")
        self.status = tk.StringVar(value="")
        tk.Label(sb, textvariable=self.status, bg=self.PAPER2, fg=self.INK3,
                 font=(F_UI, 9)).pack(side="right", padx=12, pady=3)
        hints = tk.Frame(sb, bg=self.PAPER2)
        hints.pack(side="left", padx=10, pady=3)
        for keys, label in [(["↵"], "コピー"), (["1", "9"], "即コピー"),
                            (["↑↓"], "選択"), (["Esc"], "隠す")]:
            grp = tk.Frame(hints, bg=self.PAPER2)
            grp.pack(side="left", padx=(0, 12))
            for ki, k in enumerate(keys):
                if ki == 1:
                    tk.Label(grp, text="–", bg=self.PAPER2, fg=self.INK4,
                             font=(F_UI, 9)).pack(side="left", padx=1)
                self._kbd(grp, k).pack(side="left")
            tk.Label(grp, text=label, bg=self.PAPER2, fg=self.INK3,
                     font=(F_UI, 9)).pack(side="left", padx=(4, 0))

    def _kbd(self, parent, text):
        return tk.Label(parent, text=text, bg=self.LINE2, fg=self.INK2,
                        font=(F_MONO, 8), padx=4, pady=0,
                        highlightthickness=1, highlightbackground=self.KBD_BD)

    def _search_focus(self, on):
        bg = self.WHITE if on else self.LINE2
        for w in (self._search_entry, self._clear_btn,
                  self._search_entry.master):
            try:
                w.config(bg=bg)
            except tk.TclError:
                pass
        for child in self._search_entry.master.winfo_children():
            try:
                child.config(bg=bg)
            except tk.TclError:
                pass

    def _draw_fab(self, hover=False):
        c = self._fab
        c.delete("all")
        fill = darken(self.ACC, 0.14) if (hover and _lum(self.ACC) > 0.2) else self.ACC
        if hover and _lum(self.ACC) <= 0.2:
            fill = "#000000"
        c.create_oval(4, 3, 44, 43, fill=fill, outline="")
        c.create_text(24, 22, text="＋", fill=self.ACC_FG, font=(F_UI, 17, "bold"))

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

    # -- 自前タブバー（フォルダ・ピル型） -----------------------------------
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
            self._tab_layout = []

            entries = []
            if self._has_pins():
                entries.append((self.FAV_KEY, None))
            for idx, folder in enumerate(self.data["folders"]):
                entries.append((idx, folder))

            created = [(self._make_tab_chip(key, folder), key) for key, folder in entries]
            self.update_idletasks()

            rowh = max([c.winfo_reqheight() for c, _ in created] + [26])
            gap, x = 3, 0
            for chip, key in created:
                w = chip.winfo_reqwidth()
                self._tab_layout.append((chip, key, x, w))
                self._tab_chips.append((chip, key))
                x += w + gap
            self._tab_total = max(x - gap, 0)
            self._tabbar.config(height=rowh)
            self._place_tabs()
            self._update_tab_arrows()
        finally:
            self._rendering = False

    def _avail(self):
        w = self._tabbar.winfo_width()
        return w if w > 1 else max(self.winfo_width() - 260, 200)

    def _max_offset(self):
        return max(0, self._tab_total - self._avail())

    def _place_tabs(self):
        self._tab_offset = min(max(self._tab_offset, 0), self._max_offset())
        off = self._tab_offset
        for chip, key, bx, w in self._tab_layout:
            try:
                chip.place(x=bx - off, y=0)
            except tk.TclError:
                pass

    def _scroll_tabs(self, direction):
        maxoff = self._max_offset()
        if maxoff <= 0:
            return
        step = max(int(self._avail() * 0.7), 80)
        self._tab_offset = min(max(self._tab_offset + direction * step, 0), maxoff)
        self._place_tabs()
        self._update_tab_arrows()

    def _update_tab_arrows(self):
        maxoff = self._max_offset()
        self._tab_larr.pack_forget()
        self._tab_rarr.pack_forget()
        if maxoff > 0:
            self._tab_larr.pack(side="left", before=self._tabbar)
            self._tab_rarr.pack(side="right", before=self._tab_plus)
            self._tab_larr.config(fg=self.INK3 if self._tab_offset > 0 else self.INK4)
            self._tab_rarr.config(fg=self.INK3 if self._tab_offset < maxoff else self.INK4)

    def _scroll_into_view(self, key):
        avail = self._avail()
        for chip, k, bx, w in self._tab_layout:
            if k == key:
                if bx < self._tab_offset:
                    self._tab_offset = bx
                elif bx + w > self._tab_offset + avail:
                    self._tab_offset = bx + w - avail
                self._place_tabs()
                self._update_tab_arrows()
                return

    def _is_selected_key(self, key):
        if key == self.FAV_KEY:
            return self._fav
        return (not self._fav) and key == self._current

    def _make_tab_chip(self, key, folder):
        sel = self._is_selected_key(key)
        bg = self.ACC if sel else self.PAPER
        fg = self.ACC_FG if sel else self.INK3
        font = (F_UI, 10, "bold" if sel else "normal")
        chip = tk.Frame(self._tabbar, bg=bg, cursor="hand2")
        if key == self.FAV_KEY:
            lbl = tk.Label(chip, text="★ お気に入り", bg=bg, fg=fg,
                           padx=12, pady=5, font=font)
        else:
            lbl = tk.Label(chip, text=self._tab_text(folder["name"]),
                           bg=bg, fg=fg, padx=12, pady=5, font=font)
        lbl.pack(fill="both", expand=True)

        for w in (chip, lbl):
            w.bind("<ButtonPress-1>", lambda e, k=key: self._tab_press(e, k))
            w.bind("<B1-Motion>", self._tab_motion)
            w.bind("<ButtonRelease-1>", self._tab_release)
            if key != self.FAV_KEY:
                w.bind("<Double-Button-1>", lambda e, k=key: self.rename_folder(k))
                w.bind("<Button-3>", lambda e, k=key: self._tab_context(e, k))
        if not sel:
            for w in (chip, lbl):
                w.bind("<Enter>", lambda e, c=chip, l=lbl: self._tab_hover(c, l, True), add="+")
                w.bind("<Leave>", lambda e, c=chip, l=lbl: self._tab_hover(c, l, False), add="+")
        chip._lbl = lbl
        chip._key = key
        return chip

    def _tab_hover(self, chip, lbl, on):
        try:
            bg = self.LINE2 if on else self.PAPER
            chip.config(bg=bg)
            lbl.config(bg=bg, fg=self.INK2 if on else self.INK3)
        except tk.TclError:
            pass

    def _make_plus_chip(self, parent):
        plus = tk.Label(parent, text="＋", bg=self.PAPER, fg=self.INK3,
                        cursor="hand2", font=(F_UI, 12, "bold"), padx=8, pady=4)
        plus.bind("<Button-1>", lambda e: self.add_folder())
        plus.bind("<Enter>", lambda e: plus.config(bg=self.LINE2, fg=self.INK))
        plus.bind("<Leave>", lambda e: plus.config(bg=self.PAPER, fg=self.INK3))
        return plus

    def _restyle_tabs(self):
        """チップを破棄せず色だけ更新（破棄するとダブルクリックが消える）。"""
        for chip, key in self._tab_chips:
            try:
                if not chip.winfo_exists():
                    continue
                sel = self._is_selected_key(key)
                bg = self.ACC if sel else self.PAPER
                chip.config(bg=bg)
                chip._lbl.config(bg=bg, fg=self.ACC_FG if sel else self.INK3,
                                 font=(F_UI, 10, "bold" if sel else "normal"))
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
        self._scroll_into_view(key)
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
        container = tk.Frame(parent, bg=self.PAPER)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=self.PAPER, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview,
                           style="Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=self.PAPER)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_inner(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", on_inner)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        def on_wheel(e):
            # モーダル中は背面を動かさない。カードの上でも効くよう常時バインドする
            # （canvas の Enter/Leave で bind/unbind するとカードに乗った瞬間に切れる）。
            if self.grab_current() is not None:
                return
            if inner.winfo_reqheight() > canvas.winfo_height():
                canvas.yview_scroll(int(-e.delta / 120), "units")
        self.bind_all("<MouseWheel>", on_wheel)
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
            entries.sort(key=lambda e: 0 if e[2].get("pinned") else 1)
        return entries

    def _update_meta(self, shown, total):
        if self._fav:
            name = "お気に入り"
        else:
            fi = self._current_folder_index()
            name = self.data["folders"][fi]["name"] if fi is not None else ""
        self._meta_name.config(text=name)
        q = self._search.strip()
        if q:
            self._meta_count.config(text=f"{shown}件（{total}件中・全フォルダ検索）")
        else:
            self._meta_count.config(text=f"{shown}件")
        self._meta_hint.pack_forget()
        if self._reorderable and shown > 1:
            self._meta_hint.pack(side="right", padx=(8, 18), pady=(8, 6))

    def _fill_rows(self, *_):
        if self._fav and not self._has_pins():
            self._fav = False
            self._restyle_tabs()
        canvas, inner = self._canvas, self._inner
        for w in inner.winfo_children():
            w.destroy()
        self._drop_line = None

        entries = self._collect_entries()
        self._visible = entries
        self._rows = []
        q = self._search.strip()
        show_folder = self._fav or (self._search_all and bool(q))
        self._reorderable = (not self._fav) and (not (self._search_all and q)) and (q == "")

        total = 0
        if not self._fav:
            fi = self._current_folder_index()
            total = len(self.data["folders"][fi]["items"]) if fi is not None else 0
        else:
            total = sum(1 for f in self.data["folders"] for it in f["items"] if it.get("pinned"))

        for j, (fi, idx, item) in enumerate(entries):
            num = (j + 1) if j < 9 else "·"
            fname = self.data["folders"][fi]["name"] if show_folder else None
            self._make_card(inner, fi, idx, item, j, num, fname)

        if not entries:
            if q:
                msg = f"「{q}」に該当する定型文はありません。"
            elif self._fav:
                msg = "お気に入りはまだありません。\n★を押すとここに集まります。"
            else:
                msg = "このフォルダはまだ空です。\n右下の ＋ で追加できます。"
            tk.Label(inner, text=msg, bg=self.PAPER, fg=self.INK3,
                     font=(F_UI, 11), justify="center", pady=60).pack(fill="x")
        else:
            tk.Frame(inner, bg=self.PAPER, height=70).pack(fill="x")  # FAB の下敷き

        self._update_meta(len(entries), total)
        self._sel = 0 if entries else -1
        self._paint_sel()
        canvas.yview_moveto(0)

    # -- カード -------------------------------------------------------------
    def _make_card(self, parent, fi, idx, item, rownum, num, folder_name):
        secret = item.get("secret")
        pinned = item.get("pinned")
        cardbg = self.SECRET_BG if secret else self.WHITE
        card = tk.Frame(parent, bg=cardbg, highlightthickness=1,
                        highlightbackground=self.LINE, highlightcolor=self.LINE)
        card.pack(fill="x", padx=12, pady=4)
        pad = tk.Frame(card, bg=cardbg)
        pad.pack(fill="x", padx=14, pady=8)

        # 見出し行：グリップ・★・鍵・タイトル（小ラベル）・番号
        tl = tk.Frame(pad, bg=cardbg)
        tl.pack(fill="x")

        grip = tk.Label(tl, bg=cardbg, cursor="fleur",
                        image=self._icons.get("blank"))
        grip.pack(side="left", padx=(0, 6))
        grip.bind("<ButtonPress-1>", lambda e, j=rownum: self._drag_start(j))
        grip.bind("<B1-Motion>", self._drag_motion)
        grip.bind("<ButtonRelease-1>", self._drag_end)

        star_col = text_on_white(self.ACC)
        star = tk.Label(tl, bg=cardbg, cursor="hand2",
                        text="★" if pinned else "☆",
                        fg=(star_col if pinned else self.INK4), font=(F_UI, 12))
        star.pack(side="left", padx=(0, 5))
        star.bind("<Button-1>", lambda e, f=fi, i=idx: self._toggle_pin(f, i))
        star.bind("<Enter>", lambda e, s=star, p=pinned, c=star_col:
                  s.config(fg=c if p else self.INK2))
        star.bind("<Leave>", lambda e, s=star, p=pinned, c=star_col:
                  s.config(fg=c if p else self.INK4))

        title_text = item.get("title", "").strip()
        if folder_name:
            title_text = f"［{folder_name}］{('  ' + title_text) if title_text else ''}"
        if not title_text:
            title_text = "無題"
        if secret:
            lkimg = self._icons.get("unlock" if self._armed == (fi, idx) else "lock")
            lk = tk.Label(tl, bg=cardbg, image=lkimg)
            lk.pack(side="left", padx=(0, 4))
        title = tk.Label(tl, text=title_text, bg=cardbg, fg=self.INK3,
                         font=(F_UI, 9, "bold"), anchor="w")
        title.pack(side="left", fill="x", expand=True)
        numlbl = tk.Label(tl, text=str(num), bg=cardbg, fg=self.INK4, font=(F_MONO, 10))
        numlbl.pack(side="right")

        # 本文（主役）
        body = item.get("body", "").strip() or "（本文なし）"
        if len(body) > 200:
            body = body[:200] + "…"
        bodylbl = tk.Label(pad, text=body, bg=cardbg, fg=self.INK, font=(F_UI, 12),
                           justify="left", anchor="w", wraplength=440)
        bodylbl.pack(fill="x", anchor="w", pady=(3, 0))
        card.bind("<Configure>",
                  lambda e, l=bodylbl: l.config(wraplength=max(e.width - 40, 200)))

        # フッタ（ホバー/選択のときだけ出す＝普段はタイトル＋本文だけでコンパクト）
        foot = tk.Frame(pad, bg=cardbg)
        hint = "↵ でコピー" if num == "·" else f"↵ または {num} でコピー"
        hintlbl = tk.Label(foot, text=hint, bg=cardbg, fg=cardbg, font=(F_UI, 9))
        hintlbl.pack(side="left")
        used = item.get("used", 0)
        usedlbl = tk.Label(foot, text=(f"  ・  {used}回" if used else ""),
                           bg=cardbg, fg=cardbg, font=(F_UI, 9))
        usedlbl.pack(side="left")

        acts = []
        del_lbl = self._foot_act(foot, cardbg, "delete",
                                 lambda e, f=fi, i=idx: self.delete_item(f, i))
        edit_lbl = self._foot_act(foot, cardbg, "edit",
                                  lambda e, f=fi, i=idx: self.edit_item(f, i))
        acts = [del_lbl, edit_lbl]

        # クリックでコピー（グリップ・★・編集削除を除く）
        for w in (card, pad, tl, title, bodylbl, numlbl, foot, hintlbl, usedlbl):
            w.bind("<Button-1>", lambda e, f=fi, i=idx: self._row_click(f, i))

        meta = {"frame": card, "base": cardbg, "grip": grip, "num": numlbl,
                "foot": foot, "foot_text": [hintlbl, usedlbl], "acts": acts,
                "sel": False, "reorder": self._reorderable}
        self._rows.append(meta)
        card.bind("<Enter>", lambda e, m=meta: self._reveal_card(m, True), add="+")
        card.bind("<Leave>", lambda e, m=meta: self._leave_card(m), add="+")
        return card

    def _foot_act(self, foot, cardbg, icon_name, command):
        lbl = tk.Label(foot, bg=cardbg, cursor="hand2", image=self._icons.get("blank"))
        lbl.pack(side="right", padx=(6, 0))
        lbl.bind("<Button-1>", command)
        lbl._real = self._icons.get(icon_name)
        return lbl

    def _reveal_card(self, meta, on):
        try:
            sel = meta.get("sel", False)
            show = on or sel
            if show:
                meta["foot"].pack(fill="x", pady=(6, 0))
            else:
                meta["foot"].pack_forget()
            border = self.ACC if sel else (self.INK3 if on else self.LINE)
            meta["frame"].config(highlightbackground=border, highlightcolor=border)
            meta["grip"].config(
                image=self._icons.get("grip") if (on and meta["reorder"])
                else self._icons.get("blank"))
            meta["num"].config(fg=self.ACC if sel else (self.INK3 if on else self.INK4))
            for w in meta["foot_text"]:
                w.config(fg=self.INK3 if show else meta["base"])
            for lbl in meta["acts"]:
                lbl.config(image=(lbl._real if show else self._icons.get("blank")))
        except tk.TclError:
            pass

    def _leave_card(self, meta):
        def check():
            frame = meta["frame"]
            try:
                x, y = self.winfo_pointerxy()
                w = self.winfo_containing(x, y)
                inside = w is not None and (w is frame or str(w).startswith(str(frame) + "."))
            except tk.TclError:
                return
            if not inside:
                self._reveal_card(meta, False)
        self.after(1, check)

    # -- キーボード選択の描画 -----------------------------------------------
    def _paint_sel(self):
        for j, meta in enumerate(self._rows):
            meta["sel"] = (j == self._sel)
            self._reveal_card(meta, False)

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
            canvas.yview_moveto(max(y - 6, 0) / total)
        elif y + h > top + ch:
            canvas.yview_moveto((y + h - ch + 6) / total)

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
            self._fill_rows()
        else:
            self._armed = (fi, idx)
            self._armed_at = now
            self.status.set(f"鍵付き：もう一度クリック / Enter でコピー → {item_label(item)}")
            self._fill_rows()

    def _do_copy(self, item):
        text = self._expand_placeholders(item.get("body", ""))
        if text is None:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        item["used"] = item.get("used", 0) + 1
        save_data(self.data)
        self.status.set(f"コピーしました → {item_label(item)}")
        if (self.data.get("settings", {}).get("paste_back", True)
                and sys.platform == "win32" and self._prev_hwnd):
            self._paste_to_prev()
        else:
            self._toast(f"{item_label(item)} をコピー")

    # -- 直接貼り付け（呼び出し前のウィンドウへ Ctrl+V） --------------------
    def _track_prev_window(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            if self._own_hwnd is None:
                self._own_hwnd = u.GetAncestor(self.winfo_id(), 2)  # GA_ROOT
            fg = u.GetForegroundWindow()
            if fg and fg != self._own_hwnd:
                self._prev_hwnd = fg
        except Exception:
            pass

    def _paste_to_prev(self):
        hwnd = self._prev_hwnd
        if not hwnd:
            self._toast("コピーしました")
            return
        try:
            import ctypes
            u = ctypes.windll.user32
            self.withdraw()                      # 自分を引っ込めてフォーカスを渡す
            u.SetForegroundWindow(hwnd)
            self.after(70, self._send_ctrl_v)
        except Exception:
            self.deiconify()

    def _send_ctrl_v(self):
        try:
            import ctypes
            u = ctypes.windll.user32
            VK_CONTROL, VK_V, KEYUP = 0x11, 0x56, 0x2
            u.keybd_event(VK_CONTROL, 0, 0, 0)
            u.keybd_event(VK_V, 0, 0, 0)
            u.keybd_event(VK_V, 0, KEYUP, 0)
            u.keybd_event(VK_CONTROL, 0, KEYUP, 0)
        except Exception:
            pass

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
        tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.configure(bg=self.INK)
        tk.Label(tw, text=text, bg=self.INK, fg=self.PAPER,
                 font=(F_UI, 10), padx=14, pady=7).pack()
        tw.update_idletasks()
        try:
            self.update_idletasks()
            cx = self.winfo_rootx() + self.winfo_width() // 2
            by = self.winfo_rooty() + self.winfo_height() - 64
            tw.wm_geometry(f"+{cx - tw.winfo_reqwidth() // 2}+{by}")
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.after(750, tw.destroy)

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

    # -- ホットキー / トレイ -------------------------------------------------
    def _start_hotkey(self):
        hk = self.data.get("settings", {}).get("hotkey", "")
        if not self.hotkeys.available:
            return
        ok = self.hotkeys.start(hk)
        if not ok and hk:
            self.status.set(f"ホットキー「{hk}」を登録できませんでした（他アプリと競合の可能性）")

    def _poll_events(self):
        self._track_prev_window()
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
        self._scroll_into_view(self._current)
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
        self._fill_rows()

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
            dlg.result.update({"pinned": False, "used": 0})
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
            dlg.result.update({"pinned": False, "used": 0})
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
            dlg.result["used"] = item.get("used", 0)
            self.data["folders"][fi]["items"][idx] = dlg.result
            save_data(self.data)
            self._fill_rows()
            self.status.set(f"更新しました → {item_label(dlg.result)}")

    def _toggle_pin(self, fi, idx):
        item = self.data["folders"][fi]["items"][idx]
        item["pinned"] = not item.get("pinned")
        save_data(self.data)
        self._render_tabbar()
        self._fill_rows()
        self.status.set(
            ("お気に入りに追加 → " if item["pinned"] else "お気に入りから外しました → ")
            + item_label(item))

    def delete_item(self, fi, idx):
        title = item_label(self.data["folders"][fi]["items"][idx])
        if self.data.get("settings", {}).get("confirm_delete", True):
            if not messagebox.askyesno(APP_NAME, f"「{title}」を削除しますか？"):
                return
        del self.data["folders"][fi]["items"][idx]
        save_data(self.data)
        self._disarm()
        self._render_tabbar()
        self._fill_rows()
        self.status.set(f"削除しました → {title}")

    # -- ドラッグ並び替え（ドロップ位置の線＋つかみ元を淡く） ----------------
    def _drag_start(self, vj):
        if not self._reorderable:
            self._drag_from = None
            self.status.set("並び替えは通常表示のときだけ（検索・お気に入り表示中は不可）")
            return
        self._drag_from = vj
        self._drag_moved = False

    def _drag_motion(self, event):
        if self._drag_from is None:
            return
        if not self._drag_moved:
            self._drag_moved = True
            try:    # つかみ元を淡く
                self._rows[self._drag_from]["frame"].config(
                    highlightbackground=self.ACC, bg=self.LINE2)
            except (tk.TclError, IndexError):
                pass
            if self._drop_line is None:
                self._drop_line = tk.Frame(self._inner, bg=self.ACC, height=2)
        self._autoscroll_edge(event.y_root)
        t = self._row_target_index(event.y_root)
        if t is not None:
            self._show_drop(t)

    def _drag_end(self, event):
        if self._drag_from is None:
            return
        fj = self._drag_from
        moved = self._drag_moved
        self._drag_from = None
        self._drag_moved = False
        if self._drop_line is not None:
            self._drop_line.place_forget()
        if not moved:
            return
        tj = self._row_target_index(event.y_root)
        if tj is None or tj == fj:
            self._fill_rows()
            return
        fi = self._visible[fj][0]
        items = self.data["folders"][fi]["items"]
        order = [v[1] for v in self._visible]
        m = order.pop(fj)
        if tj > fj:
            tj -= 1
        order.insert(tj, m)
        items[:] = [items[k] for k in order]
        save_data(self.data)
        self._fill_rows()
        self.status.set("並び替えました")

    def _autoscroll_edge(self, y_root):
        try:
            c = self._canvas
            top = c.winfo_rooty()
            h = c.winfo_height()
        except tk.TclError:
            return
        if y_root < top + 24:
            c.yview_scroll(-1, "units")
        elif y_root > top + h - 24:
            c.yview_scroll(1, "units")

    def _show_drop(self, tj):
        if not self._rows or self._drop_line is None:
            return
        self._inner.update_idletasks()
        try:
            if tj < len(self._rows):
                f = self._rows[tj]["frame"]
                y = f.winfo_y() - 3
            else:
                f = self._rows[-1]["frame"]
                y = f.winfo_y() + f.winfo_height() + 2
            w = self._inner.winfo_width() - 28
            self._drop_line.place(x=14, y=max(y, 0), width=max(w, 40))
            self._drop_line.lift()
        except tk.TclError:
            pass

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
