import os
import sys
import pyautogui
import subprocess
import configparser
import telebot
import requests
from telebot import types
import logging
import user
import re
import smtplib 
import time
# -*- coding: utf-8 -*-

users={}

start_time = time.time()

config = configparser.ConfigParser()
config.read('config.ini')

bot = telebot.TeleBot(config['default']['token'])
logger = logging.getLogger('tgbot') 
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('tgbot.log', mode='a', encoding='utf-8')
fh.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)
logger.info('Starting TelegramBot')
admins=config['default']['admins'].split()
for admin in admins:
   users[admin]=user.User(str(admin))

def send2admins(msg):
    for admin in admins:
        bot.send_message(users[admin].chat_id,msg)

def download_file(url,filename):
    if len(filename) > 0:
        local_filename = filename
    else:
        local_filename = url.split('/')[-1]
    print("Download "+url+" into "+local_filename)
    # NOTE the stream=True parameter below
    r=requests.get(url, stream=True)
    r.raise_for_status()
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
        f.flush()
    return local_filename
def blocked(message):
    bot.send_message(message.chat.id,"Вас заблоковано адміністратором")

def is_registered(message):
    if message.from_user.id not in users:
        users[message.from_user.id] = user.User(str(message.from_user.id))
        if users[message.from_user.id].blocked:
            blocked(message)
            return 
    
        users[message.from_user.id].username=message.from_user.username
        users[message.from_user.id].chat_id=message.chat.id
        users[message.from_user.id].save()
    if users[message.from_user.id].registered != True:
        if users[message.from_user.id].phone_number_provided != True:
            if message.content_type=='contact': 
                users[message.from_user.id].phone_number = message.contact.phone_number
                users[message.from_user.id].phone_number_provided = True
                bot.send_message(message.chat.id,"Вкажіть Ваше Прізвище, Ім'я і по-батькові", reply_markup = types.ReplyKeyboardRemove())
                return False
            else: # not contact
                markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
                markup.add(types.KeyboardButton(text = "Відправити номер телефону", request_contact = True))
                bot.send_message(message.chat.id, "Вам потрібно авторизуватися в системі", reply_markup = markup)
                return False
        else:      #phone provided
            if users[message.from_user.id].fio_provided != True:
                if message.content_type=='text' and re.match(r'(.*) (.*) (.*)',message.text): 
                    users[message.from_user.id].fio = message.text
                    users[message.from_user.id].fio_provided = True
                    users[message.from_user.id].registered = True
                    bot.send_message(message.chat.id, "Додатково ви можете вказати свою електронну пошту командою для отримання копії звернення: \n /email my@email.com")
                    users[message.from_user.id].save()
                    return True
                else:
                    bot.send_message(message.chat.id,"Вкажіть Ваше Прізвище, Ім'я і по-батькові")
                    return False
        return False
    return True

def is_selected(message):
    if users[message.from_user.id].selected != 0:
        try:
            if config["service"+str(users[message.from_user.id].selected)].getboolean("active"):
#                if users[message.from_user.id].location_provided != True:
                if users[message.from_user.id].service_provided != True:
                    users[message.from_user.id].service_provided = True
                    btn = types.KeyboardButton("/finish")
                    markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
                    markup.add(btn)
                    bot.send_message(message.chat.id,"Опишіть звернення і приєднайте фото/відео/аудіо докази, після завершення натисніть /finish", reply_markup=markup)
                    users[message.from_user.id].start() 
                    return False
 
                if message.content_type=='location':
                    users[message.from_user.id].location_provided = True
                    users[message.from_user.id].location = message.location

                users[message.from_user.id].append(message)
                if message.content_type in ["text","location"]:
                    return False

                if message.photo is not None:
                   f=bot.get_file(message.photo[-1].file_id)

                if message.audio is not None:
                    f=bot.get_file(file_id=message.audio.file_id)
                if message.voice is not None:
                    f=bot.get_file(file_id=message.voice.file_id)
                if message.video is not None:
                    f=bot.get_file(file_id=message.video.file_id)

                filename=re.sub('/','_',f.file_path)

                if message.document is not None:
                    f=bot.get_file(file_id=message.document.file_id)
                    filename=message.document.file_name

                try:
                    logger.info("Download file "+str(message.document)+" "+str(f))
                    download_file("https://api.telegram.org/file/bot"+config['default']['token']+"/"+f.file_path, users[message.from_user.id].filespath(filename))
                    bot.send_message(message.chat.id,"Прийнято")
                except Exception as error:
                    logger.error(str(error))
                return False
                    
            else:
                bot.send_message(message.chat.id,config["service"+str(users[message.from_user.id].selected)]["not_active_msg"])
        except Exception as error:
            logger.error("No service " + str(users[message.from_user.id].selected) + " found " + str(error))


    markup = types.ReplyKeyboardMarkup(resize_keyboard = True, row_width = 2)
    for indx in range(1,int(config["default"]["services_count"]) + 1):
        try:
            btn = types.KeyboardButton("/service " + str(indx) + " \"" + config["service"+str(indx)]["name"] + "\"")
            markup.add(btn)
        except Exception as error:
            logger.error("No service " + str(indx) + " found " + str(error))
    bot.send_message(message.chat.id,"Ви авторизовані як " + users[message.from_user.id].fio + "\nВиберіть службу", reply_markup=markup)
    return False

