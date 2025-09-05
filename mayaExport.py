# Maya Python Script (Final 3-File Pipeline Version)
# Exports:
# 1. Geometry to .usd
# 2. Main object metadata to _attrs.json
# 3. Helper data to _helpers.json in a specific flat format.

import maya.cmds as cmds
import os
import json
import sys
import argparse

try:
    import maya.standalone
except ImportError:
    pass

FINAL_EXPORTER_WINDOW = "final_3_File_Exporter"

def export_final_workflow(base_file_path, export_all):
    if not base_file_path:
        cmds.warning("Please provide a file path and name (without extension).")
        return

    output_dir = os.path.dirname(base_file_path)
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        except Exception as e:
            cmds.error(f"Could not create directory: {e}")
            return

    # --- Krok 1: Identyfikacja obiektów do eksportu ---
    source_objects = []
    if export_all:
        print("Mode: Exporting entire scene.")
        source_objects = cmds.ls(assemblies=True, long=True)
        source_objects = [obj for obj in source_objects if obj not in ['|persp', '|top', '|front', '|side']]
    else:
        print("Mode: Exporting selection.")
        source_objects = cmds.ls(selection=True, long=True)

    if not source_objects:
        cmds.warning("No objects found to export.")
        return

    original_selection = cmds.ls(selection=True, long=True)
    cmds.select(source_objects, replace=True)

    # --- Krok 2: Eksport geometrii do USD ---
    print("\n--- Starting USD Export for Geometry ---")
    usd_path = base_file_path + ".usd"

    export_options = {
        "file": usd_path,
        "selection": True,
        "mergeTransformAndShape": True,
        "shadingMode": "none",
        "materialsScopeName": "Materials"
    }

    try:
        cmds.mayaUSDExport(**export_options)
        print(f"Successfully exported geometry to: {usd_path}")
    except Exception as e:
        cmds.error(f"USD Export failed: {e}")
        if original_selection: cmds.select(original_selection, replace=True)
        return
    finally:
        if original_selection:
            cmds.select(original_selection, replace=True)

    # --- Krok 3: Eksport DANYCH do dwóch osobnych plików JSON ---
    print("\n--- Starting Data Export to two JSON files ---")

    # Przygotowanie struktur danych dla obu plików
    attrs_json_path = base_file_path + "_attrs.json"
    helpers_json_path = base_file_path + "_helpers.json"

    metadata_data = {}
    helpers_data = [] # Płaska lista dla helperów

    all_descendants = cmds.listRelatives(source_objects, allDescendents=True, type='transform', fullPath=True) or []

    # Filtrujemy, aby nie przetwarzać helperów jako głównych obiektów
    objects_for_json = [
        o for o in list(set(source_objects + all_descendants))
        if not (cmds.listRelatives(o, parent=True, fullPath=True) or [''])[0].endswith('|connectivity')
    ]

    for obj in objects_for_json:
        # --- CZĘŚĆ 1: Zbieranie metadanych dla głównego obiektu ---
        json_key = obj.replace('|', '/')
        metadata_data[json_key] = {}

        attributes_to_collect = cmds.listAttr(obj, userDefined=True) or []
        attributes_to_collect.extend(cmds.listAttr(obj, string='LEGO*') or [])
        attributes_to_collect.extend(cmds.listAttr(obj, string='vray*') or [])
        attributes_to_collect.extend(cmds.listAttr(obj, string='VME*') or [])

        for attr in list(set(attributes_to_collect)):
            try:
                if cmds.getAttr(f"{obj}.{attr}", settable=True):
                   metadata_data[json_key][attr] = cmds.getAttr(f"{obj}.{attr}")
            except:
                pass

        # --- CZĘŚĆ 2: Szukanie i przetwarzanie helperów dla tego obiektu ---
        try:
            children = cmds.listRelatives(obj, children=True, type='transform', fullPath=True) or []
            connectivity_node = next((child for child in children if child.split('|')[-1] == 'connectivity'), None)

            if connectivity_node:
                helpers = cmds.listRelatives(connectivity_node, children=True, type='transform', fullPath=True) or []
                if helpers:
                    # Znajdź shape nadrzędnego obiektu - RAZ dla wszystkich helperów w tej grupie
                    parent_shapes = cmds.listRelatives(obj, shapes=True, fullPath=True)
                    if not parent_shapes:
                        cmds.warning(f"Parent object '{obj}' has no shape node. Skipping its helpers.")
                        continue

                    parent_shape_path = parent_shapes[0].replace('|', '/')

                    for helper in helpers:
                        try:
                            helper_matrix = cmds.xform(helper, query=True, matrix=True, worldSpace=True)

                            # Tworzenie słownika w wymaganym formacie
                            helper_instance = {
                                "path": parent_shape_path,
                                "type": helper.split('|')[-1],
                                "hasMesh": True,
                                "transform": helper_matrix
                            }
                            helpers_data.append(helper_instance)
                        except Exception as e_helper:
                            cmds.warning(f"Could not process helper '{helper}': {e_helper}")
        except Exception as e_conn:
            cmds.warning(f"An error occurred while scanning for helpers in '{obj}': {e_conn}")

    # --- Krok 4: Zapis plików JSON ---
    # Zapis pliku z metadanymi
    try:
        json_string_attrs = json.dumps(metadata_data, indent=4, ensure_ascii=False)
        with open(attrs_json_path, 'wb') as f:
            f.write(json_string_attrs.encode('utf-8'))
        print(f"Successfully saved main attributes to: {attrs_json_path}")
    except Exception as e:
        cmds.error(f"Failed to save ATTRS JSON file: {e}")

    # Zapis pliku z helperami
    try:
        json_string_helpers = json.dumps(helpers_data, indent=4, ensure_ascii=False)
        with open(helpers_json_path, 'wb') as f:
            f.write(json_string_helpers.encode('utf-8'))
        print(f"Successfully saved helper data to: {helpers_json_path}")
    except Exception as e:
        cmds.error(f"Failed to save HELPERS JSON file: {e}")

    try:
        if not cmds.about(batch=True):
            cmds.confirmDialog(
                title="Export Complete!",
                message=f"Created three files:\n1. Geometry (USD): {os.path.basename(usd_path)}\n2. Attributes (JSON): {os.path.basename(attrs_json_path)}\n3. Helpers (JSON): {os.path.basename(helpers_json_path)}",
                button=["OK"]
            )
    except: pass

