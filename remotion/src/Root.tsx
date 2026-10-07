import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { Teste } from "./Teste";
import { Elemento, metadados, padrao } from "./Elemento";
import { Edicao, metadadosEdicao } from "./Edicao";
import { PROJETOS } from "./projetos.gen";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition id="Teste" component={Teste} durationInFrames={75} fps={30} width={1080} height={1920}
        defaultProps={{ texto: "não existe perfil perfeito" }} />
      {/* usado pelo editor (editor/remotion_fx.py): props definem tipo, tamanho e duração */}
      <Composition id="Elemento" component={Elemento} calculateMetadata={metadados}
        durationInFrames={72} fps={30} width={1080} height={1920} defaultProps={padrao} />
      {/* a edição completa de cada vídeo (gerada por editor/projeto.py) — abra no Studio para ver/editar */}
      {PROJETOS.map((pr) => (
        <Composition key={pr.id} id={pr.id} component={Edicao} calculateMetadata={metadadosEdicao}
          durationInFrames={30} fps={30} width={1080} height={1920} defaultProps={pr.props} />
      ))}
      {/* usada pelo render final (render-edicao.mjs passa o projeto como inputProps) */}
      <Composition id="Edicao" component={Edicao} calculateMetadata={metadadosEdicao}
        durationInFrames={30} fps={30} width={1080} height={1920}
        defaultProps={{ nome: "", W: 1080, H: 1920, fps: 30, dur: 1, raiz: "", base: "",
          tema: { ...padrao.tema, fonte_legenda: "Inter", tamanho_legenda: 64 }, legendas: [], camadas: [] }} />
    </>
  );
};
