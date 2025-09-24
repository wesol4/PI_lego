# -*- coding: utf-8 -*-
"""
Dummy JSON exporter (example)
- output: <sceneName>.json
"""

import argparse, os, sys, json
import maya.standalone
import maya.cmds as cmds

def norm_path(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/") if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def export_json(path):
    try:
        data = {"objects": cmds.ls(geometry=True)}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[OK] JSON exported to: {path}")
        return True
    except Exception as e:
        print(f"[ERROR] JSON export failed: {e}")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True)
    ap.add_argument("--outputBasePath", required=True)
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_json = norm_path(os.path.join(out_dir, base + ".json"))

    maya.standalone.initialize(name='python')
    try:
        cmds.file(input_file, open=True, force=True)
        ok = export_json(final_json)
        sys.stdout.flush(); sys.stderr.flush()
        return 0 if ok else 1
    finally:
        pass

if __name__ == "__main__":
    sys.exit(main())
