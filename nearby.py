#!/usr/bin/python3
# -*- coding: utf-8 -*-

import re
import webbrowser
import pywikibot
from pywikibot import pagegenerators
from colorama import init, Fore, Style

init()

# ---------------------------------------
# Pomocné funkce
# ---------------------------------------

def extract_qids(text):
    """Najde QID ve formátech:
       [[:d:Q12345|...]]
       {{Q|Q12345}}
       {{Odkaz na položku WD|Q12345}}
    """
    qids = set()
    qids |= set(re.findall(r":d:(Q\d+)", text))
    qids |= set(re.findall(r"\{\{Q\|?(Q\d+)\}\}", text))
    qids |= set(re.findall(r"Odkaz na položku WD\|?(Q\d+)", text))
    return list(qids)


def get_coords(repo, qid):
    """Vrátí souřadnice položky z Wikidat."""
    item = pywikibot.ItemPage(repo, qid)
    try:
        item.get()
    except Exception:
        return None

    coords = item.coordinates()
    if not coords:
        return None

    if isinstance(coords, list):
        coords = coords[0]

    return coords.lat, coords.lon


def get_label(repo, qid):
    """Vrátí český nebo anglický label."""
    item = pywikibot.ItemPage(repo, qid)
    try:
        item.get()
    except Exception:
        return ""
    return item.labels.get("cs") or item.labels.get("en") or ""


def color_for_distance(dist):
    """Vrátí barvu podle vzdálenosti."""
    if dist < 10:
        return Fore.RED      # kriticky blízko
    elif dist < 25:
        return Fore.YELLOW   # velmi blízko
    else:
        return Fore.GREEN    # blízko (do 50 m)


# ---------------------------------------
# Hlavní skript
# ---------------------------------------

def main():
    factory = pagegenerators.GeneratorFactory()

    # nejdřív argumenty, až potom Site()
    args = pywikibot.handle_args()
    for arg in args:
        factory.handle_arg(arg)

    site = pywikibot.Site("cs", "wikipedia")
    repo = site.data_repository()
    siteWD = pywikibot.Site("wikidata", "wikidata")

    gen = factory.getCombinedGenerator()
    if not gen:
        print("❌ Nebyly nalezeny žádné stránky.")
        return

    for page in gen:
        print(f"\n=== Stránka: {page.title()} ===")

        text = page.get()
        qids = extract_qids(text)

        if not qids:
            print("  → žádné QID")
            continue

        for qid in qids:
            print(f"\n  → Kontroluji {qid}")

            coords = get_coords(repo, qid)
            if not coords:
                print("    ✖ bez souřadnic")
                continue

            lat, lon = coords

            label = get_label(repo, qid)
            print(f"    Objekt: {qid} — {label}")

            # Wikidata geosearch (NE cs.wiki, NE SPARQL)
            req = siteWD.simple_request(
                action="query",
                list="geosearch",
                gscoord=f"{lat}|{lon}",
                gsradius=50,
                gslimit=10,
                format="json"
            )
            data = req.submit()

            nearby = data.get("query", {}).get("geosearch", [])
            nearby_items = []

            for obj in nearby:
                q2 = obj["title"]   # vždy QID
                dist = obj["dist"]

                if q2 == qid:
                    continue  # stejný objekt

                label2 = get_label(repo, q2)
                color = color_for_distance(dist)
                nearby_items.append((dist, q2, label2, color))

            if not nearby_items:
                print("    → žádné blízké objekty")
                continue

            print("\n    Blízké objekty:")

            for dist, q2, label2, color in sorted(nearby_items, key=lambda x: x[0]):
                print(f"      {color}[{dist:.1f} m]{Style.RESET_ALL}  {q2} — {label2}")

            choice = input("\n    Zadej QID k otevření (Enter = přeskočit): ").strip()

            if choice.startswith("Q"):
                webbrowser.open(f"https://www.wikidata.org/wiki/{choice}")


if __name__ == "__main__":
    main()

