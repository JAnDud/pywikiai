#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vylepšená verze harvest_pap.py:
- Přeskočí položky, kde P1433 už má kvalifikátory (P155/P156)
- Doplní P155/P156, pokud chybí
- Pokud je víc P1433 se stejným cílem, odstraní duplicitní bez kvalifikátorů (po potvrzení)
- Pokud je víc různých P1433, nabídne otevření stránky na Wikidatech
"""

import pywikibot
from pywikibot import pagegenerators
import re
import webbrowser

TEMPLATE_NAME = "NavigacePaP"


def get_param_from_template(page, param):
    """Najde hodnotu parametru v šabloně NavigacePaP."""
    text = page.text
    m = re.search(r"\{\{\s*%s[^{}]*?\|\s*%s\s*=\s*([^|{}]+)" % (TEMPLATE_NAME, param), text, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip()


def get_item_for_page(site, title):
    """Vrátí Wikidata item pro danou stránku Wikizdrojů."""
    page = pywikibot.Page(site, title)
    try:
        return pywikibot.ItemPage.fromPage(page)
    except Exception:
        return None


def get_p1433_claims(item):
    """Vrátí všechny výroky P1433."""
    return item.claims.get("P1433", [])


def has_qualifiers(claim, qualifiers=("P155", "P156")):
    """Zjistí, zda výrok má uvedené kvalifikátory."""
    for q in qualifiers:
        if claim.qualifiers.get(q):
            return True
    return False


def add_statement_with_qualifier(repo, item, prop, target_item, journal_claim):
    """Přidá kvalifikátor P155/P156 k existujícímu výroku P1433."""
    if not target_item or not journal_claim:
        return

    # Zkontroluj, zda už takový kvalifikátor neexistuje
    for qual in journal_claim.qualifiers.get(prop, []):
        if qual.getTarget() == target_item:
            return  # už existuje

    qual_claim = pywikibot.Claim(repo, prop)
    qual_claim.setTarget(target_item)
    journal_claim.addQualifier(qual_claim, summary=f"Adding qualifier {prop} for P1433 (NavigacePaP)")
    pywikibot.output(f"  Přidávám {prop} → {target_item.id} ({target_item.labels.get('cs')}) jako kvalifikátor k P1433")


def cleanup_p1433_duplicates(repo, item, claims):
    """Pokud je více P1433, sjednotí nebo nabídne odstranění duplicit."""
    targets = [c.getTarget() for c in claims]
    unique_targets = list({t.id for t in targets if isinstance(t, pywikibot.ItemPage)})

    # Více různých P1433
    if len(unique_targets) > 1:
        pywikibot.output(" ⚠ Různé hodnoty 'publikováno v':")
        for c in claims:
            target = c.getTarget()
            pywikibot.output(f"   - {target.id} ({target.labels.get('cs')})")
        ans = input("Otevřít položku ve webovém prohlížeči? [y/N]: ").lower()
        if ans == "y":
            webbrowser.open(f"https://www.wikidata.org/wiki/{item.id}")
        return None

    # Duplicitní stejné P1433 – ponech ten s kvalifikátory
    target_qid = unique_targets[0]
    with_qual = [c for c in claims if has_qualifiers(c)]
    no_qual = [c for c in claims if not has_qualifiers(c)]

    if len(claims) > 1 and no_qual:
        pywikibot.output(f" ⚠ Více P1433 se stejným cílem ({target_qid}).")
        for c in no_qual:
            pywikibot.output("   - Kandidát na odstranění (bez kvalifikátorů).")
        ans = input("Odstranit nadbytečné bez kvalifikátorů? [y/n/a]: ").lower()
        if ans in {"y", "a"}:
            for c in no_qual:
                item.removeClaims([c], summary="Odstraněno duplicitní 'publikováno v' bez kvalifikátorů")
            pywikibot.output("   Duplicitní tvrzení odstraněna.")
            if ans == "a":
                global always_yes
                always_yes = True

    return [c for c in claims if c.getTarget().id == target_qid][0]


def process_page(page, repo):
    """Zpracuje jednu stránku Wikizdrojů."""
    pywikibot.output(f"\n== {page.title()} ==")
    try:
        item = pywikibot.ItemPage.fromPage(page)
    except Exception:
        pywikibot.warning("  ⚠ Stránka nemá položku Wikidat.")
        return

    site = page.site

    # Načti parametry z NavigacePaP
    prev_title = get_param_from_template(page, "PŘEDCHOZÍ")
    next_title = get_param_from_template(page, "DALŠÍ")

    if not (prev_title or next_title):
        pywikibot.output("  (žádná NavigacePaP nalezena nebo chybí předchozí/následující část)")
        return

    claims = get_p1433_claims(item)
    if not claims:
        pywikibot.warning("  ⚠ Žádné 'publikováno v (P1433)' nenalezeno – přeskočeno.")
        return

    # Vyřeš situaci s více P1433
    journal_claim = cleanup_p1433_duplicates(repo, item, claims)
    if journal_claim is None:
        return

    # Pokud má kvalifikátory P155/P156, přeskoč
    if has_qualifiers(journal_claim):
        pywikibot.output("  ℹ P1433 již obsahuje vymezení P155/P156 – přeskočeno.")
        return

    journal_qid = journal_claim.getTarget().id
    pywikibot.output(f"  Publikováno v: {journal_qid}")

    # === NOVĚ: Urč základní název podle faktické struktury stránky ===
    parts = page.title().split("/")
    if len(parts) > 1:
        base_title = "/".join(parts[:-1])  # rodičovská stránka
    else:
        base_title = page.title()
    pywikibot.output(f"  Určen základní název: {base_title}")

    # === Předchozí stránka ===
    if prev_title:
        # Pokud má stránka víceúrovňovou strukturu, doplň ji plně
        prev_full = "/".join(parts[:-1] + [prev_title.strip()])
        prev_item = get_item_for_page(site, prev_full)
        if prev_item:
            add_statement_with_qualifier(repo, item, 'P155', prev_item, journal_claim)
        else:
            pywikibot.warning(f"  ⚠ Nenalezena položka pro předchozí: {prev_full}")

    # === Následující stránka ===
    if next_title:
        next_full = "/".join(parts[:-1] + [next_title.strip()])
        next_item = get_item_for_page(site, next_full)
        if next_item:
            add_statement_with_qualifier(repo, item, 'P156', next_item, journal_claim)
        else:
            pywikibot.warning(f"  ⚠ Nenalezena položka pro následující: {next_full}")


def main():
    import sys
    global always_yes
    always_yes = False

    local_args = pywikibot.handle_args(sys.argv[1:])
    genFactory = pagegenerators.GeneratorFactory()
    genFactory.handle_args(local_args)
    gen = genFactory.getCombinedGenerator(preload=True)

    site = pywikibot.Site()
    repo = site.data_repository()

    if not gen:
        pywikibot.bot.suggest_help(missing_generator=True)
        return

    for page in gen:
        if not page.exists() or page.isRedirectPage():
            continue
        process_page(page, repo)


if __name__ == "__main__":
    main()

