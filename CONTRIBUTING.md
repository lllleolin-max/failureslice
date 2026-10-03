# Contributing / 贡献

Use Python 3.11+ and a local virtualenv. Install normally, run `python -m unittest discover -s tests -v`, execute `tools/demo.py` and `tools/contrast.py` with fresh ignored destinations. Keep candidate construction and observation semantics explicit. A changed reducer needs an independent tiny exhaustive oracle; test count alone is not evidence. Preserve primary-source credits and never report a heuristic as a minimum.

贡献前请说明支持范围、复现命令、失败/修复结果及剩余限制。不要加入个人数据、凭据或绝对本机路径到 tracked 文件。所有原始安装/执行日志置于 `.local/`，safe receipts 只保留必要结果。审查前使用 `tools/archive_check.py HEAD --suite --demo --contrast` 正常 wheel 验证已提交版本。CI 配置存在不代表远端 CI 已通过。
