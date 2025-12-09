/**
 * Reaction game front-end logic.
 * Handles countdown -> gameplay -> end screen flow, tracks per-question stats,
 * and submits the score payload to the existing backend endpoint.
 */

// Timing and animation constants
const maxDelay = 0.6 * 1000;
const minDelay = 0.25 * 1000;
const slowThreshold = 550;
const blackoutTime = 400;
const bounceInterval = 53;
const maxJiggle = 10;

// Game state
let score = 0;
let timer = 45;
let countdown;
let countdownInterval;
let correctSide;
let questionStartTime;
let totalReactionTime = 0;
let correctClicks = 0;
let incorrectClicks = 0;
let slowAnswers = 0;
let fastestTime = null;
let slowestTime = 0;
let answerRecord = [];
let penaltyMessage = "";
let middleBallShown = false;
let lockInput = false;
let sessionToken = null; // Reserved for future secure scoring
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
const usernameRegex = /^[A-Za-z0-9_]{3,20}$/;


function getUsername() {
    return localStorage.getItem("username") || "";
}

function ensureUsername() {
    const saved = getUsername();
    if (!usernameRegex.test(saved)) {
        alert("Please choose a valid username first.");
        window.location.href = "/";
        return false;
    }
    return true;
}

function showInstructionBox() {
    const instructionBox = document.getElementById('instruction-box');
    const countdownDisplay = document.getElementById('countdown');

    if (instructionBox) {
        instructionBox.style.display = 'flex';
    }

    if (countdownDisplay) {
        countdownDisplay.style.display = 'none';
        countdownDisplay.textContent = '';
    }

    document.getElementById('game-container').style.display = 'block';
}

function startCountdown() {
    if (!ensureUsername()) return;
    let countdownValue = 3;
    const countdownDisplay = document.getElementById("countdown");

    const instructionBox = document.getElementById('instruction-box');
    if (instructionBox) instructionBox.style.display = 'none';

    document.getElementById('end-screen').style.display = 'none';
    countdownDisplay.style.display = 'block';

    countdownInterval = setInterval(() => {
        countdownDisplay.textContent = countdownValue;
        countdownValue--;

        if (countdownValue < 0) {
            clearInterval(countdownInterval);
            countdownDisplay.style.display = 'none';
            startGame();
        }
    }, 1000);
}

function startGame() {
    document.getElementById('game-container').style.display = 'block';
    middleBallShown = false;
    lockInput = false;

    countdown = setInterval(() => {
        if (timer > 0) {
            timer--;
            document.getElementById('timer').textContent = timer;
        } else {
            clearInterval(countdown);
            showEndScreen();
        }
    }, 1000);

    startNewRound();
    startBouncing();
}

function resetGame() {
    score = 0;
    timer = 45;
    correctClicks = 0;
    incorrectClicks = 0;
    totalReactionTime = 0;
    slowAnswers = 0;
    fastestTime = null;
    slowestTime = 0;
    answerRecord = [];
    middleBallShown = false;
    lockInput = false;
    penaltyMessage = "";

    document.getElementById('timer').textContent = timer;
    document.getElementById('game-container').style.display = 'none';
    document.getElementById('end-screen').style.display = 'none';
    clearInterval(countdown);
    showInstructionBox();
}

function startNewRound() {
    middleBallShown = false;
    lockInput = false;

    const colors = ["red", "blue"];
    const leftColor = colors[Math.floor(Math.random() * 2)];
    const rightColor = leftColor === "red" ? "blue" : "red";

    document.getElementById("left-ball").style.backgroundColor = leftColor;
    document.getElementById("right-ball").style.backgroundColor = rightColor;

    correctSide = (Math.random() < 0.5) ? "left" : "right";
    const centerColor = (correctSide === "left") ? leftColor : rightColor;
    document.getElementById("center-ball").style.backgroundColor = centerColor;

    document.getElementById("left-ball").style.visibility = "visible";
    document.getElementById("right-ball").style.visibility = "visible";
    document.getElementById("center-ball").style.visibility = "hidden";

    clearTimeout(countdownInterval);

    const delay = Math.random() * (maxDelay - minDelay) + minDelay;
    countdownInterval = setTimeout(() => {
        document.getElementById("center-ball").style.visibility = "visible";
        middleBallShown = true;
        questionStartTime = Date.now();
    }, delay);
}

function chooseSide(side) {
    if (!middleBallShown || lockInput) return;

    const reactionTime = Date.now() - questionStartTime;
    const isCorrect = (side === correctSide);

    if (isCorrect) {
        correctClicks++;
        score++;
        totalReactionTime += reactionTime;
        if (reactionTime > slowThreshold) slowAnswers++;
        if (fastestTime === null || reactionTime < fastestTime) fastestTime = reactionTime;
        if (reactionTime > slowestTime) slowestTime = reactionTime;
    } else {
        incorrectClicks++;
        score--;
    }

    answerRecord.push({
        isCorrect: isCorrect,
        reactionTime: reactionTime,
    });

    lockInput = true;
    document.getElementById("left-ball").style.visibility = "hidden";
    document.getElementById("center-ball").style.visibility = "hidden";
    document.getElementById("right-ball").style.visibility = "hidden";

    setTimeout(startNewRound, blackoutTime);
}

