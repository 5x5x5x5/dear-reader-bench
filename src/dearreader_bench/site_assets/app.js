(() => {
  const dataEl = document.getElementById("drb-data");
  if (!dataEl) return;
  const DATA = JSON.parse(dataEl.textContent);

  const esc = (s) =>
    String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");

  const shortSys = (id) => {
    const parts = id.split("/");
    return parts.length > 1 ? parts[1].replace(":free", "") : id;
  };

  // ---------- Theme Toggle ----------
  const themeBtn = document.getElementById("theme-toggle");
  const savedTheme = localStorage.getItem("drb-theme");
  if (savedTheme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  }
  const syncThemeLabel = () => {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    if (themeBtn) themeBtn.textContent = isLight ? "Dark Velvet" : "Archival Paper";
  };
  syncThemeLabel();
  themeBtn?.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    if (next === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.removeAttribute("data-theme");
    localStorage.setItem("drb-theme", next);
    syncThemeLabel();
  });

  // ---------- Hero Spotlight (live showcase of s2-005: His Honor the Goat) ----------
  const spotlightSeg =
    DATA.segments.find((s) => s.id === "s2-005") || DATA.segments[0];
  const subs = DATA.submissions;
  const spotTabs = document.getElementById("spotlight-tabs");
  const spotTr = document.getElementById("spotlight-tr");
  const spotMeterFill = document.getElementById("spotlight-meter-fill");
  const spotMeterText = document.getElementById("spotlight-meter-text");

  function renderSpotlight(sysId) {
    const sub = subs.find((s) => s.system === sysId) || subs[0];
    if (!sub || !spotlightSeg) return;
    const seg = sub.segments[spotlightSeg.id];
    if (spotTr) spotTr.textContent = seg ? seg.text : "";
    const ratio = seg ? seg.fill_ratio : 0;
    const pct = Math.min(100, Math.round((ratio / 1.5) * 100));
    if (spotMeterFill) {
      spotMeterFill.style.width = `${pct}%`;
      spotMeterFill.className =
        "meter-fill" + (ratio >= 1.5 ? " forfeit" : ratio > 1.1 ? " warn" : "");
    }
    if (spotMeterText) {
      spotMeterText.textContent = `est. ${seg.est_seconds.toFixed(1)}s / ${spotlightSeg.seconds}s (${Math.round(ratio * 100)}% fill)`;
    }
    spotTabs?.querySelectorAll(".chip").forEach((el) => {
      el.classList.toggle("active", el.dataset.sys === sub.system);
    });
  }

  if (spotTabs && subs.length) {
    const featured = subs.slice(0, 6);
    spotTabs.innerHTML = featured
      .map(
        (s, i) =>
          `<button class="chip ${i === 0 ? "active" : ""}" data-sys="${esc(s.system)}">${esc(shortSys(s.system))}</button>`
      )
      .join("");
    spotTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip");
      if (btn) renderSpotlight(btn.dataset.sys);
    });
    renderSpotlight(featured[0].system);
  }

  // ---------- Screening Room (Interactive 48-Segment Comparison Stage) ----------
  const gagFilter = document.getElementById("filter-gag");
  const featFilter = document.getElementById("filter-feature");
  const filmstrip = document.getElementById("filmstrip");
  const selA = document.getElementById("select-sys-a");
  const selB = document.getElementById("select-sys-b");
  const stageSource = document.getElementById("stage-source");
  const stageCards = document.getElementById("stage-cards");
  const stageCompare = document.getElementById("stage-compare");

  let activeSegId = DATA.segments[0]?.id || "";
  let activeCardId = null;

  if (gagFilter) {
    Object.entries(DATA.corpus.gags).forEach(([gid, phrase]) => {
      const opt = document.createElement("option");
      opt.value = gid;
      opt.textContent = `${gid} — "${phrase}"`;
      gagFilter.appendChild(opt);
    });
  }

  const allFeatures = [...new Set(DATA.segments.flatMap((s) => s.features))].sort();
  if (featFilter) {
    allFeatures.forEach((f) => {
      const opt = document.createElement("option");
      opt.value = f;
      opt.textContent = f.replaceAll("_", " ");
      featFilter.appendChild(opt);
    });
  }

  if (selA && selB && subs.length) {
    const opts = subs
      .map((s) => `<option value="${esc(s.system)}">${esc(s.system)}</option>`)
      .join("");
    selA.innerHTML = opts;
    selB.innerHTML = opts;
    const defaultA =
      subs.find((s) => s.system.includes("gemini"))?.system || subs[0].system;
    const defaultB =
      subs.find((s) => s.system.includes("claude"))?.system ||
      subs[Math.min(1, subs.length - 1)].system;
    selA.value = defaultA;
    selB.value = defaultB;
  }

  function filteredSegments() {
    const g = gagFilter?.value || "";
    const f = featFilter?.value || "";
    return DATA.segments.filter(
      (s) => (!g || s.gag_id === g) && (!f || s.features.includes(f))
    );
  }

  function highlightSource(text, card) {
    let html = esc(text);
    if (!card) return html;
    const setup = esc(card.setup_span);
    const punch = esc(card.punchline_span);
    if (setup && html.includes(setup)) {
      html = html.replace(setup, `<mark class="hl-setup">${setup}</mark>`);
    }
    if (punch && html.includes(punch)) {
      html = html.replace(punch, `<mark class="hl-punch">${punch}</mark>`);
    }
    return html;
  }

  function highlightBible(text, tokens) {
    let html = esc(text);
    const uniq = [...new Set(tokens.filter((t) => t && t.length >= 2))].sort(
      (a, b) => b.length - a.length
    );
    for (const tok of uniq) {
      const e = esc(tok);
      if (html.includes(e)) {
        html = html.replaceAll(e, `<mark class="hl-bible">${e}</mark>`);
      }
    }
    return html;
  }

  function renderFilmstrip() {
    const list = filteredSegments();
    if (!list.some((s) => s.id === activeSegId) && list.length) {
      activeSegId = list[0].id;
      activeCardId = null;
    }
    if (!filmstrip) return;
    filmstrip.innerHTML = list
      .map(
        (s) => `
        <button class="frame-pill ${s.id === activeSegId ? "active" : ""}" data-seg="${esc(s.id)}">
          <span>${esc(s.id)}</span>
          <span class="frame-sec">${s.seconds}s${s.gag_id ? " · gag" : ""}</span>
        </button>`
      )
      .join("");
    renderStage();
  }

  function renderStage() {
    const seg = DATA.segments.find((s) => s.id === activeSegId);
    if (!seg) return;
    const cards = DATA.cards.filter((c) => c.segment_id === seg.id);
    if (!cards.some((c) => c.joke_id === activeCardId)) {
      activeCardId = cards[0]?.joke_id || null;
    }
    const activeCard = cards.find((c) => c.joke_id === activeCardId) || null;

    if (stageSource) {
      const featBadges = seg.features
        .map((f) => `<span class="badge badge-blind">${esc(f.replaceAll("_", " "))}</span>`)
        .join(" ");
      const gagBadge = seg.gag_id
        ? `<span class="badge badge-warn">arc: ${esc(seg.gag_id)}</span>`
        : "";
      stageSource.innerHTML = `
        <div class="panel-title">
          <h3>${esc(seg.id)} <span class="mono" style="font-size:0.85rem;color:var(--brass)">${seg.seconds}s window</span></h3>
          <span class="mono" style="font-size:0.76rem;color:var(--ink-muted)">EN source ${Math.round(seg.source_fill_ratio * 100)}% fill</span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px">${gagBadge} ${featBadges}</div>
        <p class="spotlight-scene">${esc(seg.scene)}</p>
        <div class="source-box">${highlightSource(seg.text, activeCard)}</div>
      `;
    }

    if (stageCards) {
      stageCards.innerHTML = cards
        .map(
          (c) => `
          <div class="joke-card ${c.joke_id === activeCardId ? "active" : ""}" data-card="${esc(c.joke_id)}">
            <div class="joke-card-head">
              <span class="mech-tag">${esc(c.mechanism.replaceAll("_", " "))}</span>
              <span class="opp-tag">${esc(c.script_opposition[0])} × ${esc(c.script_opposition[1])}</span>
              <span class="badge ${c.portable ? "badge-ok" : "badge-aware"}">${c.portable ? "portable" : "non-portable pun"}</span>
            </div>
            <div class="joke-spans">
              <strong>Setup:</strong> ${esc(c.setup_span)} · <strong>Punchline:</strong> ${esc(c.punchline_span)}
            </div>
          </div>`
        )
        .join("");
    }

    if (stageCompare && subs.length) {
      const chosen = [selA?.value, selB?.value]
        .map((id) => subs.find((s) => s.system === id))
        .filter(Boolean);
      const matchedNames = DATA.corpus.names.filter((n) =>
        seg.text.toLowerCase().includes(n.toLowerCase())
      );
      stageCompare.innerHTML = chosen
        .map((sub, idx) => {
          const item = sub.segments[seg.id];
          const ratio = item ? item.fill_ratio : 0;
          const pct = Math.min(100, Math.round((ratio / 1.5) * 100));
          const bibleTokens = [];
          const bibleBadges = [];
          matchedNames.forEach((n) => {
            const ren = sub.bible.names[n];
            if (ren) {
              bibleTokens.push(ren);
              bibleBadges.push(`<span class="badge badge-warn">${esc(n)} → ${esc(ren)}</span>`);
            }
          });
          if (seg.gag_id && sub.bible.gag_anchors[seg.gag_id]) {
            const ga = sub.bible.gag_anchors[seg.gag_id];
            bibleTokens.push(ga);
            bibleBadges.push(`<span class="badge badge-ok">gag: ${esc(ga)}</span>`);
          }
          const roleBadge = sub.system.endsWith("+literal")
            ? '<span class="badge badge-blind">literal anchor</span>'
            : sub.system.endsWith("+rewrite")
              ? '<span class="badge badge-aware">rewrite anchor</span>'
              : "";
          return `
            <div class="cand-card">
              <div class="cand-head">
                <span class="cand-name">${idx === 0 ? "A · " : "B · "}${esc(sub.system)}</span>
                ${roleBadge}
              </div>
              <div class="cand-bible-hits">${bibleBadges.join("")}</div>
              <p class="cand-text">${highlightBible(item?.text || "", bibleTokens)}</p>
              <div class="meter-row">
                <div class="meter-track"><div class="meter-fill ${ratio >= 1.5 ? "forfeit" : ratio > 1.1 ? "warn" : ""}" style="width:${pct}%"></div></div>
                <span>${item ? item.est_seconds.toFixed(1) : "0"}s / ${seg.seconds}s (${Math.round(ratio * 100)}%)</span>
              </div>
            </div>`;
        })
        .join("");
    }
  }

  filmstrip?.addEventListener("click", (e) => {
    const pill = e.target.closest(".frame-pill");
    if (!pill) return;
    activeSegId = pill.dataset.seg;
    activeCardId = null;
    renderFilmstrip();
  });

  stageCards?.addEventListener("click", (e) => {
    const card = e.target.closest(".joke-card");
    if (!card) return;
    activeCardId = card.dataset.card;
    renderStage();
  });

  gagFilter?.addEventListener("change", renderFilmstrip);
  featFilter?.addEventListener("change", renderFilmstrip);
  selA?.addEventListener("change", renderStage);
  selB?.addEventListener("change", renderStage);
  renderFilmstrip();

  // ---------- Bible Wall Tabs ----------
  const bibleTabBar = document.getElementById("bible-tabs");
  const bibleContent = document.getElementById("bible-content");

  function renderBibleTab(mode) {
    bibleTabBar?.querySelectorAll(".chip").forEach((el) => {
      el.classList.toggle("active", el.dataset.tab === mode);
    });
    if (!bibleContent) return;

    if (mode === "notes") {
      bibleContent.innerHTML = `<div class="notes-grid">${subs
        .map(
          (s) => `
          <div class="note-card">
            <h4>${esc(s.system)}</h4>
            <p>${esc(s.bible.register_note || "—")}</p>
          </div>`
        )
        .join("")}</div>`;
      return;
    }

    const keys =
      mode === "names"
        ? DATA.corpus.names.map((n) => [n, n])
        : Object.entries(DATA.corpus.gags).map(([gid, phr]) => [gid, `${gid} ("${phr}")`]);

    const headCols = subs.map((s) => `<th>${esc(shortSys(s.system))}</th>`).join("");
    const rows = keys
      .map(([key, label]) => {
        const cells = subs
          .map((s) => {
            const map = mode === "names" ? s.bible.names : s.bible.gag_anchors;
            return `<td class="jp-cell">${esc(map[key] || "—")}</td>`;
          })
          .join("");
        return `<tr><td><strong>${esc(label)}</strong></td>${cells}</tr>`;
      })
      .join("");
    bibleContent.innerHTML = `
      <div class="table-scroll">
        <table class="data-table">
          <thead><tr><th>Source ${mode === "names" ? "Epithet" : "Running Gag"}</th>${headCols}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  bibleTabBar?.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (btn) renderBibleTab(btn.dataset.tab);
  });
  renderBibleTab("names");

  // ---------- Copy Buttons ----------
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy || "";
      try {
        await navigator.clipboard.writeText(text);
        const orig = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => {
          btn.textContent = orig;
        }, 1200);
      } catch {
        btn.textContent = "Select & copy";
      }
    });
  });
})();
