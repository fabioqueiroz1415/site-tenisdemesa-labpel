from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from dotenv import load_dotenv
import requests
import base64
from datetime import datetime
import os
import re
import qrcode
import json
import socket
from io import BytesIO
import webbrowser
from tkinter import Tk, Label
from PIL import Image, ImageTk
import threading
import subprocess
import locale

# Configuração de locale para datas em português
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.utf8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        pass

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)

# ===================================================================
# PARTE 1 - APP PRINCIPAL (GitHub - Presença, Alunos, Ensino)
# ===================================================================

TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO", "fabioqueiroz1415/tenisdemesa-labpel")
BRANCH = os.getenv("GITHUB_BRANCH", "main")

BASE_URL = f"https://api.github.com/repos/{REPO}/contents"


@app.route("/a.sh", methods=["GET"])
def baixar_script():
    return send_file(
        "/home/labpel/site-tenisdemesa-labpel/static/93/a.sh",
        as_attachment=True,
        download_name="a.sh"
    )

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
    try:
        erro = r.json()
    except Exception:
        erro = {"message": r.text}
    return None, erro


def github_put(path, content_text, sha=None, message="update via flask"):
    url = f"{BASE_URL}/{path}"
    encoded = base64.b64encode(content_text.encode("utf-8")).decode("utf-8")
    payload = {"message": message, "content": encoded, "branch": BRANCH}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=get_headers(), json=payload)
    try:
        resposta = r.json()
    except Exception:
        resposta = {"message": r.text}
    return r.status_code in (200, 201), resposta


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


# -------------------------------------------------------------------
# Rotas do App Principal
# -------------------------------------------------------------------

@app.route("/")
def menu():
    return render_template("menu.html")


@app.route("/presenca")
def presenca():
    return render_template("presenca.html")


@app.route("/api/presenca/carregar")
def presenca_carregar():
    tipo = request.args.get("tipo")
    data = request.args.get("data")
    path = f"{tipo}/frequencia/presencas/{data}.txt"
    conteudo, sha_ou_erro = github_get(path)

    github_url = f"https://github.com/{REPO}/blob/{BRANCH}/{path}"

    return jsonify({
        "conteudo": conteudo or "",
        "sha": sha_ou_erro if conteudo else None,
        "caminho": path,
        "github_url": github_url
    })


@app.route("/api/presenca/salvar", methods=["POST"])
def presenca_salvar():
    dados = request.get_json()
    tipo = dados["tipo"]
    data = dados["data"]
    conteudo = dados["conteudo"]
    sha = dados.get("sha")
    path = f"{tipo}/frequencia/presencas/{data}.txt"

    if not sha:
        conteudo_atual, sha_atual = github_get(path)
        if conteudo_atual is not None:
            github_delete(
                path,
                sha_atual,
                message=f"apaga presença {tipo} {data} para recriar"
            )
            sha = None
        else:
            sha = None

    if not sha:
        ok, resp = github_put(
            path,
            conteudo,
            sha=None,
            message=f"presença {tipo} {data}"
        )
    else:
        ok, resp = github_put(
            path,
            conteudo,
            sha=sha,
            message=f"presença {tipo} {data}"
        )

    if ok:
        github_url = f"https://github.com/{REPO}/blob/{BRANCH}/{path}"
        return jsonify({
            "ok": True,
            "github": resp,
            "github_url": github_url
        })

    return jsonify({"ok": False, "github": resp})


@app.route("/api/presenca/estatisticas")
def presenca_estatisticas():
    tipo = request.args.get("tipo")
    arquivos = github_list_files(f"{tipo}/frequencia/presencas")
    total_aulas = len(arquivos)

    contagem = {}

    for arq in arquivos:
        conteudo, _ = github_get(
            f"{tipo}/frequencia/presencas/{arq['name']}"
        )
        if not conteudo:
            continue

        for nome in conteudo.splitlines():
            nome = nome.strip()
            if nome:
                contagem[nome] = contagem.get(nome, 0) + 1

    stats = {}

    for nome, presencas in contagem.items():
        faltas = total_aulas - presencas
        stats[nome] = {
            "presencas": presencas,
            "faltas": faltas,
            "pct_presenca": round(presencas / total_aulas * 100)
            if total_aulas else 0,
            "pct_falta": round(faltas / total_aulas * 100)
            if total_aulas else 0,
        }

    return jsonify({
        "total_aulas": total_aulas,
        "stats": stats
    })


