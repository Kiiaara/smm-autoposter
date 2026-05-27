import smtplib
import ssl
from email.message import EmailMessage
from config import settings


def send_login_code(to_email: str, code: str) -> None:
    """Отправляет 6-значный код на email через SMTP (mail.ru/yandex/...).
    Бросает исключение если SMTP не настроен или письмо не ушло."""
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError("SMTP не настроен на сервере (smtp_user/smtp_password)")

    msg = EmailMessage()
    msg["Subject"] = f"Код входа в Otlozhka: {code}"
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to_email
    msg.set_content(
        f"Ваш код для входа в Otlozhka ot Kiiara: {code}\n\n"
        f"Код действителен 5 минут. Если вы не запрашивали вход - просто проигнорируйте письмо."
    )
    # HTML версия для красоты
    msg.add_alternative(
        f"""<html><body style="font-family:sans-serif">
<h2 style="color:#7c3aed">Otlozhka ot Kiiara</h2>
<p>Код для входа:</p>
<div style="font-size:32px;font-weight:bold;letter-spacing:6px;background:#f3f4f6;padding:16px 24px;border-radius:8px;display:inline-block">{code}</div>
<p style="color:#666;margin-top:24px">Код действителен 5 минут.<br>Если вы не запрашивали вход - просто проигнорируйте письмо.</p>
</body></html>""",
        subtype="html",
    )

    context = ssl.create_default_context()
    # mail.ru/yandex - порт 465 SSL. Если 587 - SMTP+STARTTLS
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=15) as srv:
            srv.login(settings.smtp_user, settings.smtp_password)
            srv.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as srv:
            srv.starttls(context=context)
            srv.login(settings.smtp_user, settings.smtp_password)
            srv.send_message(msg)
