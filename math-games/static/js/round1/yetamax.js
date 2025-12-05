const GAME_DURATION_MS = 90_000;
const QUESTION_TIME_LIMIT_MS = 30_000;
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

const STATE = {
    ROUND1: 'round1',
    ROUND1_SUMMARY: 'round1_summary',
    ROUND2: 'round2',
    FINISHED: 'finished',
};

const roundLabels = {
    [STATE.ROUND1]: 'Round 1: Yetamax',
    [STATE.ROUND2]: 'Round 2: Maveric',
};

let timerInterval = null;
let endTimeout = null;
let breakInterval = null;
let questionTimeout = null;
let gameStartedAt = 0;
let questionStartedAt = 0;
let currentQuestion = null;
let wrongAttemptsForCurrent = 0;
let gameActive = false;
let gameState = STATE.ROUND1;

const roundStats = {
    [STATE.ROUND1]: createStats('round1'),
    [STATE.ROUND2]: createStats('round2'),
};

let round1ServerResult = null;
let round2ServerResult = null;

const questionText = document.getElementById('question-text');
const answerInput = document.getElementById('answer-input');
const answerForm = document.getElementById('answer-form');
const correctCountEl = document.getElementById('correct-count');
const wrongCountEl = document.getElementById('wrong-count');
const timeoutCountEl = document.getElementById('timeout-count');
const timerDisplay = document.getElementById('timer-display');
const feedbackEl = document.getElementById('feedback');
const instructionsBlock = document.getElementById('instructions-block');
const introPanel = document.getElementById('intro-panel');
const gamePanel = document.getElementById('game-panel');
const midPanel = document.getElementById('midround-panel');
const resultPanel = document.getElementById('result-panel');
const roundIndicator = document.getElementById('round-indicator');

const round2Countdown = document.getElementById('round2-countdown');

const combinedScoreLine = document.getElementById('combined-score-line');
const resultRound1Score = document.getElementById('result-round1-score');
const resultRound2Score = document.getElementById('result-round2-score');
const resultCombinedScore = document.getElementById('result-combined-score');
const tableRound1Correct = document.getElementById('table-round1-correct');
const tableRound1Wrong = document.getElementById('table-round1-wrong');
const tableRound1Timeouts = document.getElementById('table-round1-timeouts');
const tableRound1Fastest = document.getElementById('table-round1-fastest');
const tableRound2Correct = document.getElementById('table-round2-correct');
const tableRound2Wrong = document.getElementById('table-round2-wrong');
const tableRound2Timeouts = document.getElementById('table-round2-timeouts');
const tableRound2Fastest = document.getElementById('table-round2-fastest');
const operatorRows = document.getElementById('operator-rows');
const round2Rows = document.getElementById('round2-rows');

const restartButton = document.getElementById('restart-button');
const startButton = document.getElementById('start-button');
const desktopLine = document.getElementById('desktop-line');
const mobileLine = document.getElementById('mobile-line');
const keypad = document.getElementById('keypad');

const isMobile =
    /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '') ||
    (typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches);

function createStats(label) {
    return {
        label,
        correctCount: 0,
        wrongCount: 0,
        timedOutCount: 0,
        totalTimeMs: 0,
        minTimeMs: null,
        perQuestions: [],
        typeStats: {},
    };
}

function resetRoundStats(roundKey) {
    roundStats[roundKey] = createStats(roundKey);
}

function resetAll() {
    clearInterval(timerInterval);
    clearTimeout(endTimeout);
    clearInterval(breakInterval);
    clearTimeout(questionTimeout);
    gameActive = false;
    gameState = STATE.ROUND1;
    currentQuestion = null;
    wrongAttemptsForCurrent = 0;
    round1ServerResult = null;
    round2ServerResult = null;
    resetRoundStats(STATE.ROUND1);
    resetRoundStats(STATE.ROUND2);
    updateHud(roundStats[STATE.ROUND1]);
    timerDisplay.textContent = `${(GAME_DURATION_MS / 1000).toFixed(1)}s`;
    feedbackEl.textContent = '';
    instructionsBlock?.classList.remove('hidden');
    introPanel.classList.remove('hidden');
    gamePanel.classList.add('hidden');
    midPanel.classList.add('hidden');
    resultPanel.classList.add('hidden');
    updateRoundIndicator(STATE.ROUND1);
}

function updateRoundIndicator(roundKey) {
    roundIndicator.textContent = roundLabels[roundKey] || '';
}

