# -*- coding: utf-8 -*-
# USD Exporter (Maya 2025) — jak w UI:
# Skeletons: All (Automatically Create SkelRoots) => exportSkels=auto
# Skin Clusters: All (Automatically Create SkelRoots) => exportSkins=auto
# Staging do %TEMP% + kopiowanie do celu. chaser=[] (valid JSON)

import os, sys, io, argparse, tempfile, getpass, shutil, time

# środowisko batch
os.environ.setdefault("MAYA_SKIP_USERSETUP", "1")
os.environ.setdefault("MAYA_DISABLE_CLEANUP", "1")
os.environ.setdefault("MAYA_UNLOAD_PLUGINS", "0")
os.environ.setdefault("MAYA_NO_WARNING_FOR_MISSING_DEFAULT_RENDERER", "1")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# I/O UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import maya.standalone
import maya.cmds as cmds

# --- utils ---
def norm(p: str) -> str: return p.replace("\\", "/") if p else p
def ensure_dir(p: str) -> str: os.makedirs(p, exist_ok=True); return p
def log(m: str):
    try: print(m)
    except: print(m.encode("ascii","replace").decode())

def copy_with_retry(src: str, dst: str, tries=6, delay=0.4):
    ensure_dir(os.path.dirname(dst))
    last = None
    for i in range(tries):
        try:
            tmp = dst + ".part"
            shutil.copy2(src, tmp)
            if os.path.exists(dst): os.remove(dst)
            os.replace(tmp, dst)
            return True, None
        except Exception as e:
            last = e
            time.sleep(delay * (i+1))
    return False, last

# --- core ---
def export_usd_to_temp(in_file: str, out_name: str, usd_format: str,
                       do_anim: bool, start: float|None, end: float|None,
                       blendshapes: bool) -> str:
    # TEMP staging
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    ext = ".usda" if usd_format.lower() == "usda" else ".usd"
    tmp_usd = os.path.join(tmp_dir, os.path.splitext(out_name)[0] + ext)

    # otwarcie sceny
    cmds.file(in_file, open=True, force=True, ignoreVersion=True, options="v=0;")
    log(f"[OK] Opened: {in_file}")

    # anim (timeline jeśli nie podano ręcznie)
    if do_anim:
        s = float(start if start is not None else cmds.playbackOptions(q=True, minTime=True))
        e = float(end   if end   is not None else cmds.playbackOptions(q=True, maxTime=True))
    else:
        s = e = None

    # Export dokładnie jak w UI + poprawny JSON dla chaser
    opts = [
        f"defaultUSDFormat={usd_format}",
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
        "exportSkels=auto",             # = All (Auto-create SkelRoots)
        "exportSkins=auto",             # = All (Auto-create SkelRoots)
        f"exportBlendShapes={'1' if blendshapes else '0'}",
        "shadingMode=none",
        "chaser=[]",                    # VALID JSON (a nie pusty string)
    ]
    if do_anim:
        opts += [f"animation=1", f"startTime={s}", f"endTime={e}"]
    else:
        opts += ["animation=0"]

    options_str = ";".join(opts) + ";"

    # zapis do TEMP (exportAll)
    log(f"[INFO] Staging → {norm(tmp_usd)}")
    cmds.file(norm(tmp_usd), force=True, options=options_str, typ="USD Export", pr=True, ea=True)

    size = os.path.getsize(tmp_usd) if os.path.exists(tmp_usd) else 0
    if not size:
        raise RuntimeError("Exporter nie zapisał pliku (TEMP).")
    log(f"[OK] Staged: {norm(tmp_usd)}  size={size} B")
    return tmp_usd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd/usda)")
    ap.add_argument("--usdFormat", choices=["usdc","usda"], default="usdc", help="Format pliku")
    ap.add_argument("--anim", action="store_true", help="Eksport animacji (timeline lub --start/--end)")
    ap.add_argument("--start", type=float, default=None, help="Start klatek")
    ap.add_argument("--end", type=float, default=None, help="Koniec klatek")
    ap.add_argument("--blendshapes", action="store_true", help="Eksportuj blend-shapes")
    args = ap.parse_args()

    in_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath).rstrip("/")
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(in_file))[0]
    out_ext = ".usda" if args.usdFormat == "usda" else ".usd"
    final_usd = norm(os.path.join(out_dir, base + out_ext))

    maya.standalone.initialize(name="python")
    try:
        if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
            cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        log("[INFO] mayaUsdPlugin ready")

        # EXPORT → %TEMP%
        tmp_usd = export_usd_to_temp(
            in_file=in_file,
            out_name=os.path.basename(final_usd),
            usd_format=args.usdFormat,
            do_anim=args.anim,
            start=args.start,
            end=args.end,
            blendshapes=args.blendshapes,
        )

        # KOPIOWANIE z TEMP do docelowej lokalizacji
        log(f"[INFO] Copy → {final_usd}")
        ok, err = copy_with_retry(tmp_usd, final_usd)
        if ok:
            size = os.path.getsize(final_usd)
            log(f"[OK] Saved: {final_usd}  size={size} B")
            os._exit(0)
        else:
            log(f"[ERROR] Copy failed: {err}")
            log(f"[HINT] Masz gotowy plik w TEMP: {tmp_usd}")
            os._exit(2)

    except Exception as e:
        log(f"[ERROR] Unhandled: {e}")
        os._exit(1)

if __name__ == "__main__":
    main()
