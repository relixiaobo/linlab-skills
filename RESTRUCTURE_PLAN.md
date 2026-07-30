# 仓库重组执行计划

状态: v4, 已按 codex review 三轮意见修订, 待复审
作者: Claude (结构分析会话, 2026-07-30)
修订记录:
v2 采纳 codex review 第一轮全部 5 条意见 — (1) 放弃 pytest, 保留 unittest discover;
(2) 区分 pinned condition 中 `skills[].path`(历史树, 不改)与 `ablations[].replacement`
(当前工作树, 必须改)两种路径语义, R6 grep 规则增加豁免;(3) Phase 4 改为显式
check-ID 清单 + 机器可比对的覆盖验收;(4) quick_validate 的校验内容内置进仓库成为
强制测试, 外部脚本降为可选交叉核对;(5) Phase 0 增加 preflight commit 与基线输出的
固定保存位置。
v3 采纳第二轮 3 条意见 — (1) 新增 R8: Node 为硬性必需依赖(集成检查直接调用 Node,
SKIP 不可行), 删除所有允许 node 缺失 SKIP 的表述, Phase 0 增加工具链预检;
(2) 新增 R9 基线对照规则: 默认基线全绿, 带病执行须提交 expected-failure allowlist,
各 Phase 验证门统一按"无新增失败、不恶化"判定, Phase 4 比对同时覆盖 `ok` 状态;
(3) 修正 P2 背景中 tests/unit 的测试风格表述(unittest, 非 pytest)。
v4 采纳第三轮 2 条意见 — (1) 消除 optional quick_validate 与 R9 的状态冲突:
基线 `quick_validate:<skill>` ×10 经改名映射对应强制检查 `skill-packages:<skill>`,
外部交叉核对改用全新 ID `external-quick-validate:<skill>`(无基线对应项, 允许
skipped);统一定义 `status: passed|failed|skipped` 语义, 不再用 `ok` 兼任 SKIP;
(2) Phase 0 基线命令块前补 `mkdir -p reports/restructure-baseline-20260730`。
执行方式: 按 Phase 顺序执行, 每个 Phase 一个独立 commit, 结束时必须通过该 Phase 的验证门。
本文档在最终 Phase 完成后删除或归档到 `reports/`。

---

## 一、背景:发现的问题

### P1 — evals/ 是一次未完成的迁移,新旧两套体系并存(最严重)

`evals/` 下同时存在:

- **新体系**(规范格式): `cases/`、`conditions/`、`suites/`、`runners/`、`judges/`、`schemas/`
- **旧体系**(按技能名组织,新体系明文反对): `evals/artifact-skills/`、
  `evals/code-review/`、`evals/data-analysis/`、`evals/feed-processing/`、
  `evals/presentation/`、`evals/shape-product-spec/`、`evals/video-studio/`

旧体系内部状态不一致:

- `evals/presentation/run_checks.py` 已是纯转发包装(转调 `tests/integration/presentation/`);
- `evals/data-analysis/` 仍持有真实 fixture(`real-data/`、`sample-data/`、`cases.yaml`、`README.md`),
  且被 `tests/integration/data-analysis/run_checks.py` 引用;
- `evals/code-review/`、`evals/video-studio/`、`evals/feed-processing/`、
  `evals/shape-product-spec/` 各有独立 `run_checks.py` + fixtures;
- `evals/artifact-skills/` 是遗留的 trigger/smoke 套件,由 `evals/run_artifact_skill_checks.py` 驱动。

后果: "评估数据放哪"有三个答案(`evals/<skill>/`、`evals/cases/`、`tests/fixtures/`),
取决于文件写作年代。旧体系约占 evals 下 113 个跟踪文件中的 50 个。

### P2 — 验证入口碎片化

README 的 Validate 一节需要约 6 条命令才能跑完所有检查。另外:

- `evals/run_all_skill_checks.py` 依赖仓库外的
  `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py`,跨机器即断;
- `tests/unit/` 是标准 unittest 用例(由 `unittest discover` 运行),`tests/integration/` 是自制 `run_checks.py` 脚本,双范式并存;
- feed-processing 的确定性检查仍在 `evals/feed-processing/`,未随其他技能搬入 `tests/integration/`。

