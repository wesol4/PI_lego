# -*- coding: utf-8 -*-
"""
Minimal Alembic exporter for mayapy (Maya 2025)
- Export 1 frame (no animation)
- Output: <sceneName>.abc in --outputBasePath
"""

import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.abc)")
    args = ap.parse_args()

    maya.standalone.initialize(name='python')
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)

        cmds.file(args.inputFile.replace("\\", "/"), open=True, force=True, ignoreVersion=True, prompt=False)

        # zawsze biezaca klatka, bez animacji
        current = cmds.currentTime(q=True)
        start = end = current

        # budujemy sciezke do pliku wynikowego
        base = os.path.splitext(os.path.basename(args.inputFile))[0]
        out_path = os.path.join(args.outputBasePath, base + ".abc").replace("\\", "/")

        # job string (Export All, 1 frame)
        job = f"-frameRange {start} {end} -uvWrite -worldSpace -writeVisibility -root |Model_grp -file {out_path}"
        print("[ABC] Export job:", job)

        cmds.AbcExport(j=job)

        print(f"[ABC] OK: zapisano {out_path}")
        sys.exit(0)
    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()

