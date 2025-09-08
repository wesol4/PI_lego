# -*- coding: utf-8 -*-
"""
Importer helperów do Houdini z JSON-a w formacie:
[
  {
    "path": "/root/connectivity/MyHelper/",
    "type": "VX0060596",
    "hasMesh": true,
    "matrix": [[...],[...],[...],[tx,ty,tz,1]]
  },
  ...
]

Funkcje:
- tworzy hierarchię w /obj (domyślnie pod /obj/helpers_import),
- każdy helper to Null (control type: hex lub circle), kolor zależnie od hasMesh,
- ustawia world transform z 4x4 (z konwersją jednostek cm->m),
- dodaje spare parm "helper_type" = typ z JSON.

Uruchomienie z hythona:
  hython import_helpers_to_houdini.py --json "P:/.../setofdoom_helpers.json" --root "/obj/helpers_import"

Jeśli skrypt wklejasz do shelf toola, ustaw JSON_PATH poniżej i wywołaj main_in_houdini().
"""

import json, os, sys, argparse

# Houdini API
import hou

# ---------- konfiguracja domyślna ----------
DEFAULT_ROOT = "/obj/helpers_import"
UNIT_SCALE = 0.01  # Maya cm -> Houdini m

# ---------- utilsy ----------
def ensure_node(parent: hou.Node, name: str, op_type: str) -> hou.Node:
    """Utwórz lub zwróć istniejący node o danej nazwie."""
    n = parent.node(name)
    if n is None:
        n = parent.createNode(op_type, node_name=name)
    return n

def ensure_hierarchy_from_path(root_parent: hou.Node, dag_path: str) -> hou.Node:
    """
    Zamienia DAG '/a/b/c/' na węzły w Houdini:
    - pośrednie poziomy: subnet (albo null jako grupa) — tu użyjemy NULL jako grupy dla lekkości
    - ostatni element: to nasz docelowy helper (też Null; potem ustawimy transform)
    """
    parts = [p for p in dag_path.split('/') if p]  # bez pustych
    if not parts:
        raise ValueError(f"Empty path in entry: {dag_path}")
    parent = root_parent
    for i, part in enumerate(parts):
        is_leaf = (i == len(parts) - 1)
        # dla uproszczenia: wszystkie poziomy to Null-e; leaf różni się parametrami wyglądu
        node = parent.node(part)
        if node is None:
            node = parent.createNode("null", node_name=part)
            # pośrednie: mniejszy geoscale i inny kształt
            node.parm("geoscale").set(0.05 if not is_leaf else 0.1)
            node.parm("controltype").set(0 if not is_leaf else 7)  # 0=Null, 7=Hex
            # zaznacz jako "grupa" na userData (nie wpływa na działanie)
            if not is_leaf:
                node.setUserData("is_helper_group", "1")
        parent = node
    return parent

def matrix_list_to_hou_matrix4(m_list, unit_scale=UNIT_SCALE) -> hou.Matrix4:
    """
    m_list: [[r00..r03],[r10..r13],[r20..r23],[r30..r33]]  (row-major)
    Przelicza translacje cm->m.
    """
    # Skopiuj, żeby nie modyfikować oryginału
    rows = [list(row) for row in m_list]
    # translation w wierszu 3 kolumny 0..2 (row-major)
    rows[3][0] = float(rows[3][0]) * unit_scale
    rows[3][1] = float(rows[3][1]) * unit_scale
    rows[3][2] = float(rows[3][2]) * unit_scale
    return hou.Matrix4(rows)

def set_world_matrix(obj_node: hou.Node, M: hou.Matrix4):
    """
    Ustaw world transform tak, by pasował do macierzy M (już w metrach).
    Wymaga poprawnej hierarchii (parent ustawiony przed wywołaniem).
    """
    obj_node.setWorldTransform(M)

