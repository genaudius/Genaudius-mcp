#!/bin/bash
# SSL renewal — ejecutado diariamente por cron
cd /opt/genaudius/vps
docker-compose --profile ssl run --rm certbot renew --quiet
docker-compose exec nginx nginx -s reload
