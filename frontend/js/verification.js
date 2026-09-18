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

    const data = await res.json();

    if (res.status === 429) {
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

    if (data.verified) {
      const contact = data.contact_info;
      resBox.innerHTML = `
        <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 12px; padding: 1.25rem;">
          <div style="color: #34d399; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            <i class="fa-solid fa-circle-check"></i> Verification Successful! (Match Score: ${data.similarity_score}%)
          </div>
          <p style="font-size: 0.9rem; color: var(--text-main); margin-bottom: 1rem;">
            ${escapeHtml(data.message)} Contact details have been unmasked below:
          </p>
          <div style="background: rgba(15, 23, 42, 0.8); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; font-size: 0.9rem;">
            <div><strong>Finder Custodian:</strong> ${escapeHtml(contact.finder_name)}</div>
            <div><strong>Finder Contact:</strong> <a href="mailto:${escapeHtml(contact.finder_contact)}" style="color: #60a5fa;">${escapeHtml(contact.finder_contact)}</a></div>
            <div><strong>Owner Name:</strong> ${escapeHtml(contact.owner_name)}</div>
            <div><strong>Owner Contact:</strong> ${escapeHtml(contact.owner_contact)}</div>
            <div><strong>Holding Notes:</strong> ${escapeHtml(contact.public_notes || 'N/A')}</div>
          </div>
        </div>
      `;
    } else {
      resBox.innerHTML = `
        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 12px; padding: 1.25rem;">
          <div style="color: #f87171; font-weight: 700; font-size: 1.1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
            <i class="fa-solid fa-triangle-exclamation"></i> Verification Failed (Match Score: ${data.similarity_score}%)
          </div>
          <p style="font-size: 0.9rem; color: var(--text-muted);">
            ${escapeHtml(data.message)} The description provided did not match the owner's registered characteristic.
          </p>
        </div>
      `;
    }
  } catch (err) {
    resBox.innerHTML = `<div style="color: #f87171;">Error performing verification check.</div>`;
  }
}