function updateHud(stats) {
    correctCountEl.textContent = stats.correctCount;
    wrongCountEl.textContent = stats.wrongCount;
    timeoutCountEl.textContent = stats.timedOutCount || 0;
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

function randomIntExcluding(min, max, excludedSet) {
    if (excludedSet?.size) {
        let value;
        let safety = 0;
        do {
            value = randomInt(min, max);
            safety += 1;
        } while (excludedSet.has(value) && safety < 25);
        if (!excludedSet.has(value)) return value;
        // fallback if the range is too tight
    }
    return randomInt(min, max);
}

function randomDigitInt(digits) {
    const low = 10 ** (digits - 1);
    const high = 10 ** digits - 1;
    return randomInt(low, high);
}

function generateRound1Question() {
    const stats = roundStats[STATE.ROUND1];
    const difficultyLevel = Math.floor(stats.correctCount / 10);
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
        a = randomInt(Math.max(addMin, 13), addMax);
        b = randomInt(addMin, addMax);
        answer = a + b;
    } else if (operator === '-') {
        a = randomInt(Math.max(addMin, 22), addMax);
        const maxB = Math.max(2, a - 11);
        b = randomInt(2, maxB);
        answer = a - b;
        if (answer < 11) {
            // guard against edge cases when ranges tighten
            return generateRound1Question();
        }
    } else if (operator === '*') {
        const excluded = new Set([10]);
        a = randomIntExcluding(2, 12, excluded);
        b = randomIntExcluding(mulBMin, 100, excluded);
        answer = a * b;
    } else {
        const excluded = new Set([10]);
        b = randomIntExcluding(2, 12, excluded);
        let multiplier = randomIntExcluding(mulBMin, 100, excluded);
        answer = multiplier;
        a = b * multiplier;
    }

    const expression = `${a} ${operator} ${b}`;
    return { operator, a, b, answer, expression, category: operator };
}

function generateRound2Question() {
    if (window.MavericRound?.generateQuestion) {
        return window.MavericRound.generateQuestion();
    }
    console.warn('Maveric round generator missing; falling back to Round 1 logic');
    return generateRound1Question();
}

function clearQuestionTimer() {
    if (questionTimeout) {
        clearTimeout(questionTimeout);
        questionTimeout = null;
    }
}

function startQuestionTimer() {
    clearQuestionTimer();
    questionTimeout = setTimeout(() => {
        handleQuestionTimeout();
    }, QUESTION_TIME_LIMIT_MS);
}

function showQuestion(question) {
    currentQuestion = question;
    wrongAttemptsForCurrent = 0;
    questionStartedAt = performance.now();
    questionText.textContent = question.expression;
    feedbackEl.textContent = '';
    answerInput.value = '';
    answerInput.classList.remove('input-error', 'shake');
    answerInput.focus();
    startQuestionTimer();
}

function startTimer() {
    gameStartedAt = performance.now();
    timerInterval = setInterval(() => {
        const elapsed = performance.now() - gameStartedAt;
        const remaining = Math.max(0, GAME_DURATION_MS - elapsed);
        timerDisplay.textContent = `${(remaining / 1000).toFixed(1)}s`;
        if (remaining <= 0) {
            endRound(true);
        }
    }, 100);
    endTimeout = setTimeout(() => endRound(true), GAME_DURATION_MS + 50);
}

function startRound(roundKey) {
    clearInterval(breakInterval);
    wrongAttemptsForCurrent = 0;
    gameState = roundKey;
    gameActive = true;
    const stats = roundStats[roundKey];
    resetRoundStats(roundKey);
    updateRoundIndicator(roundKey);
    updateHud(roundStats[roundKey]);
    introPanel.classList.add('hidden');
    midPanel.classList.add('hidden');
    resultPanel.classList.add('hidden');
    gamePanel.classList.remove('hidden');
    instructionsBlock?.classList.add('hidden');
    answerInput.disabled = false;
    timerDisplay.textContent = `${(GAME_DURATION_MS / 1000).toFixed(1)}s`;
    startTimer();
    const question = roundKey === STATE.ROUND1 ? generateRound1Question() : generateRound2Question();
    showQuestion(question);
}

function handleWrongAnswer() {
    const stats = roundStats[gameState];
    stats.wrongCount += 1;
    wrongAttemptsForCurrent += 1;
    updateHud(stats);
    feedbackEl.textContent = 'Try again';
    answerInput.value = '';
    answerInput.classList.remove('shake');
    // force reflow so animation can replay
    void answerInput.offsetWidth;
    answerInput.classList.add('input-error', 'shake');
}

function handleQuestionTimeout() {
    if (!gameActive) return;
    const stats = roundStats[gameState];
    clearQuestionTimer();
    const timeMs = Math.max(0, performance.now() - questionStartedAt);
    stats.wrongCount += 1;
    stats.timedOutCount += 1;

    stats.perQuestions.push({
        index: stats.perQuestions.length + 1,
        category: currentQuestion.category,
        operator: currentQuestion.operator,
        expression: currentQuestion.expression,
        a: currentQuestion.a,
        b: currentQuestion.b,
        time_ms: Math.round(Math.min(timeMs, QUESTION_TIME_LIMIT_MS)),
        wrong_attempts: wrongAttemptsForCurrent,
        timed_out: true,
    });

    updateHud(stats);
    const nextQuestion = gameState === STATE.ROUND1 ? generateRound1Question() : generateRound2Question();
    showQuestion(nextQuestion);
}

