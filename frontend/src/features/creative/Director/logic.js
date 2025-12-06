// frontend/src/features/creative/Director/logic.js
import { SCHEMA, DEFAULTS } from './constants';

export const initializeStrategy = (savedConfigMap, assetsMap, sourceLang = 'zh') => {
    const strategy = {};
    ['narration', 'localize', 'audio', 'edit'].forEach(domain => {
        const domainSchema = SCHEMA[domain];
        const domainDefaults = DEFAULTS[domain];
        const savedDomainConfig = savedConfigMap[domain] || {};
        const hasAsset = assetsMap[domain]?.exists || false;

        let mode = 'NEW';
        if (hasAsset) mode = 'LOCKED';
        else if (domain === 'localize') mode = 'SKIP';

        const config = {};
        Object.keys(domainSchema).forEach(key => {
            const defaultVal = domainDefaults[key];
            let item = { ...defaultVal }; // Clone

            // 只处理单值恢复
            if (savedDomainConfig[key] !== undefined) {
                item.value = savedDomainConfig[key];
            }
            config[key] = item;
        });

        strategy[domain] = {
            ...config,
            _meta: { mode, has_asset: hasAsset, locked_source: assetsMap[domain]?.name }
        };
    });
    return computeDerivedState(strategy, sourceLang);
};

export const computeDerivedState = (currentStrategy, sourceLang) => {
    // Deep clone to avoid mutation issues
    const nextStrategy = JSON.parse(JSON.stringify(currentStrategy));

    // 1. Narration 语速适配
    const narrationRateField = SCHEMA.narration.speaking_rate;
    if (narrationRateField.options_map) {
        const simpleLang = sourceLang.split('-')[0].toLowerCase();
        const preset = narrationRateField.options_map[simpleLang] || narrationRateField.options_map['zh'];
        // 初始化 _runtime 对象
        if (!nextStrategy.narration.speaking_rate._runtime) nextStrategy.narration.speaking_rate._runtime = {};
        Object.assign(nextStrategy.narration.speaking_rate._runtime, { options: preset.options, unit: preset.unit });
    }

    // 2. Localize 语速适配
    const locLang = nextStrategy.localize.target_lang.value || 'en';
    const locRateField = SCHEMA.localize.speaking_rate;
    if (locRateField.options_map) {
        const preset = locRateField.options_map[locLang] || locRateField.options_map['en'];
        if (!nextStrategy.localize.speaking_rate._runtime) nextStrategy.localize.speaking_rate._runtime = {};
        Object.assign(nextStrategy.localize.speaking_rate._runtime, { options: preset.options, unit: preset.unit });
    }

    // 3. 动态显隐逻辑: Perspective -> Character Name
    const perspVal = nextStrategy.narration.perspective.value;
    if (!nextStrategy.narration.perspective_character._runtime) {
        nextStrategy.narration.perspective_character._runtime = {};
    }
    // 只有选了 first_person 才显示
    nextStrategy.narration.perspective_character._runtime.hidden = (perspVal !== 'first_person');

    // 4. 动态显隐逻辑: Scope -> Start/End
    const scopeVal = nextStrategy.narration.scope.value;
    const isRange = (scopeVal === 'episode_range');

    ['scope_start', 'scope_end'].forEach(field => {
        if (!nextStrategy.narration[field]._runtime) nextStrategy.narration[field]._runtime = {};
        nextStrategy.narration[field]._runtime.hidden = !isRange;
    });

    return nextStrategy;
};