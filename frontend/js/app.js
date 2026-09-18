// Retrace.io Main Application Controller
const API_BASE = "http://127.0.0.1:8000/api";

let lostMap, foundMap;
let lostMarker, foundMarker;
let allLostItems = [];
let allFoundItems = [];

const MOCK_LOST_ITEMS = [
  {
    id: 1,
    title: "Black College Bag",
    description: "I lost a black college bag near the library. It has a blue water bottle in the side pocket and notebook inside.",
    category: "Bag",
    primary_color: "Black",
    location_name: "College Library Main Entrance",
    latitude: 12.9716,
    longitude: 77.5946,
    lost_datetime: "2026-09-18T14:00:00",
    owner_name: "Rohan Sharma",
    hidden_characteristic: "blue turtle keychain",
    image_url: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
  },
  {
    id: 2,
    title: "iPhone 15 Pro",
    description: "Lost my dark grey iPhone near the Student Cafeteria around lunchtime. Has a transparent silicone case.",
    category: "Electronics",
    primary_color: "Grey",
    location_name: "Student Cafeteria Block A",
    latitude: 12.9722,
    longitude: 77.5950,
    lost_datetime: "2026-09-18T12:30:00",
    owner_name: "Ananya Patel",
    hidden_characteristic: "golden retriever wallpaper",
    image_url: "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?auto=format&fit=crop&w=600&q=80"
  },
  {
    id: 3,
    title: "Silver Car Keys",
    description: "Set of silver keys lost near the Sports Complex basketball court.",
    category: "Keys",
    primary_color: "Silver",
    location_name: "Campus Sports Complex",
    latitude: 12.9705,
    longitude: 77.5930,
    lost_datetime: "2026-09-17T18:00:00",
    owner_name: "Vikram Verma",
    hidden_characteristic: "red leather lanyard",
    image_url: "https://images.unsplash.com/photo-1582142839970-2b9322079f82?auto=format&fit=crop&w=600&q=80"
  }
];

const MOCK_FOUND_ITEMS = [
  {
    id: 1,
    title: "Dark Backpack",
    description: "Found a dark school bag near Block B path containing a hydration bottle and some study notes.",
    category: "Bag",
    primary_color: "Black",
    location_name: "Academic Block B Pathway",
    latitude: 12.9718,
    longitude: 77.5949,
    found_datetime: "2026-09-18T15:15:00",
    finder_name: "Security Desk Staff",
    finder_contact: "security.desk@campus.edu",
    image_url: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80",
    public_notes: "Handed over to Block B security guard."
  },
  {
    id: 2,
    title: "Smartphone with Clear Case",
    description: "Found a grey smartphone lying on a bench outside Student Union.",
    category: "Electronics",
    primary_color: "Grey",
    location_name: "Student Union Bench",
    latitude: 12.9723,
    longitude: 77.5952,
    found_datetime: "2026-09-18T13:00:00",
    finder_name: "Priya Nair",
    finder_contact: "priya.nair@example.edu",
    image_url: "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?auto=format&fit=crop&w=600&q=80",
    public_notes: "Currently with cafeteria staff."
  },
  {
    id: 3,
    title: "Keychain with Lanyard",
    description: "Found keys with a lanyard on the grass near sports ground.",
    category: "Keys",
    primary_color: "Silver",
    location_name: "Sports Ground Edge",
    latitude: 12.9708,
    longitude: 77.5933,
    found_datetime: "2026-09-17T19:30:00",
    finder_name: "David Ray",
    finder_contact: "david.ray@example.com",
    image_url: "https://images.unsplash.com/photo-1582142839970-2b9322079f82?auto=format&fit=crop&w=600&q=80",
    public_notes: "Kept safely at main gate."
  }
];

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initMaps();
  initEventDelegation();
  fetchFeeds();
  
  const nowStr = new Date().toISOString().slice(0, 16);
  document.getElementById("lost-datetime").value = nowStr;
  document.getElementById("found-datetime").value = nowStr;
});

