# Rich Content Canonicalization Report

## 结论

真实 DOCX 已由正式 Canonical Contract **1.2** 重新 Canonical 化。平台现在能以可定位、可追溯、可验证的方式保存 DrawingML 图、图标题、正文图引用、媒体资源与 OMML 公式；但它**不**声称理解图片视觉内容，也不把 VML、OLE 或未闭环的图引用放宽为 Gold 证据。

这是一项 Data Layer 变更：未运行 LightRAG/RAG、未生成 held-out 数据、未改动 Adapter、scorer、metric 或 Bundle 2.0。

## 输入与可复现性

| 项目 | 值 |
| --- | --- |
| 源文件 | `XXX网站系统（S2A2G2）_V2.0.docx` |
| source digest | `7d50899d15356000782b292bb84e135e4f1ebe20672ba9799939a6a1e2861755` |
| parser | `rag-eval-authoring-ooxml/1` |
| canonicalizer | `rag-eval-authoring-canonicalizer/4` |
| configuration digest | `c080c4c14a1b938a65a5a34bbedd09c8e0b62368020ae97079e03a5eb160190b` |
| Canonical schema | `1.2` |
| Canonical record digest | `27d785cf946cd6ef02a39cd687709dfa4bda0ef569eb8a0cb5ac20d9a2e24d5c` |
| Canonical document/manifest digest | `f1bfe418f5b28ee2541dbe7e31bb0a5d098b106dfe5a8adcf9d03358bb305ed6` |
| current DocumentRevision | `document-revision-4867d37a2e17407e8ec774794e853b3c-000004` |

对同一 source、parser、canonicalizer 与 config 连续 Canonical 化两次，manifest digest 均为 `f1bfe…5ed6`。DocumentRevision 是 append-only；旧的 1.0/1.1 解析和旧 Frozen Release 的 Canonical snapshots 未被改写。Release reader 也已显式兼容 Canonical 1.0、1.1、1.2。

源侧审计输出保存于实际 Authoring workspace 的 `diagnostics/rich-content-source-audit.v1.json`；当前 Canonical 的对象、关系与 manifest 位于相同 workspace 的 `canonical/` 下。

## 真实 DOCX 源侧审计

审计直接读取 `word/document.xml`、关系部件和 package media，而非以 synthetic fixture 推断。

| 源侧对象 | 数量 | 审计结论 |
| --- | ---: | --- |
| DrawingML inline drawing | 2 | 均有图片 relationship、尺寸、相邻图标题和正文显式引用 |
| DrawingML anchor | 0 | 无 anchor 实例；实现与测试仍覆盖 anchor fail-closed 路径 |
| package media | 5 | 2 个 PNG 属于已闭环 DrawingML；3 个 WMF 属于旧 VML/OLE 语境 |
| 图标题候选 | 60 | 大多数为表标题；图 1-1、图 2-1、图 3-1 为图标题候选 |
| 正文图号提及 | 6 | 其中图 1-1、图 3-1 可唯一解析；图 2-1 无实际 DrawingML 资源 |
| OMML logical equations | 17 | 3 个 block，14 个 inline/符号片段 |
| VML shape | 3 | legacy 对象，保留 partial |
| OLE object | 3 | legacy Equation/OLE，保留 unsupported |

两个可闭环的图为：

- `figure:00001`：图 1-1「等级保护测评工作流程图」，body ordinal 329，`rId21 → media/image1.png`，紧随标题在 330，正文在 323 显式引用。
- `figure:00002`：图 3-1「漏洞扫描工具接入测试示意图」，body ordinal 616，`rId22 → media/image2.png`，紧随标题在 617，正文在 611 显式引用。

图 2-1 有正文引用和标题，但 DOCX package 中没有与其对应的 DrawingML/媒体资源；该引用保持 `partial`，不猜测也不补造图片。3 个 VML 和 3 个 OLE 均按原始对象保留其 source locator 与 provenance，不转换成图片语义或公式语义。

## Contract 1.2 与关系恢复

Canonical 1.2 增加了 `media_resource` 对象，以及 `figure_has_resource`、`paragraph_references_figure`、`equation_in_paragraph`、`section_contains_figure`、`section_contains_equation` typed relation。图仍使用既有 `caption_of` / `reference_to` 关系，且关联必须有 source span 与 locator。

对每个 DrawingML 图保存：relationship ID、资源 part、资源 SHA-256、byte count、图尺寸、`wp:docPr`、anchor kind、所属 paragraph/section、caption object、正文 reference object 与关联状态。公式保存 `raw_omml`、raw OMML digest、递归 OMML tree、presentation text、block/inline placement、paragraph/section、source span 和解析状态。

本次实际 Canonical 结果：

