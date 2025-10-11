# -*- coding: utf-8 -*-
# USD exporter for mayapy (Maya 2025)
# Eksport: staging do %TEMP%, potem kopiowanie do celu.
# Zakończenie os._exit → brak crasha na zamknięciu.

import argparse, os, shutil, tempfile, time, getpass, sys, io
from typing import Optional, Tuple, List

# --- stabilizacja środowiska przed importem Mayi
os.environ.setdefault("MAYA_DISABLE_CLEANUP", "1")
os.environ.setdefault("MAYA_UNLOAD_PLUGINS", "0")
os.environ.setdefault("MAYA_NO_WARNING_FOR_MISSING_DEFAULT_RENDERER", "1")

# stdout/stderr w UTF-8 (żeby nie sypało na znaki specjalne)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import maya.standalone
import maya.cmds as cmds


# ------------------- utils -------------------

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


def log(msg: str):
    try:
        print(msg)
    except Exception:
        safe = msg.encode("ascii", errors="replace").decode()
        print(safe)


# ------------------- maya scene helpers -------------------

def load_usd_plugin():
    if not cmds.pluginInfo("mayaUsdPlugin", q=True, loaded=True):
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        log("[INFO] mayaUsdPlugin loaded")


def open_scene_safe(path: str):
    try:
        cmds.file(path, open=True, force=True, ignoreVersion=True, options="v=0;")
    except Exception as e:
        log(f"[WARN] Errors while opening scene: {e}")


def scene_statistics():
    """Prosty log: ile jest transformów / meshów / jointów / skinClusterów."""
    transforms = cmds.ls(type="transform") or []
    meshes     = cmds.ls(type="mesh") or []
    joints     = cmds.ls(type="joint") or []
    skins      = cmds.ls(type="skinCluster") or []
    log(f"[INFO] Scene stats: transforms={len(transforms)}, meshes={len(meshes)}, joints={len(joints)}, skinClusters={len(skins)}")


def detect_anim_frame_range() -> Tuple[bool, float, float]:
    """Zwraca (has_anim, start, end) bazując na krzywych animacji lub timeline."""
    anim_curves = cmds.ls(type=("animCurveTA", "animCurveTL", "animCurveTT", "animCurveTU")) or []
    if anim_curves:
        start = float(cmds.playbackOptions(q=True, minTime=True))
        end   = float(cmds.playbackOptions(q=True, maxTime=True))
        return True, start, end
    return False, 1.0, 1.0


def find_joint_roots() -> List[str]:
    """Zwraca listę potencjalnych root joints (parent nie-joint)."""
    all_joints = cmds.ls(type="joint", long=True) or []
    roots = []
    for j in all_joints:
        parent = cmds.listRelatives(j, parent=True, fullPath=True) or []
        if not parent:
            roots.append(j)
        else:
            p = parent[0]
            if cmds.nodeType(p) != "joint":
                roots.append(j)
    return sorted(set(roots))


