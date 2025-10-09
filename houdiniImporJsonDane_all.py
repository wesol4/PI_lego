import hou
import json
import os

# Bieżący węzeł i geometria
node = hou.pwd()
geo = node.geometry()

# Parametr "output" - gdzie zapisać
json_path = node.parm("output").eval()
os.makedirs(os.path.dirname(json_path), exist_ok=True)

# Pobierz wszystkie atrybuty prymitywów
prim_attribs = geo.primAttribs()
attrib_names = [a.name() for a in prim_attribs]

all_data = []

for prim in geo.prims():
    prim_data = {}
    for attrib in prim_attribs:
        name = attrib.name()
        try:
            value = prim.attribValue(attrib)
        except Exception as e:
            print(f"⚠️ Błąd przy atrybucie '{name}': {e}")
            continue

        # Konwersja typów do formatu JSON
        if isinstance(value, hou.Vector3):
            prim_data[name] = list(value)
        elif isinstance(value, hou.Vector2):
            prim_data[name] = list(value)
        elif isinstance(value, hou.Matrix4):
            prim_data[name] = list(value.asTuple())  # 16 floatów
        elif isinstance(value, hou.Matrix3):
            prim_data[name] = list(value.asTuple())  # 9 floatów
        elif isinstance(value, (tuple, list)):
            prim_data[name] = list(value)
        else:
            prim_data[name] = value

    all_data.append(prim_data)

# Zapisz do JSON
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=4, ensure_ascii=False)

print(f":white_check_mark: Wyeksportowano {len(all_data)} prymitywów z {len(attrib_names)} atrybutami do pliku: {json_path}")