@app.route("/api/presenca/criar_arquivo", methods=["POST"])
def presenca_criar_arquivo():
    dados = request.get_json()
    tipo = dados["tipo"]
    data = dados["data"]

    path_alunos = f"{tipo}/frequencia/alunos.txt"
    conteudo_alunos, _ = github_get(path_alunos)

    if not conteudo_alunos:
        return jsonify({
            "ok": False,
            "error": "Nenhum aluno cadastrado nesta turma"
        }), 400

    lista_alunos = [
        n.strip()
        for n in conteudo_alunos.splitlines()
        if n.strip()
    ]

    if not lista_alunos:
        return jsonify({
            "ok": False,
            "error": "Lista de alunos vazia"
        }), 400

    path_presenca = f"{tipo}/frequencia/presencas/{data}.txt"
    conteudo_presenca = "\n".join(lista_alunos) + "\n"

    ok, resp = github_put(
        path_presenca,
        conteudo_presenca,
        message=f"cria presença {tipo} {data} com todos os alunos"
    )

    if ok:
        github_url = f"https://github.com/{REPO}/blob/{BRANCH}/{path_presenca}"
        return jsonify({
            "ok": True,
            "github_url": github_url,
            "caminho": path_presenca
        })

    return jsonify({
        "ok": False,
        "error": resp
    }), 500


@app.route("/api/presenca/listar_arquivos")
def presenca_listar_arquivos():
    tipo = request.args.get("tipo")
    arquivos = github_list_files(f"{tipo}/frequencia/presencas")

    resultado = []

    for arq in arquivos:
        nome = arq["name"]

        if nome.endswith(".txt"):
            data = nome.replace(".txt", "")
            resultado.append({
                "nome": nome,
                "data": data,
                "download_url": arq.get("download_url")
            })

    return jsonify({"arquivos": resultado})


# -------------------------------------------------------------------
# NOVO: períodos
# -------------------------------------------------------------------

PERIODOS_PATH = "static/periodos.txt"


def converter_data_periodo(valor):
    """
    Converte DD-MM-AA para objeto date.
    Datas com ano de 00-68 são tratadas como 2000-2068.
    Datas com ano de 69-99 são tratadas como 1969-1999.
    """
    try:
        return datetime.strptime(valor.strip(), "%d-%m-%y").date()
    except ValueError:
        return None


def formatar_data_periodo(data):
    """
    Formato visual:
    25 ago 2026
    """
    meses = [
        "jan", "fev", "mar", "abr", "mai", "jun",
        "jul", "ago", "set", "out", "nov", "dez"
    ]
    return f"{data.day:02d} {meses[data.month - 1]} {data.year:04d}"


def carregar_periodos():
    conteudo, erro = github_get(PERIODOS_PATH)

    if conteudo is None:
        return [], erro

    periodos = []

    for numero_linha, linha in enumerate(conteudo.splitlines(), start=1):
        linha = linha.strip()

        # Linhas vazias e comentários são ignorados.
        if not linha or linha.startswith("#"):
            continue

        partes = linha.split()

        if len(partes) < 3:
            continue

        nome = " ".join(partes[:-2])
        inicio_texto = partes[-2]
        fim_texto = partes[-1]

        inicio = converter_data_periodo(inicio_texto)
        fim = converter_data_periodo(fim_texto)

        if inicio is None or fim is None:
            continue

        periodos.append({
            "nome": nome,
            "inicio": inicio_texto,
            "fim": fim_texto,
            "inicio_iso": inicio.isoformat(),
            "fim_iso": fim.isoformat(),
            "inicio_formatado": formatar_data_periodo(inicio),
            "fim_formatado": formatar_data_periodo(fim),
            "rotulo": (
                f"{nome} "
                f"({formatar_data_periodo(inicio)} a "
                f"{formatar_data_periodo(fim)})"
            )
        })

    return periodos, None


@app.route("/api/periodos")
def periodos():
    lista, erro = carregar_periodos()

    if erro is not None:
        return jsonify({
            "ok": False,
            "periodos": [],
            "erro": erro,
            "github_url": f"https://github.com/{REPO}/blob/{BRANCH}/{PERIODOS_PATH}"
        }), 500

    return jsonify({
        "ok": True,
        "periodos": lista,
        "github_url": f"https://github.com/{REPO}/blob/{BRANCH}/{PERIODOS_PATH}"
    })


