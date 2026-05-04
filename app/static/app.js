(() => {
  const MD_TITLE = "# Job Search Preferences";

  const SECTION_ORDER = [
    "job_titles",
    "location",
    "work_mode",
    "salary",
    "company_type",
    "must_have",
    "nice_to_have",
    "exclude",
  ];

  const MD_SECTION_HEADING = {
    job_titles: "Job Titles",
    location: "Location",
    work_mode: "Work Mode",
    salary: "Salary",
    company_type: "Company Type",
    must_have: "Must-Have",
    nice_to_have: "Nice-to-Have",
    exclude: "Exclude",
  };

  /** Normalize ## heading text to our internal key */
  const headingToKey = (name) => {
    const n = name.trim().toLowerCase().replace(/\s+/g, " ");
    const map = {
      "job titles": "job_titles",
      location: "location",
      "work mode": "work_mode",
      salary: "salary",
      "company type": "company_type",
      "must-have": "must_have",
      "must have": "must_have",
      "nice-to-have": "nice_to_have",
      "nice to have": "nice_to_have",
      exclude: "exclude",
    };
    return map[n] || null;
  };

  const els = {
    btnSearch: document.getElementById("btn-search"),
    btnPrefs: document.getElementById("btn-prefs"),
    btnReload: document.getElementById("btn-reload"),
    btnDownload: document.getElementById("btn-download"),
    btnHistory: document.getElementById("btn-history"),
    statusBar: document.getElementById("status-bar"),
    loading: document.getElementById("loading"),
    empty: document.getElementById("empty"),
    controls: document.getElementById("controls"),
    results: document.getElementById("results"),
    chips: document.querySelectorAll(".chip"),
    sortBy: document.getElementById("sort-by"),
    modalPrefs: document.getElementById("modal-prefs"),
    modalHistory: document.getElementById("modal-history"),
    historyList: document.getElementById("history-list"),
    prefsMeta: document.getElementById("prefs-meta"),
    prefsExtraWrap: document.getElementById("prefs-extra-wrap"),
    btnSave: document.getElementById("btn-save"),
    btnSaveSearch: document.getElementById("btn-save-search"),
    btnCancel: document.getElementById("btn-cancel"),
    toast: document.getElementById("toast"),
  };

  const prefIds = {
    intro: "pref-intro",
    extra: "pref-extra",
    ...Object.fromEntries(SECTION_ORDER.map((k) => [k, `pref-${k}`])),
  };

  const state = {
    jobs: [],
    filter: "all",
    sort: "best",
    latestCsv: null,
    prefsOriginal: "",
  };

  /* -------- Markdown parse / build -------- */

  function parsePrefsMarkdown(md) {
    const raw = (md || "").replace(/^\uFEFF/, "");
    const data = {
      intro: "",
      extra: "",
    };
    SECTION_ORDER.forEach((k) => {
      data[k] = "";
    });

    let rest = raw;
    const headerMatch = rest.match(/^#\s+Job Search Preferences\s*\r?\n/i);
    if (headerMatch) {
      rest = rest.slice(headerMatch[0].length);
    }

    const bqMatch = rest.match(
      /^((?:>\s?[^\r\n]*(?:\r?\n|$))+)\s*/
    );
    if (bqMatch) {
      data.intro = bqMatch[1]
        .split(/\r?\n/)
        .map((line) => line.replace(/^>\s?/, ""))
        .join("\n")
        .trim();
      rest = rest.slice(bqMatch[0].length);
    }

    const headers = [];
    const re = /^##\s+(.+?)\s*$/gm;
    let m;
    while ((m = re.exec(rest)) !== null) {
      headers.push({
        title: m[1].trim(),
        headerEnd: m.index + m[0].length,
        index: m.index,
      });
    }

    const unknownChunks = [];

    for (let i = 0; i < headers.length; i++) {
      const h = headers[i];
      const bodyStart = h.headerEnd;
      const bodyEnd = i + 1 < headers.length ? headers[i + 1].index : rest.length;
      const body = rest.slice(bodyStart, bodyEnd).trim();
      const key = headingToKey(h.title);
      if (key) {
        data[key] = body;
      } else {
        unknownChunks.push(`## ${h.title}\n\n${body}`);
      }
    }

    if (unknownChunks.length) {
      data.extra = unknownChunks.join("\n\n").trim();
    }

    return data;
  }

  function buildPrefsMarkdown(data) {
    let out = `${MD_TITLE}\n\n`;
    const intro = (data.intro || "").trim();
    if (intro) {
      out +=
        intro
          .split(/\r?\n/)
          .map((line) => "> " + line)
          .join("\n") + "\n\n";
    }

    for (const key of SECTION_ORDER) {
      const title = MD_SECTION_HEADING[key];
      const body = (data[key] || "").trim();
      out += `## ${title}\n\n${body}\n\n`;
    }

    const extra = (data.extra || "").trim();
    if (extra) {
      out += `${extra}\n`;
    }

    out = out.trimEnd();
    if (!out.endsWith("\n")) out += "\n";
    return out;
  }

  function collectFormData() {
    const data = {
      intro: document.getElementById(prefIds.intro).value,
      extra: document.getElementById(prefIds.extra).value,
    };
    SECTION_ORDER.forEach((k) => {
      data[k] = document.getElementById(prefIds[k]).value;
    });
    return data;
  }

  function applyFormData(data) {
    document.getElementById(prefIds.intro).value = data.intro || "";
    document.getElementById(prefIds.extra).value = data.extra || "";
    SECTION_ORDER.forEach((k) => {
      document.getElementById(prefIds[k]).value = data[k] || "";
    });

    const hasExtra = Boolean(data.extra && data.extra.trim());
    els.prefsExtraWrap.classList.toggle("hidden", !hasExtra);
  }

  /* -------- Helpers -------- */

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));

  let toastTimer = null;
  const toast = (message, ms = 2200) => {
    els.toast.textContent = message;
    els.toast.classList.remove("hidden");
    requestAnimationFrame(() => els.toast.classList.add("show"));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      els.toast.classList.remove("show");
      setTimeout(() => els.toast.classList.add("hidden"), 250);
    }, ms);
  };

  const showStatus = (html) => {
    if (!html) {
      els.statusBar.classList.add("hidden");
      els.statusBar.innerHTML = "";
      return;
    }
    els.statusBar.innerHTML = html;
    els.statusBar.classList.remove("hidden");
  };

  const isPrefsDirty = () => {
    const current = buildPrefsMarkdown(collectFormData());
    return current !== state.prefsOriginal;
  };

  const updatePrefsMeta = () => {
    const md = buildPrefsMarkdown(collectFormData());
    const lines = md.split("\n").length;
    const dirty = md !== state.prefsOriginal
      ? " &middot; <strong>unsaved changes</strong>"
      : "";
    els.prefsMeta.innerHTML = `${lines} lines in file &middot; ${md.length} chars${dirty}`;
  };

  /* -------- Filtering & Sorting -------- */

  const matchesFilter = (job, filter) => {
    if (filter === "all") return true;
    const mode = (job.work_mode || "").toLowerCase();
    if (filter === "remote") return mode.includes("remote");
    if (filter === "hybrid") return mode.includes("hybrid");
    if (filter === "nonprofit") return job.is_nonprofit_or_h1b_cap_exempt === true;
    if (filter === "hassalary") return Boolean(job.salary && String(job.salary).trim());
    return true;
  };

  const parseSalaryNumber = (raw) => {
    if (!raw) return -1;
    const matches = String(raw).match(/\$?\s*([\d,]+(?:\.\d+)?)\s*(k|K)?/g);
    if (!matches) return -1;
    let max = -1;
    for (const m of matches) {
      const num = parseFloat(m.replace(/[^\d.]/g, ""));
      if (Number.isNaN(num)) continue;
      const value = /k/i.test(m) && num < 1000 ? num * 1000 : num;
      if (value > max) max = value;
    }
    return max;
  };

  const parseDate = (raw) => {
    if (!raw) return 0;
    const t = Date.parse(raw);
    if (!Number.isNaN(t)) return t;
    const m = String(raw).toLowerCase().match(/(\d+)\s*(day|hour|week|month)/);
    if (m) {
      const n = parseInt(m[1], 10);
      const unit = m[2];
      const ms = { hour: 3.6e6, day: 8.64e7, week: 6.048e8, month: 2.628e9 }[unit] || 0;
      return Date.now() - n * ms;
    }
    return 0;
  };

  const sortJobs = (jobs, mode) => {
    const arr = [...jobs];
    if (mode === "newest") {
      arr.sort((a, b) => parseDate(b.posted) - parseDate(a.posted));
    } else if (mode === "salary") {
      arr.sort((a, b) => parseSalaryNumber(b.salary) - parseSalaryNumber(a.salary));
    }
    return arr;
  };

  /* -------- Rendering -------- */

  const renderCard = (job, idx) => {
    const badges = [];
    if (job.location) badges.push(`<span class="badge location">${esc(job.location)}</span>`);
    if (job.work_mode) badges.push(`<span class="badge work-mode">${esc(job.work_mode)}</span>`);
    if (job.salary) badges.push(`<span class="badge salary">${esc(job.salary)}</span>`);
    if (job.is_nonprofit_or_h1b_cap_exempt === true) {
      badges.push(`<span class="badge nonprofit">Non-profit / H1B-exempt</span>`);
    }

    const posted = job.posted ? `<span class="posted">Posted ${esc(job.posted)}</span>` : "";
    const sourceLine = job.source ? ` &middot; ${esc(job.source)}` : "";

    return `
      <article class="card" data-idx="${idx}">
        <div class="card-head">
          <div>
            <h3>${esc(job.title || "Untitled role")}</h3>
            <div class="company">${esc(job.company || "Unknown employer")}${sourceLine}</div>
          </div>
          ${posted}
        </div>
        <div class="badges">${badges.join("")}</div>
        ${job.why_match ? `<p class="why">${esc(job.why_match)}</p>` : ""}
        <div class="card-actions">
          ${
            job.url
              ? `<a class="btn btn-secondary" href="${esc(job.url)}" target="_blank" rel="noopener">Open posting</a>
                 <button class="btn btn-ghost" data-copy="${esc(job.url)}" type="button">Copy link</button>`
              : `<span class="muted">No link provided</span>`
          }
        </div>
      </article>
    `;
  };

  const render = () => {
    const filtered = state.jobs.filter((j) => matchesFilter(j, state.filter));
    const sorted = sortJobs(filtered, state.sort);

    if (state.jobs.length === 0) {
      els.results.innerHTML = "";
      els.controls.classList.add("hidden");
      return;
    }

    els.controls.classList.remove("hidden");

    if (sorted.length === 0) {
      els.results.innerHTML = `<p class="empty" style="padding:32px;">No jobs match this filter.</p>`;
      return;
    }

    els.results.innerHTML = sorted.map(renderCard).join("");

    els.results.querySelectorAll("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(btn.dataset.copy);
          toast("Link copied");
        } catch {
          toast("Couldn't copy");
        }
      });
    });
  };

  /* -------- API -------- */

  const apiSearch = async () => {
    els.empty.classList.add("hidden");
    els.results.innerHTML = "";
    els.controls.classList.add("hidden");
    els.loading.classList.remove("hidden");
    showStatus("");
    els.btnSearch.disabled = true;

    try {
      const res = await fetch("/api/search", { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || "Search failed");
      }
      const data = await res.json();
      state.jobs = data.jobs || [];
      state.latestCsv = data.csv_filename || null;

      const savedLine = state.latestCsv
        ? ` &middot; Saved to <code>results/${esc(state.latestCsv)}</code>`
        : "";
      showStatus(
        `<strong>${state.jobs.length}</strong> job${state.jobs.length === 1 ? "" : "s"} found in ${data.elapsed_seconds}s using <code>${esc(data.model)}</code>${savedLine}`
      );

      if (state.jobs.length === 0) els.empty.classList.remove("hidden");

      if (state.latestCsv) els.btnDownload.classList.remove("hidden");
      render();
      refreshHistoryList({ silent: true });
    } catch (e) {
      showStatus(`<strong>Search failed:</strong> ${esc(e.message)}`);
    } finally {
      els.loading.classList.add("hidden");
      els.btnSearch.disabled = false;
    }
  };

  const apiGetPrefs = async () => {
    const res = await fetch("/api/preferences");
    const data = await res.json();
    return data.content || "";
  };

  const apiSavePrefs = async (content) => {
    const res = await fetch("/api/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Save failed");
    }
  };

  const apiReloadPrefs = async () => {
    const res = await fetch("/api/preferences/reload", { method: "POST" });
    const data = await res.json();
    return data.content || "";
  };

  const apiListResults = async () => {
    const res = await fetch("/api/results");
    const data = await res.json();
    return data.results || [];
  };

  /* -------- Modals -------- */

  const openPrefsModal = async () => {
    try {
      const content = await apiGetPrefs();
      state.prefsOriginal = content;
      applyFormData(parsePrefsMarkdown(content));
      updatePrefsMeta();
      els.modalPrefs.classList.remove("hidden");
      document.getElementById(prefIds.intro).focus();
    } catch {
      toast("Couldn't load preferences");
    }
  };

  const closePrefsModal = (force = false) => {
    if (!force && isPrefsDirty()) {
      if (!confirm("Discard unsaved changes?")) return;
    }
    els.modalPrefs.classList.add("hidden");
  };

  const openHistoryModal = async () => {
    await refreshHistoryList({ silent: true });
    els.modalHistory.classList.remove("hidden");
  };

  const closeHistoryModal = () => {
    els.modalHistory.classList.add("hidden");
  };

  const savePrefs = async () => {
    const md = buildPrefsMarkdown(collectFormData());
    if (!md.trim()) {
      toast("Preferences can't be empty");
      return false;
    }
    try {
      await apiSavePrefs(md);
      state.prefsOriginal = md;
      applyFormData(parsePrefsMarkdown(md));
      updatePrefsMeta();
      toast("Saved");
      return true;
    } catch (e) {
      toast(e.message);
      return false;
    }
  };

  const renderHistoryItems = (items) => {
    if (!items.length) {
      els.historyList.innerHTML = `<li class="muted" style="padding:12px;">No past runs yet.</li>`;
      return;
    }
    els.historyList.innerHTML = items
      .map(
        (it) => `
        <li class="history-item">
          <div>
            <strong>${esc(it.filename)}</strong>
            <div class="meta">${esc(it.created_at)} &middot; ${it.rows} row${it.rows === 1 ? "" : "s"} &middot; ${(it.size_bytes / 1024).toFixed(1)} KB</div>
          </div>
          <a class="btn btn-secondary" href="/api/results/${encodeURIComponent(it.filename)}" download>Download</a>
        </li>`
      )
      .join("");
  };

  const refreshHistoryList = async ({ silent = false } = {}) => {
    try {
      const items = await apiListResults();
      renderHistoryItems(items);
      if (items.length > 0) els.btnHistory.classList.remove("hidden");
      else els.btnHistory.classList.add("hidden");
    } catch {
      if (!silent) toast("Couldn't load history");
    }
  };

  /* -------- Wiring -------- */

  els.btnSearch.addEventListener("click", apiSearch);
  els.btnPrefs.addEventListener("click", openPrefsModal);

  els.btnReload.addEventListener("click", async () => {
    try {
      const content = await apiReloadPrefs();
      state.prefsOriginal = content;
      if (!els.modalPrefs.classList.contains("hidden")) {
        applyFormData(parsePrefsMarkdown(content));
        updatePrefsMeta();
      }
      toast("Preferences reloaded from disk");
    } catch {
      toast("Reload failed");
    }
  });

  els.btnDownload.addEventListener("click", () => {
    if (!state.latestCsv) return;
    window.location.href = `/api/results/${encodeURIComponent(state.latestCsv)}`;
  });

  els.btnHistory.addEventListener("click", openHistoryModal);

  els.chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      els.chips.forEach((c) => c.classList.remove("is-active"));
      chip.classList.add("is-active");
      state.filter = chip.dataset.filter;
      render();
    });
  });

  els.sortBy.addEventListener("change", (e) => {
    state.sort = e.target.value;
    render();
  });

  els.btnSave.addEventListener("click", async () => {
    const ok = await savePrefs();
    if (ok) closePrefsModal(true);
  });

  els.btnSaveSearch.addEventListener("click", async () => {
    const ok = await savePrefs();
    if (!ok) return;
    closePrefsModal(true);
    apiSearch();
  });

  els.btnCancel.addEventListener("click", () => closePrefsModal(false));

  document.querySelectorAll("[data-close]").forEach((node) => {
    node.addEventListener("click", (e) => {
      const modal = node.getAttribute("data-modal");
      if (modal === "history") closeHistoryModal();
      else if (modal === "prefs") closePrefsModal(false);
    });
  });

  const prefInputs = [
    prefIds.intro,
    prefIds.extra,
    ...SECTION_ORDER.map((k) => prefIds[k]),
  ];
  prefInputs.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", updatePrefsMeta);
  });

  document.addEventListener("keydown", (e) => {
    if (!els.modalHistory.classList.contains("hidden")) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeHistoryModal();
      }
      return;
    }
    if (!els.modalPrefs.classList.contains("hidden")) {
      if (e.key === "Escape") {
        e.preventDefault();
        closePrefsModal(false);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        savePrefs().then((ok) => ok && closePrefsModal(true));
      }
    }
  });

  refreshHistoryList({ silent: true });
})();
