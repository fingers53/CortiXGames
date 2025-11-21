/**
 * Landing page utilities for username handling and navigation.
 * Provides validation for usernames and gates game navigation on a saved username
 * stored in localStorage under the "username" key.
 */

const USERNAME_KEY = "username";
const bestReaction = document.getElementById("best-reaction");
const bestMemory = document.getElementById("best-memory");

function validateUsername(name) {
    const usernameRegex = /^[A-Za-z0-9_]{3,20}$/;
    return usernameRegex.test(name);
}

function confirmUsername() {
    const usernameInput = document.getElementById("username");
    const enterButton = document.getElementById("enter-button");
    if (!usernameInput) return;

    const chosen = usernameInput.value.trim();
    if (!validateUsername(chosen)) {
        alert("Please choose a username (3–20 letters, digits, underscore).");
        return;
    }

    localStorage.setItem(USERNAME_KEY, chosen);
    usernameInput.value = chosen;
    usernameInput.disabled = true;
    usernameInput.style.backgroundColor = "#f0f0f0";
    usernameInput.style.color = "#555";

    if (enterButton) {
        enterButton.style.display = "none";
    }

    fetchBestScores();
}

function getSavedUsername() {
    return localStorage.getItem(USERNAME_KEY);
}

function ensureUsernameOrAlert() {
    const saved = getSavedUsername();
    if (!validateUsername(saved || "")) {
        alert("Please choose a valid username first.");
        return false;
    }
    return true;
}

function attachNavigation(buttonId, path) {
    const button = document.getElementById(buttonId);
    if (!button) return;
    button.addEventListener("click", () => {
        if (ensureUsernameOrAlert()) {
            window.location.href = path;
        }
    });
}

function hydrateUsernameField() {
    const usernameInput = document.getElementById("username");
    const enterButton = document.getElementById("enter-button");
    const savedUsername = getSavedUsername();

    if (!usernameInput) return;

    if (savedUsername) {
        usernameInput.value = savedUsername;
        usernameInput.disabled = true;
        usernameInput.style.backgroundColor = "#f0f0f0";
        usernameInput.style.color = "#555";
        if (enterButton) {
            enterButton.style.display = "none";
        }
    }
}

function renderBestScores(reactionBest, memoryBest) {
    if (bestReaction) {
        bestReaction.textContent = `Best Reaction: ${reactionBest ?? "–"}`;
    }
    if (bestMemory) {
        bestMemory.textContent = `Best Memory: ${memoryBest ?? "–"}`;
    }
}

function fetchBestScores() {
    const username = getSavedUsername();
    if (!validateUsername(username || "")) return;

    fetch(`/api/my-best-scores?username=${encodeURIComponent(username)}`)
        .then((res) => res.json())
        .then((data) => {
            renderBestScores(data.reaction_best, data.memory_best);
        })
        .catch((err) => console.error("Failed to fetch best scores:", err));
}

window.addEventListener("DOMContentLoaded", () => {
    hydrateUsernameField();
    fetchBestScores();
    attachNavigation("memory-button", "/memory-game");
    attachNavigation("reaction-button", "/reaction-game");
});

window.confirmUsername = confirmUsername;
