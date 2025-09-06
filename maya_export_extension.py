# -*- coding: utf-8 -*-
"""
Maya batch exporter: USD / FBX / Alembic
- nazwy wyjściowe na bazie nazwy pliku wejściowego
- fix dla USD na udziałach sieciowych:
  * ustawia USD_LAYER_TMP_DIR na lokalny TMP
  * próbuje 'fileSafetyMode=none'
  * ma fallback: eksport do %TEMP% i kopiowanie na docelowy folder
"""

import argparse
import os
import shutil
import tempfile
import time
import getpass

import maya.standalone
import maya.cmds as cmds
import maya.mel as mel

# ---------- helpers ----------

def norm(p):
    return os.path.normpath(p) if p else p

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path

def can_write(dirpath):
    """Zwraca (True, None) jeśli zapis możliwy, inaczej (False, Exception)."""
    dirpath = ensure_dir(dirpath)
    test = os.path.join(dirpath, "_writetest.tmp")
    try:
        with open(test, "wb") as f:
            f.write(b"x")
        os.remove(test)
        return True, None
    except Exception as e:
        return False, e

def copy_with_retry(src, dst, retries=5, delay=0.5):
    ensure_dir(os.path.dirname(dst))
    for i in range(retries):
        try:
            shutil.copy2(src, dst)
            return True, None
        except Exception as e:
            if i == retries - 1:
                return False, e
            time.sleep(delay * (i + 1))

def move_with_retry(src, dst, retries=5, delay=0.5):
    ensure_dir(os.path.dirname(dst))
    for i in range(retries):
        try:
            shutil.move(src, dst)
            return True, None
        except Exception as e:
            if i == retries - 1:
                return False, e
            time.sleep(delay * (i + 1))

def top_level_transforms():
    # Pomijamy standardowe systemowe: |persp|top|front|side jeśli istnieją
    sys_cams = set(cmds.listCameras() or [])
    assemblies = cmds.ls(assemblies=True, long=True) or []
    return [a for a in assemblies if os.path.basename(a) not in sys_cams]

def load_plugins():
    for plug in ("mayaUsdPlugin", "fbxmaya", "AbcExport"):
        try:
            if not cmds.pluginInfo(plug, q=True, loaded=True):
                cmds.loadPlugin(plug, quiet=True)
        except Exception:
            # FBX/Alembic/USD są opcjonalnie instalowane; brak = pomijamy
            pass

# ---------- exporters ----------

def export_usd(final_base_noext):
    """
    Próbuje bezpośredni zapis USD do finalnej ścieżki z:
      - USD_LAYER_TMP_DIR = TMP
      - fileSafetyMode=none
    Jeśli się nie uda, robi staging do %TEMP% i kopiuje na docelowy folder.
    """
    usd_final = final_base_noext + ".usd"
    ensure_dir(os.path.dirname(usd_final))

    # 1) ustaw TMP dla USD (staging tymczasowy poza udziałem sieciowym)
    os.environ["USD_LAYER_TMP_DIR"] = tempfile.gettempdir()

    # 2) Select all (USD exporter honoruje selection)
    if not cmds.ls(sl=True):
        cmds.select(all=True)

    options = "ExportUVs=1;ExportColorSets=1;fileSafetyMode=none;"
    try:
        cmds.file(usd_final, force=True, options=options, typ="USD Export", pr=True, es=True)
        print(f"✅ USD exported to: {usd_final}")
        return
    except Exception as e_direct:
        print(f"⚠️ USD direct export failed: {e_direct}")

    # 3) fallback: eksport do %TEMP%, potem kopiowanie na docelowy folder
    tmp_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "usd_staging", getpass.getuser()))
    tmp_usd = os.path.join(tmp_dir, os.path.basename(usd_final))
    try:
        cmds.file(tmp_usd, force=True, options=options, typ="USD Export", pr=True, es=True)
        ok, err = copy_with_retry(tmp_usd, usd_final)
        if ok:
            print(f"✅ USD staged to TEMP and copied to: {usd_final}")
        else:
            print(f"❌ USD copy failed: {err}")
    except Exception as e_stage:
        print(f"❌ USD staging export failed: {e_stage}")

def export_fbx(final_base_noext):
    fbx_file = final_base_noext + ".fbx"
    ensure_dir(os.path.dirname(fbx_file))
    try:
        if not cmds.ls(sl=True):
            cmds.select(all=True)
        # Możesz ustawić własne opcje FBX; zostawiamy puste dla szerokiej kompatybilności
        cmds.file(fbx_file, force=True, options="", typ="FBX export", pr=True, es=True)
        print(f"✅ FBX exported to: {fbx_file}")
    except Exception as e:
        print(f"❌ FBX export failed: {e}")

def export_abc(final_base_noext, frame_start=1, frame_end=1):
    abc_file = final_base_noext + ".abc"
    ensure_dir(os.path.dirname(abc_file))
    try:
        roots = top_level_transforms()
        if not roots:
            raise RuntimeError("No top-level transforms found for Alembic export.")
        roots_args = " ".join([f"-root {r}" for r in roots])
        mel.eval(
            'AbcExport -j "-frameRange {fs} {fe} {roots} -uvWrite -writeColorSets -file \\"{out}\\""' \
            .format(fs=frame_start, fe=frame_end, roots=roots_args, out=abc_file)
        )
        print(f"✅ Alembic exported to: {abc_file}")
    except Exception as e:
        print(f"❌ Alembic export failed: {e}")

# ---------- main ----------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputFile", required=True, help="Ścieżka do pliku .ma/.mb")
    parser.add_argument("--outputBasePath", required=True, help="Folder wyjściowy")
    # opcjonalnie możesz odkomentować dodatkowe parametry:
    # parser.add_argument("--frameStart", type=int, default=1)
    # parser.add_argument("--frameEnd", type=int, default=1)
    args = parser.parse_args()

    input_file = norm(args.inputFile)
    out_dir = norm(args.outputBasePath)
    ensure_dir(out_dir)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    final_base = norm(os.path.join(out_dir, base_name))

    maya.standalone.initialize(name='python')
    try:
        load_plugins()
        cmds.file(input_file.replace("\\", "/"), open=True, force=True)

        # Exporty
        export_usd(final_base)
        export_fbx(final_base)
        export_abc(final_base)  # , frame_start=args.frameStart, frame_end=args.frameEnd

    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
