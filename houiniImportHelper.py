# -*- coding: utf-8 -*-
"""
Eksport helperów z Maya do JSON (tylko grupa/i 'connectivity').
Zapisuje listę obiektów:
  {
    "path": "/pelna/sciezka/dag/",
    "matrix": [[...],[...],[...],[...]]  # world 4x4, row-major
  }

Użycie (PowerShell):
  "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" maya_export_helpers.py ^
    --inputFile "C:\path\setofdoom.ma" ^
    --outputBasePath "C:\path\out"
"""

import argparse
import os
import json

import maya.standalone
import maya.cmds as cmds

# -------- utils --------

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
    # Szukaj
