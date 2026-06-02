# 当前持仓补研究优先级清单

日期：2026-06-02
生成时间：2026-06-02_094121
模块：portfolio_research_backlog
版本：v1.0

## 1. 读取文件

- `README.md`
- `docs/PROJECT_MEMORY.md`
- `docs/WORKFLOW.md`
- `docs/FILE_NAMING.md`
- `docs/modules/ETF_RESEARCH.md`
- `docs/modules/STOCK_RESEARCH.md`
- `research/portfolio/portfolio_snapshot_2026-06-02_092310.md`
- `research/portfolio/portfolio_snapshot_2026-06-02_092310.json`
- `research/etfs/etf_registry.json`
- `research/stocks/stock_registry.json`
- `research/logs/decision_log.md`

## 2. 口径和边界

- 本清单只按当前仓位比例、是否缺档、主题/行业集中度生成优先级。
- 不使用市值、成本金额、盈亏金额，也不使用盈亏比例作为排序依据。
- 本清单不提供买卖建议，不提供调仓动作。
- 范围为当前持仓中登记状态为 `to_research` 或无时间戳档案的标的。
- 已建档 ETF 不纳入本次补档 backlog；其后续数据缺口可在 ETF 档案复核中单独处理。

## 3. 优先级规则

| 优先级 | 判定规则 |
| --- | --- |
| P0 | 影响后续操作建议的关键缺档标的：债券/现金承接工具、单只未建档 ETF 仓位较高、未建档主题集中度较高、或单只未建档股票仓位达到 2% 左右。 |
| P1 | 仓位超过 1% 的未建档股票/ETF，或虽然单只不极高但属于组合集中主题，需要尽快补研究。 |
| P2 | 仓位低于 1% 或当前可暂缓的未建档标的。 |

## 4. P0：影响操作建议，必须优先补研究

| 代码 | 名称 | 类型 | 当前仓位比例 | 缺失内容 | 为什么是 P0 | 应进入模块 | 需要 Tushare 数据 | 需要绑定主线 | 研究完成后影响模块 |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| 511360 | 短融ETF海富通 | ETF | 35.04% | 无时间戳 ETF 档案；待确认资产类型、久期/信用风险、流动性、份额变化、现金替代边界。 | 仓位比例最高，且承担债券/现金仓角色；后续操作建议需要先确认它是否适合作为仓位收缩承接工具。 | ETF_RESEARCH | 是 | 否，绑定债券/现金仓角色即可 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 159992 | 创新药ETF银华 | ETF | 6.22% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 当前最大未建档权益 ETF；创新药/医药组合占比 8.93%，会直接影响主题集中度和后续操作建议。 | ETF_RESEARCH | 是 | 是，需绑定创新药/医药主线或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 512070 | 证券保险ETF易方达 | ETF | 4.99% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 证券/券商/保险 ETF 合计 10.62%，本标的是其中最大未建档单只，影响金融主题是否过度集中。 | ETF_RESEARCH | 是 | 是，需绑定金融证券主题或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 159842 | 券商ETF银华 | ETF | 4.37% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 与 512070、512880 共同形成 10.62% 金融证券暴露，缺档会阻断后续对该主题的组合判断。 | ETF_RESEARCH | 是 | 是，需绑定金融证券主题或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002920 | 德赛西威 | 股票 | 2.45% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 当前仓位最高的未建档个股；个股档案缺失会影响股票仓 22.14% 的后续操作建议。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定智能汽车/无人驾驶或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002352 | 顺丰控股 | 股票 | 2.01% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 单只未建档股票仓位达到 2% 左右；需要先确认其是长期核心、波段、观察还是非主线持仓。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定有效主线；若无则标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |

## 5. P1：仓位较高或主题集中，需要尽快研究

