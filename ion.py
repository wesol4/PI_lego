[1mdiff --git a/maya_export_extension.py b/maya_export_extension.py[m
[1mindex e69de29..ef82e1d 100644[m
[1m--- a/maya_export_extension.py[m
[1m+++ b/maya_export_extension.py[m
[36m@@ -0,0 +1,62 @@[m
[32m+[m[32mimport argparse[m
[32m+[m[32mimport os[m
[32m+[m[32mimport maya.standalone[m
[32m+[m[32mimport maya.cmds as cmds[m
[32m+[m[32mimport maya.mel as mel[m
[32m+[m
[32m+[m[32mdef export_usd(output_path):[m
[32m+[m[32m    try:[m
[32m+[m[32m        cmds.loadPlugin("mayaUsdPlugin", quiet=True)[m
[32m+[m[32m        cmds.select(all=True)[m
[32m+[m[32m        usd_file = output_path + ".usd"[m
[32m+[m[32m        cmds.file(usd_file, force=True, options="ExportUVs=1;ExportColorSets=1", typ="USD Export", pr=True, es=True)[m
[32m+[m[32m        print(f"✅ USD exported to: {usd_file}")[m
[32m+[m[32m    except Exception as e:[m
[32m+[m[32m        print(f"❌ USD export failed: {e}")[m
[32m+[m
[32m+[m[32mdef export_fbx(output_path):[m
[32m+[m[32m    try:[m
[32m+[m[32m        cmds.loadPlugin("fbxmaya", quiet=True)[m
[32m+[m[32m        cmds.select(all=True)[m
[32m+[m[32m        fbx_file = output_path + ".fbx"[m
[32m+[m[32m        cmds.file(fbx_file, force=True, options="", typ="FBX export", pr=True, es=True)[m
[32m+[m[32m        print(f"✅ FBX exported to: {fbx_file}")[m
[32m+[m[32m    except Exception as e:[m
[32m+[m[32m        print(f"❌ FBX export failed: {e}")[m
[32m+[m
[32m+[m[32mdef export_abc(output_path):[m
[32m+[m[32m    try:[m
[32m+[m[32m        cmds.loadPlugin("AbcExport", quiet=True)[m
[32m+[m[32m        abc_file = output_path + ".abc"[m
[32m+[m[32m        top_nodes = cmds.ls(assemblies=True, long=True)[m
[32m+[m[32m        if not top_nodes:[m
[32m+[m[32m            raise RuntimeError("No valid root nodes found for Alembic export.")[m
[32m+[m[32m        abc_roots = " ".join([f"-root {node}" for node in top_nodes])[m
[32m+[m[32m        mel.eval(f'AbcExport -j "-frameRange 1 1 {abc_roots} -file \\"{abc_file}\\""')[m
[32m+[m[32m        print(f"✅ Alembic exported to: {abc_file}")[m
[32m+[m[32m    except Exception as e:[m
[32m+[m[32m        print(f"❌ Alembic export failed: {e}")[m
[32m+[m
[32m+[m[32mdef main():[m
[32m+[m[32m    parser = argparse.ArgumentParser()[m
[32m+[m[32m    parser.add_argument("--inputFile", required=True)[m
[32m+[m[32m    parser.add_argument("--outputBasePath", required=True)[m
[32m+[m[32m    args = parser.parse_args()[m
[32m+[m
[32m+[m[32m    input_file = args.inputFile.replace("\\", "/")[m
[32m+[m[32m    output_dir = args.outputBasePath.replace("\\", "/")[m
[32m+[m
[32m+[m[32m    base_name = os.path.splitext(os.path.basename(input_file))[0][m
[32m+[m[32m    output_base = os.path.join(output_dir, base_name).replace("\\", "/")[m
[32m+[m
[32m+[m[32m    maya.standalone.initialize(name='python')[m
[32m+[m[32m    cmds.file(input_file, open=True, force=True)[m
[32m+[m
[32m+[m[32m    export_usd(output_base)[m
[32m+[m[32m    export_fbx(output_base)[m
[32m+[m[32m    export_abc(output_base)[m
[32m+[m
[32m+[m[32m    maya.standalone.uninitialize()[m
[32m+[m
[32m+[m[32mif __name__ == "__main__":[m
[32m+[m[32m    main()[m
