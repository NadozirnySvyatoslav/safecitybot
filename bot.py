import os
import sys
import pyautogui
import subprocess
import configparser
import telebot
import requests
from telebot import types
from telebot import util
import logging
import user
import re
import smtplib 
import time
# -*- coding: utf-8 -*-

users={}
admin_users={}

start_time = time.time()

config = configparser.ConfigParser()
try:
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
except Exception as error:
    print("Error read config.ini")
    exit()

for admin in admins:
   admin_users[admin]=user.User(str(admin))

def send2admins(msg):
    for admin in admins:
        try:
            bot.send_message(admin_users[admin].chat_id,msg)
        except Exception as error:
            logger.error('No admins found')    

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

def is_private(message):
    if str(message.chat.type)!="private" and not (str(message.from_user.id) in admins):
        bot.send_message(message.chat.id,"Для подачі звернення напишіть напряму боту "+config['default']['name'])
        return
    else:
        return True

def is_registered(message):
    if not is_private(message):
        return
    if str(message.from_user.id) not in users:
        logger.info("User not present")
        users[str(message.from_user.id)] = user.User(str(message.from_user.id))
        if users[str(message.from_user.id)].blocked:
            blocked(message)
            return 
        users[str(message.from_user.id)].username=message.from_user.username
        users[str(message.from_user.id)].chat_id=message.chat.id
        users[str(message.from_user.id)].save()
    logger.info("User present")

    if users[str(message.from_user.id)].registered != True:
    	logger.info("User not registered")
    	if users[str(message.from_user.id)].phone_number_provided != True:
            logger.info("phone not provided")
            if message.content_type=='contact': 
                users[str(message.from_user.id)].phone_number = message.contact.phone_number
                users[str(message.from_user.id)].phone_number_provided = True
                users[str(message.from_user.id)].save()
                bot.send_message(message.chat.id,"Вкажіть Ваше Прізвище, Ім'я і по батькові", reply_markup = types.ReplyKeyboardRemove())
                return False
            else: # not contact
                markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
                markup.add(types.KeyboardButton(text = "Відправити номер телефону", request_contact = True))
                logger.info(users[str(message.from_user.id)].greeting)
                if not users[str(message.from_user.id)].greeting :
                	users[str(message.from_user.id)].greeting = True
                	bot.send_message(message.chat.id, config['default']['start_msg'])

                bot.send_message(message.chat.id,"""\nДля подачі звернень, Вам потрібно авторизуватися в системі. 
Для цього достатньо відправити номер телефону і вказати своє Прізвище, ім'я та по батькові.
""", reply_markup = markup)
                return False
    	else:
        #phone provided
            logger.info("phone provided")
            if users[str(message.from_user.id)].fio_provided != True:
                if message.content_type=='text' and re.match(r'(.*) (.*)',message.text): 
                    users[str(message.from_user.id)].fio = message.text
                    users[str(message.from_user.id)].fio_provided = True
                    users[str(message.from_user.id)].registered = True
                    bot.send_message(message.chat.id, "Додатково при бажанні Ви можете вказати свою електронну пошту: \n /email my@email.com")
                    users[str(message.from_user.id)].save()
                    return True
                else:
                    bot.send_message(message.chat.id,"Вкажіть Ваше Прізвище, Ім'я і по батькові")
                    return False
    	return False
    	logger.info("User registered")
    return True

def is_selected(message):
    logger.info("Service: "+str(users[str(message.from_user.id)].selected))
    if users[str(message.from_user.id)].selected != 0:
        try:
            if config["service"+str(users[str(message.from_user.id)].selected)].getboolean("active"):
    #                if users[str(message.from_user.id)].location_provided != True:
                
                if users[str(message.from_user.id)].service_provided != True:
                    users[str(message.from_user.id)].service_provided = True
                    btn = types.KeyboardButton("/finish")
                    markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
                    markup.add(btn)
                    bot.send_message(message.chat.id,"Опишіть звернення і приєднайте фото/відео/аудіо докази, після завершення натисніть /finish", reply_markup=markup)
                    users[str(message.from_user.id)].start() 
                    return False

                if message.content_type=='location':
                    users[str(message.from_user.id)].location_provided = True
                    users[str(message.from_user.id)].location = message.location

                users[str(message.from_user.id)].append(message)
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
                    download_file("https://api.telegram.org/file/bot"+config['default']['token']+"/"+f.file_path, users[str(message.from_user.id)].filespath(filename))
                    bot.send_message(message.chat.id,"Прийнято")
                except Exception as error:
                    logger.error(str(error))
                return False
                    
            else:
                bot.send_message(message.chat.id,config["service"+str(users[str(message.from_user.id)].selected)]["not_active_msg"])
        except Exception as error:
            logger.error("No service " + str(users[str(message.from_user.id)].selected) + " found " + str(error))


    markup = types.ReplyKeyboardMarkup(resize_keyboard = True, row_width = 2)
    for indx in range(1,int(config["default"]["services_count"]) + 1):
        try:
            btn = types.KeyboardButton("/service " + str(indx) + " \"" + config["service"+str(indx)]["name"] + "\"")
            markup.add(btn)
        except Exception as error:
            logger.error("No service " + str(indx) + " found " + str(error))
    bot.send_message(message.chat.id,"Ви авторизовані як " + users[str(message.from_user.id)].fio + "\nВиберіть службу", reply_markup=markup)
    return False

