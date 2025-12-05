(function () {
  const root = document.getElementById("profile-root");
  if (!root) return;

  const username = root.dataset.username;
  const radarEl = document.getElementById("radarChart");
  const radarPlaceholder = document.getElementById("radarPlaceholder");
  const shareBtn = document.getElementById("share-btn");
  const shareNotice = document.getElementById("share-notice");

  function showShareNotice() {
    if (!shareNotice) return;
    shareNotice.style.display = "block";
    setTimeout(() => (shareNotice.style.display = "none"), 1500);
  }

  async function fetchProfile() {
    const res = await fetch(`/api/profile/${encodeURIComponent(username)}/metrics`);
    if (!res.ok) {
      console.error("Failed to load profile metrics", await res.text());
      return null;
    }
    return res.json();
  }

  function renderRadar(metrics) {
    if (!radarEl) return;
    const values = metrics.radar;
    const labels = [
      "Processing speed",
      "Accuracy",
      "Working memory",
      "Consistency",
      "Engagement",
    ];
    const data = [
      values.processing_speed,
      values.accuracy,
      values.working_memory,
      values.consistency,
      values.engagement,
    ];
    if (window.Chart) {
      if (radarPlaceholder) radarPlaceholder.style.display = "none";
      new Chart(radarEl, {
        type: "radar",
        data: {
          labels,
          datasets: [
            {
              label: "Profile",
              data,
              backgroundColor: "rgba(99, 102, 241, 0.3)",
              borderColor: "#6366f1",
              pointBackgroundColor: "#a855f7",
            },
          ],
        },
        options: {
          scales: {
            r: { beginAtZero: true, suggestedMax: 100 },
          },
        },
      });
    } else if (radarPlaceholder) {
      radarEl.style.display = "none";
      radarPlaceholder.innerText = data.join(" · ");
    }
  }

  function renderCard(el, title, rows) {
    if (!el) return;
    el.innerHTML = `
      <div class="card-title">${title}</div>
      <div class="subtext">Latest performance</div>
      ${rows
        .map(
          (row) => `
          <div class="metric-row">
            <span>${row.label}</span>
            <span class="pill">${row.value}</span>
          </div>`
        )
        .join("")}
    `;
  }

  function renderAchievements(grid, earned, locked) {
    if (!grid) return;
    grid.innerHTML = "";
    const makeCard = (item, gotIt) => {
      const status = gotIt ? "earned" : "locked";
      return `<div class="achievement ${status}">
        <div class="code">${item.code}</div>
        <div class="card-title">${item.name}</div>
        <div class="subtext">${item.description}</div>
        <div class="badge">${item.category}</div>
      </div>`;
    };
    const earnedCards = earned.map((a) => makeCard(a, true)).join("");
    const lockedCards = locked.map((a) => makeCard(a, false)).join("");
    grid.innerHTML = earnedCards + lockedCards;
  }

  function formatNumber(value, suffix = "") {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") {
        const rounded = Math.round(value * 100) / 100;
        return `${rounded}${suffix}`;
    }
    return `${value}${suffix}`;
  }

  fetchProfile().then((payload) => {
    if (!payload) return;
    const { metrics, achievements } = payload;
    renderRadar(metrics);

    renderCard(document.getElementById("reaction-card"), "Reaction", [
      { label: "Best score", value: formatNumber(metrics.reaction.best_score) },
      { label: "Avg reaction", value: formatNumber(metrics.reaction.avg_reaction_ms, " ms") },
      { label: "Accuracy", value: formatNumber(metrics.reaction.accuracy) },
    ]);

    renderCard(document.getElementById("memory-card"), "Memory", [
      { label: "Best total", value: formatNumber(metrics.memory.best_total_score) },
      { label: "Avg total", value: formatNumber(metrics.memory.avg_total_score) },
      { label: "Sessions", value: metrics.memory.sessions || 0 },
    ]);

    renderCard(document.getElementById("math-card"), "Maths", [
      { label: "Round 1 best", value: formatNumber(metrics.math.yetamax_best) },
      { label: "Round 2 best", value: formatNumber(metrics.math.maveric_round2_best) },
      { label: "Round 3 best", value: formatNumber(metrics.math.maveric_round3_best) },
      { label: "Questions", value: metrics.math.total_questions || 0 },
    ]);

    renderAchievements(
      document.getElementById("achievements-grid"),
      achievements.earned || [],
      achievements.locked || []
    );
  });

  if (shareBtn) {
    shareBtn.addEventListener("click", async () => {
      const url = window.location.href;
      if (navigator.share) {
        try {
          await navigator.share({ url, title: "CortiX Profile" });
        } catch (err) {
          console.warn("Share cancelled", err);
        }
      } else if (navigator.clipboard) {
        try {
          await navigator.clipboard.writeText(url);
          showShareNotice();
        } catch (err) {
          console.error("Clipboard failed", err);
        }
      } else {
        showShareNotice();
      }
    });
  }
})();
