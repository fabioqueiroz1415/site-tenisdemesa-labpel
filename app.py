from flask import Flask, render_template, request, jsonify
import requests
import base64
from datetime import datetime
import os

app = Flask(__name__)
load_dotenv()
# --- Configuração do GitHub ---
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN",  "seu_token_aqui")
GITHUB_USER   = os.environ.get("GITHUB_USER",   "seu_usuario")
GITHUB_REPO   = os.environ.get("GITHUB_REPO",   "seu_repositorio")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# ATENÇÃO: headers são montados aqui, mas o token já foi lido acima.
# Se as variáveis de ambiente não estiverem definidas ANTES de iniciar o app,
# o token ficará como "seu_token_aqui". Configure-as no painel do PythonAnywhere.

def get_headers():
    return {
        "Authorization": f"token {os.environ.get('GITHUB_TOKEN', GITHUB_TOKEN)}",
        "Accept": "application/vnd.github.v3+json",
    }

def base_url():
    user  = os.environ.get("GITHUB_USER",  GITHUB_USER)
    repo  = os.environ.get("GITHUB_REPO",  GITHUB_REPO)
    return f"https://api.github.com/repos/{user}/{repo}/contents"

def branch():
    return os.environ.get("GITHUB_BRANCH", GITHUB_BRANCH)


def github_get(path):
    """Busca um arquivo do GitHub. Retorna (conteúdo_texto, sha) ou (None, erro)."""
    url = f"{base_url()}/{path}?ref={branch()}"
    r = requests.get(url, headers=get_headers())
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    return None, r.json()  # devolve o erro do GitHub para diagnóstico


def github_put(path, content_text, sha=None, message="update via flask"):
    url = f"{base_url()}/{path}"
    encoded = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": encoded, "branch": branch()}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=get_headers(), json=payload)
    return r.status_code in (200, 201), r.json()


def github_list(path):
    url = f"{base_url()}/{path}?ref={branch()}"
    r = requests.get(url, headers=get_headers())
    if r.status_code == 200:
        return [item["name"] for item in r.json() if item["type"] == "file"]
    return []


def github_delete(path, sha, message="delete via flask"):
    url = f"{base_url()}/{path}"
    payload = {"message": message, "sha": sha, "branch": branch()}
    r = requests.delete(url, headers=get_headers(), json=payload)
    return r.status_code == 200


# --- Rotas ---

@app.route("/")
def menu():
    return render_template("menu.html")


# ── Template 1: Presença ──────────────────────────────────────────────────────

@app.route("/presenca")
def presenca():
    hoje = datetime.now().strftime("%d-%m-%y")
    tipo = request.args.get("tipo", "iniciacao")
    return render_template("presenca.html", hoje=hoje, tipo=tipo)


@app.route("/api/presenca/carregar")
def presenca_carregar():
    tipo = request.args.get("tipo")
    data = request.args.get("data")
    path = f"{tipo}/frequencia/presencas/{data}.txt"
    conteudo, sha_ou_erro = github_get(path)
    return jsonify({"conteudo": conteudo or "", "sha": sha_ou_erro if conteudo else None})


@app.route("/api/presenca/salvar", methods=["POST"])
def presenca_salvar():
    dados = request.get_json()
    tipo     = dados["tipo"]
    data     = dados["data"]
    conteudo = dados["conteudo"]
    sha      = dados.get("sha") or None
    path = f"{tipo}/frequencia/presencas/{data}.txt"
    ok, resp = github_put(path, conteudo, sha=sha, message=f"presença {tipo} {data}")
    return jsonify({"ok": ok, "github": resp})


# ── Template 2: Alunos ────────────────────────────────────────────────────────

@app.route("/alunos")
def alunos():
    return render_template("alunos.html")


@app.route("/api/alunos/carregar")
def alunos_carregar():
    tipo = request.args.get("tipo")
    path = f"{tipo}/frequencia/alunos.txt"
    conteudo, sha_ou_erro = github_get(path)
    lista = [n.strip() for n in (conteudo or "").splitlines() if n.strip()]
    # inclui o erro do GitHub na resposta para facilitar diagnóstico
    erro = sha_ou_erro if not conteudo else None
    return jsonify({"alunos": lista, "sha": sha_ou_erro if conteudo else None, "erro": erro})


@app.route("/api/alunos/salvar", methods=["POST"])
def alunos_salvar():
    dados = request.get_json()
    tipo  = dados["tipo"]
    lista = dados["alunos"]
    sha   = dados.get("sha") or None
    conteudo = "\n".join(lista) + "\n"
    path = f"{tipo}/frequencia/alunos.txt"
    ok, resp = github_put(path, conteudo, sha=sha, message=f"alunos {tipo} atualizados")
    return jsonify({"ok": ok, "github": resp})


# ── Template 3: Ensino ────────────────────────────────────────────────────────

@app.route("/ensino")
def ensino():
    tipo = request.args.get("tipo", "iniciacao")
    user = os.environ.get("GITHUB_USER", GITHUB_USER)
    repo = os.environ.get("GITHUB_REPO", GITHUB_REPO)
    br   = branch()
    plano_url = f"https://github.com/{user}/{repo}/blob/{br}/{tipo}/ensino/plano.md"
    aulas = github_list(f"{tipo}/ensino/aulas")
    aulas_urls = [
        {"nome": a, "url": f"https://github.com/{user}/{repo}/blob/{br}/{tipo}/ensino/aulas/{a}"}
        for a in aulas
    ]
    return render_template("ensino.html", tipo=tipo, plano_url=plano_url, aulas=aulas_urls)


if __name__ == "__main__":
    app.run(debug=True)
