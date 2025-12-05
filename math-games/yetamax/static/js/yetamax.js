const GAME_DURATION_MS = 90_000;
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

let timerInterval = null;
let endTimeout = null;
let gameStartedAt = 0;
let questionStartedAt = 0;
let questionIndex = 0;
let currentQuestion = null;
let wrongAttemptsForCurrent = 0;
let gameActive = false;

let correctCount = 0;
let wrongCount = 0;
let totalTimeMs = 0;
let minTimeMs = null;
let perQuestionTimes = [];
const perOperatorStats = {
    '+': { count: 0, totalTime: 0 },
    '-': { count: 0, totalTime: 0 },
    '*': { count: 0, totalTime: 0 },
    '/': { count: 0, totalTime: 0 },
};

const questionText = document.getElementById('question-text');
const answerInput = document.getElementById('answer-input');
const answerForm = document.getElementById('answer-form');
const correctCountEl = document.getElementById('correct-count');
const wrongCountEl = document.getElementById('wrong-count');
const timerDisplay = document.getElementById('timer-display');
const feedbackEl = document.getElementById('feedback');
const introPanel = document.getElementById('intro-panel');
const gamePanel = document.getElementById('game-panel');
const resultPanel = document.getElementById('result-panel');
const scoreLine = document.getElementById('score-line');
const resultCorrect = document.getElementById('result-correct');
const resultWrong = document.getElementById('result-wrong');
const resultAvg = document.getElementById('result-avg');
const resultMin = document.getElementById('result-min');
const operatorRows = document.getElementById('operator-rows');
const restartButton = document.getElementById('restart-button');
const startButton = document.getElementById('start-button');
const desktopLine = document.getElementById('desktop-line');
const mobileLine = document.getElementById('mobile-line');
const keypad = document.getElementById('keypad');

const isMobile =
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '') ||
    (typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches);

function resetStats() {
    correctCount = 0;
    wrongCount = 0;
    totalTimeMs = 0;
    minTimeMs = null;
    perQuestionTimes = [];
    Object.keys(perOperatorStats).forEach((op) => {
        perOperatorStats[op].count = 0;
        perOperatorStats[op].totalTime = 0;
    });
    questionIndex = 0;
    wrongAttemptsForCurrent = 0;
}

function updateHud() {
    correctCountEl.textContent = correctCount;
    wrongCountEl.textContent = wrongCount;
}

function applyDeviceUi() {
    if (isMobile) {
        keypad?.classList.remove('hidden');
        mobileLine?.classList.remove('hidden');
        desktopLine?.classList.add('hidden');
    } else {
        keypad?.classList.add('hidden');
        mobileLine?.classList.add('hidden');
        desktopLine?.classList.remove('hidden');
    }
}

function weightedChoice(weights) {
    const entries = Object.entries(weights);
    const total = entries.reduce((sum, [, w]) => sum + w, 0);
    let roll = Math.random() * total;
    for (const [key, weight] of entries) {
        if (roll < weight) return key;
        roll -= weight;
    }
    return entries[0][0];
}

function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateQuestion() {
    const difficultyLevel = Math.floor(correctCount / 10);
    const operatorWeights = {
        '+': 1,
        '-': 1,
        '*': 1 + difficultyLevel * 0.3,
        '/': 1 + difficultyLevel * 0.3,
    };
    const operator = weightedChoice(operatorWeights);

    const addMin = Math.min(100, Math.max(2, 2 + difficultyLevel * 3));
    const addMax = 100;
    const mulBMin = Math.min(100, 2 + difficultyLevel * 5);

    let a = 0;
    let b = 0;
    let answer = 0;

    if (operator === '+') {
        a = randomInt(addMin, addMax);
        b = randomInt(addMin, addMax);
        answer = a + b;
    } else if (operator === '-') {
        a = randomInt(addMin, addMax);
        b = randomInt(2, a); // keep non-negative
        answer = a - b;
    } else if (operator === '*') {
        a = randomInt(2, 12);
        b = randomInt(mulBMin, 100);
        answer = a * b;
    } else {
        // division based on multiplication pairs
        b = randomInt(2, 12);
        const multiplier = randomInt(mulBMin, 100);
        answer = multiplier;
        a = b * multiplier;
    }

    const expression = `${a} ${operator} ${b}`;
    return { operator, a, b, answer, expression };
}

function showQuestion(question) {
    currentQuestion = question;
    wrongAttemptsForCurrent = 0;
    questionStartedAt = performance.now();
    questionText.textContent = question.expression;
    feedbackEl.textContent = '';
    answerInput.value = '';
    answerInput.focus();
}

function startTimer() {
    gameStartedAt = performance.now();
    timerInterval = setInterval(() => {
        const elapsed = performance.now() - gameStartedAt;
        const remaining = Math.max(0, GAME_DURATION_MS - elapsed);
        timerDisplay.textContent = `${(remaining / 1000).toFixed(1)}s`;
        if (remaining <= 0) {
            endGame(true);
        }
    }, 100);
    endTimeout = setTimeout(() => endGame(true), GAME_DURATION_MS + 50);
}

function startGame() {
    resetStats();
    updateHud();
    introPanel.classList.add('hidden');
    resultPanel.classList.add('hidden');
    gamePanel.classList.remove('hidden');
    answerInput.disabled = false;
    gameActive = true;
    timerDisplay.textContent = `${(GAME_DURATION_MS / 1000).toFixed(1)}s`;

    startTimer();
    showQuestion(generateQuestion());
}

