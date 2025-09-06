import argparse
import os
import maya.standalone
import maya.cmds as cmds
import maya.mel as mel

def export_usd(output_path):
    try:
        cmds.loadPlugin("mayaUsdPlugin", quiet=True)
        cmds.select(all=True)
        usd_file = output_path + ".usd"
        cmds.file(usd_file, force=True, options="ExportUVs=1;ExportColorSets=1", typ="USD Export", pr=True, es=True)
        print(f"✅ USD exported to: {usd_file}")
    except Exception as e:
        print(f"❌ USD export failed: {e}")

def export_fbx(output_path):
    try:
        cmds.loadPlugin("fbxmaya", quiet=True)
        cmds.select(all=True)
        fbx_file = output_path + ".fbx"
        cmds.file(fbx_file, force=True, options="", typ="FBX export", pr=True, es=True)
        print(f"✅ FBX exported to: {fbx_file}")
    except Exception as e:
        print(f"❌ FBX export failed: {e}")

def export_abc(output_path):
    try:
        cmds.loadPlugin("AbcExport", quiet=True)
        abc_file = output_path + ".abc"
        top_nodes = cmds.ls(assemblies=True, long=True)
        if not top_nodes:
            raise RuntimeError("No valid root nodes found for Alembic export.")
        abc_roots = " ".join([f"-root {node}" for node in top_nodes])
        mel.eval(f'AbcExport -j "-frameRange 1 1 {abc_roots} -file \\"{abc_file}\\""')
        print(f"✅ Alembic exported to: {abc_file}")
    except Exception as e:
        print(f"❌ Alembic export failed: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputFile", required=True)
    parser.add_argument("--outputBasePath", required=True)
    args = parser.parse_args()

    input_file = args.inputFile.replace("\\", "/")
    output_dir = args.outputBasePath.replace("\\", "/")

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_base = os.path.join(output_dir, base_name).replace("\\", "/")

    maya.standalone.initialize(name='python')
    cmds.file(input_file, open=True, force=True)

    export_usd(output_base)
    export_fbx(output_base)
    export_abc(output_base)

    maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
