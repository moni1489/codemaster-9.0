"""Сборка seed/branches.json из «Адреса и контакты филиалов.xls» + «Контакты.docx» (главное здание).

Запуск:  python seed/tools/build_branches.py   (нужен пакет xlrd: pip install xlrd)

Координаты НЕ из источника заказчика: проставлены вручную по центрам населённых пунктов
(приблизительно) → coords_verified=false у всех; где населённый пункт неоднозначен — null.
Переводы названий на kk/en сделаны разработчиком → translation_status='machine'.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parents[2]
XLS = ROOT / "docs" / "source" / "Адреса и контакты филиалов.xls"
OUT = ROOT / "seed" / "branches.json"

# slug, короткое имя ru/kk/en, населённый пункт ru/kk/en, lat, lon (приблизительно; None — неизвестно)
META: dict[str, tuple[str, str, str, str, str, str, str, float | None, float | None]] = {
    "Алтай": ("altai", "Филиал района Алтай", "Алтай ауданының филиалы", "Altai District Branch",
              "г. Алтай", "Алтай қ.", "Altai", 49.727, 84.273),
    "Глубоков": ("glubokoe", "Глубоковский районный филиал", "Глубокое аудандық филиалы",
                 "Glubokoe District Branch", "п. Глубокое", "Глубокое к.", "Glubokoe", 50.139, 82.312),
    "Зайсан": ("zaisan", "Зайсанский районный филиал", "Зайсан аудандық филиалы", "Zaisan District Branch",
               "г. Зайсан", "Зайсан қ.", "Zaisan", 47.469, 84.871),
    "Катон": ("katonkaragai", "Катон-Карагайский районный филиал", "Катонқарағай аудандық филиалы",
              "Katon-Karagai District Branch", "с. Катон-Карагай", "Катонқарағай а.", "Katon-Karagai",
              49.177, 85.610),
    "Курчум": ("kurchum", "Курчумский районный филиал", "Күршім аудандық филиалы",
               "Kurchum District Branch", "с. Курчум", "Күршім а.", "Kurchum", 48.566, 83.656),
    "Марқакөл": ("markakol", "Филиал района Марқакөл", "Марқакөл ауданының филиалы",
                 "Markakol District Branch", "с. Маркаколь", "Марқакөл а.", "Markakol", None, None),
    "Риддер": ("ridder", "Риддерский городской филиал", "Риддер қалалық филиалы", "Ridder City Branch",
               "г. Риддер", "Риддер қ.", "Ridder", 50.345, 83.513),
    "Самар": ("samar", "Филиал района Самар", "Самар ауданының филиалы", "Samar District Branch",
              "с. Самар", "Самар а.", "Samar", 49.033, 83.350),
    "Тарбагатай": ("tarbagatai", "Тарбагатайский районный филиал", "Тарбағатай аудандық филиалы",
                   "Tarbagatai District Branch", "с. Акжар", "Ақжар а.", "Akzhar", None, None),
    "Улан": ("ulan", "Уланский районный филиал", "Ұлан аудандық филиалы", "Ulan District Branch",
             "пос. Касыма Кайсенова", "Қасым Қайсенов к.", "Kasym Kaisenov", 49.865, 82.768),
    "Үлкен": ("ulkennaryn", "Филиал района Үлкен Нарын", "Үлкен Нарын ауданының филиалы",
              "Ulken Naryn District Branch", "с. Улкен Нарын", "Үлкен Нарын а.", "Ulken Naryn", 49.217, 84.513),
    "Усть-Каменогорский": ("ukg-personnel", "Усть-Каменогорский городской филиал по личному составу",
                           "Өскемен қалалық жеке құрам бойынша филиалы",
                           "Ust-Kamenogorsk City Branch (personnel records)",
                           "г. Усть-Каменогорск", "Өскемен қ.", "Ust-Kamenogorsk", 49.951, 82.611),
    "Шемонаих": ("shemonaikha", "Шемонаихинский районный филиал", "Шемонаиха аудандық филиалы",
                 "Shemonaikha District Branch", "г. Шемонаиха", "Шемонаиха қ.", "Shemonaikha", 50.628, 81.911),
}

MAIN = {
    "slug": "main",
    "type": "main",
    "name": {
        "ru": "КГУ «Государственный архив Восточно-Казахстанской области» управления цифровизации и архивов ВКО",
        "kk": "ШҚО цифрландыру және архивтер басқармасының «Шығыс Қазақстан облысының мемлекеттік архиві» КММ",
        "en": "State Archive of East Kazakhstan Region (main building)",
    },
    "short_name": {"ru": "Главное здание", "kk": "Бас ғимарат", "en": "Main building"},
    "locality": {"ru": "г. Усть-Каменогорск", "kk": "Өскемен қ.", "en": "Ust-Kamenogorsk"},
    "address": {
        "ru": "070000, г. Усть-Каменогорск, ул. Бейбітшілік, 26/1 (Головкова, 26/1)",
        "kk": "070000, Өскемен қ., Бейбітшілік к-сі, 26/1",
        "en": "26/1 Beibitshilik St., Ust-Kamenogorsk 070000",
    },
    "director": "Жапаров Аскар Кенжебаевич",
    "phone": "8 (7232) 25-13-22",
    "phones_extra": {"Приёмная": "8 (7232) 25-59-76", "Инспектор по кадрам": "8 (7232) 25-26-60",
                     "Бухгалтерия": "8 (7232) 70-31-06"},
    "email": "arhiv-ukg@yandex.kz",
    "hours": {"ru": "Пн–Пт 8:00–17:00; читальный зал Пн–Пт 9:00–16:00",
              "kk": "Дс–Жм 8:00–17:00; оқу залы Дс–Жм 9:00–16:00",
              "en": "Mon–Fri 8:00–17:00; reading room Mon–Fri 9:00–16:00"},
    "lat": 49.9555,
    "lon": 82.6170,
    "coords_verified": False,
    "translation_status": {"ru": "original", "kk": "machine", "en": "machine"},
    "source": "docs/source/Контакты.docx",
}


def build() -> list[dict[str, object]]:
    sheet = xlrd.open_workbook(str(XLS)).sheet_by_index(0)
    out: list[dict[str, object]] = [MAIN]
    for r in range(5, sheet.nrows):
        cells = [" ".join(str(c.value).split()) for c in sheet.row(r)]
        if not cells[1]:
            continue
        key = next(k for k in META if k in cells[1])
        slug, ru, kk, en, loc_ru, loc_kk, loc_en, lat, lon = META[key]
        address = re.sub(r"^ВКО,\s*", "", cells[3])
        email = cells[5].replace("alimvko", "akimvko").replace(".qov.", ".gov.")
        out.append({
            "slug": slug,
            "type": "branch",
            "name": {"ru": f"{ru} КГУ «Государственный архив ВКО»", "kk": f"«ШҚО мемлекеттік архиві» КММ {kk}",
                     "en": f"{en}, State Archive of East Kazakhstan Region"},
            "official_name_ru": cells[1],
            "short_name": {"ru": ru, "kk": kk, "en": en},
            "locality": {"ru": loc_ru, "kk": loc_kk, "en": loc_en},
            "address": {"ru": address, "kk": address, "en": address},
            "director": cells[2],
            "phone": cells[4] or None,
            "email": email or None,
            "hours": {"ru": "Пн–Пт 9:00–18:00 (уточняйте по телефону)",
                      "kk": "Дс–Жм 9:00–18:00 (телефон арқылы нақтылаңыз)",
                      "en": "Mon–Fri 9:00–18:00 (please confirm by phone)"},
            "hours_verified": False,
            "lat": lat,
            "lon": lon,
            "coords_verified": False,
            "translation_status": {"ru": "original", "kk": "machine", "en": "machine"},
            "source": "docs/source/Адреса и контакты филиалов.xls",
        })
    return out


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(data)} объектов "
          f"({sum(1 for d in data if d['lat'] is None)} без координат)")
