# apifox-watch

定期爬取 Apifox 在线文档站，把 dump + 生成的 OpenAPI 提交到 git，
通过 `git log` / `git diff` 跟踪接口变更。

## 文件

- `apifox_scrape.py` —— 主爬虫，输出 `apifox-dump/<projectId>/`
- `apifox_to_openapi.py` —— dump → `openapi.yaml`
- `apifox_split_openapi.py` —— `openapi.yaml` → `openapi-split/*.yaml`
- `scrape.sh` —— 一键跑完三步，有变化则推到 `scrape/<date>` 分支并开 PR（无变化则跳过）
- `apifox-dump/<projectId>/` —— 爬下来的产物

## 配置

环境变量（默认值在 `scrape.sh` 里）：

- `APIFOX_DOMAIN` —— 默认 `openapi.qixiangyun.com`
- `APIFOX_PROJECT_ID` —— 默认 `2393904`

## 手动跑一次

```bash
./scrape.sh
gh pr list             # 看刚开的 PR
```

每月跑一次会在 `scrape/<YYYY-MM-DD>` 分支上开 PR 到 main，
diff 检查后再 merge。

## 定时任务

已在 crontab 注册，每月 1 号 03:17 跑一次（见 `crontab -l`）。
日志写到 `scrape.log`（已 gitignore）。
