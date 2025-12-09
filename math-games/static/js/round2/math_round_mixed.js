(function () {
    const MAX_RETRIES = 50;

    function randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    function randomDigitInt(digits) {
        const low = 10 ** (digits - 1);
        const high = 10 ** digits - 1;
        return randomInt(low, high);
    }

    function weightedChoice(weights) {
        const entries = Object.entries(weights);
        const total = entries.reduce((sum, [, weight]) => sum + weight, 0);
        let roll = Math.random() * total;
        for (const [key, weight] of entries) {
            if (roll < weight) return key;
            roll -= weight;
        }
        return entries[0][0];
    }

    function isTrivialPercent(percentValue) {
        return percentValue <= 0 || percentValue === 100;
    }

    function guardGeneration(generator, validator) {
        let last = null;
        for (let i = 0; i < MAX_RETRIES; i++) {
            const candidate = generator();
            last = candidate;
            if (!validator || validator(candidate)) {
                return candidate;
            }
        }
        return last;
    }

    function genIntAddSub() {
        return guardGeneration(() => {
            const digits = Math.random() < 0.6 ? 3 : 4;
            let a = randomDigitInt(digits);
            let b = randomDigitInt(digits);
            const op = Math.random() < 0.5 ? '+' : '-';
            if (op === '-' && Math.random() < 0.4) {
                const sorted = [a, b].sort((x, y) => x - y);
                [a, b] = sorted;
            }
            const ans = op === '+' ? a + b : a - b;
            return { expression: `${a} ${op} ${b}`, answer: ans, category: 'int_add_sub', operator: op, a, b };
        }, (q) => {
            if (Math.abs(q.answer) <= 5) return false;
            if (q.operator === '+' && (q.a === 0 || q.b === 0)) return false;
            if (q.operator === '-' && q.a === q.b) return false;
            return true;
        });
    }

    function genMissingPercent() {
        return guardGeneration(() => {
            const base = randomInt(800, 4500);
            const pctOptions = [25, 35, 45, 55, 65, 75];
            const pct = pctOptions[randomInt(0, pctOptions.length - 1)];
            const value = (base * pct) / 100;
            return {
                expression: `_ % of ${base} = ${value.toFixed(1)}`,
                answer: Math.round(pct),
                category: 'missing_percent',
                operator: '%',
                base,
                pct,
            };
        }, (q) => !isTrivialPercent(q.pct));
    }

    function genDecDiv() {
        return guardGeneration(() => {
            const numerators = [48, 56, 64, 72, 84, 90, 98, 120, 144, 156];
            const denoms = [0.2, 0.4, 0.8, 1.25];
            const numerator = numerators[randomInt(0, numerators.length - 1)];
            const denom = denoms[randomInt(0, denoms.length - 1)];
            const answer = Math.round((numerator / denom) * 100) / 100;
            return { expression: `${numerator} / ${denom}`, answer, category: 'dec_div', operator: '/', numerator, denom };
        }, (q) => q.denom !== 1 && q.numerator !== q.denom && q.answer !== q.numerator);
    }

    function genDecMult() {
        return guardGeneration(() => {
            const bases = [120, 150, 180, 200, 240, 360, 420];
            const factors = [0.3, 0.4, 0.6, 1.25];
            const base = bases[randomInt(0, bases.length - 1)];
            const factor = factors[randomInt(0, factors.length - 1)];
            const answer = Math.round(base * factor * 100) / 100;
            return { expression: `${base} × ${factor}`, answer, category: 'dec_mult', operator: '×', base, factor };
        }, (q) => q.factor !== 1 && q.base !== 0);
    }

    function genMissingEquation() {
        return guardGeneration(() => {
            const template = weightedChoice({
                proportion: 4,
                balance_add: 3,
                prod_missing: 2,
                digit_missing: 1,
            });

            if (template === 'proportion') {
                const a = randomInt(4, 12);
                const b = randomInt(3, 11);
                const left = a * b;
                const denLeft = a;
                const denRight = [3, 4, 5, 6, 7][randomInt(0, 4)];
                const numRight = (left * denRight) / denLeft;
                return {
                    expression: `${left} / ${denLeft} = _ / ${denRight}`,
                    answer: Math.round(numRight),
                    category: 'missing_equation',
                    operator: '/',
                    a: left,
                    b: denLeft,
                };
            }

            if (template === 'balance_add') {
                const x = randomInt(50, 500);
                const y = randomInt(50, 500);
                const total = x + y;
                const z = randomInt(50, 500);
                const missing = total - z;
                return {
                    expression: `${x} + ${y} = ${z} - _`,
                    answer: Math.round(missing),
                    category: 'missing_equation',
                    operator: '+',
                    a: x,
                    b: y,
                };
            }

            if (template === 'prod_missing') {
                const a = randomInt(2, 30);
                const b = randomInt(2, 20);
                const prod = a * b;
                const candidates = Array.from({ length: 19 }, (_, idx) => idx + 2).filter((d) => prod % d === 0);
                const c = candidates[randomInt(0, candidates.length - 1)];
                const missing = prod / c;
                return {
                    expression: `${a} × ${b} = ${c} × _`,
                    answer: Math.round(missing),
                    category: 'missing_equation',
                    operator: '×',
                    a,
                    b,
                };
            }

            const first = randomDigitInt(2);
            const missingDigit = randomInt(0, 9);
            const tail = randomInt(10, 99);
            const second = 5000 + missingDigit * 100 + tail;
            const total = first + second;
            return {
                expression: `${first} + 5_${tail} = ${total}`,
                answer: Math.round(missingDigit),
                category: 'missing_equation',
                operator: '+',
                a: first,
                b: second,
            };
        }, (q) => {
            if (q.operator === '+' && (q.a === 0 || q.b === 0)) return false;
            if (q.operator === '×' && (q.a === 1 || q.b === 1)) return false;
            return true;
        });
    }

    function genIntMult() {
        return guardGeneration(() => {
            const a = randomInt(18, 320);
            const factors = [6, 7, 8, 9, 11, 12];
            const b = factors[randomInt(0, factors.length - 1)];
            return { expression: `${a} × ${b}`, answer: a * b, category: 'int_mult', operator: '×', a, b };
        }, (q) => q.a !== 1 && q.b !== 1);
    }

    function genPercentOf() {
        return guardGeneration(() => {
            const base = randomInt(150, 800);
            const pct = [15, 20, 25, 35, 40, 60][randomInt(0, 5)];
            return {
                expression: `${pct}% of ${base}`,
                answer: Math.round((base * pct) / 100),
                category: 'percent_of',
                operator: '%',
                base,
                pct,
            };
        }, (q) => !isTrivialPercent(q.pct));
    }

    function genPercentIncrease() {
        return guardGeneration(() => {
            const base = randomInt(80, 980);
            const pct = [8, 10, 12, 15][randomInt(0, 3)];
            return {
                expression: `${base} + ${pct}%`,
                answer: Math.round(base * (1 + pct / 100)),
                category: 'percent_increase',
                operator: '%',
                base,
                pct,
            };
        }, (q) => !isTrivialPercent(q.pct));
    }

    const round2Generators = [genMissingPercent, genDecDiv, genDecMult, genIntAddSub];
    const round3Generators = [genMissingEquation, genIntMult, genPercentOf, genPercentIncrease];

    function chooseGenerator(generators) {
        const idx = randomInt(0, generators.length - 1);
        return generators[idx];
    }

    function generateRound2Question() {
        return chooseGenerator(round2Generators)();
    }

    function generateRound3Question() {
        return chooseGenerator(round3Generators)();
    }

    function generateRound2Quiz(n) {
        return Array.from({ length: n }, () => generateRound2Question());
    }

    function generateRound3Quiz(n) {
        return Array.from({ length: n }, () => generateRound3Question());
    }

    window.AdvancedRounds = {
        generateRound2Question,
        generateRound2Quiz,
        generateRound3Question,
        generateRound3Quiz,
    };
})();