function handleCorrectAnswer() {
    const stats = roundStats[gameState];
    clearQuestionTimer();
    const timeMs = Math.max(0, performance.now() - questionStartedAt);
    stats.correctCount += 1;
    stats.totalTimeMs += timeMs;
    stats.minTimeMs = stats.minTimeMs === null ? timeMs : Math.min(stats.minTimeMs, timeMs);

    stats.perQuestions.push({
        index: stats.perQuestions.length + 1,
        category: currentQuestion.category,
        operator: currentQuestion.operator,
        expression: currentQuestion.expression,
        a: currentQuestion.a,
        b: currentQuestion.b,
        time_ms: Math.round(timeMs),
        wrong_attempts: wrongAttemptsForCurrent,
        timed_out: false,
    });

    const key = currentQuestion.category || currentQuestion.operator;
    if (!stats.typeStats[key]) {
        stats.typeStats[key] = { count: 0, totalTime: 0 };
    }
    stats.typeStats[key].count += 1;
    stats.typeStats[key].totalTime += timeMs;

    updateHud(stats);
    const nextQuestion = gameState === STATE.ROUND1 ? generateRound1Question() : generateRound2Question();
    showQuestion(nextQuestion);
}

function calculateAvgTime(stats) {
    return stats.correctCount > 0 ? stats.totalTimeMs / stats.correctCount : 0;
}

function calculateLocalScore(stats) {
    const avgTimeMs = calculateAvgTime(stats);
    const safeAvg = avgTimeMs > 0 ? avgTimeMs : Number.POSITIVE_INFINITY;
    const speedBonus = safeAvg === Infinity ? 0 : Math.max(0, Math.floor(3000 / safeAvg));
    return stats.correctCount * 10 - stats.wrongCount * 2 + speedBonus;
}

