const state = {
  userId: localStorage.getItem("yournews_user_id") || "",
  feedbackByArticleId: new Map(),
  digestItems: [],
  savedDigests: [],
  recentArticles: [],
  preferences: [],
  deliveriesByDigestId: new Map(),
};

const elements = {
  emailInput: document.querySelector("#email-input"),
  createUserButton: document.querySelector("#create-user-button"),
  selectedUserId: document.querySelector("#selected-user-id"),
  selectedUserPill: document.querySelector("#selected-user-pill"),
  userStatus: document.querySelector("#user-status"),
  loadDigestButton: document.querySelector("#load-digest-button"),
  generateDigestButton: document.querySelector("#generate-digest-button"),
  digestList: document.querySelector("#digest-list"),
  loadSavedDigestsButton: document.querySelector("#load-saved-digests-button"),
  savedDigestsList: document.querySelector("#saved-digests-list"),
  savedDigestDetail: document.querySelector("#saved-digest-detail"),
  loadPreferencesButton: document.querySelector("#load-preferences-button"),
  preferencesList: document.querySelector("#preferences-list"),
  loadArticlesButton: document.querySelector("#load-articles-button"),
  articlesList: document.querySelector("#articles-list"),
  metricUser: document.querySelector("#metric-user"),
  metricDigests: document.querySelector("#metric-digests"),
  metricPreferences: document.querySelector("#metric-preferences"),
  metricArticles: document.querySelector("#metric-articles"),
  toastRoot: document.querySelector("#toast-root"),
};

const feedbackOptions = [
  { label: "Interesting", value: "INTERESTING", icon: "👍" },
  { label: "Neutral", value: "NEUTRAL", icon: "•" },
  { label: "Not interested", value: "NOT_INTERESTING", icon: "👎" },
];

function setStatus(message) {
  elements.userStatus.textContent = message;
}

function showToast(message, type = "default") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  elements.toastRoot.append(toast);
  window.setTimeout(() => toast.remove(), 3600);
}

function setSelectedUser(userId) {
  state.userId = String(userId || "");
  elements.selectedUserId.textContent = state.userId || "none";
  elements.selectedUserPill.textContent = state.userId ? `User #${state.userId}` : "No user selected";
  elements.selectedUserPill.classList.toggle("active", Boolean(state.userId));
  if (state.userId) {
    localStorage.setItem("yournews_user_id", state.userId);
  } else {
    localStorage.removeItem("yournews_user_id");
  }
  updateMetrics();
}

function updateMetrics() {
  elements.metricUser.textContent = state.userId ? `#${state.userId}` : "None";
  elements.metricDigests.textContent = state.savedDigests.length ? String(state.savedDigests.length) : "0";
  elements.metricPreferences.textContent = state.preferences.length ? String(state.preferences.length) : "0";
  elements.metricArticles.textContent = state.recentArticles.length ? String(state.recentArticles.length) : "0";
}

