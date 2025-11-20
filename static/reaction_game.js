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

function startCountdown() {
    let countdownValue = 3;
    const countdownDisplay = document.getElementById("countdown");

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
    clearInterval(countdown);
    startCountdown();
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

    fetch("/reaction-game/submit_score", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            scoreData: scoreData,
        }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.status === "success") {
            const scoreResult = data.scoreResult;
            document.getElementById("end-screen").innerHTML = `
                <div style="background-color: #fdf5e6; border: 3px solid #f4a460; padding: 20px; border-radius: 10px;">
                    <h1>Final Score: ${scoreResult.finalScore}</h1>
                    <div class="score-breakdown">
                        <div class="column">
                            <h2>Score</h2>
                            <p>Correct Answers: ${correctClicks}</p>
                            <p>Incorrect Answers: ${incorrectClicks}</p>
                            <p>Total: ${correctClicks - incorrectClicks}</p>
                            <p> Accuracy: ${scoreResult.accuracy}
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
            document.getElementById("end-screen").style.display = 'block';
        }
    })
    .catch(error => {
        console.error("Error submitting score:", error);
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
window.onload = startCountdown;
