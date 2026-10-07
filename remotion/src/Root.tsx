import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { Teste } from "./Teste";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition id="Teste" component={Teste} durationInFrames={75} fps={30} width={1080} height={1920}
        defaultProps={{ texto: "não existe perfil perfeito" }} />
    </>
  );
};
