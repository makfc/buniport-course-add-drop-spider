import os
import pickle
import re
import threading
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
    browser.driver.get("https://buniport.hkbu.edu.hk")
    # alert = browser.driver.switch_to_alert()
    # alert.accept()
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


def wait_new_tab():
    count = len(browser.driver.window_handles)
    while len(browser.driver.window_handles) <= count:
        pass


def visit_course_add_drop():
    global window_courseAddDrop
    browser.click_link_by_partial_text('增修/退修科目')
    wait_new_tab()
    window_courseAddDrop = browser.driver.window_handles[-1]  # Get last window
    browser.driver.switch_to_window(window_courseAddDrop)
    try:
        browser.is_element_present_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:imgEdit')
        return True
    except Exception as e:
        logger.error(e)

    return False


def auto_login_loop(is_exception=False):
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
                if visit_course_add_drop():
                    break
                browser.windows.current.close()
                time.sleep(2)
                browser.driver.switch_to_window(window_home)
                browser.reload()
                is_exception = True

            if is_exception:
                return

            course_list = [["GCPS1005", lambda x: int(x[0]) == 35 and 'Jonathan' in x[2]]
                           ]
            check_sections_info(course_list)

        time.sleep(1)


def remove_space(text):
    return re.sub('[\n\t]+', '\t', str(text).strip(' \t\n\r'))


isFull = True
found = False


def check_sections_info(task_list):
    global isFull, found, window_checkSections

    count = len(browser.driver.window_handles)
    open_in_new_tab("")
    while len(browser.driver.window_handles) <= count:
        pass
    # wait_new_tab()  # time.sleep(1)
    window_checkSections = browser.driver.window_handles[-1]
    browser.driver.switch_to_window(window_checkSections)

    old_list = []
    while True:
        for task in task_list:
            # Task setup
            if type(task) == str:
                course_code = task
                filter_func = None
            elif type(task) == list and len(task) == 2:
                course_code = task[0]
                filter_func = task[1]
            else:
                raise Exception("Wrong type in course_list")

            browser.visit(
                f"https://iss.hkbu.edu.hk/sisweb2/reg/sectionInfo.seam?acYear=2018&term=S2&subjCode={course_code}")
            bs = BeautifulSoup(browser.html, "lxml")
            page_title = bs(class_="pageTitle")[0].text

            # Get header
            table_header = ' | '.join([item.text for item in bs(class_="rich-table-header")[0]])

            table_data = []
            table_row_tag_list = [x for x in bs(class_="rich-table-row")]
            for row in table_row_tag_list:
                # 0     Section code
                # 1     Day/Time/Venue
                # 2     Instructor (Dept)
                # 3     Medium ofInstruction
                # 4     Available Quota
                # 5     Others
                # 6     Remarks
                row = [row(class_='sectDtlSection')[0].text, row(class_='sectDtlDayTimeVenue')[0].text,
                       row(class_='sectDtlInst')[0].text, row(class_='sectDtlMedium')[0].text,
                       row(class_='sectDtlQS')[0].text,
                       [item.get("title") for item in row(class_='sectDtlIcon')[0]("img")],
                       row(class_='sectDtlRemarks')[0].text]
                table_data.append(row)

            # Remove all unnecessary stuff
            table_data = (map(lambda x:
                              [remove_space(y) for y in x]
                              , table_data))

            # Apply custom filter
            if filter_func is not None:
                table_data = (filter(filter_func, table_data))

            # Get all available section
            table_data = list(filter(lambda x: x[4] != 'Full', table_data))

            # If there is a difference from the previous check
            if table_data != old_list:
                old_list = table_data
                text = page_title + f"\n{table_header}"
                if len(table_data) > 0:
                    # Print all available section
                    for row in table_data:
                        text += "\n" + ("-" * 70)
                        text += f"\n{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}|{row[5]}"
                        break
                else:
                    text += "\n" + ("-" * 70)
                    text += "\nAll selected section full again!"
                logger.info(text)
                send_text(text)
                # send_screenshot()

            if len(table_data) > 0:
                # Execute reg_course
                for row in table_data:
                    reg_course(course_code, row[0])  # "#N-FREE-001"
                    break

                browser.driver.switch_to_window(window_checkSections)
        time.sleep(1)


