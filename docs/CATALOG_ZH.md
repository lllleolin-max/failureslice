# 项目说明与复现入口

**FailureSlice 0.1.0**：离线缩减有前置条件的有限测试/准备步骤清单，要求缩减后仍触发同一结构化失败签名。不是通用源码缩减器，也不宣称新发明 delta debugging。对发布/支持工程师而言，实际价值是避免把原问题缩成“缺少 setup”或另一个异常后再交接给同事。

在 Python >=3.11 的独立虚拟环境中正常安装：Windows 使用 `py -3 -m venv .local/venv` 和 `.local/venv/Scripts/python -m pip install .`；Linux 使用 `python -m venv .local/venv` 和 `.local/venv/bin/python -m pip install .`。已实测环境为 Windows/Python 3.14。CI 声明 Ubuntu/Windows × 3.11/3.14，但未把未执行的远端 CI 当成通过证据。

运行 `.local/venv/Scripts/python tools/demo.py .local/demo`。脚本查询 sysconfig 的 scripts 目录并执行已注册安装的 failureslice CLI，生成真实 runner 配置和报告。SQLite 示例从 6 步缩减到 `schema`、`seed`、`duplicate-import` 三步，实际 56 次命令调用、64 个候选状态，目标签名为 duplicate-import 操作的 users.email 唯一约束异常。报告含每次重复观测、签名、缓存键及新调用数，适合作为人工审阅后的复现交接材料。

运行 `.local/venv/Scripts/python tools/contrast.py --out .local/contrast.json`，执行同一输入、两次重复和同一调用上限的四种方法。主场景中，忽略签名但补齐前置步骤的 ddmin 使用 10 次调用得到了两步的 JSON 错误；带签名 predicate 的普通 ddmin 使用 18 次调用保留三步目标错误；FailureSlice 完整枚举使用 56 次调用保留三步并完成最小性证据。无旧格式错误的标准成功场景中，普通带签名 ddmin 同样成功且更省调用。60 次调用上限的反例中，普通 heuristic 得到三步目标错误，而完整枚举仍为 12 步/UNKNOWN。工具不把更慢但有证书描述为整体更优。

技术实现为固定顺序的依赖闭合子集空间、实际命令数组 runner、结构化 outcome 状态、保留冲突的重复观测缓存和有状态/调用边界的归约器。exact 模式不假设单调性；完整检查所有允许子集后才给出基数最小且包含最小的证书，报告并列最小解。local 模式只声明测试过的“删除一步并删除所有依赖步骤”条件，不能把它提升为任意多步删除下的最小性。

资源与失败边界：最多 64 步；JSON 1 MiB/深度 32/精确整数边界；命令时间、stdout+stderr 字节、重复、状态和调用数均有显式上限。目标失败、成功、其他失败、无效 setup、超时、执行错误、重复冲突和未完成观测各自保留。Windows 使用启动前分配的 Job Object，超时和输出超限时终止子进程树；POSIX 进程组支持不脱离新 session 的子进程。明确选定的本地命令拥有用户权限，这不是 OS 沙箱。少量重复不能证明没有偶发失败，隐藏外部状态也不能由哈希证明稳定。

自审三轮都针对完成后的初始实现，旧/新版本正常 archive wheel 的相同 probe 分别失败/通过：诊断耗时被误当作失败身份；浅冻结允许外部字典改写历史缓存；声明环境变化时混合证据仍生成最小性证书。独立的数学测试文件用集合关系构造小实例完整 oracle，与 reducer 分开实现；它并非另一个人的独立评分。最终独立审查分数由根代理另行填写，构建者没有假定商业、技术或创新分数已达标。

商业试点假设：五个经脱敏的本地失败复现、每个 <=12 步/512 次调用，比较目标复现率、无效调用、步骤数和人工排查时间。假设人工排查原需 20 分钟、oracle 一次一秒，100 次调用的机器成本约 100 秒；只有节省人工时间大于清单编写/复位成本时才有净收益。这不是实测节省，也没有客户、收入、采用率或付费意愿证据。MIT 许可、严格格式和正常 CLI/SDK 安装降低接入门槛；非单调 exact 的指数成本及签名/依赖声明错误仍是实际限制。

参考 [Picire 官方 README](https://github.com/renatahodovan/picire/blob/master/README.rst) 与 [Hypothesis 作者机制说明](https://hypothesis.works/articles/how-hypothesis-works/)，2026-10-03 核验。它们已提供归约、interestingness predicate 或保持生成不变量的 shrinking；可给 Picire 自定义同等签名/依赖 predicate。这里的可检验区分是可复用清单、命令协议、冲突证据和有限证书的交互，不是“竞品做不到”，也没有运行竞品本身后声称胜出。
