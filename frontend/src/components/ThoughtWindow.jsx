// frontend/src/components/ThoughtWindow.jsx

import React from 'react';

const ThoughtWindow = ({ thought, selectedAI, onClose }) => {
  if (!thought) {
    return (
      <div style={{
        border: '1px solid #ddd',
        borderRadius: 8,
        padding: 12,
        marginTop: 16,
        background: '#f9f9f9'
      }}>
        <h4 style={{ margin: '0 0 8px 0' }}>AI 内心独白</h4>
        <div style={{ color: '#999', textAlign: 'center', padding: 20 }}>
          点击玩家头像查看 AI 心理活动
        </div>
      </div>
    );
  }

  return (
    <div style={{
      border: '1px solid #ddd',
      borderRadius: 8,
      padding: 12,
      marginTop: 16,
      background: '#f9f9f9',
      position: 'relative'
    }}>
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          right: 8,
          top: 8,
          background: 'none',
          border: 'none',
          fontSize: 16,
          cursor: 'pointer'
        }}
      >
        ×
      </button>
      <h4 style={{ margin: '0 0 8px 0' }}>AI {selectedAI} 的内心独白</h4>
      <div style={{
        padding: 8,
        background: 'white',
        borderRadius: 4,
        border: '1px solid #eee',
        fontStyle: 'italic'
      }}>
        {thought}
      </div>
    </div>
  );
};

export default ThoughtWindow;