def reg_course(code, section, group=""):
    logger.info(f"reg_course with ({code}|{section}|{group})")
    try:
        browser.driver.switch_to_window(window_courseAddDrop)

        tag_id = 'addDrop:tabAddDrop_lbl'
        if browser.find_by_id(tag_id):
            browser.click_link_by_id(tag_id)
        else:
            browser.visit("https://iss.hkbu.edu.hk/sisweb2/olreg/addDropEd.seam")
            browser.is_element_present_by_id(tag_id)
            browser.click_link_by_id(tag_id)
            browser.click_link_by_id('addDrop:imgEdit')

    except Exception as e2:
        # When current courseAddDrop page session timeout and redirected to home page
        logger.error(e2)
        logger.error("CourseAddDrop page session timeout!")
        raise Exception
        # browser.close()
        # browser.driver.switch_to_window(window_home)
        # vist_home()
        # auto_login_loop(is_exception=True)

    # Check if enrolled
    is_change_section = False
    input_tag_id = None  # Change Section input
    add_drop_table = None
    while True:
        # Waiting for page javascript to load
        add_drop_table = BeautifulSoup(browser.html, "lxml")(id="addDrop:enroll:tb")[0]
        if len(add_drop_table('input')) > 0:
            break

    for row_tag in add_drop_table('tr'):
        td_tag = row_tag(class_='enrCourse')
        if len(td_tag) > 0:
            if code in td_tag[0].text:
                if section in row_tag(class_='enrSect')[0].text:  # is_enrolled
                    return
                is_change_section = True
                td_tag = row_tag(class_='enrChgSect')
                if len(td_tag) > 0:
                    input_tag = td_tag[0]('input')
                    if len(input_tag) > 0:
                        input_tag_id = input_tag[0].get('id')
                break

    if is_change_section and input_tag_id is None:
        return

    if is_change_section and input_tag_id is not None:
        browser.execute_script(f"document.getElementById('{input_tag_id}').value = '{section}'")
    else:
        # Start auto fill
        browser.is_element_present_by_id("addDrop:toAdd:0:s")
        # browser.fill("addDrop:toAdd:0:s", code)
        # browser.fill("addDrop:toAdd:0:lc", section)
        browser.execute_script(f"document.getElementById('addDrop:toAdd:0:s').value = '{code}'")
        browser.execute_script(f"document.getElementById('addDrop:toAdd:0:lc').value = '{section}'")

        if group == "":
            logger.info("Group is not specified, the group will be automatically selected")
            browser.click_link_by_id("addDrop:toAdd:0:imgSL")
            browser.is_element_present_by_id("addDrop:slSubjList")
            browser.find_by_name("addDrop:slSubjList").last.click()
            browser.click_link_by_id("addDrop:cmdChgCourseGrp")
            browser.is_text_present("addDrop:toAdd:0:sl")
            group = browser.find_by_id("addDrop:toAdd:0:sl")[0].value
        else:
            # browser.fill("addDrop:toAdd:0:sl", group)
            browser.execute_script(f"document.getElementById('addDrop:toAdd:0:sl').value = '{group}'")

    logger.info(f"Filled with {code}|{section}|{group}")
    browser.click_link_by_id("cmdSaveTop")
    logger.info("Clicked cmdSaveTop")
    time.sleep(3)

    # Waiting for results
    browser.is_element_present_by_id("addDrop:tabValidRst", wait_time=30)
    logger.info("is_element_present_by_id")

    # Get all table messages
    submit_result = ''
    next_line = ''
    table_tag_list = BeautifulSoup(browser.html, "lxml")(id='addDrop:tabValidRst')[0](class_='rich-table')
    for table_tag in table_tag_list:
        table_data = [cell.text for cell in table_tag(["td", "th"])]
        submit_result += next_line + str(list(map(lambda x: remove_space(x), table_data)))
        next_line = '\n'

    logger.info(submit_result)
    send_text(submit_result)


# def send_screenshot():
#     file_name = time.strftime("%Y%m%d-%H%M%S")
#     browser.driver.save_screenshot(f"{file_name}.pmg")
#     bot.send_document(config.my_user_id, document=open(file_name, 'rb'))


def send_text(message):
    t = threading.Thread(target=bot.send_message,
                         args=(config.my_user_id,
                               message),
                         kwargs={})
    t.start()
    # bot.send_message(config.my_user_id, message)
    # bot.send_message(-1001170605458, message)


def close_others_window():
    while len(browser.windows) > 1:
        browser.windows.current.close_others()


# def set_sessions(driver):
#     request = requests.Session()
#     headers = {
#         "User-Agent":
#             "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 "
#             "(KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36"
#     }
#     request.headers.update(headers)
#     cookies = driver.get_cookies()
#     for cookie in cookies:
#         request.cookies.set(cookie['name'], cookie['value'])
#
#     return request


cookie_setup()
while True:
    try:
        vist_home()
        is_logged_in = False
        auto_login_loop()
    except Exception as e:
        logger.error(e)
        close_others_window()
# os.execl(sys.executable, sys.executable, *sys.argv)
