# -*- coding: utf-8 -*-
"""
Alembic-only exporter for mayapy (Maya 2025)
- output: <sceneName>.abc in --outputBasePath
- direct write to UNC (no TEMP staging/copy)

"""
# & "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" `
# >>   "C:\Users\wesol\git\PI_lego\maya_export_geo.py" `
# >>   --inputFile "C:\Users\wesol\git\PI_lego\ma\setofdoom.ma" `
# >>   --outputBasePath "C:\Users\wesol\git\PI_lego\tmp_export\"




import argparse, os, sys
import maya.standalone
import maya.cmds as cmds

def norm(p): return os.path.normpath(p) if p else p
def ensure_dir(p): os.makedirs(p, exist_ok=True); return p

def load_alembic_plugin():
    # Maya 2025: plugin id "AbcExport"
    try:
        if not cmds.pluginInfo("AbcExport", q=True, loaded=True):
            cmds.loadPlugin("AbcExport", quiet=True)
    except Exception as e:
        print(f"❌ AbcExport plugin load failed: {e}")
        raise

def get_top_roots_from_selection_or_scene():
    sel = cmds.ls(sl=True, long=True, type="transform") or []
    if not sel:
        # cały scene graph: weź top-level transformy niebędące defaultami
        all_transforms = cmds.ls(assemblies=True, long=True) or []
        # odfiltruj systemowe
        top = [n for n in all_transforms if not n.startswith("|__") and n not in ("|persp","|top","|front","|side")]
    else:
        # dla selekcji: eksportuj ich top-level parenty, bez duplikatów / zawężeń
        top = []
        for n in sel:
            root = n.split("|")[1] if n.startswith("|") else n  # pierwszy segment
            full = "|" + root
            if full not in top:
                top.append(full)
    return top

def build_abc_job_args(roots, start_frame, end_frame, step,
                       world_space=True, uvs=True, colors=True,
                       visibility=True, euler_filter=True,
                       write_creases=True, write_face_sets=False,
                       write_normals=True, strip_namespaces=True):
    args = []
    # frame range
    args += ["-frameRange", str(start_frame), str(end_frame)]
    if step and step > 0:
        args += ["-step", str(step)]
    # write options
    if world_space:   args += ["-worldSpace"]
    if uvs:           args += ["-uvWrite"]
    if colors:        args += ["-writeColorSets"]
    if visibility:    args += ["-writeVisibility"]
    if write_normals: args += ["-writeNormals"]
    if write_creases: args += ["-writeCreases"]
    if write_face_sets: args += ["-writeFaceSets"]
    if euler_filter:  args += ["-eulerFilter"]
    if strip_namespaces: args += ["-stripNamespaces", "-stripNamespaces", "1"]
    # data format: Ogawa (domyślnie), nic nie trzeba dopisywać
    # roots
    for r in roots:
        args += ["-root", r]
    return args

def export_alembic(final_abc_path, start_frame, end_frame, step):
    ensure_dir(os.path.dirname(final_abc_path))

    # honoruj selekcję; jeśli pusto -> wszystkie top-levely
    roots = get_top_roots_from_selection_or_scene()
    if not roots:
        print("⚠️ Brak niczego do eksportu (nie znaleziono transformów).")
        return False

    job_args = build_abc_job_args(
        roots=roots,
        start_frame=start_frame,
        end_frame=end_frame,
        step=step,
        world_space=True,
        uvs=True,
        colors=True,
        visibility=True,
        euler_filter=True,
        write_creases=True,
        write_face_sets=False,
        write_normals=True,
        strip_namespaces=True
    )

    # koniecznie forward slashe dla AbcExport
    final_abc_path = final_abc_path.replace("\\", "/")
    job_args += ["-file", final_abc_path]

    try:
        # AbcExport przyjmuje jeden string komend
        cmds.AbcExport(j=" ".join(job_args))
        print(f"✅ Alembic exported to: {final_abc_path}")
        return True
    except Exception as e:
        print(f"❌ Alembic export failed: {e}")
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder docelowy (powstanie <scene>.abc)")
    ap.add_argument("--frameStart", type=float, default=None, help="Start frame (domyślnie bieżąca klatka)")
    ap.add_argument("--frameEnd", type=float, default=None, help="End frame (domyślnie bieżąca klatka)")
    ap.add_argument("--step", type=float, default=1.0, help="Krok próbkowania (domyślnie 1.0)")
    args = ap.parse_args()

    input_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_abc = norm(os.path.join(out_dir, base + ".abc"))

    maya.standalone.initialize(name='python')
    try:
        load_alembic_plugin()
        # otwarcie pliku
        cmds.file(input_file.replace("\\", "/"), open=True, force=True)

        # domyślna klatka = bieżący czas sceny
        current = cmds.currentTime(q=True)
        start = args.frameStart if args.frameStart is not None else current
        end   = args.frameEnd   if args.frameEnd   is not None else current

        ok = export_alembic(final_abc, start, end, args.step)
        sys.stdout.flush(); sys.stderr.flush()
        sys.exit(0 if ok else 1)
    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass

if __name__ == "__main__":
    main()
