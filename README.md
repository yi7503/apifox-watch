# apifox-watch — 七翔云开放平台 API 文档镜像

本仓库定期把 [Apifox 文档站 `openapi.qixiangyun.com`](https://openapi.qixiangyun.com)
（projectId `2393904`，branchId `2914965`）爬下来存到 git，
供 AI 在写七翔云对接代码时**离线、可 grep、可版本对比**地查阅接口定义。

> AI 在实现某个接口对接前，**先读这里的接口定义**，再写代码。
> 不要凭印象写字段名 —— Apifox 文档是单一事实来源。

---

## 给 AI：如何用这个仓库写接口

### 1. 先看模块总览

接口按 **14 个业务模块**组织。从 `apifox-dump/2393904/openapi-split/INDEX.md`
开始挑模块：

| 模块 | 接口数 | OpenAPI 文件 |
|---|---:|---|
| 申报业务 | 277 | `openapi-split/申报业务.yaml` |
| 发票业务 | 192 | `openapi-split/发票业务.yaml` |
| 数据业务 | 47 | `openapi-split/数据业务.yaml` |
| 登录业务（旧版） | 44 | `openapi-split/登录业务_旧版.yaml` |
| 登录业务（新） | 30 | `openapi-split/登录业务_新.yaml` |
| 进出口退税业务 | 27 | `openapi-split/进出口退税业务.yaml` |
| 办税小号业务 | 11 | `openapi-split/办税小号业务.yaml` |
| 产品订购 | 5 | `openapi-split/产品订购.yaml` |
| 法规库 | 5 | `openapi-split/法规库.yaml` |
| 平台基础服务 | 3 | `openapi-split/平台基础服务.yaml` |
| 平台查询 | 3 | `openapi-split/平台查询.yaml` |
| 风控报告 | 2 | `openapi-split/风控报告.yaml` |
| 平台接口鉴权 | 1 | `openapi-split/平台接口鉴权.yaml` |
| 办税助手 | 1 | `openapi-split/办税助手.yaml` |

每个 split yaml 是合法 OpenAPI 3.0，可直接喂给代码生成器或直接读。
最准的字段定义在这些 yaml 里。

### 2. 按 method/path 定位单个接口

整个项目 648 个接口的索引在 `apifox-dump/2393904/index.md`，按 method/path/name/folder
列出来，**最适合 grep**：

```bash
# 找一个接口（例如查"发起企业基本信息"）
grep -i "企业基本信息" apifox-dump/2393904/index.md

# 按路径找
grep "/v2/public/account/create" apifox-dump/2393904/index.md
# -> | POST | `/v2/public/account/create` | 账号创建 | ... | apis/398469975.json |
```

### 3. 读原始接口定义

`apifox-dump/2393904/apis/<apiId>.json` 是 Apifox 单接口的**完整原始描述**，
比 OpenAPI 信息更全（包含 `description`、`codeSamples`、`responseExamples` 等）。
写代码时建议同时看：

- `apis/<id>.json` 的 `description` —— 业务语义、踩坑点
- `apis/<id>.json` 的 `requestBody.jsonSchema` —— 请求字段（含中文 `title`、`type`、`required`）
- `apis/<id>.json` 的 `responses[].jsonSchema` —— 响应字段
- `apis/<id>.json` 的 `parameters.header` —— 必填请求头

单文件示意结构：

```jsonc
{
  "id": 398469975,
  "name": "账号创建",
  "method": "post",
  "path": "/v2/public/account/create",
  "description": "## 接口描述\n该接口用于税局已注册的登录账号信息在平台侧进行创建维护...",
  "parameters": { "header": [...], "query": [...], "path": [...], "cookie": [] },
  "requestBody": { "type": "application/json", "jsonSchema": {...} },
  "responses": [ { "code": 200, "jsonSchema": {...} } ],
  "responseExamples": [...],
  "codeSamples": [...]
}
```

### 4. 文档（非接口）

`apifox-dump/2393904/docs/<docId>.json` 是 Apifox 文档节点：对接指引、
公共错误码、发布日志、加密说明等。`description` / `content` 字段是 Markdown。
做对接前**强烈建议**先看：

- `开发必读 / 快速开始` 类目下的所有 doc
- 「平台公共 code 码」「加密说明」「调用模式」

入口同样是 `index.md` 末尾的 **Docs** 表。

2026 新版增值税的完整接口变化、动态表单和业务校验规则另见原始附件：
[`attachments/外部-新版增值税对接流程与业务规则.xlsx`](apifox-dump/2393904/attachments/外部-新版增值税对接流程与业务规则.xlsx)（12 个工作表）。

### 5. 配合 qxy-* skills 使用

仓库里只是**接口定义**。要真正发请求，签名 / OAuth / RSA 加密这些公共逻辑
建议复用：

- `qxy-common` skill —— OAuth 鉴权、`req_sign` 签名、`access_token` 缓存
- `qxy-invoice` skill —— 发票业务（192 接口）已封装
- `qxy-declaration` skill —— 申报业务

如果某个接口业务 skill 还没覆盖，按上面 1-3 步从 dump 里读定义后自己拼请求，
鉴权和签名走 `qxy-common`。

---

## Dump 目录结构

```
apifox-dump/2393904/
├── meta.json                  Apifox 项目元信息 (projectId/branchId)
├── tree.json                  Apifox 原始目录树 (含文件夹层级)
├── index.md                   全部 648 个 API + 362 个 doc 的可读索引
├── failures.json              本次爬取失败的节点 (Apifox 端 403 等)
├── openapi.yaml               全部接口的合并 OpenAPI 3.0 (7.8 MB)
├── openapi-split/
│   ├── INDEX.md               按业务模块拆分的索引
│   └── <模块>.yaml × 14       每个模块一份独立 OpenAPI
├── apis/<apiId>.json × 648    单个接口完整定义 (Apifox 原始 schema)
├── docs/<docId>.json × 362    单个文档节点 (Markdown content)
└── attachments/               Apifox 文档引用的离线附件
```

---

## 仓库运维（人类）

- 爬虫脚本：`apifox_scrape.py` → `apifox_to_openapi.py` → `apifox_split_openapi.py`
- 一键脚本：`scrape.sh` —— 三步串联，有变化推到 `scrape/<YYYY-MM-DD>` 分支并自动开 PR
- 定时：crontab 每月 1 号 03:17（`17 3 1 * *`）
- 日志：`scrape.log`（gitignored）
- 配置（环境变量）：`APIFOX_DOMAIN`（默认 `openapi.qixiangyun.com`）、`APIFOX_PROJECT_ID`（默认 `2393904`）
- 完整性：任一节点重试后仍失败或目录异常大幅收缩时停止，不生成或发布可疑快照；完整抓取后自动删除已下架节点和失效 split 文件
- 安全性：上游示例中的 Alibaba AccessKey ID 形态值会替换为 `<ALIBABA_ACCESS_KEY_ID>`

手动跑一次：

```bash
./scrape.sh
gh pr list      # 查看自动开的 PR
```

每月的 PR 在 `git diff` 里能直接看到 Apifox 上游接口的新增 / 修改 / 删除，
review 后 merge 即可。
