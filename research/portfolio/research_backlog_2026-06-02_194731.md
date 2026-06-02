# 当前持仓补研究优先级清单
日期：2026-06-02  
生成时间：2026-06-02_194731  
版本：v1.4  
数据口径：ratio_only；不保存持仓金额、成本金额、盈亏金额或份额  
边界：研究优先级清单；不生成买卖建议，不生成调仓动作。
## 1. 本次变化
- `512710.SH 军工龙头ETF富国` 已完成时间戳 ETF 档案。
- 剩余待研究标的从 19 个降至 18 个。
- P1 从 14 个降至 13 个，P2 仍为 5 个。
## 2. 剩余统计
| 优先级 | ETF | 股票 | 合计 |
| --- | ---: | ---: | ---: |
| P0 | 0 | 0 | 0 |
| P1 | 2 | 11 | 13 |
| P2 | 1 | 4 | 5 |

## 3. 剩余标的

| 优先级 | 代码 | 名称 | 类型 | 当前比例 | 原因 | 目标模块 |
| --- | --- | --- | --- | ---: | --- | --- |
| P1 | 603596 | 伯特利 | 股票 | 1.79% | Intelligent vehicle stock; company profile needed. | STOCK_RESEARCH |
| P1 | 002625 | 光启技术 | 股票 | 1.78% | Defense/low-altitude/new-materials exposure. | STOCK_RESEARCH |
| P1 | 000970 | 中科三环 | 股票 | 1.75% | Nonferrous/rare-earth/resources concentration. | STOCK_RESEARCH |
| P1 | 513180 | 恒生科技ETF华夏 | ETF | 1.61% | Cross-market technology exposure. | ETF_RESEARCH |
| P1 | 512400 | 有色金属ETF南方 | ETF | 1.58% | Nonferrous/rare-earth/resources concentration. | ETF_RESEARCH |
| P1 | 600764 | 中国海防 | 股票 | 1.57% | Defense informatization exposure. | STOCK_RESEARCH |
| P1 | 002241 | 歌尔股份 | 股票 | 1.41% | Technology/AI terminal exposure needs validation. | STOCK_RESEARCH |
| P1 | 688032 | 禾迈股份 | 股票 | 1.36% | Power equipment/new-energy exposure needs validation. | STOCK_RESEARCH |
| P1 | 688333 | 西安铂力特 | 股票 | 1.34% | High-end equipment/defense chain exposure. | STOCK_RESEARCH |
| P1 | 300724 | 捷佳伟创 | 股票 | 1.29% | Photovoltaic equipment/power equipment exposure. | STOCK_RESEARCH |
| P1 | 688439 | 振华风光 | 股票 | 1.21% | Military electronics exposure. | STOCK_RESEARCH |
| P1 | 002258 | 利尔化学 | 股票 | 1.16% | Chemical/agriculture-chain role needs validation. | STOCK_RESEARCH |
| P1 | 603087 | 甘李药业 | 股票 | 1.03% | Medical group role needs validation. | STOCK_RESEARCH |
| P2 | 562800 | 稀有金属ETF嘉实 | ETF | 0.82% | Small position; related to resources group. | ETF_RESEARCH |
| P2 | 002041 | 登海种业 | 股票 | 0.63% | Small position; agriculture/seed exposure. | STOCK_RESEARCH |
| P2 | 300627 | 华测导航 | 股票 | 0.58% | Small position; satellite navigation/low-altitude exposure. | STOCK_RESEARCH |
| P2 | 603903 | 中持股份 | 股票 | 0.42% | Small position; environmental/public utility exposure. | STOCK_RESEARCH |
| P2 | 300760 | 迈瑞医疗 | 股票 | 0.36% | Small position; medical device exposure. | STOCK_RESEARCH |

## 4. 后续执行顺序

- P1 军工/低空组个股：`002625`、`600764`、`688439`。
- P1 资源组：`512400`、`000970`、`562800`。
- P1 智能车、科技和电力设备个股：`603596`、`002241`、`688032`、`688333`、`300724`。
- P2 小仓位标的等待更高影响档案完成后处理。

## 5. 边界

- 本清单只决定研究顺序。
- 不生成买入、卖出、加仓、减仓或调仓动作。
- 后续组合建议必须读取最新时间戳版本。
