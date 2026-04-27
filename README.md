# nexus-werewolf-ai
A multi-agent werewolf game platform with human-AI interaction and thought-process visualization.
# Nexus-Werewolf AI：分布式多智能体博弈与可视化平台

## 1. 项目愿景
本项目致力于构建一个基于 **DeepSeek-V3/R1** 大语言模型的智能博弈系统。通过 5 名 AI 智能体与 1 名人类玩家的同台对抗，探索 AI 在不完全信息博弈中的**逻辑推理、身份伪装、信任构建及长短期记忆管理**能力。

### 核心亮点
- **思维黑盒透明化**：实时展示 AI 的内心独白（Thought Chain），揭示其决策逻辑。
- **信任矩阵可视化**：动态量化智能体间的信任度变化。
- **人机无缝对讲**：支持自然语言输入，AI 自动进行意图解析与博弈响应。

---

## 2. 技术架构 (System Architecture)

本项目采用前后端分离架构，通过异步消息机制确保智能体决策的高并发处理：

- **Frontend**: React 18 + Vite + Tailwind CSS + WebSocket (用于实时状态同步)
- **Backend**: Python 3.10 + FastAPI + Pydantic (严格类型校验)
- **AI Engine**: DeepSeek-V3 API + LangChain / PydanticAI
- **Data/Memory**: Redis (实时缓存) + SQLite (历史回溯) + 文本摘要算法 (Memory Summary)

---

## 3. 团队分工与 8 天冲刺路线图 (Sprint Plan)

### 3.1 成员职责
- **组长 (Lead)**: 后端核心引擎、状态机、API 协议定义、系统集成。
- **算法 (AI)**: Prompt 工程、思维链设计、结构化输出控制、API 调用稳定性。
- **数据 (Data)**: 记忆摘要系统、信任度矩阵计算、对话持久化。
- **前端 (Front)**: 响应式 Web 界面、WebSocket 交互逻辑、AI 思维监控看板。
- **工程 (QA)**: 自动化测试脚本、Docker 容器化、演示视频录制、技术文档。

### 3.2 每日里程碑
| 日期 | 阶段 | 核心目标 |
| :--- | :--- | :--- |
| **Day 1** | **协议筑基** | 完成 API 协议定义，跑通“前端-后端-AI”最小闭环（Hello World）。 |
| **Day 2** | **逻辑闭环** | 实现核心游戏流程（发牌、发言轮询、投票），AI 能返回基础 JSON。 |
| **Day 3** | **灵魂注入** | A 组员优化身份 Prompt，AI 开始学会根据身份进行伪装与反驳。 |
| **Day 4** | **记忆增强** | D 组员实现对话摘要，解决长文本 Token 溢出，AI 开始拥有“记性”。 |
| **Day 5** | **可视化** | F 组员完成“内心独白”与“信任关系图”渲染，D 完成信任评分系统。 |
| **Day 6** | **人机融合** | L 组员打通人类玩家接入点，实现发言中断与语义解析。 |
| **Day 7** | **健壮性优化** | 压力测试，处理 API 报错重试逻辑，优化 UI 动效与交互细节。 |
| **Day 8** | **交付展示** | 录制 Demo 视频，整理最终技术文档，准备演示 PPT。 |

---

## 4. 通信协议规范 (Critical Spec)

### 4.1 AI 智能体输出标准 (JSON)
AI 必须返回以下结构，否则后端将触发 Retry 逻辑：
```json
{
  "player_id": 1,
  "role": "WEREWOLF", 
  "thought": "3号玩家发言有逻辑漏洞，我决定悍跳预言家查杀他。",
  "speech": "我是预言家，昨晚查验了3号，他是狼！",
  "vote_target": 3,
  "trust_scores": {"2": 50, "3": 10, "4": 80, "5": 60, "6": 60}
}
4.2 游戏阶段定义 (Phase)
• WAITING: 房间等待
• NIGHT_WOLF: 狼人请睁眼 (AI 协同)
• NIGHT_SEER: 预言家查验
• DAY_DISCUSSION: 白天自由发言 (人类玩家可在此阶段输入)
• DAY_VOTE: 全员投票
• GAME_OVER: 结算
￼
5. 开发守则 (Engineering Guidelines)
1. API Key 安全: 严禁将 .env 或包含 API Key 的代码上传至仓库！使用 config.py 读取环境变量。
2. 分支策略: 采用 Feature Branch 模式。新功能请从 main 切出分支，合并需经过组长 Code Review。
3. 失败回退: AI 接口响应超时需返回默认的“划水发言”，确保游戏进程不中断。
