const USERNAME_KEY = "username";
const bodyEl = document.body;
const isLoggedIn = (bodyEl?.dataset?.loggedIn || "false") === "true";
const prefillUsername = bodyEl?.dataset?.prefillUsername || "";
const bestReaction = document.getElementById("best-reaction");
const bestMemory = document.getElementById("best-memory");
const bestScoresContainer = document.getElementById("best-scores");
const passwordUpgrade = document.getElementById("password-upgrade");
const passwordUsernameInput = document.getElementById("password-username");

function togglePasswordUpgrade(username) {
    const valid = validateUsername(username || "");
    if (!passwordUpgrade) return;

    if (isLoggedIn) {
        passwordUpgrade.style.display = "none";
        return;
    }

    if (valid) {
        passwordUpgrade.style.display = "block";
        if (passwordUsernameInput) {
            passwordUsernameInput.value = username;
        }
    } else {
        passwordUpgrade.style.display = "none";
        if (passwordUsernameInput) {
            passwordUsernameInput.value = "";
        }
    }
}

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

    togglePasswordUpgrade(chosen);

    if (enterButton) {
        enterButton.style.display = "none";
    }

    // Now that we have a valid username, fetch best scores
    fetchBestScores();
}

function getSavedUsername() {
    // If the backend says the user is logged OUT, ignore whatever is in localStorage.
    if (!isLoggedIn) {
        return null;
    }
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
    if (!getSavedUsername() && validateUsername(prefillUsername || "")) {
        localStorage.setItem(USERNAME_KEY, prefillUsername);
    }

    const savedUsername = getSavedUsername() || prefillUsername;

    if (!usernameInput) return;

    if (savedUsername && validateUsername(savedUsername)) {
        usernameInput.value = savedUsername;
        usernameInput.disabled = true;
        usernameInput.style.backgroundColor = "#f0f0f0";
        usernameInput.style.color = "#555";
        if (enterButton) {
            enterButton.style.display = "none";
        }
        togglePasswordUpgrade(savedUsername);
        // we *might* have scores; fetch them and show container only if they exist
        fetchBestScores();
    } else {
        // no valid username → hide the block
        if (bestScoresContainer) {
            bestScoresContainer.style.display = "none";
        }
        togglePasswordUpgrade("");
    }
}

function renderBestScores(reactionBest, memoryBest) {
    const hasReaction = reactionBest != null;
    const hasMemory = memoryBest != null;

    // If we have no scores at all, keep it hidden
    if (!hasReaction && !hasMemory) {
        if (bestScoresContainer) {
            bestScoresContainer.style.display = "none";
        }
        return;
    }

    if (bestScoresContainer) {
        bestScoresContainer.style.display = "block";
    }

    if (bestReaction && hasReaction) {
        bestReaction.textContent = `Best Reaction: ${reactionBest}`;
    }

    if (bestMemory && hasMemory) {
        bestMemory.textContent = `Best Memory: ${memoryBest}`;
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
        .catch((err) => {
            console.error("Failed to fetch best scores:", err);
            // on error, hide rather than show junk
            if (bestScoresContainer) {
                bestScoresContainer.style.display = "none";
            }
        });
}

window.addEventListener("DOMContentLoaded", () => {
    hydrateUsernameField();
    attachNavigation("memory-button", "/memory-game");
    attachNavigation("reaction-button", "/reaction-game");
    attachNavigation("yetamax-button", "/math-game/yetamax");
});

window.confirmUsername = confirmUsername;