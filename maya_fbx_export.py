# Importer #1: Metadane dla głównej geometrii

import hou
import json
import os

# Aktualny node i geometria
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

# Mapa: path -> prim
path_map = {prim.attribValue("path"): prim for prim in geo.prims() if prim.attribValue("path")}

print("--- Przypisywanie atrybutów do geometrii ---")

for path_key, attributes in attr_data.items():
    prim = path_map.get(path_key)
    if not prim:
        continue

    for attr_name, attr_val in attributes.items():
        # Jeśli atrybut nie istnieje — utwórz go z odpowiednim typem domyślnym
        if not geo.findPrimAttrib(attr_name):
            if isinstance(attr_val, str):
                geo.addAttrib(hou.attribType.Prim, attr_name, "")
            elif isinstance(attr_val, (int, bool)):
                geo.addAttrib(hou.attribType.Prim, attr_name, 0)
            elif isinstance(attr_val, float):
                geo.addAttrib(hou.attribType.Prim, attr_name, 0.0)
            elif isinstance(attr_val, (list, tuple)):
                # Obsłuż listy numeryczne jako float[] (np. vector)
                if all(isinstance(v, (int, float)) for v in attr_val):
                    default_val = [0.0] * len(attr_val)
                    geo.addAttrib(hou.attribType.Prim, attr_name, default_val)
                else:
                    print(f"⚠️ Pominięto atrybut {attr_name} — lista zawiera nienumeryczne dane")
                    continue
            else:
                print(f"⚠️ Nieobsługiwany typ dla atrybutu {attr_name}: {type(attr_val)}")
                continue

        # Spróbuj ustawić wartość
        attrib = geo.findPrimAttrib(attr_name)
        if attrib:
            try:
                prim.setAttribValue(attr_name, attr_val)
            except hou.OperationFailed:
                print(f"⚠️ Nie udało się ustawić {attr_name}={attr_val} (typ niezgodny)")
        else:
            print(f"⚠️ Nie znaleziono atrybutu {attr_name} po dodaniu")

print("--- Zakończono przypisywanie metadanych. ---")
