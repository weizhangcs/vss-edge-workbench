// apps/workflow/static/creative/js/factory/utils.js
// [FIXED] 移除 export，直接挂载到 window

window.FactoryLogic = {
    parseEnum: (str) => {
        if (!str) return [];
        if (Array.isArray(str)) return str;
        return str.split(/[,，]/).map(s => s.trim()).filter(s => s);
    },

    calculateRange: (conf) => {
        if (conf.type !== 'range') return [];
        let start = parseFloat(conf.min);
        let end = parseFloat(conf.max);
        let step = parseFloat(conf.step);
        if (isNaN(start) || isNaN(end) || isNaN(step) || step <= 0) return [];

        let res = [];
        let count = 0;
        for (let i = start; i <= end + 0.00001; i += step) {
            res.push(Number(i.toFixed(2)));
            count++;
            if (count > 50) break;
        }
        return res;
    },

    calcCombinations: (domainStrategy) => {
        let total = 1;
        for (let key in domainStrategy) {
            if (key === '_meta') continue;

            let c = domainStrategy[key];
            // [新增] custom 类型计数为 1
            if (c.type === 'fixed' || c.type === 'custom') {
                total *= 1;
            } else if (c.type === 'enum') {
                let len = window.FactoryLogic.parseEnum(c.values_str).length;
                total *= (len > 0 ? len : 1);
            } else if (c.type === 'range') {
                let len = window.FactoryLogic.calculateRange(c).length;
                total *= (len > 0 ? len : 1);
            }
        }
        return total;
    },

    transformSavedConfig: (defaultStrategy, savedFlatConfig) => {
        const merged = JSON.parse(JSON.stringify(defaultStrategy));
        if (!savedFlatConfig || Object.keys(savedFlatConfig).length === 0) {
            return merged;
        }
        for (const key in savedFlatConfig) {
            if (Object.prototype.hasOwnProperty.call(merged, key)) {
                const val = savedFlatConfig[key];
                // 默认将保存的值视为 fixed，用户可在 UI 切换为 custom
                merged[key] = {
                    type: 'fixed',
                    value: String(val)
                };
            }
        }
        return merged;
    }
};