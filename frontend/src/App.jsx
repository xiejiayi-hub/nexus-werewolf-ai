import { useEffect, useState } from "react";
import TrustMatrix from "./components/TrustMatrix";
import ThoughtWindow from "./components/ThoughtWindow";

function App() {
  // ======================
  // 状态层
  // ======================
  const [ws, setWs] = useState(null);
  const [logs, setLogs] = useState([]);
  const [currentSpeaker, setCurrentSpeaker] = useState(1);
  const [phase, setPhase] = useState("");
  const [isMyTurn, setIsMyTurn] = useState(false);
  const [votePhase, setVotePhase] = useState(false);
  const [voteTarget, setVoteTarget] = useState(null);
  const [currentPlayer, setCurrentPlayer] = useState(1);
  const [myRole, setMyRole] = useState("");
  const [myPlayerId, setMyPlayerId] = useState(1); 
  const [isConnected, setIsConnected] = useState(false);
  const [selectedThought, setSelectedThought] = useState(null);
  const [selectedAI, setSelectedAI] = useState(1);
  const [trustMatrix, setTrustMatrix] = useState({});
  const [matrixUpdateTrigger, setMatrixUpdateTrigger] = useState(0);
  const [speechInput, setSpeechInput] = useState("");
  const [eliminatedPlayers, setEliminatedPlayers] = useState([]);
  
  // ========== 新增：夜晚选择相关状态 ==========
  const [nightAction, setNightAction] = useState(null);
  const [nightCandidates, setNightCandidates] = useState([]);
  const [showNightModal, setShowNightModal] = useState(false);
  const [nightActionType, setNightActionType] = useState("");

  const players = [1, 2, 3, 4, 5, 6];

  // ========== 定义 fetchTrustMatrix 函数 ==========
  const fetchTrustMatrix = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/game/trust-matrix");
      const data = await response.json();
      console.log("信任矩阵数据:", data.trust_matrix);
      setTrustMatrix(data.trust_matrix);
    } catch (err) {
      console.error("获取信任矩阵失败:", err);
    }
  };

  // ========== 定时刷新信任矩阵 ==========
  useEffect(() => {
    fetchTrustMatrix();  // 立即获取一次
    const interval = setInterval(fetchTrustMatrix, 2000); // 每2秒刷新一次
    return () => clearInterval(interval);  // 清理定时器
  }, [matrixUpdateTrigger]);  // 当matrixUpdateTrigger变化时重新获取

  // ======================
  // WebSocket（核心实时层）
  // ======================
  const handleSocketMessage = (data) => {
    console.log("=== 收到消息 ===");
    console.log("消息类型:", data.type);
    console.log("消息内容:", data.data);

    switch (data.type) {

      case "ROLE_ASSIGNMENT":
        console.log("收到角色分配:", data.data);
        console.log("当前玩家ID:", currentPlayer);
        console.log("data.data.player_id:", data.data.player_id);
        if (data.data.player_id === currentPlayer) {
            setMyRole(data.data.role);
            console.log("设置角色为:", data.data.role);
            
            let roleMessage = `你的身份是：${data.data.role}`;
            
            if (data.data.role === "WEREWOLF" && data.data.werewolf_teammates) {
                const teammates = data.data.werewolf_teammates.map(id => `P${id}`).join(", ");
                roleMessage += `，你的狼人队友是：${teammates}`;
                console.log("狼人队友:", teammates);
            }
            
            setLogs((prev) => [
                ...prev,
                {
                    player_id: "SYSTEM",
                    content: roleMessage
                }
            ]);
        } else {
            console.log("角色分配不是给当前玩家，忽略");
        }
        break;
      
      // ========== 新增：处理夜晚选择请求 ==========
      case "NIGHT_CHOOSE_TARGET":
        console.log("夜晚选择目标:", data.data);
        setNightActionType(data.data.action);
        setNightCandidates(data.data.candidates);
        setShowNightModal(true);
        break;

      // ========== 新增：处理预言家查验结果 ==========
      case "SEER_RESULT":
        setLogs((prev) => [
          ...prev,
          {
            player_id: "SYSTEM",
            content: `🔍 你查验了 P${data.data.target}，他是${data.data.result}`
          }
        ]);
        break;

      // ======================
      // 游戏开始
      // ======================
      case "GAME_START":
        setCurrentSpeaker(data.data.first_speaker);
        setMatrixUpdateTrigger(prev => prev + 1);
        setLogs((prev) => [
          ...prev,
          {
            player_id: "SYSTEM",
            content: "游戏开始"
          }
        ]);

        break;

      // ======================
      // 轮到当前玩家
      // ======================
      case "YOUR_TURN":
        console.log("收到 YOUR_TURN 消息:", data.data);  // 添加日志
        setIsMyTurn(true);
        setVotePhase(false);
        setPhase("DAY");

        // 添加系统提示
        setLogs((prev) => [
          ...prev,
          {
            player_id: "SYSTEM",
            content: `轮到你发言了！你是 ${myPlayerId} 号玩家`
          }
        ]);
        break;

      // ======================
      // 进入投票阶段
      // ======================
      case "VOTE_PHASE":

        setVotePhase(true);
        setIsMyTurn(false);
        setPhase("VOTE");

        break;

      case "VOTE_CAST":
        setMatrixUpdateTrigger(prev => prev + 1);
        setLogs((prev) => [...prev, data.data]);

        break;

      // ======================
      // 玩家发言
      // ======================
      case "SPEECH":
        setMatrixUpdateTrigger(prev => prev + 1);
        setLogs((prev) => [...prev, data.data]);

        break;

      // ======================
      // 下一位发言人
      // ======================
      case "NEXT_SPEAKER":

        setCurrentSpeaker(data.data.current);

        break;

      // ======================
      // 玩家淘汰
      // ======================
      case "ELIMINATION":
        setMatrixUpdateTrigger(prev => prev + 1);
        setLogs((prev) => [...prev, data.data]);

        // 记录淘汰玩家
        setEliminatedPlayers((prev) => [
          ...prev,
          data.data.player_id
        ]);

        break;

      // ======================
      // 夜晚结果
      // ======================
      case "NIGHT_RESULT":

        setLogs((prev) => [...prev, data.data]);

        break;


      case "NEXT_DAY":

        setLogs((prev) => [
          ...prev,
          {
            player_id: "SYSTEM",
            content: `进入第 ${data.data.round} 天`
          }
        ]);
        setMatrixUpdateTrigger(prev => prev + 1);
        setCurrentSpeaker(data.data.current);
        // 更新存活玩家列表，移除已淘汰的
        if (data.data.alive_players) {
          const newEliminated = players.filter(p => !data.data.alive_players.includes(p));
          setEliminatedPlayers(newEliminated);
        }
        break;


      // ======================
      // 游戏结束
      // ======================
      case "GAME_OVER":

        alert(`游戏结束：${data.data.winner}`);

        setIsMyTurn(false);
        setVotePhase(false);

        break;

      // ======================
      // 未知消息
      // ======================
      default:

        console.log("Unknown WS message:", data);
    }
  };
  
  useEffect(() => {
    const playerId = 1;  // 人类玩家固定为1
    setCurrentPlayer(playerId);
    setMyPlayerId(playerId);

    console.log("正在连接 WebSocket...");
    const socket = new WebSocket(`ws://localhost:8000/ws/${playerId}`);

    socket.onopen = () => {
      console.log("✅ WebSocket 连接成功!");
      console.log("准备设置 isConnected = true");
      setIsConnected(true);
      console.log("isConnected 已设置为 true");
    };

    socket.onmessage = (event) => {
      console.log("收到 WebSocket 消息:", event.data);
      const data = JSON.parse(event.data);
      handleSocketMessage(data);
    };

    socket.onclose = (event) => {
      console.log("❌ WebSocket 断开连接, code:", event.code, "reason:", event.reason);
      setIsConnected(false);
    };

    socket.onerror = (e) => {
      console.log("⚠️ WebSocket 错误:", e);
      setIsConnected(false);
    };

    setWs(socket);

    return () => {
      console.log("清理 WebSocket 连接");
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, []);
  
  // 调试：监听 isConnected 状态变化
  useEffect(() => {
    console.log("=== isConnected 状态变化 ===");
    console.log("isConnected 当前值:", isConnected);
  }, [isConnected]);

  const handleVote = async (targetId) => {

    try {

      // 当前选择目标
      setVoteTarget(targetId);

      await fetch(
        "http://localhost:8000/api/game/vote",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            voter_id: currentPlayer,
            target_id: targetId,
          }),
        }
      );

      // 投票结束
      setVotePhase(false);

      // 系统日志
      setLogs((prev) => [
        ...prev,
        {
          player_id: "SYSTEM",
          content: `你投票给了 P${targetId}`
        }
      ]);
      setMatrixUpdateTrigger(prev => prev + 1);

    } catch (err) {

      console.error("Vote failed:", err);
    }
  };

  const sendSpeech = () => {

    if (!speechInput.trim()) return;

    if (ws) {
      ws.send(speechInput);

      setSpeechInput("");
      setIsMyTurn(false);
    }
  };


  // ========== 获取AI思维 ==========
