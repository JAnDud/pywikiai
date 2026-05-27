#!/usr/bin/python3
# -*- coding: utf-8 -*-

import pywikibot
from pywikibot import pagegenerators
from pywikibot.data import sparql

site = pywikibot.Site("wikidata", "wikidata")
repo = site.data_repository()
repo.get_tokens(['csrf'])
repo.tokens['csrf']

PROPERTY = "P4075"   # vstupní property P6736
LANG = "cs"
AUTO_MODE = False

# -------------------------
# Heuristický genitiv (fallback)
# -------------------------

def guess_genitive(label):
    l = label

    if l.endswith("ice"):
        return l
    if l.endswith("nice"):
        return l
    if l.endswith("e"):
        return l
    if l.endswith("a"):
        return l[:-1] + "y"
    if l.endswith("y"):
        return l[:-1] + ""
    if l.endswith("o"):
        return l[:-1] + "a"
    if l.endswith("ovice"):
        return l[:-3] + "ic"
    if l.endswith("ov"):
        return l + "a"
    return l + "u"

# -------------------------
# Genitiv přes P1448 → lexém
# -------------------------

def get_genitive_from_p1448(item):
    """Vrátí genitiv přes P1448 + P7018, jinak None."""

    if "P1448" not in item.claims:
        return None

    for claim in item.claims["P1448"]:
        target = claim.getTarget()

        if not hasattr(target, "language") or target.language != "cs":
            continue

        # --- kvalifikátor s lexémem ---
        if "P7018" not in claim.qualifiers:
            continue

        for q in claim.qualifiers["P7018"]:
            lex_target = q.getTarget()

            # normalizace na lexém
            if hasattr(lex_target, "on_lexeme"):
                lexeme = lex_target.on_lexeme
            else:
                lexeme = lex_target

            try:
                lexeme.get()
            except Exception:
                continue

            for form in lexeme.forms:
                try:
                    data = form.toJSON()
                    features = data.get("grammaticalFeatures", [])
                except Exception:
                    continue

                # genitiv
                if "Q146233" in features:
                    reps = data.get("representations", {})
                    if "cs" in reps:
                        return reps["cs"]["value"]

    return None
    
def get_genitive(label, item=None):

    # 1) přes P1448 + P7018
    if item:
        gen = get_genitive_from_p1448(item)
        if gen:
            return gen

    # 2) SPARQL lexém podle názvu
    lexeme_id = get_lexeme_by_lemma(label)
    if lexeme_id:
        gen = get_genitive_from_lexeme_id(lexeme_id)
        if gen:
            return gen

    # 3) výjimky
    if label.startswith("Praha"):
        return label.replace("Praha", "Prahy")

    if label == "Plzeň":
        return "Plzně"

    # 4) fallback
    return guess_genitive(label)
    
from pywikibot.data import sparql

def get_lexeme_by_lemma(label):
    query = f'''
    SELECT ?lexeme WHERE {{
      ?lexeme dct:language wd:Q9056 ;
              wikibase:lemma "{label}"@cs .
    }}
    LIMIT 1
    '''
    sq = sparql.SparqlQuery()
    data = sq.select(query)

    if data:
        return data[0]['lexeme'].split('/')[-1]

    return None
    
def get_genitive_from_lexeme_id(lexeme_id):
    lexeme = pywikibot.LexemePage(repo, lexeme_id)

    try:
        lexeme.get()
    except Exception:
        return None

    for form in lexeme.forms:
        data = form.toJSON()
        features = data.get("grammaticalFeatures", [])

        if "Q146786" in features:  # genitiv
            reps = data.get("representations", {})
            if "cs" in reps:
                return reps["cs"]["value"]

    return None        
    
def try_with_aliases(item, description):
    aliases = item.aliases.get(LANG, [])
    original_label = item.labels.get(LANG)

    for alias in aliases:
        alias = alias.strip()

        if not alias or alias == original_label:
            continue

        print(f"→ Zkouším alias jako label: {alias}")

        try:
            item.editEntity({
                "labels": {LANG: alias},
                "descriptions": {LANG: description}
            }, summary="Použit alias jako label kvůli konfliktu")

            print(f"✓ Uloženo s aliasem: {alias}")
            return True

        except Exception as e:
            if "label-with-description-conflict" in str(e):
                print("  ↳ stále konflikt")
                continue
            else:
                raise

    return False     
    