def colorize(node: hou.Node, has_mesh: bool):
    """Kolor: zielony dla hasMesh, niebieski dla helperów bez mesha."""
    node.setColor(hou.Color((0.35, 0.75, 0.35)) if has_mesh else hou.Color((0.35, 0.55, 0.85)))

def add_helper_type_parm(node: hou.Node, value: str):
    """Dodaj spare parm 'helper_type' jeśli nie istnieje i ustaw wartość."""
    ptg = node.parmTemplateGroup()
    if node.parm("helper_type") is None:
        s = hou.StringParmTemplate("helper_type", "Helper Type", 1, default_value=(value or "",))
        s.setTags({"spare_category": "Helper"})
        ptg.append(s)
        node.setParmTemplateGroup(ptg)
    node.parm("helper_type").set(value or "")

# ---------- import właściwy ----------
def import_helpers(json_path: str, root_path: str = DEFAULT_ROOT, unit_scale: float = UNIT_SCALE):
    if not os.path.isfile(json_path):
        raise FileNotFoundError(json_path)

    # 1) przygotuj root w /obj
    obj = hou.node("/obj")
    if obj is None:
        raise RuntimeError("Nie znaleziono /obj (scene leve).")
    root = obj.node(root_path.split('/')[-1]) if root_path.startswith("/obj/") else None
    if root is None:
        # utwórz bezwzględnie w /obj z nazwą z końca ścieżki
        root_name = root_path.split('/')[-1] if root_path.startswith("/obj/") else "helpers_import"
        root = obj.createNode("subnet", node_name=root_name)

    # 2) wczytaj JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("JSON root nie jest listą.")

    created = 0
    for entry in data:
        try:
            dag_path = entry.get("path") or ""
            typ = entry.get("type") or ""
            has_mesh = bool(entry.get("hasMesh", False))
            m_list = entry.get("matrix")

            if not dag_path or not m_list:
                continue

            # a) zbuduj hierarchię i pobierz node-liścia
            leaf = ensure_hierarchy_from_path(root, dag_path)

            # b) ustaw wygląd / kolor / spare parm
            colorize(leaf, has_mesh)
            # dla helpera (leaf) użyj kontrolki "hex" lub "circle"
            leaf.parm("controltype").set(7 if has_mesh else 1)  # 7=Hex, 1=Circle
            leaf.parm("geoscale").set(0.1)
            add_helper_type_parm(leaf, typ)

            # c) ustaw world transform
            M = matrix_list_to_hou_matrix4(m_list, unit_scale=unit_scale)
            set_world_matrix(leaf, M)

            created += 1
        except Exception as e:
            print(f"⚠️ pominięto wpis (path={entry.get('path')}): {e}")

    # 3) uporządkuj layout i wyświetl info
    try:
        root.layoutChildren()
    except Exception:
        pass
    print(f"✅ Zaimportowano helperów: {created} do {root.path()}")

# ---------- tryby uruchomienia ----------
def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Ścieżka do pliku JSON (…_helpers.json)")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="Docelowy węzeł w /obj (np. /obj/helpers_import)")
    parser.add_argument("--unitScale", type=float, default=UNIT_SCALE, help="Skala translacji (Maya cm->m = 0.01)")
    args = parser.parse_args()
    import_helpers(args.json, args.root, args.unitScale)

def main_in_houdini(JSON_PATH=None, ROOT_PATH=DEFAULT_ROOT, UNIT=UNIT_SCALE):
    """Wygodne wywołanie, gdy wklejasz kod do Python Source Editor/Shelf Toola."""
    if JSON_PATH is None:
        raise ValueError("Podaj JSON_PATH!")
    import_helpers(JSON_PATH, ROOT_PATH, UNIT)

# Jeśli skrypt startowany przez hython/houdini - użyj CLI.
if __name__ == "__main__":
    # W środowisku 'hython' hou jest już dostępne; w czystym Pythonie to się nie uruchomi.
    main_cli()
