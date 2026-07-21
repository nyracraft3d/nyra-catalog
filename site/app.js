const MAIN = ["Anime", "Oyun", "Film-Dizi", "DC", "Marvel"];
const SUBS = ["Tüm Oyunlar", "League of Legends", "World of Warcraft", "Diğer Oyunlar"];
const ICONS = {
  Anime: "🎌",
  Oyun: "🎮",
  "Film-Dizi": "🎬",
  DC: "🦇",
  Marvel: "🦸"
};

const s = {
  items: [],
  main: null,
  sub: "Tüm Oyunlar",
  q: "",
  searchMode: false
};

const $ = selector => document.querySelector(selector);
const norm = value => (value || "").toLocaleLowerCase("tr-TR");

async function init() {
  s.items = await (await fetch("data/catalog.json", { cache: "no-store" })).json();
  renderCats();
  renderSubs();
  updateSearchLayout();
  render();
}

function countMain(category) {
  return s.items.filter(item => item.mainCategory === category).length;
}

function countSub(category) {
  const games = s.items.filter(item => item.mainCategory === "Oyun");

  if (category === "Tüm Oyunlar") return games.length;

  if (category === "Diğer Oyunlar") {
    return games.filter(item =>
      !["League of Legends", "World of Warcraft"].includes(item.gameGroup)
    ).length;
  }

  return games.filter(item => item.gameGroup === category).length;
}

function renderCats() {
  $("#mainCategories").innerHTML = MAIN.map(category => `
    <article class="category-card" data-c="${category}">
      <div class="icon">${ICONS[category]}</div>
      <div>
        <h3>${category}</h3>
        <span>${countMain(category)} figür</span>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".category-card").forEach(card => {
    card.onclick = () => {
      s.main = card.dataset.c;
      s.sub = "Tüm Oyunlar";
      s.searchMode = false;
      $("#gameSubs").hidden = s.main !== "Oyun";
      renderSubs();
      updateSearchLayout();
      render();
      $(".catalog").scrollIntoView({ behavior: "smooth", block: "start" });
    };
  });
}

function renderSubs() {
  $("#gameSubChips").innerHTML = SUBS.map(category => `
    <button class="chip ${s.sub === category ? "active" : ""}" data-s="${category}">
      ${category} (${countSub(category)})
    </button>
  `).join("");

  document.querySelectorAll(".chip").forEach(chip => {
    chip.onclick = () => {
      s.sub = chip.dataset.s;
      renderSubs();
      render();
    };
  });
}

function list() {
  const query = norm(s.q);

  return s.items.filter(item => {
    let matchesCategory = !s.main || item.mainCategory === s.main;

    if (matchesCategory && s.main === "Oyun") {
      if (s.sub === "League of Legends") {
        matchesCategory = item.gameGroup === "League of Legends";
      } else if (s.sub === "World of Warcraft") {
        matchesCategory = item.gameGroup === "World of Warcraft";
      } else if (s.sub === "Diğer Oyunlar") {
        matchesCategory = !["League of Legends", "World of Warcraft"].includes(item.gameGroup);
      }
    }

    const searchableText = norm([
      item.id,
      item.name,
      item.mainCategory,
      item.universe,
      item.gameGroup,
      ...(item.tags || [])
    ].join(" "));

    return matchesCategory && (!query || searchableText.includes(query));
  });
}

function render() {
  const items = list();
  let title = s.main || "Tüm Figürler";
  let breadcrumb = s.main || "Tüm Katalog";

  if (s.main === "Oyun" && s.sub !== "Tüm Oyunlar") {
    breadcrumb = "Oyun";
    title = s.sub;
  }

  if (s.q) {
    breadcrumb = "Arama Sonucu";
    title = `“${s.q}”`;
  }

  $("#breadcrumb").textContent = breadcrumb;
  $("#resultsTitle").textContent = title;
  $("#resultCount").textContent = `${items.length} figür`;
  $("#emptyState").hidden = items.length !== 0;

  $("#catalogGrid").innerHTML = items.map(item => `
    <article class="card" data-id="${item.id}">
      <img src="${item.cover}" loading="lazy" onerror="this.src='assets/placeholder.svg'">
      <div>
        <span>${item.universe} · ${item.id}</span>
        <h3>${item.name}</h3>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".card").forEach(card => {
    card.onclick = () => openModal(s.items.find(item => item.id === card.dataset.id));
  });
}