function calculateStreaks() {
    let maxStreak = 0;
    let currentStreak = 0;

    for (let i = 0; i < answerRecord.length; i++) {
        if (!answerRecord[i].isCorrect) {
            currentStreak++;
            if (currentStreak > maxStreak) {
                maxStreak = currentStreak;
            }
        } else {
            currentStreak = 0;
        }
    }

    penaltyMessage = maxStreak > 1
        ? `Penalized for a streak of ${maxStreak} consecutive incorrect answers.`
        : "Great job! No penalty for consecutive incorrect answers.";

    return maxStreak > 1 ? maxStreak : 0;
}

async function showEndScreen() {
    const scoreData = {
        correctClicks,
        incorrectClicks,
        totalReactionTime,
        slowAnswers,
        fastestTime,
        slowestTime,
        answerRecord
    };

    const username = getUsername();
    const localScore = computeLocalScore();
    buildEndScreen(localScore, "Saving your score…");

    fetch("/reaction-game/submit_score", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ username, scoreData }),
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then((data) => {
            if (data.status === "success") {
                buildEndScreen(data.scoreResult);
            } else {
                console.error("Score submission error:", data);
                buildEndScreen(localScore, "Score saved locally. Server unavailable.");
            }
        })
        .catch((error) => {
            console.error("Error submitting score:", error);
            buildEndScreen(localScore, "Score saved locally. Server unavailable.");
        });
}

function startBouncing() {
    setInterval(() => {
        const randomOffsetLeft = Math.floor(Math.random() * 2 * maxJiggle) - maxJiggle;
        const randomOffsetRight = Math.floor(Math.random() * 2 * maxJiggle) - maxJiggle;

        document.getElementById("left-ball").style.transform = `translateY(${randomOffsetLeft}px)`;
        document.getElementById("right-ball").style.transform = `translateY(${randomOffsetRight}px)`;
    }, bounceInterval);
}

function chooseSideFromKeyboard(event) {
    if (event.key === "1") {
        chooseSide("left");
    } else if (event.key === "0") {
        chooseSide("right");
    }
}

document.addEventListener("keydown", chooseSideFromKeyboard);
document.addEventListener("DOMContentLoaded", () => {
    showInstructionBox();

    const startButton = document.getElementById('start-game-button');
    if (startButton) {
        startButton.addEventListener('click', startCountdown);
    }
});

function computeLocalScore() {
    const averageTime = correctClicks > 0 ? totalReactionTime / correctClicks : 0;
    const speedBonus = averageTime > 0 ? (correctClicks - incorrectClicks) * (1000 / averageTime) : 0;
    const fastestTimeBonus = fastestTime && fastestTime < 300 ? 300 / fastestTime : 0;
    const slowestTimePenalty = slowestTime > 500 ? slowestTime / 500 : 0;
    const streakPenalty = calculateStreaks();
    const accuracy = (correctClicks + incorrectClicks) > 0 ? (correctClicks / (correctClicks + incorrectClicks)) * 100 : 0;
    const finalScore = correctClicks - incorrectClicks + speedBonus + fastestTimeBonus - slowestTimePenalty - streakPenalty;

    return {
        finalScore: Number(finalScore.toFixed(2)),
        averageTime: Number(averageTime.toFixed(2)),
        accuracy: Number(accuracy.toFixed(2)),
        speedBonus: Number(speedBonus.toFixed(2)),
        fastestTimeBonus: Number(fastestTimeBonus.toFixed(2)),
        slowestTimePenalty: Number(slowestTimePenalty.toFixed(2)),
        streakPenalty: Number(streakPenalty.toFixed(2)),
        fastestTime: Number((fastestTime || 0).toFixed(2)),
        slowestTime: Number((slowestTime || 0).toFixed(2)),
        penaltyMessage: penaltyMessage || "Local score computed.",
    };
}

function buildEndScreen(scoreResult, bannerText = null) {
    const endScreen = document.getElementById("end-screen");
    if (!endScreen) return;

    const header = bannerText
        ? `<h1>${bannerText}</h1>`
        : `<h1>Final Score: ${scoreResult.finalScore}</h1>`;

    endScreen.innerHTML = `
        <div style="background-color: #fdf5e6; border: 3px solid #f4a460; padding: 20px; border-radius: 10px;">
            ${header}
            <div class="score-breakdown">
                <div class="column">
                    <h2>Score</h2>
                    <p>Correct Answers: ${correctClicks}</p>
                    <p>Incorrect Answers: ${incorrectClicks}</p>
                    <p>Total: ${correctClicks - incorrectClicks}</p>
                    <p> Accuracy: ${scoreResult.accuracy}</p>
                </div>
                <div class="column">
                    <h2>Speed</h2>
                    <p>Average Time: ${scoreResult.averageTime} ms</p>
                    <p>Fastest Time: ${scoreResult.fastestTime} ms</p>
                    <p>Slowest Time: ${scoreResult.slowestTime} ms</p>
                    <p>Bonus: Speed: +${scoreResult.speedBonus}</p>
                    <p>Bonus: Fastest time below 300ms: +${scoreResult.fastestTimeBonus}</p>
                    <p>Penalty: Slowest time over 500ms: -${scoreResult.slowestTimePenalty}</p>
                </div>
                <div class="column">
                    <h2>Streaks</h2>
                    <p>${scoreResult.penaltyMessage}</p>
                    <p>Streak Penalty: -${scoreResult.streakPenalty}</p>
                </div>
            </div>
            <button onclick="resetGame()">Play Again</button>
            <button onclick="window.location.href='/'">Home</button>
            <button onclick="window.location.href='/leaderboard/reaction-game'">Leaderboard</button>
        </div>
    `;
    document.getElementById("game-container").style.display = 'none';
    endScreen.style.display = 'block';
}