### P3 — 根目录污染,技能(仓库主角)不可辨识

根目录 31 个条目中 9 个是技能、约 13 个是评估/测试/产物/工作区,结构上完全同构,
唯一的判别标准是目录内有无 `SKILL.md`(隐式约定)。干扰源:

- 6 个 `*-workspace/` 产物目录(已 gitignore,但堆在根目录);
- `rss-workspace/` 与 `feed-processing-workspace/` 是同一技能改名前后的两份工作区;
- `presentation.zip`、`Archive.zip`、`.DS_Store`(未跟踪的手工产物);
- `portfolio`、`reports`、`results` 等名字与技能名无法区分。

### P4 — 技能包违反自身规范

README 规定技能目录只含运行时资源(`SKILL.md`、`agents/`、`references/`、`scripts/`、`assets/`),但:

- `data-analysis/` 内有空的运行输出目录 `analysis_runs/`、自带 `.gitignore`、`.DS_Store`;
- 结构守门测试 `tests/integration/presentation/test_skill_structure.py` 只覆盖 presentation,
  未推广到其余 8 个技能。

### P5 — 技能清单只存在于散文文档

技能列表仅见于 README 散文和 `portfolio/SKILL_STATUS.md` 表格;第 10 个技能
(已退役的 `research`)在 `archive/` 下。没有一个结构位置能回答"有哪些 skill"。

---

## 二、目标结构

```text
linlab-skills/
├── skills/                  # 9 个在役技能; ls skills/ 即完整清单
│   ├── code-review/
│   ├── data-analysis/
│   ├── document/
│   ├── feed-processing/
│   ├── pdf/
│   ├── presentation/
│   ├── shape-product-spec/
│   ├── spreadsheet/
│   └── video-studio/
├── archive/                 # 退役技能(research), 位置不变
├── evals/                   # 只剩新体系: cases/ conditions/ suites/ runners/ judges/ schemas/
├── tests/                   # unit/ + integration/ + fixtures/, 含唯一的确定性总入口
├── reports/                 # 已审阅的评估报告(历史文档, 不改写)
├── results/                 # 原始运行输出(gitignore)
├── work/                    # 所有工作区产物, 取代 6 个 *-workspace/(gitignore)
├── PORTFOLIO.md             # 原 portfolio/SKILL_STATUS.md(可选项, 见 Phase 5)
└── README.md
```

## 三、非目标(评审时请确认边界)

- 不新写评估 case、不改 judge 打分逻辑、不改任何技能的行为和内容;
- 不改写 `reports/` 与 `results/` 中的历史文档里的旧路径(它们是当时的记录);
- 不把 `tests/integration/` 的 run_checks 脚本改造成 pytest(可作后续工作);
- `evals/artifact-skills/` 中 trigger 评估语义向 `evals/cases/` 的转换是独立后续任务,
  本计划只做文件安置与入口修正。

## 四、全局约束与风险