# --- UI i Batch Mode (bez zmian) ---
def create_final_exporter_ui():
    if cmds.window(FINAL_EXPORTER_WINDOW, exists=True):
        cmds.deleteUI(FINAL_EXPORTER_WINDOW, window=True)
    cmds.window(FINAL_EXPORTER_WINDOW, title="3-File Exporter (USD + Attrs + Helpers)", widthHeight=(500, 180))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 10))
    export_all_checkbox = cmds.checkBox(label="Export entire scene (instead of selection)", value=True)
    file_path_control = cmds.textFieldButtonGrp(label="Output Filename (no extension)", buttonLabel="Browse...")

    scene_path = cmds.file(query=True, sceneName=True)
    if scene_path:
        scene_dir = os.path.dirname(scene_path)
        scene_name_with_ext = os.path.basename(scene_path)
        scene_name_no_ext = scene_name_with_ext.split('.')[0]
        default_output_path = os.path.join(scene_dir, scene_name_no_ext, scene_name_no_ext)
        cmds.textFieldButtonGrp(file_path_control, edit=True, text=default_output_path)

    cmds.textFieldButtonGrp(file_path_control, edit=True, buttonCommand=lambda: browse_base_path(file_path_control))
    cmds.button(label="Export All Data", height=40, backgroundColor=(0.5, 0.6, 0.4),
                command=lambda *args: export_final_workflow(
                    cmds.textFieldButtonGrp(file_path_control, query=True, text=True),
                    cmds.checkBox(export_all_checkbox, query=True, value=True)))
    cmds.setParent('..')
    cmds.showWindow(FINAL_EXPORTER_WINDOW)

def browse_base_path(control_name):
    file_path_list = cmds.fileDialog2(fileFilter="USD Files (*.usd);;All Files (*.*)",
                                      dialogStyle=2, fileMode=0,
                                      caption="Select Output Base Name and Location")
    if file_path_list:
        full_path = file_path_list[0]
        base_path = os.path.splitext(full_path)[0]
        cmds.textFieldButtonGrp(control_name, edit=True, text=base_path)

def main_batch():
    parser = argparse.ArgumentParser(description="Maya 3-File Exporter for batch processing.")
    parser.add_argument("--inputFile", required=True, help="Path to the source Maya file (.ma or .mb).")
    parser.add_argument("--outputBasePath", required=True, help="Base path for the output files (no extension).")
    args = parser.parse_args(sys.argv[1:])

    print(f"--- Running in Batch Mode ---")
    print(f"Input file: {args.inputFile}")
    print(f"Output base path: {args.outputBasePath}")
    output_base_path = args.outputBasePath
    if os.path.isdir(output_base_path) or output_base_path.endswith('/') or output_base_path.endswith('\\'):
        scene_name_with_ext = os.path.basename(args.inputFile)
        scene_name_no_ext = scene_name_with_ext.split('.')[0]
        output_base_path = os.path.join(output_base_path, scene_name_no_ext, scene_name_no_ext)
        print(f"New constructed output base path: {output_base_path}")

    try:
        maya.standalone.initialize(name='python')
        plugin_name = "mayaUsdPlugin"
        if not cmds.pluginInfo(plugin_name, query=True, loaded=True):
            print(f"Loading plugin: {plugin_name}...")
            cmds.loadPlugin(plugin_name)
        cmds.file(args.inputFile, open=True, force=True)
        print(f"Successfully opened: {args.inputFile}")
        export_final_workflow(base_file_path=output_base_path, export_all=True)
    except Exception as e:
        sys.stderr.write(f"Batch export failed: {e}\n")
    finally:
        print("--- Batch processing finished. Uninitializing Maya. ---")
        maya.standalone.uninitialize()

if __name__ == "__main__":
    is_batch = False
    try:
        is_batch = cmds.about(batch=True)
    except:
        is_batch = True
    if is_batch:
        main_batch()
    else:
        create_final_exporter_ui()