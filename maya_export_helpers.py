# -*- coding: utf-8 -*-
"""
Eksport helperów (dzieci grupy 'connectivity') do JSON:
- path: ścieżka DAG w stylu /root/a/b/
- matrix: 4x4 world (row-major)
- attributes: WSZYSTKIE user-defined ("Extra Attributes") z transformu helpera
- attrNiceNames: mapowanie longName -> niceName (jeśli dostępne)
- name: ostatni segment ścieżki (np. TechnicKnob61)
- orientationHint:
    - rotateEulerDeg: [rx, ry, rz] z .r (stopnie)
    - rotateOrder: 'xyz'|'yzx'|'zxy'|'xzy'|'yxz'|'zyx' z .ro
    - rotateAxisDeg: [ax, ay, az] z .ra (jeśli istnieje)

Użycie (PowerShell):
  "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" maya_export_helpers.py ^
    --inputFile "C:\path\setofdoom.ma" ^
    --outputBasePath "C:\path\out"
"""

import argparse
import os
import json
import re

import maya.standalone
import maya.cmds as cmds

# ---------------- utils ----------------

def _norm(p):
    return os.path.normpath(p) if p else p

def _ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p

def _dag_to_unix_path(dag_full):
    # Maya: |root|A|B -> /root/A/B/
    parts = [p for p in dag_full.split('|') if p]
    return "/" + "/".join(parts) + "/"

def _world_matrix(node):
    # 16 wartości row-major -> 4x4
    m = cmds.xform(node, q=True, m=True, ws=True)
    return [m[0:4], m[4:8], m[8:12], m[12:16]]

def _find_connectivity_roots():
    # szukaj transformów o nazwie dokładnie 'connectivity'
    all_transforms = cmds.ls(type='transform', long=True) or []
    return [n for n in all_transforms if n.split('|')[-1] == 'connectivity']

def _list_helpers_under(root):
    # wszystkie transformy poniżej 'connectivity', od góry do dołu
    nodes = cmds.listRelatives(root, ad=True, type='transform', fullPath=True) or []
    return list(reversed(nodes))

# ---------------- atrybuty (Extra Attributes) ----------------

_VME_LONGNAME_GUESSES = [
    "VMECommonPartType", "vmeCommonPartType", "VME_CommonPartType", "vme_commonPartType",
    "vmeCommonType", "VMECommonType"
]

def _matches_vme_nicename(s):
    if not s: return False
    key = re.sub(r'[\s_]+', '', s).lower()
    return key in ("vmecommonparttype", "vmecommonpart", "vmecommontype")

def _safe_get_attr(attr_full, as_string_for_enum=True):
    try:
        node, attr = attr_full.split('.', 1)
        aty = cmds.getAttr(attr_full, type=True)  # np. "double", "enum", "matrix", "string"
        if aty == "enum" and as_string_for_enum:
            try:
                idx = cmds.getAttr(attr_full)
                enum_str = cmds.attributeQuery(attr, node=node, listEnum=True)
                if enum_str:
                    names = enum_str[0].split(':')
                    if isinstance(idx, (list, tuple)): idx = idx[0]
                    if 0 <= idx < len(names):
                        return names[idx]
                return idx
            except Exception:
                return cmds.getAttr(attr_full)
        val = cmds.getAttr(attr_full)
        return val
    except Exception:
        try:
            idxs = cmds.getAttr(attr_full, multiIndices=True)
            if idxs:
                out = []
                for i in idxs:
                    try:
                        out.append(cmds.getAttr(f"{attr_full}[{i}]"))
                    except Exception:
                        out.append(None)
                return out
        except Exception:
            pass
        try:
            node, attr = attr_full.split('.', 1)
            if cmds.attributeQuery(attr, node=node, numberOfChildren=True):
                kids = cmds.attributeQuery(attr, node=node, listChildren=True) or []
                d = {}
                for k in kids:
                    af = f"{node}.{k}"
                    try:
                        d[k] = cmds.getAttr(af)
                    except Exception:
                        d[k] = None
                return d
        except Exception:
            pass
        return None

