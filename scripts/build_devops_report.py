"""Gera o PDF da disciplina Secure DevOps Tools & Cloud Computing (Deploy Blindado).

Usa as evidências de scripts/devops_evidence.py e os preços oficiais da API de varejo do Azure.

Uso: python scripts/build_devops_report.py
"""
import json
import subprocess
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from build_report import BODY, CELL, H1, H2, INK_2, SMALL, TITLE, figure, table

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "docs/devops/evidencias"
OUT = ROOT / "docs/devops/relatorio_devops.pdf"
REPO_URL = "https://github.com/viniciusborgess/agrofacil"
REGION = "brazilsouth"
MONTH_S = 30 * 24 * 3600


def terraform_output(name):
    return subprocess.run(["terraform", "-chdir=infra", "output", "-raw", name], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def prices():
    """Preços de varejo em USD para a região, direto da API oficial do Azure."""
    cache = ROOT / "docs/devops/precos_azure.json"
    queries = {
        "aca": f"serviceName eq 'Azure Container Apps' and armRegionName eq '{REGION}' and skuName eq 'Standard'",
        "acr": f"serviceName eq 'Container Registry' and armRegionName eq '{REGION}' and skuName eq 'Basic'",
        "log": f"serviceName eq 'Log Analytics' and armRegionName eq '{REGION}' and skuName eq 'Analytics Logs'",
    }
    items = []
    for f in queries.values():
        url = "https://prices.azure.com/api/retail/prices?" + urllib.parse.urlencode({"$filter": f})
        items += json.load(urllib.request.urlopen(url, timeout=30))["Items"]
    meters = {i["meterName"]: i["retailPrice"] for i in items if i["tierMinimumUnits"] == 0 or "Ingestion" not in i["meterName"]}
    data = {"consultado_em": date.today().isoformat(), "regiao": REGION, "medidores": meters}
    cache.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return meters


def cost_rows(m):
    """Uma réplica de 0,5 vCPU e 1 GiB ligada o mês todo, descontada a cota gratuita mensal do Container Apps."""
    vcpu_s, mem_s = 0.5 * MONTH_S, 1.0 * MONTH_S
    free_vcpu, free_mem = 180_000, 360_000
    idle = (vcpu_s - free_vcpu) * m["Standard vCPU Idle Usage"] + (mem_s - free_mem) * m["Standard Memory Idle Usage"]
    active = (vcpu_s - free_vcpu) * m["Standard vCPU Active Usage"] + (mem_s - free_mem) * m["Standard Memory Active Usage"]
    acr = 30 * m["Basic Registry Unit"]
    rows = [
        ["Container Apps (1 réplica, 0,5 vCPU, 1 GiB)", f"US$ {idle:.2f}", f"US$ {active:.2f}",
         "Ocioso na maior parte do tempo; o pior caso é processar sem parar o mês inteiro"],
        ["Container Registry Basic", f"US$ {acr:.2f}", f"US$ {acr:.2f}", "Diária fixa; 10 GB incluídos"],
        ["Log Analytics", "US$ 0,00", "US$ 0,00", "Teto de 0,15 GB/dia, dentro dos 5 GB/mês gratuitos"],
        ["Storage do state do Terraform", "< US$ 0,01", "< US$ 0,01", "Um arquivo de cerca de 30 KB"],
        ["Identidades, ambiente, TLS e domínio", "US$ 0,00", "US$ 0,00", "Sem cobrança"],
    ]
    total = [f"US$ {idle + acr:.2f}".replace(".", ","), f"US$ {active + acr:.2f}".replace(".", ",")]
    for row in rows:
        row[1], row[2] = row[1].replace(".", ","), row[2].replace(".", ",")
    return rows, total


def diagram(path):
    """Desenha a arquitetura. As ligações correm pelos corredores entre as áreas, sem cruzar caixas."""
    W, H = 1800, 1100
    img = PILImage.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 26)
    reg = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 21)
    ink, muted, line = (11, 11, 11), (82, 81, 78), (120, 120, 116)
    green, blue, orange = (31, 92, 52), (42, 120, 214), (235, 104, 52)

    def zone(x1, y1, x2, y2, title, color):
        d.rounded_rectangle([x1, y1, x2, y2], 16, outline=color, width=3)
        d.text((x1 + 18, y1 + 12), title, font=bold, fill=color)

    def box(x, y, w, h, title, lines=()):
        d.rounded_rectangle([x, y, x + w, y + h], 10, fill=(248, 248, 246), outline=line, width=2)
        d.text((x + 14, y + 10), title, font=bold, fill=ink)
        for i, text in enumerate(lines):
            d.text((x + 14, y + 46 + i * 26), text, font=reg, fill=muted)

    def path_arrow(points, color=line, label=None, label_at=None):
        d.line(points, fill=color, width=4, joint="curve")
        (x1, y1), (x2, y2) = points[-2], points[-1]
        if x1 == x2:
            sign = 1 if y2 > y1 else -1
            tip = [(x2, y2), (x2 - 9, y2 - 16 * sign), (x2 + 9, y2 - 16 * sign)]
        else:
            sign = 1 if x2 > x1 else -1
            tip = [(x2, y2), (x2 - 16 * sign, y2 - 9), (x2 - 16 * sign, y2 + 9)]
        d.polygon(tip, fill=color)
        if label:
            d.text(label_at, label, font=reg, fill=color)

    zone(30, 30, 800, 560, "GitHub", ink)
    box(60, 90, 300, 110, "Repositório", ["código, Dockerfile,", "Terraform, workflow"])
    box(60, 250, 710, 280, "GitHub Actions (a cada push)")
    for i, stage in enumerate(["Gitleaks", "Semgrep", "Testes", "Trivy IaC"]):
        x = 80 + i * 170
        box(x, 305, 155, 60, stage)
        d.line([(x + 77, 365), (x + 77, 390)], fill=line, width=4)
    d.line([(157, 390), (667, 390)], fill=line, width=4)
    path_arrow([(240, 390), (240, 420)])
    box(80, 420, 320, 90, "Build + Trivy imagem", ["barra HIGH/CRITICAL"])
    box(440, 420, 310, 90, "Deploy (só main)", ["login OIDC, sem senha"])
    path_arrow([(210, 200), (210, 250)])
    path_arrow([(400, 465), (440, 465)])

    zone(920, 30, 1770, 720, "Azure · Brazil South · rg-agrofacil-prod", blue)
    box(960, 90, 360, 110, "Container Registry", ["Basic, sem usuário admin", "push: AcrPush (GitHub)"])
    box(1360, 90, 380, 110, "Identidades gerenciadas", ["app: AcrPull", "GitHub: OIDC, escopo mínimo"])
    box(960, 270, 780, 170, "Container Apps (ca-agrofacil-prod)", [
        "API FastAPI + modelo ONNX, usuário não root, 1 a 3 réplicas",
        "Ingress só HTTPS (TLS da plataforma), sem SSH nem RDP",
        "/metrics protegido por token (secret do Container App)"])
    box(960, 520, 370, 150, "Log Analytics", ["logs dos containers", "30 dias, teto 0,15 GB/dia"])
    box(1370, 520, 370, 150, "Storage (state)", ["tfstate remoto", "só Entra ID, TLS 1.2"])
    path_arrow([(1140, 200), (1140, 270)], blue, "pull", (1152, 220))
    path_arrow([(1140, 440), (1140, 520)], blue, "logs", (1152, 465))

    # Deploy: envia a imagem ao registro e atualiza a revisão do app.
    path_arrow([(750, 445), (830, 445), (830, 145), (960, 145)], blue)
    path_arrow([(750, 485), (850, 485), (850, 330), (960, 330)], blue)
    # Produtor acessa o app por HTTPS.
    box(60, 610, 340, 130, "Produtor (celular)", ["navegador, câmera", "ou envio de foto"])
    path_arrow([(400, 675), (870, 675), (870, 380), (960, 380)], green)
    # Prometheus lê /metrics do app por HTTPS com token.
    zone(30, 790, 800, 980, "Monitoramento (docker compose local)", orange)
    box(60, 850, 330, 110, "Prometheus", ["4 alertas", "coleta a cada 15 s"])
    box(450, 850, 330, 110, "Grafana", ["painel dos 4 sinais", "de ouro"])
    path_arrow([(390, 905), (450, 905)])
    path_arrow([(225, 960), (225, 1020), (890, 1020), (890, 420), (960, 420)], orange)

    box(960, 790, 780, 190, "Terraform (máquina do time)", [
        "cria tudo acima de forma declarativa; state no Storage",
        ".tfvars e state fora do git; plan revisado antes de cada apply",
        "credencial federada só para o environment production"])
    path_arrow([(1350, 790), (1350, 720)])

    legend = [(blue, "deploy: imagem e nova revisão"), (green, "uso pelo produtor (HTTPS)"), (orange, "monitoramento (HTTPS + token)")]
    x = 60
    for color, text in legend:
        d.line([(x, 1068), (x + 40, 1068)], fill=color, width=6)
        d.text((x + 50, 1056), text, font=reg, fill=muted)
        x += 60 + d.textlength(text, font=reg) + 30
    img.save(path)


