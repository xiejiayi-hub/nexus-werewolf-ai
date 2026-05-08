import { useEffect, useState } from "react";

function TrustMatrix() {

  const [trustMatrix, setTrustMatrix] = useState({});

  // ======================
  // 获取 trust matrix
  // ======================
  const fetchTrustMatrix = async () => {

    try {

      const response = await fetch(
        "http://localhost:8000/api/game/trust-matrix"
      );

      const data = await response.json();

      setTrustMatrix(data.trust_matrix);

    } catch (err) {

      console.error("Fetch trust matrix failed:", err);
    }
  };

  // ======================
  // 自动刷新
  // ======================
  useEffect(() => {

    fetchTrustMatrix();

    const interval = setInterval(
      fetchTrustMatrix,
      3000
    );

    return () => clearInterval(interval);

  }, []);

  // ======================
  // 根据信任值决定颜色
  // ======================
  const getColor = (value) => {

    if (value >= 70) return "#22c55e";

    if (value >= 40) return "#eab308";

    return "#ef4444";
  };

  return (

    <div style={{ marginTop: 20 }}>

      <h4>Trust Matrix</h4>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 6
        }}
      >

        {Object.entries(trustMatrix || {}).map(
          ([from, row]) => (

            <div
              key={from}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4
              }}
            >

              {/* 行标签 */}
              <div
                style={{
                  width: 30,
                  fontWeight: "bold"
                }}
              >
                P{from}
              </div>

              {/* 热力图 */}
              {Object.entries(row).map(([to, value]) => (

                <div
                  key={to}
                  title={`P${from} -> P${to}: ${value}`}
                  style={{
                    width: 38,
                    height: 38,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: getColor(value),
                    color: "white",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: "bold"
                  }}
                >
                  {value}
                </div>

              ))}

            </div>
          )
        )}

      </div>

    </div>
  );
}

export default TrustMatrix;