def _collect_extra_attributes(node):
    attrs = {}
    nice  = {}

    ud = cmds.listAttr(node, ud=True) or []
    for a in ud:
        long_name = a
        full = f"{node}.{long_name}"
        val  = _safe_get_attr(full)
        attrs[long_name] = val
        try:
            nn = cmds.attributeQuery(long_name, node=node, niceName=True)
            if nn and nn != long_name:
                nice[long_name] = nn
        except Exception:
            pass

    have_vme = any(k.lower().endswith("commonparttype") or "vme" in k.lower() for k in attrs.keys())
    if not have_vme:
        for cand in _VME_LONGNAME_GUESSES:
            if cmds.attributeQuery(cand, node=node, exists=True):
                full = f"{node}.{cand}"
                attrs[cand] = _safe_get_attr(full)
                try:
                    nn = cmds.attributeQuery(cand, node=node, niceName=True)
                    if nn and nn != cand:
                        nice[cand] = nn
                    elif _matches_vme_nicename(nn):
                        nice[cand] = nn
                except Exception:
                    pass
                break
        else:
            all_attrs = cmds.listAttr(node) or []
            for a in all_attrs:
                try:
                    nn = cmds.attributeQuery(a, node=node, niceName=True)
                except Exception:
                    nn = None
                if _matches_vme_nicename(nn):
                    full = f"{node}.{a}"
                    attrs[a] = _safe_get_attr(full)
                    if nn and nn != a:
                        nice[a] = nn
                    break

    return attrs, nice

# ----------- orient hint (Euler/Order/Axis) -----------
_RO_MAP = {0:"xyz",1:"yzx",2:"zxy",3:"xzy",4:"yxz",5:"zyx"}

def _get_rotate_info(node):
    """Zwraca dict z rotateEulerDeg, rotateOrder, rotateAxisDeg (jeśli dostępne)."""
    info = {}
    try:
        r = cmds.getAttr(node + ".r")
        # getAttr(".r") zwraca listę/tuplę – weź pierwszą trójkę liczb
        if isinstance(r, (list, tuple)):
            r = r[0] if r and isinstance(r[0], (list, tuple)) else r
        if r and len(r) >= 3:
            info["rotateEulerDeg"] = [float(r[0]), float(r[1]), float(r[2])]
    except Exception:
        pass

    try:
        ro = cmds.getAttr(node + ".ro")
        if isinstance(ro, (list, tuple)): ro = ro[0]
        info["rotateOrder"] = _RO_MAP.get(int(ro), "xyz")
    except Exception:
        # zostaw puste – importer może założyć 'xyz'
        pass

    try:
        ra = cmds.getAttr(node + ".ra")
        if isinstance(ra, (list, tuple)):
            ra = ra[0] if ra and isinstance(ra[0], (list, tuple)) else ra
        if ra and len(ra) >= 3:
            info["rotateAxisDeg"] = [float(ra[0]), float(ra[1]), float(ra[2])]
    except Exception:
        pass

    return info

# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputFile", required=True, help="Ścieżka do .ma/.mb")
    ap.add_argument("--outputBasePath", required=True, help="Folder wyjściowy na JSON")
    args = ap.parse_args()

    scene_path = _norm(args.inputFile)
    out_dir    = _ensure_dir(_norm(args.outputBasePath))

    scene_name = os.path.splitext(os.path.basename(scene_path))[0]
    out_json   = os.path.join(out_dir, f"{scene_name}_helpers.json")

    maya.standalone.initialize(name='python')
    try:
        cmds.file(scene_path.replace("\\", "/"), open=True, force=True)

        roots = _find_connectivity_roots()
        data = []
        if not roots:
            print("⚠️  Nie znaleziono grupy 'connectivity' w scenie.")
        else:
            seen = set()
            for root in roots:
                for node in _list_helpers_under(root):
                    if node in seen:
                        continue
                    seen.add(node)
                    try:
                        attrs, nice = _collect_extra_attributes(node)
                        entry = {
                            "path": _dag_to_unix_path(node),
                            "name": node.split('|')[-1],                     # nowość
                            "matrix": _world_matrix(node),
                            "attributes": attrs,
                            "attrNiceNames": nice,
                            "orientationHint": _get_rotate_info(node)        # nowość
                        }
                        data.append(entry)
                    except Exception as e:
                        print(f"⚠️  Pominięto '{node}': {e}")

        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Zapisano: {out_json} (helperów: {len(data)})")

    finally:
        maya.standalone.uninitialize()

if __name__ == "__main__":
    main()
