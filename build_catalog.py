from pathlib import Path
import csv
import json
import re
import shutil
import sys

IMAGE_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".webp", ".avif", ".bmp", ".gif", ".tif", ".tiff"}

MAIN_ALIASES = {
    "anime": "Anime",
    "oyun": "Oyun",
    "film-dizi": "Film-Dizi",
    "film & dizi": "Film-Dizi",
    "film ve dizi": "Film-Dizi",
    "film": "Film-Dizi",
    "dizi": "Film-Dizi",
    "dc": "DC",
    "dc comics": "DC",
    "marvel": "Marvel",
}

LOL_ALIASES = {"league of legends", "leagueoflegends", "lol"}
WOW_ALIASES = {"world of warcraft", "wow", "warcraft 3", "warcraft"}

def slugify(text: str) -> str:
    table = {"ı":"i","İ":"i","ş":"s","Ş":"s","ğ":"g","Ğ":"g","ü":"u","Ü":"u","ö":"o","Ö":"o","ç":"c","Ç":"c"}
    for old, new in table.items():
        text = text.replace(old, new)
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "figur"

def direct_images(folder: Path) -> list[Path]:
    return sorted(
        file for file in folder.iterdir()
        if file.is_file() and file.suffix.lower() in IMAGE_EXTS
    )

def read_description(folder: Path) -> str:
    for name in ("aciklama.txt", "açıklama.txt", "description.txt"):
        file = folder / name
        if file.exists():
            return file.read_text(encoding="utf-8", errors="ignore").strip()
    return ""

def classify(relative_parts: tuple[str, ...]) -> tuple[str, str, str]:
    """
    Figür klasörü yolundan:
    - ana kategori
    - görünen evren
    - oyun özel grubu
    çıkarır.
    """
    parents = list(relative_parts[:-1])
    normalized = [part.strip().lower() for part in parents]

    if not parents:
        return "Oyun", "Diğer Oyunlar", "Diğer Oyunlar"

    first = normalized[0]

    if first in MAIN_ALIASES:
        main_category = MAIN_ALIASES[first]

        if main_category == "Oyun":
            universe = parents[1] if len(parents) >= 2 else "Diğer Oyunlar"
        else:
            universe = parents[1] if len(parents) >= 2 else main_category
    else:
        # Eski yapı: output/League of Legends/Ahri
        main_category = "Oyun"
        universe = parents[0]

    universe_key = universe.strip().lower()

    if universe_key in LOL_ALIASES:
        game_group = "League of Legends"
    elif universe_key in WOW_ALIASES:
        game_group = "World of Warcraft"
    else:
        game_group = "Diğer Oyunlar"

    return main_category, universe, game_group

def main() -> None:
    project = Path(__file__).resolve().parent
    site = project / "site"

    arg = " ".join(sys.argv[1:]).strip()
    source = Path(arg.strip('"')) if arg else Path(input("Output klasörünün yolunu yapıştır: ").strip().strip('"'))

    if not source.exists() or not source.is_dir():
        print("Klasör bulunamadı:", source)
        return

    target = site / "assets" / "catalog"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    # V3 kuralı: İçinde doğrudan en az bir görsel bulunan HER klasör bir figürdür.
    all_dirs = sorted(folder for folder in source.rglob("*") if folder.is_dir())
    figure_folders = [folder for folder in all_dirs if direct_images(folder)]

    items = []
    used_ids = set()
    rows = []

    for folder in figure_folders:
        rel = folder.relative_to(source).parts
        name = rel[-1]
        main_category, universe, game_group = classify(rel)
        images = direct_images(folder)

        base_id = slugify("-".join(rel))
        item_id = base_id
        number = 2
        while item_id in used_ids:
            item_id = f"{base_id}-{number}"
            number += 1
        used_ids.add(item_id)

        destination = target / item_id
        destination.mkdir(parents=True, exist_ok=True)

        copied = []
        for index, image in enumerate(images, 1):
            ext = ".jpg" if image.suffix.lower() in {".jpeg", ".jpe", ".jfif"} else image.suffix.lower()
            filename = f"{index:02d}{ext}"
            shutil.copy2(image, destination / filename)
            copied.append(f"assets/catalog/{item_id}/{filename}")

        description = read_description(folder)

        item = {
            "id": item_id,
            "name": name,
            "mainCategory": main_category,
            "universe": universe,
            "gameGroup": game_group,
            "tags": [name, universe, main_category, game_group, *rel[:-1]],
            "cover": copied[0],
            "images": copied[1:],
            "description": description,
        }
        items.append(item)

        rows.append({
            "figür": name,
            "ana_kategori": main_category,
            "evren": universe,
            "oyun_grubu": game_group,
            "görsel_sayısı": len(images),
            "açıklama_var": "Evet" if description else "Hayır",
            "klasör": str(folder),
        })

    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "catalog.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (project / "envanter.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys() if rows else ["figür"])
        writer.writeheader()
        writer.writerows(rows)

    report = [
        f"Taranan toplam klasör: {len(all_dirs)}",
        f"Doğrudan görsel içeren figür klasörü: {len(figure_folders)}",
        f"Kataloğa eklenen figür: {len(items)}",
        f"Toplam görsel: {sum(row['görsel_sayısı'] for row in rows)}",
        "",
        "ÖNEMLİ:",
        "Bu sayı beklediğiniz sayıdan düşükse, eksik figür klasörleri seçtiğiniz output klasöründe değildir.",
        "envanter.csv dosyası kataloğa eklenen bütün figürleri tek tek listeler.",
    ]
    (project / "tarama_raporu.txt").write_text("\n".join(report), encoding="utf-8")

    print()
    print(f"Taranan toplam klasör: {len(all_dirs)}")
    print(f"Doğrudan görsel içeren figür klasörü: {len(figure_folders)}")
    print(f"Kataloğa eklenen figür: {len(items)}")
    print(f"Toplam görsel: {sum(row['görsel_sayısı'] for row in rows)}")
    print()
    print("Envanter:", (project / "envanter.csv").resolve())
    print("Rapor:", (project / "tarama_raporu.txt").resolve())
    print()
    print("Test komutu:")
    print("python -m http.server 8000 -d site")

if __name__ == "__main__":
    main()
