// Retrace.io Multidimensional Matching Engine UI Controller

document.addEventListener("DOMContentLoaded", () => {
  const select = document.getElementById("match-target-select");
  if (select) select.addEventListener("change", runMatchFromUI);

  const runBtn = document.getElementById("btn-run-match");
  if (runBtn) runBtn.addEventListener("click", runMatchFromUI);

  const sliders = ["w-img", "w-txt", "w-loc", "w-time", "w-attr"];
  sliders.forEach(id => {
    const elem = document.getElementById(id);
    if (elem) elem.addEventListener("input", updateWeightsUI);
  });

  const container = document.getElementById("match-results-container");
  if (container) {
    container.addEventListener("click", (e) => {
      const claimBtn = e.target.closest("[data-action='verify-claim']");
      if (claimBtn) {
        const lostId = parseInt(claimBtn.getAttribute("data-lost-id"));
        const foundId = parseInt(claimBtn.getAttribute("data-found-id"));
        if (lostId && foundId) {
          openVerificationModal(lostId, foundId);
        }
      }
    });
  }
});

function populateTargetSelect() {
  const select = document.getElementById("match-target-select");
  if (!select) return;

  let options = `<optgroup label="Lost Items">`;
  allLostItems.forEach(item => {
    options += `<option value="lost_${item.id}">Lost: ${escapeHtml(item.title)} (${escapeHtml(item.location_name)})</option>`;
  });
  options += `</optgroup><optgroup label="Found Items">`;
  allFoundItems.forEach(item => {
    options += `<option value="found_${item.id}">Found: ${escapeHtml(item.title)} (${escapeHtml(item.location_name)})</option>`;
  });
  options += `</optgroup>`;

  select.innerHTML = options;
}

function updateWeightsUI() {
  const imgElem = document.getElementById("w-img-val");
  const txtElem = document.getElementById("w-txt-val");
  const locElem = document.getElementById("w-loc-val");
  const timeElem = document.getElementById("w-time-val");
  const attrElem = document.getElementById("w-attr-val");

  if (imgElem) imgElem.innerText = document.getElementById("w-img").value;
  if (txtElem) txtElem.innerText = document.getElementById("w-txt").value;
  if (locElem) locElem.innerText = document.getElementById("w-loc").value;
  if (timeElem) timeElem.innerText = document.getElementById("w-time").value;
  if (attrElem) attrElem.innerText = document.getElementById("w-attr").value;
}

function triggerMatchForLost(id) {
  navigateTo("match-results");
  const select = document.getElementById("match-target-select");
  if (select) {
    select.value = `lost_${id}`;
    runMatchFromUI();
  }
}

function triggerMatchForFound(id) {
  navigateTo("match-results");
  const select = document.getElementById("match-target-select");
  if (select) {
    select.value = `found_${id}`;
    runMatchFromUI();
  }
}

