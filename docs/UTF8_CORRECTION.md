# Strict UTF-8 correction / 严格 UTF-8 修复

An independent review found that the promised UTF-8 oracle protocol was not enforced at the shared byte reader. Python `json.loads(bytes)` auto-detected UTF-16/32. Consequently invalid encoded output could be treated as the target failure and yield a complete certificate. The frozen rejected artifact remains `05451e86e91aacce04c6ecd7712be9b5fa1ee9b8`; its review assets were not modified. New scores or acceptance are not assumed.

独立审查发现了真实保证缺陷：原 JSON 字节入口让 Python 自动识别 UTF-16/32，而文档要求 UTF-8。因此非法协议输出曾获得完整最小性证书。修复保留原协议范围，在解析前显式严格解码 UTF-8。解码后的含 NUL 非法 JSON 仍由 JSON 语法拒绝，不能仅检查 BOM。合法 UTF-8 的重音字符、中文、emoji 和组合字符保持可用。

Only shared decoding behavior changed in the library. Manifest/config bytes now reject unsupported encodings before oracle construction (CLI 2). Oracle stdout with unsupported or malformed encoding becomes the existing ERROR category and cannot support TARGET; initial reduction is UNKNOWN/incomplete, with actual registered console exit 3 and a valid UTF-8 report. Raw source bytes remain unchanged. Byte, depth, integer and output limits are preserved; text SDK input also uses its real UTF-8 byte length.

库代码只修改共享解码边界；不改变失败签名、依赖闭合或非单调枚举规则。非法 manifest/runner 配置返回 2 且不执行命令，非法 stdout 归类 ERROR、拒绝证书并返回 3。源码和配置不被覆盖，报告仍使用 UTF-8。原少量重复、显式环境和可信本地命令的局限保持不变。

The unchanged independent encoding probe (SHA-256 `b68ddb617fc7b738b27ef0e19bfdcbd0dcf384f2b47631948511225adb16d1af`) ran against separately built ordinary wheels: direct parent `05451e86...` exited 1, direct correction child `cd880be2...` exited 0. Required `--out` destinations were new. UTF-8 remained accepted; UTF-16 BOM, UTF-32 BOM, UTF-16LE without BOM and UTF-32BE without BOM changed from complete/CLI 0 to ERROR/UNKNOWN/CLI 3. [Safe receipt](utf8-correction-receipt.json) records those measured observations.

Current CI's real workflow command remains `python tools/archive_check.py HEAD --suite --demo --contrast`. It builds an ordinary wheel in a new venv, compares every module with Git/archive/wheel/site bytes, runs the installed SDK tests and registered console, and executes fair synthetic contrasts. Target interpreter calls use `-I -X utf8`; package import location is explicitly checked. The local Windows/Python 3.14 run passed; matrix entries for Ubuntu/Windows × 3.11/3.14 are configured but no remote CI success is claimed. The initial harness path-encoding failure is disclosed in the iteration log.

运行当前完整验证：`python tools/archive_check.py HEAD --suite --demo --contrast --label utf8-review`（label 应使用新的值）。回归测试包含共享 reader、manifest/config、真实 stdout、Unicode 报告及预算边界。外部冻结审阅探针使用审阅者提供的原文件，加必填 `--out NEW_JSON` 在该 wheel 的解释器运行；不要改写历史附件或将它们搬进 CI 以制造额外成功记录。

Version remains **0.1.0**, because no release has been published. This correction fixes the reported protocol issue; it does not establish unflakiness, hidden-state identity, unlimited exact-search scale, an OS sandbox, remote CI success or a new independent passing score.
