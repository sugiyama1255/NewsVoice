#!/usr/bin/env bash
set -euo pipefail

APP=/home/hisatsugu/apps/newsvoice
DOMAIN=newsvoice.simoyakaviewer.com

install -m 0644 "$APP/deploy/newsvoice.service" /etc/systemd/system/newsvoice.service
systemctl daemon-reload
systemctl enable --now newsvoice.service
systemctl status newsvoice.service --no-pager -l

install -m 0644 "$APP/deploy/newsvoice.nginx" /etc/nginx/sites-available/newsvoice
ln -sfn /etc/nginx/sites-available/newsvoice /etc/nginx/sites-enabled/newsvoice
nginx -t
systemctl reload nginx

certbot --nginx -d "$DOMAIN"
nginx -t
systemctl reload nginx

curl -I "https://$DOMAIN/"
