@echo off
REM ============================================================
REM  Grimoire (グリモワ)  exe ビルドスクリプト (Windows)
REM  PyInstaller で単一の .exe を dist\ に出力します。
REM ============================================================

echo [1/2] PyInstaller を確認 / インストール...
python -m pip install --upgrade pyinstaller

echo [2/2] exe をビルド...
python -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "Grimoire" ^
  --icon "icon.ico" ^
  --add-data "icon.ico;." ^
  --add-data "ui_lock.png;." ^
  --add-data "ui_unlock.png;." ^
  --add-data "ui_gear.png;." ^
  --add-data "ui_edit.png;." ^
  --add-data "ui_delete.png;." ^
  --add-data "ui_search.png;." ^
  --add-data "ui_blank.png;." ^
  --add-data "ui_grip.png;." ^
  --add-data "ui_star.png;." ^
  --add-data "ui_star_off.png;." ^
  stamper.py

echo.
echo 完了しました。 dist\Grimoire.exe を確認してください。
pause
