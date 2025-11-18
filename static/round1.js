import {
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
let userPattern = [];
let questionCount = 0;
let sequenceLength = 5;
const roundLength = 30;//30;
let canClick = false;
let isRoundActive = false;

function handleCanvasClick(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / 5));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / 5));
    handlePatternClick(x, y);
}

// Initialize Round 1
export function initRound1(callback) {
    clearGrid();
    showCanvas();

    // Attach the event listener
    canvas.addEventListener("click", handleCanvasClick);

    showIntro("Get Ready for Round 1! Memorize the pattern and replicate it.");
    setTimeout(() => {
        hideIntro();
        startRound(callback);
    }, 2000);
}


function startRound(callback) {
    console.log("Starting Round 2");
    questionCount = 0;
    sequenceLength = 5;
    canClick = false;
    isRoundActive = true; // Set the round as active

    startRoundTimer(callback);
    if (isRoundActive) {
        nextQuestion();
    }
}

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
            isRoundActive = false; // Set the round as inactive
            showFeedback("Time's Up!", false);
            setTimeout(() => endRound(callback), 1200);
        }
    }, 1000);
}
function endRound(callback) {
    console.log("Ending Round 1");

    // Stop the timer and clear the canvas
    stopTimer();
    hideCanvas();
    clearGrid();

    // Remove the click event listener
    canvas.removeEventListener("click", handleCanvasClick);
    console.log('End of Round 1');

    // Proceed to the next round after a short delay
    setTimeout(callback, 1000); // Pass to memory_game.js
}



// Generate and display the pattern
function nextQuestion() {
    userPattern = [];
    generatePattern(sequenceLength);
    displayPattern();

    // Add distractions with a 65% chance after the fourth question
    if (questionCount >= 4 && Math.random() < 0.65) {
        addDistractions();
    }

    // Increment sequence length every 3 questions
    if (questionCount > 0 && questionCount % 3 === 0) {
        sequenceLength = Math.min(sequenceLength + 1, 22);
    }

    questionCount++;
}

// Generate a random pattern with a given length
function generatePattern(length) {
    currentPattern = [];
    while (currentPattern.length < length) {
        const x = Math.floor(Math.random() * gridSize);
        const y = Math.floor(Math.random() * gridSize);
        if (!currentPattern.some(([px, py]) => px === x && py === y)) {
            currentPattern.push([x, y]);
        }
    }
}

// Display the pattern briefly, then enable user input
function displayPattern() {
    clearGrid();
    currentPattern.forEach(([x, y]) => drawDot(x, y, "blue"));

    setTimeout(() => {
        clearGrid();
        canClick = true;
    }, 500);
}

// Check if the user clicked correctly
function handlePatternClick(x, y) {
    const isCorrectClick = currentPattern.some(([px, py]) => px === x && py === y);

    if (isCorrectClick) {
        if (userPattern.some(([ux, uy]) => ux === x && uy === y)) return;

        userPattern.push([x, y]);
        drawDot(x, y, "blue");

        const isPatternComplete = currentPattern.every(([px, py]) =>
            userPattern.some(([ux, uy]) => ux === px && uy === py)
        );

        if (isPatternComplete) {
            showFeedback("Correct!", true);
            canClick = false;
            setTimeout(nextQuestion, 1000);
        }
    } else {
        showFeedback("Incorrect! Here is the correct pattern:", false);
    }
}

// Show feedback and display the correct pattern briefly
function showFeedback(message, isCorrect) {
    canClick = false;
    feedbackOverlay.textContent = message;
    feedbackOverlay.style.display = "block";
    feedbackOverlay.style.color = isCorrect ? "green" : "red";
    feedbackOverlay.style.fontSize = "2em";

    clearGrid();

    // Show correct pattern in green if the answer was incorrect
    if (!isCorrect) {
        currentPattern.forEach(([x, y]) => drawDot(x, y, "green"));
    }

    setTimeout(() => {
        feedbackOverlay.style.display = "none";
        clearGrid();
        // Move to the next question if the answer was incorrect
        if (!isCorrect) setTimeout(nextQuestion, 1000);
    }, 800);
}

// Draw a dot on the canvas
function drawDot(x, y, color = "blue") {
    const cellSize = canvas.width / gridSize;
    ctx.beginPath();
    ctx.arc(x * cellSize + cellSize / 2, y * cellSize + cellSize / 2, cellSize / 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

function addDistractions() {
    // Set the maximum number of distractions based on the number of questions answered
    const maxDistractions = Math.min(5, 2 + Math.floor(questionCount / 3));
    
    // Set the distraction count with a higher chance for more distractions as question count increases
    const distractionCount = Math.max(2, Math.floor(Math.random() * maxDistractions));

    const distractions = [];
    while (distractions.length < distractionCount) {
        const x = Math.floor(Math.random() * gridSize);
        const y = Math.floor(Math.random() * gridSize);

        if (
            !currentPattern.some(([px, py]) => px === x && py === y) &&
            !distractions.some(([dx, dy]) => dx === x && dy === y)
        ) {
            distractions.push([x, y]);
            drawDot(x, y, "orange");
        }
    }
}
