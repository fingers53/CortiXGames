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

export function logMemoryQuestion(event) {
    questionLog.push(event);
}

export function endMemoryGame() {
    hideCanvas();
    console.log("Memory game finished. Question log:", questionLog);
}

export function startMemoryGame() {
    questionLog.length = 0;
    initCanvas();
    initRound1(() => initRound2(() => initRound3(() => endMemoryGame())));
}

window.addEventListener("DOMContentLoaded", startMemoryGame);
