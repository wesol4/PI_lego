# maya_export_alembic_helpers.py
# Eksport helperów (locatory/Null-e) do Alembic .abc z Mayi (mayapy/standalone).
# Autor: ChatGPT — LEGO TEST HELPER ABC

import os
import sys
import argparse
import traceback

# --- Maya standalone ---
import maya.standalone
maya.standalone.initialize(name="python")

import maya.cmds as cmds


def log(msg: str):
    print(msg)
    sys.stdout.flush()


def ensure_dir(path: str):
    d = os.path.dirname(path) if os.path.splitext(path)[1] else path
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def load_alembic_plugin():
    # AbcExport jest pluginem — w mayapy trzeba go jawnie załadować
    if not cmds.pluginInfo("AbcExport", query=True, loaded=True):
        try:
            # Spróbuj przez nazwę
            cmds.loadPlugin("AbcExport")
            log("✅ Załadowano plugin AbcExport")
        except Exception:
            # Spróbuj pełną ścieżką (typowa dla Windows)
            candidate = r"C:\Program Files\Autodesk\Maya2025\bin\plug-ins\AbcExport.mll"
            if os.path.exists(candidate):
                cmds.loadPlugin(candidate)
                log(f"✅ Załadowano plugin AbcExport: {candidate}")
            else:
                raise RuntimeError("❌ Nie udało się załadować AbcExport.mll — sprawdź instalację Mayi.")


def open_scene(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ Brak pliku sceny: {path}")
    log(f"📂 Otwieram scenę: {path}")
    cmds.file(new=True, force=True)
    cmds.file(path, open=True, force=True, prompt=False)


def find_locator_transforms():
    """
    Zwróć listę transformów, które mają shape typu 'locator'.
    """
    loc_shapes = cmds.ls(type="locator") or []
    if not loc_shapes:
        return []
    transforms = cmds.listRelatives(loc_shapes, parent=True, fullPath=True) or []
    # Upewnij się o unikalności i pełnych ścieżkach
    transforms = list(dict.fromkeys([cmds.ls(t, long=True)[0] for t in transforms]))
    return transforms


def get_toplevel_roots(nodes):
    """
    Z listy długich ścieżek wybiera tylko top-level (takie, które nie są potomkami innych w tej liście).
    """
    if not nodes:
        return []
    nodes = sorted(set(nodes), key=lambda x: x.count('|'))  # krótsze ścieżki pierwsze
    roots = []
    for n in nodes:
        if not any(n != r and n.startswith(r + '|') for r in roots):
            roots.append(n)
    return roots


def discover_helper_roots():
    """
    Znajdź sensowne rooty helperów:
    - locatory → ich transformaty → top-level
    - jeśli pusto, spróbuj nazwy z frazami 'Helper'/'helpers'
    """
    loc_xforms = find_locator_transforms()
    if loc_xforms:
        roots = get_toplevel_roots(loc_xforms)
        if roots:
            log(f"🔎 Znaleziono locatory (rooty xform): {len(roots)}")
            return roots

    # Szukanie po nazwach (fallback)
    candidates = cmds.ls("*Helper*", "*helpers*", type="transform", long=True) or []
    if candidates:
        roots = get_toplevel_roots(candidates)
        if roots:
            log(f"🔎 Fallback po nazwie — rooty: {len(roots)}")
            return roots

    return []


def scene_name_base():
    sc = cmds.file(q=True, sn=True) or "scene"
    base = os.path.splitext(os.path.basename(sc))[0]
    return base


def build_abc_job_string(roots, frame, world_space=True, attr_prefixes=None, euler_filter=True, ogawa=True):
    """
    Buduje listę argumentów job stringa dla AbcExport.
    """
    args = []
    # Pojedyncza klatka
    f = str(int(frame))
    args += ['-frameRange', f, f]

    if world_space:
        args += ['-worldSpace']

    # Atrybuty użytkownika
    attr_prefixes = attr_prefixes or []
    for p in attr_prefixes:
        # AbcExport rozumie -attrPrefix <prefix>
        args += ['-attrPrefix', p]

    # Jakość/format
    if euler_filter:
        args += ['-eulerFilter']
    if ogawa:
        args += ['-dataFormat', 'ogawa']

    # Widoczność/UV (na wszelki wypadek, chociaż helpery nie mają UV)
    args += ['-uvWrite', '-writeVisibility']

    # Rooty
    for r in roots:
        args += ['-root', r]

    return args


def export_alembic(abc_path, roots, frame, world_space, attr_prefixes):
    ensure_dir(abc_path)
    job_args = build_abc_job_string(
        roots=roots,
        frame=frame,
        world_space=world_space,
        attr_prefixes=attr_prefixes,
        euler_filter=True,
        ogawa=True
    )
    job_args += ['-file', abc_path]
    job_str = ' '.join(job_args)

    log("▶️ AbcExport args:")
    log("    " + job_str)

    cmds.AbcExport(j=job_str)
    log(f"✅ Wyeksportowano Alembic: {abc_path}")


def main():
    parser = argparse.ArgumentParser(description="Export helpers (locators) to Alembic .abc (world space).")
    parser.add_argument('--inputFile', required=True, help='Ścieżka do pliku .ma/.mb/.maya')
    parser.add_argument('--outputBasePath', required=True, help='Katalog wyjściowy albo pełna ścieżka do pliku .abc')
    parser.add_argument('--root', action='append', default=None,
                        help='Pełna ścieżka root transform (można podać wielokrotnie). Np. "|Helpers_EXPORT"')
    parser.add_argument('--frame', type=int, default=100, help='Klatka do eksportu (domyślnie 100)')
    parser.add_argument('--noWorldSpace', action='store_true', help='Eksport w lokalnych transformach (domyślnie world)')
    parser.add_argument('--attrPrefix', action='append', default=[],
                        help='Prefiks atrybutów użytkownika do eksportu (można podać wielokrotnie), np. VME_, vrayUser')
    args = parser.parse_args()

    try:
        load_alembic_plugin()
        open_scene(args.inputFile)

        # Rooty: podane → użyj; inaczej spróbuj znaleźć
        if args.root:
            roots = []
            for r in args.root:
                full = cmds.ls(r, long=True) or []
                if not full:
                    log(f"⚠️ Nie znaleziono roota: {r}")
                else:
                    roots += full
            roots = get_toplevel_roots(roots)
        else:
            roots = discover_helper_roots()

        if not roots:
            raise RuntimeError("❌ Nie znaleziono żadnych rootów helperów. Podaj --root lub dodaj locatory do sceny.")

        # Zbuduj ścieżkę wyjściową
        if args.outputBasePath.lower().endswith('.abc'):
            abc_path = args.outputBasePath
        else:
            base_dir = args.outputBasePath
            ensure_dir(base_dir)
            base_name = scene_name_base()
            abc_path = os.path.join(base_dir, f"{base_name}_helpers.abc")

        export_alembic(
            abc_path=abc_path,
            roots=roots,
            frame=args.frame,
            world_space=(not args.noWorldSpace),
            attr_prefixes=args.attrPrefix,
        )

        log("🎉 DONE")
        return 0

    except Exception as e:
        log("💥 Błąd eksportu Alembic:")
        log(str(e))
        traceback.print_exc()
        return 1

    finally:
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