// Navigation Handling
function initNavigation() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetScreen = btn.getAttribute("data-screen");
      navigateTo(targetScreen);
    });
  });
}

function navigateTo(screenId) {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    if (btn.getAttribute("data-screen") === screenId) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  const activeScreen = document.getElementById(`screen-${screenId}`);
  if (activeScreen) {
    activeScreen.classList.add("active");
  }

  if (screenId === "report-lost" && lostMap) setTimeout(() => lostMap.invalidateSize(), 200);
  if (screenId === "report-found" && foundMap) setTimeout(() => foundMap.invalidateSize(), 200);
  if (screenId === "match-results") populateTargetSelect();
}

function initEventDelegation() {
  document.body.addEventListener("click", (e) => {
    const actionBtn = e.target.closest("[data-action]");
    if (!actionBtn) return;

    const action = actionBtn.getAttribute("data-action");
    if (action === "nav") {
      const target = actionBtn.getAttribute("data-target");
      if (target) navigateTo(target);
    } else if (action === "refresh-feeds") {
      fetchFeeds();
    } else if (action === "match-lost") {
      const id = actionBtn.getAttribute("data-id");
      if (id) triggerMatchForLost(id);
    } else if (action === "match-found") {
      const id = actionBtn.getAttribute("data-id");
      if (id) triggerMatchForFound(id);
    }
  });

  const lostForm = document.getElementById("form-report-lost");
  if (lostForm) lostForm.addEventListener("submit", handleReportLost);

  const foundForm = document.getElementById("form-report-found");
  if (foundForm) foundForm.addEventListener("submit", handleReportFound);
}

// Leaflet Maps Setup
function initMaps() {
  const defaultLat = 12.9716;
  const defaultLng = 77.5946;

  lostMap = L.map('map-lost').setView([defaultLat, defaultLng], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: 'OpenStreetMap'
  }).addTo(lostMap);

  lostMarker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(lostMap);
  lostMarker.on('dragend', (e) => {
    const pos = e.target.getLatLng();
    updateLostCoords(pos.lat, pos.lng);
  });
  lostMap.on('click', (e) => {
    lostMarker.setLatLng(e.latlng);
    updateLostCoords(e.latlng.lat, e.latlng.lng);
  });

  foundMap = L.map('map-found').setView([defaultLat + 0.0002, defaultLng + 0.0003], 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: 'OpenStreetMap'
  }).addTo(foundMap);

  foundMarker = L.marker([defaultLat + 0.0002, defaultLng + 0.0003], { draggable: true }).addTo(foundMap);
  foundMarker.on('dragend', (e) => {
    const pos = e.target.getLatLng();
    updateFoundCoords(pos.lat, pos.lng);
  });
  foundMap.on('click', (e) => {
    foundMarker.setLatLng(e.latlng);
    updateFoundCoords(e.latlng.lat, e.latlng.lng);
  });
}

function updateLostCoords(lat, lng) {
  document.getElementById("lost-lat").value = lat;
  document.getElementById("lost-lng").value = lng;
  document.getElementById("lost-lat-disp").innerText = lat.toFixed(4);
  document.getElementById("lost-lng-disp").innerText = lng.toFixed(4);
}

function updateFoundCoords(lat, lng) {
  document.getElementById("found-lat").value = lat;
  document.getElementById("found-lng").value = lng;
  document.getElementById("found-lat-disp").innerText = lat.toFixed(4);
  document.getElementById("found-lng-disp").innerText = lng.toFixed(4);
}

