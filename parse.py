"""Парсер каталога товаров: собирает карточки в Excel-таблицу."""

import argparse
import sys
import time
from pathlib import Path

from catalog.exporter import to_excel, to_json
from catalog.fetcher import FetchError, Fetcher
from catalog.scraper import CATALOGUE_URL, scrape


def build_reporter(quiet: bool):
    def report(kind: str, value, extra=""):
        if quiet:
            return
        if kind == "page":
            print(f"\n  Страница {value}: {extra}")
        elif kind == "item":
            print(f"    [{value:>4}] {extra[:60]}")
        elif kind == "skip":
            print(f"    ! {value} — пропущен ({extra})")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Собирает карточки товаров из каталога в Excel-таблицу.",
        epilog="Пример: python3 parse.py --pages 5 -o каталог.xlsx",
    )
    parser.add_argument("-p", "--pages", type=int, default=3, help="сколько страниц обойти (по умолчанию 3)")
    parser.add_argument("-a", "--all", action="store_true", help="весь каталог целиком")
    parser.add_argument("-o", "--out", type=Path, default=Path("каталог.xlsx"), help="куда сохранить Excel")
    parser.add_argument("--json", type=Path, help="дополнительно выгрузить в JSON")
    parser.add_argument("--json-short", type=int, metavar="N", help="в JSON подрезать описания до N символов и убрать отступы")
    parser.add_argument("--no-details", action="store_true", help="не заходить в карточки — быстрее, но без характеристик")
    parser.add_argument("-d", "--delay", type=float, default=0.5, help="пауза между запросами в секундах")
    parser.add_argument("--url", default=CATALOGUE_URL, help="стартовая страница каталога")
    parser.add_argument("-q", "--quiet", action="store_true", help="меньше вывода")
    args = parser.parse_args()

    if args.pages < 1 and not args.all:
        print("Ошибка: --pages должно быть больше нуля", file=sys.stderr)
        return 1

    pages = None if args.all else args.pages
    fetcher = Fetcher(delay=args.delay)
    started = time.monotonic()

    print(f"Каталог: {args.url}")
    print(f"Страниц: {'все' if pages is None else pages} | характеристики: {'нет' if args.no_details else 'да'} | пауза: {args.delay}с")

    try:
        products = scrape(
            fetcher,
            pages=pages,
            with_details=not args.no_details,
            start_url=args.url,
            on_progress=build_reporter(args.quiet),
        )
    except FetchError as error:
        sys.stdout.flush()
        print(f"\nОшибка: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        sys.stdout.flush()
        print("\nПрервано пользователем", file=sys.stderr)
        return 130
    finally:
        fetcher.close()

    if not products:
        print("\nНичего не собрано: проверьте адрес каталога", file=sys.stderr)
        return 1

    to_excel(products, args.out)
    if args.json:
        to_json(products, args.json, max_description=args.json_short)

    elapsed = time.monotonic() - started
    prices = [p.price for p in products if p.price is not None]

    print(f"\nСобрано товаров: {len(products)}")
    print(f"Запросов: {fetcher.requests_made} | время: {elapsed:.1f}с")
    if prices:
        print(f"Цены: от {min(prices)} до {max(prices)}, средняя {sum(prices) / len(prices):.2f}")
    print(f"Готово: {args.out}" + (f" и {args.json}" if args.json else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
