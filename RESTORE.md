# Восстановление БД из бэкапа

Бэкапы лежат на сервере в `/opt/backups/smm/`.
Хранятся 30 дней, делаются автоматом каждый день в 4:00 ночи.

## Как откатиться

Зайди по SSH:
```
ssh root@193.233.232.200
```

Посмотри какие бэкапы есть:
```
ls -la /opt/backups/smm/
```

Выбери нужную дату из списка (например `smm_20260518_040000.db`).

Замени `ДАТА` в командах ниже на свою и выполни **по очереди**:

```
systemctl stop otlozhka-backend
cp /opt/backups/smm/smm_ДАТА.db /opt/smm-autoposter/backend/smm.db
tar xzf /opt/backups/smm/uploads_ДАТА.tar.gz -C /opt/smm-autoposter/backend/
systemctl start otlozhka-backend
systemctl status otlozhka-backend
```

Последняя команда должна показать `Active: active (running)` зелёным.

## Сделать бэкап прямо сейчас (вручную)

```
/opt/smm-autoposter/backup.sh
ls -la /opt/backups/smm/
```

## Если что-то сломалось

Посмотреть логи бэка:
```
journalctl -u otlozhka-backend -n 100
```

Перезапустить бэк:
```
systemctl restart otlozhka-backend
```

## Полный список полезного

```
# Логи бэка в реальном времени
journalctl -u otlozhka-backend -f

# Логи nginx (ошибки)
tail -50 /var/log/nginx/error.log

# Обновить код с GitHub
cd /opt/smm-autoposter
git pull
cd frontend && npm run build
systemctl restart otlozhka-backend

# Перезапустить nginx (после правки конфига)
nginx -t && systemctl reload nginx
```