| Canonical 对象/关系 | 结果 |
| --- | --- |
| figure | 5：2 complete、3 partial(VML) |
| equation | 17 complete（17 个均保留 raw OMML/tree） |
| media_resource | 2（两个 resource-backed DrawingML PNG） |
| embedded_object | 3 unsupported（OLE） |
| figure-caption reliable association | 2 |
| resolved textual figure reference | 2 |
| unresolved textual figure reference | 1（图 2-1） |
| `figure_has_resource` | 2 |
| `paragraph_references_figure` | 2 |
| `equation_in_paragraph` / `section_contains_equation` | 17 / 17 |

这解决了此前 1.1 仅把 figure/equation 以 partial surface record 保存、缺少媒体资源、图标题/正文引用闭环和 raw OMML 结构的问题。它并未把视觉识别结果伪装成解析结果。

## Gold eligibility（fail-closed）

图的 `semantic_status` 只说明文字结构已被验证；`visual_semantic_status` 为 `unverified`。因此即使图可用，Gold scope 也严格为 `caption_and_text_only`：问题只能依赖正文、图号、caption 和明确文本关系，不能询问 PNG 中的流程节点、箭头、拓扑或其它视觉内容。

允许进入未来 Gold 候选的 rich evidence：

| 对象 | 准入范围 |
| --- | --- |
| `doc-…:figure:00001` | 图 1-1 的 caption + 正文文本引用；禁止视觉内容答案 |
| `doc-…:figure:00002` | 图 3-1 的 caption + 正文文本引用；禁止视觉内容答案 |
| `doc-…:equation:00002` | 上下文明确、raw OMML 完整的 block 公式 |
| `doc-…:equation:00003` | 上下文明确、raw OMML 完整的 block 公式 |
| `doc-…:equation:00004` | 上下文明确、raw OMML 完整的 block 公式 |

禁止作为正式 Gold evidence：3 个 VML、3 个 OLE、图 2-1 unresolved reference、任何图片视觉推断、没有可靠 caption/reference 的图、14 个 inline OMML/符号片段、以及所有 partial/unsupported/missing rich object。每一条 Gold 准入在 Contract validator 中由必需属性、relation 可靠性、semantic/visual status 和 source provenance 联合检查；伪造 Gold-eligible figure 会被 fail-closed 拒绝。

没有使用 OCR 或 VLM。若未来接入，它们只能生成 `unverified` proposal，并需独立 review 才可能形成新的 Canonical revision；不得覆盖 raw OOXML 或自动放行 Gold。

## DRY-08 复审与发布影响

`benchmark-v0-dry-run-48` 的 4 个 DRY-08 slot 都要求“figure-caption relation plus equation-reference relation”的**独立多证据**问题。重新审计后，基础图/公式能力已存在，但本文件没有一个自然的业务主张把任一合格图标题/正文引用与综合得分公式语义连接起来。把它们拼成同题会违反 evidence-first 和自然性要求。

因此 4 个 slot 保持 `blocked`，并通过 append-only reassessment revision 把原因从过时的 `unsupported_modality` 更新为 `other_documented_reason`：没有自然的 figure-to-equation 语义证据链。没有删除或改写旧 assignment，也没有错误计入 coverage。

本阶段新增 Case/Gold 为 **0 / 0**，因为没有自然的 slot actualization；所以没有创建 successor Frozen Dataset Release。既有两个 Frozen Release 文件的 SHA-256 仍分别为：

- `dataset-release-4758bfcc6b91c492bac9c9f2`: `04064248a82b6351ad4690fdd5d6273f370ec3c52b2be79f985e61631227bca8`
- `dataset-release-bcc904a2f011e567e5fb5548`: `49563d06cdbd428c0ff6c1dc781399d19632a98796713036ab4d6119c1720669`

当前 Portfolio 仍为 33 frozen、15 blocked、其余状态为 0；Coverage Report digest 为 `ada7f06bfced1afd25520894b7371d354d7e392982b6e01863aee53658bfa9c3`。既有 frozen 20-case Bundle、Gold 和历史运行引用未触碰。

## 验证

新增并通过的测试覆盖了 DrawingML inline/anchor、media resource lineage、caption/reference 关系、raw OMML/tree 与 block/inline placement、ambiguous caption fail-closed、rich Gold eligibility fail-closed、blocked reassessment append-only、Release 1.1 reader compatibility，以及 Canonical deterministic rebuild。相关测试与既有 Authoring/Contract/Portfolio/Formal Release 测试共 **34 passed**（1 个第三方 deprecation warning）。

## 最终判断

Data Layer 现在能可靠处理本源 DOCX 的**文本与结构可验证**图/图标题/正文引用/公式信息，并为这两张图和三个 block 公式提供受限的 Gold 准入路径。它尚不具备通用图片视觉理解，也不会把 VML/OLE 或图 2-1 的缺失资源解释为可用证据。

所以：可继续为具有自然文本—caption—公式链的 future Portfolio slot 做 Authoring；对当前 DRY-08，正确结果仍是 blocked。不存在本阶段的 Data Layer blocker，但存在源文档固有的内容限制，不能以 Canonicalizer “修复”来伪造该类 Benchmark。
