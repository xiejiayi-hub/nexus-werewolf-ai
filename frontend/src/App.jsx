import { useEffect, useState } from "react";
import TrustMatrix from "./components/TrustMatrix";
import ThoughtWindow from "./components/ThoughtWindow";

function App() {
  // ======================
  // 状态层
  // ======================
  const [ws, setWs] = useState(null);

  // 游戏日志
  const [logs, setLogs] = useState([]);

  // 当前发言玩家
  const [currentSpeaker, setCurrentSpeaker] = useState(1);

  // 当前阶段
  const [phase, setPhase] = useState("");

  // 是否轮到自己
  const [isMyTurn, setIsMyTurn] = useState(false);

  // 是否进入投票阶段
  const [votePhase, setVotePhase] = useState(false);

  // 当前选择投票目标
  const [voteTarget, setVoteTarget] = useState(null);

  // 当前用户ID
  const [currentPlayer, setCurrentPlayer] = useState(1);

  // AI thought
  const [selectedThought, setSelectedThought] = useState(null);

  // 当前查看的AI
  const [selectedAI, setSelectedAI] = useState(1);

  // 输入框内容
  const [speechInput, setSpeechInput] = useState("");
  const [eliminatedPlayers, setEliminatedPlayers] = useState([]);

  const players = [1, 2, 3, 4, 5, 6];
  // ======================
  // WebSocket（核心实时层）
  // ======================
  const handleSocketMessage = (data) => {

    switch (data.type) {

      // ======================
      // 轮到当前玩家
      // ======================
      case "YOUR_TURN":

        setIsMyTurn(true);
        setVotePhase(false);
        setPhase("DAY");

        break;

      // ======================
      // 进入投票阶段
      // ======================
      case "VOTE_PHASE":

        setVotePhase(true);
        setIsMyTurn(false);
        setPhase("VOTE");

        break;

      // ======================
      // 玩家发言
      // ======================
      case "SPEECH":

      case "AI_SPEECH":

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

      // ======================
      // 游戏开始
      // ======================
      case "GAME_START":

        setCurrentSpeaker(data.data.first_speaker);

        setLogs((prev) => [
          ...prev,
          {
            player_id: "SYSTEM",
            content: "游戏开始"
          }
        ]);

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

    const socket = new WebSocket(
      `ws://localhost:8000/ws/${currentPlayer}`
    );

    socket.onopen = () => {
      console.log("WebSocket connected");
    };

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleSocketMessage(data);
    };

    socket.onclose = () => {
      console.log("WebSocket disconnected");
    };

    socket.onerror = (e) => {
      console.log("WS error", e);
    };

    setWs(socket);

    return () => socket.close();

  }, [currentPlayer]);

  
  
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

    } catch (err) {

      console.error("Vote failed:", err);
    }
  };

  const sendSpeech = async () => {

    // 空输入不发送
    if (!speechInput.trim()) return;

    try {

      await fetch(
        "http://localhost:8000/api/game/ai/speak",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            player_id: currentPlayer,
            speech: speechInput,
          }),
        }
      );

      // 清空输入框
      setSpeechInput("");

      // 发言结束
      setIsMyTurn(false);

    } catch (err) {

      console.error("Send speech failed:", err);
    }
  };


  const fetchThought = async (playerId) => {

    try {

      const response = await fetch(
        `http://localhost:8000/api/ai/thought/${playerId}`
      );

      const data = await response.json();

      setSelectedThought(data.thought);

      setSelectedAI(playerId);

    } catch (err) {

      console.error("Fetch thought failed:", err);
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

        <button
          onClick={startGame}
          style={{
            marginTop: 10,
            padding: "8px 16px",
            cursor: "pointer"
          }}
        >
          开始游戏
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
                  background: "white"
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
                  {msg.content || msg.speech}
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

        <h3>AI 思维监视器</h3>

        <TrustMatrix />

        {/* AI选择 */}
        <div>
          {players.map((id) => (
            <button
              key={id}
              onClick={() => setSelectedAI(id)}
              style={{
                margin: 3,
                background: selectedAI === id ? "black" : "white",
                color: selectedAI === id ? "white" : "black"
              }}
            >
              AI{id}
            </button>
          ))}
        </div>

        <ThoughtWindow
          thought={selectedThought}
          selectedAI={selectedAI}
          onClose={() => setSelectedThought(null)}
        />


      </div>
    </div>
  );
}

export default App;