def get_coords_string(item):
    if "P625" not in item.claims:
        return None

    coord = item.claims["P625"][0].getTarget()
    lat = round(coord.lat, 5)
    lon = round(coord.lon, 5)

    return f"({lat}, {lon})"
    
def try_numbered_labels(item, description):
    base_label = item.labels.get(LANG)

    for i in range(1, 100):
        new_label = f"{base_label} {i}"

        print(f"→ Zkouším: {new_label}")

        try:
            item.editEntity({
                "labels": {LANG: new_label},
                "descriptions": {LANG: description}
            }, summary="Rozlišení pomocí čísla + souřadnic")

            print(f"✓ Uloženo jako: {new_label}")
            return True

        except Exception as e:
            if "label-with-description-conflict" in str(e):
                continue
            else:
                raise

    return False           
    
# -------------------------
# SPARQL: najít položky s danou property
# -------------------------

query = f"""
SELECT ?item WHERE {{
  ?item wdt:{PROPERTY} ?x .
}}
"""

generator = pagegenerators.WikidataSPARQLPageGenerator(query, site=site)

# -------------------------
# Hlavní smyčka
# -------------------------

from pywikibot.exceptions import OtherPageSaveError

for item in generator:
    item.get()
    qid = item.id

    print("\n====================================")
    print(f"Položka: {qid}")
    print("====================================")

    # přeskočit pokud má popis
    if LANG in item.descriptions:
        print("→ Má popis, přeskočeno.")
        continue

    # P31
    if "P31" not in item.claims:
        print("→ Nemá P31, přeskočeno.")
        continue

    p31_target = item.claims["P31"][0].getTarget()
    p31_label = (
        p31_target.labels.get(LANG)
        or p31_target.labels.get("en")
        or p31_target.id
    )

    # P131
    if "P131" not in item.claims:
        print("→ Nemá P131, přeskočeno.")
        continue

    p131_target = item.claims["P131"][0].getTarget()
    p131_label = (
        p131_target.labels.get(LANG)
        or p131_target.labels.get("en")
        or p131_target.id
    )

    # genitiv
    gen = get_genitive(p131_label, p131_target)

    print(f"P31:  {p31_label}")
    print(f"P131: {p131_label} → genitiv: {gen}")

    # základní description (bez souřadnic)
    description = f"{p31_label} na území {gen}"

    print(f"Navržený popis: {description}")


    if not AUTO_MODE:
        confirm = input("Potvrdit? ([y]es / [a]ll / [n]o): ").strip().lower()
    
        if confirm == "a":
            AUTO_MODE = True
            print("→ Přepnuto do AUTO režimu (bez dalších dotazů)")
    
        elif confirm != "y":
            print("→ Zrušeno.")
            continue
    # --- pokus o uložení ---
    try:
        item.editDescriptions(
            {LANG: description},
            summary="Automatic [cs] description according P31 and P131"
        )
        print("✓ Popis uložen.")
        continue

    except OtherPageSaveError as e:
        if "label-with-description-conflict" not in str(e):
            raise

        print("⚠ Konflikt label+description")

    # --- 1) alias ---
    if try_with_aliases(item, description):
        continue

    # --- 2) přidat souřadnice do description ---
    coords = get_coords_string(item)

    if coords:
        description2 = f"{p31_label} na území {gen} {coords}"
        print(f"→ Zkouším se souřadnicemi: {description2}")

        try:
            item.editDescriptions(
                {LANG: description2},
                summary="Automatic description + coordinates (conflict fix)"
            )
            print("✓ Uloženo se souřadnicemi")
            continue

        except OtherPageSaveError as e:
            if "label-with-description-conflict" not in str(e):
                raise

    # --- 3) číslovaný label ---
    if try_numbered_labels(item, description2 if coords else description):
        continue

    print("✗ Nelze vyřešit → přeskočeno")
