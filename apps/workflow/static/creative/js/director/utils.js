// apps/workflow/static/creative/js/director/utils.js

(function() {
    const { SCHEMA, DEFAULTS, TYPES } = window.DirectorConfig;

    window.DirectorLogic = {
        initializeStrategy: (savedConfigMap, assetsMap, sourceLang = 'zh') => {
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
            return window.DirectorLogic.computeDerivedState(strategy, sourceLang);
        },

        computeDerivedState: (currentStrategy, sourceLang) => {
            const nextStrategy = JSON.parse(JSON.stringify(currentStrategy));

            // Narration 语速适配
            const narrationRateField = SCHEMA.narration.speaking_rate;
            if (narrationRateField.options_map) {
                const simpleLang = sourceLang.split('-')[0].toLowerCase();
                const preset = narrationRateField.options_map[simpleLang] || narrationRateField.options_map['zh'];
                nextStrategy.narration.speaking_rate._runtime = { options: preset.options, unit: preset.unit };
            }

            // Localize 语速适配
            // Director 模式下 target_lang 是单值 value，不再是 values_str
            const locLang = nextStrategy.localize.target_lang.value || 'en';
            const locRateField = SCHEMA.localize.speaking_rate;
            if (locRateField.options_map) {
                const preset = locRateField.options_map[locLang] || locRateField.options_map['en'];
                nextStrategy.localize.speaking_rate._runtime = { options: preset.options, unit: preset.unit };
            }

            // A. Perspective -> Character Name
            const perspVal = nextStrategy.narration.perspective.value;
            // 如果 runtime 对象不存在则初始化
            if (!nextStrategy.narration.perspective_character._runtime) {
                nextStrategy.narration.perspective_character._runtime = {};
            }
            // 只有选了 first_person 才显示
            nextStrategy.narration.perspective_character._runtime.hidden = (perspVal !== 'first_person');

            // B. Scope -> Start/End
            const scopeVal = nextStrategy.narration.scope.value;
            const isRange = (scopeVal === 'episode_range');

            ['scope_start', 'scope_end'].forEach(field => {
                if (!nextStrategy.narration[field]._runtime) nextStrategy.narration[field]._runtime = {};
                nextStrategy.narration[field]._runtime.hidden = !isRange;
            });

            return nextStrategy;
        },

        calcCombinations: () => 1 // 导演模式永远是 1
    };
})();