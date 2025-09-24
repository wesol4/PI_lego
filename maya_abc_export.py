# -*- coding: utf-8 -*-
"""
Alembic exporter for mayapy (Maya 2025)
- output: <sceneName>.abc
"""

import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

def norm_path(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/") if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def load_alembic_plugin():
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)
            print("[OK] AbcExport plugin loaded")
    except Exception as e:
        print(f"[ERROR] AbcExport plugin load failed: {e}")
        raise

def export_abc(path, start, end):
    args = [
        "-frameRange", str(start), str(end),
        "-uvWrite", "-worldSpace",
        "-writeVisibility", "-writeNormals",
        "-root", "|Model_grp",  # lub wszystkie top-levely
        "-file", path
    ]
    try:
        cmds.AbcExport(j=" ".join(args))
        print(f"[OK] Alembic exported to: {path}")
        return True
    except Exception as e:
        print(f"[ERROR] Alembic export failed: {e}")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True)
    ap.add_argument("--outputBasePath", required=True)
    ap.add_argument("--frameStart", type=int, default=1)
    ap.add_argument("--frameEnd", type=int, default=1)
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_abc = norm_path(os.path.join(out_dir, base + ".abc"))

    maya.standalone.initialize(name='python')
    try:
        load_alembic_plugin()
        cmds.file(input_file, open=True, force=True)
        ok = export_abc(final_abc, args.frameStart, args.frameEnd)
        sys.stdout.flush(); sys.stderr.flush()
        return 0 if ok else 1
    finally:
        pass

if __name__ == "__main__":
    sys.exit(main())