function buildOperatorBreakdown(targetEl, statsMap) {
    targetEl.innerHTML = '';
    const entries = Object.entries(statsMap || {});
    if (!entries.length) {
        targetEl.innerHTML = '<tr><td colspan="3">All questions skipped or timed out.</td></tr>';
        return;
    }
    entries.forEach(([op, info]) => {
        const count = info.count ?? 0;
        const totalTime = info.totalTime ?? (info.avg_time_ms != null ? info.avg_time_ms * count : 0);
        const avg = count > 0 ? totalTime / count : 0;
        const avgSeconds = Number.isFinite(avg) ? avg / 1000 : null;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${op}</td>
            <td>${count}</td>
            <td>${avgSeconds != null ? avgSeconds.toFixed(2) : '—'}</td>
        `;
        targetEl.appendChild(row);
    });
}

async function submitRound1Results(payload) {
    try {
        const resp = await fetch('/api/math-game/yetamax/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error('Failed to submit round 1', err);
        return null;
    }
}

async function submitRound2Results(payload) {
    try {
        const resp = await fetch('/api/math-game/yetamax/round2/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify(payload),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error('Failed to submit round 2', err);
        return null;
    }
}

async function submitSessionLink(round1Id, round2Id, combinedScore) {
    try {
        const resp = await fetch('/api/math-game/yetamax/session/submit', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken,
            },
            body: JSON.stringify({
                round1_score_id: round1Id,
                round2_score_id: round2Id,
                combined_score: combinedScore,
            }),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error('Failed to submit combined session', err);
        return null;
    }
}

function endRound(endedByTimeout) {
    if (!gameActive) return;
    gameActive = false;
    clearInterval(timerInterval);
    clearTimeout(endTimeout);
    clearQuestionTimer();
    answerInput.disabled = true;

    const stats = roundStats[gameState];
    const runDuration = performance.now() - gameStartedAt;
    const avgTimeMs = calculateAvgTime(stats);

    if (gameState === STATE.ROUND1) {
        const avgTimeByOperator = {};
        Object.entries(stats.typeStats).forEach(([key, val]) => {
            if (val.count > 0) {
                avgTimeByOperator[key] = {
                    count: val.count,
                    avg_time_ms: val.totalTime / val.count,
                };
            }
        });

        const payload = {
            correct_count: stats.correctCount,
            wrong_count: stats.wrongCount,
            avg_time_ms: avgTimeMs,
            min_time_ms: stats.minTimeMs ?? 0,
            per_question_times: stats.perQuestions,
            avg_time_by_operator: avgTimeByOperator,
            total_time_ms: stats.totalTimeMs,
            run_duration_ms: runDuration,
            ended_by_timeout: endedByTimeout,
            timed_out_count: stats.timedOutCount,
            version: 'v1',
        };

        submitRound1Results(payload).then((resp) => {
            const score = resp?.score ?? calculateLocalScore(stats);
            round1ServerResult = { ...payload, score, is_valid: resp?.is_valid, id: resp?.yetamax_score_id };
            showRound1Summary(payload, resp, score);
        });
    } else if (gameState === STATE.ROUND2) {
        const typeBreakdown = {};
        Object.entries(stats.typeStats).forEach(([key, val]) => {
            if (val.count > 0) {
                typeBreakdown[key] = {
                    count: val.count,
                    avg_time_ms: val.totalTime / val.count,
                };
            }
        });

        const payload = {
            correct_count: stats.correctCount,
            wrong_count: stats.wrongCount,
            avg_time_ms: avgTimeMs,
            min_time_ms: stats.minTimeMs ?? 0,
            total_questions: stats.perQuestions.length,
            per_question: stats.perQuestions,
            ended_by_timeout: endedByTimeout,
            type_breakdown: typeBreakdown,
            score_client: calculateLocalScore(stats),
            timed_out_count: stats.timedOutCount,
        };

        submitRound2Results(payload).then((resp) => {
            const score = resp?.round2_score ?? calculateLocalScore(stats);
            round2ServerResult = { ...payload, score, is_valid: resp?.is_valid, id: resp?.maveric_score_id };
            const combined = (round1ServerResult?.score || 0) + score;
            if (round1ServerResult?.id && resp?.maveric_score_id) {
                submitSessionLink(round1ServerResult.id, resp.maveric_score_id, combined);
            }
            showFinalResults(score, combined, typeBreakdown);
        });
    }
}

function showRound1Summary(payload, response, score) {
    gamePanel.classList.add('hidden');
    midPanel.classList.remove('hidden');
    gameState = STATE.ROUND1_SUMMARY;

    let countdown = 6;
    round2Countdown.textContent = `Starting Round 2 in ${countdown}...`;
    const startRound2 = () => {
        clearInterval(breakInterval);
        startRound(STATE.ROUND2);
    };
    breakInterval = setInterval(() => {
        countdown -= 1;
        if (countdown <= 0) {
            startRound2();
        } else {
            round2Countdown.textContent = `Starting Round 2 in ${countdown}...`;
        }
    }, 1000);
    setTimeout(startRound2, countdown * 1000 + 200);
}

function showFinalResults(round2Score, combinedScore, typeBreakdown) {
    const round1Score = round1ServerResult?.score ?? calculateLocalScore(roundStats[STATE.ROUND1]);
    gamePanel.classList.add('hidden');
    midPanel.classList.add('hidden');
    resultPanel.classList.remove('hidden');
    gameState = STATE.FINISHED;

    combinedScoreLine.textContent = `Combined score: ${combinedScore}`;
    resultRound1Score.textContent = round1Score;
    resultRound2Score.textContent = round2Score;
    resultCombinedScore.textContent = combinedScore;

    tableRound1Correct.textContent = roundStats[STATE.ROUND1].correctCount;
    tableRound1Wrong.textContent = roundStats[STATE.ROUND1].wrongCount;
    tableRound1Timeouts.textContent = roundStats[STATE.ROUND1].timedOutCount;
    tableRound1Fastest.textContent = formatFastest(roundStats[STATE.ROUND1].minTimeMs);

    tableRound2Correct.textContent = roundStats[STATE.ROUND2].correctCount;
    tableRound2Wrong.textContent = roundStats[STATE.ROUND2].wrongCount;
    tableRound2Timeouts.textContent = roundStats[STATE.ROUND2].timedOutCount;
    tableRound2Fastest.textContent = formatFastest(roundStats[STATE.ROUND2].minTimeMs);

            buildOperatorBreakdown(operatorRows, roundStats[STATE.ROUND1].typeStats);
            buildOperatorBreakdown(round2Rows, typeBreakdown);
}

function formatFastest(value) {
    if (value === null || value === undefined) return '—';
    return `${(value / 1000).toFixed(2)}`;
}

function answersMatch(expected, provided) {
    const tolerance = Math.abs(expected) < 1 ? 1e-6 : 0.01;
    return Math.abs(expected - provided) < tolerance;
}

function handleAnswerSubmit() {
    if (!gameActive) return;
    const trimmed = answerInput.value.trim();
    if (trimmed === '') return;
    const value = Number(trimmed);
    if (!Number.isFinite(value)) return;

    if (answersMatch(currentQuestion.answer, value)) {
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
    startRound(STATE.ROUND1);
});

restartButton?.addEventListener('click', () => {
    if (gameActive) return;
    resetAll();
});

keypad?.addEventListener('click', handleKeypadInteraction);

applyDeviceUi();
resetAll();
