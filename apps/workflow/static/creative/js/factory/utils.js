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
            // [修复] 适配新类型命名 (single/text 代替 fixed/custom)
            if (c.type === 'single' || c.type === 'text' || c.type === 'fixed' || c.type === 'custom') {
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

                // [核心修复] 智能填充
                // 不再粗暴地覆盖为 { type: 'fixed', value: val }
                // 而是根据默认配置的类型，决定填入 value 还是 values_str

                const defaultType = merged[key].type;

                if (defaultType === 'enum') {
                    // 如果默认是多选，历史值填入 values_str
                    merged[key].values_str = String(val);
                    // 保持 type: 'enum' 不变
                } else {
                    // 如果默认是单选(single) 或其他，填入 value
                    merged[key].value = String(val);

                    // 确保 type 正确 (将旧的 fixed 修正为 single)
                    if (defaultType === 'fixed') {
                        merged[key].type = 'single';
                    }
                    // 如果已经是 single/text/range，保持原样，只更新值
                }
            }
        }
        return merged;
    }
};