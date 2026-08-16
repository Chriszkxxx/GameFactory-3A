<p align="center">
  <img src="https://github.com/user-attachments/assets/61446541-7aa0-46f3-9023-496f90678372" alt="A3GameForge" width="240" />
</p>

# A3GameForge

**A3GameForge 让 Coding Agent 根据游戏需求生成可用于游戏构建的资产与引擎代码。**

> **A3GameForge 是一个全面的开源 3A 游戏生成 Skill 与资产框架。** 它覆盖图片、3D 资产、动作、音频与 CG 视频生成，并支持使用 **UE5、Blender、Unity 和 three.js** 构建游戏。

[English](README.md)

---

## 游戏演示

<!--
视频插入规则：
- 先将视频上传到 GitHub Issue 或 Pull Request，再把生成的
  github.com/user-attachments/assets/... 链接替换到下方 VIDEO_URL 槽位。
- 每条横版视频统一使用 width="420"；桌面端每行两个，第三、第四条放在下一行。
- 建议使用 16:9 MP4、时长 20–60 秒；若玩法目标不明显，在每一行视频后补一行说明。
-->

### UE5

<p align="center">
  <video src="VIDEO_URL_UE5_01" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_UE5_02" width="420" controls muted playsinline></video>
</p>
<p align="center">
  <video src="VIDEO_URL_UE5_03" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_UE5_04" width="420" controls muted playsinline></video>
</p>

### Blender

<p align="center">
  <video src="VIDEO_URL_BLENDER_01" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_BLENDER_02" width="420" controls muted playsinline></video>
</p>
<p align="center">
  <video src="VIDEO_URL_BLENDER_03" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_BLENDER_04" width="420" controls muted playsinline></video>
</p>

### Unity

<p align="center">
  <video src="VIDEO_URL_UNITY_01" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_UNITY_02" width="420" controls muted playsinline></video>
</p>
<p align="center">
  <video src="VIDEO_URL_UNITY_03" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_UNITY_04" width="420" controls muted playsinline></video>
</p>

### three.js

<p align="center">
  <video src="VIDEO_URL_THREE_JS_01" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_THREE_JS_02" width="420" controls muted playsinline></video>
</p>
<p align="center">
  <video src="VIDEO_URL_THREE_JS_03" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_THREE_JS_04" width="420" controls muted playsinline></video>
</p>

## CG 视频演示

<p align="center">
  <video src="VIDEO_URL_CG_01" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_CG_02" width="420" controls muted playsinline></video>
</p>
<p align="center">
  <video src="VIDEO_URL_CG_03" width="420" controls muted playsinline></video>
  <video src="VIDEO_URL_CG_04" width="420" controls muted playsinline></video>
</p>

---

## 快速开始：让 Coding Agent 生成游戏

```text
1. 打开 Coding Agent，例如 Codex、Claude Code（CC）或其他兼容 Agent。
2. cd A3GameForge
3. 告诉 Agent 你的游戏需求，并要求它先阅读 agent_skills/setting_overview.md。
```

`agent_skills/setting_overview.md` 是使用 A3GameForge 生成资产、玩法、UI
和特定引擎游戏时的入口文档。它会将 Agent 路由到对应的资产 Skill 和引擎
API 上下文。

### 为 A3GameForge 框架贡献代码

这与“使用框架生成游戏”是两条独立路径。若要新增或修改模型封装、Operator
或 Pipeline Runner，请从
[`agent_skills/develop_harness/README.md`](agent_skills/develop_harness/README.md)
开始，并先运行其中定义的 CPU smoke harness，再使用模型权重或 GPU。

---

## A3GameForge 能做什么

| 能力 | 产物 | 主要 Pipeline 位置 |
|---|---|---|
| 图片与 T-pose 预处理 | 源图像、角色可用输入 | `pipeline/assets_gen/gen_tpose_image/` |
| 3D 物体生成 | 道具、角色、武器与可复用网格 | `pipeline/assets_gen/gen_3d_object/` |
| 3D 场景生成 | 重建的室内场景或组合式环境 | `pipeline/assets_gen/gen_3d_scene/` |
| 动作生成 | 骨骼、生成动作、重定向动画片段 | `pipeline/assets_gen/gen_motion/` |
| 音频生成 | 对话、音效、环境声与 WAV 资产 | `pipeline/assets_gen/gen_audio/` |
| CG 视频生成 | 文本、首帧、首尾帧、参考图驱动的 MP4 | `pipeline/assets_gen/gen_cg_video/` |
| 玩法生成 | 引擎原生的机制与运行时行为 | `pipeline/mechanic/` |
| UI 生成 | HUD、菜单、界面与交互流程 | `pipeline/ui/` |
| 完整游戏切片 | 资产、玩法、UI 与评测的协同结果 | `pipeline/full_pipeline/` |

### 支持的游戏构建引擎

| 引擎 | Agent 上下文 | 参考实现 |
|---|---|---|
| UE5 | `agent_skills/engine_context/ue5_api.md` | `engine_adapters/ue5/` |
| Blender | `agent_skills/engine_context/blender_api.md` | `engine_adapters/blender/` |
| Unity | `agent_skills/engine_context/unity3d_api.md` | `engine_adapters/unity3d/` |
| three.js | `agent_skills/engine_context/three_js_api.md` | `engine_adapters/three_js/` |

---

## 项目目录

```text
A3GameForge/
├── agent_skills/               # 供 Agent 阅读的工作流、QA Skill 与引擎 API 上下文
│   ├── setting_overview.md     # 游戏生成 Agent 从这里开始
│   ├── asset_qa/               # 资产生成与视觉 QA Skill
│   ├── code_gen/               # 将已验收资产整合为玩法和 UI 的 Skill
│   ├── develop_harness/        # models → operators → pipeline 的贡献者契约
│   ├── engine_context/         # UE5、Blender、Unity、three.js 与浏览器 API 上下文
│   └── reference/              # 已迁移的任务说明与后端参考资料
├── engine_adapters/            # 引擎参考代码与公开 Adapter API
├── models/                     # 本地模型与云模型封装
├── operators/                  # 组合已加载模型的任务逻辑
├── pipeline/                   # 生成、评测与完整 Pipeline 入口
│   ├── assets_gen/             # 图片、3D、场景、动作、音频与 CG 视频任务
│   ├── mechanic/               # 玩法代码生成
│   ├── ui/                     # UI 代码生成
│   └── full_pipeline/          # 端到端游戏切片编排
├── scripts/                    # 环境配置、引擎启动器与导入工具
│   ├── asset_env_setup/        # 按资产任务组织的环境配置
│   ├── engine_install/         # UE5、Blender、Unity、three.js 的安装与启动脚本
│   ├── gen_motion/             # 动作运行时、固定源码与权重安装
│   └── cloud_api_install.sh    # 各任务云 API 安装器复用的共享实现
├── test/                       # 用于验证流程实际可运行的契约、集成与 smoke 脚本
├── test_data/                  # 示例需求；生成的游戏结果位于 outputs/
└── third_party/                # 资产/引擎安装包与检出的外部依赖
```

生成产物位于 `test_data/outputs/`，并按照游戏、运行、任务类别和任务 ID
组织。Agent 与贡献者应使用 `pipeline/common/paths.py`，不要手工拼接输出路径。

---

## 引用

```bibtex
@misc{a3gameforge,
  title        = {A3GameForge: Open-Source 3A Game Generation Skills and Asset Framework},
  author       = {},
  year         = {2026},
  howpublished = {\url{https://github.com/OpenDCAI/AAAGameForge}},
  note         = {Open-source software repository}
}
```