function openModal(item) {
  if (!item) return;

  $("#modalImage").src = item.cover;
  $("#modalTitle").textContent = item.name;
  $("#modalUniverse").textContent = `${item.universe} · ${item.id}`;

  const extras = [item.scale, item.height].filter(Boolean).join(" · ");
  $("#modalDescription").textContent =
    (extras ? `${extras}\n\n` : "") +
    (item.description || "Bu model sipariş üzerine Nyra Craft atölyesinde üretilip elde boyanabilir.");

  const gallery = [item.cover, ...(item.images || [])];
  $("#gallery").innerHTML = [...new Set(gallery)]
    .map(image => `<img src="${image}">`)
    .join("");

  document.querySelectorAll("#gallery img").forEach(image => {
    image.onclick = () => {
      $("#modalImage").src = image.src;
    };
  });

  $("#modal").showModal();
}

const stickySearch = $("#stickySearchInput");
const heroSearch = $("#searchInput");

function updateSearchLayout() {
  $("#categorySection").hidden = s.searchMode;
  $("#searchReturn").hidden = !s.searchMode;

  if (s.searchMode) {
    $("#gameSubs").hidden = true;
  } else {
    $("#gameSubs").hidden = s.main !== "Oyun";
  }
}

function enterSearchMode({ scroll = true } = {}) {
  s.searchMode = true;
  updateSearchLayout();

  if (scroll) {
    requestAnimationFrame(() => {
      $(".catalog").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}

function leaveSearchMode({ clear = true, scroll = true } = {}) {
  s.searchMode = false;

  if (clear) {
    s.q = "";
    if (heroSearch) heroSearch.value = "";
    if (stickySearch) stickySearch.value = "";
  }

  updateSearchLayout();
  render();

  if (scroll) {
    requestAnimationFrame(() => {
      $("#categorySection").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }
}

function syncSearch(value) {
  s.q = value;

  if (heroSearch && heroSearch.value !== value) {
    heroSearch.value = value;
  }

  if (stickySearch && stickySearch.value !== value) {
    stickySearch.value = value;
  }

  // Arama sırasında sayfayı otomatik kaydırma.
  // Böylece kullanıcı yazdığı metni ekranda görmeye devam eder.
  enterSearchMode({ scroll: false });
  render();
}

if (heroSearch) {
  heroSearch.onfocus = () => enterSearchMode({ scroll: false });
  heroSearch.oninput = event => syncSearch(event.target.value);
}

if (stickySearch) {
  stickySearch.onfocus = () => enterSearchMode({ scroll: false });
  stickySearch.oninput = event => syncSearch(event.target.value);
}

$("#clearSearch").onclick = () => leaveSearchMode({ clear: true, scroll: true });
$("#clearStickySearch").onclick = () => leaveSearchMode({ clear: true, scroll: true });
$("#showCategoriesButton").onclick = () => leaveSearchMode({ clear: true, scroll: true });

$("#backButton").onclick = () => {
  s.main = null;
  s.sub = "Tüm Oyunlar";
  $("#gameSubs").hidden = true;
  render();
};

$("#homeLink").onclick = event => {
  event.preventDefault();
  s.main = null;
  s.sub = "Tüm Oyunlar";
  leaveSearchMode({ clear: true, scroll: false });
  scrollTo({ top: 0, behavior: "smooth" });
};

$("#closeModal").onclick = () => $("#modal").close();
$("#modal").onclick = event => {
  if (event.target === $("#modal")) {
    $("#modal").close();
  }
};

init();
