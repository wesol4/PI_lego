import hou, os, json

node = hou.pwd()
geo  = node.geometry()

def _norm(p):
    if not p: return ""
    p = p.replace("|", "/")
    while "//" in p: p = p.replace("//", "/")
    return p.rstrip("/")

def _parse_matrix16(val):
    # 1) jeśli string, spróbuj json.loads
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except Exception:
            return None
    # 2) jeśli 16 liczb
    if isinstance(val, (list, tuple)) and len(val) == 16 and all(isinstance(x,(int,float)) for x in val):
        return tuple(float(x) for x in val)
    # 3) jeśli 4x4
    if isinstance(val, (list, tuple)) and len(val) == 4 and all(isinstance(r,(list,tuple)) and len(r)==4 for r in val):
        flat = []
        for r in val: flat.extend(float(x) for x in r)
        return tuple(flat)
    return None

def _to_vec3(v):
    if isinstance(v,(list,tuple)) and len(v)==3 and all(isinstance(x,(int,float)) for x in v):
        return hou.Vector3([float(x) for x in v])
    if isinstance(v,str):
        try:
            vv = json.loads(v)
            if isinstance(vv,(list,tuple)) and len(vv)==3:
                return hou.Vector3([float(x) for x in vv])
        except: pass
    return None

# --- 1) Wczytaj JSON ---
json_path = node.evalParm("json_file")
if not os.path.exists(json_path):
    raise hou.NodeError(f"Nie znaleziono pliku JSON: {json_path}")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)

records = data.get("meshes", [])

# --- 2) Mapa po ścieżkach ---
rec_map = {}
for rec in records:
    for k in ("path","transformPathUnix","shapePathUnix"):
        p = _norm(rec.get(k,""))
        if p: rec_map[p] = rec

pathA  = geo.findPrimAttrib("path")
shapeA = geo.findPrimAttrib("shape_path")
xformA = geo.findPrimAttrib("xform_path")

def _rec_for(prim):
    for a in (pathA,shapeA,xformA):
        if not a: continue
        try:
            p = _norm(prim.attribValue(a))
            if p in rec_map: return rec_map[p]
        except: pass
    return None

# --- 3) TWARDY RESET typów macierzy -> zawsze float[16] ---
for name in ("LEGO_startPosition","worldMatrix"):
    if geo.findPrimAttrib(name):
        geo.removePrimAttrib(name)
geo.addAttrib(hou.attribType.Prim, "LEGO_startPosition", tuple(0.0 for _ in range(16)))
geo.addAttrib(hou.attribType.Prim, "worldMatrix",       tuple(0.0 for _ in range(16)))

# + pomocnicze (opcjonalne)
if not geo.findPrimAttrib("LEGO_startPosition_translation"):
    geo.addAttrib(hou.attribType.Prim, "LEGO_startPosition_translation", hou.Vector3((0.0,0.0,0.0)))
if not geo.findPrimAttrib("worldMatrix_translation"):
    geo.addAttrib(hou.attribType.Prim, "worldMatrix_translation", hou.Vector3((0.0,0.0,0.0)))

# bbox
if not geo.findPrimAttrib("bbox_min"):
    geo.addAttrib(hou.attribType.Prim, "bbox_min", hou.Vector3((0.0,0.0,0.0)))
if not geo.findPrimAttrib("bbox_max"):
    geo.addAttrib(hou.attribType.Prim, "bbox_max", hou.Vector3((0.0,0.0,0.0)))

# --- 4) Główna pętla ---
applied = 0
for prim in geo.prims():
    rec = _rec_for(prim)
    if not rec: continue

    # worldMatrix (top-level)
    wm16 = _parse_matrix16(rec.get("worldMatrix"))
    if wm16:
        prim.setAttribValue("worldMatrix", wm16)
        prim.setAttribValue("worldMatrix_translation", hou.Vector3((wm16[12]*0.01, wm16[13]*0.01, wm16[14]*0.01)))

    # LEGO_startPosition (może być w extra.transform/shape lub top-level)
    start_raw = None
    extra = rec.get("extraAttributes") or {}
    for sec in ("transform","shape"):
        if "LEGO_startPosition" in (extra.get(sec) or {}):
            start_raw = extra[sec]["LEGO_startPosition"]
            break
    if start_raw is None and "LEGO_startPosition" in rec:
        start_raw = rec["LEGO_startPosition"]

    sm16 = _parse_matrix16(start_raw)
    if sm16:
        prim.setAttribValue("LEGO_startPosition", sm16)
        prim.setAttribValue("LEGO_startPosition_translation", hou.Vector3((sm16[12]*0.01, sm16[13]*0.01, sm16[14]*0.01)))

    # bbox (cm->m)
    bbox = rec.get("bbox") or {}
    vmin = _to_vec3(bbox.get("min"))
    vmax = _to_vec3(bbox.get("max"))
    if vmin: prim.setAttribValue("bbox_min", vmin*0.01)
    if vmax: prim.setAttribValue("bbox_max", vmax*0.01)

    # wybrane pola skalarne (bez prefiksów; dodaj po potrzebie)
    for k in ("vmeCommonPartType","instanced","vertices","faces"):
        if k in rec:
            val = rec[k]
            # proste typy lub zrzut do stringa (nie ruszamy macierzy tutaj!)
            if isinstance(val, (int,float,str)):
                # utwórz atrybut jeśli brak
                if not geo.findPrimAttrib(k):
                    if isinstance(val,int):   geo.addAttrib(hou.attribType.Prim,k,0)
                    elif isinstance(val,float): geo.addAttrib(hou.attribType.Prim,k,0.0)
                    else:                     geo.addAttrib(hou.attribType.Prim,k,"")
                prim.setAttribValue(k, val)

    # extraAttributes.* (pomijamy LEGO_startPosition – obsłużone wyżej)
    for sec in ("transform","shape"):
        items = (extra.get(sec) or {}).items()
        for k,v in items:
            if k == "LEGO_startPosition": 
                continue
            # proste mapowanie typów: int/float/str / vec3
            if isinstance(v,(int,float,str)):
                if not geo.findPrimAttrib(k):
                    if isinstance(v,int): geo.addAttrib(hou.attribType.Prim,k,0)
                    elif isinstance(v,float): geo.addAttrib(hou.attribType.Prim,k,0.0)
                    else: geo.addAttrib(hou.attribType.Prim,k,"")
                prim.setAttribValue(k,v)
            else:
                vec = _to_vec3(v)
                if vec is not None:
                    if not geo.findPrimAttrib(k):
                        geo.addAttrib(hou.attribType.Prim,k,hou.Vector3((0,0,0)))
                    prim.setAttribValue(k,vec)
                # inne typy (listy różnej długości itd.) – w razie potrzeby dopisz case

    applied += 1

print(f"✅ Zastosowano macierze i meta: {applied} / {geo.intrinsicValue('primitivecount')}")
