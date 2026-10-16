"use strict";

(() => {
  const state = { data: null, category: "all", query: "", read: new Set(), current: -1, returnTo: null };
  const grid = document.querySelector("#dimension-grid");
  const dialog = document.querySelector("#dimension-dialog");
  const search = document.querySelector("#dimension-search");
  const status = document.querySelector("#results-status");
  const sourceLevels = { sections: "已核对相关章节或图表", abstract: "已核对摘要或图注", webpage: "已核对公开网页", metadata: "仅书目核对" };
  const sourceTypes = { review: "综述", consensus: "共识框架", consensus_classification: "分类共识", official_health_information: "官方公众资料", original_rct: "随机试验", original_human_observational: "人体观察或任务研究", webpage: "公众资料", official_webpage: "公众资料" };
  const icons = {
    memory: "M5 6h7a4 4 0 0 1 4 4v9M5 6v13h7a4 4 0 0 1 4 3V10a4 4 0 0 1 4-4h7v13h-7a4 4 0 0 0-4 3M8 10h3m-3 4h3m10-4h3m-3 4h3",
    attention: "M16 5v4m0 14v4M5 16h4m14 0h4M10 10l3 3m6 6 3 3m0-12-3 3m-6 6-3 3M16 12a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
    communication: "M5 7h22v15H16l-7 5v-5H5V7Zm5 5h12m-12 5h8",
    executive: "M9 5h14v6H9V5Zm7 6v5M7 22h6v6H7v-6Zm12 0h6v6h-6v-6M10 22v-6h12v6",
    perception: "M3 16s5-8 13-8 13 8 13 8-5 8-13 8S3 16 3 16Zm13-4a4 4 0 1 0 0 8 4 4 0 0 0 0-8",
    personality: "M16 4a6 6 0 1 0 0 12 6 6 0 0 0 0-12M6 28v-3a10 10 0 0 1 20 0v3M23 5l3-2m1 9h3M2 12h3m1-7L3 3",
    affect: "M16 27S4 20 4 12a6 6 0 0 1 12-2 6 6 0 0 1 12 2c0 8-12 15-12 15ZM11 16h3l2-4 2 8 2-4h3",
    motivation: "M8 25 17 4l-1 10h9L13 29l3-11H7M4 8h4m17 17h4",
    social: "M11 6a4 4 0 1 0 0 8 4 4 0 0 0 0-8m11 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6M3 27v-3a8 8 0 0 1 16 0v3m2-8a6 6 0 0 1 8 6v2",
    self: "M12 5h12v23H12M8 9H5v15h3M18 10a3 3 0 1 0 0 6 3 3 0 0 0 0-6m-5 10v-2a5 5 0 0 1 10 0v2",
    autonomy: "M4 26h24M7 26V15h5v11m4 0V9h5v17m-5-20 6-4 6 4M24 2v15",
    experience: "M16 5a11 11 0 1 0 0 22 11 11 0 0 0 0-22M11 13h.1m9.9 0h.1M10 19s2 4 6 4 6-4 6-4"
  };

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(id) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 32 32");
    svg.setAttribute("class", "dimension-icon");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", icons[id] || icons.memory);
    svg.append(path);
    return svg;
  }

  function externalLink(text, href, className) {
    const url = new URL(href);
    if (url.protocol !== "https:") throw new Error("Unsupported evidence URL");
    const link = element("a", className, text);
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.append(element("span", "sr-only", "（新窗口）"));
    return link;
  }

  function filteredDimensions() {
    if (!state.data) return [];
    return state.data.dimensions.filter((dimension) => {
      const inCategory = state.category === "all" || dimension.category === state.category;
      const searchable = [dimension.title, dimension.english, dimension.summary, dimension.normal, dimension.example, dimension.simulation, ...dimension.questions].join(" ").toLocaleLowerCase();
      return inCategory && (!state.query || searchable.includes(state.query));
    });
  }

  function renderCards() {
    if (!state.data) return;
    const dimensions = filteredDimensions();
    const fragment = document.createDocumentFragment();
    for (const dimension of dimensions) {
      const card = element("article", "dimension-card");
      card.dataset.category = dimension.category;
      card.setAttribute("aria-labelledby", `card-title-${dimension.id}`);
      const button = element("button", "card-button");
      button.type = "button";
      button.dataset.dimension = dimension.id;
      button.setAttribute("aria-haspopup", "dialog");
      const top = element("span", "card-topline");
      top.append(element("span", "card-number", dimension.number), element("span", "card-category", state.data.categories[dimension.category]));
      const title = element("span", "card-title");
      title.id = `card-title-${dimension.id}`;
      title.append(icon(dimension.id), element("span", "", dimension.title));
      const bottom = element("span", "card-bottomline");
      bottom.append(element("span", state.read.has(dimension.id) ? "read-indicator" : "", state.read.has(dimension.id) ? "✓ 本次已读" : "机制 · 日常 · 设定"), element("span", "card-arrow", "↗"));
      bottom.lastChild.setAttribute("aria-hidden", "true");
      button.append(top, title, element("span", "card-summary", dimension.summary), bottom);
      button.addEventListener("click", () => openDimension(dimension.id));
      card.append(button);
      fragment.append(card);
    }
    grid.replaceChildren(fragment);
    document.querySelector("#empty-state").hidden = dimensions.length !== 0;
    const category = state.category === "all" ? "全部维度" : state.data.categories[state.category];
    status.textContent = `${category} · 显示 ${dimensions.length} 个维度${state.query ? ` · 搜索“${search.value.trim()}”` : " · 点击卡片展开阅读"}`;
  }

  function detailSection(title, text, className) {
    const section = element("section", "detail-section");
    const heading = element("h3");
    heading.append(element("span", "section-marker"), document.createTextNode(title));
    heading.firstChild.setAttribute("aria-hidden", "true");
    section.append(heading, element("p", className || "", text));
    return section;
  }

  function renderDetail() {
    const dimension = state.data.dimensions[state.current];
    if (!dimension) return;
    const content = document.querySelector("#dialog-content");
    const title = element("h2", "dialog-title", dimension.title);
    title.id = "dialog-title";
    title.tabIndex = -1;
    const simulation = detailSection("用于 AD 角色模拟时", dimension.simulation);
    simulation.append(element("p", "simulation-boundary", dimension.boundary));
    const questions = element("section", "optional-questions");
    questions.append(element("h3", "", "如果愿意，可以补充这些设定"));
    const questionList = element("ul");
    for (const question of dimension.questions) questionList.append(element("li", "", question));
    questions.append(questionList, element("p", "", "这些问题在后续对话中回答即可，本页不收集答案。也可以全部跳过：启动流程会补齐带来源标记的虚构背景，之后仍可编辑。"));
    const evidence = element("details", "evidence-details");
    evidence.append(element("summary", "", `依据与边界 · ${dimension.references.length} 条证据卡`));
    evidence.append(element("p", "evidence-caveat", dimension.evidence_note));
    const sources = element("ul", "source-list");
    for (const reference of dimension.references) {
      const source = state.data.sources[reference];
      const row = element("li");
      row.append(element("span", "source-ref", `${reference} · ${source.year} · ${sourceTypes[source.source_type] || "研究资料"}`));
      row.append(externalLink(source.title + " ↗", source.evidence_card));
      row.append(element("span", "source-note", sourceLevels[source.verification_level] || "阅读范围见证据卡"));
      sources.append(row);
    }
    evidence.append(sources, externalLink("查看本维度的完整模拟定义 ↗", dimension.definition_url, "text-button definition-link"));
    content.replaceChildren(element("p", "dialog-eyebrow", `${dimension.number} / 12 · ${dimension.english}`), title, element("p", "dialog-summary", dimension.summary), detailSection("正常机制 · 功能说明", dimension.normal), detailSection("生活里的例子", dimension.example, "everyday-example"), simulation, questions, evidence);
    document.querySelector("#dialog-position").textContent = `${state.data.categories[dimension.category]} / ${dimension.number} — 12`;
    document.querySelector("#previous-dimension").disabled = state.current === 0;
    document.querySelector("#next-dimension").disabled = state.current === state.data.dimensions.length - 1;
    updateReadButton();
    dialog.scrollTop = 0;
  }

  function openDimension(id) {
    state.current = state.data.dimensions.findIndex((dimension) => dimension.id === id);
    if (state.current < 0) return;
    if (!dialog.open) state.returnTo = id;
    renderDetail();
    if (!dialog.open) {
      dialog.showModal();
      document.body.classList.add("dialog-open");
    }
    document.querySelector("#dialog-title").focus({ preventScroll: true });
  }

  function updateReadButton() {
    const current = state.data.dimensions[state.current];
    const button = document.querySelector("#mark-read");
    const isRead = state.read.has(current.id);
    button.setAttribute("aria-pressed", String(isRead));
    button.replaceChildren(document.createTextNode(isRead ? "已读 · 点击撤销" : "标记已读"), element("span", "", "✓"));
    button.lastChild.setAttribute("aria-hidden", "true");
  }

  function updateProgress() {
    document.querySelector("#read-count").textContent = state.read.size;
    document.querySelector("#progress-fill").style.width = `${state.read.size / 12 * 100}%`;
    document.querySelector(".progress-track").setAttribute("aria-valuenow", String(state.read.size));
  }

  function selectCategory(category) {
    state.category = category;
    for (const button of document.querySelectorAll("[data-category].filter-button")) {
      const active = button.dataset.category === category;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
    renderCards();
  }

  function validateContent(data) {
    const ids = Object.keys(icons);
    if (!data || data.schema_version !== 1 || !Array.isArray(data.dimensions) || data.dimensions.length !== 12) throw new Error("Invalid content");
    if (new Set(data.dimensions.map((dimension) => dimension.id)).size !== 12) throw new Error("Duplicate dimension");
    for (const dimension of data.dimensions) {
      if (!ids.includes(dimension.id) || !data.categories[dimension.category] || !Array.isArray(dimension.questions) || !Array.isArray(dimension.references)) throw new Error("Invalid dimension");
      for (const key of ["number", "title", "english", "summary", "normal", "example", "simulation", "boundary", "evidence_note", "definition_url"]) {
        if (typeof dimension[key] !== "string" || !dimension[key].trim()) throw new Error("Missing content");
      }
      for (const reference of dimension.references) {
        if (!data.sources[reference] || !data.sources[reference].evidence_card) throw new Error("Missing source");
      }
    }
  }

  async function loadContent() {
    document.querySelector("#load-error").hidden = true;
    status.textContent = "正在准备十二个维度…";
    try {
      const response = await fetch("./dimensions.json", { credentials: "omit", cache: "no-cache" });
      if (!response.ok) throw new Error("Content unavailable");
      const data = await response.json();
      validateContent(data);
      state.data = data;
      renderCards();
    } catch (_) {
      status.textContent = "内容暂未加载。";
      document.querySelector("#load-error").hidden = false;
    }
  }

  document.querySelectorAll(".filter-button").forEach((button) => button.addEventListener("click", () => selectCategory(button.dataset.category)));
  search.addEventListener("input", () => {
    state.query = search.value.trim().toLocaleLowerCase();
    renderCards();
  });
  document.querySelector("#clear-filters").addEventListener("click", () => {
    search.value = "";
    state.query = "";
    selectCategory("all");
    search.focus();
  });
  document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("dialog-open");
    const opener = grid.querySelector(`[data-dimension="${state.returnTo}"]`);
    if (opener) opener.focus({ preventScroll: true });
  });
  document.querySelector("#previous-dimension").addEventListener("click", () => {
    if (state.current > 0) openDimension(state.data.dimensions[state.current - 1].id);
  });
  document.querySelector("#next-dimension").addEventListener("click", () => {
    if (state.current < state.data.dimensions.length - 1) openDimension(state.data.dimensions[state.current + 1].id);
  });
  document.querySelector("#mark-read").addEventListener("click", () => {
    const current = state.data.dimensions[state.current];
    if (state.read.has(current.id)) state.read.delete(current.id);
    else state.read.add(current.id);
    updateReadButton();
    updateProgress();
    renderCards();
    document.querySelector("#reader-announcement").textContent = `${current.title}${state.read.has(current.id) ? "已标记为已读" : "已取消已读标记"}，当前共 ${state.read.size} 个维度已读。`;
  });
  document.querySelector("#retry-load").addEventListener("click", loadContent);
  loadContent();
})();