| # | 约束/风险 | 处置 |
| --- | --- | --- |
| R1 | **3 个 condition 固定了 `skills[].revision`**: `evals/conditions/presentation-main.json`、`presentation-image-improved.json`、`presentation-image-improved-no-visual-instructions.json`。runner 用 `git archive` 从历史 commit 物化技能,那些 commit 树中技能仍在根目录。**同一文件内存在两种路径语义**: `skills[].path` 与 ablation 的目标 `path`(包内相对路径)在历史/物化树中解析;`ablations[].replacement` 由 `evals/runners/evalctl.py:252` 按 `ROOT / replacement` 从**当前工作树**解析(`eval_lib.py:417` 在 validate 时同样按当前仓库校验其存在)。 | 这 3 个文件中的 `skills[].path` 与 ablation 目标 `path` **一律不改**。其中唯一带 ablation 的是 `presentation-image-improved-no-visual-instructions.json`,它的全部 `replacement` 值(`presentation/...`)**必须**改为 `skills/presentation/...`,否则 Phase 2 后 validate 即失败。另两个 pinned 文件无 ablation(已核实 grep 计数为 0),整文件不动。未固定 revision 的 condition 正常更新 `path`。执行前用 `grep -L revision evals/conditions/*.json` 复核清单。 |
| R2 | 目录移动丢失 git 历史 | 全部用 `git mv`,commit 后用 `git log --follow` 抽查 2-3 个文件确认 rename 被识别。 |
| R3 | 外部依赖 `~/.codex/.../quick_validate.py` 在执行机器上可能不存在,但它承担着真实校验(SKILL.md YAML frontmatter 合法性、允许字段、技能名格式、描述约束),简单 SKIP 会丢失覆盖 | Phase 4 把这些校验**内置进仓库**(`tests/integration/skills/test_skill_packages.py`),成为强制检查;外部 quick_validate 降为可选交叉核对,使用独立 ID `external-quick-validate:<skill>`(存在则跑、缺失则 `status=skipped` 并输出原因),与基线 ID 不复用(见 Phase 4)。覆盖验收以内置测试为准,不依赖外部脚本。 |
| R4 | 用户侧 `~/.agents/skills` 符号链接在 skills/ 移动后失效 | 不属于仓库变更;在 README 安装节更新命令,并在 PR 描述中提醒重新链接。 |
| R5 | 根目录 zip(`presentation.zip`、`Archive.zip`)可能是唯一副本 | **删除前必须获得仓库所有者确认**;未确认则移入 `work/` 保留。 |
| R6 | 隐藏引用遗漏 | 每个涉及移动的 Phase 结束前,对旧路径做全仓库 grep(排除 `.venv`、`__pycache__`、`results/`、`reports/`、`work/`),清零后才算完成。**豁免清单**(允许保留旧路径字符串、grep 时逐条人工核对而非机械清零): (a) 3 个 pinned condition 中的 `skills[].path` 与 ablation 目标 `path` 字段(见 R1);(b) 本文档 `RESTRUCTURE_PLAN.md` 中作为记录出现的旧路径。豁免项之外必须为 0 命中。 |
| R7 | `evals/runners/eval_lib.py` 对 condition `path` 的解析方式需确认 | Phase 2 第一步先读 runner 代码确认 path 是仓库相对路径且无其他技能路径假设,再动手。 |
| R8 | **Node 是必需依赖,不是可选项**: 除 `node-check` 外,feed-processing(`evals/feed-processing/run_checks.py:82`)、artifact-skills、presentation 的集成检查都直接调用 Node,缺 Node 时仅跳过 node-check 也无法使总入口通过 | Phase 0 预检把 `node` 在 PATH 上列为硬性前置条件,缺失即停止执行并回报。任何验证门都**不允许**以 SKIP 方式豁免 Node 相关检查。 |
| R9 | **基线对照规则**(各 Phase 验证门统一引用): 若允许"带病重构"而无明确规则,后续"全绿"门槛与基线失败项互相矛盾 | 默认要求 Phase 0 基线**全绿**,否则停止并回报。所有者确需带病执行时,须在 Phase 0 commit 中提交 expected-failure allowlist(`reports/restructure-baseline-20260730/expected-failures.json`,列出 check-ID 与失败摘要);此后每个验证门的判定为: **无新增失败,且 allowlist 内检查的失败状态不恶化**(基线 passed 的检查必须仍 passed)。状态语义统一为 `status: passed|failed|skipped`(基线旧格式的 `ok` 布尔按 true→passed、false→failed 折算),`skipped` 仅允许出现在无基线对应项的可选检查上;check-ID 比对(Phase 4)同时比对状态,不只比对 ID 存在性。 |

## 五、执行阶段

每个 Phase: 先做 → 跑该 Phase 验证门 → 单独 commit。任何验证门失败即停止并回报,不得跳过。

### Phase 0 — 预检与基线(preflight commit)

