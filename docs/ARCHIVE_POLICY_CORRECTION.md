# Canonical archive portability / 规范归档的可移植性

The real CI verification command must compare canonical Git module bytes with archive, ordinary wheel and installed site-packages bytes even when the caller inherits Windows-style text conversion. The previous verifier used plain `git archive`; under `core.autocrlf=true`, the archive contained CRLF-transformed library modules and its raw association check correctly failed.

实际 CI 验证工具必须在继承 `core.autocrlf=true` 时仍按 Git blob 原字节关联 archive、普通 wheel 和 site-packages。旧工具没有对归档命令设置临时规范导出策略，导致 LF 库源码在 ZIP 中变成 CRLF；原始相等断言因此真实失败。这个工具缺陷与此前 JSON receipt 的合法 CRLF 格式提示不同。

The correction uses only command-local `git -c core.autocrlf=false -c core.eol=lf archive`. It does not alter global/source/clone persistent settings, remove the true-policy scenario, normalize bytes for comparison, or weaken any association assertion. None of the seven library modules or mathematical reducer tests changed. The source tree remains `4ea83d9e02b2711e8fd6cfc2e8a3dab6f2cad057`, and version remains unpublished 0.1.0. This tool fix is not an extra application core correction cycle.

修复仅向单次归档命令添加临时配置；不修改全局 Git、不排除 true 环境、不在比较前替换行尾，也不放宽字节断言。新增真实 Git 回归测试同时检查 LF 文本、二进制和已有 CRLF blob 的原字节导出，并确认调用后仓库配置仍为 true/crlf。原 35 项应用测试保持不变，连同一项工具测试共 36 项。

The frozen independent probe SHA-256 is `8717b97b68554df8448402f6ba1e9294bc5de776632834b5e21434008f8b0e39`. Against a fresh full-history private clone of old `f4188c645b0b7c72054367fce6810e77e452551c`, it exited 1 with CANONICAL_ARCHIVE_ASSOCIATION: blob 300 bytes / 0 CRLF, archive 306 bytes / 6 CRLF. Against direct correction child `d8dc62ecbd74ea456bee52e0f37cb008359176d2`, the unchanged bytes exited 0, with both 300 bytes / 0 CRLF, all seven associations and the actual suite/console/contrast workflow passing. [Safe measured receipt](archive-policy-correction-receipt.json) preserves these results; raw logs are private and ignored.

The normal workflow remains `python tools/archive_check.py HEAD --suite --demo --contrast --label NEW_LABEL`. The external original audit probe needs `--repo REPO --commit SHA --out NEW_PRIVATE_DIR`; use the frozen file supplied by the reviewer unchanged. Ubuntu/Windows × Python 3.11/3.14 CI is configured. The inherited-policy workflow was actually run locally on Windows/Python 3.14; no remote CI or new independent acceptance is claimed here. Library/runtime limits from the architecture documentation are unchanged.