def pick_best_root(candidates: List[str]) -> Optional[str]:
    """Wybierz root z największą liczbą potomków (heurystyka)."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    best = None
    best_count = -1
    for r in candidates:
        desc = cmds.listRelatives(r, ad=True, fullPath=True) or []
        cnt = sum(1 for x in desc if cmds.nodeType(x) == "joint")
        if cnt > best_count:
            best_count = cnt
            best = r
    return best


def collect_skinned_mesh_transforms() -> List[str]:
    """Zbierz transformaty dla geometrii podpiętej do skinClusterów."""
    result = []
    skins = cmds.ls(type="skinCluster") or []
    for sc in skins:
        geos = cmds.skinCluster(sc, q=True, geometry=True) or []
        for g in geos:
            # g bywa shape’em → weź parent transform
            if cmds.nodeType(g) != "transform":
                parents = cmds.listRelatives(g, parent=True, fullPath=True) or []
                result.extend(parents)
            else:
                result.append(g)
    return sorted(set(result))


def select_rig_and_skinned(rig_root: Optional[str]) -> List[str]:
    """Zaznacz riga (hierarchia jointów) + wszystkie skinnowane meshe. Zwraca listę zaznaczonych."""
    selection = []
    if rig_root and cmds.objExists(rig_root):
        joints = [rig_root] + (cmds.listRelatives(rig_root, ad=True, type="joint", fullPath=True) or [])
        selection.extend(joints)
    else:
        # fallback: wszystkie joints (jeśli nie podano root’a)
        selection.extend(cmds.ls(type="joint", long=True) or [])

    # skinnowane meshe (transformaty)
    mesh_xforms = collect_skinned_mesh_transforms()
    selection.extend(mesh_xforms)

    # de-dupe
    selection = sorted(set(selection))
    if selection:
        cmds.select(selection, r=True)
    else:
        cmds.select(clear=True)
    return selection


# ------------------- USD export (via file options) -------------------

def export_usd_to_temp(
    scene_usd_name: str,
    export_all: bool = False,
    rig_root: Optional[str] = None,
    parent_scope: str = "/World/Char",
    export_blendshapes: bool = False,
    force_anim: Optional[bool] = None,  # True/False/None (auto)
    start_override: Optional[float] = None,
    end_override: Optional[float] = None,
    usd_format: str = "usdc",           # 'usdc'|'usda'
    merge_xform_shape: bool = True
) -> str:
    """
    Eksportuje USD do %TEMP% i zwraca jego ścieżkę.
    Domyślnie eksportuje TYLKO riga (jointy) + skinnowane meshe (exportSelected).
    Dla UsdSkel → WorldSpace=0 oraz exportSkels/Skin=explicit.
    """
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, scene_usd_name)

    scene_statistics()

    # anim: auto-detect (chyba, że wymuszone)
    has_anim, auto_start, auto_end = detect_anim_frame_range()
    export_anim = has_anim if force_anim is None else bool(force_anim)
    start = float(start_override if start_override is not None else (auto_start if export_anim else 1.0))
    end   = float(end_override   if end_override   is not None else (auto_end   if export_anim else 1.0))

    # KLUCZOWE: dla UsdSkel → WorldSpace=0 (nie bake do world)
    world_space = 0

    # zbuduj selekcję (chyba, że export_all)
    selected = []
    if export_all:
        cmds.select(clear=True)
    else:
        if not rig_root:
            # spróbuj wykryć root
            roots = find_joint_roots()
            log(f"[INFO] Found joint roots: {roots}")
            rig_root = pick_best_root(roots)
            log(f"[INFO] Picked rig root: {rig_root}")
        selected = select_rig_and_skinned(rig_root)
        log(f"[INFO] Selected {len(selected)} nodes for export (rig + skinned meshes).")

    # łańcuch opcji eksportera "USD Export"
    options = (
        f"ExportUVs=1;"
        f"ExportColorSets=1;"
        f"ExportDisplayColor=1;"
        f"ExportVisibility=1;"
        f"WorldSpace={world_space};"
        f"DynamicAttributes=1;"
        f"CurveDefaultWidth=1.0;"
        # UsdSkel — wymuś, żeby powstał SkelRoot
        f"exportSkels=explicit;"
        f"exportSkins=explicit;"
        f"exportBlendShapes={'1' if export_blendshapes else '0'};"
        # Animacja (SkelAnimation / time-samples)
        f"animation={'1' if export_anim else '0'};"
        f"eulerFilter=1;"
        f"staticSingleSample=0;"
        f"startTime={start};"
        f"endTime={end};"
        f"frameStride=1;"
        f"frameSample=0.0;"
        # Stabilny scope do łatwego namierzenia w Houdini
        f"parentScope={parent_scope};"
        # Format i inne
        f"mergeTransformAndShape={'1' if merge_xform_shape else '0'};"
        f"defaultUSDFormat={usd_format};"
    )

    # właściwy eksport
    if export_all:
        cmds.file(
            norm_path(tmp_usd),
            force=True,
            options=options,
            typ="USD Export",
            pr=True,
            ea=True  # export ALL
        )
    else:
        cmds.file(
            norm_path(tmp_usd),
            force=True,
            options=options,
            typ="USD Export",
            pr=True,
            es=True  # export SELECTED (rig + skinned)
        )

    # sanity-check
    tmp_usd_n = norm_path(tmp_usd)
    log(f"[OK] USD exported to TEMP: {tmp_usd_n}")
    try:
        size = os.path.getsize(tmp_usd)
        log(f"[INFO] TEMP file size: {size} bytes")
        if size < 2048:
            log("[WARN] Plik USD jest bardzo mały (<2KB) — sprawdź selekcję/rig.")
    except Exception as e:
        log(f"[WARN] Nie mogę odczytać rozmiaru pliku: {e}")

    if export_anim:
        log(f"[INFO] SkelAnimation ON, frames: {start}..{end}")
    log(f"[INFO] parentScope={parent_scope}, WorldSpace={world_space}, format={usd_format}")
    return tmp_usd


# ------------------- main -------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.usd)")

    # tryb eksportu
    ap.add_argument("--exportAll", action="store_true",
                    help="Eksportuj całą scenę (domyślnie: tylko rig + skinnowane meshe)")

    # kontrola riga
    ap.add_argument("--rigRoot", type=str, default=None,
                    help="Ścieżka DAG do root jointa (np. |Model_grp|Root_JNT). Jeśli nie podasz, skrypt wybierze najlepszy kandydat.")

    # UsdSkel / anim / itp.
    ap.add_argument("--blendshapes", action="store_true", help="Eksport blend-shapes (exportBlendShapes=1)")
    ap.add_argument("--exportAnimation", action="store_true",
                    help="Wymuś eksport animacji (w przeciwnym razie auto-wykrywanie)")
    ap.add_argument("--start", type=float, default=None, help="Start klatek animacji (opcjonalnie)")
    ap.add_argument("--end", type=float, default=None, help="Koniec klatek animacji (opcjonalnie)")
    ap.add_argument("--parentScope", type=str, default="/World/Char",
                    help="Docelowy scope/root w USD (łatwy cel dla Houdini)")
    ap.add_argument("--usdFormat", choices=["usdc", "usda"], default="usdc",
                    help="Format wyjściowy USD (binarny usdc lub ASCII usda)")
    ap.add_argument("--noMergeXformShape", action="store_true",
                    help="Wyłącz mergeTransformAndShape (domyślnie włączone)")

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

        tmp_usd = export_usd_to_temp(
            scene_usd_name=os.path.basename(final_usd),
            export_all=args.exportAll,
            rig_root=args.rigRoot,
            parent_scope=args.parentScope,
            export_blendshapes=args.blendshapes,
            force_anim=(True if args.exportAnimation else None),
            start_override=args.start,
            end_override=args.end,
            usd_format=args.usdFormat,
            merge_xform_shape=(not args.noMergeXformShape),
        )

        # kopiowanie z retry
        ok, err = copy_with_retry(tmp_usd, final_usd)
        if ok:
            try:
                size = os.path.getsize(final_usd)
                log(f"[OK] USD copied to destination: {final_usd} (size={size} bytes)")
                if size < 2048:
                    log("[WARN] Docelowy USD bardzo mały (<2KB) — sprawdź, czy selekcja zawiera rig i skinnowane meshe.")
            except Exception:
                log(f"[OK] USD copied to destination: {final_usd}")
            status = 0
        else:
            log(f"[ERROR] USD copy failed to '{final_usd}': {err}")
            status = 1

        sys.stdout.flush()
        sys.stderr.flush()
    except Exception as e:
        log(f"[ERROR] Unhandled exception: {e}")
        status = 1
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        # kończymy brutalnie → brak crasha na cleanupie pluginów
        os._exit(status)


if __name__ == "__main__":
    main()
