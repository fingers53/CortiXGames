(function () {
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

    function genIntAddSub() {
        const digits = Math.random() < 0.7 ? 3 : 4;
        let a = randomDigitInt(digits);
        let b = randomDigitInt(digits);
        const op = Math.random() < 0.5 ? '+' : '-';
        if (op === '-' && Math.random() < 0.3) {
            const sorted = [a, b].sort((x, y) => x - y);
            [a, b] = sorted;
        }
        const expr = `${a} ${op} ${b}`;
        const ans = op === '+' ? a + b : a - b;
        return { expression: expr, answer: ans, category: 'int_add_sub' };
    }

    function genIntDivInt() {
        const q = randomInt(6, 80);
        const divisors = [3, 5, 7, 9, 12, 15, 16, 17, 48];
        const d = divisors[randomInt(0, divisors.length - 1)];
        const n = q * d;
        return { expression: `${n} / ${d}`, answer: n / d, category: 'int_div_int' };
    }

    function genIntMult() {
        const a = randomInt(24, 499);
        const factors = [6, 7, 8, 9, 12];
        const b = factors[randomInt(0, factors.length - 1)];
        return { expression: `${a} × ${b}`, answer: a * b, category: 'int_mult' };
    }

    function genDecDiv() {
        const numerators = [48, 56, 64, 72, 84, 90, 98, 120];
        const denoms = [0.2, 0.4, 0.8];
        const numerator = numerators[randomInt(0, numerators.length - 1)];
        const denom = denoms[randomInt(0, denoms.length - 1)];
        return { expression: `${numerator} / ${denom}`, answer: numerator / denom, category: 'dec_div' };
    }

    function genDecMult() {
        const bases = [90, 120, 135, 144, 150, 160];
        const factors = [0.3, 0.4, 0.6];
        const base = bases[randomInt(0, bases.length - 1)];
        const factor = factors[randomInt(0, factors.length - 1)];
        return { expression: `${base} × ${factor}`, answer: base * factor, category: 'dec_mult' };
    }

    function genPercentOf() {
        const base = randomInt(150, 400);
        const pct = [25, 50, 75][randomInt(0, 2)];
        return { expression: `${pct}% of ${base}`, answer: (base * pct) / 100, category: 'percent_of' };
    }

    function genPercentIncrease() {
        const base = randomDigitInt(3);
        const pct = 10;
        return { expression: `${base} + ${pct}%`, answer: base * 1.1, category: 'percent_increase' };
    }

    function genMissingPercent() {
        const base = randomInt(1000, 4000);
        const pctOptions = [25, 35, 50, 75];
        const pct = pctOptions[randomInt(0, pctOptions.length - 1)];
        const value = (base * pct) / 100;
        return { expression: `_ % of ${base} = ${value.toFixed(1)}`, answer: pct, category: 'missing_percent' };
    }

    function genMissingEquation() {
        const template = weightedChoice({
            proportion: 4,
            balance_add: 3,
            prod_missing: 2,
            digit_missing: 1,
        });

        if (template === 'proportion') {
            const a = randomInt(4, 12);
            const b = randomInt(2, 9);
            const left = a * b;
            const denLeft = a;
            const denRight = [3, 4, 5, 6][randomInt(0, 3)];
            const numRight = (left * denRight) / denLeft;
            return { expression: `${left} / ${denLeft} = _ / ${denRight}`, answer: numRight, category: 'missing_equation' };
        }

        if (template === 'balance_add') {
            const x = randomInt(50, 500);
            const y = randomInt(50, 500);
            const total = x + y;
            const z = randomInt(50, 500);
            const missing = total - z;
            return { expression: `${x} + ${y} = ${z} - _`, answer: missing, category: 'missing_equation' };
        }

        if (template === 'prod_missing') {
            const a = randomInt(2, 30);
            const b = randomInt(2, 20);
            const prod = a * b;
            const candidates = Array.from({ length: 19 }, (_, idx) => idx + 2).filter((d) => prod % d === 0);
            const c = candidates[randomInt(0, candidates.length - 1)];
            const missing = prod / c;
            return { expression: `${a} × ${b} = ${c} × _`, answer: missing, category: 'missing_equation' };
        }

        const first = randomDigitInt(2);
        const missingDigit = randomInt(0, 9);
        const tail = randomInt(10, 99);
        const second = 5000 + missingDigit * 100 + tail;
        const total = first + second;
        return { expression: `${first} + 5_${tail} = ${total}`, answer: missingDigit, category: 'missing_equation' };
    }

    const round2Generators = [
        genIntAddSub,
        genMissingEquation,
        genIntDivInt,
        genIntMult,
        genPercentOf,
        genDecDiv,
        genDecMult,
        genPercentIncrease,
        genMissingPercent,
    ];

    const round2Weights = [28, 6, 8, 6, 3, 1, 1, 2, 1];

    function generateRound2Question() {
        const totalWeight = round2Weights.reduce((sum, val) => sum + val, 0);
        let roll = Math.random() * totalWeight;
        for (let i = 0; i < round2Generators.length; i++) {
            const weight = round2Weights[i];
            if (roll < weight) {
                return round2Generators[i]();
            }
            roll -= weight;
        }
        return round2Generators[0]();
    }

    window.MavericRound = {
        generateQuestion: generateRound2Question,
    };
})();
