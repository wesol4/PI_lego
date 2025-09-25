# Importer #1: Metadane dla głównej geometrii

import hou
import json
import os

node = hou.pwd()
geo = node.geometry()

# Parametr z plikiem JSON
json_path_param = node.parm('json_file')
if not json_path_param:
    raise hou.Error("Brak parametru 'json_file'. Dodaj go w 'Edit Parameter Interface...'")

json_path = json_path_param.eval()
if not os.path.exists(json_path):
    raise hou.Error(f"Plik JSON nie został znaleziony: {json_path}")

# Wczytaj dane JSON
with open(json_path, 'r', encoding='utf-8') as f:
    attr_data = json.load(f)

print("--- Skanowanie atrybutów z pliku JSON ---")

# Mapowanie path -> prim
path_map = {prim.attribValue("path"): prim for prim in geo.prims() if prim.attribValue("path")}

print(f"Znaleziono {len(path_map)} prymitywów z atrybutem 'path'.")

print("--- Przypisywanie atrybutów do geometrii ---")

for path_key, attributes in attr_data.items():
    prim = path_map.get(path_key)
    if not prim:
        print(f"⚠️ Brak prymitywu dla path={path_key}")
        continue

    print(f"\n➡️ Path: {path_key}")
    for attr_name, attr_val in attributes.items():
        # 1. Utwórz atrybut jeśli nie istnieje
        if not geo.findPrimAttrib(attr_name):
            if isinstance(attr_val, str):
                geo.addAttrib(hou.attribType.Prim, attr_name, "")
            elif isinstance(attr_val, (int, bool)):
                geo.addAttrib(hou.attribType.Prim, attr_name, 0)
            elif isinstance(attr_val, float):
                geo.addAttrib(hou.attribType.Prim, attr_name, 0.0)
            elif isinstance(attr_val, (list, tuple)):
                if all(isinstance(v, (int, float)) for v in attr_val):
                    geo.addAttrib(hou.attribType.Prim, attr_name, [0.0] * len(attr_val))
                else:
                    print(f"⚠️ Pominięto {attr_name} — lista zawiera nienumeryczne dane: {attr_val}")
                    continue
            else:
                print(f"⚠️ Pominięto {attr_name} — nieobsługiwany typ: {type(attr_val)}")
                continue
            print(f"  ➕ Utworzono atrybut: {attr_name} (typ {type(attr_val).__name__})")

        # 2. Ustaw wartość
        try:
            prim.setAttribValue(attr_name, attr_val)
            print(f"  ✅ {attr_name} = {attr_val}")
        except hou.OperationFailed as e:
            print(f"  ❌ Nie udało się ustawić {attr_name}={attr_val} ({e})")

print("\n--- Zakończono przypisywanie metadanych. ---")
