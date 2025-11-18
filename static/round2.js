import {
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
} from './gameFlow.js';

let currentPattern = [];
let userPattern = [];
let questionCount = 0;
let sequenceLength = 5;
const roundLength = 60;
let canClick = false;
let isRoundActive = false;


function handleCanvasClickRound2(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / 5));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / 5));

    handlePatternClick(x, y);
}

// Initialize Round 2
export function initRound2(callback) {
    clearGrid();
    showCanvas();

    // Attach the event listener
    canvas.addEventListener("click", handleCanvasClickRound2);

    showIntro("Get Ready for Round 2! Watch the dots appear sequentially, then replicate the pattern. Ignore any orange dots!");
    setTimeout(() => {
        hideIntro();
        startRound(callback);
    }, 2000);
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
            isRoundActive = false; // Set the round as inactive
            showFeedback("Time's Up!", false);
            setTimeout(() => endRound(callback), 1200);
        }
    }, 1000);
}

function startRound(callback) {
    console.log("Starting Round 2");
    questionCount = 0;
    sequenceLength = 5;
    canClick = false;
    isRoundActive = true; // Set the round as active

    startRoundTimer(callback);
    nextQuestion(); // Initial call to start the first question
}
// End the round and reset
function endRound(callback) {
    console.log("Ending Round 2");

    // Stop the timer and clear the canvas
    stopTimer();
    hideCanvas();
    clearGrid();

    // Set the round as inactive
    isRoundActive = false;

    // Proceed to the next round after a short delay
    setTimeout(callback, 1000); // Pass to memory_game.js
}

// Check if the user clicked correctly (order doesn't matter)
function handlePatternClick(x, y) {
    if (userPattern.some(([ux, uy]) => ux === x && uy === y)) {
        console.log("Click ignored: already recorded this dot.");
        return;
    }

    const isCorrectClick = currentPattern.some(([px, py, pcolor]) => px === x && py === y && pcolor === "blue");

    if (isCorrectClick) {
        userPattern.push([x, y, "blue"]);
        drawDot(x, y, "blue");
        console.log(`Correct click at (${x}, ${y}). User pattern so far:`, JSON.stringify(userPattern));

        const isPatternComplete = currentPattern
            .filter(([px, py, pcolor]) => pcolor === "blue")
            .every(([px, py, pcolor]) =>
                userPattern.some(([ux, uy, ucolor]) => ux === px && uy === py && ucolor === pcolor)
            );

        if (isPatternComplete) {
            console.log("Pattern complete. Showing correct feedback.");
            showFeedback("Correct!", true);
            canClick = false;
            setTimeout(nextQuestion, 1000);
        }
    } else {
        console.log(`Incorrect feedback triggered for click at (${x}, ${y}). Current pattern:`, JSON.stringify(currentPattern));
        showFeedback("Incorrect! Here is the correct pattern:", false);
    }
}

// Show feedback and display the correct pattern briefly
function showFeedback(message, isCorrect) {
    canClick = false;
    feedbackOverlay.textContent = message;
    feedbackOverlay.style.display = "block";
    feedbackOverlay.style.color = isCorrect ? "green" : "red";

    clearGrid();
    if (!isCorrect) {
        console.log("Displaying correct pattern in green for feedback.");
        // Only show blue dots in green
        currentPattern
            .filter(([x, y, color]) => color === "blue")
            .forEach(([x, y]) => drawDot(x, y, "green"));
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
    const cellSize = canvas.width / 5;
    ctx.beginPath();
    ctx.arc(x * cellSize + cellSize / 2, y * cellSize + cellSize / 2, cellSize / 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

// Updated function to add distractions to the pattern
function addDistractions() {
    const distractionCount = Math.floor(Math.random() * 3) + 1; // Between 1 and 3 distractions
    console.log(`Adding ${distractionCount} distractions.`);
    const distractions = [];

    while (distractions.length < distractionCount) {
        const x = Math.floor(Math.random() * 5);
        const y = Math.floor(Math.random() * 5);

        // Ensure distractions do not overlap with the main pattern or other distractions
        if (!currentPattern.some(([px, py]) => px === x && py === y) &&
            !distractions.some(([dx, dy]) => dx === x && dy === y)) {
            distractions.push([x, y, "orange"]);
        }
    }

    // Randomly insert distractions into the current pattern
    distractions.forEach(distraction => {
        const insertIndex = Math.floor(Math.random() * (currentPattern.length + 1));
        currentPattern.splice(insertIndex, 0, distraction);
    });

    console.log("Updated pattern with distractions:", JSON.stringify(currentPattern));
}

// Updated function to display the sequence (including distractions)
function displaySequentialPattern() {
    console.log("Displaying pattern sequentially:", JSON.stringify(currentPattern));

    let delay = 0;
    currentPattern.forEach(([x, y, color]) => {
        const randomDelay = Math.floor(Math.random() * 200) + 500; // Vary delay between 500ms and 700ms
        setTimeout(() => {
            clearGrid();
            drawDot(x, y, color);
            console.log(`Displaying dot at (${x}, ${y}) in color ${color}`);
        }, delay);
        delay += randomDelay;
    });

    setTimeout(() => {
        clearGrid();
        canClick = true;
        console.log("Pattern display complete. Clicks are now enabled.");
    }, delay);
}

// Updated function to generate a pattern
function generatePattern(length) {
    currentPattern = [];
    while (currentPattern.length < length) {
        const x = Math.floor(Math.random() * 5);
        const y = Math.floor(Math.random() * 5);
        if (!currentPattern.some(([px, py]) => px === x && py === y)) {
            currentPattern.push([x, y, "blue"]); // Main pattern dots are blue
        }
    }
    console.log("Generated base pattern:", JSON.stringify(currentPattern));
}

// Updated nextQuestion function to ensure distractions are added into the sequence
function nextQuestion() {
    if (!isRoundActive) {
        console.log("Round is not active. nextQuestion will not be called.");
        return;
    }

    console.log(`Question ${questionCount + 1} with sequence length ${sequenceLength}`);
    userPattern = [];
    canClick = false;

    // Increment sequence length every 3 questions
    if (questionCount > 0 && questionCount % 3 === 0) {
        sequenceLength = Math.min(sequenceLength + 1, 22);
        console.log(`Increasing sequence length to ${sequenceLength}`);
    }

    generatePattern(sequenceLength);

    // Add distractions to the pattern after the 3rd question
    if (questionCount >= 3 && Math.random() < 0.95) {
        addDistractions();
    }

    displaySequentialPattern();
    questionCount++;
}