async function runMatchFromUI() {
  const select = document.getElementById("match-target-select");
  if (!select || !select.value) return;

  const [type, idStr] = select.value.split("_");
  const itemId = parseInt(idStr);

  const payload = {
    item_id: itemId,
    item_type: type,
    min_score_threshold: 10.0,
    weights: {
      image_weight: parseFloat(document.getElementById("w-img").value) / 100.0,
      text_weight: parseFloat(document.getElementById("w-txt").value) / 100.0,
      location_weight: parseFloat(document.getElementById("w-loc").value) / 100.0,
      time_weight: parseFloat(document.getElementById("w-time").value) / 100.0,
      attribute_weight: parseFloat(document.getElementById("w-attr").value) / 100.0
    }
  };

  const container = document.getElementById("match-results-container");
  container.innerHTML = `<div style="text-align: center; padding: 3rem;"><i class="fa-solid fa-spinner fa-spin fa-2x" style="color: #60a5fa;"></i><p style="margin-top: 1rem;">Computing multi-vector AI feature similarities...</p></div>`;

  try {
    const res = await fetch(`${API_BASE}/match`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    renderMatchResults(data.matches || []);
  } catch (err) {
    container.innerHTML = `<div class="doc-box" style="color: #f87171;">Failed to compute AI matches. Please check backend connection.</div>`;
  }
}

function renderMatchResults(matches) {
  const container = document.getElementById("match-results-container");
  if (!matches.length) {
    container.innerHTML = `<div class="doc-box">No matching candidates found above threshold. Try adjusting algorithm weightings above.</div>`;
    return;
  }

  container.innerHTML = matches.map(m => {
    const b = m.breakdown;
    const lost = m.lost_item;
    const found = m.found_item;
    const attrScore = b.attribute_similarity !== undefined ? b.attribute_similarity : b.characteristics_similarity;

    return `
      <div class="match-result-card">
        <!-- Score Column -->
        <div class="score-badge">
          <div class="score-num ${m.status_color}">${m.final_score}%</div>
          <div class="score-tag ${m.status_color}">${m.match_status}</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.6rem;">Combined Weighted Similarity</div>
          
          <button class="btn-primary" style="margin-top: 1.25rem; width: 100%; justify-content: center; font-size: 0.85rem;" 
                  data-action="verify-claim" data-lost-id="${lost.id}" data-found-id="${found.id}">
            <i class="fa-solid fa-shield-halved"></i> Verify & Claim
          </button>
        </div>

        <!-- Breakdown Progress Bars -->
        <div>
          <div style="font-weight: 700; margin-bottom: 0.75rem; font-size: 1.1rem; display: flex; align-items: center; justify-content: space-between;">
            <span>Lost: ${escapeHtml(lost.title)}</span>
            <span style="color: #a78bfa;"><i class="fa-solid fa-arrow-right-arrow-left"></i></span>
            <span>Found: ${escapeHtml(found.title)}</span>
          </div>

          <div class="metric-row">
            <div class="metric-header"><span>🖼️ Image Visual Features</span><span>${b.image_similarity}%</span></div>
            <div class="progress-bar-bg"><div class="progress-bar-fill blue" style="width: ${b.image_similarity}%;"></div></div>
          </div>

          <div class="metric-row">
            <div class="metric-header"><span>📝 Semantic Text Similarity</span><span>${b.text_similarity}%</span></div>
            <div class="progress-bar-bg"><div class="progress-bar-fill purple" style="width: ${b.text_similarity}%;"></div></div>
          </div>

          <div class="metric-row">
            <div class="metric-header"><span>📍 Spatial Location Proximity</span><span>${b.location_proximity}%</span></div>
            <div class="progress-bar-bg"><div class="progress-bar-fill emerald" style="width: ${b.location_proximity}%;"></div></div>
          </div>

          <div class="metric-row">
            <div class="metric-header"><span>🕒 Temporal Proximity Window</span><span>${b.time_proximity}%</span></div>
            <div class="progress-bar-bg"><div class="progress-bar-fill amber" style="width: ${b.time_proximity}%;"></div></div>
          </div>

          <div class="metric-row">
            <div class="metric-header"><span>🏷️ Attribute Match (Category/Color)</span><span>${attrScore}%</span></div>
            <div class="progress-bar-bg"><div class="progress-bar-fill purple" style="width: ${attrScore}%;"></div></div>
          </div>
        </div>

        <!-- Explainable AI Insights -->
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border-color); border-radius: 12px; padding: 1rem;">
          <div style="font-weight: 700; font-size: 0.85rem; color: #60a5fa; margin-bottom: 0.5rem;"><i class="fa-solid fa-lightbulb"></i> Explainable AI Breakdown</div>
          <ul class="explanation-list">
            ${m.explanations.map(exp => `<li>${escapeHtml(exp)}</li>`).join("")}
          </ul>
        </div>
      </div>
    `;
  }).join("");
}
