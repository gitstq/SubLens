# 贡献指南 / Contributing

感谢你考虑为 SubLens 做贡献！本项目坚持 **零运行时依赖、纯标准库、全确定性** 三条底线。

## 开发环境

```bash
git clone https://github.com/gitstq/SubLens.git
cd SubLens
python3 -m unittest discover -s tests -v
```

无需安装任何第三方依赖（测试可用标准库 `unittest` 直接运行）。

## 提交规范

采用 Angular Conventional Commits：

- `feat: 新增 XXX 规则` —— 新功能
- `fix: 修复 VTT 标识符解析` —— 缺陷修复
- `docs: 补充繁中 README` —— 文档
- `refactor: 抽取时间轴变换` —— 重构
- `test: 增加帧率边界测试` —— 测试

## 新增审计规则

1. 在 `sublens/audit.py` 中实现 `r_xxxx(sub, cfg) -> List[Finding]`；
2. 分配稳定规则 ID（`SUB0NN`），并注册到 `RULES` 与 `RULE_IDS`；
3. 在 `tests/test_audit_repair.py` 中补充正例与反例；
4. 若在 README 规则表中列出，三语 README 需同步更新。

## 设计原则

- **确定性**：禁止随机、禁止依赖当前时间、禁止浮点累积误差（统一用毫秒整数）。
- **只读审计**：audit 模块不得修改字幕对象。
- **无损往返**：解析 -> 写出应尽可能保真（标识符、settings、头部块）。
- **零依赖**：运行时仅用 Python 标准库。

## Pull Request

- 一个 PR 只做一件事；
- 附上运行 `python3 -m unittest discover -s tests` 的结果；
- 更新相关语言 README（至少英文）。