@bot.message_handler(commands=["help"])
def help(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        bot.send_message(message.chat.id, config['text']['admin_help'])
    bot.send_message(message.chat.id, config['text']['help'])

@bot.message_handler(commands=["id"])
def myid(message):
    if not is_private(message):
        return
    bot.send_message(message.chat.id, str(message.from_user.id))

@bot.message_handler(commands=["list_users"])
def list_users(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        users_list="telegram_id / Username / ПІБ\n"
        usersconfig=configparser.ConfigParser()
        for user_id in os.listdir('users' + os.path.sep):
            usersconfig.read('users' + os.path.sep + user_id + os.path.sep + 'config.ini')
            users_list=users_list + ("%s @%s %s\n" % (user_id,usersconfig['userdata']['username'],usersconfig['userdata']['fio']))
        splitted_text = util.split_string(users_list, 3000)
        for text in splitted_text:
            bot.send_message(message.chat.id, text)

@bot.message_handler(commands=["service_tg"])
def service_tg(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=message.text.split(" ")
            if match[1] != "" and match[1] >str(0) and match[1] <= str(config['default']['services_count']) :
                service_id = match[1]
                if len(match) > 2:
                    user_id = match[2]
                    if user_id not in users:
                        users[str(user_id)]=user.User(str(user_id))
                else:
                    user_id=""
                config['service'+str(service_id)]['responsible_tg'] = user_id
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Отримувача змінено")
                if user_id:
                    bot.send_message(user_id,"Вас зроблено отримувачем повідомлень від бота, /help "+" @"+str(users[str(message.from_user.id)].username))
            else:
                bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби /help") 
        except Exception as error:
            logger.error("Set service tg error " + str(error))
            bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби /help") 

@bot.message_handler(commands=["service_email"])
def service_email(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=message.text.split(" ")
            if match[1] != "" and match[1] >str(0) and match[1] <= str(config['default']['services_count']) :
                service_id = match[1]
                if len(match) > 2:
                    user_email = match[2]
                else:    
                    user_email=""
                config['service'+str(service_id)]['responsible_email'] = user_email
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Отримувача email змінено")
            else:
                bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби /help") 
        except Exception as error:
            logger.error("Set service email error " + str(error))
            bot.send_message(message.chat.id,"Для додавання введіть правильний номер служби /help") 

@bot.message_handler(commands=["service_enable"])
def service_enable(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=re.split(r' +',message.text)
            if match[1] != "" and match[1] >str(0) and match[1] <= str(config['default']['services_count']) :
                service_id = match[1]
                config['service'+str(service_id)]['active'] ="True"
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Службу включено")
            else:
                bot.send_message(message.chat.id,"Для включення введіть правильний номер служби /help") 
        except Exception as error:
            logger.error("Set service enable error " + str(error))
            bot.send_message(message.chat.id,"Для включення введіть правильний номер служби /help") 

@bot.message_handler(commands=["service_disable"])
def service_enable(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=message.text.split(" ")
            if match[1] != "" and match[1] >str(0) and match[1] <= str(config['default']['services_count']) :
                service_id = match[1]
                config['service'+str(service_id)]['active'] = "False"
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                bot.send_message(message.chat.id,"Службу виключено")
            else:
                bot.send_message(message.chat.id,"Для відключення введіть правильний номер служби /help") 
        except Exception as error:
            logger.error("Set service disable error " + str(error))
            bot.send_message(message.chat.id,"Для відключення введіть правильний номер служби /help") 

       
@bot.message_handler(commands=["add_admin"])
def add_admin(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/add_admin (\d+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[str(user_id)]=user.User(str(user_id))
                if not user_id in admins:
                	admins.append(user_id)
                config['default']['admins'] = " ".join(admins)
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                    logger.info("Administrator added: "+str(user_id))
                bot.send_message(message.chat.id,"Адміністратора додано")
                bot.send_message(int(user_id),"Вас зроблено адміністратором, /help"+" @" + str(users[str(message.from_user.id)].username))
        except Exception as error:
            logger.error("Add admin error " + str(error))
            bot.send_message(message.chat.id,"Для додавання адміністратора введіть:\n /add_admin user_id\n/help") 

@bot.message_handler(commands=["del_admin"])
def del_admin(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/del_admin (\d+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[str(user_id)]=user.User(str(user_id))
                if user_id in admins and (user_id!=message.from_user.id):
                	admins.remove(user_id)
                config['default']['admins'] = " ".join(admins)
                with open('config.ini',"w") as configfile:
                    config.write(configfile)
                    logger.info("Administrator deleted: "+str(user_id))
                bot.send_message(message.chat.id,"Адміністратора видалено")
                bot.send_message(user_id,"Вас видалено з адміністраторів "+" @"+str(users[str(message.from_user.id)].username))
        except Exception as error:
            logger.error("Del admin error " + str(error))
            bot.send_message(message.chat.id,"Для видалення адміністратора введіть:\n /del_admin user_id\n/help")         

@bot.message_handler(commands=["list_admins"])
def list_admin(message):
    if not is_private(message):
        return
    if str(message.from_user.id) in admins:
        try:
            bot.send_message(message.chat.id,"Адміністратори:\n"+"\n".join(admins))
        except Exception as error:
            logger.error("List admin error " + str(error))

def hms_string(sec_elapsed):
    h = int(sec_elapsed / (60 * 60))
    m = int((sec_elapsed % (60 * 60)) / 60)
    s = sec_elapsed % 60.
    return "{}:{:>02}:{:>05.2f}".format(h, m, s)

@bot.message_handler(commands=["stats"])
def stats(message):
    if not is_private(message):
        return
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
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        logger.info("Kill command")
        if users[str(message.from_user.id)].username is None:
        	adminname=""
        else:
        	adminname="@"+str(users[str(message.from_user.id)].username)
        send2admins("Бота зупинив користувач: "+str(message.from_user.id)+adminname)
        bot.stop()

@bot.message_handler(commands=["ban"])
def ban(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/ban (\d+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[str(user_id)]=user.User(str(user_id))
                users[str(user_id)].blocked=True
                users[str(user_id)].save()
                bot.send_message(message.chat.id,"User banned")
                if users[str(message.from_user.id)].username is None:
                	adminname=""
                else:
                	adminname="@"+str(users[str(message.from_user.id)].username)
                bot.send_message(user_id,"Вас заблоковано адміністратором "+adminname)
        except Exception as error:
            logger.error("Ban error " + str(error))
            bot.send_message(message.chat.id,"Для блокування користувача введіть:\n /ban user_id \n/help") 

@bot.message_handler(commands=["unban"])
def ban(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    if str(message.from_user.id) in admins:
        try:
            match=re.match('/unban (\d+)',message.text)
            if match.group(1) != "" :
                user_id = match.group(1)
                if user_id not in users:
                    users[str(user_id)]=user.User(str(user_id))
                users[str(user_id)].blocked=False
                users[str(user_id)].save()
                bot.send_message(message.chat.id,"User unbanned")
                if users[str(message.from_user.id)].username is None:
                	adminname=""
                else:
                	adminname="@"+str(users[str(message.from_user.id)].username)
                bot.send_message(user_id,"Вас розблоковано адміністратором "+adminname)
        except Exception as error:
            logger.error("Ban error " + str(error))
            bot.send_message(message.chat.id,"Для розблокування користувача введіть:\n /unban user_id \n/help") 

@bot.message_handler(commands=["email"])
def email(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    logger.debug(message)
    if message.from_user.id not in users:
        if not is_registered(message):
        	return 
    if users[str(message.from_user.id)].blocked:
        blocked(message)
        return 
        
    try:
        try:
            match=re.match('/email (.+@.+\..+)',message.text)
            if match.group(1) != "" and users[str(message.from_user.id)].registered:
                users[str(message.from_user.id)].email = match.group(1)
                users[str(message.from_user.id)].save()
                bot.send_message(message.chat.id,"Ваш емейл змінено на " + users[str(message.from_user.id)].email)
        except Exception as error:
            logger.error("Illegal service provided " + str(error))
            bot.send_message(message.chat.id,"Для зміни емейлу введіть команду:\n /email ваш_емейл\n/help ") 
    except Exception as error:
        logger.error("Email error" + str(error))

@bot.message_handler(commands=["start"])
def start(message):
    if not is_private(message):
        return
    try:
        logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+str(message.content_type)+"]: "+str(message.text))
        logger.debug(message)
        if is_registered(message):
            if users[str(message.from_user.id)].blocked:
                blocked(message)
            else:
                bot.send_message(message.chat.id, config['default']['start_msg'])
    except Exception as error:
        logger.error("Start error" + str(error))

@bot.message_handler(commands=["name"])
def name(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    logger.debug(message)
    if message.from_user.id not in users:
        if not is_registered(message):
            return 
    if users[str(message.from_user.id)].blocked:
        blocked(message)
        return 
    users[str(message.from_user.id)].fio=""
    users[str(message.from_user.id)].fio_provided=False
    users[str(message.from_user.id)].registered=False
    is_registered(message)

@bot.message_handler(commands=["finish"])
def finish(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    logger.debug(message)
    if message.from_user.id not in users:
        if not is_registered(message):
            return 
    if users[str(message.from_user.id)].blocked:
        blocked(message)
        return 
    try:
        if users[str(message.from_user.id)].uuid != "":
            try:
                if "responsible_email" in config['service'+str(users[str(message.from_user.id)].selected)] and config['service'+str(users[str(message.from_user.id)].selected)]['responsible_email'] :
                    logger.info("Підготовка листа")
                    msg = users[str(message.from_user.id)].get_email_msg()
                    logger.debug(msg.as_string());
                    msg['From'] = config['email']['from_addr'] 
                    msg['To'] = config['service'+str(users[str(message.from_user.id)].selected)]['responsible_email']
                    msg['Subject'] = "Прийнято звернення "+ users[str(message.from_user.id)].uuid
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
                    logger.info("Відправка листа " + users[str(message.from_user.id)].uuid)
                    s.sendmail(msg['From'], msg['To'], text)
                    if users[str(message.from_user.id)].email !="":
                         msg['To']=users[str(message.from_user.id)].email
                         s.sendmail(msg['From'], msg['To'], text)
                    logger.debug("Sendmail: "+str(s));
                    s.quit() 
                    logger.debug("Quit: "+str(s));
                    
                if "responsible_tg" in config['service'+str(users[str(message.from_user.id)].selected)] and  config['service'+str(users[str(message.from_user.id)].selected)]['responsible_tg'] :
                    msg = users[str(message.from_user.id)].get_tg_msg()
                    bot.send_message(config['service'+str(users[str(message.from_user.id)].selected)]['responsible_tg'],"Подано нове звернення:\n"+msg)
                    files=users[str(message.from_user.id)].get_tg_files()
                    for doc in files:
                        bot.send_document(config['service'+str(users[str(message.from_user.id)].selected)]['responsible_tg'], open(doc, 'rb'))
                    logger.info(files)
                users[str(message.from_user.id)].selected=0
                users[str(message.from_user.id)].location_provided = False
                users[str(message.from_user.id)].service_provided = False
                users[str(message.from_user.id)].uuid = ""
                users[str(message.from_user.id)].location = {}
                bot.send_message(message.chat.id,"Дякуємо, Ваше звернення взяте на обробку", reply_markup = types.ReplyKeyboardRemove())
            except Exception as error:
                logger.error("Sent error " + str(error))
        is_selected(message)
    except Exception as error:
        logger.error("Finish error" + str(error))


@bot.message_handler(commands=["service"])
def service(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    logger.debug(message)
    if message.from_user.id not in users:
        if not is_registered(message): 
            return 
    if users[str(message.from_user.id)].blocked:
        blocked(message)
        return 
    try:
        match=re.match('/service (\d+) ?.*',message.text)
        if int(match.group(1)) >0 :
            users[str(message.from_user.id)].selected = int(match.group(1))
    except Exception as error:
        logger.error("Illegal service provided " + str(error))
    is_selected(message)


@bot.message_handler(content_types=['contact','text','location','document','video','photo','audio','voice'])
def other_messages(message):
    if not is_private(message):
        return
    logger.info("Отримано повідомлення від \""+str(message.from_user.id)+"\" ["+message.content_type+"]: "+str(message.text))
    logger.debug(message)
    if message.from_user.id not in users:
        if not is_registered(message):
            return 
    if users[str(message.from_user.id)].blocked:
        blocked(message)
        return 
    is_selected(message)
    

if __name__ == '__main__':
    send2admins("Бот рестартовано, /help")
    bot.polling(none_stop=True)

logger.info('Closing TelegramBot')