# -------------------------------------------------------------------
# NOVO: histórico completo, permitindo filtrar por período no cliente
# -------------------------------------------------------------------

def data_arquivo_para_date(nome):
    """
    Recebe, por exemplo, 25-08-26.txt e devolve date.
    """
    texto = nome[:-4] if nome.endswith(".txt") else nome
    try:
        return datetime.strptime(texto, "%d-%m-%y").date()
    except ValueError:
        return None


@app.route("/api/presenca/historico")
def presenca_historico():
    tipo = request.args.get("tipo")

    if not tipo:
        return jsonify({
            "ok": False,
            "error": "Turma não informada"
        }), 400

    path_alunos = f"{tipo}/frequencia/alunos.txt"
    conteudo_alunos, erro_alunos = github_get(path_alunos)

    alunos = [
        n.strip()
        for n in (conteudo_alunos or "").splitlines()
        if n.strip()
    ]

    arquivos = github_list_files(f"{tipo}/frequencia/presencas")

    registros = []

    for arq in arquivos:
        nome_arquivo = arq["name"]

        if not nome_arquivo.endswith(".txt"):
            continue

        data = data_arquivo_para_date(nome_arquivo)

        if data is None:
            continue

        conteudo, _ = github_get(
            f"{tipo}/frequencia/presencas/{nome_arquivo}"
        )

        presentes = set()

        if conteudo:
            presentes = {
                nome.strip()
                for nome in conteudo.splitlines()
                if nome.strip()
            }

        registros.append({
            "nome": nome_arquivo,
            "data": data.isoformat(),
            "data_br": nome_arquivo[:-4],
            "presentes": list(presentes)
        })

    registros.sort(key=lambda item: item["data"])

    # Se o arquivo alunos.txt estiver vazio, usa os nomes encontrados
    # nas próprias listas de presença.
    if not alunos:
        encontrados = set()
        for registro in registros:
            encontrados.update(registro["presentes"])
        alunos = sorted(encontrados, key=str.lower)

    datas = [registro["data_br"] for registro in registros]

    presencas_por_aluno = {
        aluno: {
            registro["data_br"]: aluno in set(registro["presentes"])
            for registro in registros
        }
        for aluno in alunos
    }

    return jsonify({
        "ok": True,
        "alunos": alunos,
        "datasDisponiveis": datas,
        "registros": registros,
        "presencasPorAluno": presencas_por_aluno,
        "totalAulas": len(registros)
    })


# -------------------------------------------------------------------
# Alunos
# -------------------------------------------------------------------

@app.route("/alunos")
def alunos():
    return render_template("alunos.html")


@app.route("/api/alunos/carregar")
def alunos_carregar():
    tipo = request.args.get("tipo")
    path = f"{tipo}/frequencia/alunos.txt"
    conteudo, sha_ou_erro = github_get(path)

    lista = [
        n.strip()
        for n in (conteudo or "").splitlines()
        if n.strip()
    ]

    erro = sha_ou_erro if conteudo is None else None
    github_url = f"https://github.com/{REPO}/blob/{BRANCH}/{path}"

    return jsonify({
        "alunos": lista,
        "sha": sha_ou_erro if conteudo else None,
        "erro": erro,
        "caminho": path,
        "github_url": github_url
    })


@app.route("/api/alunos/salvar", methods=["POST"])
def alunos_salvar():
    dados = request.get_json()
    tipo = dados["tipo"]
    lista = dados["alunos"]
    sha = dados.get("sha") or None

    conteudo = "\n".join(lista) + "\n"
    path = f"{tipo}/frequencia/alunos.txt"

    ok, resp = github_put(
        path,
        conteudo,
        sha=sha,
        message=f"alunos {tipo} atualizados"
    )

    return jsonify({"ok": ok, "github": resp})


# -------------------------------------------------------------------
# Ensino
# -------------------------------------------------------------------

@app.route("/ensino")
def ensino():
    tipo = request.args.get("tipo", "iniciacao")
    data = request.args.get("data")
    numero = request.args.get("numero")
    listar = request.args.get("listar", "false")

    return render_template(
        "ensino.html",
        tipo_param=tipo,
        data_param=data,
        numero_param=numero,
        listar_param=listar
    )


