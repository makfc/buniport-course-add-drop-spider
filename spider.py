import os
import pickle
import re
import time
import config
import logging

from selenium import webdriver
from splinter import Browser

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


# web_driver_setup
chrome_options = webdriver.ChromeOptions()
chrome_options.add_extension('violentmonkey-2.9.5.crx')
chrome_options.add_argument("user-data-dir=" + config.chrome_profile_path)
chrome_options.add_argument("--disable-session-crashed-bubble")
prefs = {"profile.default_content_setting_values.notifications": 2}
chrome_options.add_experimental_option("prefs", prefs)
browser = Browser('chrome', options=chrome_options)


######################################################

def start():
    if os.path.exists(COOKIES_FILE_NAME):
        cookies = pickle.load(open(COOKIES_FILE_NAME, "rb"))
        for cookie in cookies:
            browser.driver.add_cookie(cookie)

    # Visit URL
    url = "https://buniport.hkbu.edu.hk"
    browser.visit(url)


def loop():
    is_logged_in = False
    while True:
        if re.match("https://iss.hkbu.edu.hk/buam/(m/)?signForm.seam.*", browser.url):
            is_logged_in = False
            browser.fill('signinForm:username', config.student_id)
            browser.fill('signinForm:password', config.password)
            browser.click_link_by_id('signinForm:submit')
            # browser.execute_script(
            #     "document.getElementById('signinForm:username').value = " + config.student_id + ";"
            #     "document.getElementById('signinForm:password').value = " + config.password + ";"
            #     "document.getElementById('signinForm:submit').click();")
        elif re.match("https://buniport03.hkbu.edu.hk.*", browser.url):
            if not is_logged_in:
                is_logged_in = True
                pickle.dump(browser.driver.get_cookies(), open(COOKIES_FILE_NAME, "wb"))
                logger.info('Login successful!')

        time.sleep(1)


start()
loop()
pass