async function apiFetch(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function requireUser() {
  if (!state.userId) {
    showToast("Create or select a user first.", "error");
    setStatus("Create or select a user first.");
    return false;
  }
  return true;
}

function setLoading(container, message) {
  container.className = container.className.replace(/\bempty-state\b|\berror-state\b/g, "").trim();
  container.classList.add("loading-state");
  container.textContent = message;
}

function setEmpty(container, message) {
  container.className = container.className.replace(/\bloading-state\b|\berror-state\b/g, "").trim();
  container.classList.add("empty-state");
  container.textContent = message;
}

function setError(container, message) {
  container.className = container.className.replace(/\bloading-state\b|\bempty-state\b/g, "").trim();
  container.classList.add("error-state");
  container.textContent = message;
}

function clearStateClass(container) {
  container.classList.remove("empty-state", "loading-state", "error-state");
}

function formatDate(value) {
  if (!value) return "No publish date";
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function renderTopics(container, topics) {
  container.replaceChildren();
  if (!topics || topics.length === 0) {
    const empty = document.createElement("span");
    empty.className = "topic-pill";
    empty.textContent = "No topics";
    container.append(empty);
    return;
  }

  topics.forEach((topic) => {
    const pill = document.createElement("span");
    pill.className = "topic-pill";
    pill.textContent = topic;
    container.append(pill);
  });
}

function renderScoreBreakdown(article) {
  const breakdown = article.score_breakdown;
  if (!breakdown) return document.createDocumentFragment();

  const scoreDetails = document.createElement("div");
  scoreDetails.className = "score-breakdown";
  const entries = [
    ["Topic", breakdown.topic_score],
    ["Preference", breakdown.preference_score],
    ["Freshness", breakdown.freshness_score],
    ["Source penalty", breakdown.source_penalty > 0 ? `-${breakdown.source_penalty}` : "0"],
  ];

  entries.forEach(([label, value]) => {
    const item = document.createElement("div");
    item.className = "score-item";
    item.innerHTML = `<span class="score-label"></span><span class="score-value"></span>`;
    item.querySelector(".score-label").textContent = label;
    item.querySelector(".score-value").textContent = value;
    scoreDetails.append(item);
  });

  return scoreDetails;
}

async function loadFeedbackState() {
  if (!state.userId) return;
  const feedbackRows = await apiFetch(`/feedback?user_id=${encodeURIComponent(state.userId)}&limit=100`);
  state.feedbackByArticleId = new Map();
  feedbackRows.forEach((row) => {
    if (!state.feedbackByArticleId.has(row.article_id)) {
      state.feedbackByArticleId.set(row.article_id, row.label);
    }
  });
}

function updateFeedbackButtons(card, selectedLabel, isSaving = false) {
  card.querySelectorAll(".feedback-option").forEach((button) => {
    const isActive = button.dataset.label === selectedLabel;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
    button.disabled = isSaving;
  });
}

function renderFeedbackControl(article, card) {
  const panel = document.createElement("div");
  panel.className = "feedback-panel";
  const articleId = article.article_id || article.id;
  const selectedLabel = state.feedbackByArticleId.get(articleId);
  panel.innerHTML = `<div class="feedback-label">Your feedback</div>`;

  const segmented = document.createElement("div");
  segmented.className = "segmented-control";
  feedbackOptions.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "feedback-option";
    button.dataset.label = option.value;
    button.setAttribute("aria-pressed", String(selectedLabel === option.value));
    button.innerHTML = `<span>${option.icon}</span><span>${option.label}</span>`;
    button.addEventListener("click", () => submitFeedback(articleId, option.value, card));
    segmented.append(button);
  });

  const status = document.createElement("p");
  status.className = "inline-status";
  status.textContent = selectedLabel ? `Saved as ${labelToText(selectedLabel)}.` : "Choose a signal to tune recommendations.";

  panel.append(segmented, status);
  updateFeedbackButtons(panel, selectedLabel);
  return panel;
}

function labelToText(label) {
  return feedbackOptions.find((option) => option.value === label)?.label || label;
}

function createDigestCard(article) {
  const card = document.createElement("article");
  card.className = "digest-card";
  const articleId = article.article_id || article.id;
  card.dataset.articleId = articleId;

  const main = document.createElement("div");
  main.className = "digest-card-main";
  main.innerHTML = `
    <div class="digest-card-header">
      <div>
        <span class="rank-badge">#${article.rank || "—"}</span>
        <a class="article-title" target="_blank" rel="noreferrer"></a>
        <div class="card-meta"></div>
      </div>
      <span class="score-pill">Score ${article.score ?? "—"}</span>
    </div>
    <div class="topics"></div>
  `;
  const title = main.querySelector(".article-title");
  title.textContent = article.title;
  title.href = article.url;
  const articleDate = formatDate(article.published_at || article.created_at);
  main.querySelector(".card-meta").textContent = `${article.source_name || "Unknown source"} · ${articleDate}`;
  renderTopics(main.querySelector(".topics"), article.topics || []);
  main.append(renderScoreBreakdown(article));

  card.append(main, renderFeedbackControl(article, card));
  return card;
}

