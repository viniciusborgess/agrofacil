# AgroFácil Visão

Este repositório traz o componente de visão computacional do **AgroFácil**, a CitizenTech da equipe na Global Solution 2026.2 da FIAP (Engenharia de Software, 4º ano), entregue na disciplina Applied Computer Vision.

O sistema detecta em tempo real folhas sadias e doentes pela câmera do celular ou por foto. Para cada folha, mostra onde está o possível problema e sugere o primeiro cuidado em linguagem simples.

- **Relatório:** [`docs/relatorio_computer_vision.pdf`](docs/relatorio_computer_vision.pdf)
- **Vídeo de demonstração:** (link do YouTube)
- **Roteiro do vídeo:** [`docs/ROTEIRO_VIDEO.md`](docs/ROTEIRO_VIDEO.md)

## Integrantes

| Nome | RM |
|---|---|
| Julia Ortiz | RM550204 |
| Julia Palomari | RM551910 |
| Leticia Baptista | RM550289 |
| Vinicius Sobreira Borges | RM97767 |

## Ficha Técnica do MVP (componente Visão)

| Campo | Conteúdo |
|---|---|
| **Produto** | AgroFácil Visão, módulo do AgroFácil |
| **Cidadão e território** | Pequeno produtor rural, muitas vezes sem assistência técnica por perto |
| **Problema** | O produtor percebe a doença na folha tarde e não sabe qual é o primeiro cuidado |
| **Proposta de valor** | Apontar o celular para a folha e saber, em segundos, se há sinal de doença, onde está e o que fazer primeiro |
| **Arquitetura** | Navegador (câmera) → API FastAPI → YOLO11n em ONNX Runtime (CPU) → regras de decisão → JSON para a plataforma |
| **Fontes de dados** | [PlantDoc](https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset) (CC BY 4.0), 20 classes de 8 culturas |
| **Modelo de IA** | YOLO11n pré-treinado no COCO, com treinamento customizado (detecção de objetos) |
| **Indicadores** | mAP@50 no teste, % de folhas doentes sinalizadas, % de doentes ditas saudáveis, tempo por imagem (`docs/results/metrics.json`) |
| **ODS** | 2 (Fome zero e agricultura sustentável), 9 (Inovação), 10 (Redução das desigualdades), 13 (Ação climática) |

## Culturas e classes

| Cultura | O que o modelo reconhece |
|---|---|
| Tomate | sadia, pinta-preta, septoriose, mancha-bacteriana, requeima, mosaico, enrolamento-amarelo, mofo-das-folhas |
| Milho | cercosporiose, helmintosporiose, ferrugem |
| Batata | pinta-preta, requeima |
| Pimentão | sadia, mancha-bacteriana |
| Abóbora | oídio |
| Uva | sadia, podridão-negra |
| Soja, morango | sadia |

Pragas não estão cobertas: o dataset tem só 2 imagens da única praga anotada.

## Como rodar a demo

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt
scripts/run_demo.sh          # abra http://localhost:8000
```

Com Docker:

```bash
docker build -t agrofacil-visao .
docker run -p 8000:8000 agrofacil-visao
```

## API

`POST /v1/detections` recebe `multipart/form-data` com o campo `imagem` (até 8 MB):

```json
{
  "id": "6f1c...",
  "modelo": "yolo11n-plantdoc20-v1",
  "status": "possivel_doenca",
  "mensagem": "Encontramos sinais de uma possível doença.",
  "deteccoes": [{
    "classe": "Tomato leaf late blight",
    "cultura": "Tomate",
    "condicao": "Requeima",
    "tipo": "doenca",
    "confianca": 0.87,
    "confiavel": true,
    "caixa": {"x1": 0.12, "y1": 0.08, "x2": 0.71, "y2": 0.93},
    "orientacao": "A requeima avança rápido em tempo frio e úmido..."
  }],
  "revisao_humana_recomendada": true,
  "aviso": "Este resultado é uma sugestão e pode estar errado...",
  "inferencia_ms": 41.3
}
```

- **`status`:** `possivel_doenca`, `folha_saudavel`, `inconclusivo` (pede outra foto) ou `nada_detectado`.
- **Caixas:** normalizadas entre 0 e 1.
- **Outras rotas:** `GET /health` e `GET /v1/classes`.

## Reproduzir o treino e a avaliação

```bash
uv pip install --python .venv/bin/python -r requirements-train.txt
scripts/download_data.sh                      # PlantDoc, no commit registrado em docs/data_report.json
.venv/bin/python scripts/prepare_data.py      # valida, deduplica e separa os dados
.venv/bin/python scripts/train.py             # Apple Silicon; em GPU: --device 0
.venv/bin/python scripts/evaluate.py          # calibra, testa, exporta para ONNX
.venv/bin/python -m pytest tests              # testes da API
.venv/bin/python scripts/build_report.py      # gera o PDF
```

Para gerar o vídeo automático: `scripts/select_samples.py`, depois `scripts/record_demo.py` e por fim `scripts/build_video.py`.

## Estrutura

```
api/        API FastAPI, inferência ONNX e textos para o produtor
web/        demo no navegador (câmera e envio de foto)
scripts/    dados, treino, avaliação, vídeo e relatório
tests/      testes do contrato da API, segurança e LGPD
weights/    modelo final (ONNX e PyTorch) e metadados
docs/       relatório, métricas, figuras e roteiro do vídeo
```

## Segurança, LGPD e IA responsável

- **Fotos:** processadas em memória e descartadas. Nada é gravado em disco.
- **Logs:** sem imagem nem nome de arquivo.
- **Decisão:** só afirma algo acima do limiar calibrado na validação. Abaixo dele, pede outra foto.
- **Confirmação humana:** toda resposta recomenda confirmar com agrônomo ou ATER. Não indicamos produtos químicos.
- **Limitações medidas** (no relatório): desempenho com fotos degradadas, respostas para culturas desconhecidas e imagens sem planta, e viés dos dados, que não vêm de lavouras brasileiras.

## Licenças

- **Dados:** PlantDoc, de Singh et al. (2020), sob CC BY 4.0.
- **Treinamento:** Ultralytics YOLO, sob AGPL-3.0. Por isso, este repositório deve permanecer público.
