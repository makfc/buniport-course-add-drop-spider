import os
import pickle
import re
import threading
import time

from telegram import ParseMode

import config
import config_task
from task import Task
import logging
from telegram.ext import Updater, CommandHandler

from selenium import webdriver
from splinter import Browser
# import requests
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

try:
    with open(preferences_path, encoding='utf-8') as f:
        data = json.load(f)
    data['profile']['exit_type'] = "None"
    data['profile']['exited_cleanly'] = True

    with open(preferences_path, 'w', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False))
except FileNotFoundError:
    pass
######################################################

# Telegram bot setup
if config.start_bot:
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
if config.headless:
    browser.driver.set_window_position(-3000, 0)
window_home = None
window_courseAddDrop = None
window_checkSections = None


######################################################

def open_in_new_tab(url):
    browser.execute_script(f'''window.open("{url}","_blank");''')


def cookie_setup():
    if os.path.exists(COOKIES_FILE_NAME):
        visit_home()
        browser.driver.delete_all_cookies()
        cookies = pickle.load(open(COOKIES_FILE_NAME, "rb"))
        for cookie in cookies:
            browser.driver.add_cookie(cookie)


def visit_home():
    global window_home

    url = 'https://buniport.hkbu.edu.hk'
    logger.info(f'Visit {url}')
    browser.driver.get(url)
    # alert = browser.driver.switch_to_alert()
    # alert.accept()
    window_home = browser.driver.window_handles[0]
    browser.driver.switch_to_window(window_home)


def login():
    # browser.fill('signinForm:username', config.student_id)
    # browser.fill('signinForm:password', config.password)
    # Same as above but faster
    # browser.execute_script(
    #     f"document.getElementById('signinForm:username').value = '{config.student_id}'")
    # browser.execute_script(
    #     f"document.getElementById('signinForm:password').value = '{config.password}'")

    # Captcha
    wait_time = 2
    end_time = time.time() + wait_time
    while time.time() < end_time and len(browser.find_by_id('signinForm:recaptcha_response_field').value) != 4:
        time.sleep(0.1)  # pass

    browser.click_link_by_id('signinForm:submit')


def wait_new_tab():
    count = len(browser.driver.window_handles)
    while len(browser.driver.window_handles) <= count:
        time.sleep(0.1)  # pass


def visit_course_add_drop():
    global window_courseAddDrop
    url = 'https://buniport03.hkbu.edu.hk/wps/myportal/hidden/Home/Studies/MyStudies'
    logger.info(f'Visit {url}')
    browser.driver.get(url)
    try:
        browser.click_link_by_partial_text('增修/退修科目')
    except Exception:
        browser.click_link_by_partial_text('Course Add/Drop')

    wait_new_tab()
    window_courseAddDrop = browser.driver.window_handles[-1]  # Get last window
    browser.driver.switch_to_window(window_courseAddDrop)
    try:
        browser.is_element_present_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:tabAddDrop_lbl')
        browser.click_link_by_id('addDrop:imgEdit')
    except Exception:
        logger.error('Course add drop is currently unavailable!')
        time.sleep(2)
        raise Exception


def automatic_login_loop():
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

            visit_course_add_drop()
            check_sections_info(config_task.task_list)

        time.sleep(1)


def remove_space(text):
    return re.sub('[\n\t]+', ' ' * 4, str(text).strip(' \t\n\r'))


is_full = True


def check_sections_info(task_list):
    global is_full, window_checkSections

    count = len(browser.driver.window_handles)
    open_in_new_tab("")
    while len(browser.driver.window_handles) <= count:
        time.sleep(0.1)  # pass
    # wait_new_tab()  # time.sleep(1)
    window_checkSections = browser.driver.window_handles[-1]
    browser.driver.switch_to_window(window_checkSections)

    old_list = []
    while True:
        for task in task_list:
            # Task setup
            if type(task) is not Task:
                raise Exception("Wrong type in course_list")

            browser.visit(
                f"https://iss.hkbu.edu.hk/sisweb2/reg/sectionInfo.seam?acYear=2019&term=S2&subjCode={task.course_code}")
            bs = BeautifulSoup(browser.html, "lxml")
            page_title = bs(class_="pageTitle")[0].text

            # Get header
            table_header = [item.text for item in bs(class_="rich-table-header")[0]]
            # table_header = ' | '.join([item.text for item in bs(class_="rich-table-header")[0]])

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
            if task.filter_func is not None:
                table_data = (filter(task.filter_func, table_data))

            # Get all available section
            table_data = filter(lambda x: x[4] != 'Full', table_data)

            # Convert to list
            table_data = list(table_data)

            # If there is a difference from the previous check
            if table_data != old_list:
                old_list = table_data
                text = f'`{page_title}\n{str(table_header)}'
                if len(table_data) > 0:
                    # Print all available section
                    for row in table_data:
                        text += f'\n{str(row)}'
                        # text += f"\n{row[0]}|{row[1]}|{row[2]}|{row[3]}|{row[4]}|{row[5]}"
                        break
                else:
                    text += "\nAll selected section full again!"
                text += '`'
                logger.info(text)
                send_text(text)
                # send_screenshot()

            if len(table_data) > 0:
                # Execute reg_course
                for row in table_data:
                    result = reg_course(task.course_code, row[0])  # "#N-FREE-001"
                    if result == 0:
                        task_list.remove(task)
                    break

                browser.driver.switch_to_window(window_checkSections)
        time.sleep(1)