1. 从当前分支切出 `restructure/skills-layout`;把已批准的 `RESTRUCTURE_PLAN.md`
   作为本 Phase commit 的一部分纳入版本控制(在此之前不要求工作树 clean——本文档
   本身就是那个未跟踪文件;除本文档外不得有其他未提交变更)。
   工具链预检(R8): 确认 `node` 在 PATH 上、`.venv` 已安装
   `evals/requirements.txt` 与 `data-analysis/requirements.txt`;任一缺失即停止并回报,
   不进入基线步骤。
2. 建立基线并把输出保存到固定位置 `reports/restructure-baseline-20260730/`:
   ```sh
   mkdir -p reports/restructure-baseline-20260730
   .venv/bin/python evals/run_all_skill_checks.py > reports/restructure-baseline-20260730/run_all.json
   .venv/bin/python evals/runners/evalctl.py validate --suite evals/suites/representative-ab.json
   .venv/bin/python evals/runners/evalctl.py validate --suite evals/suites/presentation-image-smoke.json
   .venv/bin/python evals/runners/evalctl.py validate --suite evals/suites/presentation-image-assets-smoke.json
   .venv/bin/python evals/runners/evalctl.py validate --suite evals/suites/presentation-current-image-assets-ab.json
   python3 -m unittest discover -s tests/unit -p 'test_*.py'
   ```
   注: `run_all_skill_checks.py` 本身已内含 unittest discover、3 个 suite contract、
   全部技能检查、python-compile 与 node-check;单列命令用于失败时定位。
   `run_all.json` 中每个检查的 `name` 字段构成**基线 check-ID 集合**,是 Phase 4
   覆盖验收的比对基准。**不使用 pytest**——仓库测试为 unittest 风格且未声明 pytest
   依赖(评审确认项)。
3. 基线按 R9 处理: 默认要求**全绿**,有失败项即停止并回报所有者。所有者明确决定
   带病执行时,提交 `reports/restructure-baseline-20260730/expected-failures.json`
   (check-ID + 失败摘要),此后所有 Phase 的验证门按 R9 的
   "无新增失败、不恶化"规则判定。
4. 本 Phase commit 内容: `RESTRUCTURE_PLAN.md` + `reports/restructure-baseline-20260730/`
   (含 allowlist,如启用)。

验证门: 基线 JSON 已提交;check-ID 集合可从 `run_all.json` 机器提取;基线全绿或
allowlist 已提交并获所有者确认。

### Phase 1 — 根目录清理(低风险,不动 git 跟踪的技能/评估文件)

1. 新建 `work/`;把 6 个 `*-workspace/` 目录整体移入:
   `work/artifact-skills/`、`work/presentation/`、`work/feed-processing/`、
   `work/video-studio/`、`work/shape-product-spec/`、`work/rss/`。
2. 比对 `work/rss/` 与 `work/feed-processing/`(旧 `rss-workspace` 是 feed-processing
   改名前的工作区):内容重复则删 `work/rss/`,不重复则保留并在本文档记一笔。
3. `presentation.zip`、`Archive.zip`: 按 R5 处理(确认后删,或移入 `work/`)。
4. 删除根目录与各子目录游离的 `.DS_Store`。
5. 更新 `.gitignore`: 移除 `*-workspace/`,加入 `work/`。
6. 更新硬编码路径 `artifact-skills-workspace` → `work/artifact-skills`
   (已知位置: `evals/run_artifact_skill_checks.py` 第 67、415 行附近;再全仓库 grep 兜底)。

验证门: `evals/run_all_skill_checks.py` 与基线一致;`grep -rn 'workspace' --include='*.py' --include='*.json' --include='*.md'`(按 R6 排除规则)无指向旧目录名的活引用。

### Phase 2 — 技能归拢进 skills/

1. 按 R7 先读 `evals/runners/eval_lib.py`(及 `codex_exec_adapter.py`)确认 condition
   `path` 的解析假设。
