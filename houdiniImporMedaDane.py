# Importer #1: Metadane dla głównej geometrii

import hou
import json
import os

node = hou.pwd()
geo = node.geometry()

json_path_param = node.parm('json_file')
if not json_path_param:
    raise hou.Error("Brak parametru 'json_file'. Dodaj go w 'Edit Parameter Interface...'")
json_path = json_path_param.eval()

if not os.path.exists(json_path):
    raise hou.Error(f"Plik JSON nie został znaleziony: {json_path}")

with open(json_path, 'r', encoding='utf-8') as f:
    attr_data = json.load(f)

# Skanowanie i tworzenie atrybutów
print("--- Skanowanie atrybutów z _attrs.json ---")
prim_attrib_info = {}
# ... (logika skanowania i tworzenia atrybutów - uproszczona dla zwięzłości, kod jest identyczny jak w naszej pierwszej rozmowie)

# Tworzenie mapy ścieżek
path_map = {prim.attribValue("path"): prim for prim in geo.prims()}

print("--- Przypisywanie atrybutów do geometrii ---")
for path_key, attributes in attr_data.items():
    prim = path_map.get(path_key)
    if not prim:
        continue

    for attr_name, attr_val in attributes.items():
        # Upewnij się, że atrybut istnieje, zanim go ustawisz
        if not geo.findPrimAttrib(attr_name):
            if isinstance(attr_val, str):
                geo.addAttrib(hou.attribType.Prim, attr_name, "")
            elif isinstance(attr_val, (int, bool)):
                 geo.addAttrib(hou.attribType.Prim, attr_name, 0)
            elif isinstance(attr_val, float):
                geo.addAttrib(hou.attribType.Prim, attr_name, 0.0)
            # Domyślnie pomijamy bardziej złożone typy w tym fragmencie

        try:
            prim.setAttribValue(attr_name, attr_val)
        except hou.OperationFailed:
            pass # Ignoruj błędy, jeśli typ się nie zgadza

print("--- Zakończono przypisywanie metadanych. ---")