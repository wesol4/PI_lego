# -*- coding: utf-8 -*-
"""
USD-only exporter for mayapy (Maya 2025)
- output: <sceneName>.usd in --outputBasePath
- network-safe: USD_LAYER_TMP_DIR + TEMP staging + copy-back fallback
"""

import argparse, os, shutil, tempfile, time, getpass, sys
import maya.standalone
import maya.cmds as cmds

def norm(p): return os.path.normpath(p) if p else p
def ensure_dir(p): os.makedirs(p, exist_ok=True); return p

def copy_with_retry(src, dst, retries=5, delay=0.5):
    ensure_dir(os.path.dirname(dst))
    for i in range(retries):
        try:
            shutil.copy2(src, dst)  # preserve mtime
            return True, None
        except Exception as e:
            if i == retries - 1: return False, e
            time.sleep(delay * (i + 1))

def load_usd_plugin():
    try:
        if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
    except Exception as e:
        print(f"⚠️  mayaUsdPlugin load failed: {e}")

def export_usd(final_usd_path):
    ensure_dir(os.path.dirname(final_usd_path))

    # USD temp dir -> lokalny dysk (unikamy tmp/rename na SMB)
    os.environ["USD_LAYER_TMP_DIR"] = tempfile.gettempdir()

    # USD honoruje selekcję; wybierz wszystko jeśli pusto
    if not cmds.ls(sl=True):
        cmds.select(all=True)

    options = "ExportUVs=1;ExportColorSets=1;fileSafetyMode=none;"

    # 1) próba bezpośrednia
    try:
        cmds.file(final_usd_path, force=True, options=options, typ="USD Export", pr=True, es=True)
        print(f"✅ USD exported to: {final_usd_path}")
        return True
    except Exception as e_direct:
        print(f"⚠️ USD direct export failed: {e_direct}")

    # 2) fallback: TEMP -> copy
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, os.path.basename(final_usd_path))
    try:
        cmds.file(tmp_usd, force=True, options=options, typ="USD Export", pr=True, es=True)
        ok, err = copy_with_retry(tmp_usd, final_usd_path)
        if ok:
            print(f"✅ USD staged to TEMP and copied to: {final_usd_path}")
            return True
        else:
            print(f"❌ USD copy failed: {err}")
    except Exception as e_stage:
        print(f"❌ USD staging export failed: {e_stage}")

    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd)")
    args = ap.parse_args()

    input_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_usd = norm(os.path.join(out_dir, base + ".usd"))

    maya.standalone.initialize(name='python')
    try:
        load_usd_plugin()
        cmds.file(input_file.replace("\\", "/"), open=True, force=True)
        ok = export_usd(final_usd)
        sys.stdout.flush(); sys.stderr.flush()
        sys.exit(0 if ok else 1)
    finally:
        # Maya potrafi rzucić GIL error przy finalizacji; sys.exit przed uninitialize zwykle zapobiega.
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass

if __name__ == "__main__":
    main()
