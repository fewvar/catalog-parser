"""Разбор каталога: список товаров, пагинация, карточка товара."""

import re
from dataclasses import dataclass, asdict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .fetcher import FetchError, Fetcher

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_URL = urljoin(BASE_URL, "catalogue/page-1.html")

RATING_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass
class Product:
    name: str
    price: float | None
    currency: str
    rating: int | None
    availability: str
    in_stock: int | None
    category: str
    upc: str
    reviews: int | None
    description: str
    url: str

    def as_dict(self) -> dict:
        return asdict(self)


def clean_text(value: str) -> str:
    """Схлопываем переносы и повторные пробелы — иначе в Excel каша."""
    return re.sub(r"\s+", " ", value or "").strip()


def parse_price(raw: str) -> tuple[float | None, str]:
    """Валюта пишется и до числа (£51.77), и после (1 250,50 ₽) — ловим оба варианта."""
    text = clean_text(raw)
    match = re.search(r"(\d[\d\s ]*(?:[.,]\d+)?)", text)
    if not match:
        return None, ""

    currency_match = re.search(r"[£$€₽¥]|руб\.?|USD|EUR|RUB", text, re.IGNORECASE)
    currency = currency_match.group(0) if currency_match else ""

    number = match.group(1).replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(number), currency
    except ValueError:
        return None, currency


def parse_stock_count(availability: str) -> int | None:
    match = re.search(r"(\d+)\s+available", availability)
    return int(match.group(1)) if match else None


def parse_listing(html: str, page_url: str) -> tuple[list[dict], str | None]:
    """Возвращает товары со страницы списка и ссылку на следующую страницу."""
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        if not link:
            continue

        price_tag = card.select_one(".price_color")
        price, currency = parse_price(price_tag.get_text() if price_tag else "")

        rating = None
        rating_tag = card.select_one("p.star-rating")
        if rating_tag:
            for css_class in rating_tag.get("class", []):
                if css_class in RATING_WORDS:
                    rating = RATING_WORDS[css_class]
                    break

        stock_tag = card.select_one(".instock.availability")

        items.append({
            "name": clean_text(link.get("title") or link.get_text()),
            "price": price,
            "currency": currency,
            "rating": rating,
            "availability": clean_text(stock_tag.get_text()) if stock_tag else "",
            "url": urljoin(page_url, link.get("href", "")),
        })

    next_link = soup.select_one("li.next a")
    next_url = urljoin(page_url, next_link.get("href")) if next_link else None
    return items, next_url


def parse_product_page(html: str, url: str) -> dict:
    """Достаёт характеристики со страницы товара."""
    soup = BeautifulSoup(html, "html.parser")
    details: dict[str, str] = {}

    for row in soup.select("table.table-striped tr"):
        header = row.find("th")
        value = row.find("td")
        if header and value:
            details[clean_text(header.get_text())] = clean_text(value.get_text())

    category = ""
    crumbs = soup.select("ul.breadcrumb li a")
    if len(crumbs) >= 2:
        category = clean_text(crumbs[-1].get_text())

    description = ""
    marker = soup.select_one("#product_description")
    if marker:
        paragraph = marker.find_next("p")
        if paragraph:
            description = clean_text(paragraph.get_text())

    reviews = details.get("Number of reviews", "")
    availability = details.get("Availability", "")

    return {
        "category": category,
        "upc": details.get("UPC", ""),
        "description": description,
        "reviews": int(reviews) if reviews.isdigit() else None,
        "availability_detailed": availability,
        "in_stock": parse_stock_count(availability),
    }


def scrape(
    fetcher: Fetcher,
    pages: int | None = 3,
    with_details: bool = True,
    start_url: str = CATALOGUE_URL,
    on_progress=None,
) -> list[Product]:
    """Обходит пагинацию и собирает товары. pages=None — весь каталог."""
    products: list[Product] = []
    url = start_url
    page_number = 0

    while url and (pages is None or page_number < pages):
        page_number += 1
        if on_progress:
            on_progress("page", page_number, url)

        html = fetcher.get(url)
        items, next_url = parse_listing(html, url)

        for item in items:
            extra = {
                "category": "",
                "upc": "",
                "description": "",
                "reviews": None,
                "in_stock": None,
                "availability_detailed": "",
            }

            if with_details:
                try:
                    extra = parse_product_page(fetcher.get(item["url"]), item["url"])
                except FetchError as error:
                    if on_progress:
                        on_progress("skip", item["name"], str(error))

            products.append(Product(
                name=item["name"],
                price=item["price"],
                currency=item["currency"],
                rating=item["rating"],
                availability=extra["availability_detailed"] or item["availability"],
                in_stock=extra["in_stock"],
                category=extra["category"],
                upc=extra["upc"],
                reviews=extra["reviews"],
                description=extra["description"],
                url=item["url"],
            ))

            if on_progress:
                on_progress("item", len(products), item["name"])

        url = next_url

    return products
