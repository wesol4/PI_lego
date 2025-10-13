# -*- coding: utf-8 -*-
# Minimalny exporter USD (Maya 2025) = to samo co w UI:
# Skeletons: All (Automatically Create SkelRoots)
# Skin Clusters: All (Automatically Create SkelRoots)

import os, sys, io, argparse

# cicho w batchu
os.environ.setdefault("MAYA_SKIP_USERSETUP", "1")
os.environ.setdefault("MAYA_DISABLE_CLEANUP", "1")
os.environ.setdefault("MAYA_UNLOAD_PLUGINS", "0")
os.environ.setdefault("MAYA_NO_WARNING_FOR_MISSING_DEFAULT_RENDERER", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# stdout/stderr w UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import maya.standalone
import maya.cmds as cmds

def norm(p: str) -> str:
    return p.replace("\\", "/") if p else p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder wyjściowy (powstanie <scene>.usd/usda)")
    ap.add_argument("--usdFormat", choices=["usdc","usda"], default="usdc", help="Format USD")
    ap.add_argument("--anim", action="store_true", help="Eksportuj animację (domyślnie timeline)")
    ap.add_argument("--start", type=float, default=None, help="Start klatek (opcjonalnie)")
    ap.add_argument("--end", type=float, default=None, help="Koniec klatek (opcjonalnie)")
    ap.add_argument("--blendshapes", action="store_true", help="Eksportuj blend-shapes")
    args = ap.parse_args()

    in_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath).rstrip("/")

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(in_file))[0]
    out_ext = ".usda" if args.usdFormat == "usda" else ".usd"
    out_path = norm(os.path.join(out_dir, base + out_ext))

    maya.standalone.initialize(name="python")

    try:
        # MayaUSD
        if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)

        # otwórz scenę
        cmds.file(in_file, open=True, force=True, ignoreVersion=True, options="v=0;")
        print(f"[OK] Opened: {in_file}")

        # animacja: z timeline jeśli nie podano
        if args.anim:
            start = args.start if args.start is not None else float(cmds.playbackOptions(q=True, minTime=True))
            end   = args.end   if args.end   is not None else float(cmds.playbackOptions(q=True, maxTime=True))
        else:
            start = end = None

        # dokładny odpowiednik UI
        opts = [
            f"defaultUSDFormat={args.usdFormat}",
            "mergeTransformAndShape=1",
            "ExportUVs=1",
            "ExportColorSets=1",
            "ExportDisplayColor=1",
            "ExportVisibility=1",
            "WorldSpace=0",                 # KLUCZOWE dla UsdSkel
            "DynamicAttributes=1",
            "eulerFilter=1",
            "staticSingleSample=0",
            "frameStride=1",
            "frameSample=0.0",
            "rootPrim=World",
            "exportSkels=auto",             # = All (Automatically Create SkelRoots)
            "exportSkins=auto",             # = All (Automatically Create SkelRoots)
            f"exportBlendShapes={'1' if args.blendshapes else '0'}",
            "chaser=",                      # brak chaserów (np. vray)
        ]
        if args.anim:
            opts += [f"animation=1", f"startTime={start}", f"endTime={end}"]
        else:
            opts += ["animation=0"]

        options_str = ";".join(opts) + ";"

        print(f"[INFO] Export → {out_path}")
        cmds.file(out_path, force=True, options=options_str, typ="USD Export", pr=True, ea=True)

        size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
        print(f"[OK] Saved: {out_path}  ({size} B)")
        if size < 4096:
            print("[WARN] Plik wygląda na bardzo mały (<4KB) — sprawdź czy rig/meshe faktycznie się wyeksportowały.")

        # gotowe
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(0)

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)

if __name__ == "__main__":
    main()
