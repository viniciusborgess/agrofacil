"""Gera o relatório em PDF exigido pela disciplina, com os números reais da avaliação.

Seções: título, integrantes, resumo (até 250 palavras), introdução, objetivo (até 50
palavras), ferramentas, metodologia, resultados e conclusão.

Uso: python scripts/build_report.py --repo-url https://github.com/<conta>/agrofacil-vision
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_JUSTIFY  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,  # noqa: E402
                                SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs/figures"
SERIES_1, SERIES_2 = "#2a78d6", "#eb6834"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BRAND = colors.HexColor("#1f5c34")

pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
BODY = ParagraphStyle("body", fontName="Arial", fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=7)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor(INK_2), alignment=0)
H1 = ParagraphStyle("h1", fontName="Arial-Bold", fontSize=15, leading=20, textColor=BRAND, spaceBefore=10, spaceAfter=8, keepWithNext=1)
H2 = ParagraphStyle("h2", fontName="Arial-Bold", fontSize=12, leading=16, spaceBefore=8, spaceAfter=5, keepWithNext=1)
TITLE = ParagraphStyle("title", fontName="Arial-Bold", fontSize=24, leading=30, textColor=BRAND, spaceAfter=12)
CELL = ParagraphStyle("cell", fontName="Arial", fontSize=8.5, leading=11)
CELL_B = ParagraphStyle("cellb", parent=CELL, fontName="Arial-Bold")


def num(value, digits=3):
    return f"{value:.{digits}f}".replace(".", ",")


def pct(value, digits=1):
    return "n/d" if value is None else f"{value * 100:.{digits}f}%".replace(".", ",")


def ci(rate):
    low, high = rate["ic95"]
    if low is None:
        return "n/d"
    return f"{pct(rate['valor'])} (IC95% {pct(low)} a {pct(high)}; n={rate['n']})"


def words(text):
    return len(text.split())


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), CELL_B if header and i == 0 else CELL) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ea") if header else colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9cfc3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def figure(path, width_cm, caption):
    if not Path(path).exists():
        return Paragraph(f"[figura ausente: {Path(path).name}]", SMALL)
    reader = Image(str(path))
    ratio = reader.imageHeight / reader.imageWidth
    return KeepTogether([Image(str(path), width=width_cm * cm, height=width_cm * cm * ratio), Spacer(1, 3),
                         Paragraph(caption, SMALL), Spacer(1, 8)])


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def chart_training(results_csv, out):
    rows = list(csv.DictReader(results_csv.open()))
    rows = [{k.strip(): v for k, v in r.items()} for r in rows]
    epochs = [int(r["epoch"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=200)
    for key, label, color in (("metrics/mAP50(B)", "mAP@50", SERIES_1), ("metrics/mAP50-95(B)", "mAP@50-95", SERIES_2)):
        values = [float(r[key]) for r in rows]
        ax.plot(epochs, values, color=color, linewidth=2, label=label)
        ax.annotate(f"{label}: {num(values[-1], 2)}", (epochs[-1], values[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8.5, color=INK)
    style_axes(ax)
    ax.set_xlabel("Época", color=INK_2, fontsize=9)
    ax.set_ylabel("Validação", color=INK_2, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_xlim(1, epochs[-1] + max(4, len(epochs) * 0.25))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def chart_bars(labels, values, out, xlabel, fmt):
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(labels) + 0.8), dpi=200)
    y = range(len(labels))
    ax.barh(list(y), values, color=SERIES_1, height=0.66)
    for i, v in zip(y, values):
        ax.text(v, i, f"  {fmt(v)}", va="center", fontsize=8, color=INK)
    ax.set_yticks(list(y), labels, fontsize=8.5, color=INK)
    ax.invert_yaxis()
    style_axes(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.set_xlim(0, max(values) * 1.18)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, default=ROOT / "docs/results/metrics.json")
    ap.add_argument("--results-csv", type=Path, default=ROOT / "runs/agrofacil_yolo11n_480/results.csv")
    ap.add_argument("--build", type=Path, default=ROOT / "assets/video_build")
    ap.add_argument("--repo-url", default="(link do repositório)")
    ap.add_argument("--video-url", default="(link do vídeo)")
    ap.add_argument("--out", type=Path, default=ROOT / "docs/relatorio_computer_vision.pdf")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)

    m = json.loads(args.metrics.read_text())
    data = json.loads((ROOT / "docs/data_report.json").read_text())
    team = json.loads((ROOT / "docs/integrantes.json").read_text())
    test, p, rob, lat = m["teste"], m["produto"], m["robustez_map50"], m["latencia"]
    oos, nonplant = m["culturas_fora_do_escopo"], m["imagens_sem_planta"]
    tr, va, te, cnt = data["train"], data["val"], data["test"], data["contagens"]
    cpu2 = lat["ONNX CPU, 2 thread(s)"]
    epochs_run = sum(1 for _ in args.results_csv.open()) - 1
    samples = json.loads((ROOT / "assets/samples/manifest.json").read_text())["uploads"]

    chart_training(args.results_csv, FIG / "treino.png")
    per_class = sorted(tr["por_classe"].items(), key=lambda kv: -kv[1]["caixas"])
    chart_bars([k for k, _ in per_class], [v["caixas"] for _, v in per_class], FIG / "classes.png",
               "Caixas anotadas no treino", lambda v: str(int(v)))
    chart_bars(list(rob), list(rob.values()), FIG / "robustez.png", "mAP@50 no teste", lambda v: num(v, 2))

    resumo = (
        "Pequenos produtores rurais costumam perceber doenças nas folhas tarde, muitas vezes sem assistência técnica "
        "por perto, o que atrasa o manejo e aumenta perdas. Este trabalho apresenta o AgroFácil Visão, componente de "
        "visão computacional da plataforma AgroFácil, que detecta e localiza em tempo real folhas sadias e doentes de "
        "oito culturas, a partir da câmera do celular ou de uma foto. Treinamos de forma customizada um detector YOLO11n, "
        "pré-treinado no COCO, com o dataset aberto PlantDoc, restrito a 20 classes. Antes do treino, auditamos os "
        f"dados: removemos {cnt['imagens removidas por duplicidade']} duplicatas, inclusive "
        f"{cnt['grupos com vazamento treino/teste']} casos de vazamento entre treino e teste, e descartamos anotações "
        "incompatíveis. O limiar de decisão foi calibrado apenas na validação, e o teste foi usado uma única vez. "
        f"No conjunto de teste, com {te['imagens']} imagens, o modelo obteve mAP@50 de {num(test['map50'])} e "
        f"mAP@50-95 de {num(test['map50_95'])}. Na decisão entregue ao produtor, sinalizou "
        f"{pct(p['doente_sinalizada']['valor'])} das folhas doentes e chamou de saudáveis "
        f"{pct(p['doente_dita_saudavel']['valor'])} delas. Exportado para ONNX, processa cerca de "
        f"{round(cpu2['fps'])} imagens por segundo em CPU, sem placa de vídeo. Também medimos o comportamento fora do "
        "cenário ideal, com fotos degradadas, culturas desconhecidas e imagens sem planta. A solução é servida por uma "
        "API que não armazena imagens, devolve orientações em linguagem simples e recomenda confirmação humana. Os "
        "resultados mostram viabilidade como ferramenta de triagem, não de diagnóstico, sobretudo porque os dados não "
        "vêm de lavouras brasileiras e quase não contêm pragas. O código, os dados de avaliação e as instruções para "
        "reproduzir tudo estão no repositório público do projeto."
    )
    objetivo = (
        "Treinar de forma customizada um detector de objetos YOLO11n que localize e classifique, em tempo real e em "
        "CPU comum, folhas sadias e doentes de oito culturas da agricultura familiar, integrá-lo à plataforma AgroFácil "
        "por meio de uma API segura e medir com rigor seu desempenho e seus limites."
    )
    assert 235 <= words(resumo) <= 250, f"resumo com {words(resumo)} palavras"
    assert 45 <= words(objetivo) <= 50, f"objetivo com {words(objetivo)} palavras"

    story = [
        Spacer(1, 3 * cm),
        Paragraph("AgroFácil Visão: detecção em tempo real de doenças em folhas para o pequeno produtor", TITLE),
        Paragraph("Applied Computer Vision · Global Solution 2026.2 · Desafio CitizenTech", H2),
        Paragraph("Engenharia de Software · 4º ano (4ES) · FIAP", BODY),
        Paragraph("Professores: Arnaldo Viana e Paulo Rodrigues", BODY),
        Spacer(1, 1.2 * cm),
        Paragraph("Integrantes", H2),
        table([["Nome completo", "RM"]] + [[t["nome"], t["rm"]] for t in team], [10 * cm, 4 * cm]),
        Spacer(1, 1.2 * cm),
        Paragraph(f"Repositório: {args.repo_url}", BODY),
        Paragraph(f"Vídeo de demonstração: {args.video_url}", BODY),
        Paragraph(f"São Paulo, {date.today().strftime('%d/%m/%Y')}", BODY),
        PageBreak(),

        Paragraph("Resumo", H1),
        Paragraph(resumo, BODY),
        Paragraph(f"<i>{words(resumo)} palavras.</i>", SMALL),

        Paragraph("1. Introdução", H1),
        Paragraph(
            "O AgroFácil é a CitizenTech da equipe: uma plataforma que ajuda pequenos produtores rurais a decidir sobre "
            "irrigação, plantio e cuidados com a lavoura usando dados climáticos e inteligência artificial. Uma das "
            "funcionalidades previstas é identificar problemas na plantação por imagem. Este relatório documenta esse "
            "componente, chamado AgroFácil Visão.", BODY),
        Paragraph(
            "O produtor costuma notar uma mancha na folha antes de ter acesso a quem saiba interpretá-la. Algumas "
            "doenças, como a requeima do tomate e da batata, avançam em poucos dias em clima frio e úmido, e a demora "
            "no primeiro cuidado pesa no resultado da safra. Um celular comum, apontado para a folha, pode reduzir essa "
            "espera: o sistema indica onde está o possível problema, sugere o primeiro manejo em linguagem simples e "
            "recomenda confirmar com um agrônomo ou com a assistência técnica (ATER).", BODY),
        Paragraph(
            "A disciplina pede detecção de objetos em tempo real com treinamento customizado. Escolhemos detecção, e "
            "não apenas classificação da imagem inteira, porque uma foto de campo mostra várias folhas, fundo e solo: "
            "a caixa mostra ao produtor qual folha motivou o alerta, o que torna o resultado verificável.", BODY),

        Paragraph("2. Objetivo", H1),
        Paragraph(objetivo, BODY),
        Paragraph(f"<i>{words(objetivo)} palavras.</i>", SMALL),

        Paragraph("3. Explicação técnica das ferramentas", H1),
        table([
            ["Ferramenta", "Papel no projeto", "Por que foi escolhida"],
            ["PlantDoc (CC BY 4.0)", "Dataset de 2.598 fotos reais de folhas, anotadas com caixas, em 13 espécies.",
             "É um dos poucos datasets abertos de detecção com fotos fora do laboratório."],
            ["YOLO11n (Ultralytics)", "Arquitetura de detecção de um estágio: backbone convolucional, pescoço com fusão de "
             "escalas e cabeça sem âncoras, que prevê caixa e classe para cada célula.",
             "É o menor modelo da família (2,6 milhões de parâmetros), adequado a CPU e celulares de entrada."],
            ["Transfer learning (COCO)", "Pesos pré-treinados em 80 classes gerais, ajustados para as 20 classes do projeto.",
             "Com cerca de 1.400 imagens de treino, partir do zero não convergiria bem."],
            ["PyTorch + CUDA (Google Colab)", "Treino em uma GPU NVIDIA T4 gratuita do Google Colab.",
             "No notebook da equipe (Apple M1, 8 GB) cada época levava cerca de 17 minutos; na T4, as 40 épocas levaram cerca de 13."],
            ["ONNX + ONNX Runtime", "Modelo exportado e executado em CPU, com pré e pós-processamento (letterbox e NMS) "
             "próprios em NumPy.", "Imagem de produção sem PyTorch, menor e mais barata de hospedar."],
            ["FastAPI", "API com POST /v1/detections, que devolve JSON com caixas, rótulos e orientação.",
             "Contrato claro para a plataforma AgroFácil e documentação automática."],
            ["Navegador (getUserMedia)", "Demonstração com a câmera: envia quadros de 480 px e desenha as caixas.",
             "Funciona no celular sem instalar aplicativo."],
            ["imagehash (pHash)", "Encontra fotos quase idênticas entre treino e teste.", "Evita resultados inflados por vazamento."],
            ["Docker", "Empacota a API com usuário sem privilégios.", "Integra-se ao componente de DevOps do grupo."],
        ], [3.6 * cm, 6.4 * cm, 6.4 * cm]),

        Paragraph("4. Metodologia", H1),
        ListFlowable([ListItem(Paragraph(s, BODY), leftIndent=12) for s in [
            "<b>Escopo.</b> Mantivemos 20 classes de oito culturas comuns em pequenas propriedades: tomate, milho, batata, "
            "pimentão, abóbora, soja, morango e uva. Ficaram de fora as fruteiras de clima temperado e duas classes sem "
            "exemplos suficientes; entre elas, a única praga do dataset (ácaro-rajado), com apenas 2 imagens.",
            "<b>Extração.</b> Lemos os arquivos direto dos objetos do git, porque o repositório original tem nomes que só "
            "diferem por maiúsculas e se sobrescrevem no macOS e no Windows.",
            f"<b>Validação das anotações.</b> Pareamos imagem e XML, descartamos {cnt.get('TRAIN: anotação incompatível com a imagem', 0) + cnt.get('TEST: anotação incompatível com a imagem', 0)} "
            "anotações cujas dimensões não batiam com a imagem e caixas degeneradas, e corrigimos a orientação EXIF.",
            f"<b>Deduplicação.</b> Agrupamos duplicatas exatas e quase idênticas (distância de pHash até 4). Removemos "
            f"{cnt['imagens removidas por duplicidade']} imagens, inclusive {cnt['grupos com vazamento treino/teste']} grupos "
            "presentes ao mesmo tempo no treino e no teste. Nesses casos, preservamos a cópia do teste oficial.",
            f"<b>Divisão.</b> Do treino oficial, separamos 15% para validação, estratificado pela classe principal "
            f"(semente 42). Resultado: {tr['imagens']} imagens de treino, {va['imagens']} de validação e {te['imagens']} de "
            "teste, este intocado até a avaliação final.",
            f"<b>Treino.</b> YOLO11n pré-treinado no COCO, imagens de 480 px, lote 16, até 40 épocas com taxa de aprendizado "
            f"cosseno e parada antecipada (paciência 12), em uma GPU NVIDIA T4 do Google Colab. Foram {epochs_run} épocas. Além do mosaico "
            "padrão, usamos rotação de 15° e inversão vertical, porque folhas não têm orientação fixa.",
            f"<b>Calibração.</b> Escolhemos na validação o limiar de confiança que maximiza o F1 médio: {num(m['conf_decisao'], 2)}. "
            "Abaixo dele o sistema não afirma nada e pede outra foto.",
            "<b>Avaliação.</b> No teste, medimos mAP, precisão e recall por classe; a decisão final por imagem, com "
            "intervalos de confiança por bootstrap; a robustez a fotos degradadas; respostas para culturas desconhecidas "
            "e imagens sem planta; e a latência em CPU.",
            "<b>Integração.</b> Exportamos para ONNX, servimos por FastAPI e conferimos que a saída em ONNX é idêntica à "
            "do PyTorch para a mesma entrada (25 de 25 imagens, diferença zero).",
        ]], bulletType="1"),
        figure(FIG / "classes.png", 15, f"Figura 1. Caixas anotadas por classe no treino ({tr['caixas']} no total). O "
               "desbalanceamento é alto: as classes com menos exemplos tendem a ter desempenho pior."),

        PageBreak(),
        Paragraph("5. Resultados", H1),
        Paragraph("5.1 Métricas de detecção", H2),
        table([
            ["Conjunto", "mAP@50", "mAP@50-95", "Precisão", "Recall"],
            ["Validação", num(m["validacao"]["map50"]), num(m["validacao"]["map50_95"]), "-", "-"],
            [f"Teste ({te['imagens']} imagens)", num(test["map50"]), num(test["map50_95"]), num(test["precisao"]), num(test["recall"])],
        ], [5 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm]),
        Spacer(1, 8),
        figure(FIG / "treino.png", 15, "Figura 2. Evolução do mAP na validação durante o treino."),
        figure(ROOT / "docs/results/test/confusion_matrix_normalized.png", 13,
               "Figura 3. Matriz de confusão normalizada no teste. As confusões mais frequentes são entre doenças da "
               "mesma cultura, cujos sintomas se parecem."),
        Paragraph("5.2 Desempenho por classe (teste)", H2),
        table([["Classe", "Precisão", "Recall", "mAP@50", "mAP@50-95"]] + [
            [c["classe"], num(c["precisao"], 2), num(c["recall"], 2), num(c["map50"], 2), num(c["map50_95"], 2)]
            for c in sorted(test["por_classe"], key=lambda c: -c["map50"])
        ], [6.4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm]),
        Paragraph("Classes com poucas imagens no teste têm métricas muito instáveis; leia a tabela como indicação.", SMALL),

        Paragraph("5.3 A decisão que o produtor recebe", H2),
        Paragraph(
            "O mAP mede caixas. O produtor, porém, recebe uma decisão por foto: possível doença, folha saudável ou "
            "pedido de nova foto. Medimos essa decisão no teste, rodando exatamente o código da API.", BODY),
        table([
            ["Indicador", "Resultado"],
            ["Folhas doentes sinalizadas como possível doença", ci(p["doente_sinalizada"])],
            ["Folhas doentes ditas saudáveis (erro mais grave)", ci(p["doente_dita_saudavel"])],
            ["Folhas sadias reconhecidas como saudáveis", ci(p["sadia_reconhecida"])],
            ["Folhas sadias com alarme falso de doença", ci(p["sadia_com_alarme_falso"])],
            ["Fotos com resposta conclusiva", ci(p["resposta_conclusiva"])],
            ["Cultura correta, quando responde", ci(p["cultura_correta_quando_responde"])],
            ["Doença exata correta, quando responde", ci(p["classe_exata_quando_responde"])],
        ], [9 * cm, 7.4 * cm]),

        Paragraph("5.4 Fora do cenário ideal", H2),
        figure(FIG / "robustez.png", 14, "Figura 4. mAP@50 no teste com degradações que simulam câmeras simples e "
               "condições ruins de campo."),
        table([
            ["Situação", "Imagens", "Resposta indevida (afirmou doença ou folha sadia)"],
            ["Culturas que o modelo não conhece (maçã, pêssego, mirtilo etc.)", str(oos["imagens"]), ci(oos["resposta_indevida"])],
            ["Imagens sem planta (COCO128, sem pessoas nem vasos)", str(nonplant["imagens"]), ci(nonplant["resposta_indevida"])],
        ], [7.6 * cm, 2 * cm, 6.8 * cm]),

        Paragraph("5.5 Tempo real", H2),
        table([["Execução (Apple M1, imagem por imagem)", "Mediana", "p95", "Imagens/s"]] + [
            [k, f"{num(v['p50_ms'], 1)} ms", f"{num(v['p95_ms'], 1)} ms", num(v["fps"], 1)] for k, v in lat.items()
        ], [7.6 * cm, 2.8 * cm, 2.8 * cm, 3.2 * cm]),
        Paragraph("Os tempos incluem pré e pós-processamento. Na demonstração pelo navegador, que inclui rede local e "
                  "desenho na tela, o sistema manteve uma taxa compatível com uso ao vivo.", SMALL),

        Paragraph("5.6 Exemplos", H2),
        figure(args.build / "upload_doenca.png", 15, "Figura 5. Foto enviada: a caixa indica a folha, e o painel mostra a "
               "doença provável, o primeiro cuidado e o aviso de confirmação."),
        figure(args.build / "upload_foto_ruim.png", 15, "Figura 6. Foto escura e fora de foco: o sistema não arrisca e "
               + ("pede outra foto." if json.loads((args.build / "demo.json").read_text())["respostas"]["foto_ruim"]["status"] == "inconclusivo" else "responde que não encontrou uma folha conhecida.")),
        figure(args.build / "upload_erro.png", 15, f"Figura 7. Erro real do modelo no teste: {samples['erro']['descricao']}. "
               "Por isso a decisão final fica com uma pessoa."),

        Paragraph("6. IA responsável, segurança e LGPD", H1),
        ListFlowable([ListItem(Paragraph(s, BODY), leftIndent=12) for s in [
            "As fotos são processadas em memória e descartadas. Os logs registram só status, quantidade de detecções e "
            "tempo, sem imagem nem nome de arquivo, o que é verificado por testes automatizados.",
            "O sistema só afirma algo acima do limiar calibrado. Toda resposta traz o aviso de que é uma sugestão e deve "
            "ser confirmada por um agrônomo ou pela ATER. Não recomendamos produto químico nem dose.",
            "Os limites aceitam no máximo 8 MB e 40 megapixels por imagem, e o serviço responde 503 quando está ocupado, "
            "em vez de travar.",
            "Viés conhecido: as fotos do PlantDoc vêm da internet, com maior presença de Índia e Estados Unidos, e não "
            "de lavouras brasileiras.",
        ]], bulletType="bullet"),

        Paragraph("7. Conclusão", H1),
        Paragraph(
            f"Treinamos de forma customizada um detector YOLO11n para 20 classes de folhas e o colocamos em produção em "
            f"CPU, com cerca de {round(cpu2['fps'])} imagens por segundo, integrado ao AgroFácil por uma API que não "
            f"guarda fotos. No teste, o mAP@50 foi de {num(test['map50'])}, e o sistema sinalizou "
            f"{pct(p['doente_sinalizada']['valor'])} das folhas doentes. O resultado é compatível com o uso como triagem: "
            "chamar atenção para a folha certa e incentivar a busca de orientação, nunca substituir o diagnóstico.", BODY),
        Paragraph(
            "A principal lição foi a qualidade dos dados. Duplicatas e vazamento entre treino e teste teriam inflado as "
            "métricas sem que percebêssemos. Medir a decisão final por foto e o comportamento fora do cenário ideal "
            "mostrou limites que o mAP sozinho esconde.", BODY),
        Paragraph(
            "Próximos passos: coletar e anotar fotos de lavouras brasileiras com produtores e técnicos parceiros; incluir "
            "pragas com um dataset próprio; adicionar imagens sem folhas conhecidas ao treino, para reduzir respostas "
            "indevidas; e executar o modelo no próprio celular, para funcionar sem internet.", BODY),

        Paragraph("Referências", H1),
        Paragraph("SINGH, D. et al. PlantDoc: A Dataset for Visual Plant Disease Detection. CoDS-COMAD 2020. "
                  "DOI 10.1145/3371158.3371196.", SMALL),
        Paragraph("JOCHER, G.; QIU, J. Ultralytics YOLO11. 2024. https://github.com/ultralytics/ultralytics.", SMALL),
        Paragraph("ONNX Runtime. https://onnxruntime.ai.", SMALL),
        Paragraph("LIN, T.-Y. et al. Microsoft COCO: Common Objects in Context. ECCV 2014.", SMALL),
    ]

    def footer(canvas, doc):
        canvas.setFont("Arial", 8)
        canvas.setFillColor(colors.HexColor(INK_2))
        canvas.drawString(2 * cm, 1.2 * cm, "AgroFácil Visão · Applied Computer Vision · FIAP GS 2026.2")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))

    SimpleDocTemplate(str(args.out), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm,
                      bottomMargin=2 * cm, title="AgroFácil Visão", author=", ".join(t["nome"] for t in team)
                      ).build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"relatório: {args.out} | resumo {words(resumo)} palavras | objetivo {words(objetivo)} palavras")


if __name__ == "__main__":
    main()
