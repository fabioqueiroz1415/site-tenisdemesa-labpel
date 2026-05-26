#!/bin/bash
echo "Mensagem do commit: $1"
msg=$1
git add .
git commit -m "$msg"
git push
echo "----- fim. -------"