function renderDigest(items) {
  clearStateClass(elements.digestList);
  elements.digestList.replaceChildren();

  if (!items || items.length === 0) {
    setEmpty(elements.digestList, "No ranked articles found for this user yet.");
    return;
  }

  items.forEach((article) => elements.digestList.append(createDigestCard(article)));
}

function createCompactArticleCard(article, { rank } = {}) {
  const card = document.createElement("article");
  card.className = "compact-article-card";
  card.innerHTML = `
    <div class="article-card-header">
      <div>
        ${rank ? `<span class="rank-badge">#${rank}</span>` : ""}
        <a class="article-title" target="_blank" rel="noreferrer"></a>
        <div class="card-meta"></div>
      </div>
    </div>
    <div class="topics"></div>
  `;
  const title = card.querySelector(".article-title");
  title.textContent = article.title;
  title.href = article.url;
  const articleDate = formatDate(article.published_at || article.created_at);
  card.querySelector(".card-meta").textContent = `${article.source_name || "Unknown source"} · ${articleDate}`;
  renderTopics(card.querySelector(".topics"), article.topics || []);
  return card;
}

function renderPreferences(preferences) {
  state.preferences = [...(preferences || [])].sort((a, b) => Math.abs(b.weight) - Math.abs(a.weight));
  updateMetrics();
  clearStateClass(elements.preferencesList);
  elements.preferencesList.replaceChildren();

  if (state.preferences.length === 0) {
    setEmpty(elements.preferencesList, "No preferences yet. Submit feedback on digest items to build them.");
    return;
  }

  const maxWeight = Math.max(...state.preferences.map((preference) => Math.abs(preference.weight)), 1);
  state.preferences.forEach((preference, index) => {
    const isPositive = preference.weight >= 0;
    const row = document.createElement("div");
    row.className = "preference-card";
    row.innerHTML = `
      <div class="preference-topline">
        <span class="preference-topic">${index + 1}. ${preference.topic}</span>
        <span class="preference-weight ${isPositive ? "positive" : "negative"}">${preference.weight > 0 ? "+" : ""}${preference.weight}</span>
      </div>
      <div class="preference-bar-track"><div class="preference-bar-fill ${isPositive ? "positive" : "negative"}"></div></div>
    `;
    row.querySelector(".preference-bar-fill").style.width = `${Math.max(8, (Math.abs(preference.weight) / maxWeight) * 100)}%`;
    elements.preferencesList.append(row);
  });
}

function renderSavedDigests(digests) {
  state.savedDigests = digests || [];
  updateMetrics();
  clearStateClass(elements.savedDigestsList);
  elements.savedDigestsList.replaceChildren();

  if (state.savedDigests.length === 0) {
    setEmpty(elements.savedDigestsList, "No saved digests yet. Generate one from the digest preview.");
    setEmpty(elements.savedDigestDetail, "Select a saved digest to inspect its ranked items.");
    return;
  }

  state.savedDigests.forEach((digest) => {
    const row = document.createElement("article");
    row.className = "saved-digest-card";
    row.innerHTML = `
      <div>
        <div class="saved-title">Digest #${digest.id}</div>
        <p class="saved-meta">${digest.item_count} items · ${formatDate(digest.created_at)}</p>
      </div>
      <button type="button" class="button secondary">View</button>
    `;
    row.querySelector("button").addEventListener("click", () => loadSavedDigestDetail(digest.id));
    elements.savedDigestsList.append(row);
  });
}

function renderSavedDigestDetail(digest) {
  clearStateClass(elements.savedDigestDetail);
  elements.savedDigestDetail.replaceChildren();
  const header = document.createElement("div");
  header.className = "saved-detail-header";
  const createdAt = formatDate(digest.created_at);
  header.innerHTML = `
    <div>
      <strong>Digest #${digest.id}</strong>
      <p class="saved-meta">Created ${createdAt} · ${digest.items.length} items</p>
      <p class="saved-meta">Email delivery is local/dev simulation only; no external email is sent.</p>
    </div>
    <div class="button-row">
      <button type="button" class="button primary" data-action="send">Send email digest</button>
      <button type="button" class="button secondary" data-action="preview">View delivery preview</button>
      <button type="button" class="button secondary" data-action="history">Refresh deliveries</button>
    </div>
  `;
  header.querySelector('[data-action="send"]').addEventListener("click", (event) => sendEmailDigest(digest.id, event.currentTarget));
  header.querySelector('[data-action="preview"]').addEventListener("click", () => loadDeliveryPreview(digest.id));
  header.querySelector('[data-action="history"]').addEventListener("click", () => loadDeliveryHistory(digest.id));
  const list = document.createElement("div");
  list.className = "saved-detail-list";
  digest.items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "saved-detail-item";
    row.append(createCompactArticleCard(item, { rank: item.rank }));
    list.append(row);
  });
  const delivery = document.createElement("div");
  delivery.className = "delivery-preview empty-state";
  delivery.textContent = "Delivery preview not loaded.";
  const history = document.createElement("div");
  history.className = "delivery-history empty-state";
  history.textContent = "Delivery history not loaded.";
  elements.savedDigestDetail.append(header, list, delivery, history);
  loadDeliveryHistory(digest.id);
}


function renderDeliveryRecord(delivery) {
  const card = document.createElement("article");
  card.className = "delivery-card";
  card.innerHTML = `
    <div class="delivery-card-header">
      <div>
        <strong>Delivery #${delivery.id}</strong>
        <p class="saved-meta">${delivery.channel} · ${delivery.provider} · ${delivery.status} · sent ${formatDate(delivery.sent_at)}</p>
        <p class="saved-meta">To: ${delivery.recipient_email || "unknown"}</p>
      </div>
      <button type="button" class="button secondary">View stored body</button>
    </div>
    <div class="delivery-grid delivery-body" hidden>
      <section>
        <h4>Plain text email</h4>
        <pre class="delivery-text"></pre>
      </section>
      <section>
        <h4>Stored HTML email</h4>
        <iframe class="delivery-html" title="Stored delivered digest"></iframe>
      </section>
    </div>
  `;
  const body = card.querySelector(".delivery-body");
  const button = card.querySelector("button");
  card.querySelector(".delivery-text").textContent = delivery.text_body;
  card.querySelector("iframe").srcdoc = delivery.html_body;
  button.addEventListener("click", () => {
    body.hidden = !body.hidden;
    button.textContent = body.hidden ? "View stored body" : "Hide stored body";
  });
  return card;
}

function renderDeliveryHistory(digestId, deliveries) {
  const container = elements.savedDigestDetail.querySelector(".delivery-history");
  if (!container) return;
  state.deliveriesByDigestId.set(digestId, deliveries || []);
  clearStateClass(container);
  container.classList.add("delivery-history");
  container.replaceChildren();

  const heading = document.createElement("div");
  heading.className = "delivery-header";
  heading.innerHTML = `
    <div>
      <span class="section-kicker">Email delivery history</span>
      <h3>Local/dev deliveries</h3>
      <p class="saved-meta">These records simulate email sends and store the exact HTML/text bodies with tracked feedback links.</p>
    </div>
  `;
  container.append(heading);

  if (!deliveries || deliveries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No deliveries yet. Use Send email digest to create a local email delivery record.";
    container.append(empty);
    return;
  }

  deliveries.forEach((delivery) => container.append(renderDeliveryRecord(delivery)));
}

async function loadDeliveryHistory(digestId) {
  const container = elements.savedDigestDetail.querySelector(".delivery-history");
  if (!container) return;
  try {
    setLoading(container, `Loading delivery history for digest #${digestId}...`);
    const deliveries = await apiFetch(`/digests/${digestId}/deliveries`);
    renderDeliveryHistory(digestId, deliveries);
  } catch (error) {
    setError(container, `Delivery history failed: ${error.message}`);
  }
}