2. `git mv` 9 个技能目录到 `skills/<name>`。`archive/` 不动。
3. 更新引用(已核实的清单,以 grep 兜底为准):
   - `evals/conditions/` 中**未固定 revision** 的 condition 的 `"path"` 字段
     (`baseline.json` 无 skills 字段则跳过;`data-analysis-enabled.json`、
     `presentation-enabled.json`、`shape-product-spec-enabled.json`、
     `presentation-no-visual-guidance.json` 等)→ `skills/<name>`。
   - **pinned condition 按 R1 处理**: `presentation-image-improved-no-visual-instructions.json`
     只改 `ablations[].replacement`(`presentation/...` → `skills/presentation/...`),
     `skills[].path` 与 ablation 目标 `path` 不动;`presentation-main.json`、
     `presentation-image-improved.json` 整文件不动。
   - `evals/run_all_skill_checks.py` 的**三处**硬编码: `SKILLS` 列表
     (`archive/research` 项不动)、`python_files` 列表中的技能脚本路径
     (`document/scripts/...`、`presentation/scripts/...`、`pdf/scripts/...`、
     `shape-product-spec/scripts/...`、`spreadsheet/scripts/...`、
     `video-studio/scripts/...`)、Node `--check` 脚本列表中的技能脚本路径
     (`document/`、`presentation/`、`feed-processing/`、`video-studio/` 下的 `.mjs`)。
   - `tests/integration/shape-product-spec/run_checks.py`、
     `tests/integration/presentation/test_render_and_html_tools.py`、
     `tests/integration/presentation/test_pptx_tool.py`、
     `tests/integration/presentation/test_skill_structure.py` 中的技能路径。
   - `README.md`: 技能列表、安装节(循环改为 `for skill in skills/*`)、Validate 节路径。
   - `portfolio/SKILL_STATUS.md` 中的路径引述。
4. 全仓库 grep 每个旧技能根路径(如 `"presentation/`、`ROOT / "presentation"`、
   `../presentation`),按 R6 排除与豁免规则处理: pinned condition 的 `skills[].path`
   /ablation 目标 `path` 允许保留,其余清零。注意区分同名子路径
   (`evals/presentation/`、`tests/integration/presentation/` 不是技能路径,不改)。

验证门: Phase 0 的全部命令重跑,结果与基线一致(check-ID 集合相同);4 个 suite 的
`evalctl validate` 全部通过——其中 `presentation-image-assets-smoke` 引用了
pinned+ablation 的 condition(已核实其 suite 文件第 13 行),validate 会实际执行
`replacement` 的当前工作树存在性校验(`eval_lib.py:417`),这是 R1 处理正确性的
直接验证;`git log --follow skills/presentation/SKILL.md` 显示完整历史。

### Phase 3 — 完成 evals 迁移,消灭双轨

逐目录分流,方向: 确定性检查与 fixture → `tests/`;可淘汰的包装 → 删除。

1. `evals/presentation/` — 纯包装,直接删除。
2. `evals/data-analysis/` — `real-data/`、`sample-data/`、`cases.yaml`、`README.md`
   `git mv` 至 `tests/fixtures/data-analysis/`;更新
   `tests/integration/data-analysis/run_checks.py` 及其 docstring 中的引用。
   删除残余的 `run_checks.py`(先确认它已是包装或其逻辑已被 tests 覆盖;若有独立断言,
   先并入 `tests/integration/data-analysis/` 再删)。
3. `evals/feed-processing/` — `run_checks.py` + `fixtures/` `git mv` 至
   `tests/integration/feed-processing/` 与 `tests/fixtures/feed-processing/`,修内部路径。
4. `evals/code-review/`、`evals/video-studio/`、`evals/shape-product-spec/` — 同上分流:
   `run_checks.py` → `tests/integration/<skill>/`;`fixtures/`、`media/`、`source/`、
   `evals.json` → `tests/fixtures/<skill>/`。`evals.json` 若只被本目录 run_checks 消费,
   随 fixture 走;若含 trigger 评估语义,登记入"后续任务"不删除。
5. `evals/artifact-skills/` + `evals/run_artifact_skill_checks.py` —
   套件定义与 source fixture `git mv` 至 `tests/fixtures/artifact-skills/`,
   runner `git mv` 至 `tests/integration/artifact-skills/run_checks.py`,修内部 `ROOT` 相对路径。
   trigger 案例向 `evals/cases/` 的语义转换登记为后续任务(见"非目标")。
