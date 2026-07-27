"""Проверки разбора разметки. Работают на сохранённых страницах, без обращения к сети.

Запуск:  python3 tests/test_parsing.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from catalog.scraper import (
    clean_text,
    parse_listing,
    parse_price,
    parse_product_page,
    parse_stock_count,
)

FIXTURES = Path(__file__).parent / "fixtures"

passed = 0
failed = 0


def check(title, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  ✓ {title}")
    else:
        failed += 1
        print(f"  ✗ {title}: получено {actual!r}, ожидалось {expected!r}")


def test_price():
    print("Разбор цены")
    check("валюта перед числом", parse_price("£51.77"), (51.77, "£"))
    check("валюта после числа", parse_price("1 250,50 ₽"), (1250.5, "₽"))
    check("запятая как разделитель", parse_price("12,5"), (12.5, ""))
    check("текстовая валюта", parse_price("99 руб."), (99.0, "руб."))
    check("трёхбуквенный код", parse_price("Price: 1500 RUB"), (1500.0, "RUB"))
    check("нет числа", parse_price("нет цены"), (None, ""))
    check("пустая строка", parse_price(""), (None, ""))


def test_stock():
    print("Остаток на складе")
    check("есть количество", parse_stock_count("In stock (22 available)"), 22)
    check("нет количества", parse_stock_count("Out of stock"), None)
    check("пустая строка", parse_stock_count(""), None)


def test_clean():
    print("Чистка текста")
    check("переносы и пробелы", clean_text("  строка\n\n  с   пробелами \t"), "строка с пробелами")
    check("пустое значение", clean_text(""), "")


def test_listing():
    print("Страница списка")
    html = (FIXTURES / "listing.html").read_text(encoding="utf-8")
    items, next_url = parse_listing(html, "https://books.toscrape.com/catalogue/page-1.html")

    check("количество товаров", len(items), 20)
    check("ссылка на следующую", next_url, "https://books.toscrape.com/catalogue/page-2.html")
    check("название", items[0]["name"], "A Light in the Attic")
    check("цена числом", items[0]["price"], 51.77)
    check("рейтинг цифрой", items[0]["rating"], 3)
    check("ссылка абсолютная", items[0]["url"].startswith("https://"), True)
    check("у всех есть название", all(i["name"] for i in items), True)


def test_product():
    print("Карточка товара")
    html = (FIXTURES / "product.html").read_text(encoding="utf-8")
    detail = parse_product_page(html, "https://books.toscrape.com/x")

    check("артикул", detail["upc"], "a897fe39b1053632")
    check("категория из крошек", detail["category"], "Poetry")
    check("остаток", detail["in_stock"], 22)
    check("отзывы", detail["reviews"], 0)
    check("описание собрано", len(detail["description"]) > 50, True)


def test_broken():
    print("Битая разметка не роняет разбор")
    items, next_url = parse_listing("<html><body>ничего нет</body></html>", "https://x/")
    check("пустой список", items, [])
    check("нет следующей страницы", next_url, None)

    detail = parse_product_page("<html></html>", "https://x/")
    check("пустая карточка", detail["upc"], "")
    check("категория пустая", detail["category"], "")


def main():
    for test in (test_price, test_stock, test_clean, test_listing, test_product, test_broken):
        test()

    print(f"\nпройдено: {passed}, провалено: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
