# maya_meta_export.py
import argparse
import os
import json
import maya.standalone
import maya.cmds as cmds

def _norm(p): return os.path.normpath(p)
def _ensure_dir(p): os.makedirs(p, exist_ok=True); return p

def _dag_to_unix_path(dag):
    return "/" + "/".join(part for part in dag.split("|") if part) + "/"

def _world_matrix(node):
    m = cmds.xform(node, q=True, m=True, ws=True)
    return [m[0:4], m[4:8], m[8:12], m[12:16]]

def _bbox(node):
    bb = cmds.exactWorldBoundingBox(node)
    return {"min": bb[:3], "max": bb[3:]}

def _safe_get_attr(attr_full):
    try: return cmds.getAttr(attr_full)
    except: return None

def _extra_attrs(node):
    out = {}
    ud = cmds.listAttr(node, ud=True) or []
    for a in ud:
        try:
            val = _safe_get_attr(f"{node}.{a}")
            out[a] = val
        except: pass
    return out

def _vme_common_part_type(transform_attrs, shape_attrs):
    for source, attrs in [("transform", transform_attrs), ("shape", shape_attrs)]:
        for k, v in attrs.items():
            if "common" in k.lower() and "part" in k.lower() and "type" in k.lower():
                return {
                    "value": v,
                    "sourceAttr": k,
                    "onNode": source
                }
    return None

def _is_instanced(shape):
    return cmds.objectType(shape) == "mesh" and len(cmds.listRelatives(shape, p=True, f=True) or []) > 1

def _collect_materials(shape):
    sg = cmds.listConnections(shape, type="shadingEngine") or []
    mats = []
    for s in sg:
        conn = cmds.listConnections(f"{s}.surfaceShader", d=False, s=True) or []
        for m in conn:
            mats.append(m)
    return list(set(mats))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True)
    ap.add_argument("--outputBasePath", required=True)
    args = ap.parse_args()

    maya.standalone.initialize(name="python")
    try:
        scene_path = _norm(args.inputFile)
        out_dir = _ensure_dir(_norm(args.outputBasePath))
        scene_name = os.path.splitext(os.path.basename(scene_path))[0]
        out_json = os.path.join(out_dir, f"{scene_name}_geometry.json")

        cmds.file(scene_path.replace("\\", "/"), open=True, force=True)

        all_meshes = cmds.ls(type="mesh", long=True) or []
        out = {"meshes": []}
        seen_shapes = set()

        for shape in all_meshes:
            if shape in seen_shapes:
                continue
            seen_shapes.add(shape)

            transform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]

            tr_attrs = _extra_attrs(transform)
            sh_attrs = _extra_attrs(shape)

            mesh_entry = {
                "transformPathUnix": _dag_to_unix_path(transform),
                "shapePathUnix": _dag_to_unix_path(shape),
                "worldMatrix": _world_matrix(transform),
                "bbox": _bbox(shape),
                "extraAttributes": {
                    "transform": tr_attrs,
                    "shape": sh_attrs
                },
                "vmeCommonPartType": _vme_common_part_type(tr_attrs, sh_attrs),
                "instanced": _is_instanced(shape),
                "materials": _collect_materials(shape),
            }

            # Opcjonalnie: Dodaj vertices / faces (lightweight)
            # vertices = cmds.getAttr(f"{shape}.vrts", multiIndices=True)
            # faces = cmds.polyEvaluate(shape, face=True)

            out["meshes"].append(mesh_entry)

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        print(f"✅ Zapisano: {out_json} (mesh: {len(out['meshes'])})")

    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
