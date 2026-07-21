from pathlib import Path
import csv
import json
import re
import shutil
import sys
import tempfile


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


LOL_ALIASES = {
    "league of legends",
    "leagueoflegends",
    "lol",
}


WOW_ALIASES = {
    "world of warcraft",
    "wow",
    "warcraft 3",
    "warcraft",
}


PREFIXES = {
    "Anime": "ANM",
    "League of Legends": "LOL",
    "World of Warcraft": "WOW",
    "Diğer Oyunlar": "GAM",
    "Film-Dizi": "MOV",
    "DC": "DC",
    "Marvel": "MAR",
}


# GitHub reposunun kesin konumu
PROJECT_DIR = Path.home() / "Desktop" / "NyraCraftCatalog_v3"

# Web sitesinin bulunduğu klasör
SITE_DIR = PROJECT_DIR / "site"

# Programın olası çıktı klasörleri
SOURCE_CANDIDATES = [
    Path.home() / "Desktop" / "NyraCatalogManager" / "output",
    Path.home() / "NyraCatalogManager" / "output",
]


def slugify(text: str) -> str:
    table = {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }

    for old, new in table.items():
        text = text.replace(old, new)

    slug = re.sub(
        r"[^a-zA-Z0-9]+",
        "-",
        text,
    ).strip("-").lower()

    return slug or "figur"


def direct_images(folder: Path) -> list[Path]:
    try:
        return sorted(
            file
            for file in folder.iterdir()
            if file.is_file()
            and file.suffix.lower() in IMAGE_EXTS
        )
    except (PermissionError, OSError):
        return []


def read_description(folder: Path) -> str:
    possible_names = (
        "aciklama.txt",
        "açıklama.txt",
        "description.txt",
    )

    for name in possible_names:
        file = folder / name

        if file.exists():
            try:
                return file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).strip()
            except OSError:
                return ""

    return ""


def classify(
    relative_parts: tuple[str, ...],
) -> tuple[str, str, str]:
    parents = list(relative_parts[:-1])

    normalized = [
        part.strip().lower()
        for part in parents
    ]

    if not parents:
        return (
            "Oyun",
            "Diğer Oyunlar",
            "Diğer Oyunlar",
        )

    first = normalized[0]

    if first in MAIN_ALIASES:
        main_category = MAIN_ALIASES[first]

        if main_category == "Oyun":
            universe = (
                parents[1]
                if len(parents) >= 2
                else "Diğer Oyunlar"
            )
        else:
            universe = (
                parents[1]
                if len(parents) >= 2
                else main_category
            )
    else:
        # Eski klasör yapısı:
        # output/League of Legends/Ahri
        main_category = "Oyun"
        universe = parents[0]

    universe_key = universe.strip().lower()

    if universe_key in LOL_ALIASES:
        game_group = "League of Legends"

    elif universe_key in WOW_ALIASES:
        game_group = "World of Warcraft"

    else:
        game_group = "Diğer Oyunlar"

    return (
        main_category,
        universe,
        game_group,
    )


def choose_prefix(
    main_category: str,
    game_group: str,
) -> str:
    if main_category == "Oyun":
        return PREFIXES.get(
            game_group,
            "GAM",
        )

    return PREFIXES.get(
        main_category,
        "NYR",
    )


def read_info(folder: Path) -> dict:
    path = folder / "info.json"

    if not path.exists():
        return {}

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
        TypeError,
    ):
        return {}


