# -*- coding: utf-8 -*-
# USD exporter for mayapy (Maya 2025)
# Eksport: staging do %TEMP%, potem kopiowanie do celu.
# Zakończenie os._exit → brak crasha na zamknięciu.

import argparse, os, shutil, tempfile, time, getpass, sys, io

# --- stabilizacja środowiska przed importem Mayi
os.environ.setdefault("MAYA_DISABLE_CLEANUP", "1")
os.environ.setdefault("MAYA_UNLOAD_PLUGINS", "0")
os.environ.setdefault("MAYA_NO_WARNING_FOR_MISSING_DEFAULT_RENDERER", "1")

# stdout/stderr w UTF-8 (żeby nie sypało na znaki specjalne)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import maya.standalone
import maya.cmds as cmds


def norm_path(p: str) -> str:
    return p.replace("\\", "/") if p else p


def ensure_dir(p: str) -> str:
    os.makedirs(p, exist_ok=True)
    return p


def copy_with_retry(src: str, dst: str, retries: int = 8, delay: float = 0.5):
    """Kopiuje plik z retry + atomic move"""
    ensure_dir(os.path.dirname(dst))
    last_err = None
    for i in range(retries):
        try:
            tmp_dst = dst + ".part"
            shutil.copy2(src, tmp_dst)
            if os.path.exists(dst):
                os.remove(dst)
            os.replace(tmp_dst, dst)  # atomiczny move
            return True, None
        except Exception as e:
            last_err = e
            time.sleep(delay * (i + 1))
    return False, last_err


def load_usd_plugin():
    if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        print("[INFO] mayaUsdPlugin loaded")


def open_scene_safe(path: str):
    try:
        cmds.file(path, open=True, force=True, ignoreVersion=True, options="v=0;")
    except Exception as e:
        print(f"[WARN] Errors while opening scene: {e}")


def export_usd_to_temp(scene_usd_name: str) -> str:
    """Eksportuje całą scenę do pliku w %TEMP% i zwraca jego ścieżkę"""
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, scene_usd_name)

    if not cmds.ls(sl=True):
        cmds.select(all=True)

    options = (
        "ExportUVs=1;"
        "ExportColorSets=1;"
        "ExportDisplayColor=1;"
        "ExportVisibility=1;"
        "WorldSpace=1;"
        "DynamicAttributes=1;"
        "CurveDefaultWidth=1.0;"
    )

    cmds.file(norm_path(tmp_usd),
              force=True,
              options=options,
              typ="USD Export",
              pr=True,
              es=True)
    print(f"[OK] USD exported to TEMP: {norm_path(tmp_usd)}")
    return tmp_usd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd)")
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_usd = norm_path(os.path.join(out_dir, base + ".usd"))

    status = 1
    maya.standalone.initialize(name='python')
    try:
        load_usd_plugin()
        open_scene_safe(input_file)

        # staging do TEMP
        tmp_usd = export_usd_to_temp(os.path.basename(final_usd))

        # kopiowanie z retry
        ok, err = copy_with_retry(tmp_usd, final_usd)
        if ok:
            print(f"[OK] USD copied to destination: {final_usd}")
            status = 0
        else:
            print(f"[ERROR] USD copy failed to '{final_usd}': {err}")
            status = 1

        sys.stdout.flush()
        sys.stderr.flush()
    except Exception as e:
        print(f"[ERROR] Unhandled exception: {e}")
        status = 1
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        # kończymy brutalnie → brak crasha na cleanupie pluginów
        os._exit(status)


if __name__ == "__main__":
    main()
