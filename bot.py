import os
import time
import threading
import traceback
from datetime import datetime

import requests
from flask import Flask
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# =========================
# CONFIG VIA VARIÁVEIS
# =========================
MERCADO_URL = os.getenv(
    "MERCADO_URL",
    "https://app.previsao.io/evento/20903-market/rio-de-janeiro-rj-at-20903"
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

ODD_ALERTA = float(os.getenv("ODD_ALERTA", "1.15"))
INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_SEGUNDOS", "2"))
MERCADO_NOME = os.getenv("MERCADO_NOME", "Rio de Janeiro")

PORT = int(os.getenv("PORT", "10000"))

ultimo_alerta_enviado = False

app = Flask(__name__)


def criar_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    return driver


def enviar_telegram(texto: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não configurados.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "📊 Abrir mercado",
                        "url": MERCADO_URL
                    }
                ]
            ]
        }
    }

    resposta = requests.post(url, json=payload, timeout=15)
    print(f"Telegram status: {resposta.status_code} | {resposta.text}")


def enviar_alerta(odd: float):
    agora = datetime.now().strftime("%H:%M:%S")

    mensagem = (
        "🚨 ALERTA DE ODD 🚨\n\n"
        f"📍 Mercado: {MERCADO_NOME}\n"
        f"📈 Odd NÃO: *{odd:.2f}x*\n"
        f"🕒 Horário: {agora}\n\n"
        "⚡ Condição de entrada detectada!"
    )

    enviar_telegram(mensagem)
    print("✅ Alerta enviado no Telegram")


def enviar_status_inicial():
    mensagem = (
        "✅ *Bot iniciado na nuvem*\n\n"
        f"📍 Mercado: {MERCADO_NOME}\n"
        f"🎯 Alerta configurado para odd NÃO >= *{ODD_ALERTA:.2f}x*\n"
        f"🔗 Link monitorado:\n{MERCADO_URL}"
    )
    enviar_telegram(mensagem)


def abrir_mercado(driver):
    driver.get(MERCADO_URL)
    time.sleep(5)
    print("✅ Mercado carregado")


def pegar_odd_nao(driver):
    try:
        texto = driver.execute_script("""
            const botoes = document.querySelectorAll('button');

            for (let botao of botoes) {
                const texto = botao.innerText ? botao.innerText.trim() : '';
                if (texto.includes('Não')) {
                    return texto;
                }
            }
            return null;
        """)

        if not texto:
            return None

        if "(" in texto:
            numero = texto.split("(")[1].split("x")[0]
            numero = numero.replace(",", ".").strip()
            return float(numero)

        return None

    except Exception as e:
        print("Erro ao capturar odd:", e)
        return None


def loop_monitoramento():
    global ultimo_alerta_enviado

    driver = criar_driver()

    try:
        abrir_mercado(driver)
        enviar_status_inicial()

        while True:
            odd = pegar_odd_nao(driver)
            print("Odd NÃO:", odd)

            if odd is None:
                time.sleep(1)
                continue

            if odd >= ODD_ALERTA and not ultimo_alerta_enviado:
                enviar_alerta(odd)
                ultimo_alerta_enviado = True

            elif odd < ODD_ALERTA:
                ultimo_alerta_enviado = False

            time.sleep(INTERVALO_SEGUNDOS)

    finally:
        driver.quit()


def iniciar_bot():
    while True:
        try:
            loop_monitoramento()
        except Exception:
            erro = traceback.format_exc()
            print("❌ Erro geral:\n", erro)

            try:
                enviar_telegram(
                    "⚠️ *Bot reiniciando após erro*\n\n"
                    "Verifique os logs no Render."
                )
            except Exception:
                pass

            time.sleep(10)


@app.route("/")
def home():
    return "Bot rodando ✅"


if __name__ == "__main__":
    t = threading.Thread(target=iniciar_bot, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=PORT)
