let currentRound = 1; // Start with Round 1
import { initCanvas } from './gameFlow.js';


// Initialize and run the game
function startGame() {
    initCanvas(); // Ensure the canvas is set up only once
    runRound(currentRound);
}

// Run a specific round based on the round number
function runRound(roundNumber) {
    if (roundNumber === 1) {
        import('./round1.js').then((module) => {
            module.initRound1(() => proceedToNextRound());
        });
    } else if (roundNumber === 2) {
        import('./round2.js').then((module) => {
            module.initRound2(() => proceedToNextRound());
        });
    } else if (roundNumber === 3) {
        import('./round3.js').then((module) => {
            module.initRound3(() => proceedToNextRound());
        });
    } else {
        console.log("Game Over! All rounds complete.");
    }
}
// Proceed to the next round, reset state
function proceedToNextRound() {
    console.log("Proceeding to next round:", currentRound + 1);
    currentRound++;
    runRound(currentRound); // Run the next round
}

// Start the game when the window loads
window.onload = startGame;