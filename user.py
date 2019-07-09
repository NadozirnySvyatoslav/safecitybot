from pathlib import Path
import configparser
import os
import uuid
from email.mime.multipart import MIMEMultipart 
from email.mime.text import MIMEText 
from email.mime.base import MIMEBase 
from email import encoders 

users_dir = "users"
requests_dir = "requests"

class User:
    username = ""
    id = ""
    phone_number = ""
    fio = ""
    email = ""
    chat_id = ""
    registered = False
    phone_number_provided = False
    fio_provided = False
    location_provided = False
    service_provided = False
    blocked = False
    selected = 0
    uuid = '' 
    location ={}
    def __init__(self,id):
        self.id = id
        if os.path.exists(users_dir + os.path.sep + self.id + os.path.sep + 'config.ini'):
            config = configparser.ConfigParser()
            config.read(users_dir + os.path.sep + self.id + os.path.sep + 'config.ini')
            self.username=config['userdata']['username']
            self.chat_id=config['userdata']['chat_id']
            self.blocked=config['userdata'].getboolean('blocked')
            self.phone_number=config['userdata']['phone_number']
            self.fio=config['userdata']['fio']
            self.email=config['userdata']['email']
            self.registered=config['userdata'].getboolean('registered')
            if self.phone_number != "" and self.phone_number is not None:
                self.phone_number_provided = True;
            if self.fio != "" and self.fio is not None:
                self.fio_provided = True;

    def save(self):
        if not os.path.exists(users_dir):
            os.makedirs(users_dir)
        if not os.path.exists(users_dir + os.path.sep + self.id):
            os.makedirs(users_dir + os.path.sep + self.id)
        config = configparser.ConfigParser()
        config['userdata'] = { 'username' : self.username,
                               'phone_number' : self.phone_number,
                               'fio' : self.fio,
                               'email' : self.email,
                               'blocked' : self.blocked,
                               'chat_id' : self.chat_id,
                               'registered' : self.registered }
        with open(users_dir + os.path.sep + self.id + os.path.sep + 'config.ini',"w") as configfile:
            config.write(configfile)

    def start(self):
        self.uuid = str(uuid.uuid4())
        if not os.path.exists(requests_dir):
            os.makedirs(requests_dir)
        if not os.path.exists(requests_dir + os.path.sep + self.uuid):
            os.makedirs(requests_dir + os.path.sep + self.uuid)
        if not os.path.exists(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches'):
            os.makedirs(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches')
            fo=open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'data.txt',"a")
            fo.write("""Username: %s
User ID: %s
FIO: %s
Phone: %s
Email: %s
-------------------------
""" % ( self.username, self.id, self.fio, self.phone_number, self.email) )
            fo.close()

    def get_email_msg(self):
        msg = MIMEMultipart() 
        #msg.attach(MIMEText(body, 'plain')) 
        filename = 'data.txt'
        with open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'data.txt', 'r') as fp:
            msg.attach(MIMEText(fp.read()))


        for filename in os.listdir(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches' ):
            attachment = open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches' + os.path.sep + filename, "rb") 
            p = MIMEBase('application', 'octet-stream') 
            p.set_payload((attachment).read()) 
            encoders.encode_base64(p) 
            p.add_header('Content-Disposition', "attachment; filename= %s" % filename) 
            msg.attach(p) 
        return msg
    def get_tg_msg(self):
        filename = 'data.txt'
        with open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'data.txt', 'r') as fp:
            text=fp.read()
        return text
    def get_tg_files(self):
        files=[]
        for filename in os.listdir(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches' ):
            files.append(requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches' + os.path.sep + filename)
        return files

    def append(self, message):
        if message.content_type=='text':
            fo=open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'data.txt',"a")
            fo.write(message.text +"\n")
            fo.close()
        if message.content_type=='location':
            fo=open(requests_dir + os.path.sep + self.uuid + os.path.sep + 'data.txt',"a")
            fo.write("Location: " + str(self.location) +"\n")
            fo.close()


    def filespath(self,filename):
        return requests_dir + os.path.sep + self.uuid + os.path.sep + 'attaches'+ os.path.sep + filename