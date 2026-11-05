#!/usr/bin/env bash
# Instala ou atualiza o OdontoDesk em Python na máquina virtual (Ubuntu/Debian), ao lado do Servidor OdontoDesk atual.
# Usa o MESMO banco: se /etc/odontodesk/servidor.json existir (servidor atual), os dados do banco são aproveitados.
# O site escuta só dentro da máquina (127.0.0.1:8650); os aparelhos chegam pelo Tailscale, com HTTPS, na porta 8443.
#
# Uso, na pasta onde extraiu o OdontoDesk-Python.zip:
#     sudo bash odontodesk-py/nuvem/instalar.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Rode com sudo:  sudo bash $0"; exit 1; }
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST=/opt/odontodesk-py
CONF=/etc/odontodesk/python.json
SVC=odontodesk-python
PORTA=8650
passo() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }

passo "1/5 Python"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv >/dev/null
python3 --version

passo "2/5 Arquivos em $DEST"
id odontodesk >/dev/null 2>&1 || useradd --system --home-dir /opt/odontodesk --shell /usr/sbin/nologin odontodesk
mkdir -p "$DEST" /etc/odontodesk
find "$DEST" -mindepth 1 -maxdepth 1 ! -name venv -exec rm -rf {} +
tar -C "$SRC" --exclude=./venv --exclude=./config.json --exclude='*.db' --exclude=./testes -cf - . | tar -C "$DEST" -xf -
[ -d "$DEST/venv" ] || python3 -m venv "$DEST/venv"
"$DEST/venv/bin/pip" install -q --upgrade pip
"$DEST/venv/bin/pip" install -q -r "$DEST/requirements.txt"
chown -R root:root "$DEST"

passo "3/5 Configuração ($CONF)"
if [ ! -f "$CONF" ]; then
  if [ -f /etc/odontodesk/servidor.json ]; then
    echo "Aproveitando os dados do banco do Servidor OdontoDesk (/etc/odontodesk/servidor.json)."
    "$DEST/venv/bin/python" - "$CONF" <<'PY'
import json, secrets, sys
s = json.load(open("/etc/odontodesk/servidor.json"))
m = s.get("mysql") or {}
cfg = {"banco": {"tipo": "mysql", "host": m.get("host"), "porta": m.get("port") or 3306, "nome": m.get("database") or "odontodesk",
                 "usuario": m.get("user"), "senha": m.get("password") or ""},
       "chave_secreta": secrets.token_hex(32), "computador": "WEB-PYTHON", "fuso": "America/Sao_Paulo",
       "endereco": "127.0.0.1", "porta": 8650, "https": True}
open(sys.argv[1], "w").write(json.dumps(cfg, indent=2, ensure_ascii=False))
PY
  else
    ODONTODESK_PY_CONFIG="$CONF" "$DEST/venv/bin/python" -c "import sys; sys.argv=['x','--configurar']; sys.path.insert(0,'$DEST'); import executar; executar.configurar()"
    "$DEST/venv/bin/python" - "$CONF" <<'PY'
import json, sys
c = json.load(open(sys.argv[1])); c.update(endereco="127.0.0.1", porta=8650, https=True); open(sys.argv[1], "w").write(json.dumps(c, indent=2, ensure_ascii=False))
PY
  fi
else
  echo "Configuração existente mantida."
fi
chown odontodesk:odontodesk "$CONF"; chmod 600 "$CONF"
chown root:odontodesk /etc/odontodesk; chmod 750 /etc/odontodesk

passo "4/5 Serviço (inicia sozinho e reinicia se cair)"
cat > /etc/systemd/system/$SVC.service <<UNIT
[Unit]
Description=OdontoDesk em Python (sistema web)
After=network-online.target
Wants=network-online.target

[Service]
User=odontodesk
Group=odontodesk
WorkingDirectory=$DEST
Environment=ODONTODESK_PY_CONFIG=$CONF
ExecStart=$DEST/venv/bin/python $DEST/executar.py
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable $SVC >/dev/null 2>&1
systemctl restart $SVC
sleep 3
systemctl is-active --quiet $SVC || { echo "O serviço não iniciou:"; journalctl -u $SVC -n 30 --no-pager; exit 1; }

passo "5/5 Endereço com HTTPS (Tailscale, porta 8443)"
command -v tailscale >/dev/null || { echo "Tailscale não instalado. Rode antes o instalador do Servidor OdontoDesk (odontodesk/nuvem/instalar.sh)."; exit 1; }
tailscale serve --bg --https=8443 "http://127.0.0.1:$PORTA"
NOME=$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')
cat <<FIM

Pronto! OdontoDesk em Python funcionando.

  Abra no navegador (computador, celular ou tablet com o Tailscale ligado):
      https://$NOME:8443

  - Entre com o mesmo usuário e senha do OdontoDesk do computador.
  - Ver o funcionamento:  sudo journalctl -u $SVC -f
  - Atualizar: envie o zip novo, extraia por cima e rode de novo este comando.
FIM
