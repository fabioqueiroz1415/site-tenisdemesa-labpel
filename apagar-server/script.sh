#!/bin/bash

# Define o nome da pasta e o caminho do arquivo
PASTA_DESTINO="/driver-mysql"
ARQUIVO_ZIP="mysql-connector-j-9.7.0.zip"
URL_DOWNLOAD="https://labpel.pythonanywhere.com/driver"

# Cria a pasta se ela não existir
echo "Criando a pasta $PASTA_DESTINO..."
mkdir -p "$PASTA_DESTINO"

# Entra na pasta criada
cd "$PASTA_DESTINO" || exit

# Baixa o arquivo zip
echo "Baixando o driver..."
curl -L -o "$ARQUIVO_ZIP" "$URL_DOWNLOAD"

# Verifica se o download foi bem-sucedido e se o arquivo não está vazio
if [ -f "$ARQUIVO_ZIP" ] && [ -s "$ARQUIVO_ZIP" ]; then
    echo "Download concluído. Extraindo o arquivo..."

    # Descompacta o arquivo zip
    unzip "$ARQUIVO_ZIP"

    # Remove o arquivo zip após a extração
    echo "Apagando o arquivo zip original..."
    rm "$ARQUIVO_ZIP"

    echo "Processo concluído com sucesso!"
else
    echo "Erro: Falha ao baixar o arquivo ou o arquivo está corrompido."
    exit 1
fi