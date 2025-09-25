# -*- coding: utf-8 -*-
"""
USD exporter for mayapy (Maya 2025) z mechanizmem stagingu
- output: <sceneName>.usd w --outputBasePath
- zapis do TEMP i kopiowanie na UNC, żeby uniknąć permission/lock errors
"""

import argparse, os, shutil, tempfile, time, getpass, sys, io
import maya.standalone
import maya.cmds as cmds

# --- ustaw stdout/stderr na UTF-8 (żeby uniknąć problemów z kodowaniem)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def norm_path(p: str) -> str:
    return p.replace("\\", "/") if p else p


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p


def copy_with_retry(src, dst, retries=5, delay=0.5):
    ensure_dir(os.path.dirname(dst))
    for i in range(retries):
        try:
            shutil.copy2(src, dst)  # preserve timestamps
            return True, None
        except Exception as e:
            if i == retries - 1:
                return False, e
            time.sleep(delay * (i + 1))


def load_usd_plugin():
    try:
        if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
            print("[INFO] mayaUsdPlugin loaded")
    except Exception as e:
        print(f"[ERROR] mayaUsdPlugin load failed: {e}")
        raise


def open_scene_safe(path: str):
    """Otwiera scenę i ignoruje brakujące pluginy (np. V-Ray)."""
    try:
        cmds.file(path, open=True, force=True, ignoreVersion=True, options="v=0;")
    except Exception as e:
        print(f"[WARN] Errors while opening scene: {e}")


def export_usd(final_usd_path: str):
    ensure_dir(os.path.dirname(final_usd_path))

    # wybierz całą scenę jeśli brak selekcji
    if not cmds.ls(sl=True):
        cmds.select(all=True)

    options = (
        "ExportUVs=1;"
        "ExportColorSets=1;"
        "ExportDisplayColor=1;"
        "ExportVisibility=1;"
        "WorldSpace=1;"
        "DynamicAttributes=1;"
    )

    # 1) próba bezpośrednia
    try:
        cmds.file(final_usd_path,
                  force=True,
                  options=options,
                  typ="USD Export",
                  pr=True,
                  es=True)
        print(f"[OK] USD exported directly to: {final_usd_path}")
        return True
    except Exception as e_direct:
        print(f"[WARN] Direct USD export failed: {e_direct}")

    # 2) fallback: staging do TEMP i copy-back
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, os.path.basename(final_usd_path))
    try:
        cmds.file(tmp_usd,
                  force=True,
                  options=options,
                  typ="USD Export",
                  pr=True,
                  es=True)
        ok, err = copy_with_retry(tmp_usd, final_usd_path)
        if ok:
            print(f"[OK] USD staged at TEMP and copied to: {final_usd_path}")
            return True
        else:
            print(f"[ERROR] USD copy failed: {err}")
    except Exception as e_stage:
        print(f"[ERROR] Staging USD export failed: {e_stage}")

    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd)")
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_usd = norm_path(os.path.join(out_dir, base + ".usd"))

    maya.standalone.initialize(name='python')
    try:
        load_usd_plugin()
        open_scene_safe(input_file)
        ok = export_usd(final_usd)
        sys.stdout.flush(); sys.stderr.flush()
        sys.exit(0 if ok else 1)
    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    main()
