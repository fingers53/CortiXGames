/**
 * Orchestrates the three rounds of the memory game.
 * Initializes the canvas, chains the round modules, and records per-question
 * events so later phases can submit the log to the backend.
 */

import { initCanvas, hideCanvas } from './gameFlow.js';
import { initRound1 } from './round1.js';
import { initRound2 } from './round2.js';
import { initRound3 } from './round3.js';

export const questionLog = [];
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
const usernameRegex = /^[A-Za-z0-9_]{3,20}$/;

export function logMemoryQuestion(event) {
    questionLog.push(event);
}

export function endMemoryGame() {
    hideCanvas();
    const username = localStorage.getItem("username") || "";

    fetch("/memory-game/submit_score", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ username, questionLog }),
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.status === "success") {
                showMemoryEndScreen(data.finalScore);
            } else {
                console.error("Error saving memory score:", data);
                showMemoryEndScreen(null);
            }
        })
        .catch((err) => {
            console.error("Error submitting memory score:", err);
            showMemoryEndScreen(null);
        });
}

export function startMemoryGame() {
    const saved = localStorage.getItem("username") || "";
    if (!usernameRegex.test(saved)) {
        alert("Please choose a valid username first.");
        window.location.href = "/";
        return;
    }
    questionLog.length = 0;
    initCanvas();
    initRound1(() => initRound2(() => initRound3(() => endMemoryGame())));
}

window.addEventListener("DOMContentLoaded", startMemoryGame);

function showMemoryEndScreen(finalScore) {
    const timerDisplay = document.getElementById("timerDisplay");
    const introDisplay = document.getElementById("introDisplay");
    const feedbackOverlay = document.getElementById("feedbackOverlay");
    const endScreen = document.getElementById("memoryEndScreen");

    if (timerDisplay) timerDisplay.style.display = "none";
    if (introDisplay) introDisplay.style.display = "none";
    if (feedbackOverlay) feedbackOverlay.style.display = "none";
    if (!endScreen) return;

    const scoreSection =
        finalScore === null
            ? `<p class="end-score">Score saved locally. Server unavailable.</p>`
            : `<p class="end-score">Your score: ${finalScore}</p>`;

    endScreen.innerHTML = `
        <div class="end-card">
            <h2>Memory Game Finished!</h2>
            ${scoreSection}
            <div class="end-actions">
                <button onclick="window.location.href='/memory-game'">Play Again</button>
                <button onclick="window.location.href='/'">Home</button>
                <button onclick="window.location.href='/leaderboard/memory-game'">Leaderboard</button>
            </div>
        </div>
    `;

    endScreen.style.display = "block";
}
