# Importer #2: Tworzenie punktów helperów

import hou
import json
import os

node = hou.pwd()
geo = node.geometry()
geo.clear()

# Używamy nazwy 'path_json'
param = node.parm('path_json')
if not param:
    raise hou.Error("Brak parametru 'path_json'. Dodaj go w 'Edit Parameter Interface...'")
json_path = param.eval()

if not os.path.exists(json_path):
    raise hou.Error(f"Plik JSON nie został znaleziony: {json_path}")

with open(json_path, 'r', encoding='utf-8') as f:
    helpers_data = json.load(f)

if not isinstance(helpers_data, list):
    raise hou.Error("Format pliku _helpers.json jest nieprawidłowy - oczekiwano listy.")

# Tworzenie atrybutów
geo.addAttrib(hou.attribType.Point, "path", "") # Ścieżka do SHAPE rodzica
geo.addAttrib(hou.attribType.Point, "type", "")
geo.addAttrib(hou.attribType.Point, "hasMesh", 0)
identity_matrix = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
geo.addAttrib(hou.attribType.Point, "transform", identity_matrix)

print(f"--- Tworzenie {len(helpers_data)} punktów helperów ---")

for helper in helpers_data:
    new_point = geo.createPoint()

    # Przypisz atrybuty
    new_point.setAttribValue("path", helper.get("path", ""))
    new_point.setAttribValue("type", helper.get("type", ""))
    new_point.setAttribValue("hasMesh", 1 if helper.get("hasMesh", False) else 0)

    matrix_list_of_lists = helper.get("transform")
    if matrix_list_of_lists:
        try:
            flat_matrix_list = [item for sublist in matrix_list_of_lists for item in sublist]
            transform_matrix = hou.Matrix4(flat_matrix_list)
            new_point.setPosition(transform_matrix.extractTranslates())
            new_point.setAttribValue("transform", transform_matrix)
        except Exception as e:
            print(f"Ostrzeżenie: Błąd macierzy dla helpera typu '{helper.get('type', 'N/A')}': {e}")

print("--- Zakończono tworzenie helperów. ---")