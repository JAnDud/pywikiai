#!/usr/bin/python3
# -*- coding: utf-8 -*-

import pywikibot
from pywikibot.page import FilePage

# -----------------------------
# KONFIGURACE
# -----------------------------
TARGET_USER = "JAn Dudík"
SUMMARY = "Adding or completing SDC author (P170) with qualifiers"
MAX_EDITS = 10   # limit počtu EDITACÍ

# -----------------------------
# FUNKCE
# -----------------------------

def ensure_qualifier(claim, pid, value, site):
    """
    Zajistí, že kvalifikátor existuje. Pokud ne, doplní ho.
    Vrací True pokud byla provedena editace.
    """
    if pid in claim.qualifiers:
        return False  # nic se nedělá

    q = pywikibot.Claim(site, pid)
    q.setTarget(value)
    claim.addQualifier(q, summary=SUMMARY)
    print(f"  ✔ doplněn kvalifikátor {pid} → {value}")
    return True


def add_or_fix_author(file_page, username):
    """
    Vrací True pokud byla provedena editace (alespoň jedna).
    """
    media = file_page.data_item()
    media.get()

    site = file_page.site
    edited = False

    # -----------------------------
    # 1) najít nebo vytvořit P170
    # -----------------------------
    if "P170" in media.claims:
        claim = media.claims["P170"][0]
        print("✔ P170 existuje, doplňuji chybějící kvalifikátory")
    else:
        # vytvořit P170 = novalue
        claim = pywikibot.Claim(site, "P170")
        claim.setSnakType("novalue")
        media.addClaim(claim, summary=SUMMARY)
        print("✔ vytvořen P170 = novalue")
        edited = True

    # -----------------------------
    # 2) doplnit kvalifikátory
    # -----------------------------

    # P2093 – textové jméno autora
    if ensure_qualifier(claim, "P2093", username, site):
        edited = True

    # P4174 – uživatelské jméno na projektech Wikimedia
    if ensure_qualifier(claim, "P4174", username.replace(" ", " "), site):
        edited = True

    # P2699 – URL profilu
    if ensure_qualifier(
        claim,
        "P2699",
        f"https://commons.wikimedia.org/wiki/user:{username.replace(' ', '_')}",
        site
    ):
        edited = True

    return edited


# -----------------------------
# HLAVNÍ PROGRAM
# -----------------------------

site = pywikibot.Site("commons", "commons")

print(f"Načítám uploady uživatele: {TARGET_USER}")

edit_count = 0

for logentry in site.logevents(logtype='upload', user=TARGET_USER):

    if edit_count >= MAX_EDITS:
        print(f"\n⏹ Limit {MAX_EDITS} EDITACÍ dosažen, končím.")
        break

    filename = logentry.page().title()
    file_page = FilePage(site, filename)

    print(f"\n=== {filename} ===")

    try:
        if add_or_fix_author(file_page, TARGET_USER):
            edit_count += 1
            print(f"  → provedena editace ({edit_count}/{MAX_EDITS})")
        else:
            print("  → žádná editace nebyla potřeba")
    except Exception as e:
        print(f"❌ Chyba u {filename}: {e}")

print(f"\nHotovo. Provedeno {edit_count} editací.")