async function sendEmailDigest(digestId, button) {
  try {
    button.disabled = true;
    button.textContent = "Sending...";
    const delivery = await apiFetch(`/digests/${digestId}/send`, { method: "POST" });
    showToast(`Local email delivery #${delivery.id} marked ${delivery.status}.`, "success");
    renderDeliveryPreview({
      subject: delivery.subject,
      user_email: delivery.recipient_email,
      text_body: delivery.text_body,
      html_body: delivery.html_body,
    });
    await loadDeliveryHistory(digestId);
  } catch (error) {
    showToast(`Send email digest failed: ${error.message}`, "error");
  } finally {
    button.disabled = false;
    button.textContent = "Send email digest";
  }
}

function renderDeliveryPreview(preview) {
  const container = elements.savedDigestDetail.querySelector(".delivery-preview");
  if (!container) return;
  clearStateClass(container);
  container.classList.add("delivery-preview");
  container.replaceChildren();

  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
    <div class="delivery-header">
      <div>
        <span class="section-kicker">Delivery preview</span>
        <h3></h3>
        <p class="saved-meta"></p>
      </div>
    </div>
    <div class="delivery-grid">
      <section>
        <h4>Plain text</h4>
        <pre class="delivery-text"></pre>
      </section>
      <section>
        <h4>HTML preview</h4>
        <iframe class="delivery-html" title="Rendered digest delivery preview"></iframe>
      </section>
    </div>
  `;
  wrapper.querySelector("h3").textContent = preview.subject;
  wrapper.querySelector(".saved-meta").textContent = `To: ${preview.user_email || "unknown"}`;
  wrapper.querySelector(".delivery-text").textContent = preview.text_body;
  container.append(wrapper);
  container.querySelector("iframe").srcdoc = preview.html_body;
}

async function loadDeliveryPreview(digestId) {
  const container = elements.savedDigestDetail.querySelector(".delivery-preview");
  if (!container) return;
  try {
    setLoading(container, `Loading delivery preview for digest #${digestId}...`);
    const preview = await apiFetch(`/digests/${digestId}/delivery-preview`);
    renderDeliveryPreview(preview);
  } catch (error) {
    setError(container, `Delivery preview failed: ${error.message}`);
  }
}

