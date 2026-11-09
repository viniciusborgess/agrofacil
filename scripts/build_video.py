"""Monta o vídeo final: slides, gravação real do produto, narração e legendas.

Os números vêm de docs/results/metrics.json e as telas de scripts/record_demo.py.

Uso: python scripts/build_video.py --out assets/agrofacil_visao_demo.mp4
"""
import argparse
import json
import re
import statistics
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720
VOICE = "Luciana"
RATE = 178
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
BG, INK, MUTED, BRAND, CARD, LINE = (246, 244, 236), (29, 42, 31), (77, 90, 79), (31, 92, 52), (255, 255, 255), (201, 207, 195)


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else REGULAR, size)


def wrap(draw, text, f, width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=f) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    return lines + [current] if current else lines


def base(title):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, W, 10], fill=BRAND)
    draw.text((60, 44), title, font=font(44, True), fill=BRAND)
    return image, draw


def bullets_slide(title, bullets, path):
    image, draw = base(title)
    y = 130
    for text in bullets:
        f = font(31)
        lines = wrap(draw, text, f, W - 150)
        draw.ellipse([64, y + 11, 78, y + 25], fill=BRAND)
        for line in lines:
            draw.text((96, y), line, font=f, fill=INK)
            y += 42
        y += 20
    image.save(path)


def title_slide(title, subtitle, lines, path):
    image = Image.new("RGB", (W, H), BRAND)
    draw = ImageDraw.Draw(image)
    y = 150
    draw.text((80, y), title, font=font(72, True), fill=(255, 255, 255))
    y += 100
    draw.text((80, y), subtitle, font=font(32), fill=(225, 238, 228))
    y += 90
    for line in lines:
        draw.text((80, y), line, font=font(28), fill=(255, 255, 255))
        y += 40
    image.save(path)


def stats_slide(title, stats, note, path):
    """Até seis números grandes em grade, com um rótulo curto em cada."""
    image, draw = base(title)
    cw, ch, gap = 370, 200, 25
    for i, (value, label) in enumerate(stats):
        x, y = 60 + (i % 3) * (cw + gap), 130 + (i // 3) * (ch + gap)
        draw.rounded_rectangle([x, y, x + cw, y + ch], 10, fill=CARD, outline=LINE, width=2)
        draw.text((x + 22, y + 22), value, font=font(58, True), fill=BRAND)
        ly = y + 100
        for line in wrap(draw, label, font(25), cw - 44):
            draw.text((x + 22, ly), line, font=font(25), fill=INK)
            ly += 31
    y = 130 + 2 * (ch + gap) + 4
    for line in wrap(draw, note, font(25), W - 120):
        draw.text((60, y), line, font=font(25), fill=MUTED)
        y += 32
    image.save(path)


def pipeline_slide(title, steps, note, path):
    image, draw = base(title)
    box_w, box_h, gap = 208, 210, 26
    x = (W - (box_w * len(steps) + gap * (len(steps) - 1))) // 2
    y = 180
    for i, (head, body) in enumerate(steps):
        draw.rounded_rectangle([x, y, x + box_w, y + box_h], 10, fill=CARD, outline=BRAND, width=3)
        draw.text((x + 14, y + 16), head, font=font(26, True), fill=BRAND)
        ly = y + 60
        for line in wrap(draw, body, font(22), box_w - 28):
            draw.text((x + 14, ly), line, font=font(22), fill=INK)
            ly += 28
        if i < len(steps) - 1:
            ay = y + box_h // 2
            draw.line([x + box_w + 3, ay, x + box_w + gap - 5, ay], fill=BRAND, width=4)
            draw.polygon([(x + box_w + gap - 2, ay), (x + box_w + gap - 11, ay - 7), (x + box_w + gap - 11, ay + 7)], fill=BRAND)
        x += box_w + gap
    y = 440
    for line in wrap(draw, note, font(29), W - 140):
        draw.text((70, y), line, font=font(29), fill=INK)
        y += 40
    image.save(path)


def banner(lines, path):
    """Faixa semitransparente sobre a gravação, no canto superior direito."""
    image = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    left, top = 700, 20
    height = 16 + 32 * len(lines) + 8
    draw.rounded_rectangle([left, top, W - 30, top + height], 8, fill=(31, 92, 52, 240))
    for i, line in enumerate(lines):
        draw.text((left + 16, top + 12 + i * 32), line, font=font(23, True), fill=(255, 255, 255))
    image.save(path)


def speak(text, path):
    subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "--data-format=LEI16@44100", "-o", str(path), text], check=True)
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


