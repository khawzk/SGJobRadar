async function loadDashboard() {
  const response = await fetch("../data/latest.json");
  if (!response.ok) return;

  const data = await response.json();
  renderHeader(data);
  renderSignal(data);
  renderKpis(data);
  renderLineChart(data.trend_series || {});
  renderBars("#demand-chart", data.demand_clusters || [], "index");
  renderSkillGroups(data.skill_groups || []);
  renderHeatmap(data.top_skills || []);
  renderAnalysis(data);
  renderEvidence(data.evidence_examples || []);
  renderDeepDive(data.deep_dive_recommendations || []);
  renderMethodology(data.methodology || {});
  renderMiniList("#role-chart", data.top_roles || []);
  renderProjects(data.project_recommendations || []);
  document.querySelector("#source-note").textContent = data.source_note || "";
}

function renderHeader(data) {
  document.querySelector("#snapshot-label").textContent = `Snapshot ${snapshotDate(data)}`;
}

function renderSignal(data) {
  const topCluster = data.demand_clusters?.[0];
  const topSkill = data.top_skills?.[0];
  const baseline = data.comparison?.has_previous_week
    ? `Compared with ${data.comparison.previous_week_start}`
    : `Trend comparison starts after the next scheduled snapshot.`;

  document.querySelector("#signal-title").textContent = titleCase(topCluster?.name || "Collecting signal");
  document.querySelector("#signal-copy").textContent =
    `${titleCase(topCluster?.name || "This area")} is the strongest tracked hiring topic in SG tech. ${baseline}`;
}

function renderKpis(data) {
  const overview = data.overview || {};
  const topCluster = data.demand_clusters?.[0];
  const topSkill = data.top_skills?.[0];
  const topGroup = data.skill_groups?.[0];
  const kpis = [
    ["Jobs analyzed", formatNumber(overview.sampled_jobs || overview.total_jobs || 0), `Postings read on ${snapshotDate(data)}`],
    ["Demand index", formatNumber(overview.market_matches || 0), "Relative signal across tracked topics"],
    ["Hottest topic", titleCase(topCluster?.name || "-"), "Highest tracked demand"],
    ["Top skillset", topGroup?.name || "-", `${topGroup?.total_mentions || 0} grouped mentions`],
  ];

  document.querySelector("#kpis").innerHTML = kpis.map(([label, value, note]) => `
    <div class="kpi-card">
      <span>${label}</span>
      <strong>${value}</strong>
      <small>${note}</small>
    </div>
  `).join("");
}

function renderLineChart(series) {
  const sampled = series.sampled_jobs || [];
  const market = series.market_matches || [];
  const ai = series.ai_data || [];
  const cloud = series.cloud_devops || [];
  const element = document.querySelector("#trend-lines");
  if (!element) return;

  element.innerHTML = `
    <div class="line-chart">
      ${lineSvg(sampled, "Jobs analyzed", "#25d8ff")}
      ${lineSvg(market, "Demand index", "#e044ff")}
      ${lineSvg(ai, "AI & Data", "#31f6a1")}
      ${lineSvg(cloud, "Cloud & DevOps", "#f8c14a")}
    </div>
    <p class="chart-note">Trend preview only. Real comparison starts after the next scheduled snapshot.</p>
  `;
}

