# 设立文件：从 PDF 到股权节点

记录日期：2026-10-07

本文只说明「上传 PDF，再在『从设立文件生成结构』里变成股权节点」这一段。上传、存文件、挂到清单上的原有流程没有改。规则引擎和 Ask AI 也没有改。

演示实现是为了让 `demo-data/Shareholder_Register_CedarPine.pdf` 能走通确认弹窗。它要求文件里预先写好 `|` 分隔的字段。真实股东名册、章程、决议不会带这种标记，所以这段不能留作正式解析。

## 修改前

上传成功之后，文件字节在本地存储里，`case_documents` 有一行。抽取使用 `NoopExtractor`：不读文件内容，立刻返回空页、空字段，`model` 为 `None`。状态写成 `EXTRACTED`，`extraction_pages` 和 `extraction_fields` 都是 0 行。`relation_status` 保持表默认值 `NOT_APPLICABLE`。

「解析设立文件」是 `POST /api/v1/cases/{caseId}/ai/extract-formation`。它要求所选文件同时满足：

- `extraction = EXTRACTED`
- `relation_status = READY`

原来的上传只满足第一条。接口返回 422，`Document reading has not finished.`，不产生候选人或公司。

关系任务 `services/api/src/fcc_api/jobs/relations.py` 只处理 `relation_status = PENDING` 的文件。正常上传不会写成 `PENDING`。即使写成 `PENDING`，当前 noop 适配器也把该行标成 `FAILED`，不把页正文送给模型。

因此，修改前 PDF 里的文字不会进入 `parties`。图上的节点来自手工添加、Ask AI 确认后的草稿，或种子数据。

设计上的目标写在 `docs/backend/12-production-launch.md` 第 8.2 节，当时没有接上：

1. OCR 把每页正文写入 `extraction_pages.text`。
2. 关系抽取读这些正文，写入 `document_entities` 和 `document_relations`，成功后把 `relation_status` 写成 `READY`。
3. 员工打开解析弹窗时，服务端只读取已经写好的实体和关系，对照当前股权树生成建议。员工确认后才写入 `parties`。

## 修改后

改了三处，外加一份演示 PDF。

| 位置 | 作用 |
| --- | --- |
| `demo-data/Shareholder_Register_CedarPine.pdf` | 人眼可见的是 Cedar & Pine 股东页。文件注释里另有一段机器可读字段 |
| `services/api/src/fcc_api/demo_register.py` | 新文件。只认标记块 |
| `services/api/src/fcc_api/adapters/extraction.py` | `NoopExtractor` 先读字节。没有标记时仍返回原来的空结果 |
| `services/api/src/fcc_api/services/documents.py` 的 `_store_demo_register` | 抽取存页之后，把标记块写成实体和关系 |

标记块以 `FCC-DEMO-REGISTER-V1` 开始，以 `END-FCC-DEMO-REGISTER` 结束。中间每行去掉前导 `%` 后，用 `|` 分成恰好 8 段：

`姓名|PERSON 或 ENTITY|实体类型|职务|持股|国家|置信度|引用句`

职务决定关系，全部指向 `CASE_ROOT`：

- 持股大于 0，或职务含 shareholder：`OWNS`
- director：`DIRECTOR_OF` 和 `SIGNS`
- trustee：`TRUSTEE_OF` 和 `SIGNS`
- secretary、officer 或 sign：`OFFICER_OF` 和 `SIGNS`

写库时：

- 每个解析出的人写入 `document_entities`，引用格式为 `{文件名} · p.1 · {引用句}`
- 每条关系写入 `document_relations`
- 该文件 `relation_status` 改为 `READY`
- 抽取运行的 `relation_prompt_version` 为 `demo-register.v1`，`relation_model` 为 `doc-extract-demo`

没有这段标记的 PDF 或图片仍走原来的空抽取，`relation_status` 不变，解析弹窗照旧拒绝。

置信度达到 0.75 的行默认勾选。Mira Shah 是 0.72，默认不勾选。员工确认后，所选行挂到弹窗里选定的一个父节点下。这一步沿用原有的 `applyAiParties`，后端不会在抽取完成时自动改股权树。

## 之后要整改

每个待解析文件都内嵌 `|` 分隔行，只能服务这一份演示 PDF。客户交来的设立文件是普通版式，打开后看不到、也不该有 `FCC-DEMO-REGISTER-V1`。继续沿用这段逻辑，换一份真实名册就不会产生节点。

整改时拆掉演示捷径，接上第 8.2 节已经写明的顺序。上传、签名地址、隔离区、完成登记、审计保持不动。

1. 抽取适配器读取普通 PDF 或图片，把每页可见正文写入 `extraction_pages.text`。正文来自版面文字或 OCR，不要求文件作者预先插入分隔符。
2. 抽取成功后把 `relation_status` 写成 `PENDING`。关系任务读取页正文，按 `relations.v1` 产出实体和关系，校验后再写入 `document_entities` 与 `document_relations`，然后写成 `READY`。失败写成 `FAILED`，页正文保留。身份类文件（`identity`、`pep`）维持 `NOT_APPLICABLE`，与 `jobs/relations.py` 里现有的去向一致。
3. `extract-formation` 继续只读 `READY` 的结果，并对照当前 `parties`。同名节点带 `matchedPartyId`。员工确认前不写股权树。

可以删除或停用的演示代码：

- `services/api/src/fcc_api/demo_register.py`
- `NoopExtractor.extract` 里对 `page_text_from_bytes` 的调用
- `documents.py` 里的 `_store_demo_register`
- PDF 注释中的 `FCC-DEMO-REGISTER-V1` 块。可见的股东页可以留下，当作一份没有隐藏字段的样例

`demo-register.v1` 不是 `relations.v1`。正式结果要能指出上层公司，不能把每条关系都写成 `CASE_ROOT`。引用句必须是对应页正文里的连续原文。模型不能写入 PEP、制裁或 FATCA 结论。这些约束已在 `docs/backend/12-production-launch.md` 第 8.3 节和第 8.6 节。