ENCODE = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-preset", "medium", "-crf", "21",
          "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
PAD = 0.7


def run(cmd):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *cmd], check=True)


def still_segment(image, audio, duration, out, overlay=None):
    inputs = ["-loop", "1", "-framerate", "30", "-i", str(image), "-i", str(audio)]
    if overlay:
        inputs += ["-loop", "1", "-framerate", "30", "-i", str(overlay)]
        graph = ["-filter_complex", "[0:v]scale=1280:720[b];[b][2:v]overlay=0:0[v]", "-map", "[v]", "-map", "1:a"]
    else:
        graph = ["-vf", "scale=1280:720"]
    run([*inputs, *graph, "-af", f"apad=pad_dur={PAD}", "-t", f"{duration + PAD:.2f}", *ENCODE, str(out)])


def live_segment(video, start, audio, duration, overlay, out):
    run(["-ss", f"{start:.2f}", "-i", str(video), "-i", str(audio), "-loop", "1", "-framerate", "30", "-i", str(overlay),
         "-filter_complex", "[0:v]fps=30,scale=1280:720,tpad=stop_mode=clone:stop_duration=90[b];[b][2:v]overlay=0:0[v]",
         "-map", "[v]", "-map", "1:a", "-af", f"apad=pad_dur={PAD}", "-t", f"{duration + PAD:.2f}", *ENCODE, str(out)])


