export default function ThoughtWindow({

  thought,
  selectedAI,
  onClose

}) {

  // 没有内容不显示
  if (!thought) return null;

  return (

    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 999
      }}
    >

      {/* 内容窗口 */}
      <div
        style={{
          width: 500,
          background: "white",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 0 20px rgba(0,0,0,0.3)"
        }}
      >

        <h2>
          AI {selectedAI} 内心独白
        </h2>

        <div
          style={{
            marginTop: 16,
            lineHeight: 1.6,
            whiteSpace: "pre-wrap"
          }}
        >
          {thought}
        </div>

        <button
          onClick={onClose}
          style={{
            marginTop: 20,
            padding: "8px 16px",
            cursor: "pointer"
          }}
        >
          关闭
        </button>

      </div>
    </div>
  );
}