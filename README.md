#
# Labpel - Tênis de Mesa 🏓

Este é um site que fiz para ajudar na organização das aulas de tênis de mesa do **Labpel**.

A ideia é deixar as coisas mais simples, reunindo presença dos alunos, histórico das aulas, conteúdos de ensino e um placar para partidas.

## O que o site faz

- registra a presença dos alunos;
- mostra o histórico de presença;
- organiza as aulas e conteúdos;
- cria arquivos de aula em Markdown;
- possui placar para partidas de tênis de mesa;
- tem uma página separada para controlar o placar;
- gera QR Codes para acessar algumas páginas pelo celular;
- salva e lê algumas informações usando a API do GitHub.

## Tecnologias usadas

- Python
- Flask
- HTML
- CSS
- JavaScript
- API do GitHub

## Como rodar

Instale as dependências:

```bash
pip install flask requests python-dotenv qrcode pillow
```

Depois execute:

```bash
python app.py
```

O site ficará disponível normalmente em:

```text
http://localhost:5000
```

## Configuração

Crie um arquivo `.env` na pasta do projeto:

```env
GITHUB_TOKEN=seu_token
GITHUB_REPO=usuario/repositorio
GITHUB_BRANCH=main
```

O token é usado para o sistema conseguir ler e salvar arquivos no GitHub.

## Páginas principais

```text
/           Menu principal
/historico  Histórico dos alunos
/ensino     Aulas e conteúdos
/links      Links do placar
/placar     Placar
/controle   Controle do placar
```

## Sobre

Esse projeto foi criado para facilitar a organização das atividades de tênis de mesa do Labpel e também para eu praticar programação web com Python e Flask.
