# AgroFácil Visão

Este repositório traz o componente de visão computacional do **AgroFácil**, a CitizenTech da equipe na Global Solution 2026.2 da FIAP (Engenharia de Software, 4º ano), entregue na disciplina Applied Computer Vision.

O sistema detecta em tempo real folhas sadias e doentes pela câmera do celular ou por foto. Para cada folha, mostra onde está o possível problema e sugere o primeiro cuidado em linguagem simples.

- **MVP no ar:** <https://ca-agrofacil-prod.whitewave-37b28008.brazilsouth.azurecontainerapps.io>
- **Relatório de Computer Vision:** [`docs/relatorio_computer_vision.pdf`](docs/relatorio_computer_vision.pdf)
- **Relatório de DevOps (Deploy Blindado):** [`docs/devops/relatorio_devops.pdf`](docs/devops/relatorio_devops.pdf)
- **Vídeo de demonstração:** (link do YouTube)

## Integrantes

| Nome | RM |
|---|---|
| Vinicius Sobreira Borges | RM97767 |
| Julia Ortiz | RM550204 |
| Julia Palomari | RM551910 |
| Leticia Baptista | RM550289 |


## Ficha Técnica do MVP

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
| **Nuvem** | Azure, região Brazil South: Container Apps, Container Registry, Log Analytics, Storage (state do Terraform) e identidades gerenciadas |
| **URL pública** | <https://ca-agrofacil-prod.whitewave-37b28008.brazilsouth.azurecontainerapps.io> |
| **Segurança** | Gitleaks, Semgrep e Trivy a cada push; login no Azure por OIDC, sem senha; só HTTPS; container sem root; nenhuma porta de administração aberta |
| **Observabilidade** | Prometheus e Grafana (4 sinais de ouro) e 4 regras de alerta |
| **Custo estimado** | Cerca de US$ 15 por mês no uso esperado e US$ 38 no pior caso (detalhes no relatório de DevOps) |
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
scripts/fetch_model.sh       # baixa o modelo da Release e confere o SHA-256
scripts/run_demo.sh          # abra http://localhost:8000
```

Com Docker:

```bash
scripts/fetch_model.sh
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

## Deploy blindado (DevOps e nuvem)

| Exigência | Onde está |
|---|---|
| Container enxuto, não root, sem segredo | [`Dockerfile`](Dockerfile), [`.dockerignore`](.dockerignore) |
| Stack com docker compose | [`docker-compose.yml`](docker-compose.yml): API, Prometheus e Grafana |
| Nuvem por Terraform, state e `.tfvars` fora do repositório | [`infra/`](infra/), state no Azure Storage ([`scripts/bootstrap_state.sh`](scripts/bootstrap_state.sh)) |
| Sem porta de administração aberta | Azure Container Apps: só HTTPS na 443, sem SSH nem RDP |
| Pipeline com build, Gitleaks, Semgrep e Trivy a cada push | [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml) |
| Segredos no GitHub Secrets e deploy automático | Login no Azure por OIDC, sem senha; deploy em `main` com teste de fumaça |
| Observabilidade com 4 sinais de ouro e alerta | [`monitoring/`](monitoring/): painel do Grafana e regras do Prometheus |

O modelo de IA é publicado como Release do GitHub e conferido por SHA-256 ([`model.lock.json`](model.lock.json), [`scripts/fetch_model.sh`](scripts/fetch_model.sh)).

### Subir a infraestrutura

```bash
az login
scripts/bootstrap_state.sh brazilsouth                 # Storage do state remoto
cp infra/terraform.tfvars.example infra/terraform.tfvars   # preencha (fica fora do git)
terraform -chdir=infra init -backend-config=backend.hcl
terraform -chdir=infra plan -out=tfplan && terraform -chdir=infra apply tfplan
```

1. Cadastre no GitHub os secrets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` e `AZURE_SUBSCRIPTION_ID`, e as variáveis `ACR_NAME`, `RESOURCE_GROUP` e `CONTAINER_APP`. Os valores saem do `terraform output`.
2. Faça um push em `main`. O pipeline envia a imagem ao registro.
3. No primeiro deploy, rode o `apply` com `image_tag` igual ao SHA do commit para criar o app. Daí em diante, o pipeline publica sozinho.

### Monitoramento

```bash
scripts/monitoring_setup.sh      # token de métricas e alvo do Azure (fora do git)
docker compose up -d             # Grafana em http://localhost:3000, Prometheus em http://localhost:9090
.venv/bin/python scripts/load_test.py --url <URL do app> --concurrency 24 --seconds 240   # dispara o alerta de saturação
```

## Reproduzir o treino e a avaliação

```bash
uv pip install --python .venv/bin/python -r requirements-train.txt
scripts/download_data.sh                      # PlantDoc, no commit registrado em docs/data_report.json
.venv/bin/python scripts/prepare_data.py      # valida, deduplica e separa os dados
.venv/bin/python scripts/train.py --device 0 --batch 16   # GPU NVIDIA (usamos o Colab: scripts/package_colab.py)
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
infra/      Terraform da nuvem (Azure)
monitoring/ Prometheus, alertas e painel do Grafana
weights/    modelo baixado da Release (fora do git)
docs/       relatórios, métricas e figuras
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
