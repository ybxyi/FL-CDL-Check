import logging
import os
import tempfile
import requests
from twocaptcha import TwoCaptcha
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv
import os

# Загружаем переменные из .env
load_dotenv()

# Получаем API-ключ
API_KEY = os.getenv("CAPTCHA_API_KEY")
if not API_KEY:
    raise ValueError("CAPTCHA_API_KEY environment variable is not set")

# Инициализация 2Captcha
solver = TwoCaptcha(API_KEY)

# Настройки логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция скачивания капчи
def download_captcha(captcha_url):
    response = requests.get(captcha_url)
    if response.status_code == 200:
        captcha_path = os.path.join(tempfile.gettempdir(), "captcha.png")
        with open(captcha_path, "wb") as f:
            f.write(response.content)
        return captcha_path
    return None

# Функция решения капчи через 2Captcha
def solve_captcha_2captcha(image_path):
    try:
        result = solver.normal(image_path)
        return result['code']
    except Exception as e:
        logger.error(f"Ошибка распознавания капчи: {e}")
        return None

# Функция старта бота
async def start(update: Update, context):
    await update.message.reply_text("Привет! Введи свой CDL номер.")

# Функция обработки сообщения с CDL
async def handle_message(update: Update, context):
    cdl_number = update.message.text.strip()

    # Настройки Selenium
    chrome_options = Options()
    chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 1})
    service = Service(ChromeDriverManager().install())

    # Инициализация драйвера
    driver = webdriver.Chrome(service=service, options=chrome_options)

    captcha_path = None 
    screenshot_path = None

    try:
        driver.get("https://services.flhsmv.gov/dlcheck/")  # Исправленный вызов метода
        logger.info("Страница загружена.")
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "MainContent_txtDLNumber"))).send_keys(cdl_number)
        
        # Загружаем капчу
        captcha_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.LBD_CaptchaImageDiv img")))
        captcha_url = captcha_element.get_attribute("src")
        
        captcha_path = download_captcha(captcha_url)
        if not captcha_path:
            raise Exception("Ошибка загрузки капчи")
        
        # Распознаем капчу через 2Captcha
        captcha_text = solve_captcha_2captcha(captcha_path)
        if not captcha_text:
            raise Exception("Ошибка распознавания капчи через 2Captcha")

        # Ввод капчи и отправка формы
        driver.find_element(By.ID, "MainContent_txtCaptchaCode").send_keys(captcha_text)
        driver.find_element(By.ID, "MainContent_btnEnter").click()
        
        # Ожидание результата
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "MainContent_lblHeaderMessage")))

        result = driver.find_element(By.ID, "MainContent_lblHeaderMessage").text

        # Скриншот результата
        screenshot_path = os.path.join(tempfile.gettempdir(), "result.png")
        driver.save_screenshot(screenshot_path)

        # Отправка результата
        await update.message.reply_text(f"Результат проверки: {result}")
        with open(screenshot_path, 'rb') as screenshot:
            await update.message.reply_photo(photo=screenshot)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"Ошибка: {str(e)}")

    finally:
    driver.quit()
    if captcha_path and os.path.exists(captcha_path):
        os.remove(captcha_path)
    if screenshot_path and os.path.exists(screenshot_path):
        os.remove(screenshot_path)

# Запуск бота
def main():
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token("TELEGRAM_BOT_TOKEN").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
