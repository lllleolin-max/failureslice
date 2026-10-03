# FailureSlice

Reduce a finite, ordered setup/test manifest while retaining prerequisites and the **same structured failure identity**. A release engineer can hand a support team a smaller reproducer with the actual oracle observations and a precisely scoped certificate. Offline, Python >=3.11, standard-library runtime, MIT.

将有限、有序的准备/测试步骤缩减为更小的复现清单，保留声明的前置条件和**相同的结构化失败签名**。适合发布/支持工程师交接复杂复现步骤；记录真实命令调用、重复观测及结论边界。所有示例均为公开的合成夹具；没有客户、收入或生产验证声明。

```powershell
py -3 -m venv .local/venv
.local/venv/Scripts/python -m pip install .
.local/venv/Scripts/python tools/demo.py .local/demo
.local/venv/Scripts/python -m unittest discover -s tests -v
.local/venv/Scripts/python tools/contrast.py --out .local/contrast.json
```

On Linux/macOS substitute `.local/venv/bin/python` for the Windows Python path. `tools/demo.py` discovers `sysconfig.get_path('scripts')` and executes the **registered installed console**, rather than a source shim. Destinations must be new. Expected demo: `CARDINALITY_MINIMUM_AND_INCLUSION_MINIMAL: size=3 calls=56 states=64`; the report retains `schema`, `seed`, `duplicate-import`, matching the SQLite duplicate-email signature. These are fixture expectations to verify, not production performance estimates.

中文用法：先创建虚拟环境并正常安装 wheel/包，再运行 demo。demo 生成显式本地 runner 配置（私有路径放在忽略目录），通过已安装的 CLI 产生 `report.json`。查看 `reduced_manifest` 交接复现步骤，查看 `evaluations` 追踪每个候选的签名及新调用次数。目标失败签名包含类型、操作和消息；不是“退出码非零就成功”。

SDK:

```python
from failureslice import Manifest, Step, Observation, Outcome, EvidenceOracle, reduce
manifest = Manifest((Step('setup'), Step('test', ('setup',))), {'code': 'E42'})
def oracle(steps):
    return Observation(Outcome.TARGET, {'code': 'E42'}) if len(steps) == 2 else Observation(Outcome.PASS)
evidence = EvidenceOracle(manifest, oracle, {'fixture': 'v1'}, repetitions=2, max_calls=20)
result = reduce(manifest, evidence, mode='exact', max_states=100)
assert result.complete
```

For real local tests use `CommandRunner` and `EvidenceOracle(manifest, runner, runner.identity, ...)`. The CLI is `failureslice manifest.json runner.json --out new-report.json [--mode exact|local] [--max-calls N] [--max-states N] [--repetitions N]`. Exit 0 means completed within the stated certificate; 3 means incomplete/no target/UNKNOWN; 2 means invalid configuration/output. Local completion is only the dependent-deletion condition named in the certificate.

The differentiating workflow is the interaction of failure identity, dependency-closed search, contradictory-repeat retention and certificate refusal: each can change which reproducer is accepted. This is not a new delta debugging algorithm. [Picire](https://github.com/renatahodovan/picire/blob/master/README.rst) already offers configurable parallel delta debugging and custom interestingness tests; its tester can be programmed to enforce signatures and dependencies. [Hypothesis](https://hypothesis.works/articles/how-hypothesis-works/) describes invariant-preserving shrinking, and its [current settings tutorial](https://hypothesis.readthedocs.io/en/latest/tutorial/settings.html) documents control of replay/generation phases. Sources checked 2026-10-03. We do not infer feature absence from documentation. The executable contrast is against clearly disclosed small ddmin variants, **not** an executed Picire/Hypothesis superiority claim.

为什么开发：包含 SQL 导入、配置、缓存和旧格式路径的失败清单，任意失败可能缩减成另一个错误或缺失前置条件。FailureSlice 要求签名匹配，重复结果冲突时保留全部证据，并在非单调场景中用有限枚举验证最小性。普通归约器也可编写等价 predicate；这里提供可复用的严格 manifest、命令协议、证据和有边界的证明工作流。它没有源码变换、输入生成、OS 沙箱或生产稳定性保证。

See [protocol/architecture and bounds](docs/ARCHITECTURE.md), [comparison and bounded pilot](docs/PILOT.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md), and [review iterations](docs/ITERATIONS.md). Run `python tools/archive_check.py HEAD --suite --demo --contrast` for a fresh exact Git archive, ordinary wheel, isolated venv, canonical module-byte comparison and installed workflow. GitHub Actions declares Ubuntu/Windows on Python 3.11/3.14; remote CI has not yet run.