6. 更新 `evals/run_all_skill_checks.py` 中指向被移动脚本的调用路径。
7. 更新文档: `README.md`(删除"compatibility wrappers during migration"等段落)、
   `evals/README.md`(删除 legacy 段落)、`evals/VALIDATION_MATRIX.md`、
   `portfolio/SKILL_STATUS.md` 的 Cross-Skill Guidance 节。
8. 验收结构: `ls evals/` 只剩 `cases conditions suites runners judges schemas`
   + `README.md`、`requirements.txt`、`run_all_skill_checks.py`、`VALIDATION_MATRIX.md`、`__init__.py`。

验证门: Phase 0 全部命令(路径按新位置替换)满足 R9 基线对照规则(默认全绿);
按 R6 对 `evals/artifact-skills`、`evals/data-analysis` 等旧路径 grep 清零。

### Phase 4 — 统一验证入口

1. 新增 `tests/integration/skills/test_skill_packages.py`(unittest 风格): 把外部
   `quick_validate.py` 承担的校验**内置进仓库**——对 `skills/*` 与 `archive/research`
   逐个断言: SKILL.md 存在且 YAML frontmatter 可解析、frontmatter 只含允许字段、
   技能名格式合法且与目录名一致、描述满足长度/内容约束。实现前先读一遍
   `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py` 的实际规则,
   逐条对应,不得凭记忆缩水。
2. 新增 `tests/run_all.py` 作为**唯一确定性总入口**,基于现
   `evals/run_all_skill_checks.py` 改写(git mv 以保历史)。**check-ID 清单必须完整
   保留基线集合**,逐项列出:
   - `quick_validate:<skill>` ×10 → 由内置 `test_skill_packages` 以**逐技能强制检查**
     `skill-packages:<skill>` 等价替代,改名映射表含
     `quick_validate:<skill>` → `skill-packages:<skill>` 十条,状态参与 R9 比较;
     外部 quick_validate 作为可选交叉核对使用**全新 ID**
     `external-quick-validate:<skill>`(存在则跑、缺失标记 `skipped`),与基线 ID
     不复用、无基线对应项,因而不参与 R9 状态比较;
   - `eval-platform-unit`(`python -m unittest discover -s tests/unit -p 'test_*.py'`,
     **保持 unittest,不引入 pytest**);
   - suite contract: 不再硬编码 3 个,改为 glob `evals/suites/*.json` 逐个
     `evalctl validate`,check-ID 为 `suite-contract:<suite-file>`(≥ 基线的
     `eval-suite-contract`、`eval-presentation-image-contract`、
     `eval-presentation-image-assets-contract` 三项,并把此前不在基线内的
     `presentation-current-image-assets-ab` 也纳入);
   - 7 个技能确定性检查: `code-review`、`artifact-skills`、`presentation`、
     `data-analysis`、`feed-processing`、`shape-product-spec`、`video-studio`
     (调用路径按 Phase 3 之后的新位置);
   - `python-compile`(py_compile,文件清单按新路径更新,含全部技能 `scripts/*.py`
     与 evals/tests 平台代码);
   - `node-check:<script>` 全集(Node 按 R8 为必需依赖,缺失即整体失败,不设 SKIP)。
3. 覆盖验收改为**机器比对**: 从基线 `reports/restructure-baseline-20260730/run_all.json`
   提取 check-ID 集合 A,从新入口输出提取集合 B,要求 A ⊆ B(允许的 ID 改名映射——
   如 `eval-suite-contract` → `suite-contract:representative-ab.json`、
   `quick_validate:<skill>` → `skill-packages:<skill>`——在 `tests/run_all.py` 顶部
   以注释表列出,比对脚本按映射折算)。**状态语义**: 新入口每个检查输出
   `status: passed|failed|skipped`,不再用 `ok` 布尔兼任 SKIP;基线旧格式按
   `ok=true → passed`、`ok=false → failed` 折算。状态比对规则(R9): 基线 passed
   的检查(经映射)必须仍 passed;`skipped` 仅允许出现在**无基线对应项**的检查上
   (当前即 `external-quick-validate:<skill>`);仅 allowlist 内的检查允许维持
   failed,不得出现新 failed。比对命令写进本 Phase commit 信息。