def main():
    EV.mkdir(parents=True, exist_ok=True)
    team = json.loads((ROOT / "docs/integrantes.json").read_text())
    app_url = terraform_output("app_url")
    runs = json.loads((EV / "execucoes.json").read_text())
    failed, passed = runs["barrada"], runs["corrigida"]
    diagram(EV / "00_arquitetura.png")
    rows, total = cost_rows(prices())
    link = lambda url, text=None: f'<a href="{url}" color="#2a78d6">{text or url}</a>'
    loadtest = ROOT / "docs/devops/teste_de_carga.txt"

    story = [
        Spacer(1, 2.5 * cm),
        Paragraph("AgroFácil · Deploy Blindado", TITLE),
        Paragraph("Secure DevOps Tools &amp; Cloud Computing · Global Solution 2026.2 · CitizenTech", H2),
        Paragraph("Engenharia de Software · 4º ano (4ES) · FIAP", BODY),
        Paragraph("Professor: Gabriel Henrique Boyczuk Arcanjo", BODY),
        Spacer(1, 1 * cm),
        Paragraph("Integrantes", H2),
        table([["Nome completo", "RM"]] + [[t["nome"], t["rm"]] for t in team], [10 * cm, 4 * cm]),
        Spacer(1, 1 * cm),
        table([
            ["Item", "Link"],
            ["MVP publicado (URL pública)", link(app_url)],
            ["Repositório público", link(REPO_URL)],
            ["Pipeline (GitHub Actions)", link(f"{REPO_URL}/actions")],
            ["Execução barrada", link(f"{REPO_URL}/actions/runs/{failed['databaseId']}", f"run {failed['databaseId']}")],
            ["Execução corrigida", link(f"{REPO_URL}/actions/runs/{passed['databaseId']}", f"run {passed['databaseId']}")],
        ], [5 * cm, 11.4 * cm]),
        Spacer(1, 0.6 * cm),
        Paragraph(f"São Paulo, {date.today().strftime('%d/%m/%Y')}", BODY),
        PageBreak(),

        Paragraph("1. Ficha Técnica do MVP", H1),
        table([
            ["Campo", "Conteúdo"],
            ["Produto", "AgroFácil: apoio à decisão do pequeno produtor rural. Módulo publicado: AgroFácil Visão."],
            ["Cidadão e território", "Pequeno produtor rural, muitas vezes sem assistência técnica por perto."],
            ["Problema", "A doença na folha é percebida tarde, e o produtor não sabe qual é o primeiro cuidado."],
            ["Proposta de valor", "Apontar o celular para a folha e receber, em segundos, onde está o possível problema e o que fazer primeiro."],
            ["Componentes", "Navegador → API FastAPI (Container Apps) → modelo YOLO11n em ONNX; Prometheus e Grafana."],
            ["Nuvem", "Azure (Brazil South): Container Apps, Container Registry, Log Analytics, Storage, identidades gerenciadas."],
            ["Segurança", "Gitleaks, Semgrep e Trivy a cada push; OIDC sem senha; HTTPS; sem porta de administração; container não root."],
            ["URL do MVP e repositório", f"{link(app_url)}<br/>{link(REPO_URL)}"],
            ["ODS", "2 (agricultura sustentável), 9 (inovação), 10 (redução das desigualdades), 13 (ação climática)."],
        ], [4.2 * cm, 12.2 * cm]),

        Paragraph("2. Arquitetura", H1),
        figure(EV / "00_arquitetura.png", 16.4, "Figura 1. Arquitetura do deploy: o código passa por quatro barreiras de "
               "segurança antes do build, a imagem é verificada de novo e só então publicada no Azure por um login sem senha."),
        Paragraph(
            "Escolhemos o Azure Container Apps, serviço gerenciado de containers, em vez de uma máquina virtual. Não há "
            "sistema operacional para manter nem porta SSH ou RDP para proteger: o único acesso é o ingress HTTPS da "
            "plataforma. A região Brazil South mantém os dados no país e reduz a latência para o produtor.", BODY),

        Paragraph("3. Container e infraestrutura como código", H1),
        Paragraph("3.1 Dockerfile e docker compose", H2),
        ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=12) for t in [
            "Imagem <b>python:3.11-slim</b> com só as dependências de produção (sem PyTorch): FastAPI, ONNX Runtime e Pillow.",
            "Pacotes do Debian atualizados no build; <b>setuptools e wheel removidos</b> da imagem final, porque não rodam em produção.",
            "Processo roda como <b>usuário sem privilégios</b> (uid 1000), com <b>HEALTHCHECK</b>.",
            "<b>Nenhum segredo na imagem</b>: o token de métricas entra como variável de ambiente vinda de um secret da plataforma. "
            "O <b>.dockerignore</b> nega tudo e libera só o necessário.",
            "O <b>docker compose</b> sobe API, Prometheus e Grafana. A API roda com sistema de arquivos só leitura, sem "
            "capabilities e com no-new-privileges; as portas ficam presas a 127.0.0.1.",
        ]], bulletType="bullet"),
        figure(EV / "23_compose_e_usuario_nao_root.png", 16, "Figura 2. Stack local no ar com docker compose e o processo "
               "da API rodando com uid 1000, não root."),
        Paragraph("3.2 Terraform", H2),
        Paragraph(
            "Toda a nuvem é criada por Terraform (pasta infra/): grupo de recursos, registro de imagens, Log Analytics, "
            "ambiente e aplicativo do Container Apps, duas identidades gerenciadas com permissões mínimas e a credencial "
            "federada do GitHub. Cada apply foi precedido de um plan revisado; o plan atual não tem diferenças.", BODY),
        table([
            ["Exigência", "Como atendemos"],
            ["State fora do repositório", "Backend remoto no Azure Storage, com acesso só por Entra ID (sem chave compartilhada), "
             "TLS 1.2 e sem acesso público. O arquivo backend.hcl é gerado por scripts/bootstrap_state.sh e fica fora do git."],
            [".tfvars fora do repositório", "terraform.tfvars está no .gitignore; versionamos só terraform.tfvars.example."],
            ["Porta de administração nunca aberta para 0.0.0.0/0", "Não existe porta de administração: Container Apps não expõe "
             "SSH nem RDP. O único ingress é HTTPS na 443; HTTP recebe 301 para HTTPS. O registro de imagens não tem usuário admin."],
            ["Segredos", "Token de métricas como secret do Container App; no GitHub só há identificadores do OIDC, não senhas."],
        ], [5 * cm, 11.4 * cm]),
        Spacer(1, 6),
        figure(EV / "01_terraform_plan_limpo.png", 14, "Figura 3. terraform plan sem diferenças: a nuvem corresponde ao código."),
        figure(EV / "02_recursos_azure.png", 16, "Figura 4. Recursos criados pelo Terraform no grupo rg-agrofacil-prod."),
        figure(EV / "03_sem_porta_admin.png", 16, "Figura 5. Ingress só HTTPS (HTTP é redirecionado), registro sem usuário "
               "admin, /health respondendo e /metrics recusando acesso sem token."),
        figure(EV / "04_state_e_segredos_fora_do_git.png", 16, "Figura 6. tfvars, backend e segredos ignorados pelo git; o "
               "state está no Azure Storage."),

        Paragraph("4. Pipeline DevSecOps", H1),
        table([
            ["Etapa", "Ferramenta", "Barra quando"],
            ["Segredos", "Gitleaks 8.21.2 (histórico completo)", "encontra credencial em qualquer commit"],
            ["SAST", "Semgrep (p/python, p/owasp-top-ten, p/dockerfile)", "há achado de segurança no código"],
            ["Testes", "pytest (contrato da API, LGPD, limites)", "algum teste falha"],
            ["IaC", "Trivy config (Terraform e Dockerfile)", "má configuração HIGH ou CRITICAL"],
            ["Imagem", "docker build + Trivy image", "vulnerabilidade HIGH ou CRITICAL com correção"],
            ["Deploy", "azure/login (OIDC) + az containerapp update", "só roda em main, depois de tudo passar"],
            ["Verificação", "teste de fumaça em /health", "a nova versão não responde"],
        ], [2.8 * cm, 7 * cm, 6.6 * cm]),
        Spacer(1, 6),
        ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=12) for t in [
            "<b>Sem senha de nuvem no GitHub.</b> Os GitHub Secrets guardam só os identificadores do OIDC. O Azure aceita o "
            "token apenas do environment production deste repositório, identificado pelos IDs imutáveis do dono e do repositório.",
            "<b>Permissão mínima.</b> A identidade do GitHub pode enviar imagens ao registro, ler o grupo e atualizar só o app.",
            "<b>Cadeia de suprimentos.</b> Cada Action está fixada por hash de commit, e Gitleaks e Trivy são baixados com "
            "SHA-256 conferido. O modelo de IA vem de uma Release do GitHub, também conferida por SHA-256 (model.lock.json).",
        ]], bulletType="bullet"),
        figure(EV / "05_github_secrets_oidc.png", 15, "Figura 7. Secrets e variáveis do GitHub (valores ocultos) e o subject "
               "autorizado na credencial federada."),
        Paragraph("4.1 Execução barrada e execução corrigida", H2),
        Paragraph(
            f"A barreira funcionou em um caso real, não simulado. No commit {failed['headSha'][:7]}, os quatro primeiros "
            "estágios passaram, mas o Trivy encontrou na imagem vulnerabilidades HIGH e CRITICAL com correção disponível: "
            "estouro de buffer no Pillow 11.3 (CRITICAL), negação de serviço na Starlette 0.46, falhas no zlib do Debian e "
            "em setuptools e wheel herdados da imagem base. O deploy não executou.", BODY),
        figure(EV / "11_execucao_barrada.png", 15, "Figura 8. Execução barrada: o build falhou e o deploy foi pulado."),
        figure(EV / "12b_trivy_vulnerabilidades.png", 16, "Figura 9. Achados do Trivy no log da execução barrada, com as versões corrigidas."),
        Paragraph(
            "A correção atualizou Pillow para 13.0, FastAPI para 0.162 (Starlette 1.10), aplicou as atualizações do "
            "Debian no build e removeu setuptools e wheel da imagem. Na execução seguinte, todos os estágios passaram e "
            "o deploy publicou a nova versão sozinho.", BODY),
        figure(EV / "13_execucao_corrigida.png", 15, "Figura 10. Execução corrigida: todos os estágios aprovados e deploy automático."),
        Paragraph("4.2 Segundo bloqueio: Semgrep", H2),
        Paragraph(
            f"O pipeline barrou um segundo problema real. Os scripts que coletam as evidências deste relatório chamavam "
            "comandos com subprocess e shell=True, padrão que o Semgrep classifica como bloqueante por permitir injeção "
            f"de comandos. A execução {link(f'{REPO_URL}/actions/runs/42692489668', '42692489668')} parou no SAST, e o build "
            "e o deploy foram pulados. Na correção, o gerador do relatório passou a chamar o Terraform sem shell. O coletor "
            "de evidências, que roda só na máquina do time e com comandos fixos no código, recebeu uma exceção explícita "
            f"e justificada no próprio código. A execução {link(f'{REPO_URL}/actions/runs/42692692285', '42692692285')} "
            "passou em todos os estágios e publicou o modelo final.", BODY),
        figure(EV / "12c_semgrep_barrou.png", 14, "Figura 10b. Execução barrada pelo Semgrep: os achados bloqueantes impediram build e deploy."),
        figure(EV / "10_actions_historico.png", 15, "Figura 11. Histórico do pipeline."),
        figure(EV / "14_mvp_publicado.png", 15, f"Figura 12. MVP em uso na URL pública ({app_url})."),

        Paragraph("5. Observabilidade", H1),
        Paragraph(
            "A API expõe métricas no formato do Prometheus em /metrics, protegido por token. O Prometheus roda localmente "
            "com docker compose e lê, por HTTPS, a API publicada no Azure, como a disciplina permite. O Grafana mostra os "
            "quatro sinais de ouro, e o Prometheus avalia quatro regras de alerta.", BODY),
        table([
            ["Sinal de ouro", "Métrica", "Alerta"],
            ["Latência", "http_request_duration_seconds (p50 e p95)", "p95 da detecção acima de 1 s por 2 min"],
            ["Tráfego", "http_requests_total (req/s por rota)", "-"],
            ["Erros", "http_requests_total com status 5xx e 4xx", "mais de 5% de 5xx por 1 min"],
            ["Saturação", "inference_slots_in_use / inference_slots_max e recusas 503", "mais de 0,5 recusa/s por 1 min"],
            ["Disponibilidade", "up", "API fora do ar por 1 min"],
        ], [3 * cm, 7.2 * cm, 6.2 * cm]),
        Spacer(1, 6),
        figure(EV / "20_grafana_sinais_de_ouro.png", 16.4, "Figura 13. Painel do Grafana com os quatro sinais de ouro do MVP no Azure, durante o teste de carga."),
        figure(EV / "21_prometheus_alerta_disparado.png", 16.4, "Figura 14. Alerta disparado no Prometheus durante o teste de carga."),
        figure(EV / "22_prometheus_alvos.png", 16.4, "Figura 15. Alvos monitorados: API local e API no Azure."),
    ]
    if loadtest.exists():
        story.append(Paragraph(f"Teste de carga (scripts/load_test.py): {loadtest.read_text().strip().replace(chr(10), '; ')}.", SMALL))

    story += [
        Paragraph("6. Responsabilidade compartilhada", H1),
        table([
            ["Camada", "Azure", "Equipe AgroFácil"],
            ["Data center, rede física, hardware", "Sim", "-"],
            ["Sistema operacional dos hosts e orquestração (Container Apps)", "Sim", "-"],
            ["TLS, certificado e balanceamento do ingress", "Sim", "Exigir só HTTPS (configurado)"],
            ["Imagem do container (base, bibliotecas)", "-", "Sim: Trivy a cada push e atualização das dependências"],
            ["Código da aplicação", "-", "Sim: Semgrep, testes e revisão"],
            ["Identidade e acesso (IAM)", "Fornece Entra ID e RBAC", "Sim: OIDC, identidades com permissão mínima"],
            ["Segredos", "Fornece secrets do Container App", "Sim: nada no código, na imagem ou no git"],
            ["Dados pessoais (LGPD)", "Infraestrutura certificada", "Sim: minimização, retenção e transparência"],
            ["Monitoramento e resposta", "Fornece métricas e logs da plataforma", "Sim: painel, alertas e ação"],
        ], [6.4 * cm, 4.6 * cm, 5.4 * cm]),

        Paragraph("7. Onde ficam os dados pessoais (LGPD)", H1),
        table([
            ["Dado", "Onde fica", "Tratamento"],
            ["Foto da folha", "Só na memória do container, durante a análise", "Descartada em seguida; nunca gravada em disco (teste automatizado)"],
            ["Endereço IP do usuário", "Logs de acesso da plataforma no Log Analytics", "Retenção de 30 dias; acesso só da equipe via RBAC"],
            ["Logs da aplicação", "Log Analytics (Brazil South)", "Só status, quantidade de detecções e tempo; sem imagem nem nome de arquivo"],
            ["Métricas", "Prometheus local", "Agregadas, sem identificação de pessoa"],
            ["Segredos e state", "Secrets do Container App e Storage", "Criptografados em repouso pela plataforma; fora do git"],
        ], [3.4 * cm, 5.6 * cm, 7.4 * cm]),
        Paragraph("Todos os recursos estão em Brazil South, então os dados não saem do país. O app informa ao usuário que a "
                  "foto é analisada e descartada.", BODY),

        Paragraph("8. Estimativa de custo mensal", H1),
        table([["Recurso", "Uso esperado", "Pior caso", "Premissa"]] + rows + [["Total", total[0], total[1], ""]],
              [5 * cm, 2.6 * cm, 2.6 * cm, 6.2 * cm]),
        Paragraph(f"Preços de varejo do Azure em USD para {REGION}, consultados na API oficial (prices.azure.com) em "
                  f"{date.today().strftime('%d/%m/%Y')}, e salvos em docs/devops/precos_azure.json. A cota gratuita mensal do "
                  "Container Apps (180 mil vCPU-s e 360 mil GiB-s) foi descontada. Com min_replicas = 0 o app custaria perto "
                  "de zero, ao preço de alguns segundos de espera na primeira requisição; mantivemos 1 réplica para a "
                  "correção. O custo sai dos créditos do Azure for Students.", SMALL),

        Paragraph("9. Como reproduzir", H1),
        ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=12) for t in [
            "<b>scripts/bootstrap_state.sh</b>: cria o Storage do state e o infra/backend.hcl.",
            "Copie infra/terraform.tfvars.example para infra/terraform.tfvars e preencha; depois "
            "<b>terraform -chdir=infra init -backend-config=backend.hcl</b> e <b>plan</b>/<b>apply</b> (primeiro sem image_tag).",
            "Cadastre no GitHub os secrets AZURE_CLIENT_ID, AZURE_TENANT_ID e AZURE_SUBSCRIPTION_ID e as variáveis ACR_NAME, "
            "RESOURCE_GROUP e CONTAINER_APP (valores nas saídas do Terraform).",
            "Faça push em main: o pipeline envia a imagem. No primeiro deploy, rode o apply com image_tag igual ao commit para criar o app.",
            "Monitoramento: <b>scripts/monitoring_setup.sh</b> e <b>docker compose up -d</b>; painel em http://localhost:3000.",
        ]], bulletType="1"),
        Paragraph("O passo a passo completo está no README do repositório.", BODY),
    ]

    def footer(canvas, doc):
        canvas.setFont("Arial", 8)
        canvas.setFillColor(colors.HexColor(INK_2))
        canvas.drawString(2 * cm, 1.2 * cm, "AgroFácil · Deploy Blindado · FIAP GS 2026.2")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))

    SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                      title="AgroFácil · Deploy Blindado", author=", ".join(t["nome"] for t in team)
                      ).build(story, onFirstPage=footer, onLaterPages=footer)
    print("relatório:", OUT)


if __name__ == "__main__":
    main()
