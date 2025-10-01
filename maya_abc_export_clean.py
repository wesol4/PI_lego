# -*- coding: utf-8 -*-
"""
Minimal Alembic exporter for mayapy (Maya 2025)
- odpowiada ręcznemu Export All z Alembic Cache
"""

import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.abc)")
    ap.add_argument("--frameStart", type=float, default=None, help="Start frame (domyslnie biezaca klatka)")
    ap.add_argument("--frameEnd", type=float, default=None, help="End frame (domyslnie biezaca klatka)")
    args = ap.parse_args()

    maya.standalone.initialize(name='python')
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)

        cmds.file(args.inputFile.replace("\\", "/"), open=True, force=True, ignoreVersion=True, prompt=False)

        current = cmds.currentTime(q=True)
        start = args.frameStart if args.frameStart is not None else current
        end   = args.frameEnd   if args.frameEnd is not None else current

        # budujemy sciezke do .abc na podstawie inputFile + outputBasePath
        base = os.path.splitext(os.path.basename(args.inputFile))[0]
        out_path = os.path.join(args.outputBasePath, base + ".abc").replace("\\", "/")

        # job string (Export All)
        job = f"-frameRange {start} {end} -uvWrite -worldSpace -writeVisibility -root |Model_grp -file {out_path}"
        print("[ABC] Export job:", job)

        cmds.AbcExport(j=job)

        print(f"[ABC] OK: zapisano {out_path}")
        sys.exit(0)
    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
