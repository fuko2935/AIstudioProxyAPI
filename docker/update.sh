#!/bin/bash

# Yeniden kullanmak için renk değişkenlerini tanımla
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

set -e

echo -e "${GREEN}==> Hizmet güncelleniyor ve yeniden başlatılıyor...${NC}"

# 获取脚本所在的目录，并切换到项目根目录
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR/.."

echo -e "${YELLOW}--> Adım 1/4: En güncel kod çekiliyor...${NC}"
git pull

cd "$SCRIPT_DIR"

echo -e "${YELLOW}--> Adım 2/4: Eski konteynerler durdurulup kaldırılıyor...${NC}"
docker compose down

echo -e "${YELLOW}--> Adım 3/4: Docker Compose ile yeni konteynerler oluşturulup başlatılıyor...${NC}"
docker compose up -d --build

echo -e "${YELLOW}--> Adım 4/4: Çalışan konteynerlerin durumu gösteriliyor...${NC}"
docker compose ps

echo -e "${GREEN}==> Güncelleme tamamlandı!${NC}"