// Fetch Feeds from Backend with Client Fallback
async function fetchFeeds() {
  try {
    const [resLost, resFound] = await Promise.all([
      fetch(`${API_BASE}/items/lost`),
      fetch(`${API_BASE}/items/found`)
    ]);

    if (!resLost.ok || !resFound.ok) throw new Error("API not reachable");

    const lostData = await resLost.json();
    const foundData = await resFound.json();

    allLostItems = lostData.data || [];
    allFoundItems = foundData.data || [];

  } catch (err) {
    console.warn("Backend API offline or unreachable (e.g. GitHub Pages static mode). Loading sample items.", err);
    allLostItems = [...MOCK_LOST_ITEMS];
    allFoundItems = [...MOCK_FOUND_ITEMS];
  }

  document.getElementById("stat-lost-count").innerText = allLostItems.length;
  document.getElementById("stat-found-count").innerText = allFoundItems.length;

  renderLostFeed(allLostItems);
  renderFoundFeed(allFoundItems);
  populateTargetSelect();
}

function renderLostFeed(items) {
  const container = document.getElementById("lost-items-feed");
  if (!items.length) {
    container.innerHTML = `<div class="doc-box">No lost items reported yet.</div>`;
    return;
  }
  container.innerHTML = items.map(item => {
    const safeTitle = escapeHtml(item.title);
    const safeDesc = escapeHtml(item.description);
    const safeLoc = escapeHtml(item.location_name);
    const safeImg = escapeHtml(item.image_url || 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80');

    return `
      <div class="item-card">
        <div class="item-img-container">
          <img src="${safeImg}" class="item-img" alt="${safeTitle}">
          <div class="item-badge lost">LOST</div>
        </div>
        <div class="item-body">
          <div class="item-title">${safeTitle}</div>
          <div class="item-desc">${safeDesc}</div>
          <div class="item-meta">
            <div class="meta-row"><i class="fa-solid fa-location-dot"></i> ${safeLoc}</div>
            <div class="meta-row"><i class="fa-solid fa-clock"></i> ${new Date(item.lost_datetime).toLocaleString()}</div>
            <div class="meta-row"><i class="fa-solid fa-tag"></i> ${escapeHtml(item.category)} • ${escapeHtml(item.primary_color)}</div>
          </div>
          <button class="btn-primary" style="margin-top: 1rem; width: 100%; justify-content: center;" data-action="match-lost" data-id="${item.id}">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Find Matches
          </button>
        </div>
      </div>
    `;
  }).join("");
}

function renderFoundFeed(items) {
  const container = document.getElementById("found-items-feed");
  if (!items.length) {
    container.innerHTML = `<div class="doc-box">No found items reported yet.</div>`;
    return;
  }
  container.innerHTML = items.map(item => {
    const safeTitle = escapeHtml(item.title);
    const safeDesc = escapeHtml(item.description);
    const safeLoc = escapeHtml(item.location_name);
    const safeImg = escapeHtml(item.image_url || 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80');

    return `
      <div class="item-card">
        <div class="item-img-container">
          <img src="${safeImg}" class="item-img" alt="${safeTitle}">
          <div class="item-badge found">FOUND</div>
        </div>
        <div class="item-body">
          <div class="item-title">${safeTitle}</div>
          <div class="item-desc">${safeDesc}</div>
          <div class="item-meta">
            <div class="meta-row"><i class="fa-solid fa-location-dot"></i> ${safeLoc}</div>
            <div class="meta-row"><i class="fa-solid fa-clock"></i> ${new Date(item.found_datetime).toLocaleString()}</div>
            <div class="meta-row"><i class="fa-solid fa-tag"></i> ${escapeHtml(item.category)} • ${escapeHtml(item.primary_color)}</div>
          </div>
          <button class="btn-emerald" style="margin-top: 1rem; width: 100%; justify-content: center;" data-action="match-found" data-id="${item.id}">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Find Matches
          </button>
        </div>
      </div>
    `;
  }).join("");
}

// Form Submission Handlers
async function handleReportLost(e) {
  e.preventDefault();
  const formData = new FormData();
  formData.append("title", document.getElementById("lost-title").value);
  formData.append("description", document.getElementById("lost-desc").value);
  formData.append("category", document.getElementById("lost-category").value);
  formData.append("primary_color", document.getElementById("lost-color").value);
  formData.append("location_name", document.getElementById("lost-location").value);
  formData.append("latitude", document.getElementById("lost-lat").value);
  formData.append("longitude", document.getElementById("lost-lng").value);
  formData.append("lost_datetime", document.getElementById("lost-datetime").value);
  formData.append("hidden_characteristic", document.getElementById("lost-hidden").value);
  formData.append("owner_name", document.getElementById("lost-owner-name").value);
  formData.append("owner_contact", document.getElementById("lost-owner-contact").value);

  const imgFile = document.getElementById("lost-image").files[0];
  if (imgFile) formData.append("image", imgFile);

  try {
    const res = await fetch(`${API_BASE}/items/lost`, { method: "POST", body: formData });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      alert("Lost item report submitted successfully!");
      document.getElementById("form-report-lost").reset();
      await fetchFeeds();
      navigateTo("home");
      return;
    }
  } catch (err) {
    // Client-side fallback for static GitHub Pages demo
    const newItem = {
      id: allLostItems.length + 1,
      title: document.getElementById("lost-title").value,
      description: document.getElementById("lost-desc").value,
      category: document.getElementById("lost-category").value,
      primary_color: document.getElementById("lost-color").value,
      location_name: document.getElementById("lost-location").value,
      latitude: parseFloat(document.getElementById("lost-lat").value),
      longitude: parseFloat(document.getElementById("lost-lng").value),
      lost_datetime: document.getElementById("lost-datetime").value,
      hidden_characteristic: document.getElementById("lost-hidden").value,
      owner_name: document.getElementById("lost-owner-name").value,
      image_url: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
    };
    allLostItems.unshift(newItem);
    alert("Lost item report registered locally!");
    document.getElementById("form-report-lost").reset();
    renderLostFeed(allLostItems);
    populateTargetSelect();
    navigateTo("home");
  }
}

async function handleReportFound(e) {
  e.preventDefault();
  const formData = new FormData();
  formData.append("title", document.getElementById("found-title").value);
  formData.append("description", document.getElementById("found-desc").value);
  formData.append("category", document.getElementById("found-category").value);
  formData.append("primary_color", document.getElementById("found-color").value);
  formData.append("location_name", document.getElementById("found-location").value);
  formData.append("latitude", document.getElementById("found-lat").value);
  formData.append("longitude", document.getElementById("found-lng").value);
  formData.append("found_datetime", document.getElementById("found-datetime").value);
  formData.append("finder_name", document.getElementById("found-finder-name").value);
  formData.append("finder_contact", document.getElementById("found-finder-contact").value);
  formData.append("public_notes", document.getElementById("found-public-notes").value);

  const imgFile = document.getElementById("found-image").files[0];
  if (imgFile) formData.append("image", imgFile);

  try {
    const res = await fetch(`${API_BASE}/items/found`, { method: "POST", body: formData });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      alert("Found item report registered successfully!");
      document.getElementById("form-report-found").reset();
      await fetchFeeds();
      navigateTo("home");
      return;
    }
  } catch (err) {
    // Client-side fallback for static GitHub Pages demo
    const newItem = {
      id: allFoundItems.length + 1,
      title: document.getElementById("found-title").value,
      description: document.getElementById("found-desc").value,
      category: document.getElementById("found-category").value,
      primary_color: document.getElementById("found-color").value,
      location_name: document.getElementById("found-location").value,
      latitude: parseFloat(document.getElementById("found-lat").value),
      longitude: parseFloat(document.getElementById("found-lng").value),
      found_datetime: document.getElementById("found-datetime").value,
      finder_name: document.getElementById("found-finder-name").value,
      finder_contact: document.getElementById("found-finder-contact").value,
      public_notes: document.getElementById("found-public-notes").value,
      image_url: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=600&q=80"
    };
    allFoundItems.unshift(newItem);
    alert("Found item report registered locally!");
    document.getElementById("form-report-found").reset();
    renderFoundFeed(allFoundItems);
    populateTargetSelect();
    navigateTo("home");
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
