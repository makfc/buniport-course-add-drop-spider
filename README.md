# buniport-course-add-drop-spider
A web spider for course registration and notify by Telegram alert bot.

### Usage
1. If you are not using Windows, download the chromedriver from <https://sites.google.com/a/chromium.org/chromedriver/downloads> and place it to project directory

2. Clone the project in PyhCarm, create config.py with the following in project directory
```
# Create a new empty directory for chrome profile if you haven't
chrome_profile_path = "D:\chrome_profile"

# The browser window will not be displayed when True
headless = False  # Set it to False because chrome extension in headless mode doesn't work

# Check interval(second)
interval = 0

# Start the telegram bot when True
start_bot = True

# Start a conversation with the @BotFather and create a bot using the "/newbot" command
telegram_bot_token = 'TOKEN'

# Your telegram user id, https://stackoverflow.com/questions/32683992/find-out-my-own-user-id-for-sending-a-message-with-telegram-api
my_user_id = 12345678  
```

3. Modify config_task.py
4. Run spider.py
5. If this is your first time running chrome, you need to install the following 3 userscripts in the violetmonkey extension by adding a breakpoint on automatic_login_loop()
* https://github.com/makfc/buniport-captcha-solver-userscript/raw/master/buniport_captcha.user.js <br>
  Add your student ID and password on lines 19 and 84.
* https://gist.github.com/makfc/7b03fcabce77f086bcd311c62484bf23/raw/33294c2e7186b073612692c3f9d2ab3576ac6134/buniport_security_question_autofill.user.js <br>
  Enter your question keyword and answer in the ansList variable
* https://gist.github.com/makfc/13cb2ce36e5605f36d455965b2ab6188/raw/41ccef9182d8d76b43f108293195c94c8125aa07/buniport_new_tab.user.js

# Related Resource
* https://github.com/makfc/buniport-captcha-solver [Temporary Private]
