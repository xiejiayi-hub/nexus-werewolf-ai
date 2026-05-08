import { useEffect, useState } from "react";

function App() {
  // ======================
  // 状态层
  // ======================
  const [ws, setWs] = useState(null);

  const [logs, setLogs] = useState([]);
  const [currentSpeaker, setCurrentSpeaker] = useState(1);
  const [phase, setPhase] = useState("");

  const [trustMatrix, setTrustMatrix] = useState({});
  const [aiThought, setAiThought] = useState("");
  const [selectedAI, setSelectedAI] = useState(1);

  const players = [1, 2, 3, 4, 5, 6];

  // ======================
  // WebSocket（核心实时层）
  // ======================
  useEffect(() => {
    const socket = new WebSocket("ws://localhost:8000/ws/1");

    socket.onopen = () => {
      console.log("WS connected");
    };

    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);

      switch (msg.type) {

        case "SPEECH":
          setLogs((p) => [...p, msg.data]);
          break;

        case "NEXT_SPEAKER":
          setCurrentSpeaker(msg.data.current);
          break;

        case "GAME_START":
          setCurrentSpeaker(msg.data.first_speaker);
          break;

        case "NIGHT_RESULT":
        case "ELIMINATION":
          setLogs((p) => [...p, msg.data]);
          break;
      }
    };

    socket.onclose = () => console.log("WS closed");
    socket.onerror = (e) => console.log("WS error", e);

    setWs(socket);
    return () => socket.close();
  }, []);

  // ======================
  // 游戏状态
  // ======================
  useEffect(() => {
    fetch("http://localhost:8000/api/game/status")
      .then((r) => r.json())
      .then((d) => {
        setCurrentSpeaker(d.current_speaker);
        setPhase(d.phase);
      });
  }, []);

  // ======================
  // trust matrix
  // ======================
  useEffect(() => {
    fetch("http://localhost:8000/api/game/trust-matrix")
      .then((r) => r.json())
      .then((d) => setTrustMatrix(d.trust_matrix));
  }, []);

  // ======================
  // AI thought
  // ======================
  useEffect(() => {
    fetch(`http://localhost:8000/api/ai/thought/${selectedAI}`)
      .then((r) => r.json())
      .then((d) => setAiThought(d.thought));
  }, [selectedAI]);

  // ======================
  // UI
  // ======================
  return (
    <div style={{ display: "flex", padding: 20 }}>

      {/* ================= 左侧 ================= */}
      <div style={{ flex: 1 }}>

        <h2>AI Werewolf Nexus</h2>

        <div>
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
                  alignItems: "center",
                  justifyContent: "center",
                  border: id === currentSpeaker ? "3px solid red" : "1px solid #999",
                  background: "white"
                }}
              >
              <div>P{id}</div>
              {phase === "VOTE" && (
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

        {/* ===== log ===== */}
        <div>
          {logs.map((l, i) => (
            <div key={i}>
              P{l.player_id}: {l.content || l.speech}
            </div>
          ))}
        </div>

      </div>

      {/* ================= 右侧 ================= */}
      <div style={{ width: 350, marginLeft: 20 }}>

        <h3>AI 思维监视器</h3>

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

        {/* thought */}
        <div style={{
          border: "1px solid #ccc",
          padding: 10,
          marginTop: 10,
          minHeight: 100
        }}>
          {aiThought}
        </div>

        {/* trust matrix */}
        <div style={{ marginTop: 20 }}>
          <h4>Trust Matrix</h4>

          {Object.entries(trustMatrix || {}).map(([from, row]) => (
            <div key={from}>
              {Object.entries(row).map(([to, v]) => (
                <span
                  key={to}
                  style={{
                    display: "inline-block",
                    width: 28,
                    textAlign: "center",
                    background: v > 60 ? "#4ade80" : v < 40 ? "#f87171" : "#ddd"
                  }}
                >
                  {v}
                </span>
              ))}
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

export default App;