def timestamp(seconds):
    ms = int(round(seconds * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def subtitles(segments, path):
    """Divide cada narração por frase, com tempo proporcional ao tamanho do texto."""
    entries, clock = [], 0.0
    for text, duration in segments:
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
        total = sum(len(s) for s in sentences)
        t = clock
        for sentence in sentences:
            length = duration * len(sentence) / total
            entries.append(f"{len(entries) + 1}\n{timestamp(t)} --> {timestamp(t + length)}\n{sentence}\n")
            t += length
        clock += duration + PAD
    path.write_text("\n".join(entries), encoding="utf-8")


def pct(value, digits=0):
    return f"{value * 100:.{digits}f}%".replace(".", ",")


def spoken_pct(value):
    return f"{round(value * 100)} por cento"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", type=Path, default=ROOT / "docs/results/metrics.json")
    ap.add_argument("--build", type=Path, default=ROOT / "assets/video_build")
    ap.add_argument("--out", type=Path, default=ROOT / "assets/agrofacil_visao_demo.mp4")
    args = ap.parse_args()
    build = args.build
    seg_dir = build / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)

    m = json.loads(args.metrics.read_text())
    data = json.loads((ROOT / "docs/data_report.json").read_text())
    team = json.loads((ROOT / "docs/integrantes.json").read_text())
    demo = json.loads((build / "demo.json").read_text())
    p = m["produto"]
    test, robust = m["teste"], m["robustez_map50"]
    readings = [float(r.split()[0].replace(",", ".")) for r in demo["leituras_ao_vivo"][1:] if r]
    live_fps = statistics.median(readings)
    cpu = m["latencia"]["ONNX CPU, 2 thread(s)"]
    names = [t["nome"] for t in team]
    worst_label, worst_value = min(((k, v) for k, v in robust.items() if k != "Original"), key=lambda kv: kv[1])
    responses = demo["respostas"]
    samples_manifest = json.loads((ROOT / "assets/samples/manifest.json").read_text())

    plan = []

    def slide(render, narration):
        plan.append(("slide", render, narration))

    title_slide("AgroFácil Visão", "Applied Computer Vision · FIAP Global Solution 2026.2 · CitizenTech",
                [f"{t['nome']} · {t['rm']}" for t in team], build / "s_titulo.png")
    slide(build / "s_titulo.png",
          f"Este é o AgroFácil Visão, o componente de visão computacional do AgroFácil, desenvolvido por {', '.join(names[:-1])} e {names[-1]}.")

    bullets_slide("O problema", [
        "Pequenos produtores nem sempre têm um técnico por perto quando uma mancha aparece na folha.",
        "A dúvida atrasa a decisão, e algumas doenças avançam em poucos dias.",
        "O AgroFácil Visão aponta, por foto ou câmera, onde está o possível problema e o que fazer primeiro.",
    ], build / "s_problema.png")
    slide(build / "s_problema.png",
          "Quando uma mancha aparece na folha, o pequeno produtor nem sempre tem um técnico por perto, e algumas doenças avançam em poucos dias. "
          "Nosso componente aponta, por foto ou pela câmera do celular, onde está o possível problema e sugere o primeiro cuidado.")

    pipeline_slide("Como funciona", [
        ("Câmera", "Foto ou vídeo do navegador, reduzidos para gastar pouca internet"),
        ("API", "Valida a imagem e não guarda nada"),
        ("YOLO11n", "Detector em ONNX, rodando em CPU"),
        ("Regras", "Abaixo do limiar, pede outra foto em vez de arriscar"),
        ("Produtor", "Caixa na folha, orientação e aviso para confirmar"),
    ], "O resultado sai em JSON pelo endpoint POST /v1/detections, pronto para a plataforma AgroFácil consumir.", build / "s_fluxo.png")
    slide(build / "s_fluxo.png",
          "A imagem sai do navegador, passa por uma API que não guarda nenhuma foto e chega a um detector leve, que roda sem placa de vídeo. "
          "Se a confiança ficar abaixo do limiar calibrado, o sistema pede outra foto em vez de arriscar um diagnóstico.")

    tr, va, te = data["train"], data["val"], data["test"]
    counts = data["contagens"]
    bullets_slide("Treinamento customizado", [
        f"Dataset PlantDoc (CC BY 4.0), com fotos reais anotadas: {tr['imagens']} de treino, {va['imagens']} de validação e {te['imagens']} de teste.",
        f"Removemos {counts['imagens removidas por duplicidade']} duplicatas e corrigimos {counts['grupos com vazamento treino/teste']} casos de vazamento entre treino e teste.",
        "YOLO11n pré-treinado no COCO e ajustado para 20 classes de 8 culturas.",
        f"Limiar de decisão de {m['conf_decisao']:.2f}".replace(".", ",") + ", calibrado apenas na validação.",
    ], build / "s_treino.png")
    slide(build / "s_treino.png",
          f"Fizemos o treinamento customizado de uma rede YOLO onze com o dataset aberto PlantDoc, em vinte classes de oito culturas. "
          f"Antes de treinar, auditamos os dados e removemos {counts['imagens removidas por duplicidade']} duplicatas, inclusive imagens que estavam ao mesmo tempo no treino e no teste e inflariam o resultado.")

    plan.append(("live", None,
                 f"Agora, o produto em funcionamento. Para esta gravação usamos uma câmera virtual, alimentada com fotos do conjunto de teste, que o modelo nunca viu no treino. "
                 f"Todo o resto é real: cada quadro vai para a API, e as caixas e a orientação voltam na hora. "
                 f"Mesmo nesta máquina, um notebook sem placa de vídeo dedicada, o sistema fez cerca de {round(live_fps)} análises por segundo. "
                 f"Vermelho indica possível doença, e verde, folha sadia."))

    uploads = [("doenca", ["Envio de foto: possível doença"],
                "Sem internet boa para o vídeo, o produtor pode enviar uma foto. O resultado mostra a doença provável, a confiança, o primeiro cuidado e o aviso para confirmar com a assistência técnica.")]
    if "foto_ruim" in responses:
        uploads.append(("foto_ruim", [f"Foto ruim: {'nada detectado' if responses['foto_ruim']['status'] == 'nada_detectado' else 'inconclusivo'}"],
                        "Com uma foto escura e fora de foco, o sistema não arrisca: "
                        + ("ele avisa que não teve certeza e pede uma nova foto." if responses["foto_ruim"]["status"] == "inconclusivo"
                           else "ele responde que não encontrou uma folha conhecida, em vez de chutar um diagnóstico.")))
    if "erro" in responses:
        uploads.append(("erro", ["Erro real do modelo"],
                        f"O modelo também erra. Aqui, {samples_manifest['uploads']['erro']['descricao']}. Por isso o resultado é tratado como sugestão, e a decisão final fica com uma pessoa."))
    for name, label, narration in uploads:
        plan.append(("upload", (name, label), narration))

    stats_slide("Resultados no conjunto de teste", [
        (f"{test['map50']:.2f}".replace(".", ","), "mAP@50 em 20 classes"),
        (f"{test['map50_95']:.2f}".replace(".", ","), "mAP@50-95"),
        (f"{cpu['fps']:.0f} FPS".replace(".", ","), "em CPU, com 2 threads"),
        (pct(p["doente_sinalizada"]["valor"]), "das folhas doentes foram sinalizadas"),
        (pct(p["doente_dita_saudavel"]["valor"]), "das doentes foram ditas saudáveis, o pior erro"),
        (pct(p["cultura_correta_quando_responde"]["valor"]), "de cultura correta quando responde"),
    ], f"{p['imagens']} imagens de teste. As taxas por imagem têm margem de erro relevante; os intervalos de confiança estão no relatório.", build / "s_resultados.png")
    slide(build / "s_resultados.png",
          f"No conjunto de teste, separado desde o início, o modelo chegou a {str(round(test['map50'], 2)).replace('.', ',')} de m.A.P. a cinquenta, e roda a {round(cpu['fps'])} quadros por segundo em CPU. "
          f"O sistema sinalizou {spoken_pct(p['doente_sinalizada']['valor'])} das folhas doentes, e {spoken_pct(p['doente_dita_saudavel']['valor'])} das doentes foram ditas saudáveis, que é o erro mais grave. "
          f"O conjunto de teste é pequeno, então esses números servem como estimativa.")

    oos, nonplant = m["culturas_fora_do_escopo"], m["imagens_sem_planta"]
    bullets_slide("Limites que assumimos", [
        f"Foto degradada reduz a qualidade: com {worst_label.lower()}, o mAP@50 cai de {robust['Original']:.2f} para {worst_value:.2f}.".replace("0.", "0,"),
        f"Culturas que o modelo não conhece recebem resposta indevida em {pct(oos['resposta_indevida']['valor'])} dos casos; imagens sem planta, em {pct(nonplant['resposta_indevida']['valor'])}.",
        "Pragas ainda não são cobertas: o dataset quase não tem exemplos. Os dados também não vêm de lavouras brasileiras.",
        "Próximo passo: validar com fotos reais de produtores e com um agrônomo antes de usar em campo.",
    ], build / "s_limites.png")
    slide(build / "s_limites.png",
          f"Também medimos os limites. Fotos ruins reduzem a qualidade, e culturas que o modelo não conhece podem receber uma resposta indevida. "
          f"O modelo ainda não cobre pragas, porque o dataset quase não tem exemplos, e os dados não vêm de lavouras brasileiras. "
          f"O próximo passo é validar com fotos reais de produtores e com um agrônomo antes de qualquer uso em campo.")

    title_slide("AgroFácil Visão", "Detecção customizada, em tempo real, integrada por API ao AgroFácil",
                ["Código, dados de avaliação e relatório no repositório do projeto."] + [t["nome"] for t in team], build / "s_fim.png")
    slide(build / "s_fim.png", "Esse é o AgroFácil Visão: tecnologia simples, medida com honestidade, para ajudar o pequeno produtor a decidir mais cedo. Obrigado.")

    live_banner = build / "b_live.png"
    banner(["Ao vivo: navegador + API + modelo", "Câmera virtual com fotos de teste"], live_banner)

    produced, timeline = [], []
    for i, (kind, media, narration) in enumerate(plan):
        audio = seg_dir / f"{i:02d}.wav"
        duration = speak(narration, audio)
        out = seg_dir / f"{i:02d}.mp4"
        if kind == "slide":
            still_segment(media, audio, duration, out)
        elif kind == "live":
            live_segment(build / "live.webm", demo["inicio_ao_vivo_s"], audio, duration, live_banner, out)
        else:
            name, label = media
            overlay = build / f"b_{name}.png"
            banner(label, overlay)
            still_segment(build / f"upload_{name}.png", audio, duration, out, overlay)
        produced.append(out)
        timeline.append((narration, duration))

    listing = seg_dir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in produced))
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(args.out)])
    subtitles(timeline, args.out.with_suffix(".srt"))
    total = sum(d + PAD for _, d in timeline)
    print(f"vídeo: {args.out} | duração {total:.0f}s | {args.out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
