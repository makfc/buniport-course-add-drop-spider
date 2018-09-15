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
window_home = None
window_courseAddDrop = None
window_checkSections = None


######################################################

def open_in_new_tab(url):
    browser.execute_script(f'''window.open("{url}","_blank");''')


def cookie_setup():
    if os.path.exists(COOKIES_FILE_NAME):
        cookies = pickle.load(open(COOKIES_FILE_NAME, "rb"))
        for cookie in cookies:
            browser.driver.add_cookie(cookie)


def vist_home():
    global window_home

    # Visit URL
    browser.visit("https://buniport.hkbu.edu.hk")
    window_home = browser.driver.window_handles[0]
    browser.driver.switch_to_window(window_home)


def login():
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


def vist_courseAddDrop():
    global window_courseAddDrop
    browser.click_link_by_partial_text('增修/退修科目')
    time.sleep(1)
    window_courseAddDrop = browser.driver.window_handles[-1]
    # browser.windows.current = browser.windows.current.next
    browser.driver.switch_to_window(window_courseAddDrop)
    try:
        browser.is_element_present_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:imgEdit')
        return True
    except Exception as e:
        logger.error(e)

    return False


def switch_to_courseAddDrop_window_loop(is_reg_course=False):
    global is_logged_in, window_courseAddDrop
    while True:
        if bool(re.match("https://iss.hkbu.edu.hk/buam/(m/)?signForm.seam", browser.url)):
            is_logged_in = False
            login()

        elif bool(re.match("https://buniport03.hkbu.edu.hk", browser.url)):
            if not is_logged_in:
                # Update cookie file
                is_logged_in = True
                pickle.dump(browser.driver.get_cookies(), open(COOKIES_FILE_NAME, "wb"))
                logger.info('Login successful!')

            while True:
                if vist_courseAddDrop():
                    break
                browser.windows.current.close()
                time.sleep(2)
                browser.driver.switch_to_window(window_home)
                browser.reload()

            if is_reg_course:
                break

            check_sections_info()
            pass

        time.sleep(1)


isFull = True
found = False


def check_sections_info():
    global isFull, found, window_checkSections
    course_code = "LANG1026"
    open_in_new_tab(f"https://iss.hkbu.edu.hk/sisweb2/reg/sectionInfo.seam?acYear=2018&term=S1&subjCode={course_code}")
    time.sleep(1)
    # browser.windows.current = browser.windows.current.next
    window_checkSections = browser.driver.window_handles[-1]
    browser.driver.switch_to_window(window_checkSections)

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
                # 0     Section code
                # 2,4   Day/Time/Venue
                # 6     Instructor (Dept)
                # 7     Medium ofInstruction
                # 8     Available Quota
                #       Others
                #       Remarks
                text += f"{row[0]}|{row[2]}|{row[4]}|{row[6]}|{row[7]}|{row[8]}\n"
                text += "-" * 70 + '\n'
            if len(table_data) == 0:
                text = "All selected section full again!"
            else:
                text = f"{pageTitle}\n" + ("-" * 70) + f"\n{text}"
            logger.info(text)
            send_text(text)
            for row in table_data:
                reg_course(course_code, row[0], "#N-FREE-001")
            # send_screenshot()
        time.sleep(3)
        #browser.driver.switch_to_window(window_checkSections)
        browser.reload()


def reg_course(code, section, group=""):
    browser.driver.switch_to_window(window_home)
    vist_home()
    switch_to_courseAddDrop_window_loop(is_reg_course=True)
    # browser.visit("https://iss.hkbu.edu.hk/sisweb2/olreg/addDropEd.seam")
    while True:
        browser.is_element_present_by_id("addDrop:toAdd:0:s")
        browser.fill("addDrop:toAdd:0:s", code)
        browser.fill("addDrop:toAdd:0:lc", section)
        if group != "":
            browser.fill("addDrop:toAdd:0:sl", group)
        else:
            logger.info("group=""")
            browser.click_link_by_id("addDrop:toAdd:0:imgSL")

            pass
        browser.click_link_by_id("cmdSaveBottom")
        logger.info("Clicked cmdSaveBottom")
        time.sleep(3)
        browser.is_element_present_by_id("addDrop:tabValidRst", wait_time=30)
        logger.info("is_element_present_by_id")

        table_data = [[cell.text for cell in row("td")]
                      for row in BeautifulSoup(browser.html, "lxml")("tr")]
        submit_result = str(list(map(lambda x: re.sub('[\n\t]+', '\t', str(x).strip(' \t\n\r')), table_data[65])))
        logger.info(submit_result)
        send_text(submit_result)
        if len(table_data) > 67:
            submit_result = str(list(map(lambda x: re.sub('[\n\t]+', '\t', str(x).strip(' \t\n\r')), table_data[67])))
            send_text(submit_result)

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


cookie_setup()
while True:
    try:
        vist_home()
        is_logged_in = False
        switch_to_courseAddDrop_window_loop()
    except Exception as e:
        logger.error(e)
        while len(browser.windows) > 1:
            browser.windows.current.close_others()
# os.execl(sys.executable, sys.executable, *sys.argv)
