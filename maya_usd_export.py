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


def detect_anim_frame_range():
    """Zwraca (has_anim, start, end) bazując na krzywych animacji lub timeline."""
    anim_curves = cmds.ls(type=("animCurveTA","animCurveTL","animCurveTT","animCurveTU")) or []
    if anim_curves:
        # prosty wariant: użyj zakresu z timeline
        start = cmds.playbackOptions(q=True, minTime=True)
        end   = cmds.playbackOptions(q=True, maxTime=True)
        return True, float(start), float(end)
    return False, 1.0, 1.0


def export_usd_to_temp(scene_usd_name: str,
                       skels: str = "auto",
                       skins: str = "auto",
                       export_blendshapes: bool = False,
                       force_anim: bool = None,
                       start_override: float | None = None,
                       end_override: float | None = None) -> str:
    """
    Eksportuje całą scenę do pliku w %TEMP% i zwraca jego ścieżkę.
    - skels: 'none'|'auto'|'explicit'  → exportSkels
    - skins: 'none'|'auto'|'explicit'  → exportSkins
    - export_blendshapes: True/False   → exportBlendShapes
    - force_anim: True/False/None      → animation=1/0/auto (auto=wykryj)
    - start_override / end_override    → startTime / endTime (float lub None)
    """
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, scene_usd_name)

    if not cmds.ls(sl=True):
        cmds.select(all=True)

    # anim: auto-detect (chyba, że wymuszone)
    has_anim, auto_start, auto_end = detect_anim_frame_range()
    if force_anim is None:
        export_anim = has_anim
    else:
        export_anim = bool(force_anim)

    start = float(start_override if start_override is not None else (auto_start if export_anim else 1.0))
    end   = float(end_override   if end_override   is not None else (auto_end   if export_anim else 1.0))

    # Uwaga: klucze opcji pochodzą z eksportera "USD Export"
    # (exportSkels/exportSkins/exportBlendShapes/animation/startTime/endTime itd.)
    # Patrz: przykłady w dyskusjach Autodesk maya-usd. :contentReference[oaicite:0]{index=0}
    options = (
        # GEO / atrybuty
        "ExportUVs=1;"
        "ExportColorSets=1;"
        "ExportDisplayColor=1;"
        "ExportVisibility=1;"
        "WorldSpace=1;"
        "DynamicAttributes=1;"
        "CurveDefaultWidth=1.0;"
        # UsdSkel: szkielety / skiny / blend-shapes
        f"exportSkels={skels};"
        f"exportSkins={skins};"
        f"exportBlendShapes={'1' if export_blendshapes else '0'};"
        # Animacja (SkelAnimation / time-samples)
        f"animation={'1' if export_anim else '0'};"
        "eulerFilter=1;"
        "staticSingleSample=0;"
        f"startTime={start};"
        f"endTime={end};"
        "frameStride=1;"
        "frameSample=0.0;"
        # Format / drobne
        "mergeTransformAndShape=1;"
        # "defaultUSDFormat=usdc;"  # opcjonalnie: usda/usdc
    )

    cmds.file(norm_path(tmp_usd),
              force=True,
              options=options,
              typ="USD Export",
              pr=True,
              es=True)
    print(f"[OK] USD exported to TEMP: {norm_path(tmp_usd)}")
    if export_anim:
        print(f"[INFO] SkelAnimation ON, frames: {start}..{end}")
    print(f"[INFO] UsdSkel: exportSkels={skels}, exportSkins={skins}, blendShapes={'ON' if export_blendshapes else 'OFF'}")
    return tmp_usd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd)")
    # nowe, opcjonalne:
    ap.add_argument("--skeletons", choices=["none","auto","explicit"], default="auto",
                    help="Eksport szkieletów (exportSkels)")
    ap.add_argument("--skins", choices=["none","auto","explicit"], default="auto",
                    help="Eksport skinClusterów (exportSkins)")
    ap.add_argument("--blendshapes", action="store_true", help="Eksport blend-shapes (exportBlendShapes=1)")
    ap.add_argument("--exportAnimation", action="store_true",
                    help="Wymuś eksport animacji (w przeciwnym razie auto-wykrywanie)")
    ap.add_argument("--start", type=float, default=None, help="Start klatek animacji (opcjonalnie)")
    ap.add_argument("--end", type=float, default=None, help="Koniec klatek animacji (opcjonalnie)")
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

        # staging do TEMP (z UsdSkel + anim)
        tmp_usd = export_usd_to_temp(
            os.path.basename(final_usd),
            skels=args.skeletons,
            skins=args.skins,
            export_blendshapes=args.blendshapes,
            force_anim=(True if args.exportAnimation else None),
            start_override=args.start,
            end_override=args.end,
        )

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
