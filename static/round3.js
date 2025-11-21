/**
 * Round 3: Identify the rotated triangle among blue triangles while ignoring orange decoys.
 * Relies on shared canvas/timer helpers and logs each question outcome for the orchestrator.
 */

import {
    drawGrid,
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
const roundLength = 20;
const initialRotationAngles = [45, 135, 225, 315];
const extraRotationAngles = [90, 180, 270];
const dummyTriangleCount = 3;

let currentPattern = [];
let rotatedTriangle = null;
let questionIndex = 0;
let triangleCount = 6;
let canClick = false;
let attemptsForQuestion = 0;
let isRoundActive = false;

function handleCanvasClick(event) {
    if (!canClick) return;

    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left) / (canvas.width / gridSize));
    const y = Math.floor((event.clientY - rect.top) / (canvas.height / gridSize));
    handleTriangleClick(x, y);
}

export function initRound3(onRoundComplete) {
    resetState();
    clearGrid();
    showCanvas();

    canvas.addEventListener("click", handleCanvasClick);

    showIntro(
        "Round 3: Find and click the rotated triangle. Ignore the orange triangles.",
        () => startRound(onRoundComplete)
    );
}

function resetState() {
    currentPattern = [];
    rotatedTriangle = null;
    questionIndex = 0;
    triangleCount = 6;
    canClick = false;
    attemptsForQuestion = 0;
    isRoundActive = false;
}

function startRound(onRoundComplete) {
    isRoundActive = true;
    startTimer(roundLength, () => handleTimeOut(onRoundComplete));
    displayInitialTriangles();
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

function displayInitialTriangles() {
    if (!isRoundActive) return;

    attemptsForQuestion = 0;
    questionIndex += 1;

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

    setTimeout(() => {
        clearGrid();
        drawGrid();
        setTimeout(displayWithRotatedTriangle, 500);
    }, 1000);
}

function displayWithRotatedTriangle() {
    if (currentPattern.length === 0) return;

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

function handleTriangleClick(x, y) {
    if (!rotatedTriangle) return;

    const isCorrect = x === rotatedTriangle[0] && y === rotatedTriangle[1];
    attemptsForQuestion += 1;
    canClick = false;

    logMemoryQuestion({
        round: 3,
        questionIndex,
        wasCorrect: isCorrect,
        attempts: attemptsForQuestion,
        sequenceLength: triangleCount,
    });

    if (isCorrect) {
        showFeedback("Correct!", true, 800, () => {
            clearGrid();
            setTimeout(displayInitialTriangles, 400);
        });
    } else {
        showRotatedTriangle();
        showFeedback("Incorrect!", false, 800, () => {
            clearGrid();
            setTimeout(displayInitialTriangles, 400);
        });
    }
}

function showRotatedTriangle() {
    clearGrid();
    if (rotatedTriangle) {
        const [x, y, rotation] = rotatedTriangle;
        drawTriangle(x, y, rotation, "green");
    }
}

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

function getRandomElement(array) {
    return array[Math.floor(Math.random() * array.length)];
}

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