4. 原 `evals/run_all_skill_checks.py` 经步骤 2 的 `git mv` 后旧位置自然消失,
   **不留过渡包装**(本仓库无外部消费者,过渡包装正是 P1 问题的起源);
   更新所有文档中对旧路径的引用。
5. README Validate 节收敛为两条命令:
   ```sh
   .venv/bin/python tests/run_all.py        # 确定性检查(内含全部 suite contract)
   .venv/bin/python evals/runners/evalctl.py validate --suite evals/suites/representative-ab.json  # 按需单独校验某个 suite
   ```

验证门: `tests/run_all.py` 在干净 checkout(无 `~/.codex`、无 pytest,但按 R8 必须
有 Node)下可运行,允许 `status=skipped` 的**仅限** `external-quick-validate:<skill>`;
步骤 3 的 ID + 状态比对通过;`skill-packages:<skill>` 对 10 个技能包全部 passed。

### Phase 5 — 技能包卫生与结构守门

1. 删除 `skills/data-analysis/analysis_runs/`(确认为空)、包内 `.DS_Store`;
   评估包内 `.gitignore` 是否仍必要(其忽略项若已被根 `.gitignore` 覆盖则删)。
2. 把目录结构守门并入 Phase 4 新增的
   `tests/integration/skills/test_skill_packages.py`(而非另立文件): 遍历 `skills/*`,
   允许的顶层条目为 `SKILL.md`、`agents/`、`references/`、`scripts/`、`assets/` +
   显式白名单(`requirements.txt`、`package.json`、`package-lock.json`)。白名单硬编码
   在测试里,新增例外必须改测试(即留下 review 痕迹)。原
   `tests/integration/presentation/test_skill_structure.py` 的 presentation 专属
   结构断言保留在原文件,与通用守门不重复。
3. (可选,需所有者确认)`portfolio/SKILL_STATUS.md` → 根目录 `PORTFOLIO.md`,
   删除只有一个文件的 `portfolio/` 目录;同步 README 引用。
4. 本文档 `RESTRUCTURE_PLAN.md` 移入 `reports/restructure-20260730.md` 并附各 Phase
   验证门的实际输出摘要,或直接删除(所有者决定)。

验证门: `tests/run_all.py` 满足 R9 基线对照规则(默认全绿);结构守门对 9 个在役
技能全部通过。

## 六、总验收标准

1. `ls skills/` 输出恰好 9 个在役技能,根目录条目数 ≤ 12(不含隐藏文件);
2. `evals/` 下不存在任何按技能名组织的遗留目录;
3. 确定性检查一条命令(`tests/run_all.py`),在无 `~/.codex`、无 pytest 的机器可运行;
   Node 按 R8 为硬性前置依赖;允许 `status=skipped` 的**仅限**
   `external-quick-validate:<skill>`,frontmatter 等校验由内置强制检查
   `skill-packages:<skill>` 承担;
4. check-ID 覆盖为机器比对: 基线集合 ⊆ 新入口集合(按声明的改名映射折算),且
   `status` 满足 R9(基线 `passed` 的检查仍 `passed`,无新增 `failed`,allowlist 外无残留 `failed`);
5. 3 个 revision 固定 condition 的 `skills[].path` 与 ablation 目标 `path` 未被改动,
   唯一带 ablation 的 pinned condition 其 `replacement` 已更新为 `skills/` 前缀,
   全部 suite 的 `evalctl validate` 通过;
6. `git log --follow` 能追溯任一被移动文件的完整历史;
7. `reports/`(基线目录除外)、`results/` 内容未被改写;
8. 每个 Phase 一个 commit,commit 信息注明 Phase 编号与验证门结果。

## 七、登记的后续任务(不在本计划内)

- `evals/artifact-skills/` trigger 评估语义 → `evals/cases/` 用户任务用例的转换;
- `tests/integration/` run_checks 脚本向 pytest 的统一;
- `evals/` 内平台代码(runners/judges/schemas)与实验数据(cases/conditions/suites)的进一步分层。
