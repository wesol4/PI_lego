# -*- coding: utf-8 -*-
"""
USD exporter for mayapy (Maya 2025)
- output: <sceneName>.usd
"""

import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

def norm_path(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/") if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def check_writable(path: str) -> bool:
    """Sprawdza czy katalog jest zapisywalny."""
    test_file = os.path.join(path, "__test_write.tmp")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception as e:
        print(f"[ERROR] Cannot write to directory '{path}': {e}")
        return False

def load_usd_plugin():
    try:
        if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
            print("[OK] mayaUsdPlugin loaded")
    except Exception as e:
        print(f"[ERROR] mayaUsdPlugin load failed: {e}")
        raise

def export_usd(final_path):
    try:
        cmds.mayaUSDExport(
            file=final_path,
            mergeTransformAndShape=True,
            shadingMode="none"
        )
        print(f"[OK] USD exported to: {final_path}")
        return True
    except Exception as e:
        print(f"[ERROR] USD export failed: {e}")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True)
    ap.add_argument("--outputBasePath", required=True)
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    # check write permissions
    if not check_writable(out_dir):
        return 1

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_usd = norm_path(os.path.join(out_dir, base + ".usd"))

    maya.standalone.initialize(name='python')
    try:
        load_usd_plugin()
        print(f"[INFO] Opening scene: {input_file}")
        cmds.file(input_file, open=True, force=True)
        ok = export_usd(final_usd)
        sys.stdout.flush(); sys.stderr.flush()
        return 0 if ok else 1
    finally:
        print("[INFO] Shutting down Maya standalone...")
        maya.standalone.uninitialize()

if __name__ == "__main__":
    exit_code = main()
    # sys.exit() nie używamy, żeby uniknąć crasha GIL
    print(f"[INFO] Process finished with code {exit_code}")