@app.route("/api/ensino/listar_aulas")
def ensino_listar_aulas():
    tipo = request.args.get("tipo", "iniciacao")
    aulas = github_list(f"{tipo}/ensino/aulas")

    aulas_formatadas = []
    numeros = []

    for aula in aulas:
        match = re.match(r"Aula(\d+)-(\d{2}-\d{2}-\d{2})\.md", aula)

        if match:
            numero = match.group(1)
            data = match.group(2)
            numeros.append(int(numero))

            aulas_formatadas.append({
                "nome": aula,
                "data": data,
                "numero": numero
            })

        else:
            match_num = re.match(r"Aula(\d+)", aula)

            if match_num:
                numero = match_num.group(1)
                numeros.append(int(numero))

                aulas_formatadas.append({
                    "nome": aula,
                    "data": "",
                    "numero": numero
                })

    maior_numero = max(numeros) if numeros else 0

    return jsonify({
        "aulas": aulas_formatadas,
        "maior_numero": maior_numero,
        "total": len(aulas)
    })


@app.route("/api/ensino/carregar_aula")
def ensino_carregar_aula():
    tipo = request.args.get("tipo", "iniciacao")
    data = request.args.get("data")
    numero = request.args.get("numero")

    if numero:
        nome_arquivo = f"Aula{numero}-{data}.md"
    else:
        aulas = github_list(f"{tipo}/ensino/aulas")

        for aula in aulas:
            if data in aula:
                nome_arquivo = aula
                break
        else:
            return jsonify({
                "exists": False,
                "message": "Nenhuma aula encontrada para esta data"
            })

    path = f"{tipo}/ensino/aulas/{nome_arquivo}"
    conteudo, sha = github_get(path)

    if conteudo is not None:
        match = re.match(r"Aula(\d+)", nome_arquivo)
        numero_aula = match.group(1) if match else ""

        return jsonify({
            "exists": True,
            "conteudo": conteudo,
            "sha": sha,
            "nome_arquivo": nome_arquivo,
            "numero": numero_aula,
            "url": (
                f"https://github.com/{REPO}/blob/{BRANCH}/"
                f"{tipo}/ensino/aulas/{nome_arquivo}"
            )
        })

    return jsonify({
        "exists": False,
        "message": "Aula não encontrada"
    })


@app.route("/api/ensino/criar_aula", methods=["POST"])
def ensino_criar_aula():
    dados = request.get_json()
    tipo = dados["tipo"]
    data = dados["data"]
    numero = dados["numero"]

    template = f"""# Aula {numero} - {data}

## Objetivos da Aula
- Objetivo 1
- Objetivo 2
- Objetivo 3

## Conteúdo Programático
1. Tópico 1
2. Tópico 2
3. Tópico 3

## Atividades Práticas
- Atividade 1
- Atividade 2
- Atividade 3

## Observações pós aula

nenhuma observação.
"""

    nome_arquivo = f"Aula{numero}-{data}.md"
    path = f"{tipo}/ensino/aulas/{nome_arquivo}"

    ok, resp = github_put(
        path,
        template,
        message=f"Criada aula {numero} para turma {tipo} - {data}"
    )

    if ok:
        return jsonify({
            "ok": True,
            "nome_arquivo": nome_arquivo,
            "url": (
                f"https://github.com/{REPO}/blob/{BRANCH}/"
                f"{tipo}/ensino/aulas/{nome_arquivo}"
            )
        })

    return jsonify({"ok": False, "error": resp})


# ===================================================================
# PARTE 2 - APP SECUNDÁRIO (Placar, Campeonatos, Partidas)
# ===================================================================

placar = {
    "quem-saca": 1,
    "pontos1": 0,
    "pontos2": 0,
    "set1": 0,
    "set2": 0,
    "cronometro": 0,
    "qr-code": 0
}

partida = {
    "nome1": "undefined",
    "nome2": "undefined",
    "numero1": 2,
    "numero2": 1,
    "rodada": -1,
    "partida": -1,
    "situacao": 0
}

data_campeonato = '17-ago-24'


def get_rota_servidor():
    try:
        result = subprocess.run(
            ['hostname', '-I'],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            local_ip = result.stdout.strip().split()[0]
        else:
            result = subprocess.run(
                ['ipconfig'],
                capture_output=True,
                text=True
            )
            local_ip = "127.0.0.1"

    except Exception:
        local_ip = "127.0.0.1"

    return f"http://{local_ip}:5000"


def generate_qr_rota(rota="/"):
    site_url = f"{get_rota_servidor()}{rota}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=2
    )

    qr.add_data(site_url)
    qr.make(fit=True)

    return qr.make_image(
        fill_color="black",
        back_color="white"
    )


