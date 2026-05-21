# クレジット / Credits

## 制作

- **Subara3** — 企画・開発・UIアイコン
- **あきら** — アプリアイコン（アーガイル柄）

## アイコン

- アプリアイコン（`icon.ico` / `icon.png`、アーガイル柄）：**あきら** 提供。
- UIアイコン（`ui_*.png`：鍵・歯車・鉛筆・ゴミ箱・矢印など）：**Subara3 が自作**（`make_icon.py` で生成）。

いずれも著作権は各作者に帰属し、本ソフトの一部として無断での改変・再配布は禁止です。

## 使用ライブラリ・ツール

| 名称 | 用途 | ライセンス |
|------|------|-----------|
| [Python](https://www.python.org/) | 実行環境 | PSF License |
| Tkinter | GUI（Python 標準同梱） | PSF License |
| [Pillow](https://python-pillow.org/) | アイコン生成（ビルド時のみ） | MIT-CMU License |
| [PyInstaller](https://pyinstaller.org/) | exe ビルド（ビルド時のみ） | GPL（例外条項によりビルド成果物の配布は自由） |

> Pillow / PyInstaller は **ビルド時にのみ** 使用します。
> 配布する `Grimoire.exe` 自体は Python と Tkinter のみで動作します。

## 提供素材

- アプリアイコンは **あきら** 提供（`app_icon_src.png` を `icon.ico`/`icon.png` に変換して使用）。
- そのほか外部からの借用素材（フォント・効果音など）はありません。

## 本体ライセンス

**フリーソフト（無料）／オープンソースではありません。**
著作権はすべて Subara3 に帰属します（All rights reserved）。
無料での使用は可、改変・再配布・転載・販売は禁止。詳細は `LICENSE.txt`。
