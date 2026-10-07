import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

// Composição de teste: tipografia cinética branca (estilo dinamico_branco do editor).
export const Teste: React.FC<{ texto: string }> = ({ texto }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const palavras = texto.split(" ");
  return (
    <AbsoluteFill style={{ backgroundColor: "#111", justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", width: "85%", gap: 24 }}>
        {palavras.map((p, i) => {
          const s = spring({ frame: frame - i * 6, fps, config: { damping: 12 } });
          const destaque = i === palavras.length - 1;
          return (
            <span key={i} style={{
              fontFamily: "Inter, sans-serif", color: "white",
              fontWeight: destaque ? 900 : 600, fontSize: destaque ? 150 : 90,
              transform: `scale(${s})`, opacity: interpolate(s, [0, 1], [0, 1]),
            }}>{destaque ? p.toUpperCase() : p}</span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