function renderRecentArticles(articles) {
  state.recentArticles = articles || [];
  updateMetrics();
  clearStateClass(elements.articlesList);
  elements.articlesList.replaceChildren();

  if (state.recentArticles.length === 0) {
    setEmpty(elements.articlesList, "No recent articles found.");
    return;
  }

  state.recentArticles.forEach((article) => elements.articlesList.append(createCompactArticleCard(article)));
}

async function createUser() {
  const email = elements.emailInput.value.trim();
  if (!email) {
    showToast("Enter an email address.", "error");
    return;
  }

  try {
    setStatus("Creating/reusing user...");
    const user = await apiFetch("/users", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    setSelectedUser(user.id);
    showToast(`Selected ${user.email}.`, "success");
    setStatus(`Selected ${user.email}.`);
    await Promise.all([loadPreferences(), loadDigest(), loadSavedDigests()]);
  } catch (error) {
    showToast(`User request failed: ${error.message}`, "error");
    setStatus(`User request failed: ${error.message}`);
  }
}

async function loadDigest() {
  if (!requireUser()) return;
  try {
    setLoading(elements.digestList, "Loading personalized digest and feedback state...");
    await loadFeedbackState();
    const digest = await apiFetch(`/digest/preview?user_id=${encodeURIComponent(state.userId)}`);
    state.digestItems = digest.items || [];
    renderDigest(state.digestItems);
  } catch (error) {
    setError(elements.digestList, `Digest failed: ${error.message}`);
    showToast("Digest load failed.", "error");
  }
}

async function generateSavedDigest() {
  if (!requireUser()) return;
  try {
    elements.generateDigestButton.disabled = true;
    elements.generateDigestButton.textContent = "Generating...";
    const digest = await apiFetch(`/digests/generate?user_id=${encodeURIComponent(state.userId)}&limit=10`, {
      method: "POST",
    });
    showToast(`Generated digest #${digest.id} with ${digest.items.length} items.`, "success");
    await loadSavedDigests();
    renderSavedDigestDetail(digest);
  } catch (error) {
    showToast(`Generate digest failed: ${error.message}`, "error");
  } finally {
    elements.generateDigestButton.disabled = false;
    elements.generateDigestButton.textContent = "Generate saved digest";
  }
}

async function loadSavedDigests() {
  if (!requireUser()) return;
  try {
    setLoading(elements.savedDigestsList, "Loading saved digests...");
    const digests = await apiFetch(`/users/${encodeURIComponent(state.userId)}/digests`);
    renderSavedDigests(digests);
  } catch (error) {
    setError(elements.savedDigestsList, `Saved digests failed: ${error.message}`);
    showToast("Saved digests failed to load.", "error");
  }
}

async function loadSavedDigestDetail(digestId) {
  try {
    setLoading(elements.savedDigestDetail, `Loading digest #${digestId}...`);
    const digest = await apiFetch(`/digests/${digestId}`);
    renderSavedDigestDetail(digest);
  } catch (error) {
    setError(elements.savedDigestDetail, `Digest detail failed: ${error.message}`);
  }
}

async function submitFeedback(articleId, label, card) {
  if (!requireUser()) return;
  const panel = card.querySelector(".feedback-panel");
  const status = card.querySelector(".inline-status");
  const previousLabel = state.feedbackByArticleId.get(articleId);

  try {
    state.feedbackByArticleId.set(articleId, label);
    updateFeedbackButtons(panel, label, true);
    status.className = "inline-status";
    status.textContent = "Saving feedback...";
    await apiFetch("/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: Number(state.userId), article_id: Number(articleId), label }),
    });
    status.className = "inline-status success";
    status.textContent = `Saved as ${labelToText(label)}.`;
    showToast("Feedback saved.", "success");
    await loadPreferences();
  } catch (error) {
    if (previousLabel) {
      state.feedbackByArticleId.set(articleId, previousLabel);
    } else {
      state.feedbackByArticleId.delete(articleId);
    }
    updateFeedbackButtons(panel, previousLabel, false);
    status.className = "inline-status error";
    status.textContent = "Feedback failed to save.";
    showToast(`Feedback failed: ${error.message}`, "error");
    return;
  }
  updateFeedbackButtons(panel, label, false);
}

async function loadPreferences() {
  if (!requireUser()) return;
  try {
    setLoading(elements.preferencesList, "Loading preferences...");
    const preferences = await apiFetch(`/users/${encodeURIComponent(state.userId)}/preferences`);
    renderPreferences(preferences);
  } catch (error) {
    setError(elements.preferencesList, `Preferences failed: ${error.message}`);
  }
}

async function loadArticles() {
  try {
    setLoading(elements.articlesList, "Loading recent articles...");
    const articles = await apiFetch("/articles?limit=20");
    renderRecentArticles(articles);
  } catch (error) {
    setError(elements.articlesList, `Articles failed: ${error.message}`);
  }
}

elements.createUserButton.addEventListener("click", createUser);
elements.loadDigestButton.addEventListener("click", loadDigest);
elements.generateDigestButton.addEventListener("click", generateSavedDigest);
elements.loadSavedDigestsButton.addEventListener("click", loadSavedDigests);
elements.loadPreferencesButton.addEventListener("click", loadPreferences);
elements.loadArticlesButton.addEventListener("click", loadArticles);
elements.emailInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") createUser();
});

setSelectedUser(state.userId);
loadArticles();
if (state.userId) {
  Promise.allSettled([loadPreferences(), loadSavedDigests()]);
}
