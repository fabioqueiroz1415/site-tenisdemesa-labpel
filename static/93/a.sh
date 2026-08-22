#!/bin/bash

# ============================================================
# CONFIGURAÇÃO
# ============================================================

# Depois de publicar o arquivo google_sheets_webapp.gs como Web App,
# cole aqui a URL terminada em /exec.
GOOGLE_SCRIPT_URL="https://script.google.com/macros/s/AKfycby3HHmaCzCAG3YjZ8N8Pg2_Fxv5pPIYXbamRZ67GmCHtqdG0yPb27030wNZ6oYPS4DKCg/exec"

# Token compartilhado com o Google Apps Script.
GOOGLE_SCRIPT_TOKEN="8Z-1VKXm5wKsvLFdFQwR4V-9o_s1tRMH"

# ------------------------------------------------------------
# Uso:
#   ./a.sh --7.2
#
# Exemplo:
#   linha da estação = 7  -> linha da planilha = 7 + 3 = 10
#   coluna da estação = 2 -> coluna da planilha = 2 + 1 = 3 = C
#   célula final: C10
# ------------------------------------------------------------

SPREADSHEET_ID="10x6nsDcMa8FqlaNHF37UnY0lf9V4AoQVwpGhybRHhEM"


internet_ok() {
    # Primeiro tenta HTTPS com ferramentas que já possam existir.
    if command -v curl >/dev/null 2>&1; then
        curl -fsS --connect-timeout 5 --max-time 8             https://clients3.google.com/generate_204 >/dev/null 2>&1
        return $?
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -q --spider --timeout=8             https://clients3.google.com/generate_204 >/dev/null 2>&1
        return $?
    fi

    # Fallback sem curl/wget: testa DNS + TCP/443.
    getent hosts google.com >/dev/null 2>&1 || return 1
    timeout 8 bash -c '</dev/tcp/google.com/443' >/dev/null 2>&1
}


pacote_instalado() {
    local pacote="$1"
    dpkg-query -W -f='${Status}' "$pacote" 2>/dev/null         | grep -q '^install ok installed$'
}


numero_para_coluna() {
    local n="$1"
    local resultado=""
    local resto letra

    while (( n > 0 )); do
        ((n--))
        resto=$((n % 26))
        printf -v letra "\\$(printf '%03o' $((65 + resto)))"
        resultado="${letra}${resultado}"
        n=$((n / 26))
    done

    printf '%s' "$resultado"
}


status_texto() {
    if "$@"; then
        printf 'ok'
    else
        printf 'nao ok'
    fi
}


# ============================================================
# VALIDAÇÃO DO PARÂMETRO
# ============================================================