def save_info(
    folder: Path,
    info: dict,
) -> None:
    path = folder / "info.json"

    try:
        path.write_text(
            json.dumps(
                info,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as error:
        print(
            f"UYARI: info.json yazılamadı: "
            f"{folder} | {error}"
        )


def scan_existing_ids(
    figure_folders: list[Path],
) -> tuple[set[str], dict[str, int]]:
    used_ids: set[str] = set()
    max_numbers: dict[str, int] = {}

    for folder in figure_folders:
        info = read_info(folder)

        figure_id = str(
            info.get("id", "")
        ).strip().upper()

        match = re.fullmatch(
            r"([A-Z]+)-(\d{4,})",
            figure_id,
        )

        if not match:
            continue

        prefix = match.group(1)
        number = int(match.group(2))

        used_ids.add(figure_id)

        max_numbers[prefix] = max(
            max_numbers.get(prefix, 0),
            number,
        )

    return used_ids, max_numbers


def next_id(
    prefix: str,
    used_ids: set[str],
    max_numbers: dict[str, int],
) -> str:
    number = max_numbers.get(prefix, 0) + 1

    while True:
        candidate = f"{prefix}-{number:04d}"

        if candidate not in used_ids:
            used_ids.add(candidate)
            max_numbers[prefix] = number
            return candidate

        number += 1


def find_source() -> Path:
    # Komutla klasör verilmişse onu kullan:
    # python build_catalog.py "C:\...\output"
    argument = " ".join(
        sys.argv[1:]
    ).strip()

    if argument:
        source = Path(
            argument.strip('"')
        ).expanduser()

        return source.resolve()

    # Bilinen konumları otomatik tara
    for candidate in SOURCE_CANDIDATES:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()

    # Bulunamazsa kullanıcıdan iste
    entered = input(
        "NyraCatalogManager output klasörünün "
        "yolunu yapıştır: "
    ).strip().strip('"')

    return Path(entered).expanduser().resolve()


def find_figure_folders(
    source: Path,
) -> tuple[list[Path], list[Path]]:
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

    return all_dirs, figure_folders


def safely_replace_directory(
    temporary_catalog: Path,
    final_catalog: Path,
) -> None:
    backup_catalog = (
        final_catalog.parent
        / "catalog_backup"
    )

    if backup_catalog.exists():
        shutil.rmtree(backup_catalog)

    try:
        if final_catalog.exists():
            final_catalog.rename(
                backup_catalog
            )

        temporary_catalog.rename(
            final_catalog
        )

        if backup_catalog.exists():
            shutil.rmtree(
                backup_catalog
            )

    except Exception:
        if final_catalog.exists():
            shutil.rmtree(
                final_catalog
            )

        if backup_catalog.exists():
            backup_catalog.rename(
                final_catalog
            )

        raise


def main() -> None:
    print()
    print("NYRA CRAFT KATALOG OLUŞTURUCU")
    print("-" * 35)

    source = find_source()

    if (
        not source.exists()
        or not source.is_dir()
    ):
        print()
        print(
            "HATA: Kaynak klasör bulunamadı:"
        )
        print(source)
        return

    if not PROJECT_DIR.exists():
        print()
        print(
            "HATA: GitHub proje klasörü bulunamadı:"
        )
        print(PROJECT_DIR)
        return

    if not SITE_DIR.exists():
        print()
        print(
            "HATA: Site klasörü bulunamadı:"
        )
        print(SITE_DIR)
        return

    print()
    print("Kaynak klasör:")
    print(source)

    print()
    print("Hedef site klasörü:")
    print(SITE_DIR)

    all_dirs, figure_folders = (
        find_figure_folders(source)
    )

    print()
    print(
        f"Taranan klasör: {len(all_dirs)}"
    )
    print(
        f"Görsel bulunan figür klasörü: "
        f"{len(figure_folders)}"
    )

    # Kaynak yanlış veya boşsa mevcut kataloğu silme
    if not figure_folders:
        print()
        print(
            "HATA: Kaynak klasörde hiçbir figür "
            "bulunamadı."
        )
        print(
            "Mevcut katalog korunmuştur ve "
            "hiçbir dosya silinmemiştir."
        )
        return

    used_ids, max_numbers = (
        scan_existing_ids(
            figure_folders
        )
    )

    items: list[dict] = []
    rows: list[dict] = []

    data_dir = SITE_DIR / "data"
    data_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Yeni görseller önce geçici klasöre hazırlanır.
    # İşlem tamamlanmadan eski katalog silinmez.
    temporary_root = Path(
        tempfile.mkdtemp(
            prefix="nyra_catalog_",
            dir=str(SITE_DIR / "assets"),
        )
    )

    temporary_catalog = (
        temporary_root / "catalog"
    )

    temporary_catalog.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        for folder in figure_folders:
            relative_parts = (
                folder.relative_to(
                    source
                ).parts
            )

            name = relative_parts[-1]

            (
                main_category,
                universe,
                game_group,
            ) = classify(relative_parts)

            prefix = choose_prefix(
                main_category,
                game_group,
            )

            images = direct_images(folder)
            description = read_description(
                folder
            )

            info = read_info(folder)

            figure_id = str(
                info.get("id", "")
            ).strip().upper()

            if not re.fullmatch(
                r"[A-Z]+-\d{4,}",
                figure_id,
            ):
                figure_id = next_id(
                    prefix,
                    used_ids,
                    max_numbers,
                )

            info.update({
                "id": figure_id,
                "name": (
                    info.get("name")
                    or name
                ),
                "mainCategory": (
                    main_category
                ),
                "universe": universe,
                "gameGroup": game_group,
                "scale": info.get(
                    "scale",
                    "",
                ),
                "height": info.get(
                    "height",
                    "",
                ),
                "etsy": info.get(
                    "etsy",
                    "",
                ),
            })

            save_info(
                folder,
                info,
            )

            item_slug = slugify(
                figure_id
            )

            destination = (
                temporary_catalog
                / item_slug
            )

            destination.mkdir(
                parents=True,
                exist_ok=True,
            )

            copied_images: list[str] = []

            for index, image in enumerate(
                images,
                start=1,
            ):
                extension = (
                    ".jpg"
                    if image.suffix.lower()
                    in {
                        ".jpeg",
                        ".jpe",
                        ".jfif",
                    }
                    else image.suffix.lower()
                )

                filename = (
                    f"{index:02d}{extension}"
                )

                shutil.copy2(
                    image,
                    destination / filename,
                )

                copied_images.append(
                    f"assets/catalog/"
                    f"{item_slug}/"
                    f"{filename}"
                )

            item = {
                "id": figure_id,
                "slug": item_slug,
                "name": info["name"],
                "mainCategory": (
                    main_category
                ),
                "universe": universe,
                "gameGroup": game_group,
                "scale": info.get(
                    "scale",
                    "",
                ),
                "height": info.get(
                    "height",
                    "",
                ),
                "etsy": info.get(
                    "etsy",
                    "",
                ),
                "tags": [
                    figure_id,
                    info["name"],
                    universe,
                    main_category,
                    game_group,
                    *relative_parts[:-1],
                ],
                "cover": copied_images[0],
                "images": copied_images[1:],
                "description": description,
            }

            items.append(item)

            rows.append({
                "id": figure_id,
                "figür": info["name"],
                "ana_kategori": (
                    main_category
                ),
                "evren": universe,
                "oyun_grubu": (
                    game_group
                ),
                "ölçek": info.get(
                    "scale",
                    "",
                ),
                "boy": info.get(
                    "height",
                    "",
                ),
                "etsy": info.get(
                    "etsy",
                    "",
                ),
                "görsel_sayısı": (
                    len(images)
                ),
                "açıklama_var": (
                    "Evet"
                    if description
                    else "Hayır"
                ),
                "klasör": str(folder),
            })

        if not items:
            print()
            print(
                "HATA: Katalog verisi "
                "oluşturulamadı."
            )
            print(
                "Eski katalog korunmuştur."
            )
            return

        items.sort(
            key=lambda item: item["id"]
        )

        rows.sort(
            key=lambda row: row["id"]
        )

        # catalog.json önce geçici dosyaya yazılır
        temporary_json = (
            data_dir
            / "catalog.json.tmp"
        )

        temporary_json.write_text(
            json.dumps(
                items,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # Envanter
        inventory_path = (
            PROJECT_DIR / "envanter.csv"
        )

        with inventory_path.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            fieldnames = (
                list(rows[0].keys())
                if rows
                else ["id", "figür"]
            )

            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(rows)

        report = [
            (
                f"Kaynak klasör: "
                f"{source}"
            ),
            (
                f"Taranan toplam klasör: "
                f"{len(all_dirs)}"
            ),
            (
                f"Kataloğa eklenen figür: "
                f"{len(items)}"
            ),
            (
                f"Toplam görsel: "
                f"{sum(row['görsel_sayısı'] for row in rows)}"
            ),
            "",
            "ID DAĞILIMI:",
        ]

        all_prefixes = sorted({
            item["id"].split("-")[0]
            for item in items
        })

        for prefix in all_prefixes:
            count = sum(
                1
                for item in items
                if item["id"].startswith(
                    prefix + "-"
                )
            )

            report.append(
                f"{prefix}: {count}"
            )

        report_path = (
            PROJECT_DIR
            / "tarama_raporu.txt"
        )

        report_path.write_text(
            "\n".join(report),
            encoding="utf-8",
        )

        # Her şey başarıyla hazırlandıktan sonra
        # eski katalog güvenli biçimde değiştirilir.
        final_catalog = (
            SITE_DIR
            / "assets"
            / "catalog"
        )

        final_catalog.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        safely_replace_directory(
            temporary_catalog,
            final_catalog,
        )

        final_json = (
            data_dir / "catalog.json"
        )

        temporary_json.replace(
            final_json
        )

        total_images = sum(
            row["görsel_sayısı"]
            for row in rows
        )

        print()
        print("KATALOG BAŞARIYLA OLUŞTURULDU")
        print("-" * 35)
        print(
            f"Figür sayısı: {len(items)}"
        )
        print(
            f"Görsel sayısı: {total_images}"
        )
        print()
        print("Katalog verisi:")
        print(final_json.resolve())
        print()
        print("Katalog görselleri:")
        print(final_catalog.resolve())
        print()
        print("Envanter:")
        print(inventory_path.resolve())
        print()
        print("Rapor:")
        print(report_path.resolve())
        print()
        print("Şimdi çalıştır:")
        print("git status")

    except Exception as error:
        print()
        print(
            "KATALOG OLUŞTURULURKEN "
            "HATA OLUŞTU:"
        )
        print(error)
        print()
        print(
            "Mevcut katalog korunmuştur."
        )

        temporary_json = (
            data_dir
            / "catalog.json.tmp"
        )

        if temporary_json.exists():
            temporary_json.unlink()

        raise

    finally:
        if temporary_root.exists():
            shutil.rmtree(
                temporary_root,
                ignore_errors=True,
            )


if __name__ == "__main__":
    main()