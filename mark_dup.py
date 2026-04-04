import re
import pywikibot

# ==== NASTAVENÍ ====
# udělej výpis duplikátů přes program czkawka
INPUT_FILE = "duplicates.txt" 
USERNAME = "My name"
REASON = "exact duplicate"
# ==================

site = pywikibot.Site("commons", "commons")
site.login()


def extract_groups(filepath):
    groups = []
    current = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line.startswith("Found "):
                if current:
                    groups.append(current)
                    current = []
            elif line.startswith('"'):
                match = re.search(r'"(.+?)"', line)
                if match:
                    current.append(match.group(1))

        if current:
            groups.append(current)

    return groups


def filename_from_path(path):
    return path.split("\\")[-1]


def get_file_info(filename):
    page = pywikibot.FilePage(site, "File:" + filename)

    try:
        is_redirect = page.isRedirectPage()
        redirect_target = None

        if is_redirect:
            try:
                target = page.getRedirectTarget()
                redirect_target = target.title(with_ns=False)
            except:
                redirect_target = "?"

        info = page.latest_file_info
        width = info.width
        height = info.height
        size = info.size
        timestamp = info.timestamp

        text = page.text
        has_dup = ("{{duplicate" in text.lower()) or ("{{dup" in text.lower())

        return {
            "page": page,
            "width": width,
            "height": height,
            "size": size,
            "timestamp": timestamp,
            "has_dup": has_dup,
            "is_redirect": is_redirect,
            "redirect_target": redirect_target,
        }

    except Exception as e:
        print(f"CHYBA při načítání {filename}: {e}")
        return None


def print_info(idx, name, info):
    print(f"\n[{idx}] {name}")
    if info:
        print(f"  Rozměry: {info['width']}x{info['height']}")
        print(f"  Velikost: {info['size']/1024:.1f} kB")
        print(f"  Datum: {info['timestamp']}")
        print(f"  Má Duplicate: {info['has_dup']}")
        print(f"  Redirect: {info['is_redirect']}")
        if info["is_redirect"]:
            print(f"    → {info['redirect_target']}")
    else:
        print("  (chyba načtení)")

def choose_keep(infos):
    # automatický návrh
    best = None

    for i, info in enumerate(infos):
        if not info:
            continue
        if best is None:
            best = i
        else:
            a = infos[best]
            b = info

            # větší rozměry
            if (b["width"] * b["height"]) > (a["width"] * a["height"]):
                best = i
            elif (b["width"] * b["height"]) == (a["width"] * a["height"]):
                # novější
                if b["timestamp"] > a["timestamp"]:
                    best = i

    return best


groups = extract_groups(INPUT_FILE)

for group in groups:
    filenames = [filename_from_path(p) for p in group]

    infos = []
    for name in filenames:
        info = get_file_info(name)
        infos.append(info)
    # ⏭️ přeskočit skupiny, které už jsou vyřešené
    if any(
        info and (info["has_dup"] or info["is_redirect"])
        for info in infos
    ):
        print("\n⏭️ Přeskakuji – obsahuje Duplicate nebo je redirect")
        continue        
   
  
    print("\n==============================")
    
    for i, (name, info) in enumerate(zip(filenames, infos), start=1):
        print_info(i, name, info)
          
    suggested = choose_keep(infos)
    if suggested is not None:
        print(f"\n👉 Návrh: ponechat [{suggested+1}]")

    choice = input("Vyber soubor k ZACHOVÁNÍ (číslo, Enter = přeskočit): ").strip()

    if not choice:
        continue

    try:
        keep_idx = int(choice) - 1
    except:
        print("Neplatná volba")
        continue

    for i, info in enumerate(infos):
        if i == keep_idx or not info:
            continue

        page = info["page"]
        keep_name = filenames[keep_idx]

        text = page.text

        if "{{duplicate" in text.lower() or "{{dup" in text.lower():
            print(f"Už má Duplicate: {filenames[i]}")
            continue

        new_text = "{{Duplicate|" + keep_name + "|" + REASON + "}}\n" + text

        summary = f"Marked as duplicate of [[File:{keep_name}]]"

        try:
            page.text = new_text
            if info["is_redirect"]:
                print(f"Přeskakuji redirect: {filenames[i]}")
                continue
            page.save(summary=summary)
            print(f"✔ Označeno: {filenames[i]}")
        except Exception as e:
            print(f"CHYBA při ukládání {filenames[i]}: {e}")
