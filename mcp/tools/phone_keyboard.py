"""Keyboard HID commands; passcodes stay out of command receipts and errors."""

import time

from phone_macro import run_steps


APP_NAMES = {
    '微信': 'WeChat', '设置': 'Settings', '计算器': 'Calculator', '支付宝': 'Alipay',
    '相机': 'Camera', '照片': 'Photos', '信息': 'Messages', '电话': 'Phone',
    '钱包': 'Wallet', '文件': 'Files', '备忘录': 'Notes', '日历': 'Calendar',
    '指南针': 'Compass', '健康': 'Health', '日记': 'Journal', '语音备忘录': 'Voice Memos',
}
PUNCTUATION = {c: (usage, 0) for c, usage in zip('-=[]\\;\',./`', (45,46,47,48,49,51,52,54,55,56,53))}
PUNCTUATION.update({c: (usage, 2) for c, usage in zip('_+{}|:"<>?~', (45,46,47,48,49,51,52,54,55,56,53))})
PUNCTUATION.update({c: (usage, 2) for c, usage in zip('!@#$%^&*()', (30,31,32,33,34,35,36,37,38,39))})


def key(phone, usage, modifiers=0):
    phone.send(f'KEY:{modifiers},{usage}')


def home(phone):
    key(phone, 0x0B, 0x08)  # Command-H
    time.sleep(.5)


def validate_text(value):
    if not value or any(not 32 <= ord(c) <= 126 for c in value):
        raise ValueError('Use an English app search name or pinyin')


def text(phone, value):
    validate_text(value)
    for character in value:
        if character.isalpha():
            key(phone, ord(character.lower()) - ord('a') + 4, 2 if character.isupper() else 0)
        elif character == ' ':
            key(phone, 0x2C)
        elif character.isdigit():
            key(phone, 0x27 if character == '0' else 0x1D + int(character))
        else:
            usage, modifiers = PUNCTUATION[character]
            key(phone, usage, modifiers)


def app_search_name(name):
    name = APP_NAMES.get(name.strip(), name.strip())
    if not name or len(name) > 60 or any(not 32 <= ord(c) <= 126 for c in name):
        raise ValueError('Provide an English app name or pinyin (1-60 characters); common Chinese app names are supported')
    return name


def open_app(phone, name):
    name = app_search_name(name)
    home(phone)
    key(phone, 0x2C, 0x08)  # Command-Space: Spotlight
    time.sleep(.5)
    key(phone, 0x04, 0x08)  # Command-A: replace any previous search
    text(phone, name)
    time.sleep(.8)
    commands = []
    run_steps(phone, 'app-search-first-result', commands)
    return name