| 代码 | 名称 | 类型 | 当前仓位比例 | 缺失内容 | 为什么是 P1 | 应进入模块 | 需要 Tushare 数据 | 需要绑定主线 | 研究完成后影响模块 |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| 159378 | 通用航空ETF永赢 | ETF | 2.52% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 单只仓位超过 2%，且军工/航天/低空/卫星组合合计 10.00%，需要尽快确认主题角色。 | ETF_RESEARCH | 是 | 是，需绑定低空经济/通用航空或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 512710 | 军工龙头ETF富国 | ETF | 2.24% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 军工/航天/低空/卫星组合集中度较高，本 ETF 未建档会影响该组风险判断。 | ETF_RESEARCH | 是 | 是，需绑定军工/国防或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 603596 | 伯特利 | 股票 | 1.79% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且智能汽车相关个股组合占比 4.24%，需要尽快明确角色。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定智能汽车/无人驾驶或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002625 | 光启技术 | 股票 | 1.78% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且处于军工/航天/低空/卫星集中组，需要尽快补公司级研究。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定军工/低空/新材料主题或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 000970 | 中科三环 | 股票 | 1.75% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且有色/稀土/资源组合合计 7.73%，需要确认是否加剧主题集中。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定稀土/有色主题或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 513180 | 恒生科技ETF华夏 | ETF | 1.61% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、汇率/港股风险、组合重叠。 | 仓位超过 1%，且属于科技暴露，需要和 A 股 AI/半导体仓位区分。 | ETF_RESEARCH | 是 | 是，需绑定港股科技/AI 相关主题或标记为跨市场科技暴露 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 512400 | 有色金属ETF南方 | ETF | 1.58% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 仓位超过 1%，且有色/稀土/资源组合合计 7.73%，需要确认是否属于可保留副线或主题仓。 | ETF_RESEARCH | 是 | 是，需绑定有色/资源主题或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 600764 | 中国海防 | 股票 | 1.57% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且位于军工/航天/低空/卫星集中组，需要补公司级研究。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定军工/国防信息化主题或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002241 | 歌尔股份 | 股票 | 1.41% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且涉及 AI/半导体/科技组合暴露，需要确认是主线受益还是消费电子波段。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定 AI 终端/消费电子或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 688032 | 禾迈股份 | 股票 | 1.36% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，需要确认其新能源/电力设备属性和当前主线适配度。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定电力设备/新能源或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 688333 | 西安铂力特 | 股票 | 1.34% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且可能涉及高端装备/军工链，需要确认公司逻辑和主线归属。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定高端装备/军工或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 300724 | 捷佳伟创 | 股票 | 1.29% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，需要确认光伏设备/电力设备链条是否仍匹配当前主线。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定电力设备/新能源或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 688439 | 振华风光 | 股票 | 1.21% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且位于军工/航天/低空/卫星集中组，需要补公司级研究。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定军工电子或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002258 | 利尔化学 | 股票 | 1.16% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，需要确认化工/农业链条是否有有效主线支持。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定化工/农业相关主题或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 603087 | 甘李药业 | 股票 | 1.03% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位超过 1%，且创新药/医药组合占比 8.93%，需要确认医药组内部角色。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定医药/创新药或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |

## 6. P2：小仓位或暂缓

| 代码 | 名称 | 类型 | 当前仓位比例 | 缺失内容 | 为什么是 P2 | 应进入模块 | 需要 Tushare 数据 | 需要绑定主线 | 研究完成后影响模块 |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| 562800 | 稀有金属ETF嘉实 | ETF | 0.82% | 无时间戳 ETF 档案；待确认跟踪指数、估值、趋势、流动性/份额、同类替代和组合重叠。 | 单只仓位低于 1%，虽属于有色/稀土/资源组合，但可排在 P0/P1 之后。 | ETF_RESEARCH | 是 | 是，需绑定稀有金属/资源主题或标记为未评级主题 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 002041 | 登海种业 | 股票 | 0.63% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位低于 1%，暂不构成主要组合影响，可在高仓位标的之后研究。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定农业/种业主题或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 300627 | 华测导航 | 股票 | 0.58% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位低于 1%，虽处于军工/航天/低空/卫星集中组，但单只影响较小。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定卫星导航/低空经济或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 603903 | 中持股份 | 股票 | 0.42% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位低于 1%，且不在当前主要高占比主题中，可暂缓。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定环保/公用事业或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |
| 300760 | 迈瑞医疗 | 股票 | 0.36% | 无个股档案；待补商业逻辑、财务质量、业绩趋势、估值赔率、趋势资金、风险惩罚和仓位角色。 | 仓位低于 1%，虽属于创新药/医药组合，但单只比例较小，可在 P0/P1 之后研究。 | STOCK_RESEARCH | 是 | 是，需确认是否绑定医药/医疗器械或标记为非主线持仓 | PORTFOLIO_ANALYSIS、ACTION_PLAN、INTRADAY_ALERTS、POST_MARKET_REVIEW |

## 7. 数量汇总

| 优先级 | ETF 数量 | 股票数量 | 合计 |
| --- | ---: | ---: | ---: |
| P0 | 4 | 2 | 6 |
| P1 | 4 | 11 | 15 |
| P2 | 1 | 4 | 5 |
| 合计 | 9 | 17 | 26 |

## 8. 后续执行顺序

1. 先补 P0：`511360`、`159992`、`512070`、`159842`、`002920`、`002352`。
2. 再补 P1 中的集中主题：军工/低空、金融证券、有色/稀土、创新药/医药、智能汽车。
3. 最后补 P2 小仓位标的，或等用户更新持仓比例后再重排。

本清单完成的是研究优先级排序，不生成买卖清单，也不生成调仓动作。
