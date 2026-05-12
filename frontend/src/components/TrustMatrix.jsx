import React, { useEffect, useState } from 'react';

const TrustMatrix = ({ trustMatrix: externalTrustMatrix }) => {
  const [trustMatrix, setTrustMatrix] = useState({});
  
  useEffect(() => {
    console.log("TrustMatrix 收到外部数据:", externalTrustMatrix);
    if (externalTrustMatrix && Object.keys(externalTrustMatrix).length > 0) {
      setTrustMatrix(externalTrustMatrix);
    }
  }, [externalTrustMatrix]);
  
  const players = [1, 2, 3, 4, 5, 6];
  
  // 鲜艳的背景颜色（字体保持黑色）
  const getBackgroundColor = (score) => {
    if (score >= 70) {
      return '#4caf50'; // 鲜绿色 - 非常信任
    } else if (score >= 60) {
      return '#8bc34a'; // 草绿色 - 信任
    } else if (score >= 45) {
      return '#ffeb3b'; // 鲜黄色 - 中等信任
    } else if (score >= 35) {
      return '#ff9800'; // 橙色 - 怀疑
    } else {
      return '#f44336'; // 红色 - 非常怀疑
    }
  };
  
  // 如果信任矩阵为空，显示提示
  if (Object.keys(trustMatrix).length === 0) {
    return (
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12, background: 'white', marginBottom: 16 }}>
        <h4 style={{ margin: '0 0 12px 0' }}>信任矩阵 (谁信任谁)</h4>
        <div style={{ textAlign: 'center', color: '#999' }}>等待游戏开始...</div>
      </div>
    );
  }

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
                        backgroundColor: getBackgroundColor(score),
                        color: '#000',  // 黑色字体
                        fontWeight: 'bold'
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
      <div style={{ marginTop: 12, fontSize: 12, display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <span><span style={{ backgroundColor: '#4caf50', padding: '2px 8px', borderRadius: 4, color: 'white' }}>  </span> 非常信任(≥70)</span>
        <span><span style={{ backgroundColor: '#8bc34a', padding: '2px 8px', borderRadius: 4, color: 'white' }}>  </span> 信任(60-69)</span>
        <span><span style={{ backgroundColor: '#ffeb3b', padding: '2px 8px', borderRadius: 4 }}>  </span> 中等(45-59)</span>
        <span><span style={{ backgroundColor: '#ff9800', padding: '2px 8px', borderRadius: 4, color: 'white' }}>  </span> 怀疑(35-44)</span>
        <span><span style={{ backgroundColor: '#f44336', padding: '2px 8px', borderRadius: 4, color: 'white' }}>  </span> 敌视(&lt;35)</span>
      </div>
    </div>
  );
};

export default TrustMatrix;