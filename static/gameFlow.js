// Canvas and Context
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

// Elements
const introDisplay = document.getElementById("introDisplay");
const feedbackOverlay = document.getElementById("feedbackOverlay");
const timerDisplay = document.getElementById("timerDisplay");

// Game variables
let roundTimer;
const gridSize = 5; // 5x5 grid

// Initialize and resize the canvas
function initCanvas() {
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();
}

// Resize the canvas to fit the window
function resizeCanvas() {
    const size = Math.min(window.innerWidth * 0.8, window.innerHeight * 0.8);
    canvas.width = size;
    canvas.height = size;
    drawGrid();
}

// Show intro with customizable text
function showIntro(message) {
    introDisplay.innerHTML = `<h2>${message}</h2>`;
    introDisplay.style.display = "block";
    timerDisplay.style.display = "none";
}

// Hide the intro display
function hideIntro() {
    introDisplay.style.display = "none";
}

// Timer setup and management
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

// Stop the timer
function stopTimer() {
    clearInterval(roundTimer);
    timerDisplay.style.display = "none";
}


// Function to hide the canvas and clear the grid
function hideCanvas() {
    clearGrid();
    canvas.style.visibility = "hidden"; // Hide the canvas element
}

// Function to show the canvas (used at the start of each round)
function showCanvas() {
    canvas.style.visibility = "visible"; // Make the canvas visible
}


// Function to draw a constant 5x5 grid on the new canvas
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

// Function to clear the grid
function clearGrid() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid();
}

// Export all needed elements and functions
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
    showCanvas
};