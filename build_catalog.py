from pathlib import Path
import csv
import json
import re
import shutil
import sys

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif",
    ".png", ".webp", ".avif",
    ".bmp", ".gif", ".tif", ".tiff",
}

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

PREFIXES = {
    "Anime": "ANM",
    "League of Legends": "LOL",
    "World of Warcraft": "WOW",
    "Diğer Oyunlar": "GAM",
    "Film-Dizi": "MOV",
    "DC": "DC",
    "Marvel": "MAR",
}


def slugify(text: str) -> str:
    table = {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s",
        "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
        "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    }

    for old, new in table.items():
        text = text.replace(old, new)

    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower() or "figur"


def direct_images(folder: Path) -> list[Path]:
    return sorted(
        file
        for file in folder.iterdir()
        if file.is_file() and file.suffix.lower() in IMAGE_EXTS
    )


def read_description(folder: Path) -> str:
    for name in ("aciklama.txt", "açıklama.txt", "description.txt"):
        file = folder / name

        if file.exists():
            return file.read_text(
                encoding="utf-8",
                errors="ignore",
            ).strip()

    return ""


def classify(relative_parts: tuple[str, ...]) -> tuple[str, str, str]:
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


def choose_prefix(main_category: str, game_group: str) -> str:
    if main_category == "Oyun":
        return PREFIXES.get(game_group, "GAM")

    return PREFIXES.get(main_category, "NYR")


def read_info(folder: Path) -> dict:
    path = folder / "info.json"

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_info(folder: Path, info: dict) -> None:
    path = folder / "info.json"
    path.write_text(
        json.dumps(info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def scan_existing_ids(figure_folders: list[Path]) -> tuple[set[str], dict[str, int]]:
    used_ids: set[str] = set()
    max_numbers: dict[str, int] = {}

    for folder in figure_folders:
        info = read_info(folder)
        figure_id = str(info.get("id", "")).strip().upper()

        match = re.fullmatch(r"([A-Z]+)-(\d{4,})", figure_id)

        if not match:
            continue

        prefix = match.group(1)
        number = int(match.group(2))

        used_ids.add(figure_id)
        max_numbers[prefix] = max(max_numbers.get(prefix, 0), number)

    return used_ids, max_numbers


def next_id(prefix: str, used_ids: set[str], max_numbers: dict[str, int]) -> str:
    number = max_numbers.get(prefix, 0) + 1

    while True:
        candidate = f"{prefix}-{number:04d}"

        if candidate not in used_ids:
            used_ids.add(candidate)
            max_numbers[prefix] = number
            return candidate

        number += 1


def main() -> None:
    project = Path(__file__).resolve().parent
    site = project / "site"

    arg = " ".join(sys.argv[1:]).strip()

    source = (
        Path(arg.strip('"'))
        if arg
        else Path(
            input("Output klasörünün yolunu yapıştır: ")
            .strip()
            .strip('"')
        )
    )

    if not source.exists() or not source.is_dir():
        print("Klasör bulunamadı:", source)
        return

    target = site / "assets" / "catalog"

    if target.exists():
        shutil.rmtree(target)

    target.mkdir(parents=True, exist_ok=True)

    # İçinde doğrudan görsel bulunan her klasör bir figürdür.
    all_dirs = sorted(
        folder
        for folder in source.rglob("*")
        if folder.is_dir()
    )

    figure_folders = [
        folder
        for folder in all_dirs
        if direct_images(folder)
    ]

    used_ids, max_numbers = scan_existing_ids(figure_folders)

    items = []
    rows = []

    for folder in figure_folders:
        relative_parts = folder.relative_to(source).parts
        name = relative_parts[-1]

        main_category, universe, game_group = classify(relative_parts)
        prefix = choose_prefix(main_category, game_group)
        images = direct_images(folder)
        description = read_description(folder)

        info = read_info(folder)
        figure_id = str(info.get("id", "")).strip().upper()

        # Geçerli ID yoksa yeni ve kalıcı bir ID oluştur.
        if not re.fullmatch(r"[A-Z]+-\d{4,}", figure_id):
            figure_id = next_id(prefix, used_ids, max_numbers)

        # Klasör adı değişse bile ID info.json içinde korunur.
        info.update({
            "id": figure_id,
            "name": info.get("name") or name,
            "mainCategory": main_category,
            "universe": universe,
            "gameGroup": game_group,
            "scale": info.get("scale", ""),
            "height": info.get("height", ""),
            "etsy": info.get("etsy", ""),
        })

        save_info(folder, info)

        item_id = slugify(figure_id)
        destination = target / item_id
        destination.mkdir(parents=True, exist_ok=True)

        copied = []

        for index, image in enumerate(images, start=1):
            extension = (
                ".jpg"
                if image.suffix.lower() in {".jpeg", ".jpe", ".jfif"}
                else image.suffix.lower()
            )

            filename = f"{index:02d}{extension}"
            shutil.copy2(image, destination / filename)
            copied.append(
                f"assets/catalog/{item_id}/{filename}"
            )

        item = {
            "id": figure_id,
            "slug": item_id,
            "name": info["name"],
            "mainCategory": main_category,
            "universe": universe,
            "gameGroup": game_group,
            "scale": info.get("scale", ""),
            "height": info.get("height", ""),
            "etsy": info.get("etsy", ""),
            "tags": [
                figure_id,
                info["name"],
                universe,
                main_category,
                game_group,
                *relative_parts[:-1],
            ],
            "cover": copied[0],
            "images": copied[1:],
            "description": description,
        }

        items.append(item)

        rows.append({
            "id": figure_id,
            "figür": info["name"],
            "ana_kategori": main_category,
            "evren": universe,
            "oyun_grubu": game_group,
            "ölçek": info.get("scale", ""),
            "boy": info.get("height", ""),
            "etsy": info.get("etsy", ""),
            "görsel_sayısı": len(images),
            "açıklama_var": "Evet" if description else "Hayır",
            "klasör": str(folder),
        })

    # ID sırasına göre katalog sıralaması.
    items.sort(key=lambda item: item["id"])

    (site / "data").mkdir(exist_ok=True)

    (site / "data" / "catalog.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (project / "envanter.csv").open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        fieldnames = list(rows[0].keys()) if rows else ["id", "figür"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["id"]))

    report = [
        f"Taranan toplam klasör: {len(all_dirs)}",
        f"Kataloğa eklenen figür: {len(items)}",
        f"Toplam görsel: {sum(row['görsel_sayısı'] for row in rows)}",
        "",
        "ID DAĞILIMI:",
    ]

    for prefix in sorted(max_numbers):
        count = sum(1 for item in items if item["id"].startswith(prefix + "-"))
        report.append(f"{prefix}: {count}")

    (project / "tarama_raporu.txt").write_text(
        "\n".join(report),
        encoding="utf-8",
    )

    print()
    print(f"Kataloğa eklenen figür: {len(items)}")
    print(f"Toplam görsel: {sum(row['görsel_sayısı'] for row in rows)}")
    print()
    print("Her figür klasörüne info.json oluşturuldu.")
    print("ID'ler bundan sonra değişmeden korunacak.")
    print()
    print("Envanter:", (project / "envanter.csv").resolve())
    print("Rapor:", (project / "tarama_raporu.txt").resolve())
    print()
    print("Test komutu:")
    print("python -m http.server 8000 -d site")


if __name__ == "__main__":
    main()
