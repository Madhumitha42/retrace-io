// Retrace.io Document Contradiction Detector UI Controller

document.addEventListener("DOMContentLoaded", () => {
  const addBtn = document.getElementById("btn-add-doc");
  if (addBtn) addBtn.addEventListener("click", addDocumentBox);

  const runBtn = document.getElementById("btn-run-contradiction");
  if (runBtn) runBtn.addEventListener("click", runContradictionAnalysis);
});

function addDocumentBox() {
  const container = document.getElementById("docs-input-list");
  const count = container.children.length + 1;
  const newBox = document.createElement("div");
  newBox.className = "doc-box";
  newBox.innerHTML = `
    <label>Document ${count} Title</label>
    <input type="text" class="doc-title-input" value="Document ${count}" style="margin-bottom: 0.5rem;">
    <label>Document Text / Content</label>
    <textarea class="doc-text-input" rows="4" placeholder="Paste document content..."></textarea>
  `;
  container.appendChild(newBox);
}

async function runContradictionAnalysis() {
  const titleInputs = document.querySelectorAll(".doc-title-input");
  const textInputs = document.querySelectorAll(".doc-text-input");

  const documents = [];
  titleInputs.forEach((titleElem, i) => {
    const text = textInputs[i].value.trim();
    if (text) {
      documents.push({ title: titleElem.value.trim() || `Doc ${i+1}`, text: text });
    }
  });

  const resContainer = document.getElementById("contradiction-results");
  if (documents.length < 2) {
    resContainer.innerHTML = `<div class="doc-box" style="color: #fbbf24;">Please enter content for at least 2 documents to compare.</div>`;
    return;
  }

  resContainer.innerHTML = `<div style="text-align: center; padding: 2rem;"><i class="fa-solid fa-spinner fa-spin fa-2x" style="color: #fbbf24;"></i><p style="margin-top: 1rem;">Analyzing entity facts across documents...</p></div>`;

  try {
    const res = await fetch(`${API_BASE}/contradiction/detect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ documents })
    });

    const data = await res.json();
    const result = data.result;

    if (!result.has_contradiction) {
      resContainer.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 1.5rem; text-align: center;">
          <i class="fa-solid fa-circle-check fa-2x" style="color: #34d399; margin-bottom: 0.5rem;"></i>
          <h4 style="color: #34d399; font-size: 1.1rem; margin-bottom: 0.4rem;">No Contradictions Detected</h4>
          <p style="font-size: 0.9rem; color: var(--text-muted);">All extracted dates, amounts, and specs appear consistent across documents.</p>
        </div>
      `;
      return;
    }

    resContainer.innerHTML = result.contradictions.map(c => `
      <div class="contradiction-card">
        <div class="contradiction-header">
          <span><i class="fa-solid fa-triangle-exclamation"></i> ⚠ CONTRADICTION DETECTED</span>
          <span style="background: rgba(239, 68, 68, 0.3); padding: 2px 8px; border-radius: 6px; font-size: 0.75rem;">Confidence: ${escapeHtml(c.confidence)}</span>
        </div>
        <div style="font-weight: 700; font-size: 1.05rem; margin-bottom: 0.4rem;">Topic: ${escapeHtml(c.topic)}</div>
        <p style="font-size: 0.88rem; color: var(--text-muted); margin-bottom: 0.75rem;">${escapeHtml(c.explanation)}</p>

        <div style="display: flex; flex-direction: column; gap: 0.4rem;">
          ${c.details.map(d => `
            <div style="background: rgba(15, 23, 42, 0.7); border-left: 3px solid #f87171; padding: 0.6rem 0.8rem; font-size: 0.85rem; border-radius: 4px;">
              <strong style="color: #93c5fd;">${escapeHtml(d.document)}:</strong> <span style="color: #fca5a5;">"${escapeHtml(d.stated_value)}"</span>
            </div>
          `).join("")}
        </div>
      </div>
    `).join("");

  } catch (err) {
    resContainer.innerHTML = `<div class="doc-box" style="color: #f87171;">Failed to connect to contradiction detector backend.</div>`;
  }
}
