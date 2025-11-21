/**
 * Shared helpers for the memory game canvas, overlays, and timers.
 * This file owns the canvas state while rounds import its functions
 * to draw, resize, show overlays, and manage the round timer.
 */

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

const introDisplay = document.getElementById("introDisplay");
const feedbackOverlay = document.getElementById("feedbackOverlay");
const timerDisplay = document.getElementById("timerDisplay");

let roundTimer;
const gridSize = 5;

function initCanvas() {
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();
}

function resizeCanvas() {
    const size = Math.min(window.innerWidth * 0.8, window.innerHeight * 0.8);
    canvas.width = size;
    canvas.height = size;
    drawGrid();
}

function drawGrid() {
    const cellSize = canvas.width / gridSize;
    ctx.strokeStyle = "#ddd";
    ctx.lineWidth = 1;
    for (let i = 1; i < gridSize; i++) {
        ctx.beginPath();
        ctx.moveTo(i * cellSize, 0);
        ctx.lineTo(i * cellSize, canvas.height);
        ctx.moveTo(0, i * cellSize);
        ctx.lineTo(canvas.width, i * cellSize);
        ctx.stroke();
    }
}

function clearGrid() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid();
}

function showIntro(message) {
    introDisplay.innerHTML = `<h2>${message}</h2>`;
    introDisplay.style.display = "block";
    timerDisplay.style.display = "none";
}

function hideIntro() {
    introDisplay.style.display = "none";
}

function startTimer(roundLength, onTimeOut) {
    let gameTime = roundLength;
    timerDisplay.textContent = `Time Left: ${gameTime}s`;
    timerDisplay.style.display = "block";

    clearInterval(roundTimer);
    roundTimer = setInterval(() => {
        gameTime--;
        timerDisplay.textContent = `Time Left: ${gameTime}s`;

        if (gameTime <= 0) {
            clearInterval(roundTimer);
            onTimeOut();
        }
    }, 1000);
}

function stopTimer() {
    clearInterval(roundTimer);
    timerDisplay.style.display = "none";
}

function hideCanvas() {
    clearGrid();
    canvas.style.visibility = "hidden";
}

function showCanvas() {
    canvas.style.visibility = "visible";
}

function showFeedback(message, isCorrect, duration = 800, callback) {
    feedbackOverlay.textContent = message;
    feedbackOverlay.style.display = "block";
    feedbackOverlay.style.color = isCorrect ? "green" : "red";
    feedbackOverlay.style.fontSize = "2em";

    setTimeout(() => {
        feedbackOverlay.style.display = "none";
        if (callback) callback();
    }, duration);
}

export {
    initCanvas,
    resizeCanvas,
    drawGrid,
    clearGrid,
    showIntro,
    hideIntro,
    startTimer,
    stopTimer,
    canvas,
    ctx,
    introDisplay,
    feedbackOverlay,
    timerDisplay,
    hideCanvas,
    showCanvas,
    showFeedback,
};