def handler(message):
    if is_registered(message):
        is_selected(message)

def greeting(message):
    bot.send_message(message.chat.id, config['default']['start_msg'])
    handler(message)

@bot.message_handler(commands=["help"])
def charset(message):
    if str(message.from_user.id) in admins:
        bot.send_message(message.chat.id, """Команди бота для адміністратора:
/help - Отримати допомогу
/kill - зупинити
/ban user_id - заблокувати користувача
/unban user_id - розблокувати користувача
/stats - статистика
/add_admin user_id - добавити адміністратора
/del_admin user_id - видалити адміністратора
/list_admins - переглянути список адмінстраторів
/service_tg ID telegram_id - встановити телеграм для служби
""")
    bot.send_message(message.chat.id, """Команди бота для користувачів:
/help - Отримати допомогу
/start - стартувати чат з ботом
/service service_id - вибрати службу
/email user@email - вказати свій емейл для отримання копій звернень
/finish - завершити подачу звернення
""")
@bot.message_handler(commands=["service_tg"])
def service_tg(message):
    if str(message.from_user.id) in admins:
        try:
            match=message.text.split(" ")
            if match[1] != "" and match[1] >str(0) and match[1] <= str(config['default']['services_count']) :
                service_id = match[1]
                if len(match) > 2:
                    user_id = match[2]
                    if user_id not in users:
                        users[user_id]=user.User(str(user_id))
                else:
                    user_id=""
                config['service'+str(service_id)]['responsible_tg'] = user_id
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Отримувача змінено")
                if user_id:
                    bot.send_message(user_id,"Вас зроблено отримувачем повідомлень від бота, /help")
            else:
                bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби") 
        except Exception as error:
            logger.error("Set service tg error " + str(error))
            bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби ") 
       