def reg_course(course_code, section, group=""):
    logger.info(f"reg_course with ({course_code}|{section}|{group})")
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

    except Exception as e:
        # When current courseAddDrop page session timeout and redirected to home page
        logger.error(e)
        logger.error("CourseAddDrop page session timeout!")
        raise Exception
        # browser.close()
        # browser.driver.switch_to_window(window_home)
        # vist_home()
        # automatic_login_loop(is_exception=True)

    # Check if enrolled
    is_change_section = False
    input_tag_id = None  # Change Section input
    add_drop_table = None
    while True:
        # Waiting for page javascript to load
        add_drop_table = BeautifulSoup(browser.html, "lxml")(id="addDrop:enroll:tb")[0]
        if len(add_drop_table('input')) > 0:
            break
        else:
            time.sleep(0.1)

    ######################################################
    row_tag = None
    td_tag = []
    for row_tag in add_drop_table('tr'):
        if course_code in row_tag.text:
            td_tag = row_tag(class_='enrCourse')
            break

    # When the course_code contain in the add_drop_table
    if len(td_tag) > 0:
        if section in row_tag(class_='enrSect')[0].text:
            # The course section already enrolled
            logger.info('The course section already enrolled. Task completed!')
            return 0

        is_change_section = True
        td_tag = row_tag(class_='enrChgSect')
        if len(td_tag) > 0:
            input_tag = td_tag[0]('input')
            if len(input_tag) > 0:
                input_tag_id = input_tag[0].get('id')
    ######################################################

    if is_change_section and input_tag_id is None:  # Error occurs
        logger.error('is_change_section and input_tag_id is None')
        return
    elif is_change_section and input_tag_id is not None:
        browser.execute_script(f"document.getElementById('{input_tag_id}').value = '{section}'")
    else:
        # Start auto fill

        browser.is_element_present_by_id("addDrop:toAdd:0:s")

        # browser.fill("addDrop:toAdd:0:s", code)
        # browser.fill("addDrop:toAdd:0:lc", section)
        # Same as above but faster
        browser.execute_script(f"document.getElementById('addDrop:toAdd:0:s').value = '{course_code}'")
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

    logger.info(f"Filled with {course_code}|{section}|{group}")
    browser.click_link_by_id("cmdSaveTop")
    logger.info("Clicked cmdSaveTop")
    time.sleep(3)

    # Waiting for results
    browser.is_element_present_by_id("addDrop:tabValidRst", wait_time=30)
    logger.info("is_element_present_by_id")

    # Get all table messages
    submit_result = ''
    double_new_line = ''  # for print result
    table_tag_list = BeautifulSoup(browser.html, "lxml")(id='addDrop:tabValidRst')[0](class_='rich-table')
    for table_tag in table_tag_list:
        submit_result += double_new_line
        for table_row in table_tag("tr"):
            table_data = [remove_space(cell.text) for cell in table_row(["th", "td"])]
            submit_result += '\n' + str(table_data)
        double_new_line = '\n' * 2

    logger.info(submit_result)
    send_text(submit_result)


# def send_screenshot():
#     file_name = time.strftime("%Y%m%d-%H%M%S")
#     browser.driver.save_screenshot(f"{file_name}.pmg")
#     bot.send_document(config.my_user_id, document=open(file_name, 'rb'))

def send_text(message):
    if config.start_bot:
        # bot.send_message(config.my_user_id, message, ParseMode.MARKDOWN)
        # Same as above
        t = threading.Thread(target=bot.send_message,
                             args=(config.my_user_id,
                                   message, ParseMode.MARKDOWN),
                             kwargs={})
        t.start()
        # bot.send_message(-1001170605458, message)
        # https://api.telegram.org/bot<YourBOTToken>/getUpdates


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

logger.info('Setup cookie')
cookie_setup()
while True:
    try:
        visit_home()
        is_logged_in = False
        logger.info('Automatic login...')
        automatic_login_loop()
    except Exception as e:
        logger.error(e)
        close_others_window()
# os.execl(sys.executable, sys.executable, *sys.argv)
