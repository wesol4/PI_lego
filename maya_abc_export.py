# -*- coding: utf-8 -*-
"""
Alembic-only exporter for Maya 2025 (mayapy-safe, PDG-safe)
----------------------------------------------------------
Eksportuje:
 - geometrię (worldSpace)
 - wszystkie UV sety
 - color sets
 - visibility
 - eulerFilter
 - creaseWeight / creaseEdges / creaseVertices
Zapis bezpośrednio do UNC / bez stagingu.
"""

import argparse, os, sys, time
import maya.standalone
import maya.cmds as cmds

# ---------- utils ----------

def norm(p):
    return os.path.normpath(p) if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def log(msg):
    """UTF-8 safe logger for PDG."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"[ABC] {msg}")
    except Exception:
        safe = msg.encode("ascii", errors="replace").decode()
        print(f"[ABC] {safe}")

# ---------- Alembic helpers ----------

def load_alembic_plugin():
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)
        log("AbcExport plugin loaded.")
    except Exception as e:
        print(f"[ERROR] AbcExport plugin load failed: {e}")
        raise

def list_non_intermediate_meshes_under(root):
    shapes = cmds.listRelatives(root, ad=True, type="mesh", fullPath=True) or []
    out = []
    for s in shapes:
        try:
            if not cmds.getAttr(s + ".intermediateObject"):
                out.append(s)
        except Exception:
            pass
    return out

def unique_parent_transforms(shapes):
    parents = set()
    for s in shapes:
        p = cmds.listRelatives(s, parent=True, fullPath=True) or []
        if p:
            parents.add(p[0])
    return sorted(parents)

# ---------- scene scanning ----------

def get_top_level_roots_from_selection_or_scene():
    sel = cmds.ls(sl=True, long=True, type="transform") or []
    if sel:
        roots, seen = [], set()
        for n in sel:
            segs = n.split("|")
            root = "|" + segs[1] if len(segs) > 1 else "|" + segs[0].lstrip("|")
            if root not in seen:
                seen.add(root)
                roots.append(root)
        return roots

    assemblies = cmds.ls(assemblies=True, long=True) or []
    cameras = set(cmds.listCameras() or [])
    cam_parents = set(cmds.listRelatives(cameras, parent=True, fullPath=True) or [])
    return [a for a in assemblies if a not in cam_parents]

def collect_export_roots():
    candidates = get_top_level_roots_from_selection_or_scene()
    valid_roots, total_meshes = [], 0
    for r in candidates:
        meshes = list_non_intermediate_meshes_under(r)
        if meshes:
            valid_roots.append(r)
            total_meshes += len(meshes)

    if valid_roots:
        log(f"Kandydaci na -root po filtrze: {len(valid_roots)} szt. (mesh'y: {total_meshes})")
        return valid_roots

    # fallback → all non-intermediate meshes in scene
    all_shapes = cmds.ls(type="mesh", long=True) or []
    non_intermediate = []
    for s in all_shapes:
        try:
            if not cmds.getAttr(s + ".intermediateObject"):
                non_intermediate.append(s)
        except Exception:
            pass
    parent_xforms = unique_parent_transforms(non_intermediate)
    if parent_xforms:
        log(f"Fallback: używam {len(parent_xforms)} rodziców mesh'y jako -root.")
        return parent_xforms

    return []

# ---------- job args ----------

def build_abc_job_args(roots, start_frame, end_frame, step):
    """
    Buduje job string dla AbcExport:
    - zawsze eksportuje UV, color sets, visibility, creases
    """
    args = []
    args += ["-frameRange", str(start_frame), str(end_frame)]
    if step and step > 0:
        args += ["-step", str(step)]

    args += [
        "-worldSpace",
        "-uvWrite",
        "-writeUVSets",
        "-writeColorSets",
        "-writeVisibility",
        "-writeCreases",     # <--- kluczowa flaga: creaseWeight / creaseEdges
        "-eulerFilter",
        "-dataFormat", "Ogawa"
    ]

    for r in roots:
        args += ["-root", r]

    log("Flagi użyte w job stringu: " + " ".join([a for a in args if a.startswith("-")]))
    return args

# ---------- export / validate ----------

def export_alembic(final_abc_path, start_frame, end_frame, step):
    ensure_dir(os.path.dirname(final_abc_path))

    roots = collect_export_roots()
    log(f"DEBUG: znalezione roots: {roots}")
    if not roots:
        all_meshes = cmds.ls(type="mesh", long=True) or []
        log(f"DEBUG: meshes w scenie: {len(all_meshes)} → {all_meshes[:5]}")
        log("Brak NICZEGO do eksportu (nie znaleziono mesh'y).")
        return False

    job_args = build_abc_job_args(roots, start_frame, end_frame, step)
    final_abc_path = final_abc_path.replace("\\", "/")
    job_args += ["-file", final_abc_path]

    # test zapisu
    try:
        with open(final_abc_path, "wb") as f:
            f.write(b"TEST")
        os.remove(final_abc_path)
        log("Test zapisu: OK (folder dostępny).")
    except Exception as e:
        log(f"[ERROR] test zapisu nieudany: {e}")
        return False

    total_meshes = sum(len(list_non_intermediate_meshes_under(r)) for r in roots)
    log(f"Eksport: roots={len(roots)}, mesh'y~{total_meshes}, zakres={start_frame}->{end_frame}, step={step}")

    try:
        cmds.AbcExport(j=" ".join(job_args))
        cmds.flushUndo()
        cmds.file(save=True)
        time.sleep(1)

        if not os.path.exists(final_abc_path):
            log("[ERROR] Plik Alembic NIE istnieje po eksporcie!")
            return False

        size = os.path.getsize(final_abc_path)
        log(f"OK: zapisano Alembic: {final_abc_path} (rozmiar: {size} B)")
        return True
    except Exception as e:
        print(f"[ERROR] Alembic export failed: {e}")
        return False

def validate_alembic(abc_path):
    try:
        cmds.file(new=True, force=True)
        cmds.AbcImport(abc_path.replace("\\", "/"), mode="import")
        meshes = cmds.ls(type="mesh") or []
        xforms = cmds.ls(type="transform") or []
        log(f"VALIDATE: po imporcie → meshes={len(meshes)}, transforms={len(xforms)}")
        return True
    except Exception as e:
        print(f"[ERROR] Walidacja nie powiodła się: {e}")
        return False

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.abc)")
    ap.add_argument("--frameStart", type=float, default=None, help="Start frame (domyślnie bieżąca klatka)")
    ap.add_argument("--frameEnd", type=float, default=None, help="End frame (domyślnie bieżąca klatka)")
    ap.add_argument("--step", type=float, default=1.0, help="Krok próbkowania (domyślnie 1.0)")
    ap.add_argument("--validate", action="store_true", help="Po eksporcie sprawdź plik przez import do Mayi")
    args = ap.parse_args()

    input_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_abc = norm(os.path.join(out_dir, base + ".abc"))

    maya.standalone.initialize(name='python')
    try:
        load_alembic_plugin()
        cmds.file(input_file.replace("\\", "/"), open=True, force=True)
        cmds.refresh(force=True)

        current = cmds.currentTime(q=True)
        start = args.frameStart if args.frameStart is not None else current
        end   = args.frameEnd   if args.frameEnd is not None else current

        ok = export_alembic(final_abc, start, end, args.step)
        if ok and args.validate:
            validate_alembic(final_abc)

        sys.stdout.flush()
        sys.stderr.flush()
        time.sleep(0.5)
        sys.exit(0)
    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass

if __name__ == "__main__":
    main()
