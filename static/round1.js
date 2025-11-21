/**
 * Round 1: Player memorizes a pattern of dots and recreates it on the grid.
 * Uses shared helpers from gameFlow.js and reports per-question results to
 * memory_game.js via logMemoryQuestion.
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

const gridSize = 5;
const roundLength = 30;

let currentPattern = [];
let userPattern = [];
let questionIndex = 0;
let sequenceLength = 5;
let canClick = false;
let isRoundActive = false;
let attemptsForQuestion = 0;

function handleCanvasClick(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / gridSize));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / gridSize));
    handlePatternClick(x, y);
}

export function initRound1(onRoundComplete) {
    resetState();
    clearGrid();
    showCanvas();

    canvas.addEventListener("click", handleCanvasClick);

    showIntro("Get Ready for Round 1! Memorize the pattern and replicate it.");
    setTimeout(() => {
        hideIntro();
        startRound(onRoundComplete);
    }, 2000);
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
    canvas.removeEventListener("click", handleCanvasClick);
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
    if (questionIndex > 4 && Math.random() < 0.65) {
        addDistractions();
    }

    displayPattern();
}

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

function displayPattern() {
    clearGrid();
    currentPattern.forEach(([x, y]) => drawDot(x, y, "blue"));

    setTimeout(() => {
        clearGrid();
        canClick = true;
    }, 500);
}

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
            attemptsForQuestion += 1;
            canClick = false;
            logMemoryQuestion({
                round: 1,
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
        revealCorrectPattern();
        logMemoryQuestion({
            round: 1,
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

function revealCorrectPattern() {
    clearGrid();
    currentPattern.forEach(([x, y]) => drawDot(x, y, "green"));
}

function drawDot(x, y, color = "blue") {
    const cellSize = canvas.width / gridSize;
    ctx.beginPath();
    ctx.arc(x * cellSize + cellSize / 2, y * cellSize + cellSize / 2, cellSize / 4, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
}

function addDistractions() {
    const maxDistractions = Math.min(5, 2 + Math.floor(questionIndex / 3));
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
