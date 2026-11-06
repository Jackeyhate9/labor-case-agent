# 许可证与归属记录

核验日期：2026-07-22

范围：本项目 Phase 0 指定的六个公开 GitHub 参考仓库。核验以各仓库默认分支根 LICENSE 实文为主，README 徽章/描述只作辅助。本文是工程合规记录，不是正式法律意见。

## 当前归属结论

- 本项目当前**没有复制、修改、链接或打包**六个参考仓库的源码、提示词、模板、模型、数据集、图片、音频或 3D 资产。
- 当前仅记录公开事实，并在抽象层面参考架构、交互和工作流；因此本项目现阶段无需把六仓版权声明并入发布物。
- 若以后发生实质复用，必须在合并前更新本文件，记录：上游仓库、精确 commit、文件路径、版权人、SPDX 标识、修改说明、NOTICE/许可证落点、依赖传播范围和批准人。

## 许可证矩阵

| 仓库 | 根 LICENSE 核验结果 | README/GitHub 表述 | 直接复用状态 | 主要义务/阻断项 |
|---|---|---|---|---|
| [DerpZhenjun/Partlawyer-LAA](https://github.com/DerpZhenjun/Partlawyer-LAA) | [MIT](https://github.com/DerpZhenjun/Partlawyer-LAA/blob/main/LICENSE) | README 与 GitHub 均称 MIT | 暂不复用；未来可逐文件评估 | 分发副本/实质部分须保留版权和许可文本；内嵌 ChatVRM、GPT-SoVITS、模型、声音、VRM/图片和子许可证需分别核验，根 MIT 不会覆盖第三方资产 |
| [jerry046918/labor_rights_skills](https://github.com/jerry046918/labor_rights_skills) | [Anti-996 License v1.0](https://github.com/jerry046918/labor_rights_skills/blob/master/LICENSE) | 一致；GitHub 识别为 Other | **不复制** | 非标准许可，附加劳动法、强迫劳动和 ILO 条件；兼容性、可执行性和下游合规证明成本不确定 |
| [worker-aid-ai/worker-aid-agent](https://github.com/worker-aid-ai/worker-aid-agent) | [AGPL-3.0-or-later](https://github.com/worker-aid-ai/worker-aid-agent/blob/main/LICENSE) | 一致 | **不复制** | 修改/衍生与网络交互场景可能触发对应源码提供义务；与本项目拟采用许可的兼容性需专项法律审查 |
| [CaseMark/evidence-triage-OSS](https://github.com/CaseMark/evidence-triage-OSS) | [Apache-2.0](https://github.com/CaseMark/evidence-triage-OSS/blob/main/LICENSE) | 一致；仓库是 `CaseMark/casedotdev-starter-app` 的 fork | 暂不复用；未来可逐文件评估 | 随分发提供许可证、保留版权/专利/商标/归属通知、修改文件显著标注；若上游存在 NOTICE 需传递相关内容 |
| [Azhu9701/Mock-Court](https://github.com/Azhu9701/Mock-Court) | [自定义“AGPLv3 + Section 7 额外用途限制”](https://github.com/Azhu9701/Mock-Court/blob/main/LICENSE) | README 徽章称 MIT；GitHub 识别 Other | **阻断：不得复制** | 根 LICENSE 与 README 直接冲突；包含非剥削集体用途、禁军工、禁监控资本主义、禁规模数据抽取、运行横幅及额外网络披露等限制；需上游书面澄清并由律师判断附加条款有效性/兼容性 |
| [Clukay-Fun/feishu-opencode-bridge](https://github.com/Clukay-Fun/feishu-opencode-bridge) | [Apache-2.0](https://github.com/Clukay-Fun/feishu-opencode-bridge/blob/main/LICENSE) | README 末尾称 MIT；GitHub 识别 Apache-2.0 | 暂不复用；澄清前从严 | 法律文本与 README 冲突，以根 LICENSE 为工程基线；复用前要求上游澄清，并履行 Apache-2.0 通知/修改标注义务 |

## 许可兼容决策

### 可在审批后考虑的来源

1. `Partlawyer-LAA` 的原创、可独立识别且确由 MIT 覆盖的代码：只有完成逐文件来源和嵌套依赖审查后才可考虑。文书模板、音频、模型、VRM 与图片不自动视为 MIT 可复用资产。
2. `evidence-triage-OSS` 的 Apache-2.0 原创文件：可在保留许可证/归属、标注修改并检查 NOTICE 后考虑；Case.dev 商标、服务条款和 API 不因源码 Apache-2.0 而获得授权。
3. `feishu-opencode-bridge`：根许可证显示 Apache-2.0，但 README 写 MIT。即使两者都属宽松许可，义务不同；上游澄清前不复制。

### 仅作理念/流程参考的来源

- `labor_rights_skills`：Anti-996 非标准条件导致兼容性不确定。
- `worker-aid-agent`：AGPL-3.0-or-later 的网络源码义务可能传播到组合/衍生作品。
- `Mock-Court`：自定义许可与 README 冲突，且额外用途限制高度非标准。

“理念/流程参考”仅指独立观察到的通用思想，例如人工复核、证据缺口检查、对抗式审查、Provider 抽象、时间线视图。不得近似改写其独创提示词、模板、文案、测试夹具或代码结构来规避许可证。

## 第三方材料特别风险

### 法律文本与案例

法律法规、官方案例、司法解释及其整理数据库可能分别涉及公共信息可用性、编辑汇编成果、数据库服务条款和访问限制。不得因为参考仓库收录了全文或摘要，就假定可以原样复制。应从权威公开源重新取得、记录公布机关/发布日期/版本/URL/校验值，并独立制作结构化索引。

### 文书模板

通用表格字段和法定格式可独立实现；具体模板的版式、措辞、示例事实和注释可能具有独创性或带有机构权利。应依据公开官方样式自行重建，禁止复制参考仓库 DOC/DOCX/Markdown 模板。

### 模型、音频、肖像和 3D 资产

代码许可证不等于模型权重、训练数据、人物声音、肖像、角色或 VRM 资产许可。`Partlawyer-LAA` 的语音克隆/数字人链路需要额外核验模型卡、数据集条款、声音与肖像授权；本项目当前不引入这些资产。

### SaaS 与商标

Apache/MIT 源码许可不授予 Case.dev、Feishu、OpenCode 等商标权，也不替代云服务条款、数据处理协议、跨境传输评估或 API 配额/计费条款。

## 未来引入检查表

每次引入第三方内容前必须完成：

1. 固定上游 URL、commit SHA 和文件列表。
2. 确认每个文件的作者/版权和 SPDX；检查仓库根、子目录 LICENSE、NOTICE、资产说明、模型卡和数据来源。
3. 判断复制、修改、链接、网络服务、模板/提示词近似改写分别会触发什么义务。
4. 记录修改内容，保留版权/许可证/NOTICE；不得删除上游标识。
5. 检查与本项目许可证、依赖许可证及发布方式的兼容性。
6. 对 AGPL、Anti-996、自定义条款、许可冲突或来源不明内容，取得负责人和律师书面批准；未批准即不合并。
7. 对云服务另行完成隐私、数据处理、留存、删除、地域和安全评估。
8. 在发布包生成第三方通知清单，并用自动化扫描校验实际依赖与记录一致。

## 归属台账

| 日期 | 来源 | commit / 文件 | 使用方式 | 复制代码/资产 | 决策 |
|---|---|---|---|---|---|
| 2026-07-22 | 六个指定参考仓库 | 见 `reference-repository-audit.md` 的来源链接 | 只读研究、抽象流程参考 | 否 | 不产生第三方代码归属；保留本审计记录 |

后续如有任何实质引入，应追加新行，不得覆盖历史记录。