def generate_qr_rota_str(rota="/"):
    img = generate_qr_rota(rota)
    buffered = BytesIO()
    img.save(buffered, format="png")

    return base64.b64encode(
        buffered.getvalue()
    ).decode('utf-8')


def show_qr_code(qr, title, duration):
    root = Tk()
    root.title(title)

    qr_image = ImageTk.PhotoImage(qr)

    label = Label(root, image=qr_image)
    label.pack()

    window_width = qr_image.width()
    window_height = qr_image.height()

    screen_width = root.winfo_screenwidth()

    position_x = int(
        (screen_width / 2) -
        (window_width / 2) +
        40
    )

    position_y = 20

    root.geometry(
        f'{window_width}x{window_height}+'
        f'{position_x}+{position_y}'
    )

    root.after(duration, root.destroy)
    root.mainloop()


def show_qr_code_in_thread(
    qr,
    title="QR Code",
    duration=10000
):
    thread = threading.Thread(
        target=show_qr_code,
        args=(qr, title, duration)
    )
    thread.start()


@app.route('/placar')
def funcao_placar():
    rota = "/links"
    qr_code_image = generate_qr_rota_str(rota)
    rota_servidor = f"{get_rota_servidor()}{rota}"

    return render_template(
        'placar/placar.html',
        placar=placar
    )


@app.route('/controle')
def controle():
    return render_template(
        'placar/controle.html',
        placar=placar,
        partida=partida
    )


@app.route('/links')
def links():
    html_links = {
        "configurar partida": "/partida-unica",
        "placar": "/placar",
        "controle": "/controle"
    }

    keys = list(html_links.keys())
    qr_codes = {}

    for key in keys:
        qr_codes[key] = generate_qr_rota_str(
            html_links[key]
        )

    return render_template(
        'placar/links.html',
        links=html_links,
        qr_codes=qr_codes
    )


@app.route('/post-placar', methods=['POST'])
def post_placar():
    data = request.json

    global placar
    placar = data

    if placar['qr-code'] == 1:
        show_qr_code_in_thread(
            generate_qr_rota("/links"),
            "/links",
            10000
        )

    return jsonify(placar)


@app.route('/get-placar', methods=['GET'])
def get_placar():
    global placar
    return jsonify(placar)


@app.route('/get-partida', methods=['GET'])
def get_partida():
    global partida
    return jsonify(partida)


@app.route('/post-partida', methods=['POST'])
def post_partida():
    data = request.json

    global partida
    partida = data

    return jsonify({
        "status": "success",
        "placar": placar
    })


@app.route('/partida-unica')
def partida_unica():
    global partida

    partida["partida"] = "única"
    partida["rodada"] = "única"

    return render_template(
        'placar/partida_unica.html',
        placar=placar,
        partida=partida
    )


@app.route('/reiniciar-partida-unica', methods=['POST'])
def reiniciar_partida_unica():
    global placar, partida

    placar = {
        "quem-saca": 1,
        "pontos1": 0,
        "pontos2": 0,
        "set1": 0,
        "set2": 0,
        "cronometro": 0,
        "qr-code": 0
    }

    partida.update({
        "nome1": partida.get("nome1", "Jogador 1"),
        "nome2": partida.get("nome2", "Jogador 2"),
        "numero1": 1,
        "numero2": 2,
        "rodada": "única",
        "partida": "única",
        "situacao": 0
    })

    return jsonify({"status": "success"})


@app.route('/atualizar-nomes-partida-unica', methods=['POST'])
def atualizar_nomes_partida_unica():
    global partida

    data = request.json

    if 'nome1' in data:
        partida['nome1'] = data['nome1']

    if 'nome2' in data:
        partida['nome2'] = data['nome2']

    partida['rodada'] = "única"
    partida['partida'] = "única"

    return jsonify({
        "status": "success",
        "partida": partida
    })


# ===================================================================
# HISTÓRICO
# ===================================================================

@app.route("/historico")
def historico():
    return render_template("historico.html")


if __name__ == "__main__":
    app.run(
        debug=True,
        host='0.0.0.0'
    )
