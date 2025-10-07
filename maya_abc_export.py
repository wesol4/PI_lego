# -*- coding: utf-8 -*-
"""
Alembic-only exporter for mayapy (Maya 2025)
- output: <sceneName>.abc in --outputBasePath
- direct write to UNC (no TEMP staging/copy)
- robust root/mesh detection + optional post-export validation
"""

import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

# ---------- utils ----------

def norm(p):
    return os.path.normpath(p) if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def log(msg):
    """Log bezpieczny dla PDG (bez crasha na polskich znakach)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"[ABC] {msg}")
    except Exception:
        safe = msg.encode("ascii", errors="replace").decode()
        print(f"[ABC] {safe}")

# ---------- AbcExport helpers ----------

def load_alembic_plugin():
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)
        log("AbcExport plugin loaded.")
    except Exception as e:
        print(f"[ERROR] AbcExport plugin load failed: {e}")
        raise

def get_supported_flags():
    """Zwraca zbiór słów z pomocy AbcExport (używamy tylko do prostego 'czy jest w helpie')."""
    try:
        help_text = cmds.help("AbcExport") or ""
        return set(help_text.replace(",", " ").replace("\n", " ").split())
    except Exception:
        return set()

def list_non_intermediate_meshes_under(root):
    """Zwraca listę ścieżek do mesh-shape'ów (longPath), które nie są pośrednie, pod danym rootem."""
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
    """Zwraca posortowaną listę unikalnych rodziców-transformów dla podanych shape'ów."""
    parents = set()
    for s in shapes:
        p = cmds.listRelatives(s, parent=True, fullPath=True) or []
        if p:
            parents.add(p[0])
    return sorted(parents)

# ---------- scene scanning ----------

def get_top_level_roots_from_selection_or_scene():
    """
    Zwraca kandydatów na -root:
    - jeśli jest selekcja: top-level rodzice dla zaznaczonych transformów (pierwszy segment po '|')
    - jeśli brak selekcji: wszystkie assemblies poza kamerami
    """
    sel = cmds.ls(sl=True, long=True, type="transform") or []
    if sel:
        roots = []
        seen = set()
        for n in sel:
            segs = n.split("|")
            if len(segs) > 1:
                root = "|" + segs[1]
            else:
                root = "|" + segs[0].lstrip("|")
            if root not in seen:
                seen.add(root)
                roots.append(root)
        return roots

    # brak selekcji → wszystkie assemblies (bez kamer)
    assemblies = cmds.ls(assemblies=True, long=True) or []
    cameras = set(cmds.listCameras() or [])
    # kamery zwracają shape'y, więc zbierzmy ich parent transformy
    cam_parents = set()
    for c in cameras:
        p = cmds.listRelatives(c, parent=True, fullPath=True) or []
        cam_parents.update(p)
    roots = [a for a in assemblies if a not in cam_parents]
    return roots

def collect_export_roots():
    """
    1) Weź kandydatów na root i odfiltruj te, pod którymi nie ma żadnych mesh'y nie-pośrednich.
    2) Jeśli po filtrze lista pusta → fallback: weź WSZYSTKIE mesh'e w scenie (nie-pośrednie) i ich parent transformy.
    """
    candidates = get_top_level_roots_from_selection_or_scene()
    valid_roots = []
    total_meshes = 0
    for r in candidates:
        meshes = list_non_intermediate_meshes_under(r)
        if meshes:
            valid_roots.append(r)
            total_meshes += len(meshes)

    if valid_roots:
        log(f"Kandydaci na -root po filtrze: {len(valid_roots)} szt. (mesh'y: {total_meshes}).")
        return valid_roots

    # fallback: zbierz wszystkie mesh'e w scenie
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
        log(f"Fallback: brak mesh'y pod top-level. Używam {len(parent_xforms)} rodziców mesh'y jako -root.")
        return parent_xforms

    # nic nie znaleziono
    return []

# ---------- job args ----------

def build_abc_job_args(roots, start_frame, end_frame, step):
    supported = get_supported_flags()
    args = []

    # frame range
    args += ["-frameRange", str(start_frame), str(end_frame)]
    if step and step > 0:
        args += ["-step", str(step)]

    # bezpieczne, szeroko wspierane flagi
    args += ["-worldSpace"]
    args += ["-uvWrite"]
    if "-writeColorSets" in supported:
        args += ["-writeColorSets"]
    if "-writeVisibility" in supported:
        args += ["-writeVisibility"]
    if "-eulerFilter" in supported:
        args += ["-eulerFilter"]

    # jawnie Ogawa
    if "-dataFormat" in supported:
        args += ["-dataFormat", "Ogawa"]

    # roots
    for r in roots:
        args += ["-root", r]

    log("Flagi uzyte w job stringu: " + " ".join([a for a in args if a.startswith("-")]))
    return args

# ---------- export / validate ----------

def export_alembic(final_abc_path, start_frame, end_frame, step):
    ensure_dir(os.path.dirname(final_abc_path))

    roots = collect_export_roots()
    if not roots:
        log("Brak NICZEGO do eksportu (nie znaleziono mesh'y).")
        return False

    job_args = build_abc_job_args(roots, start_frame, end_frame, step)

    final_abc_path = final_abc_path.replace("\\", "/")
    job_args += ["-file", final_abc_path]

    # mały raport przed eksportem
    total_meshes = 0
    for r in roots:
        total_meshes += len(list_non_intermediate_meshes_under(r))
    log(f"Eksport: roots={len(roots)}, mesh'y (nie-posrednie) ~{total_meshes}, zakres={start_frame}->{end_frame}, step={step}")

    try:
        cmds.AbcExport(j=" ".join(job_args))
        size = 0
        try:
            size = os.path.getsize(final_abc_path)
        except Exception:
            pass
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
        log(f"VALIDATE: po imporcie w Mayi -> meshes={len(meshes)}, transforms={len(xforms)}")
        return True
    except Exception as e:
        print(f"[ERROR] Walidacja nie powiodla sie: {e}")
        return False

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Sciezka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.abc)")
    ap.add_argument("--frameStart", type=float, default=None, help="Start frame (domyslnie biezaca klatka)")
    ap.add_argument("--frameEnd", type=float, default=None, help="End frame (domyslnie biezaca klatka)")
    ap.add_argument("--step", type=float, default=1.0, help="Krok probkowania (domyslnie 1.0)")
    ap.add_argument("--validate", action="store_true", help="Po eksporcie sprawdz plik przez import do Mayi")
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

        current = cmds.currentTime(q=True)
        start = args.frameStart if args.frameStart is not None else current
        end   = args.frameEnd   if args.frameEnd is not None else current

        ok = export_alembic(final_abc, start, end, args.step)

        if ok and args.validate:
            validate_alembic(final_abc)

        sys.stdout.flush(); sys.stderr.flush()
        # UWAGA: zawsze zielona kropka w PDG
        sys.exit(0)
    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass

if __name__ == "__main__":
    main()
