import {
    drawGrid,
    clearGrid,
    showIntro,
    hideIntro,
    stopTimer,
    hideCanvas,
    showCanvas,
    canvas,
    ctx,
    feedbackOverlay,
    timerDisplay,
} from './gameFlow.js';


const gridSize = 5;
let currentPattern = [];
let rotatedTriangle = null;
let questionCount = 0;
let triangleCount = 6;
let canClick = false;
const roundLength = 20;
const initialRotationAngles = [45, 135, 225, 315];
const extraRotationAngles = [90, 180, 270];
let dummyTriangleCount = 3;

// Attach the click handler
function handleCanvasClick(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / gridSize));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / gridSize));
    handleTriangleClick(x, y);
}

// Initialize Round 3
export function initRound3(callback) {
    clearGrid();
    showCanvas();

    // Attach the event listener
    canvas.addEventListener("click", handleCanvasClick);

    showIntro("Round 3: Find and click the rotated triangle. Ignore the orange triangles.");
    setTimeout(() => {
        hideIntro();
        startRound(callback);
    }, 2000);
}

// Start the round and timer
function startRound(callback) {
    questionCount = 0;
    triangleCount = 6;
    canClick = false;
    startRoundTimer(callback);
    displayInitialTriangles();
}

// Start the round timer
function startRoundTimer(callback) {
    let gameTime = roundLength;
    timerDisplay.textContent = `Time Left: ${gameTime}s`;
    timerDisplay.style.display = "block";

    const roundTimer = setInterval(() => {
        gameTime--;
        timerDisplay.textContent = `Time Left: ${gameTime}s`;

        if (gameTime <= 0) {
            clearInterval(roundTimer);
            timerDisplay.style.display = "none";
            canClick = false;
            showFeedback("Time's Up!", false, () => endRound(callback));
        }
    }, 1000);
}

// End the round
function endRound(callback) {
    stopTimer();
    hideCanvas();
    clearGrid();

    // Remove the click event listener
    canvas.removeEventListener("click", handleCanvasClick);

    // Proceed to the next round
    setTimeout(callback, 1000);
}

// Display the initial triangles
function displayInitialTriangles() {
    clearGrid();
    drawGrid();

    currentPattern = [];
    const positions = generateUniquePositions(triangleCount, []);

    positions.forEach(([x, y]) => {
        const initialRotation = getRandomElement(initialRotationAngles);
        currentPattern.push([x, y, initialRotation]);
        drawTriangle(x, y, initialRotation, "blue");
    });

    addDummyTriangles();

    // Hide triangles briefly, then show with one rotated
    setTimeout(() => {
        clearGrid();
        drawGrid();
        setTimeout(displayWithRotatedTriangle, 500);
    }, 1000);
}

// Redisplay triangles with one rotated
function displayWithRotatedTriangle() {
    if (currentPattern.length === 0) {
        console.error("Error: currentPattern is empty.");
        return;
    }

    clearGrid();
    drawGrid();

    const rotatedIndex = Math.floor(Math.random() * currentPattern.length);
    const additionalRotation = getRandomElement(extraRotationAngles);

    currentPattern.forEach(([x, y, rotation], index) => {
        const newRotation = index === rotatedIndex ? rotation + additionalRotation : rotation;
        drawTriangle(x, y, newRotation, "blue");
        if (index === rotatedIndex) {
            rotatedTriangle = [x, y, newRotation];
        }
    });

    addDummyTriangles();
    canClick = true;
}

// Add dummy triangles
function addDummyTriangles() {
    const dummyPositions = generateUniquePositions(
        dummyTriangleCount,
        currentPattern.map(([x, y]) => [x, y])
    );

    dummyPositions.forEach(([x, y]) => {
        const rotation = getRandomElement(initialRotationAngles);
        drawTriangle(x, y, rotation, "orange");
    });
}

// Handle user clicks
function handleTriangleClick(x, y) {
    if (x === rotatedTriangle[0] && y === rotatedTriangle[1]) {
        showFeedback("Correct!", true, displayInitialTriangles);
    } else {
        showFeedback("Incorrect!", false, displayInitialTriangles);
    }
}

// Show feedback and optionally proceed to the next question
function showFeedback(message, isCorrect, callback) {
    canClick = false;
    feedbackOverlay.textContent = message;
    feedbackOverlay.style.display = "block";
    feedbackOverlay.style.color = isCorrect ? "green" : "red";
    feedbackOverlay.style.fontSize = "2em";

    clearGrid();

    // Ensure rotatedTriangle is valid before trying to draw it
    if (!isCorrect && rotatedTriangle) {
        drawTriangle(rotatedTriangle[0], rotatedTriangle[1], rotatedTriangle[2], "green");
    }

    setTimeout(() => {
        feedbackOverlay.style.display = "none";
        clearGrid();
        if (callback) setTimeout(callback, 1000);
    }, 800);
}


// Utility: Generate unique positions
function generateUniquePositions(count, excludePositions) {
    const positions = [];
    while (positions.length < count) {
        const x = Math.floor(Math.random() * gridSize);
        const y = Math.floor(Math.random() * gridSize);
        if (
            !positions.some(([px, py]) => px === x && py === y) &&
            !excludePositions.some(([px, py]) => px === x && py === y)
        ) {
            positions.push([x, y]);
        }
    }
    return positions;
}

// Utility: Get a random element from an array
function getRandomElement(array) {
    return array[Math.floor(Math.random() * array.length)];
}

// Draw a triangle
function drawTriangle(x, y, rotation = 0, color = "blue") {
    const cellSize = canvas.width / gridSize;
    const cx = x * cellSize + cellSize / 2;
    const cy = y * cellSize + cellSize / 2;
    const size = cellSize / 3;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate((rotation * Math.PI) / 180);
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size, size);
    ctx.lineTo(-size, size);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();
}
