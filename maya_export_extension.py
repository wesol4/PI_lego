import argparse, os, shutil, tempfile
import maya.standalone
import maya.cmds as cmds
import maya.mel as mel

def ensure_writable_dir(dirpath):
    dirpath = os.path.normpath(dirpath)
    os.makedirs(dirpath, exist_ok=True)
    testfile = os.path.join(dirpath, "_writetest.tmp")
    try:
        with open(testfile, "wb") as f:
            f.write(b"ok")
        os.remove(testfile)
        return True, None
    except Exception as e:
        return False, e

def safe_target_base(output_dir, base_name):
    # jeśli katalog nie jest zapisywalny -> fallback: %TEMP%\maya_export\<user>\<base_name>
    ok, err = ensure_writable_dir(output_dir)
    if ok:
        return os.path.join(output_dir, base_name), None, None
    tmp_root = os.path.join(tempfile.gettempdir(), "maya_export", os.getlogin())
    tmp_dir = os.path.join(tmp_root, base_name)
    os.makedirs(tmp_dir, exist_ok=True)
    return os.path.join(tmp_dir, base_name), output_dir, err  # (tmp_base, final_dir, original_error)

def move_if_needed(tmp_base, final_dir):
    if not final_dir:
        return True, None
    ok, err = ensure_writable_dir(final_dir)
    if not ok:
        return False, err
    moved = []
    for ext in (".usd", ".fbx", ".abc"):
        src = tmp_base + ext
        if os.path.exists(src):
            dst = os.path.join(final_dir, os.path.basename(src))
            try:
                shutil.move(src, dst)
                moved.append(dst)
            except Exception as e:
                return False, e
    return True, None

def export_usd(output_base):
    try:
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        cmds.select(all=True)
        usd_file = output_base + ".usd"
        cmds.file(usd_file, force=True, options="ExportUVs=1;ExportColorSets=1", typ="USD Export", pr=True, es=True)
        print(f"✅ USD exported to: {usd_file}")
    except Exception as e:
        print(f"❌ USD export failed: {e}")

def export_fbx(output_base):
    try:
        cmds.loadPlugin("fbxmaya", quiet=True)
        cmds.select(all=True)
        fbx_file = output_base + ".fbx"
        cmds.file(fbx_file, force=True, options="", typ="FBX export", pr=True, es=True)
        print(f"✅ FBX exported to: {fbx_file}")
    except Exception as e:
        print(f"❌ FBX export failed: {e}")

def export_abc(output_base):
    try:
        cmds.loadPlugin("AbcExport", quiet=True)
        abc_file = output_base + ".abc"
        top_nodes = cmds.ls(assemblies=True, long=True)
        if not top_nodes:
            raise RuntimeError("No valid root nodes found for Alembic export.")
        roots = " ".join([f"-root {n}" for n in top_nodes])
        mel.eval(f'AbcExport -j "-frameRange 1 1 {roots} -file \\"{abc_file}\\""')
        print(f"✅ Alembic exported to: {abc_file}")
    except Exception as e:
        print(f"❌ Alembic export failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputFile", required=True)
    parser.add_argument("--outputBasePath", required=True)
    args = parser.parse_args()

    input_file = os.path.normpath(args.inputFile)
    out_dir = os.path.normpath(args.outputBasePath)

    base_name = os.path.splitext(os.path.basename(input_file))[0]

    maya.standalone.initialize(name='python')
    try:
        cmds.file(input_file.replace("\\", "/"), open=True, force=True)

        # wybór docelowej bazy + fallback do %TEMP% jeśli P:\ niepisalny
        tmp_base, final_dir, perm_err = safe_target_base(out_dir, base_name)
        if perm_err:
            print(f"⚠️  Output dir not writable ({out_dir}): {perm_err}. Using TEMP: {os.path.dirname(tmp_base)}")

        export_usd(tmp_base)
        export_fbx(tmp_base)
        export_abc(tmp_base)

        ok, mv_err = move_if_needed(tmp_base, final_dir)
        if not ok:
            print(f"❌ Could not move files from TEMP to final dir '{final_dir}': {mv_err}")
        elif final_dir:
            print(f"✅ Moved exports to final dir: {final_dir}")
    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
