import React, { useEffect, useState } from 'react';

const TrustMatrix = ({ trustMatrix: externalTrustMatrix }) => {
  const [trustMatrix, setTrustMatrix] = useState({});
  
  useEffect(() => {
    if (externalTrustMatrix && Object.keys(externalTrustMatrix).length > 0) {
      setTrustMatrix(externalTrustMatrix);
    }
  }, [externalTrustMatrix]);
  
  const players = [1, 2, 3, 4, 5, 6];
  
  const getTrustColor = (score) => {
    if (score >= 70) return '#4caf50'; // 绿色 - 信任
    if (score >= 40) return '#ff9800'; // 橙色 - 中等
    return '#f44336'; // 红色 - 不信任
  };
  
  return (
    <div style={{
      border: '1px solid #ddd',
      borderRadius: 8,
      padding: 12,
      background: 'white',
      marginBottom: 16
    }}>
      <h4 style={{ margin: '0 0 12px 0' }}>信任矩阵 (谁信任谁)</h4>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ padding: 8, background: '#f5f5f5' }}>↓信任者\被信任者→</th>
              {players.map(p => (
                <th key={p} style={{ padding: 8, background: '#f5f5f5' }}>P{p}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {players.map(evaluator => (
              <tr key={evaluator}>
                <td style={{ padding: 8, fontWeight: 'bold', background: '#fafafa' }}>
                  P{evaluator}
                </td>
                {players.map(target => {
                  const score = trustMatrix[evaluator]?.[target] || 50;
                  return (
                    <td
                      key={target}
                      style={{
                        padding: 8,
                        textAlign: 'center',
                        backgroundColor: getTrustColor(score),
                        color: score >= 70 ? 'white' : 'black'
                      }}
                    >
                      {Math.round(score)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: '#666' }}>
        <span style={{ color: '#4caf50' }}>● 信任(≥70)</span>
        <span style={{ color: '#ff9800', marginLeft: 8 }}>● 中等(40-69)</span>
        <span style={{ color: '#f44336', marginLeft: 8 }}>● 不信任(&lt;40)</span>
      </div>
    </div>
  );
};

export default TrustMatrix;