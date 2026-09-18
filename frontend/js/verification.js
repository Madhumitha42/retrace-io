// Retrace.io Fraud Protection & Verification Modal Handler

document.addEventListener("DOMContentLoaded", () => {
  const closeBtn = document.getElementById("btn-close-modal");
  if (closeBtn) closeBtn.addEventListener("click", closeVerificationModal);

  const form = document.getElementById("form-verify-claim");
  if (form) form.addEventListener("submit", submitVerificationChallenge);
});

function openVerificationModal(lostId, foundId) {
  document.getElementById("modal-lost-id").value = lostId;
  document.getElementById("modal-found-id").value = foundId;
  document.getElementById("claim-characteristic-input").value = "";
  
  const resBox = document.getElementById("verification-result-box");
  resBox.style.display = "none";
  resBox.innerHTML = "";

  const modal = document.getElementById("modal-verification");
  modal.classList.add("active");
}

function closeVerificationModal() {
  document.getElementById("modal-verification").classList.remove("active");
}

async function submitVerificationChallenge(e) {
  e.preventDefault();
  const lostId = parseInt(document.getElementById("modal-lost-id").value);
  const foundId = parseInt(document.getElementById("modal-found-id").value);
  const claimedChar = document.getElementById("claim-characteristic-input").value;

  const resBox = document.getElementById("verification-result-box");
  resBox.style.display = "block";
  resBox.innerHTML = `<div style="text-align: center; padding: 1rem;"><i class="fa-solid fa-spinner fa-spin" style="color: #60a5fa;"></i> Evaluating private characteristic similarity...</div>`;

  try {
    const res = await fetch(`${API_BASE}/verify-claim`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lost_item_id: lostId,
        found_item_id: foundId,
        claimed_characteristic: claimedChar
      })
    });

    if (res.status === 429) {
      const data = await res.json();
      resBox.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 1.25rem;">
          <div style="color: #f87171; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem;">
            <i class="fa-solid fa-ban"></i> Rate Limit Exceeded (HTTP 429)
          </div>
          <p style="font-size: 0.9rem; color: var(--text-muted);">${escapeHtml(data.detail || 'Too many failed verification attempts.')}</p>
        </div>
      `;
      return;
    }

    if (!res.ok) throw new Error("API error");
    const data = await res.json();

    renderVerificationResult(data.verified, data.similarity_score, data.message, data.contact_info);
  } catch (err) {
    // Client-side fallback challenge evaluation for GitHub Pages static mode
    const lostItem = allLostItems.find(i => i.id === lostId) || allLostItems[0];
    const foundItem = allFoundItems.find(i => i.id === foundId) || allFoundItems[0];
    const storedSecret = (lostItem && lostItem.hidden_characteristic) ? lostItem.hidden_characteristic.toLowerCase() : "";

    const claimWords = (claimedChar.toLowerCase().match(/\b[a-z0-9]+\b/g) || []);
    const secretWords = (storedSecret.match(/\b[a-z0-9]+\b/g) || []);

    const matchCount = claimWords.filter(w => secretWords.includes(w)).length;
    const score = secretWords.length ? Math.round((matchCount / secretWords.length) * 100) : 0;
    const isVerified = (score >= 40) || (claimedChar.length > 3 && storedSecret.includes(claimedChar.toLowerCase()));

    const mockScore = isVerified ? Math.max(78, score) : Math.min(30, score);
    const mockMsg = isVerified ? "Verification Successful! Description matches registered private detail." : "Verification Failed. Description does not match registered detail.";
    
    const contactInfo = isVerified ? {
      finder_name: foundItem ? foundItem.finder_name : "Custodian",
      finder_contact: foundItem ? (foundItem.finder_contact || "custodian@campus.edu") : "contact@example.com",
      owner_name: lostItem ? lostItem.owner_name : "Owner",
      owner_contact: "owner@example.edu",
      public_notes: foundItem ? (foundItem.public_notes || "Safely held at desk") : "In safe custody"
    } : null;

    renderVerificationResult(isVerified, mockScore, mockMsg, contactInfo);
  }
}

function renderVerificationResult(verified, score, message, contact) {
  const resBox = document.getElementById("verification-result-box");
  if (verified && contact) {
    resBox.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 1.25rem;">
        <div style="color: #34d399; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="fa-solid fa-circle-check"></i> Verification Successful! (Match Confidence: ${score}%)
        </div>
        <p style="font-size: 0.9rem; color: var(--text-main); margin-bottom: 1rem;">
          ${escapeHtml(message)} Contact details unmasked below:
        </p>
        <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; font-size: 0.9rem;">
          <div><strong>Finder / Custodian:</strong> ${escapeHtml(contact.finder_name)}</div>
          <div><strong>Finder Contact:</strong> <a href="mailto:${escapeHtml(contact.finder_contact)}" style="color: #60a5fa;">${escapeHtml(contact.finder_contact)}</a></div>
          <div><strong>Owner Name:</strong> ${escapeHtml(contact.owner_name)}</div>
          <div><strong>Holding Notes:</strong> ${escapeHtml(contact.public_notes || 'N/A')}</div>
        </div>
      </div>
    `;
  } else {
    resBox.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 1.25rem;">
        <div style="color: #f87171; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
          <i class="fa-solid fa-triangle-exclamation"></i> Verification Failed (Match Score: ${score}%)
        </div>
        <p style="font-size: 0.9rem; color: var(--text-muted);">
          ${escapeHtml(message)} The description provided did not match the owner's registered detail.
        </p>
      </div>
    `;
  }
}
