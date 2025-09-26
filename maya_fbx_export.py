# -*- coding: utf-8 -*-
"""
FBX exporter for mayapy (Maya 2025)
- output: <sceneName>.fbx w --outputBasePath
- staging do TEMP (lub własny katalog) i kopiowanie na UNC (omija locki/permissions)
"""

import argparse, os, shutil, tempfile, time, getpass, sys
import maya.standalone
import maya.cmds as cmds

def norm_path(p: str) -> str:
    return os.path.normpath(p).replace("\\", "/") if p else p

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

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

def load_fbx_plugin():
    try:
        if not cmds.pluginInfo("fbxmaya", q=True, loaded=True):
            cmds.loadPlugin("fbxmaya", quiet=True)
            print("[OK] fbxmaya plugin loaded")
    except Exception as e:
        print(f"[ERROR] fbxmaya plugin load failed: {e}")
        raise

def open_scene(input_file):
    """Bezpieczne otwieranie sceny z pominięciem starych pluginów i atrybutów"""
    try:
        cmds.file(input_file,
                  open=True,
                  force=True,
                  ignoreVersion=True,
                  prompt=False,
                  options="v=0;",
                  suppressReferenceEdits=True)
        print(f"[OK] Scene opened: {input_file}")
    except Exception as e:
        print(f"[ERROR] Scene open failed: {e}")
        raise

def get_staging_dir():
    """Można ustawić własny staging folder na dysku z dużą ilością miejsca"""
    # custom_tmp = "D:/maya_fbx_staging"  # <- ustaw np. na dysku D:
    custom_tmp = os.path.join(tempfile.gettempdir(), "fbx_staging")
    path = os.path.join(custom_tmp, getpass.getuser())
    ensure_dir(path)
    return path

def export_fbx(final_fbx_path: str):
    ensure_dir(os.path.dirname(final_fbx_path))
    if not cmds.ls(sl=True):
        cmds.select(all=True)

    cmds.FBXResetExport()
    cmds.FBXExportSmoothingGroups('-v', True)
    cmds.FBXExportSmoothMesh('-v', True)
    cmds.FBXExportShapes('-v', True)
    cmds.FBXExportSkins('-v', True)
    cmds.FBXExportCameras('-v', True)
    cmds.FBXExportLights('-v', False)
    cmds.FBXExportEmbeddedTextures('-v', False)
    cmds.FBXExportInputConnections('-v', True)
    cmds.FBXExportUseSceneName('-v', False)

    # Próba bezpośredniego eksportu
    try:
        cmds.FBXExport('-f', final_fbx_path, '-s')
        print(f"[OK] FBX exported directly to: {final_fbx_path}")
        return True
    except Exception as e_direct:
        print(f"[WARN] Direct FBX export failed: {e_direct}")

    # Staging do folderu tymczasowego
    tmp_dir = get_staging_dir()
    tmp_fbx = os.path.join(tmp_dir, os.path.basename(final_fbx_path))
    try:
        cmds.FBXExport('-f', tmp_fbx, '-s')
        ok, err = copy_with_retry(tmp_fbx, final_fbx_path)
        if ok:
            print(f"[OK] FBX staged and copied to: {final_fbx_path}")
            return True
        else:
            print(f"[ERROR] FBX copy failed: {err}")
    except Exception as e_stage:
        print(f"[ERROR] Staging FBX export failed: {e_stage}")
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True)
    ap.add_argument("--outputBasePath", required=True)
    args = ap.parse_args()

    input_file = norm_path(args.inputFile)
    out_dir = norm_path(args.outputBasePath)
    ensure_dir(out_dir)

    base = os.path.splitext(os.path.basename(input_file))[0]
    final_fbx = norm_path(os.path.join(out_dir, base + ".fbx"))

    maya.standalone.initialize(name='python')
    try:
        load_fbx_plugin()
        open_scene(input_file)
        ok = export_fbx(final_fbx)
        sys.stdout.flush(); sys.stderr.flush()
        return 0 if ok else 1
    finally:
        pass

if __name__ == "__main__":
    sys.exit(main())
