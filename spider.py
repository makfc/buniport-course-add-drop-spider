import os
import pickle
import re
import time

import config
import logging
from telegram.ext import Updater, CommandHandler

from selenium import webdriver
from splinter import Browser
import requests
from bs4 import BeautifulSoup

import json

# logging
logging.basicConfig(format='%(asctime)s - %(name)12s - %(levelname)s - %(message)s',
                    level=logging.INFO)
# logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
#                     level=logging.INFO)
logger = logging.getLogger(__name__)
######################################################


# Constant declaration
COOKIES_FILE_NAME = 'cookies.pkl'
######################################################


# Disable Google Chrome session restore functionality
preferences_path = config.chrome_profile_path + "/Default/Preferences"

with open(preferences_path, encoding='utf-8') as f:
    data = json.load(f)
data['profile']['exit_type'] = "None"
data['profile']['exited_cleanly'] = True

with open(preferences_path, 'w', encoding='utf-8') as f:
    f.write(json.dumps(data, ensure_ascii=False))
######################################################

# Telegram bot setup
updater = Updater(token=config.telegram_bot_token)

# Get the dispatcher to register handlers
dp = updater.dispatcher
bot = dp.bot


######################################################


def chrome_options_setup():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_extension('violentmonkey-2.9.5.crx')
    chrome_options.add_argument("user-data-dir=" + config.chrome_profile_path)
    chrome_options.add_argument("--disable-session-crashed-bubble")
    prefs = {"profile.default_content_setting_values.notifications": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    return chrome_options


browser = Browser('chrome', options=chrome_options_setup())


######################################################

def open_in_new_tab(url):
    browser.execute_script(f'''window.open("{url}","_blank");''')


def start():
    if os.path.exists(COOKIES_FILE_NAME):
        cookies = pickle.load(open(COOKIES_FILE_NAME, "rb"))
        for cookie in cookies:
            browser.driver.add_cookie(cookie)

    # Visit URL
    url = "https://buniport.hkbu.edu.hk"
    browser.visit(url)


def loop():
    global is_logged_in
    while True:
        if re.match("https://iss.hkbu.edu.hk/buam/(m/)?signForm.seam", browser.url):
            is_logged_in = False
            # browser.fill('signinForm:username', config.student_id)
            # browser.fill('signinForm:password', config.password)
            # browser.click_link_by_id('signinForm:submit')
            browser.execute_script(
                f"document.getElementById('signinForm:username').value = '{config.student_id}'")
            browser.execute_script(
                f"document.getElementById('signinForm:password').value = '{config.password}'")
            while len(browser.find_by_id('signinForm:recaptcha_response_field').value) != 4:
                pass
            browser.click_link_by_id('signinForm:submit')

        elif re.match("https://buniport03.hkbu.edu.hk", browser.url):
            if not is_logged_in:
                is_logged_in = True
                pickle.dump(browser.driver.get_cookies(), open(COOKIES_FILE_NAME, "wb"))
                logger.info('Login successful!')

                while True:
                    browser.click_link_by_partial_text('增修/退修科目')
                    time.sleep(1)
                    browser.windows.current = browser.windows.current.next
                    try:
                        browser.is_element_present_by_id('addDrop:tabAddDrop_lbl')
                        browser.click_link_by_id('addDrop:tabAddDrop_lbl')
                        # # browser.click_link_by_id('addDrop:imgEdit')
                        break
                    except Exception as e:
                        # logger.error(e)
                        browser.windows.current.close()
                        time.sleep(2)
                        browser.reload()

                check_section_info()
                pass

        time.sleep(1)


isFull = True
found = False


def check_section_info():
    global isFull, found
    open_in_new_tab("https://iss.hkbu.edu.hk/sisweb2/reg/sectionInfo.seam?acYear=2018&term=S1&subjCode=LANG1026")
    time.sleep(1)
    browser.windows.current = browser.windows.current.next

    old_list = []
    while True:
        bs = BeautifulSoup(browser.html, "lxml")
        pageTitle = bs(class_="pageTitle")[0].text
        table_data = [[cell.text for cell in row("td")]
                      for row in bs("tr")]
        # table_data[19][0](title="Not for Exchange Students")
        table_data = (filter(lambda x: len(x) == 14, table_data))
        table_data = (map(lambda x: [re.sub('[\n\t]+', '\t', str(y).strip(' \t\n\r')) for y in x], table_data))
        table_data = (filter(lambda x: int(x[0]) <= 34, table_data))
        table_data = list(filter(lambda x: x[8] != 'Full', table_data))
        if table_data != old_list:
            old_list = table_data
            text = ""
            for row in table_data:
                # 0     Section
                # 2,4   Day/Time/Venue
                # 6     Instructor (Dept)
                # 7     Medium ofInstruction
                # 8     Available Quota
                #       Others
                #       Remarks
                text += f"{row[0]}|{row[2]}|{row[4]}|{row[6]}|{row[7]}|{row[8]}\n"
                text += "-" * 70 + '\n'
            if text == "":
                text = "All selected section full again!"
            else:
                text = f"{pageTitle}\n" + ("-" * 70) + f"\n{text}"
            logger.info(text)
            send_text(text)
            # send_screenshot()
        time.sleep(3)
        browser.reload()


# def send_screenshot():
#     file_name = time.strftime("%Y%m%d-%H%M%S")
#     browser.driver.save_screenshot(f"{file_name}.pmg")
#     bot.send_document(config.self_user_id, document=open(file_name, 'rb'))


def send_text(message):
    bot.send_message(config.self_user_id, message)


def set_sessions(driver):
    request = requests.Session()
    headers = {
        "User-Agent":
            "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36"
    }
    request.headers.update(headers)
    cookies = driver.get_cookies()
    for cookie in cookies:
        request.cookies.set(cookie['name'], cookie['value'])

    return request


start()
while True:
    try:
        is_logged_in = False
        loop()
    except Exception as e:
        logger.error(e)
        while len(browser.windows) > 1:
            browser.windows.current.close_others()
        start()
# os.execl(sys.executable, sys.executable, *sys.argv)
