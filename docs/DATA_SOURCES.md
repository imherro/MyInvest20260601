# 数据源与权限

本文记录本项目可用的数据源、使用优先级和权限配置方式。新会话和新电脑开始研究任务前必须先阅读本文。

## 1. 核心原则

- A 股行情、指数、估值、资金和财务数据优先使用结构化数据源。
- 新闻、政策、券商观点和事件催化需要注明来源和日期。
- 研究报告必须写清楚数据来源，不能只写“市场数据显示”。
- 权限信息只记录配置方法，不提交真实 token。

## 2. 已知可用数据源

### Tushare

状态：本项目可使用 Tushare 数据权限。

用途：

- A 股日线行情
- 指数行情
- ETF/基金相关数据
- 财务指标
- 估值指标
- 交易日历
- 部分资金和基础数据

使用要求：

- 新会话在做市场仓位、主线、ETF、个股、组合分析前，应优先检查本地是否存在 Tushare token。
- 如果本地 Tushare token 可用，应优先用 Tushare 获取结构化行情和财务数据。
- 如果 Tushare 缺少某类数据，再补充公开网页、交易所、基金公司、指数公司或新闻来源。

本地配置：

```text
TUSHARE_TOKEN=你的token
```

真实 token 放在本地 `.env` 文件中。`.env` 已被 `.gitignore` 忽略，不能提交到 GitHub。

### BaoStock

状态：本项目可使用 BaoStock 作为免费、免注册、Python API 数据源。已在本机安装 `baostock==0.9.1`，并通过 `sh.601318` 日线行情拉取验证。

用途：

- A 股日、周、月 K 线行情
- A 股分钟 K 线行情，按 BaoStock 当前数据范围限制使用
- 指数日、周、月 K 线行情
- 部分季频财务数据
- 上证 50、沪深 300、中证 500 等成分股信息
- 与 Tushare 行情、交易日历、财务字段进行交叉验证

使用要求：

- BaoStock 不需要 token，不在 `.env` 中配置权限。
- 文件名和文件夹名不要命名为 `baostock`，避免影响 Python 导入。
- 在 Tushare 可用时，Tushare 仍作为主数据源；BaoStock 用于缺失字段补充、价格/成交量复核、历史行情交叉验证。
- 如果 Tushare 与 BaoStock 数据不一致，报告中必须列明字段、日期、两个来源的值，并标记为“需要复核”，不能直接择一覆盖。

本地安装：

```powershell
python -m pip install -r requirements.txt
```

也可单独安装：

```powershell
python -m pip install baostock pandas -i https://pypi.org/simple
```

### QMT / XtQuant

状态：本机已安装并登录国金证券 QMT 交易端，可通过 QMT 自带 `xtquant.xtdata` 获取行情数据。已验证 `601318.SH` 实时快照可用，并在补齐历史数据后成功读取 `2026-06-01` 至 `2026-06-03` 日线行情。

本机路径：

```text
D:\国金证券QMT交易端
```

用途：

- A 股实时行情快照
- A 股历史 K 线，需先通过 QMT 补齐本地历史数据
- 分钟线、tick、Level1 行情
- QMT 账号权限覆盖范围内的行情、合约基础信息和部分财务数据
- 盘中监控、实时价格确认、Tushare 和 BaoStock 关键字段交叉验证

使用要求：

- 使用前必须确认 QMT / MiniQMT 客户端已打开并登录。
- 当前 QMT `xtquant` 二进制模块支持 Python 3.6 至 3.11；本机已安装 Python 3.11 用于 QMT 数据测试。
- 不通过 QMT 交易接口自动下单，除非用户在单独会话中明确授权交易自动化范围。
- 历史 K 线如果返回空数据，应先调用 QMT 历史数据补齐接口，再读取。
- 报告中引用 QMT 数据时，应注明“QMT 本地终端行情”及数据时间。

## 3. 新电脑配置

新电脑 clone 项目后：

1. 复制 `.env.example` 为 `.env`。
2. 在 `.env` 中填写 `TUSHARE_TOKEN`。
3. 运行研究任务前，让 Codex 先检查 `.env` 是否存在。

示例：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

```text
TUSHARE_TOKEN=你的token
```

## 4. 新会话开场要求

研究类新会话开场必须包含：

```text
请先阅读 README.md、docs/PROJECT_MEMORY.md、docs/MODULES.md、docs/RUNBOOK.md、docs/DATA_SOURCES.md 和 research/logs/decision_log.md。
本项目已知可使用 Tushare 数据权限。做 A 股行情、指数、ETF、估值、财务、交易日历等研究时，请优先检查并使用本地 Tushare token；如果不可用，再说明缺失并使用其他可靠来源补充。
本项目已安装 BaoStock，可作为 Tushare 的免费补充和交叉验证源；使用时必须注明数据来源和日期。
本机已验证 QMT / XtQuant 可用于实时行情和本地历史行情补充；使用前确认 QMT 终端已登录，且仅做数据读取，不自动交易。
```

## 5. 数据源优先级

建议优先级：

1. Tushare：结构化行情、指数、财务、估值、交易日历。
2. QMT / XtQuant：实时行情、本地终端行情、盘中监控，以及关键价格字段交叉验证。
3. BaoStock：免 token 行情、指数、部分财务数据补充，以及 Tushare 关键字段交叉验证。
4. 交易所、指数公司、基金公司官网：规则、成分、ETF 信息。
5. 政府、监管、央行、部委官网：政策和宏观信息。
6. 公司公告和交易所公告：个股重大事件和财报。
7. 主流财经媒体和券商研报：事件、观点和交叉验证。

## 6. 输出要求

每份研究报告必须写：

- 使用了哪些数据源。
- 数据日期或区间。
- 哪些数据来自 Tushare。
- 哪些数据来自 QMT / XtQuant。
- 哪些数据来自网页或人工整理。
- 哪些关键数据缺失或需要复核。

## 7. 安全规则

- 不提交 `.env`。
- 不在 Markdown 报告中写真实 token。
- 不在聊天中完整暴露 token。
- 如果需要分享权限，只说明配置方法。
