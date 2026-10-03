# Security / 安全边界

Run only commands you explicitly trust and choose. The runner is not an OS sandbox: an oracle can access/delete files, execute programs, use credentials if explicitly provided, or reach the network. Explicit argv avoids shell interpolation but does not make a destructive program safe. Use a disposable local workspace and environment without secrets. Windows Jobs and POSIX process groups manage supported descendants for timeout/output bounds, not security confinement; POSIX daemon escape is unsupported.

仅执行自己选择且可信的本地测试命令，不传入生产凭据或个人数据。payload 和失败签名会保存在报告中；发布前去除敏感内容。环境和本机路径参与私有缓存身份，但默认报告只暴露哈希键。临时候选写入系统临时目录；本地其他同权限进程可能读取。没有云上传、遥测或跨运行持久缓存。

Send security reports through a private channel agreed with the maintainer; no private reporting endpoint has been established yet. Do not place exploit payloads, secrets or private reproductions in public issues. Supported scope is finite JSON manifests and trusted local commands; unsupported or unknown state must not be used as evidence that a production system is safe.