@bot.message_handler(commands=["add_admin"])
def add_admin(message):
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/add_admin (.+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[user_id]=user.User(str(user_id))
                admins.append(user_id)
                config['default']['admins'] = " ".join(admins)
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Адміністратора додано")
                bot.send_message(user_id,"Вас зроблено адміністратором, /help")
        except Exception as error:
            logger.error("Add admin error " + str(error))
            bot.send_message(message.chat.id,"Для додавання адміністратора введіть:\n /add_admin user_id") 

@bot.message_handler(commands=["del_admin"])
def del_admin(message):
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/del_admin (.+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[user_id]=user.User(str(user_id))
                admins.remove(user_id)
                config['default']['admins'] = " ".join(admins)
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Адміністратора видалено")
                bot.send_message(user_id,"Вас видалено з адміністраторів, /help")
        except Exception as error:
            logger.error("Del admin error " + str(error))
            bot.send_message(message.chat.id,"Для видалення адміністратора введіть:\n /del_admin user_id")         

@bot.message_handler(commands=["list_admins"])
def list_admin(message):
    if str(message.from_user.id) in admins:
        try:
            bot.send_message(message.chat.id,"Адміністратори\n"+" ".join(admins))
        except Exception as error:
            logger.error("List admin error " + str(error))
            

def hms_string(sec_elapsed):
    h = int(sec_elapsed / (60 * 60))
    m = int((sec_elapsed % (60 * 60)) / 60)
    s = sec_elapsed % 60.
    return "{}:{:>02}:{:>05.2f}".format(h, m, s)

@bot.message_handler(commands=["stats"])
def stats(message):
    requests=len([name for name in os.listdir('requests') if os.path.isdir(os.path.join('requests', name))])
    users=len([name for name in os.listdir('users') if os.path.isdir(os.path.join('users', name))])
    uptime=time.time()-start_time
    bot.send_message(message.chat.id, """Статистика:
uptime: %s
користувачів: %d
звернень: %d
 """ % (hms_string(uptime),users, requests))

@bot.message_handler(commands=["kill"])
def kill(message):
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        logger.info("Kill command")
        send2admins("Бота зупинив користувач: "+str(message.from_user.id))
        bot.stop()

@bot.message_handler(commands=["ban"])
def ban(message):
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/ban (.+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[user_id]=user.User(str(user_id))
                users[user_id].blocked=True
                users[user_id].save()
                bot.send_message(message.chat.id,"User banned")
                bot.send_message(user_id,"Вас заблоковано адміністратором")
        except Exception as error:
            logger.error("Ban error " + str(error))
            bot.send_message(message.chat.id,"Для блокування користувача введіть:\n /ban user_id") 

@bot.message_handler(commands=["unban"])
def ban(message):
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/unban (.+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[user_id]=user.User(str(user_id))
                users[user_id].blocked=False
                users[user_id].save()
                bot.send_message(message.chat.id,"User unbanned")
                bot.send_message(user_id,"Вас розблоковано адміністратором")
        except Exception as error:
            logger.error("Ban error " + str(error))
            bot.send_message(message.chat.id,"Для розблокування користувача введіть:\n /ban user_id") 

@bot.message_handler(commands=["email"])
def email(message):
    if message.from_user.id not in users:
        greeting(message)
        return 
    if users[message.from_user.id].blocked:
        blocked(message)
        return 
        
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
        logger.debug(message)
        try:
            match=re.match('/email (.+@.+\..+)',message.text)
            if match.group(1) != "" and users[message.from_user.id].registered:
                users[message.from_user.id].email = match.group(1)
                users[message.from_user.id].save()
                bot.send_message(message.chat.id,"Ваш емейл змінено на " + users[message.from_user.id].email)
        except Exception as error:
            logger.error("Illegal service provided " + str(error))
            bot.send_message(message.chat.id,"Для зміни емейлу введіть команду:\n /email ваш_емейл") 
    except Exception as error:
        logger.error("Email error" + str(error))

@bot.message_handler(commands=["start"])
def start(message):
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+str(message.content_type)+"]: "+str(message.text))
        logger.debug(message)
        greeting(message)
    except Exception as error:
        logger.error("Start error" + str(error))


@bot.message_handler(commands=["finish"])
def finish(message):
    if message.from_user.id not in users:
        greeting(message)
        return 
    if users[message.from_user.id].blocked:
        blocked(message)
        return 
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
        logger.debug(message)
        if is_registered(message) and users[message.from_user.id].uuid != "":
            try:
                if config['service'+str(users[message.from_user.id].selected)]['responsible_email'] :
                    logger.info("Підготовка листа")
                    msg = users[message.from_user.id].get_email_msg()
                    logger.debug(msg.as_string());
                    msg['From'] = config['email']['from_addr'] 
                    msg['To'] = config['service'+str(users[message.from_user.id].selected)]['responsible_email']
                    msg['Subject'] = "Прийнято звернення "+ users[message.from_user.id].uuid
                    logger.debug(msg);
                    logger.info("Підключення до сервера")
                    s = smtplib.SMTP(config['email']['host'] , config['email']['port'] ) 
                    logger.debug("Open: "+str(s));
                    logger.info("Включення TLS")
                    s.starttls() 
                    logger.debug("Start TLS: "+str(s));
                    logger.info("Авторизація на сервері")
                    s.login(config['email']['login'], config['email']['password']) 
                    logger.debug("Login: "+str(s));
                    text = msg.as_string() 
                    logger.info("Відправка листа " + users[message.from_user.id].uuid)
                    s.sendmail(msg['From'], msg['To'], text)
                    if users[message.from_user.id].email !="":
                         msg['To']=users[message.from_user.id].email
                         s.sendmail(msg['From'], msg['To'], text)
                    logger.debug("Sendmail: "+str(s));
                    s.quit() 
                    logger.debug("Quit: "+str(s));
                    
                if config['service'+str(users[message.from_user.id].selected)]['responsible_tg'] :
                    msg = users[message.from_user.id].get_tg_msg()
                    bot.send_message(config['service'+str(users[message.from_user.id].selected)]['responsible_tg'],"Подано нове звернення:\n"+msg)
                    files=users[message.from_user.id].get_tg_files()
                    for doc in files:
                        bot.send_document(message.chat.id, open(doc, 'rb'))
                    logger.info(files)
                users[message.from_user.id].selected=0
                users[message.from_user.id].location_provided = False
                users[message.from_user.id].service_provided = False
                users[message.from_user.id].uuid = ""
                users[message.from_user.id].location = {}
                bot.send_message(message.chat.id,"Дякуємо, Ваше звернення взяте на обробку", reply_markup = types.ReplyKeyboardRemove())
            except Exception as error:
                logger.error("Sent error " + str(error))
        handler(message)
    except Exception as error:
        logger.error("Finish error" + str(error))


@bot.message_handler(commands=["service"])
def service(message):
    if message.from_user.id not in users:
        greeting(message)
        return 
    if users[message.from_user.id].blocked:
        blocked(message)
        return 
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
        logger.debug(message)
        try:
            match=re.match('/service (\d+) .*',message.text)
            if int(match.group(1)) >0 :
                users[message.from_user.id].selected = int(match.group(1))
        except Exception as error:
            logger.error("Illegal service provided " + str(error))
        handler(message)
    except Exception as error:
        logger.error("Finish error" + str(error))


@bot.message_handler(content_types=['contact','text','location','document','video','photo','audio','voice'])
def other_messages(message):
    if message.from_user.id not in users:
        greeting(message)
        return 
    if users[message.from_user.id].blocked:
        blocked(message)
        return 
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
        logger.debug(message)
        handler(message)
    except Exception as error:
        logger.error("Receive error" + str(error))

@bot.message_handler()
def not_messages(message):
        logger.info(message)

if __name__ == '__main__':
    send2admins("Бот рестартовано, /help")
    bot.polling(none_stop=True)

logger.info('Closing TelegramBot')
