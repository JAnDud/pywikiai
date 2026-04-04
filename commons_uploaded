#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import pywikibot
from pywikibot import pagegenerators
from pywikibot.comms import http
import requests
import time

# ==== Nastavení ====
USERNAME = "My username"
OUTPUT_DIR = "..\..\commons_thumbs"
THUMB_WIDTH = 330  # klidně 250 nebo 330
LIMIT = 1000       # None = všechny, nebo např. 1000 pro test
DELAY = 4            # pauza mezi requesty
MAX_RETRIES = 3        # retry při 429
# ==================

site = pywikibot.Site("commons", "commons")
site.login()

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

seen = set()
count = 0
skipped = 0
errors = 0

# pouze uploady (ne editace!)
for logentry in site.logevents(logtype="upload", user=USERNAME):
    try:
        page = logentry.page()
        filename = page.title(with_ns=False)

        # odstranění "File:"
        if filename.startswith("File:"):
            filename = filename[5:]

        # jen JPG/JPEG
        if not filename.lower().endswith((".jpg", ".jpeg", ".JPG", ".Jpg")):
            continue

        # deduplikace
        if filename in seen:
            continue
        seen.add(filename)

        safe_name = filename.replace("/", "_")
        output_path = os.path.join(OUTPUT_DIR, safe_name)

        # ⏭️ přeskočit existující
        if os.path.exists(output_path):
            skipped += 1
            continue

        file_page = pywikibot.FilePage(site, "File:" + filename)
        thumb_url = file_page.get_file_url(url_width=THUMB_WIDTH)

        success = False

        for attempt in range(MAX_RETRIES):
            r = http.fetch(thumb_url)

            if r.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                print(f"OK: {filename}")
                count += 1
                success = True
                break

            elif r.status_code == 429:
                wait = 2 * (attempt + 1)
                print(f"429 → čekám {wait}s: {filename}")
                time.sleep(wait)

            else:
                print(f"ERR {r.status_code}: {filename}")
                errors += 1
                break

        if not success:
            print(f"FAIL: {filename}")
            errors += 1

        # zpomalení (klíčové!)
        time.sleep(DELAY)

        if LIMIT and count >= LIMIT:
            break

    except Exception as e:
        print(f"EXCEPTION: {filename} ({e})")
        errors += 1

print("\n===== HOTOVO =====")
print(f"Staženo:   {count}")
print(f"Přeskočeno:{skipped}")
print(f"Chyby:     {errors}")
