# Roteiro do vídeo: Applied Computer Vision

Vale até 5 pontos: "vídeo de demonstração da solução funcionando". A cena da câmera ao vivo é a parte mais importante.

- **Duração-alvo:** de 3 a 4 minutos.
- **Formato:** tela do notebook gravada, com a voz de um integrante. Se der, mostre o rosto do grupo na abertura.
- **Números:** já preenchidos com os resultados finais (`docs/results/metrics.json`).

## Antes de gravar

1. Abra a URL pública no Chrome: <https://ca-agrofacil-prod.whitewave-37b28008.brazilsouth.azurecontainerapps.io>. Ela já roda o modelo final e mostra que o sistema está publicado. Alternativa local: `scripts/run_demo.sh` e <http://localhost:8000>.
2. Clique em "Ligar câmera" e permita o acesso.
3. Separe o material:
   - **Fotos de folhas na tela de outro aparelho** (mais garantido): o modelo aprendeu com fotos da internet, então reconhece melhor fotos parecidas.
   - **Folhas de verdade**: tomate, milho, pimentão, batata, abóbora, uva. Podem dar "não temos certeza"; se acontecer, explique que o sistema não chuta.
   - **Fotos de folhas doentes** em outro celular ou impressas. Use as de `assets/samples/` (são do conjunto de teste, que o modelo nunca viu no treino).
4. Ilumine bem e deixe o fundo neutro. A folha deve ocupar boa parte do quadro.
5. Grave a tela com QuickTime (Arquivo > Nova Gravação de Tela) ou OBS, com o microfone ligado.
6. Os slides prontos estão em `assets/video_build/s_*.png`. Abra em tela cheia para as partes de explicação.

## Cenas

### 1. Abertura (0:00 a 0:20) · slide `s_titulo.png` ou o grupo na câmera
> "Olá, somos Julia Ortiz, Julia Palomari, Leticia Baptista e Vinicius Borges. Este é o AgroFácil Visão, o componente de visão computacional do AgroFácil."

### 2. Problema (0:20 a 0:45) · slide `s_problema.png`
> "Quando aparece uma mancha na folha, o pequeno produtor nem sempre tem um técnico por perto, e algumas doenças, como a requeima, avançam em poucos dias. Nosso sistema aponta, pela câmera do celular, onde está o possível problema e qual é o primeiro cuidado."

### 3. Como funciona (0:45 a 1:15) · slides `s_fluxo.png` e `s_treino.png`
> "A imagem vai do navegador para uma API que não guarda nenhuma foto. Lá, um detector YOLO11n, que treinamos com o dataset aberto PlantDoc em vinte classes de oito culturas, encontra as folhas e classifica cada uma. Antes de treinar, auditamos os dados e removemos 59 duplicatas, inclusive imagens que estavam no treino e no teste ao mesmo tempo."

### 4. Demonstração ao vivo (1:15 a 2:15) · navegador com a câmera · **cena principal**
- Aponte para a folha doente e espere a caixa vermelha aparecer. Mova devagar e mostre que a caixa acompanha a folha.
- Leia a taxa embaixo do vídeo ("X análises por segundo"). Pela URL pública o número inclui a internet, então fica menor que no notebook; no teste, o modelo sozinho fez cerca de 27 imagens por segundo em CPU.
- Mostre a folha sadia (caixa verde).
- Mostre algo que não é folha, como a mão ou uma caneca, e deixe o sistema não detectar nada.

> "Aqui está ao vivo. A caixa vermelha mostra a folha com possível doença, e ao lado aparece a orientação em linguagem simples. Ele faz várias análises por segundo, rodando só em processador, sem placa de vídeo. Em uma folha sadia, a caixa fica verde. E, quando não há folha, ele não inventa resposta."

### 5. Envio de foto e incerteza (2:15 a 2:45)
- Desligue a câmera, clique em "Enviar foto" e escolha `assets/samples/upload_doenca.jpg`.
- Depois envie `upload_foto_ruim.jpg`.

> "Sem internet boa para vídeo, o produtor pode mandar uma foto. Se a foto estiver ruim, o sistema não arrisca e pede outra. Todo resultado vem com o aviso para confirmar com a assistência técnica."

### 6. Resultados e limites (2:45 a 3:30) · slides `s_resultados.png` e `s_limites.png`
> "No conjunto de teste, separado desde o início, o modelo chegou a 0,62 de mAP a cinquenta, e sinalizou 89,6% das folhas doentes. Só 4% das doentes foram chamadas de saudáveis. Também medimos os limites: fotos ruins reduzem a qualidade, e o modelo ainda não cobre pragas, porque o dataset quase não tem exemplos. O próximo passo é validar com fotos de lavouras brasileiras e com um agrônomo."

### 7. Encerramento (3:30 a 3:45) · slide `s_fim.png`
> "Esse é o AgroFácil Visão: detecção em tempo real, integrada por API ao AgroFácil, medida com honestidade. Obrigado."

## Dicas

- **Mostrar a falha:** se o modelo errar ao vivo, não corte. Diga: "aqui ele errou, por isso o resultado é uma sugestão". Isso conta a favor na parte de IA responsável.
- **Celular em vez de notebook:** a URL pública tem HTTPS, então a câmera também funciona no celular.
- **Vídeo pronto como reserva:** `assets/agrofacil_visao_demo.mp4` é a versão gerada automaticamente. Trechos dele podem ser usados na edição.
- **Antes de enviar:** publique no YouTube como não listado e teste o link em uma janela anônima.
