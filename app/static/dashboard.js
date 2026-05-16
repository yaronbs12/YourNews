const state = {
  userId: localStorage.getItem("yournews_user_id") || "",
};

const elements = {
  emailInput: document.querySelector("#email-input"),
  createUserButton: document.querySelector("#create-user-button"),
  selectedUserId: document.querySelector("#selected-user-id"),
  userStatus: document.querySelector("#user-status"),
  loadDigestButton: document.querySelector("#load-digest-button"),
  digestList: document.querySelector("#digest-list"),
  loadPreferencesButton: document.querySelector("#load-preferences-button"),
  preferencesList: document.querySelector("#preferences-list"),
  loadArticlesButton: document.querySelector("#load-articles-button"),
  articlesList: document.querySelector("#articles-list"),
  articleTemplate: document.querySelector("#article-template"),
};

const feedbackOptions = [
  { label: "Interesting", value: "INTERESTING", className: "good" },
  { label: "Neutral", value: "NEUTRAL", className: "neutral" },
  { label: "Not interesting", value: "NOT_INTERESTING", className: "bad" },
];

function setStatus(message) {
  elements.userStatus.textContent = message;
}

function setSelectedUser(userId) {
  state.userId = String(userId || "");
  elements.selectedUserId.textContent = state.userId || "none";
  if (state.userId) {
    localStorage.setItem("yournews_user_id", state.userId);
  } else {
    localStorage.removeItem("yournews_user_id");
  }
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
    setStatus("Create or select a user first.");
    return false;
  }
  return true;
}

function renderTopics(container, topics) {
  container.replaceChildren();
  if (!topics || topics.length === 0) {
    const empty = document.createElement("span");
    empty.className = "meta";
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

function renderScoreBreakdown(container, article) {
  const existing = container.querySelector(".score-breakdown");
  if (existing) existing.remove();

  if (!article.score_breakdown) return;

  const breakdown = article.score_breakdown;
  const scoreDetails = document.createElement("div");
  scoreDetails.className = "score-breakdown";
  const sourcePenalty = breakdown.source_penalty > 0 ? breakdown.source_penalty : 0;
  scoreDetails.textContent = [
    `Total score: ${breakdown.total_score}`,
    `Topic score: ${breakdown.topic_score}`,
    `Preference score: ${breakdown.preference_score}`,
    `Freshness score: ${breakdown.freshness_score}`,
    `Source penalty: ${sourcePenalty}`,
  ].join(" · ");
  container.append(scoreDetails);
}

function renderArticles(container, articles, { includeFeedback = false } = {}) {
  container.classList.remove("empty");
  container.replaceChildren();

  if (!articles || articles.length === 0) {
    container.classList.add("empty");
    container.textContent = "No articles found.";
    return;
  }

  articles.forEach((article) => {
    const node = elements.articleTemplate.content.firstElementChild.cloneNode(true);
    const title = node.querySelector(".article-title");
    const meta = node.querySelector(".meta");
    const topics = node.querySelector(".topics");
    const actions = node.querySelector(".feedback-actions");

    title.textContent = article.title;
    title.href = article.url;
    meta.textContent = `Source: ${article.source_name || "unknown"} · article_id: ${article.article_id || article.id}`;
    renderTopics(topics, article.topics || []);
    renderScoreBreakdown(node.querySelector(".article-main"), article);

    if (includeFeedback) {
      feedbackOptions.forEach((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = option.className;
        button.textContent = option.label;
        button.addEventListener("click", () => submitFeedback(article.article_id || article.id, option.value));
        actions.append(button);
      });
    } else {
      actions.remove();
    }

    container.append(node);
  });
}

function renderPreferences(preferences) {
  elements.preferencesList.classList.remove("empty");
  elements.preferencesList.replaceChildren();

  if (!preferences || preferences.length === 0) {
    elements.preferencesList.classList.add("empty");
    elements.preferencesList.textContent = "No preferences yet. Submit feedback on digest items to build them.";
    return;
  }

  preferences.forEach((preference) => {
    const row = document.createElement("div");
    row.className = "preference-item";
    row.innerHTML = `<strong></strong><span></span>`;
    row.querySelector("strong").textContent = preference.topic;
    row.querySelector("span").textContent = `weight: ${preference.weight}`;
    elements.preferencesList.append(row);
  });
}

async function createUser() {
  const email = elements.emailInput.value.trim();
  if (!email) {
    setStatus("Enter an email address.");
    return;
  }

  try {
    setStatus("Creating/reusing user...");
    const user = await apiFetch("/users", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    setSelectedUser(user.id);
    setStatus(`Selected ${user.email}.`);
    await Promise.all([loadPreferences(), loadDigest()]);
  } catch (error) {
    setStatus(`User request failed: ${error.message}`);
  }
}

async function loadDigest() {
  if (!requireUser()) return;
  try {
    elements.digestList.textContent = "Loading digest...";
    const digest = await apiFetch(`/digest/preview?user_id=${encodeURIComponent(state.userId)}`);
    renderArticles(elements.digestList, digest.items, { includeFeedback: true });
  } catch (error) {
    elements.digestList.classList.add("empty");
    elements.digestList.textContent = `Digest failed: ${error.message}`;
  }
}

async function submitFeedback(articleId, label) {
  if (!requireUser()) return;
  try {
    setStatus(`Sending ${label.toLowerCase()} feedback for article ${articleId}...`);
    await apiFetch("/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: Number(state.userId), article_id: Number(articleId), label }),
    });
    setStatus(`Saved feedback for article ${articleId}.`);
    await loadPreferences();
  } catch (error) {
    setStatus(`Feedback failed: ${error.message}`);
  }
}

async function loadPreferences() {
  if (!requireUser()) return;
  try {
    elements.preferencesList.textContent = "Loading preferences...";
    const preferences = await apiFetch(`/users/${encodeURIComponent(state.userId)}/preferences`);
    renderPreferences(preferences);
  } catch (error) {
    elements.preferencesList.classList.add("empty");
    elements.preferencesList.textContent = `Preferences failed: ${error.message}`;
  }
}

async function loadArticles() {
  try {
    elements.articlesList.textContent = "Loading recent articles...";
    const articles = await apiFetch("/articles?limit=20");
    renderArticles(elements.articlesList, articles);
  } catch (error) {
    elements.articlesList.classList.add("empty");
    elements.articlesList.textContent = `Articles failed: ${error.message}`;
  }
}

elements.createUserButton.addEventListener("click", createUser);
elements.loadDigestButton.addEventListener("click", loadDigest);
elements.loadPreferencesButton.addEventListener("click", loadPreferences);
elements.loadArticlesButton.addEventListener("click", loadArticles);
elements.emailInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") createUser();
});

setSelectedUser(state.userId);
loadArticles();
