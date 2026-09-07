# 数据集创建流程审计

审计范围：Platform Product API、WebUI 数据集页面、DOCX Authoring、手工
TXT/Markdown 创建、启动脚本和用户文档。审计不修改任何已冻结 Dataset
Release、Bundle、Gold 或运行记录。

## 当前正式流程

WebUI 的“创建/上传数据集”只保留三种入口：

1. **导入已制作的数据集（ZIP）**：导入已经封存的 Bundle；不在页面中
   修改其内容。
2. **粘贴 TXT / Markdown**：粘贴原文，选中原文位置，填写一题及标准答案，
   直接创建封存数据集。
3. **从 DOCX 创建数据集**：上传私有 DOCX，完成 Canonical 解析，按题型
   分组查看可用原文位置，选择生成数量和题型，审核题目、答案和原文，再
   导出/注册。

DOCX 候选题的原文预览按需异步加载并缓存。每个候选题的答案编辑状态按
`candidate_id` 独立保存，不会写入其他候选题。解析后的题目来源按能力类别
折叠，而不是把所有位置平铺展示。

## 已清理的重复入口和展示

- 移除了浏览器中的“注册本地路径”入口及对应 Product API。浏览器不再尝试
  解析 Platform 主机路径；受信任的 CLI/CI `register-dataset` 仍保留。
- 创建弹窗从四种方式收束为 ZIP、TXT/Markdown、DOCX 三种方式。
- 正式 Dataset Release 现在计入 Overview 的数据集数量；Bundle 3.0 仅是
  runtime/private 投影，不再被当作用户数据集或配置完成依据。
- 数据集列表只显示可继续操作的 Authoring 工作区、已导入 Bundle 和正式
  Release。已注册工作区由对应正式 Release 代表；归档工作区收在独立的
  “已归档”折叠区，可在二次确认后永久删除本地工作区。
- 永久删除在服务端同样受限：只有 `archived` Authoring 工作区可删除；
  `registered` 工作区不可归档，正式 Release、Bundle 和冻结数据始终不受此
  操作影响。
- 移除了重复的页面标题、目录计数、不可修改状态胶囊、技术溯源/MSES 说明
  和不再可达的本机路径文案。正式数据集详情保留用户需要的题目、标准答案、
  原文依据及“查看原文”。
- 手工 TXT/Markdown 界面不再暴露“保存草稿”“单独校验”步骤或可编辑的
  文件/文档 ID。改动原文时会主动清除旧选区，避免证据坐标落到已变化文本。
- 移除了没有 UI 入口的 Product 草稿列出、更新和单独校验 API，以及对应
  `DatasetDraftStore.list()` 死代码。保留创建后封存所需的内部暂存记录。
- 上传文件名使用 ASCII 安全的 UTF-8 传输形式，避免中文 DOCX/ZIP 文件名
  导致浏览器 `fetch` 因非 ISO-8859-1 Header 失败。

## 保留的边界

- `POST /api/v1/datasets` 和 `rag-eval register-dataset` 仍是高级 CLI/CI
  入口，不属于普通浏览器流程。
- Canonical、Authoring Ledger、Formal Release、Gold、Bundle 3.0 和运行历史
  仍由 Platform 管理；WebUI 只读取适合用户查看的投影。
- `scripts/start-local.sh` 仍只启动一个 Platform/WebUI 组合；它不启动常驻
  LightRAG Worker。历史运行通过只读兼容层显示，数据不会被复制或改写。
- Platform 仓库没有独立的 `docker-compose` 启动定义；Docker 是单个系统连接
  的执行提供者，不能与同一系统的本地提供者并存为两个记录。

## 验证

在本次清理后执行：

```text
rag-eval-platform/.venv/bin/python -m pytest -q
156 passed, 3 skipped

rag-eval-webui: npm run test -- --run
2 test files, 6 passed

rag-eval-webui: npm run build
TypeScript + Vite production build passed
```

还执行了两端的 `git diff --check`，并验证已移除的 Product 本机路径路由
返回 404；手工文本路径只能“创建 → 封存”，没有孤立的列表、更新或单独
校验操作。归档删除的 API 还验证了两条不可绕过的路径：未归档工作区返回
409，先归档后删除返回 204。

## 结论

普通用户的创建流程现在有清晰且互斥的三条路径，DOCX 是完整的
解析—生成—审核—注册主线。高级 CLI/CI 能力和内部可追溯记录仍被保留，
但不再干扰前端的数据集创建页面。