function lineSvg(points, label, color) {
  if (!points.length) return "";
  const values = points.map((point) => point.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = Math.max(max - min, 1);
  const coords = values.map((value, index) => {
    const x = 12 + index * 68;
    const y = 58 - ((value - min) / range) * 42;
    return `${x},${y}`;
  }).join(" ");
  return `
    <div class="sparkline">
      <div>
        <span>${label}</span>
        <strong>${formatNumber(values[values.length - 1])}</strong>
      </div>
      <svg viewBox="0 0 160 70" role="img" aria-label="${label} trend">
        <polyline points="${coords}" fill="none" stroke="${color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></polyline>
        ${coords.split(" ").map((coord) => {
          const [cx, cy] = coord.split(",");
          return `<circle cx="${cx}" cy="${cy}" r="3.5" fill="${color}"></circle>`;
        }).join("")}
      </svg>
    </div>
  `;
}

function renderBars(selector, items, suffix) {
  const element = document.querySelector(selector);
  if (!items.length) {
    element.textContent = "No data yet.";
    return;
  }

  const max = Math.max(...items.map((item) => item.job_count), 1);
  element.innerHTML = items.map((item, index) => {
    const width = Math.max((item.job_count / max) * 100, 5);
    return `
      <div class="bar-row">
        <div class="bar-meta">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <strong>${titleCase(item.name)}</strong>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${width}%"></div>
        </div>
        <div class="bar-number">${formatNumber(item.job_count)} ${suffix}</div>
      </div>
    `;
  }).join("");
}

function renderHeatmap(items) {
  const element = document.querySelector("#skill-heatmap");
  if (!items.length) {
    element.textContent = "No skill data yet.";
    return;
  }

  const max = Math.max(...items.map((item) => item.job_count), 1);
  element.innerHTML = items.slice(0, 12).map((item) => {
    const intensity = item.job_count / max;
    const alpha = 0.22 + intensity * 0.55;
    return `
      <div class="heat-cell" style="--alpha:${alpha}">
        <span>${item.name}</span>
        <strong>${item.job_count}</strong>
      </div>
    `;
  }).join("");
}

function renderSkillGroups(groups) {
  const element = document.querySelector("#skill-groups");
  if (!groups.length) {
    element.textContent = "No grouped skill data yet.";
    return;
  }

  const max = Math.max(...groups.map((group) => group.total_mentions), 1);
  element.innerHTML = groups.map((group) => {
    const width = Math.max((group.total_mentions / max) * 100, 5);
    return `
      <article class="skill-group">
        <div class="skill-group-top">
          <strong>${group.name}</strong>
          <span>${group.total_mentions} mentions</span>
        </div>
        <div class="group-track">
          <div class="group-fill" style="width:${width}%"></div>
        </div>
        <div class="skill-chips">
          ${group.top_skills.map((skill) => `<span>${skill.name} · ${skill.job_count}</span>`).join("")}
        </div>
        <div class="subcategory-list">
          ${group.subcategories.map((item) => `
            <div>
              <span>${item.name}</span>
              <strong>${item.job_count}</strong>
            </div>
          `).join("")}
        </div>
      </article>
    `;
  }).join("");
}

function renderAnalysis(data) {
  const clusters = data.demand_clusters || [];
  const skills = data.top_skills || [];
  const topGroup = data.skill_groups?.[0];
  const primary = clusters[0];
  const secondary = clusters[1];
  const cloudMentions = cloudSkillMentions(skills);
  const aiMentions = skills
    .filter((item) => ["LLM", "RAG", "Python", "TensorFlow", "PyTorch"].includes(item.name))
    .reduce((sum, item) => sum + item.job_count, 0);

  document.querySelector("#analysis").innerHTML = `
    <p><strong>${titleCase(primary?.name || "Software roles")}</strong> is the clearest hiring pool in the ${snapshotDate(data)} snapshot, ahead of <strong>${titleCase(secondary?.name || "the next cluster")}</strong>.</p>
    <p><strong>How to read this:</strong> jobs analyzed tells us what skills appeared in the postings we actually read. Demand index tells us which hiring topics look largest overall.</p>
    <p>The strongest grouped skillset is <strong>${topGroup?.name || "pending"}</strong>, while cloud terms show <strong>${cloudMentions}</strong> mentions and AI/data terms show <strong>${aiMentions}</strong>. This points to practical platform-building projects rather than pure model demos.</p>
    <p class="muted">Trend lines are intentionally kept as preview for this snapshot. They become meaningful after the next scheduled snapshot.</p>
  `;
}

function renderMiniList(selector, items) {
  const element = document.querySelector(selector);
  if (!items.length) {
    element.textContent = "No role data yet.";
    return;
  }

  element.innerHTML = items.slice(0, 8).map((item) => `
    <div class="mini-row">
      <span>${titleCase(item.name)}</span>
      <strong>${item.job_count}</strong>
    </div>
  `).join("");
}

function renderEvidence(items) {
  const element = document.querySelector("#evidence-list");
  if (!items.length) {
    element.textContent = "No evidence examples yet.";
    return;
  }

  element.innerHTML = items.map((item) => `
    <article class="evidence-card">
      <div>
        <h4>${item.title}</h4>
        <p>${item.company} · ${item.location || "Singapore"}</p>
      </div>
      <div class="evidence-meta">
        <span>${titleCase(item.source_query)}</span>
        ${item.skill_groups.map((group) => `<span>${group}</span>`).join("")}
      </div>
      <div class="skill-chips">
        ${item.matched_skills.map((skill) => `<span>${skill}</span>`).join("")}
      </div>
      ${item.url ? `<a href="${item.url}" target="_blank" rel="noreferrer">Open source posting</a>` : ""}
    </article>
  `).join("");
}

function renderMethodology(methodology) {
  const element = document.querySelector("#methodology");
  const queries = methodology.queries || [];
  const limits = methodology.limits || [];
  element.innerHTML = `
    <div class="method-metrics">
      <div><strong>${methodology.source || "Unknown"}</strong><span>source</span></div>
      <div><strong>${formatNumber(methodology.sampled_jobs || 0)}</strong><span>jobs analyzed</span></div>
      <div><strong>${queries.length}</strong><span>tracked topics</span></div>
    </div>
    <p>${methodology.skill_extraction || ""}</p>
    <div class="query-pills">${queries.map((query) => `<span>${query}</span>`).join("")}</div>
    <ul>
      ${limits.map((item) => `<li>${item}</li>`).join("")}
    </ul>
  `;
}

function renderDeepDive(items) {
  const element = document.querySelector("#deep-dive");
  if (!items.length) {
    element.textContent = "No direction recommendation yet.";
    return;
  }

  element.innerHTML = items.map((item) => `
    <article class="deep-card">
      <span>${item.track}</span>
      <h4>${item.focus}</h4>
      <p>${item.why}</p>
      <div class="skill-chips">
        ${item.next_skills.map((skill) => `<span>${skill}</span>`).join("")}
      </div>
      <small>${item.project}</small>
    </article>
  `).join("");
}

function renderProjects(projects) {
  const element = document.querySelector("#projects");
  element.innerHTML = projects.map((project) => `
    <div class="project-card">
      <h4>${project.name}</h4>
      <p>${project.why}</p>
      <div>${project.suggested_stack.map((tag) => `<span>${tag}</span>`).join("")}</div>
    </div>
  `).join("");
}

function cloudSkillMentions(skills) {
  return skills
    .filter((item) => ["AWS", "Azure", "GCP", "Docker", "Kubernetes"].includes(item.name))
    .reduce((sum, item) => sum + item.job_count, 0);
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value || 0);
}

function snapshotDate(data) {
  if (!data.generated_at) {
    return data.week_start || "pending";
  }
  return new Date(data.generated_at).toISOString().slice(0, 10);
}

function titleCase(value) {
  return String(value || "")
    .split(" ")
    .map((part) => part ? part[0].toUpperCase() + part.slice(1) : part)
    .join(" ");
}

loadDashboard().catch(() => {
  document.querySelector("#signal-copy").textContent = "Could not load dashboard data.";
});
