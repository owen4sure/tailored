# -*- coding: utf-8 -*-
"""相依自動安裝：偵測缺哪個裝哪個，裝過秒跳過。

在公司主機或使用者要求不安裝時，呼叫端傳 no_install=True，缺件就回報降級，不安裝。
"""
import importlib.util
import subprocess
import sys


def _have_py(mod):
    return importlib.util.find_spec(mod) is not None


def _pip(*pkgs):
    base = [sys.executable, "-m", "pip", "install", "-q"]
    r = subprocess.run(base + ["--break-system-packages"] + list(pkgs),
                       capture_output=True, text=True)
    if r.returncode != 0 and "no such option" in (r.stderr or ""):
        # 舊版 pip 不認得 --break-system-packages，退回一般安裝
        r = subprocess.run(base + list(pkgs), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("pip 安裝失敗：" + (r.stderr or "").strip()[-400:])


def _install_chromium():
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def ensure_dom(no_install=False, log=print):
    """確保 playwright 可匯入。回傳 True 表示可做畫面掃描。"""
    if _have_py("playwright"):
        return True
    if no_install:
        log("[bootstrap] 缺少 playwright，已指定不安裝，畫面掃描將略過。")
        return False
    log("[bootstrap] 安裝 playwright 與 chromium（只需一次）…")
    _pip("playwright")
    _install_chromium()
    return _have_py("playwright")


def launch_chromium(p, no_install=False, log=print):
    """啟動 chromium；瀏覽器檔案缺少時自動補裝一次。"""
    try:
        return p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e) or no_install:
            raise
        log("[bootstrap] 補裝 chromium 瀏覽器…")
        _install_chromium()
        return p.chromium.launch()
