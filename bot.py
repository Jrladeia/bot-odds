import os
import time
import traceback
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# =========================
# CONFIG VIA VARIÁVEIS
# =========================
LOGIN_URL = os.getenv("LOGIN_URL", "https://app.previsao.io/")
MERCADO_URL = os.getenv(
    "MERCADO_URL",
    "https://app.previsao.io/evento/20903-market/rio-de-janeiro-rj-at-20903"
)

PREVISAO_USER = os.getenv("PREVISAO_USER", "")
PREVISAO_PASS = os.getenv("PREVISAO_PASS", "")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

ODD_ALERTA = float(os.getenv("ODD_ALERTA", "1.40"))
INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_SEGUNDOS", "2"))

MERCADO_NOME = os.getenv("MERCADO_NOME", "Rio de Janeiro")


ultimo_alerta_enviado = False


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


def fazer_login(driver):
    wait = WebDriverWait(driver, 30)
    driver.get(LOGIN_URL)

    # Ajuste os seletores se o HTML do site estiver diferente
    campo_email = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"]'))
    )
    campo_senha = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
    )

    campo_email.clear()
    campo_email.send_keys(PREVISAO_USER)

    campo_senha.clear()
    campo_senha.send_keys(PREVISAO_PASS)

    botao_entrar = driver.find_element(
        By.XPATH,
        "//button[contains(., 'Entrar') or contains(., 'Login') or contains(., 'Acessar')]"
    )
    botao_entrar.click()

    time.sleep(5)
    print("✅ Login realizado")


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
        fazer_login(driver)
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


if __name__ == "__main__":
    while True:
        try:
            loop_monitoramento()
        except Exception:
            erro = traceback.format_exc()
            print("❌ Erro geral:\n", erro)

            try:
                enviar_telegram(
                    "⚠️ *Bot reiniciando após erro*\n\n"
                    "Verifique os logs no Railway."
                )
            except Exception:
                pass

            time.sleep(10)
