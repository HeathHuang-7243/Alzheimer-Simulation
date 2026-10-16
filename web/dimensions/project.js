"use strict";

(() => {
  const scenes = {
    known: {
      title: "沈岚 · 老同事的一次来访",
      background: "退休编辑，喜欢植物，表达谨慎，常先核对安排。",
      scene: "周四午后，旧同事来家中一起翻看一册植物画集。",
      recent: "上周整理过阳台。确切日期未设定，保留‘上周’的说明。",
      relation: "示例中，对话者熟悉原型，角色原本也认识这位旧同事。",
      recognition: "尚未设定，不能因为过去认识就自动回答‘认得’。"
    },
    first: {
      title: "林遥 · 旧书店里的初次会面",
      background: "喜欢旅行随笔，说话温和，习惯先问对方读过什么。",
      scene: "午后在旧书店第一次见面，谈起一本文字与蓝色封面都很熟悉的书。",
      recent: "刚才浏览过书架，并提过蓝色封面。此条是示例设定，不是本页实际发生的经历。",
      relation: "示例不以认识的真人为原型，角色与对话者此前没有共同经历。",
      recognition: "首次会面，不设定已有的熟人关系；若要加入误认，需另行明确个案。"
    }
  };

  function connectTabs(tablist, onSelect) {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    function select(tab, focus) {
      for (const item of tabs) {
        const selected = item === tab;
        item.setAttribute("aria-selected", String(selected));
        item.tabIndex = selected ? 0 : -1;
      }
      onSelect(tab);
      if (focus) tab.focus();
    }
    for (const tab of tabs) {
      tab.addEventListener("click", () => select(tab, false));
      tab.addEventListener("keydown", (event) => {
        const index = tabs.indexOf(tab);
        let next;
        if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        select(tabs[next], true);
      });
    }
  }

  connectTabs(document.querySelector(".mode-tabs"), (tab) => {
    for (const panel of document.querySelectorAll(".mode-panel")) {
      panel.hidden = panel.id !== tab.getAttribute("aria-controls");
    }
  });

  connectTabs(document.querySelector(".scene-tabs"), (tab) => {
    const scene = scenes[tab.dataset.scene];
    for (const key of ["title", "background", "scene", "recent", "relation", "recognition"]) {
      document.querySelector(`#example-${key}`).textContent = scene[key];
    }
    document.querySelector("#scene-example").setAttribute("aria-labelledby", tab.id);
  });

  const prompt = document.querySelector("#starter-prompt");
  const status = document.querySelector("#copy-status");
  document.querySelector("#copy-starter").addEventListener("click", async () => {
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(prompt.value);
      status.textContent = "已复制。请粘贴到能够读写本仓库的模型或 agent 宿主。";
    } catch (_) {
      prompt.focus();
      prompt.select();
      prompt.setSelectionRange(0, prompt.value.length);
      status.textContent = "未能自动复制，指令已选中。请按 Ctrl+C 或 Command+C，或使用设备的复制操作。";
    }
  });
})();
