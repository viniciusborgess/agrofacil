"""Coleta as evidências da disciplina de DevOps: comandos reais renderizados como print e telas do navegador.

Uso:
  python scripts/devops_evidence.py                 # infraestrutura, pipeline e MVP
  python scripts/devops_evidence.py --monitoring    # Grafana e Prometheus (stack local no ar)
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/devops/evidencias"
REPO = "viniciusborgess/agrofacil"
MONO = "/System/Library/Fonts/Menlo.ttc"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def sh(command):
    result = subprocess.run(command, shell=True, cwd=ROOT, capture_output=True, text=True)
    return ANSI.sub("", (result.stdout + result.stderr).rstrip()).expandtabs(4)


def terminal(name, commands, max_lines=34):
    """Renderiza comandos e saídas como uma janela de terminal."""
    lines = []
    for command, output in commands:
        lines.append(("$ " + command, (130, 220, 160)))
        lines += [(line, (225, 228, 222)) for line in output.splitlines()[:max_lines]]
        lines.append(("", None))
    font = ImageFont.truetype(MONO, 15)
    width = min(1500, max(900, int(max(font.getlength(t) for t, _ in lines)) + 48))
    height = 44 + 22 * len(lines) + 16
    image = Image.new("RGB", (width, height), (24, 26, 27))
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, width, 30], fill=(48, 50, 52))
    for i, color in enumerate(((237, 106, 94), (245, 191, 79), (98, 197, 84))):
        draw.ellipse([14 + i * 22, 9, 26 + i * 22, 21], fill=color)
    y = 42
    for text, color in lines:
        if color:
            draw.text((20, y), text, font=font, fill=color)
        y += 22
    image.save(OUT / f"{name}.png")
    print("print:", name)


def infra_evidence():
    rg, app, acr = "rg-agrofacil-prod", "ca-agrofacil-prod", sh("terraform -chdir=infra output -raw acr_name")
    url = sh("terraform -chdir=infra output -raw app_url")
    terminal("01_terraform_plan_limpo", [
        ("terraform -chdir=infra plan -detailed-exitcode", "\n".join(
            l for l in sh("terraform -chdir=infra plan -input=false -no-color -detailed-exitcode").splitlines()
            if l.strip() and "Refreshing" not in l and "Reading" not in l and "Read complete" not in l)),
    ])
    terminal("02_recursos_azure", [
        (f"az resource list -g {rg} -o table",
         sh(f"az resource list -g {rg} --query \"[].{{Nome:name, Tipo:type, Regiao:location}}\" -o table")),
    ])
    terminal("03_sem_porta_admin", [
        (f"az containerapp show -n {app} -g {rg} (ingress)",
         sh(f"az containerapp show -n {app} -g {rg} --query \"properties.configuration.ingress.{{externo:external, portaInterna:targetPort, httpInseguro:allowInsecure, transporte:transport}}\" -o table")),
        (f"az acr show -n {acr}", sh(f"az acr show -n {acr} --query \"{{Nome:name, Sku:sku.name, UsuarioAdmin:adminUserEnabled}}\" -o table")),
        (f"curl -I http://{url.removeprefix('https://')}/health",
         sh(f"curl -sI http://{url.removeprefix('https://')}/health | head -3")),
        (f"curl {url}/health", sh(f"curl -s {url}/health")),
        (f"curl -o /dev/null -w '%{{http_code}}' {url}/metrics   # sem token",
         sh(f"curl -s -o /dev/null -w '%{{http_code}}' {url}/metrics")),
    ])
    terminal("04_state_e_segredos_fora_do_git", [
        ("git check-ignore -v infra/terraform.tfvars infra/backend.hcl infra/.terraform monitoring/secrets weights",
         sh("git check-ignore -v infra/terraform.tfvars infra/backend.hcl infra/.terraform monitoring/secrets weights")),
        ("git ls-files | grep -E 'tfstate|tfvars$|backend.hcl|secrets' || echo 'nenhum arquivo sensível versionado'",
         sh("git ls-files | grep -E 'tfstate|tfvars$|backend.hcl|secrets' || echo 'nenhum arquivo sensível versionado'")),
        ("az storage blob list --container-name tfstate (state remoto no Azure)",
         sh("az storage blob list --account-name $(grep storage_account_name infra/backend.hcl | cut -d'\"' -f2) "
            "--container-name tfstate --auth-mode login --query \"[].{Arquivo:name, Tamanho:properties.contentLength}\" -o table")),
    ])
    terminal("05_github_secrets_oidc", [
        (f"gh secret list -R {REPO}", sh(f"gh secret list -R {REPO}")),
        (f"gh variable list -R {REPO}", sh(f"gh variable list -R {REPO}")),
        ("az identity federated-credential list (quem pode publicar)",
         sh(f"az identity federated-credential list --identity-name id-agrofacil-prod-github -g {rg} --query \"[].{{Emissor:issuer, Subject:subject}}\" -o table")),
    ])
    terminal("06_scanners_locais", [
        ("gitleaks detect --source . --redact", sh("gitleaks detect --source . --redact --no-banner 2>&1 | tail -2")),
        ("trivy config --severity HIGH,CRITICAL .", sh("trivy config -q --severity HIGH,CRITICAL --skip-dirs .venv --skip-dirs data --skip-dirs runs . | tail -12")),
    ])


def runs():
    data = json.loads(sh(f"gh run list -R {REPO} -L 40 --json databaseId,conclusion,headSha,displayTitle,createdAt"))
    failed = [r for r in data if r["conclusion"] == "failure"]
    passed = [r for r in data if r["conclusion"] == "success"]
    return failed[-1], passed[0]


def trivy_block_evidence():
    failed, _ = runs()
    log = sh(f"gh run view {failed['databaseId']} -R {REPO} --log-failed | sed 's/.*Z //'")
    rows = [l for l in log.splitlines() if re.match(r"^│ \S", l) and ("CVE-" in l or "GHSA-" in l)]
    summary = [l for l in log.splitlines() if "│" in l and ("debian" in l or "pillow" in l or "starlette" in l or "jaraco" in l or "wheel" in l)]
    terminal("12b_trivy_vulnerabilidades", [
        (f"gh run view {failed['databaseId']} --log-failed   # passo 'Vulnerabilidades da imagem'",
         "\n".join(summary[:8] + ["..."] + rows[:14] + ["", "Process completed with exit code 1  ->  deploy não executado"])),
    ], max_lines=40)


def browser_evidence():
    failed, passed = runs()
    url = sh("terraform -chdir=infra output -raw app_url")
    jobs = json.loads(sh(f"gh run view {failed['databaseId']} -R {REPO} --json jobs"))["jobs"]
    failed_job = next(j for j in jobs if j["conclusion"] == "failure")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=1)
        shots = [
            ("10_actions_historico", f"https://github.com/{REPO}/actions"),
            ("11_execucao_barrada", f"https://github.com/{REPO}/actions/runs/{failed['databaseId']}"),
            ("12_trivy_barrou_imagem", failed_job["url"]),
            ("13_execucao_corrigida", f"https://github.com/{REPO}/actions/runs/{passed['databaseId']}"),
        ]
        for name, link in shots:
            page.goto(link, wait_until="load")
            page.wait_for_timeout(4000)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("tela:", name)
        page.goto(url, wait_until="networkidle")
        sample = next((ROOT / "assets/samples").glob("upload_doenca.jpg"), None) or next((ROOT / "assets/samples").glob("*.jpg"))
        with page.expect_response("**/v1/detections"):
            page.set_input_files("#file", str(sample))
        page.wait_for_timeout(1000)
        page.screenshot(path=str(OUT / "14_mvp_publicado.png"))
        print("tela: 14_mvp_publicado")
        browser.close()
    (OUT / "execucoes.json").write_text(json.dumps({"barrada": failed, "corrigida": passed, "job_barrado": failed_job["url"]}, indent=2))


def monitoring_evidence():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto("http://127.0.0.1:3000/d/agrofacil-golden?orgId=1&var-ambiente=azure&kiosk", wait_until="networkidle")
        page.wait_for_timeout(5000)
        page.screenshot(path=str(OUT / "20_grafana_sinais_de_ouro.png"))
        page.goto("http://127.0.0.1:9090/alerts", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "21_prometheus_alerta_disparado.png"), full_page=True)
        page.goto("http://127.0.0.1:9090/targets", wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "22_prometheus_alvos.png"))
        browser.close()
    terminal("23_compose_e_usuario_nao_root", [
        ("docker compose ps", sh("docker compose ps --format 'table {{.Service}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'")),
        ("docker compose exec api id", sh("docker compose exec -T api id")),
        ("docker image ls agrofacil-visao:local", sh("docker image ls agrofacil-visao:local --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}'")),
    ])
    print("telas de monitoramento salvas")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--monitoring", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.monitoring:
        monitoring_evidence()
    else:
        infra_evidence()
        trivy_block_evidence()
        browser_evidence()


if __name__ == "__main__":
    main()