const fetchThought = async (playerId) => {
  console.log(`📖 正在获取 AI${playerId} 的内心独白...`);
  try {
    const response = await fetch(`http://localhost:8000/api/ai/thought/${playerId}`);
    const data = await response.json();
    console.log(`📖 AI${playerId} 内心独白:`, data.thought);
    setSelectedThought(data.thought);
    setSelectedAI(playerId);
  } catch (err) {
    console.error("Fetch thought failed:", err);
    setSelectedThought("无法获取心理活动，请重试");
  }
};

  const startGame = async () => {

    try {

      const response = await fetch(
        "http://localhost:8000/api/game/start",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      console.log("Game started:", data);

      setLogs((prev) => [
        ...prev,
        {
          player_id: "SYSTEM",
          content: "游戏开始"
        }
      ]);
      setMatrixUpdateTrigger(prev => prev + 1);  

    } catch (err) {

      console.error("Start game failed:", err);
    }
  };


  // ======================
  // 游戏状态
  // ======================
  useEffect(() => {

    const fetchStatus = async () => {

      const r = await fetch(
        "http://localhost:8000/api/game/status"
      );

      const d = await r.json();

      setCurrentSpeaker(d.current_speaker);
      setPhase(d.phase);
    };

    fetchStatus();

    const interval = setInterval(fetchStatus, 3000);

    return () => clearInterval(interval);

  }, []);


  // ======================
  // UI
  // ======================
  return (
    <div style={{ display: "flex", padding: 20 }}>

      {/* ================= 左侧 ================= */}
      <div style={{ flex: 1 }}>

        <h2>AI Werewolf Nexus</h2>

        <div>
          你是 {currentPlayer} 号玩家 | 身份：{myRole}
        </div>

        <button
          onClick={() => {
            console.log("按钮被点击，当前 isConnected:", isConnected);
            startGame();
          }}
          disabled={!isConnected}
          style={{
            marginTop: 10,
            padding: "8px 16px",
            cursor: isConnected ? "pointer" : "not-allowed",
            backgroundColor: isConnected ? "#007bff" : "#ccc",
            color: "white",
            border: "none",
            borderRadius: 4
          }}
        >
          {isConnected ? "开始游戏" : "连接中..."}
        </button>

        <button
          onClick={() => {
            if (ws) ws.close();
            setTimeout(() => {
              const newSocket = new WebSocket("ws://localhost:8000/ws/1");
              newSocket.onopen = () => {
                console.log("重连成功");
                setIsConnected(true);
                setWs(newSocket);
              };
              newSocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleSocketMessage(data);
              };
              newSocket.onclose = () => setIsConnected(false);
              newSocket.onerror = () => setIsConnected(false);
            }, 100);
          }}
          style={{ marginLeft: 10, padding: "8px 16px" }}
        >
          重连
        </button>
        
        <div style={{ marginTop: 10 }}>
          Phase: {phase} | Speaker: Player {currentSpeaker}
        </div>

        {/* ===== 圆桌 ===== */}
        <div style={{
          position: "relative",
          width: 320,
          height: 320,
          margin: "20px auto"
        }}>
          {players.map((id, i) => {
            const angle = (i / players.length) * 2 * Math.PI;
            const r = 120;

            const x = 160 + r * Math.cos(angle);
            const y = 160 + r * Math.sin(angle);

            return (
              <div
                key={id}
                style={{
                  position: "absolute",
                  left: x - 25,
                  top: y - 25,
                  width: 50,
                  height: 50,
                  borderRadius: "50%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  border: id === currentSpeaker ? "3px solid red" : "1px solid #999",
                  background: "white",
                  opacity: eliminatedPlayers.includes(id) ? 0.3 : 1,  // 添加这一行
                  filter: eliminatedPlayers.includes(id) ? "grayscale(100%)" : "none" 
                }}
              >
              <div
                onClick={() => fetchThought(id)}
                style={{
                  cursor: "pointer"
                }}
              >
                P{id}
              </div>
              {votePhase && id !== currentPlayer && (
                <button
                  onClick={() => handleVote(id)}
                  style={{
                    marginTop: 8,
                    fontSize: 12,
                    background: voteTarget === id ? "red" : "white",
                    cursor: "pointer"
                  }}
                >
                  投票
                </button>
              )}
              </div>
            );
          })}
        </div>

        {/* ===== 消息面板 ===== */}
        <div
          style={{
            marginTop: 20,
            border: "1px solid #ccc",
            borderRadius: 10,
            padding: 12,
            maxHeight: 350,
            overflowY: "auto",
            background: "#f8fafc"
          }}
        >

          <h3 style={{ marginTop: 0 }}>
            游戏消息面板
          </h3>

          {logs.map((msg, index) => {

            const playerId = msg.player_id;

            // 是否AI
            const isAI =
              playerId !== "SYSTEM";

            // 是否淘汰
            const isEliminated =
              eliminatedPlayers.includes(playerId);

            // 是否当前玩家
            const isCurrentSpeaker =
              playerId === currentSpeaker;

            return (

              <div
                key={index}
                style={{
                  padding: 10,
                  marginBottom: 10,
                  borderRadius: 8,

                  background:
                    isCurrentSpeaker
                      ? "#dbeafe"
                      : isAI
                      ? "#ecfeff"
                      : "#f3f4f6",

                  opacity:
                    isEliminated ? 0.45 : 1,

                  border:
                    isCurrentSpeaker
                      ? "2px solid #2563eb"
                      : "1px solid #ddd"
                }}
              >

                <div
                  style={{
                    fontWeight: "bold",
                    marginBottom: 4
                  }}
                >
                  {playerId === "SYSTEM"
                    ? "系统"
                    : `P${playerId}`}
                </div>

                <div>
                  {msg.content}
                </div>

              </div>
            );
          })}
        </div>

        {/* ===== 发言输入 ===== */}
        {isMyTurn && (

          <div style={{ marginTop: 20 }}>

            <input
              value={speechInput}
              onChange={(e) => setSpeechInput(e.target.value)}
              placeholder="输入你的发言"
              style={{
                padding: 8,
                width: 220,
                marginRight: 10
              }}
            />

            <button
              onClick={sendSpeech}
              style={{
                padding: "8px 16px",
                cursor: "pointer"
              }}
            >
              发言
            </button>

          </div>
        )}

      </div>

      {/* ================= 右侧 ================= */}
      <div style={{ width: 350, marginLeft: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>AI 思维监视器</h3>
          <button onClick={() => setMatrixUpdateTrigger(prev => prev + 1)} style={{ padding: '4px 8px', cursor: 'pointer' }}>
            🔄 刷新
          </button>
        </div>
        
        <TrustMatrix trustMatrix={trustMatrix} />
        
        {/* AI 按钮区域 - 排除人类玩家1号 */}
        <div style={{ marginTop: 12, marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#666', marginBottom: 8 }}>点击AI查看内心独白：</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {[2, 3, 4, 5, 6].map((id) => (  // 直接写死 AI 玩家编号
              <button
                key={id}
                onClick={() => {
                  console.log(`点击查看 AI${id} 的内心独白`);
                  setSelectedAI(id);
                  fetchThought(id);
                }}
                style={{
                  padding: '8px 16px',
                  cursor: 'pointer',
                  background: selectedAI === id ? "#007bff" : "#e0e0e0",
                  color: selectedAI === id ? "white" : "#333",
                  border: "none",
                  borderRadius: 6,
                  fontWeight: 'bold'
                }}
              >
                🤖 AI {id}
              </button>
            ))}
          </div>
        </div>
        
        <ThoughtWindow 
          thought={selectedThought} 
          selectedAI={selectedAI} 
          onClose={() => setSelectedThought(null)} 
        />
      </div>
      {/* ================= 夜晚选择弹窗 ================= */}
      {showNightModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: 12,
            padding: 24,
            width: 350,
            textAlign: 'center'
          }}>
            <h3 style={{ marginTop: 0 }}>
              {nightActionType === 'wolf_kill' && '🐺 狼人杀人'}
              {nightActionType === 'seer_check' && '🔮 预言家查验'}
              {nightActionType === 'witch_action' && '🧪 女巫行动'}
            </h3>
            
            {/* 女巫特殊界面 */}
            {nightActionType === 'witch_action' ? (
              <>
                <p>{nightCandidates.message || '请选择你的行动：'}</p>
                {nightCandidates.killed_target && (
                  <div style={{ marginBottom: 16 }}>
                    <p>🐺 被杀玩家：P{nightCandidates.killed_target}</p>
                    <button
                      onClick={() => {
                        if (ws) {
                          ws.send(JSON.stringify({
                            night_action: true,
                            action_type: 'witch_save',
                            target: nightCandidates.killed_target
                          }));
                        }
                        setShowNightModal(false);
                      }}
                      style={{
                        padding: '10px',
                        margin: '5px',
                        backgroundColor: '#28a745',
                        color: 'white',
                        border: 'none',
                        borderRadius: 6,
                        cursor: 'pointer'
                      }}
                    >
                      💊 使用解药救人
                    </button>
                  </div>
                )}
                <p>选择要毒杀的玩家：</p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {nightCandidates.candidates?.map(candidate => (
                    <button
                      key={candidate}
                      onClick={() => {
                        if (ws) {
                          ws.send(JSON.stringify({
                            night_action: true,
                            action_type: 'witch_poison',
                            target: candidate
                          }));
                        }
                        setShowNightModal(false);
                      }}
                      style={{
                        padding: '10px',
                        fontSize: 16,
                        cursor: 'pointer',
                        backgroundColor: '#dc3545',
                        color: 'white',
                        border: 'none',
                        borderRadius: 6
                      }}
                    >
                      💀 毒杀 P{candidate}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => {
                    if (ws) {
                      ws.send(JSON.stringify({
                        night_action: true,
                        action_type: 'witch_skip',
                        target: null
                      }));
                    }
                    setShowNightModal(false);
                  }}
                  style={{
                    marginTop: 16,
                    padding: '8px 16px',
                    cursor: 'pointer',
                    backgroundColor: '#6c757d',
                    color: 'white',
                    border: 'none',
                    borderRadius: 6
                  }}
                >
                  跳过（不使用技能）
                </button>
              </>
            ) : (
              // 狼人和预言家界面
              <>
                <p>
                  {nightActionType === 'wolf_kill' ? '请选择要击杀的目标：' : '请选择要查验的目标：'}
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {nightCandidates.map(candidate => (
                    <button
                      key={candidate}
                      onClick={() => {
                        if (ws) {
                          ws.send(JSON.stringify({
                            night_action: true,
                            action_type: nightActionType,
                            target: candidate
                          }));
                        }
                        setShowNightModal(false);
                        setNightCandidates([]);
                      }}
                      style={{
                        padding: '10px',
                        fontSize: 16,
                        cursor: 'pointer',
                        backgroundColor: '#007bff',
                        color: 'white',
                        border: 'none',
                        borderRadius: 6
                      }}
                    >
                      选择 P{candidate}
                    </button>
                  ))}
                </div>
              </>
            )}
            
            <button
              onClick={() => setShowNightModal(false)}
              style={{
                marginTop: 16,
                padding: '8px 16px',
                cursor: 'pointer',
                backgroundColor: '#ccc',
                border: 'none',
                borderRadius: 6
              }}
            >
              取消
            </button>
          </div>
        </div>
      )}

    </div>        // 最外层 flex 容器的结束标签
  );
}

export default App;