#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kontrola a oprava vlastnosti P1433 („publikováno v“) na Wikidatech
podle šablony {{NavigacePaP}} na Wikizdrojích.

Použití:
  python pwb.py check_p1433.py -family:wikisource -lang:cs -transcludes:"NavigacePaP"
"""

import sys
import re
import pywikibot
from pywikibot import pagegenerators

TEMPLATE_NAME = "NavigacePaP"


def get_param(page, name):
    text = page.text
    m = re.search(r"\|\s*%s\s*=\s*([^|{}]+)" % re.escape(name), text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def guess_base_title(page, title_param=None):
    """
    Určí základní název díla podle faktické struktury stránky na Wikizdrojích.

    Logika:
    - Vyhodnocuje všechny nadřazené úrovně podle {{PAGENAME}} a {{BASEPAGENAME}}.
    - Vrací první nadřazenou stránku, která existuje a má položku Wikidat.
    - Pokud žádná nemá položku, vrací nejvyšší existující.
    - Ignoruje parametr |TITUL=, který bývá nespolehlivý.
    """

    site = page.site
    title = page.title()
    parts = title.split("/")

    # Pokud stránka není podstránka, vrací samotný název
    if len(parts) == 1:
        return parts[0]

    # Vygeneruj všechny možné nadřazené úrovně (odshora dolů)
    # Např. A/B/C/D → ["A", "A/B", "A/B/C"]
    candidates = ["/".join(parts[:i]) for i in range(1, len(parts))]

    # Projdeme kandidáty od nejnižší úrovně k nejvyšší (od „nejbližšího rodiče“ směrem nahoru)
    best_existing = None
    for candidate in reversed(candidates):
        candidate_page = pywikibot.Page(site, candidate)
        if not candidate_page.exists():
            continue
        if candidate_page.isRedirectPage():
            candidate_page = candidate_page.getRedirectTarget()

        best_existing = candidate_page.title()

        # pokud má Wikidata položku, vracíme ji jako výsledek
        try:
            pywikibot.ItemPage.fromPage(candidate_page)
            return candidate_page.title()
        except Exception:
            continue

    # Pokud žádná nadřazená stránka nemá položku Wikidat,
    # vrať nejvyšší existující
    return best_existing or parts[0]


def get_item_for_page(site, title):
    page = pywikibot.Page(site, title)
    try:
        return pywikibot.ItemPage.fromPage(page)
    except Exception:
        return None


def get_publication_item(item):
    """Vrátí aktuální položku P1433 (pokud existuje)."""
    if "P1433" in item.claims:
        claim = item.claims["P1433"][0]
        tgt = claim.getTarget()
        if isinstance(tgt, pywikibot.ItemPage):
            return tgt
    return None


def confirm(question):
    """Zeptá se uživatele."""
    while True:
        ans = input(question + " [y]es / [n]o / [a]ll > ").strip().lower()
        if ans in {"y", "n", "a"}:
            return ans


def process_page(page, repo, all_yes=False):
    print(f"\n== {page.title()} ==")

    try:
        item = pywikibot.ItemPage.fromPage(page)
    except Exception:
        print(" ⚠ Stránka nemá položku Wikidat.")
        return all_yes

    site = page.site
    title_param = get_param(page, "TITUL")

    # --- TITUL chybí, zkus odhadnout z nadřazené stránky ---
    if not title_param:
       print(" ⚠ Šablona NavigacePaP nemá TITUL.")
       parts = page.title().split("/")
       if len(parts) <= 1:
           print("   ⚠ Nelze odhadnout název – stránka nemá nadřazenou úroveň.")
           return all_yes

    # Projdeme hierarchii od nejbližšího rodiče po nejvyšší úroveň
       candidates = ["/".join(parts[:i]) for i in range(len(parts) - 1, 0, -1)]

       for cand in candidates:
           print(f"   ➜ Zkouším odhadovaný titul: {cand}")
           cand_page = pywikibot.Page(site, cand)
           if not cand_page.exists():
                continue
           if cand_page.isRedirectPage():
               cand_page = cand_page.getRedirectTarget()

           cand_item = get_item_for_page(site, cand_page.title())
           if cand_item:
               print(f"   ✅ Nalezeno: {cand_page.title()} ({cand_item.id})")
               ans = "y" if all_yes else confirm(f"Přidat publikováno v {cand_item.id} ({cand_page.title()})?")
               if ans in {"y", "a"}:
                   claim = pywikibot.Claim(repo, 'P1433')
                   claim.setTarget(cand_item)
                   item.addClaim(claim, summary="Doplněno publikováno v (odhad hierarchie bez TITUL)")
                   if ans == "a":
                       all_yes = True
               return all_yes

       print("   ⚠ Žádná nadřazená úroveň nemá položku Wikidat.")
       return all_yes


    # --- běžné zpracování, pokud TITUL existuje ---
    base_title = guess_base_title(page, title_param)
    expected_item = get_item_for_page(site, base_title)

    # --- Nenalezena položka, zkus vícestupňový odhad ---
    if not expected_item:
        print(f" ⚠ Nenalezena položka pro očekávané dílo: {base_title}")

        parts = page.title().split("/")
        if len(parts) > 2:
            prefix = "/".join(parts[:-1])
            if not base_title.startswith(prefix):
                candidate_full = f"{prefix}/{base_title}"
                print(f"   ➜ Zkouším odhadnutý úplný titul: {candidate_full}")
                candidate_item = get_item_for_page(site, candidate_full)
                if candidate_item:
                    print(f"   ✅ Nalezeno jako {candidate_item.id} ({candidate_item.labels.get('cs')})")
                    # ... po nalezení cand_item a před dotazem "Přidat publikováno v ..."
                    current_item = get_publication_item(item)

                    # Pokud už položka má stejné P1433, nedělej nic
                    if current_item and current_item.id == cand_item.id:
                        print(f"   ✅ Položka již má správné 'publikováno v' ({current_item.id}) – bez změny.")
                        return all_yes

                    ans = "y" if all_yes else confirm(f"Použít {candidate_full}?")
                    if ans in {"y", "a"}:
                        claim = pywikibot.Claim(repo, 'P1433')
                        claim.setTarget(candidate_item)
                        item.addClaim(claim, summary="Oprava publikováno v (NavigacePaP, odhad vícestupňového názvu)")
                        if ans == "a":
                            all_yes = True
                    return all_yes
                else:
                    print(f"   ⚠ {candidate_full} nemá položku Wikidat.")

        # --- Fallback: nabídni podobné názvy ---
        search_title = base_title.lower()
        alt_candidates = []
        for p in site.allpages(namespace=0):
            if search_title in p.title().lower() and "/" not in p.title():
                alt_candidates.append(p)
            if len(alt_candidates) >= 5:
                break

        if alt_candidates:
            print("   🔎 Možné kandidáty:")
            for i, cand in enumerate(alt_candidates, 1):
                print(f"     {i}. {cand.title()}")

            choice = input("   Zadej číslo správného titulu (nebo Enter pro přeskočit): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(alt_candidates):
                chosen_page = alt_candidates[int(choice) - 1]
                expected_item = get_item_for_page(site, chosen_page.title())
                if expected_item:
                    ans = "y" if all_yes else confirm(f"Použít {chosen_page.title()} ({expected_item.id}) místo {base_title}?")
                    if ans in {"y", "a"}:
                        claim = pywikibot.Claim(repo, 'P1433')
                        claim.setTarget(expected_item)
                        item.addClaim(claim, summary="Oprava publikováno v (NavigacePaP, nalezeno podobné dílo)")
                        if ans == "a":
                            all_yes = True
                else:
                    print("   ⚠ Zvolená stránka nemá položku Wikidat.")
        else:
            print("   ⚠ Nenašel jsem žádné podobné názvy.")
        return all_yes

    # --- Zpracování existující položky ---
    current_item = get_publication_item(item)

    # Chybí P1433
    if not current_item:
        print(f" ➕ Chybí 'publikováno v' — mělo by být {expected_item.id} ({expected_item.labels.get('cs')})")
        ans = "y" if all_yes else confirm("Přidat?")
        if ans in {"y", "a"}:
            claim = pywikibot.Claim(repo, 'P1433')
            claim.setTarget(expected_item)
            item.addClaim(claim, summary="Doplněno publikováno v (NavigacePaP)")
            if ans == "a":
                all_yes = True
        return all_yes

    # Odpovídá
    if current_item.id == expected_item.id:
        print(f" ✅ P1433 odpovídá ({current_item.id})")
        return all_yes

    # Nesoulad
    print(f" ⚠ Nesoulad:")
    print(f"   aktuální : {current_item.id} ({current_item.labels.get('cs')})")
    print(f"   očekávané: {expected_item.id} ({expected_item.labels.get('cs')})")
    ans = "y" if all_yes else confirm("Nahradit?")
    if ans in {"y", "a"}:
        claim = item.claims["P1433"][0]
        claim.changeTarget(expected_item, summary="Oprava publikováno v (NavigacePaP)")
        if ans == "a":
            all_yes = True
    return all_yes


def main():
    local_args = pywikibot.handle_args(sys.argv[1:])
    genFactory = pagegenerators.GeneratorFactory()
    genFactory.handle_args(local_args)
    gen = genFactory.getCombinedGenerator(preload=True)

    site = pywikibot.Site()
    repo = site.data_repository()

    if not gen:
        pywikibot.bot.suggest_help(missing_generator=True)
        return

    all_yes = False
    for page in gen:
        if not page.exists() or page.isRedirectPage():
            continue
        all_yes = process_page(page, repo, all_yes)


if __name__ == "__main__":
    main()

