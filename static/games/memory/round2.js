/**
 * Round 2: Pattern appears sequentially (with occasional orange distractions).
 * Players recreate the blue pattern in any order. Results are logged through
 * memory_game.js for later processing.
 */

import {
    clearGrid,
    showIntro,
    hideIntro,
    startTimer,
    stopTimer,
    hideCanvas,
    showCanvas,
    canvas,
    ctx,
    showFeedback,
} from './gameFlow.js';
import { logMemoryQuestion } from './memory_game.js';

const roundLength = 60;
const gridSize = 5;

let currentPattern = [];
let userPattern = [];
let questionIndex = 0;
let sequenceLength = 5;
let canClick = false;
let isRoundActive = false;
let attemptsForQuestion = 0;

function handleCanvasClickRound2(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / gridSize));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / gridSize));

    handlePatternClick(x, y);
}

export function initRound2(onRoundComplete) {
    resetState();
    clearGrid();
    showCanvas();

    canvas.addEventListener("click", handleCanvasClickRound2);

    showIntro(
        "Get Ready for Round 2! Watch the dots appear, then replicate the blue ones.",
        () => startRound(onRoundComplete)
    );
}

function resetState() {
    currentPattern = [];
    userPattern = [];
    questionIndex = 0;
    sequenceLength = 5;
    canClick = false;
    isRoundActive = false;
    attemptsForQuestion = 0;
}

function startRound(onRoundComplete) {
    isRoundActive = true;
    startTimer(roundLength, () => handleTimeOut(onRoundComplete));
    nextQuestion();
}

function endRound(onRoundComplete) {
    isRoundActive = false;
    stopTimer();
    canClick = false;
    canvas.removeEventListener("click", handleCanvasClickRound2);
    hideCanvas();
    clearGrid();
    setTimeout(onRoundComplete, 500);
}

function handleTimeOut(onRoundComplete) {
    canClick = false;
    isRoundActive = false;
    showFeedback("Time's Up!", false, 800, () => endRound(onRoundComplete));
}

function nextQuestion() {
    if (!isRoundActive) return;

    attemptsForQuestion = 0;
    userPattern = [];
    questionIndex += 1;

    if (questionIndex > 1 && (questionIndex - 1) % 3 === 0) {
        sequenceLength = Math.min(sequenceLength + 1, 22);
    }

    generatePattern(sequenceLength);
    if (questionIndex > 3 && Math.random() < 0.95) {
        addDistractions();
    }

    displaySequentialPattern();
}

function generatePattern(length) {
    currentPattern = [];
    while (currentPattern.length < length) {
        const x = Math.floor(Math.random() * gridSize);
        const y = Math.floor(Math.random() * gridSize);
        if (!currentPattern.some(([px, py]) => px === x && py === y)) {
            currentPattern.push([x, y, "blue"]);
        }
    }
}

function addDistractions() {
    const distractionCount = Math.floor(Math.random() * 3) + 1;
    const distractions = [];

    while (distractions.length < distractionCount) {
        const x = Math.floor(Math.random() * gridSize);
        const y = Math.floor(Math.random() * gridSize);

        if (!currentPattern.some(([px, py]) => px === x && py === y) &&
            !distractions.some(([dx, dy]) => dx === x && dy === y)) {
            distractions.push([x, y, "orange"]);
        }
    }

    distractions.forEach(distraction => {
        const insertIndex = Math.floor(Math.random() * (currentPattern.length + 1));
        currentPattern.splice(insertIndex, 0, distraction);
    });
}

function displaySequentialPattern() {
    let delay = 0;
    currentPattern.forEach(([x, y, color]) => {
        const randomDelay = Math.floor(Math.random() * 200) + 500;
        setTimeout(() => {
            clearGrid();
            drawDot(x, y, color);
        }, delay);
        delay += randomDelay;
    });

    setTimeout(() => {
        clearGrid();
        canClick = true;
    }, delay);
}

function handlePatternClick(x, y) {
    if (userPattern.some(([ux, uy]) => ux === x && uy === y)) {
        return;
    }

    const isCorrectClick = currentPattern.some(([px, py, pcolor]) => px === x && py === y && pcolor === "blue");

    if (isCorrectClick) {
        userPattern.push([x, y, "blue"]);
        drawDot(x, y, "blue");

        const isPatternComplete = currentPattern
            .filter(([px, py, pcolor]) => pcolor === "blue")
            .every(([px, py, pcolor]) =>
                userPattern.some(([ux, uy, ucolor]) => ux === px && uy === py && ucolor === pcolor)
            );

        if (isPatternComplete) {
            attemptsForQuestion += 1;
            canClick = false;
            logMemoryQuestion({
                round: 2,
                questionIndex,
                wasCorrect: true,
                attempts: attemptsForQuestion,
                sequenceLength,
            });
            showFeedback("Correct!", true, 800, () => {
                clearGrid();
                setTimeout(nextQuestion, 400);
            });
        }
    } else {
        attemptsForQuestion += 1;
        canClick = false;
        revealBluePattern();
        logMemoryQuestion({
            round: 2,
            questionIndex,
            wasCorrect: false,
            attempts: attemptsForQuestion,
            sequenceLength,
        });
        showFeedback("Incorrect! Here is the correct pattern:", false, 800, () => {
            clearGrid();
            setTimeout(nextQuestion, 400);
        });
    }
}

function revealBluePattern() {
    clearGrid();
    currentPattern
        .filter(([x, y, color]) => color === "blue")
        .forEach(([x, y]) => drawDot(x, y, "green"));
}

function drawDot(x, y, color = "blue") {
    const cellSize = canvas.width / gridSize;
    ctx.beginPath();
    ctx.arc(x * cellSize + cellSize / 2, y * cellSize + cellSize / 2, cellSize / 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}