function handleWrongAnswer() {
    wrongCount += 1;
    wrongAttemptsForCurrent += 1;
    updateHud();
    feedbackEl.textContent = 'Try again';
}

function handleCorrectAnswer() {
    const timeMs = Math.max(0, performance.now() - questionStartedAt);
    correctCount += 1;
    totalTimeMs += timeMs;
    minTimeMs = minTimeMs === null ? timeMs : Math.min(minTimeMs, timeMs);

    perQuestionTimes.push({
        index: questionIndex + 1,
        operator: currentQuestion.operator,
        expression: currentQuestion.expression,
        a: currentQuestion.a,
        b: currentQuestion.b,
        time_ms: Math.round(timeMs),
        wrong_attempts: wrongAttemptsForCurrent,
    });

    const opStats = perOperatorStats[currentQuestion.operator];
    opStats.count += 1;
    opStats.totalTime += timeMs;

    updateHud();
    questionIndex += 1;
    showQuestion(generateQuestion());
}

function calculateLocalScore(avgTimeMs) {
    const safeAvg = avgTimeMs > 0 ? avgTimeMs : Number.POSITIVE_INFINITY;
    const speedBonus = safeAvg === Infinity ? 0 : Math.max(0, Math.floor(3000 / safeAvg));
    return correctCount * 10 - wrongCount * 2 + speedBonus;
}

function buildOperatorBreakdown(avgByOp) {
    operatorRows.innerHTML = '';
    const entries = Object.entries(avgByOp);
    if (!entries.length) {
        operatorRows.innerHTML = '<tr><td colspan="3">No answers recorded.</td></tr>';
        return;
    }
    entries.forEach(([op, info]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${op}</td>
            <td>${info.count}</td>
            <td>${info.avg_time_ms.toFixed(1)}</td>
        `;
        operatorRows.appendChild(row);
    });
}

function showResults(payload, response) {
    const avgTimeMs = payload.avg_time_ms;
    const minMs = payload.min_time_ms;
    const score = response?.score ?? calculateLocalScore(avgTimeMs);

    scoreLine.textContent = `Score: ${score}${response && response.is_valid === false ? ' (flagged)' : ''}`;
    resultCorrect.textContent = payload.correct_count;
    resultWrong.textContent = payload.wrong_count;
    resultAvg.textContent = `${avgTimeMs.toFixed(1)} ms`;
    resultMin.textContent = `${minMs.toFixed(1)} ms`;
    buildOperatorBreakdown(payload.avg_time_by_operator);

    gamePanel.classList.add('hidden');
    resultPanel.classList.remove('hidden');
}

async function submitResults(payload) {
    try {
        const resp = await fetch('/api/math-game/yetamax/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        return await resp.json();
    } catch (err) {
        console.error('Failed to submit results', err);
        return null;
    }
}

function endGame(endedByTimeout) {
    if (!gameActive) return;
    gameActive = false;
    clearInterval(timerInterval);
    clearTimeout(endTimeout);
    answerInput.disabled = true;

    const runDuration = performance.now() - gameStartedAt;
    const avgTimeMs = correctCount > 0 ? totalTimeMs / correctCount : 0;
    const avgTimeByOperator = {};
    Object.entries(perOperatorStats).forEach(([op, stats]) => {
        if (stats.count > 0) {
            avgTimeByOperator[op] = {
                count: stats.count,
                avg_time_ms: stats.totalTime / stats.count,
            };
        }
    });

    const payload = {
        correct_count: correctCount,
        wrong_count: wrongCount,
        avg_time_ms: avgTimeMs,
        min_time_ms: minTimeMs ?? 0,
        per_question_times: perQuestionTimes,
        avg_time_by_operator: avgTimeByOperator,
        total_time_ms: totalTimeMs,
        run_duration_ms: runDuration,
        ended_by_timeout: endedByTimeout,
        version: 'v1',
    };

    submitResults(payload).then((resp) => {
        showResults(payload, resp);
    });
}

function handleAnswerSubmit() {
    if (!gameActive) return;
    const trimmed = answerInput.value.trim();
    if (trimmed === '') return;
    const value = Number(trimmed);
    if (!Number.isFinite(value)) return;

    if (value === currentQuestion.answer) {
        handleCorrectAnswer();
        answerInput.value = '';
    } else {
        handleWrongAnswer();
    }
}

function handleKeypadInteraction(event) {
    const target = event.target;
    if (!(target instanceof HTMLButtonElement)) return;
    const { key, action } = target.dataset;
    if (key) {
        answerInput.value = `${answerInput.value || ''}${key}`;
        answerInput.focus();
        return;
    }
    if (action === 'clear') {
        answerInput.value = '';
    } else if (action === 'backspace') {
        answerInput.value = answerInput.value.slice(0, -1);
    } else if (action === 'submit') {
        handleAnswerSubmit();
    }
    answerInput.focus();
}

answerForm?.addEventListener('submit', (event) => {
    event.preventDefault();
    handleAnswerSubmit();
});

startButton?.addEventListener('click', () => {
    if (gameActive) return;
    startGame();
});

restartButton?.addEventListener('click', () => {
    if (gameActive) return;
    introPanel.classList.remove('hidden');
    resultPanel.classList.add('hidden');
});

keypad?.addEventListener('click', handleKeypadInteraction);

applyDeviceUi();
