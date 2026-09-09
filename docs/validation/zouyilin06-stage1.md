# Zouyilin06 阶段一执行记录

日期：2026-09-09

本记录已由 v2 数据管线工作更新。前 20 道菜现在有源文件哈希、逐行引文、需求类型、
选择组、工具和待裁决问题的 AI 辅助草稿；`sample-20-zouyilin06-draft.json` 是便于查看的
摘录，权威草稿在 `src/cookkg/resources/annotations_v2.json`。

第二名标注人员尚未独立完成同一 20 道，组长也尚未裁决分歧或冻结规范。
因此阶段一的技术准备已经完成，课程要求的双人独立标注与人工裁决仍未完成。

运行 `cookkg data-v2 build` 后，第二名标注人员应先打开
`data/processed/v2/pilot-20-blind.html`，并填写
`pilot-20-independent.blank.json`。这个原文包不显示第一份结论。
两份完整标注可用 `cookkg data-v2 compare` 生成分歧表，再交给组长裁决。

当前验证：前 20 个 ID 唯一，全部来源哈希及逐字引文匹配固定 HowToCook 提交；
AI 标注不能把 `review_state` 自行设为 `confirmed`；人工批准同时绑定来源哈希与标注哈希。
完整数据与图谱结果见 `zouyilin06-data-v2.md`。
