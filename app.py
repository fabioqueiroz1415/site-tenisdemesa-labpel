from flask import Flask, render_template, request, jsonify
import requests
import base64
from datetime import datetime
import os

app = Flask(__name__)

# --- Configuração do GitHub ---
# GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "token")
GITHUB_USER = os.environ.get("GITHUB_USER", "labpel")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "site-tenisdemesa-labpel")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# HEADERS = {
#     "Authorization": f"token {GITHUB_TOKEN}",
#     "Accept": "application/vnd.github.v3+json",
# }

BASE_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents"


def github_get(path):
    """Busca um arquivo do GitHub. Retorna (conteúdo_texto, sha) ou (None, None)."""
    url = f"{BASE_URL}/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    return None, None


def github_put(path, content_text, sha=None, message="update via flask"):
    """Cria ou atualiza um arquivo no GitHub."""
    url = f"{BASE_URL}/{path}"
    encoded = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    payload = {
        "message": message,
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=HEADERS, json=payload)
    return r.status_code in (200, 201), r.json()


def github_list(path):
    """Lista arquivos em uma pasta do GitHub. Retorna lista de nomes."""
    url = f"{BASE_URL}/{path}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return [item["name"] for item in r.json() if item["type"] == "file"]
    return []


def github_delete(path, sha, message="delete via flask"):
    """Remove um arquivo do GitHub."""
    url = f"{BASE_URL}/{path}"
    payload = {"message": message, "sha": sha, "branch": GITHUB_BRANCH}
    r = requests.delete(url, headers=HEADERS, json=payload)
    return r.status_code == 200


# --- Rotas ---

@app.route("/")
def menu():
    return render_template("menu.html")


# ── Template 1: Presença ──────────────────────────────────────────────────────

@app.route("/presenca")
def presenca():
    hoje = datetime.now().strftime("%d-%m-%y")
    tipo = request.args.get("tipo", "iniciacao")  # iniciacao ou aprimoramento
    return render_template("presenca.html", hoje=hoje, tipo=tipo)


@app.route("/api/presenca/carregar")
def presenca_carregar():
    tipo = request.args.get("tipo")
    data = request.args.get("data")
    path = f"{tipo}/frequencia/presencas/{data}.txt"
    conteudo, sha = github_get(path)
    return jsonify({"conteudo": conteudo or "", "sha": sha})


@app.route("/api/presenca/salvar", methods=["POST"])
def presenca_salvar():
    dados = request.get_json()
    tipo = dados["tipo"]
    data = dados["data"]
    conteudo = dados["conteudo"]
    sha = dados.get("sha") or None
    path = f"{tipo}/frequencia/presencas/{data}.txt"
    ok, resp = github_put(path, conteudo, sha=sha, message=f"presença {tipo} {data}")
    return jsonify({"ok": ok})


# ── Template 2: Alunos ────────────────────────────────────────────────────────

@app.route("/alunos")
def alunos():
    return render_template("alunos.html")


@app.route("/api/alunos/carregar")
def alunos_carregar():
    tipo = request.args.get("tipo")
    path = f"{tipo}/frequencia/alunos.txt"
    conteudo, sha = github_get(path)
    lista = [n.strip() for n in (conteudo or "").splitlines() if n.strip()]
    return jsonify({"alunos": lista, "sha": sha})


@app.route("/api/alunos/salvar", methods=["POST"])
def alunos_salvar():
    dados = request.get_json()
    tipo = dados["tipo"]
    lista = dados["alunos"]
    sha = dados.get("sha") or None
    conteudo = "\n".join(lista) + "\n"
    path = f"{tipo}/frequencia/alunos.txt"
    ok, resp = github_put(path, conteudo, sha=sha, message=f"alunos {tipo} atualizados")
    return jsonify({"ok": ok})


# ── Template 3: Ensino ────────────────────────────────────────────────────────

@app.route("/ensino")
def ensino():
    tipo = request.args.get("tipo", "iniciacao")
    # plano
    plano_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{tipo}/ensino/plano.md"
    # aulas
    aulas = github_list(f"{tipo}/ensino/aulas")
    aulas_urls = [
        {
            "nome": a,
            "url": f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/blob/{GITHUB_BRANCH}/{tipo}/ensino/aulas/{a}"
        }
        for a in aulas
    ]
    return render_template("ensino.html", tipo=tipo, plano_url=plano_url, aulas=aulas_urls)


if __name__ == "__main__":
    app.run(debug=True)
