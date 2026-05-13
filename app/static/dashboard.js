const state = {
  userId: localStorage.getItem("yournews_user_id") || "",
  userEmail: localStorage.getItem("yournews_user_email") || "",
  pendingFeedbackArticleId: null,
  feedbackByArticle: {},
};

const elements = {
  emailInput: document.querySelector("#email-input"),
  createUserButton: document.querySelector("#create-user-button"),
  signedInState: document.querySelector("#signed-in-state"),
  userStatus: document.querySelector("#user-status"),
  loadDigestButton: document.querySelector("#load-digest-button"),
  digestList: document.querySelector("#digest-list"),
  digestStatus: document.querySelector("#digest-status"),
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

function setDigestStatus(message) {
  elements.digestStatus.textContent = message;
}

function formatFeedbackLabel(value) {
  const option = feedbackOptions.find((item) => item.value === value);
  return option ? option.label : value;
}

function showDigestEmptyState(message) {
  elements.digestList.classList.add("empty");
  elements.digestList.textContent = message;
}

function setArticleFeedbackPending(articleNode, disabled) {
  const buttons = articleNode.querySelectorAll(".feedback-actions button");
  buttons.forEach((button) => {
    button.disabled = disabled;
  });
}

function setArticleFeedbackStatus(articleNode, message, isError = false) {
  const status = articleNode.querySelector(".feedback-status");
  status.textContent = message;
  status.classList.toggle("error", isError);
}

function markSelectedFeedback(articleNode, selectedValue) {
  articleNode.querySelectorAll(".feedback-actions button").forEach((button) => {
    button.classList.toggle("selected", button.dataset.feedbackValue === selectedValue);
  });
}

function setSelectedUser(user) {
  if (!user) {
    state.userId = "";
    state.userEmail = "";
    elements.signedInState.textContent = "Not signed in yet.";
    localStorage.removeItem("yournews_user_id");
    localStorage.removeItem("yournews_user_email");
    return;
  }

  state.userId = String(user.id || "");
  state.userEmail = user.email || state.userEmail;
  elements.signedInState.textContent = state.userEmail ? `Signed in as ${state.userEmail}` : "Signed in.";
  localStorage.setItem("yournews_user_id", state.userId);
  if (state.userEmail) {
    localStorage.setItem("yournews_user_email", state.userEmail);
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
    const message = "Enter an email to create or reuse a user, then your personalized digest will load here.";
    setStatus("Enter an email to get started.");
    setDigestStatus("");
    showDigestEmptyState(message);
    return false;
  }
  return true;
}

function renderTopics(container, topics) {
  container.replaceChildren();
  if (!topics || topics.length === 0) {
    const empty = document.createElement("span");
    empty.className = "topic-empty";
    empty.textContent = "No topics yet";
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

function renderArticles(container, articles, { includeFeedback = false } = {}) {
  container.classList.remove("empty");
  container.replaceChildren();

  if (!articles || articles.length === 0) {
    container.classList.add("empty");
    container.textContent = includeFeedback
      ? "No digest items yet. Ingest articles, then reload your digest."
      : "No recent articles found yet.";
    return;
  }

  articles.forEach((article) => {
    const articleId = article.article_id || article.id;
    const node = elements.articleTemplate.content.firstElementChild.cloneNode(true);
    const title = node.querySelector(".article-title");
    const meta = node.querySelector(".meta");
    const topics = node.querySelector(".topics");
    const panel = node.querySelector(".feedback-panel");
    const actions = node.querySelector(".feedback-actions");
    const savedFeedback = state.feedbackByArticle[articleId];

    node.dataset.articleId = articleId;
    title.textContent = article.title;
    title.href = article.url;
    meta.textContent = `Source: ${article.source_name || "Unknown source"}`;
    renderTopics(topics, article.topics || []);

    if (includeFeedback) {
      feedbackOptions.forEach((option) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `feedback-button ${option.className}`;
        button.dataset.feedbackValue = option.value;
        button.textContent = option.label;
        button.disabled = state.pendingFeedbackArticleId === articleId;
        button.addEventListener("click", () => submitFeedback(articleId, option.value, node));
        actions.append(button);
      });

      if (savedFeedback) {
        markSelectedFeedback(node, savedFeedback);
        setArticleFeedbackStatus(node, `Feedback saved: ${formatFeedbackLabel(savedFeedback)}`);
      }
    } else {
      panel.remove();
    }

    container.append(node);
  });
}

function renderPreferences(preferences) {
  elements.preferencesList.classList.remove("empty");
  elements.preferencesList.replaceChildren();

  if (!preferences || preferences.length === 0) {
    elements.preferencesList.classList.add("empty");
    elements.preferencesList.textContent = "No preferences yet. React to digest items to build them.";
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
    setStatus("Enter an email address to continue.");
    return;
  }

  try {
    setStatus("Signing you in...");
    const user = await apiFetch("/users", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    setSelectedUser(user);
    setStatus(`Signed in as ${user.email}`);
    await Promise.all([loadPreferences(), loadDigest()]);
  } catch (error) {
    setStatus(`Could not sign in: ${error.message}`);
  }
}

async function loadDigest() {
  if (!requireUser()) return;
  try {
    if (state.pendingFeedbackArticleId === null) {
      setDigestStatus("");
    }
    elements.digestList.textContent = "Loading your personalized digest...";
    const digest = await apiFetch(`/digest/preview?user_id=${encodeURIComponent(state.userId)}`);
    renderArticles(elements.digestList, digest.items, { includeFeedback: true });
  } catch (error) {
    elements.digestList.classList.add("empty");
    elements.digestList.textContent = `Could not load digest: ${error.message}`;
  }
}

async function submitFeedback(articleId, label, articleNode) {
  if (!requireUser() || state.pendingFeedbackArticleId !== null) return;
  try {
    state.pendingFeedbackArticleId = articleId;
    setArticleFeedbackPending(articleNode, true);
    markSelectedFeedback(articleNode, label);
    setArticleFeedbackStatus(articleNode, `Saving: ${formatFeedbackLabel(label)}...`);
    setDigestStatus("Saving feedback...");
    await apiFetch("/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: Number(state.userId), article_id: Number(articleId), label }),
    });
    state.feedbackByArticle[articleId] = label;
    setArticleFeedbackStatus(articleNode, `Feedback saved: ${formatFeedbackLabel(label)}`);
    setDigestStatus("Feedback saved. Refreshing preferences and digest...");
    await Promise.all([loadPreferences(), loadDigest()]);
    setDigestStatus("Feedback saved. Preferences and digest refreshed.");
  } catch (error) {
    setArticleFeedbackStatus(articleNode, `Feedback failed: ${error.message}`, true);
    setDigestStatus(`Feedback failed: ${error.message}`);
  } finally {
    state.pendingFeedbackArticleId = null;
    setArticleFeedbackPending(articleNode, false);
    document.querySelectorAll(".feedback-actions button").forEach((button) => {
      button.disabled = false;
    });
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
    elements.preferencesList.textContent = `Could not load preferences: ${error.message}`;
  }
}

async function loadArticles() {
  try {
    elements.articlesList.textContent = "Loading recent articles...";
    const articles = await apiFetch("/articles?limit=20");
    renderArticles(elements.articlesList, articles);
  } catch (error) {
    elements.articlesList.classList.add("empty");
    elements.articlesList.textContent = `Could not load recent articles: ${error.message}`;
  }
}

elements.createUserButton.addEventListener("click", createUser);
elements.loadDigestButton.addEventListener("click", loadDigest);
elements.loadPreferencesButton.addEventListener("click", loadPreferences);
elements.loadArticlesButton.addEventListener("click", loadArticles);
elements.emailInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") createUser();
});

if (state.userId) {
  setSelectedUser({ id: state.userId, email: state.userEmail });
} else {
  setSelectedUser(null);
}
loadArticles();
