from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import base64
from datetime import datetime
import os

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)

# --- Configuração do GitHub ---
TOKEN  = os.getenv("GITHUB_TOKEN")
REPO   = os.getenv("GITHUB_REPO", "fabioqueiroz1415/tenisdemesa-labpel")
BRANCH = os.getenv("GITHUB_BRANCH", "main")

BASE_URL = f"https://api.github.com/repos/{REPO}/contents"

def get_headers():
    return {
        "Authorization": f"token {os.getenv('GITHUB_TOKEN', TOKEN)}",
        "Accept": "application/vnd.github.v3+json",
    }


def github_get(path):
    url = f"{BASE_URL}/{path}?ref={BRANCH}"
    r = requests.get(url, headers=get_headers())
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]
    return None, r.json()


def github_put(path, content_text, sha=None, message="update via flask"):
    url = f"{BASE_URL}/{path}"
    encoded = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": encoded, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=get_headers(), json=payload)
    return r.status_code in (200, 201), r.json()


def github_list_files(path):
    """Retorna lista de dicts {name, download_url} de arquivos numa pasta."""
    url = f"{BASE_URL}/{path}?ref={BRANCH}"
    r = requests.get(url, headers=get_headers())
    if r.status_code == 200:
        return [item for item in r.json() if item["type"] == "file"]
    return []


def github_list(path):
    url = f"{BASE_URL}/{path}?ref={BRANCH}"
    r = requests.get(url, headers=get_headers())
    if r.status_code == 200:
        return [item["name"] for item in r.json() if item["type"] == "file"]
    return []


def github_delete(path, sha, message="delete via flask"):
    url = f"{BASE_URL}/{path}"
    payload = {"message": message, "sha": sha, "branch": BRANCH}
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


@app.route("/api/presenca/estatisticas")
def presenca_estatisticas():
    """
    Lê todos os arquivos de presença da turma e retorna, para cada aluno:
    total de aulas, presenças, faltas e percentuais.
    """
    tipo = request.args.get("tipo")

    # 1. Lista todos os arquivos de presença
    arquivos = github_list_files(f"{tipo}/frequencia/presencas")
    total_aulas = len(arquivos)

    # 2. Conta presenças por aluno
    contagem = {}  # nome -> nº de presenças
    for arq in arquivos:
        conteudo, _ = github_get(f"{tipo}/frequencia/presencas/{arq['name']}")
        if not conteudo:
            continue
        for nome in conteudo.splitlines():
            nome = nome.strip()
            if nome:
                contagem[nome] = contagem.get(nome, 0) + 1

    # 3. Monta resultado
    stats = {}
    for nome, presencas in contagem.items():
        faltas = total_aulas - presencas
        stats[nome] = {
            "presencas": presencas,
            "faltas": faltas,
            "pct_presenca": round(presencas / total_aulas * 100) if total_aulas else 0,
            "pct_falta":    round(faltas    / total_aulas * 100) if total_aulas else 0,
        }

    return jsonify({"total_aulas": total_aulas, "stats": stats})


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
    plano_url = f"https://github.com/{REPO}/blob/{BRANCH}/{tipo}/ensino/plano.md"
    aulas = github_list(f"{tipo}/ensino/aulas")
    aulas_urls = [
        {"nome": a, "url": f"https://github.com/{REPO}/blob/{BRANCH}/{tipo}/ensino/aulas/{a}"}
        for a in aulas
    ]
    return render_template("ensino.html", tipo=tipo, plano_url=plano_url, aulas=aulas_urls)


if __name__ == "__main__":
    app.run(debug=True)
