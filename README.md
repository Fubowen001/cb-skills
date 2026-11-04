# CB Skills

个人可复用 Codex 技能库。每个 skill 独立维护，仓库保存技能说明、工具代码与必要资源；实际项目的照片、模型、运行环境和账号配置留在本机。

## 技能目录

| Skill | 用途 | 入口 |
|---|---|---|
| photo-to-3d-diorama | 根据照片或原画制作完整 3D 微观场景；支持风格参考、分部制作和证据化验收 | [技能说明](skills/photo-to-3d-diorama/SKILL.md) |

[机器可读目录](catalog.json)由管理脚本生成。

## 在 Codex 中安装

向 Codex 发送：

> 请使用 skill-installer，从 Fubowen001/cb-skills 安装 skills/photo-to-3d-diorama。

已安装同名技能时，先备份并比较本机修改，再更新；安装工具遇到同名目录会停止，不会自动覆盖。安装完成后在下一轮对话使用：

> $photo-to-3d-diorama 将我上传的照片分别制作成完整的 3D 微观场景。

技能代码不等于运行环境已配置，首次使用请检查该技能的依赖和交付格式。

## 管理方式

- **新增：** 新建 `skills/技能名/SKILL.md`，其余代码和资源放在同一目录。
- **修改：** 在仓库中改源码、检查并提交，然后同步到本机安装目录；项目案例不提交。
- **更新目录：** `python scripts/manage_skills.py catalog`。
- **检查：** `python scripts/manage_skills.py check`；每次推送及 PR 都会自动运行检查。
- **版本：** 用 Git 提交记录追踪修改；需要固定某技能版本时，可使用 `技能名-v版本号` 标签，不必让全部技能一起升级。

详细步骤见 [管理指南](docs/管理指南.md) 和 [贡献说明](CONTRIBUTING.md)。

```text
skills/<skill-name>/SKILL.md   技能入口
skills/<skill-name>/scripts/  可复用工具
skills/<skill-name>/references/  按需阅读的流程说明
skills/<skill-name>/assets/   必要模板和第三方资源
scripts/manage_skills.py     目录生成和基础检查
docs/                       仓库级管理说明
```

## 当前技能的能力边界

photo-to-3d-diorama 包含本机 TripoSplat 高斯生成、分部与细节工具和验收流程。可编辑网格、骨骼或碰撞需要实际制作，保存为 Blender 文件不自动获得这些能力。流程测试通过不代表任意照片都能达到严格视觉还原。第三方预览库许可保留在技能内的 `assets/LICENSE.txt`。
