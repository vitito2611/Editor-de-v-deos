import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { Teste } from "./Teste";
import { Elemento, metadados, padrao } from "./Elemento";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition id="Teste" component={Teste} durationInFrames={75} fps={30} width={1080} height={1920}
        defaultProps={{ texto: "não existe perfil perfeito" }} />
      {/* usado pelo editor (editor/remotion_fx.py): props definem tipo, tamanho e duração */}
      <Composition id="Elemento" component={Elemento} calculateMetadata={metadados}
        durationInFrames={72} fps={30} width={1080} height={1920} defaultProps={padrao} />
    </>
  );
};
