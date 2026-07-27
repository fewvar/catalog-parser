import { writeXlsx } from "./xlsx.js";

const PAGE_SIZE = 50;

const dom = {
  stats: document.getElementById("stats"),
  statCount: document.getElementById("statCount"),
  statCats: document.getElementById("statCats"),
  statAvg: document.getElementById("statAvg"),
  statRange: document.getElementById("statRange"),
  controls: document.getElementById("controls"),
  search: document.getElementById("search"),
  category: document.getElementById("category"),
  rating: document.getElementById("rating"),
  download: document.getElementById("download"),
  error: document.getElementById("error"),
  loading: document.getElementById("loading"),
  found: document.getElementById("found"),
  table: document.getElementById("table"),
  moreWrap: document.getElementById("moreWrap"),
  more: document.getElementById("more"),
};

const COLUMNS = [
  { key: "name", title: "Название", sortable: true },
  { key: "category", title: "Категория", sortable: true },
  { key: "price", title: "Цена", sortable: true, numeric: true },
  { key: "rating", title: "Рейтинг", sortable: true, numeric: true },
  { key: "in_stock", title: "На складе", sortable: true, numeric: true },
  { key: "reviews", title: "Отзывов", sortable: true, numeric: true },
  { key: "upc", title: "Артикул" },
];

let all = [];
let filtered = [];
let shown = PAGE_SIZE;
let sort = { key: null, dir: 1 };

const money = (value) =>
  typeof value === "number" ? value.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

function showError(message) {
  dom.error.textContent = message;
  dom.error.hidden = !message;
}

function renderStats() {
  const prices = all.map((p) => p.price).filter((p) => typeof p === "number");
  const categories = new Set(all.map((p) => p.category).filter(Boolean));
  dom.statCount.textContent = all.length.toLocaleString("ru-RU");
  dom.statCats.textContent = categories.size;
  dom.statAvg.textContent = prices.length ? `£${money(prices.reduce((a, b) => a + b, 0) / prices.length)}` : "—";
  dom.statRange.textContent = prices.length ? `£${money(Math.min(...prices))}–£${money(Math.max(...prices))}` : "—";
  dom.stats.hidden = false;
}

function fillCategories() {
  const categories = [...new Set(all.map((p) => p.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, "en"));
  dom.category.innerHTML = "";
  const any = document.createElement("option");
  any.value = "";
  any.textContent = `Все категории (${categories.length})`;
  dom.category.append(any);
  for (const name of categories) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    dom.category.append(option);
  }
}

function applyFilters() {
  const query = dom.search.value.trim().toLowerCase();
  const category = dom.category.value;
  const minRating = Number(dom.rating.value) || 0;

  filtered = all.filter((product) => {
    if (category && product.category !== category) return false;
    if (minRating && !(product.rating >= minRating)) return false;
    if (query) {
      const haystack = `${product.name} ${product.description || ""}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });

  if (sort.key) {
    const column = COLUMNS.find((c) => c.key === sort.key);
    filtered.sort((a, b) => {
      const x = a[sort.key];
      const y = b[sort.key];
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const result = column?.numeric ? x - y : String(x).localeCompare(String(y), "en");
      return result * sort.dir;
    });
  }

  shown = PAGE_SIZE;
  render();
}

function render() {
  const slice = filtered.slice(0, shown);

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");

  for (const column of COLUMNS) {
    const th = document.createElement("th");
    th.textContent = column.title;
    if (column.sortable) {
      th.classList.add("sortable");
      if (sort.key === column.key) {
        th.classList.add("is-sorted");
        th.textContent = `${column.title} ${sort.dir > 0 ? "↑" : "↓"}`;
      }
      th.addEventListener("click", () => {
        if (sort.key === column.key) sort.dir *= -1;
        else sort = { key: column.key, dir: 1 };
        applyFilters();
      });
    }
    headRow.append(th);
  }
  thead.append(headRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const product of slice) {
    const tr = document.createElement("tr");
    for (const column of COLUMNS) {
      const td = document.createElement("td");
      const value = product[column.key];

      if (column.key === "name") {
        const link = document.createElement("a");
        link.href = product.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = value;
        link.className = "row-link";
        td.append(link);
      } else if (column.key === "price") {
        td.textContent = `£${money(value)}`;
        td.className = "num";
      } else if (value === null || value === undefined || value === "") {
        td.textContent = "—";
        td.className = "empty";
      } else {
        td.textContent = value;
        if (column.numeric) td.className = "num";
      }
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(tbody);

  dom.table.innerHTML = "";
  dom.table.append(table);
  dom.table.hidden = false;

  dom.found.textContent = filtered.length
    ? `Найдено ${filtered.length.toLocaleString("ru-RU")} — показано ${slice.length}`
    : "Ничего не найдено — попробуйте изменить фильтры";
  dom.found.hidden = false;

  dom.moreWrap.hidden = shown >= filtered.length;
}

async function download() {
  if (!filtered.length) return;
  dom.download.disabled = true;
  dom.download.textContent = "Готовлю…";

  try {
    const header = ["Название", "Категория", "Цена", "Валюта", "Рейтинг", "На складе", "Отзывов", "Артикул", "Описание", "Ссылка"];
    const rows = filtered.map((p) => [
      p.name, p.category, p.price, p.currency, p.rating, p.in_stock, p.reviews, p.upc,
      (p.description || "").slice(0, 300), p.url,
    ]);

    const byCategory = new Map();
    for (const product of filtered) {
      const key = product.category || "без категории";
      if (!byCategory.has(key)) byCategory.set(key, []);
      byCategory.get(key).push(product);
    }

    const summary = [["Категория", "Товаров", "Средняя цена", "Мин", "Макс"]];
    for (const name of [...byCategory.keys()].sort((a, b) => a.localeCompare(b, "en"))) {
      const items = byCategory.get(name);
      const prices = items.map((p) => p.price).filter((p) => typeof p === "number");
      summary.push([
        name,
        items.length,
        prices.length ? Math.round((prices.reduce((a, b) => a + b, 0) / prices.length) * 100) / 100 : null,
        prices.length ? Math.min(...prices) : null,
        prices.length ? Math.max(...prices) : null,
      ]);
    }
    summary.push([]);
    summary.push(["Всего товаров", filtered.length]);

    const blob = await writeXlsx([
      { name: "Товары", rows: [header, ...rows] },
      { name: "Сводка", rows: summary },
    ]);

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "каталог.xlsx";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showError(`Не удалось собрать файл: ${error.message}`);
  } finally {
    dom.download.disabled = false;
    dom.download.textContent = "Скачать Excel";
  }
}

let searchTimer = null;
dom.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 180);
});
dom.category.addEventListener("change", applyFilters);
dom.rating.addEventListener("change", applyFilters);
dom.download.addEventListener("click", download);
dom.more.addEventListener("click", () => { shown += PAGE_SIZE; render(); });

(async () => {
  try {
    const response = await fetch("data/catalog.json");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    all = await response.json();
    if (!Array.isArray(all) || !all.length) throw new Error("файл с данными пуст");

    dom.loading.hidden = true;
    dom.controls.hidden = false;
    renderStats();
    fillCategories();
    applyFilters();
  } catch (error) {
    dom.loading.hidden = true;
    showError(`Не удалось загрузить каталог: ${error.message}`);
  }
})();
