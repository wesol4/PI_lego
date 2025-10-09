def build_abc_job_args(roots, start_frame, end_frame, step):
    """
    Buduje pełny job string dla AbcExport:
    - zawsze eksportuje UV + wszystkie UV sety
    - zapisuje kolory, widoczność, rotacje z eulerFilter
    - wymusza format Ogawa
    """
    # W niektórych środowiskach (mayapy/PDG) help() nic nie zwraca → fallback
    try:
        help_text = cmds.help("AbcExport") or ""
        supported = set(help_text.replace(",", " ").replace("\n", " ").split())
    except Exception:
        supported = set()

    args = []

    # Zakres klatek
    args += ["-frameRange", str(start_frame), str(end_frame)]
    if step and step > 0:
        args += ["-step", str(step)]

    # Główne flagi eksportowe (wymuszamy — są wspierane od wielu wersji Mayi)
    args += [
        "-worldSpace",       # globalne współrzędne
        "-uvWrite",          # główny UV set (map1)
        "-writeUVSets",      # wszystkie UV sety
        "-writeColorSets",   # kolory wierzchołków
        "-writeVisibility",  # animacja widoczności
        "-eulerFilter"       # poprawne rotacje
    ]

    # Format Alembica: Ogawa (szybszy i mniejszy niż HDF5)
    if "-dataFormat" in supported or True:
        args += ["-dataFormat", "Ogawa"]

    # Roots
    for r in roots:
        args += ["-root", r]

    # Log diagnostyczny
    log("Flagi użyte w job stringu: " + " ".join([a for a in args if a.startswith("-")]))
    return args