if [[ $# -ne 1 || ! "$1" =~ ^--([0-9]+)\.([0-9]+)$ ]]; then
    echo "Uso: $0 --LINHA.COLUNA"
    echo "Exemplo: $0 --7.2"
    exit 2
fi

ESTACAO_LINHA="${BASH_REMATCH[1]}"
ESTACAO_COLUNA="${BASH_REMATCH[2]}"

PLANILHA_LINHA=$((10#$ESTACAO_LINHA + 3))
PLANILHA_COLUNA=$((10#$ESTACAO_COLUNA + 1))
PLANILHA_LETRA="$(numero_para_coluna "$PLANILHA_COLUNA")"
CELULA="${PLANILHA_LETRA}${PLANILHA_LINHA}"


echo "=============================================="
echo " Estação: ${ESTACAO_LINHA}.${ESTACAO_COLUNA}"
echo " Célula:  $CELULA"
echo "=============================================="
echo


# ============================================================
# INTERNET
# ============================================================

echo "==> Verificando conexão com a internet..."

if ! internet_ok; then
    echo
    echo "ERRO: não há conexão com a internet."
    echo "O processamento foi abortado. Nenhum pacote será instalado."
    exit 1
fi

echo "Internet: OK"
echo


# ============================================================
# INSTALAÇÃO
# ============================================================

echo "==> Configurando repositórios do Ubuntu..."
sudo sed -i     's/^Suites: noble$/Suites: noble noble-updates noble-backports/'     /etc/apt/sources.list.d/ubuntu.sources

echo
echo "==> Atualizando lista de pacotes..."
sudo apt update

echo
echo "==> Instalando GHC..."
sudo apt install -y ghc

echo
echo "==> Instalando dependências do VirtualBox..."
sudo apt install -y     build-essential     dkms     "linux-headers-$(uname -r)"     curl     gnupg

echo
echo "==> Adicionando chave GPG do VirtualBox..."
wget -qO- https://www.virtualbox.org/download/oracle_vbox_2016.asc     | gpg --dearmor     | sudo tee /usr/share/keyrings/oracle-virtualbox-2016.gpg >/dev/null

echo
echo "==> Adicionando repositório do VirtualBox..."
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/oracle-virtualbox-2016.gpg] https://download.virtualbox.org/virtualbox/debian noble contrib"     | sudo tee /etc/apt/sources.list.d/virtualbox.list >/dev/null

echo
echo "==> Atualizando lista de pacotes..."
sudo apt update

echo
echo "==> Instalando VirtualBox 7.2..."
sudo apt install -y virtualbox-7.2


# ============================================================
# VERIFICAÇÃO
# ============================================================

echo
echo "=============================================="
echo " VERIFICAÇÃO DOS PACOTES"
echo "=============================================="

GHC_STATUS="$(status_texto pacote_instalado ghc)"
VBOX_STATUS="$(status_texto pacote_instalado virtualbox-7.2)"

BUILD_STATUS="$(status_texto pacote_instalado build-essential)"
DKMS_STATUS="$(status_texto pacote_instalado dkms)"
HEADERS_STATUS="$(status_texto pacote_instalado "linux-headers-$(uname -r)")"

echo "ghc:                       $GHC_STATUS"
echo "virtualbox-7.2:            $VBOX_STATUS"
echo "build-essential:           $BUILD_STATUS"
echo "dkms:                      $DKMS_STATUS"
echo "linux-headers-$(uname -r): $HEADERS_STATUS"

RESULTADO="$(printf 'ghc: %s\nvirtualbox: %s' "$GHC_STATUS" "$VBOX_STATUS")"

echo
echo "Conteúdo a registrar em $CELULA:"
printf '%s\n' "$RESULTADO"


# ============================================================
# GOOGLE SHEETS
# ============================================================

echo
echo "==> Enviando resultado para o Google Sheets..."

if [[ -z "$GOOGLE_SCRIPT_URL" ]]; then
    echo
    echo "ERRO: GOOGLE_SCRIPT_URL ainda não foi configurada no início do arquivo."
    echo "A instalação/verificação terminou, mas o resultado NÃO foi enviado."
    exit 3
fi

# Escapa somente o necessário para este payload JSON.
RESULTADO_JSON="${RESULTADO//\\/\\\\}"
RESULTADO_JSON="${RESULTADO_JSON//\"/\\\"}"
RESULTADO_JSON="${RESULTADO_JSON//$'\n'/\\n}"

TMP_RESPOSTA="$(mktemp)"
trap 'rm -f "$TMP_RESPOSTA"' EXIT

# --data já faz a primeira requisição como POST.
# -L segue o redirecionamento usado pelo ContentService do Apps Script.
HTTP_CODE="$(
    curl -sS -L         --connect-timeout 10         --max-time 30         --proto '=https'         --proto-redir '=https'         -H 'Content-Type: application/json'         --data "{\"token\":\"$GOOGLE_SCRIPT_TOKEN\",\"spreadsheetId\":\"$SPREADSHEET_ID\",\"cell\":\"$CELULA\",\"value\":\"$RESULTADO_JSON\"}"         -o "$TMP_RESPOSTA"         -w '%{http_code}'         "$GOOGLE_SCRIPT_URL"
)"
CURL_STATUS=$?

RESPOSTA="$(cat "$TMP_RESPOSTA")"

if [[ $CURL_STATUS -ne 0 ]]; then
    echo "ERRO: falha de comunicação com o Google Apps Script (curl=$CURL_STATUS)."
    exit 4
fi

if [[ "$HTTP_CODE" == "401" ]]; then
    echo "ERRO HTTP 401: o Web App exige autenticação."
    echo "No Apps Script, publique como Web App com:"
    echo "  Executar como: Eu"
    echo "  Quem pode acessar: Qualquer pessoa"
    echo "A implantação precisa aceitar acesso anônimo."
    exit 4
fi

if [[ "$HTTP_CODE" == "403" ]]; then
    echo "ERRO HTTP 403: acesso ao Web App foi negado."
    echo "Confira a implantação e se ela permite acesso anônimo."
    exit 4
fi

if [[ ! "$HTTP_CODE" =~ ^2[0-9][0-9]$ ]]; then
    echo "ERRO HTTP $HTTP_CODE ao enviar para o Google Sheets."
    [[ -n "$RESPOSTA" ]] && echo "$RESPOSTA"
    exit 4
fi

if [[ "$RESPOSTA" == *'"ok":true'* ]]; then
    echo "Resultado salvo com sucesso na célula $CELULA."
else
    echo "ERRO: o Google Apps Script respondeu:"
    if [[ -n "$RESPOSTA" ]]; then
        echo "$RESPOSTA"
    else
        echo "(resposta vazia)"
    fi
    exit 5
fi
