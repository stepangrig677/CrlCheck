#
# скрипт :CrlCheck.py 
# конфиг: CrlCheck.conf 
# запуск: python3 CrlCheck.py
# требуется openssl
#
import logging
import urllib.request
import re
import smtplib
import threading
from subprocess import Popen, PIPE
import time
import os
from datetime import datetime, timedelta
import traceback


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

fhandler = logging.FileHandler('logger1.log')
fhandler.setLevel(logging.INFO)

chandler = logging.StreamHandler()
chandler.setLevel(logging.INFO)
logger.addHandler(chandler)

formatter = logging.Formatter('%(asctime)s - %(message)s')
fhandler.setFormatter(formatter)

logger.addHandler(fhandler)


agentName=""
timeOut=0
CrlPaths=[]
AlertEmails=[]
SmtpServers=[]

Errors=""

def UseConf():
    f = open('CrlCheck.conf', 'r')
    text=f.read()

    agentName=re.search('AgentName: "[A-Za-z]*"',text).group(0)[12:-1]

    timeOut=int(re.search('TimeOut: [0-9]*',text).group(0)[9:])

    crlPaths=re.search('CrlPaths: "[a-zA-Z:/\.\-; \r\n0-9]*"',text).group(0)[11:-1]
    [CrlPaths.append(x.replace('\n', '').replace(' ', '')) for x in crlPaths.split(";")]

    alertEmails=re.search('AlertEmails: "[a-zA-Z@/0-9/\.\-; \r\n]*"',text).group(0)[14:-1]
    [AlertEmails.append(x.replace('\n', '').replace(' ', '')) for x in alertEmails.split(";")]

    smtpServers=re.search('SmtpServers: "[a-zA-Z@/0-9/\.\-;: \r\n#]*"',text).group(0)[14:-1]
    [SmtpServers.append(x.replace('\n', '').replace(' ', '').split("#")) for x in smtpServers.split(";")]



def ParsFilesAdreses(url='https://squaretrade.ru/help'):
    if url[-1]!='/': url+='/'
    found=[]
    logger.info('downloading page '+url+'...')
    try:
        html = str(urllib.request.urlopen(url).read())
        logger.info(url+' downloaded sucesfully')
        found = re.findall('http://[a-zA-Z0-9/\.\-]*\.crl', html)
        found2 = re.findall('"[a-zA-Z0-9/\.\-]*\.crl', html)
        [found.append(url+str(x[x.find('/',3):])) for x in found2 if '.crl' in (x[x.find('/',3):]) ]
        [found.append(url+str(x[1:])) for x in found2 ]
        [logger.info('    '+x) for x in found]
        logger.info('CLR adresses from '+url+' parsed successfully')    

    except:
        logger.info('Warning: '+url+' page not downloaded ')
        global Errors
        Errors=Errors+'\nWarning: '+url+' page not downloaded '

    return found


def GetFileByUrl(url="http://crl.skynet-kazan.com/squaretrade2016.crl", filename="tmp.clr"):
    logger.info('downloading CLR file '+url+'...')
    try:
        down = urllib.request.urlopen(url).read()
        f = open(filename, "wb")
        f.write(down)
        f.close()
        logger.info('CLR file from '+url+' downloaded successfully')    
    except:
        logger.info('Warning: '+url+' CLR file not downloaded ')
        filename=""
    return filename    



def CheckCRLUpdate(clrfile="", pemfile="crl.pem"):
    result=""
    global Errors
    if clrfile=="": return ""
    command="openssl crl -in "+clrfile+" -inform DER -out "+pemfile
    Popen(command, shell=True, stdin=PIPE, stdout=PIPE)
    logger.info(command)
    
    stoptime = datetime.now() + timedelta(seconds=5)
    while (not os.path.exists(pemfile)) and datetime.now()<=stoptime: pass
    if datetime.now()>=stoptime : 
	    logger.info('Warning: "'+command+'" not work ')
	    Errors=Errors+'\nWarning: "'+command+'" not work '
	    return ""
	
    command="openssl crl -in "+pemfile+" -noout -text"
    infocrl=str(Popen(command, shell=True, stdin=PIPE, stdout=PIPE).stdout.read())
    logger.info(command)
    try:
        time=(re.findall('Last Update:[ :a-zA-Z0-9]*GMT', infocrl))[0][13:33]
        date_object = datetime.strptime(time, '%b %d %H:%M:%S %Y')
        date_agging=datetime.now()-timedelta(minutes=timeOut)
        if date_object<date_agging :
            logger.info(time+' - CRL too old')
            result= str(date_object)+' << '+str(date_agging)[:-7]
    except:
        logger.info('Warning: CRL Last Update time not found ')
        Errors=Errors+'\nWarning: CRL Last Update time not found '
        
    os.remove(clrfile)
    os.remove(pemfile)
    return result



def SendEmails(EMAILS=['test6771@gmail.com'],
               TEXT='Hello from python.',
               SUBJECT = "test",
               mail_sender = 'test6772@gmail.com',
               HostPort= 'smtp.gmail.com:587',
               mail_passwd = 'Password'):

    smtp_split=HostPort.split(":")
    smtp_host=smtp_split[0]
    smtp_port=25
    if len(smtp_split)>1: smtp_port=int(smtp_split[1])
    logger.info(' email sended from '+mail_sender)
    try:
        if 'mail.ru' in smtp_host or 'yandex.ru' in smtp_host:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else: server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.login(mail_sender, mail_passwd)

        for TO in EMAILS:
            BODY = '\r\n'.join(['To: %s' % TO,
				'From: %s' % mail_sender,
				'Subject: %s' % SUBJECT,
				'', TEXT])
            server.sendmail(mail_sender, [TO], BODY)
            logger.info('   email sended to'+TO)
    except:
        logger.info('Warning: email not sended ')
        global Errors
        Errors=Errors+'\nWarning: email not sended from '+mail_sender 
        return False
    
    server.quit()
    return True


def SendEmailsAnyway(Text=" ",Subject="CRL too old"):
    for x in SmtpServers:
        if len(x)>2 :
               SendEmails(EMAILS=AlertEmails,
               TEXT=Text,
               SUBJECT = Subject,
               mail_sender = x[0],
               HostPort= x[1],
               mail_passwd = x[2]) 


try:
    UseConf()
    
except:
    logger.info('Error: damaged or missing CrlCheck.conf ')
    Errors=Errors+'\nError: damaged or missing CrlCheck.conf '
    exit()



try :
    CRLAdresses=[]
    for x in CrlPaths:
        CRLAdresses.extend(ParsFilesAdreses(str(x)))
    
    for x in CRLAdresses:
        Time=CheckCRLUpdate(GetFileByUrl(url=x))
        if Time!="":
            logger.info('\n CRL file: '+x+' is too old. Last Update: '+Time)
            Errors=Errors+'\n CRL file: '+x+' is too old. Last Update: '+Time

except  Exception as e:
    logger.info(traceback.format_exc())
    Errors=Errors+'\n'+traceback.format_exc()

  
#Есть ошибки
if Errors!="":
    SendEmailsAnyway(Subject = "Problems with CRL checking",Text='Errors:\n'+Errors)
    print('1')
    #print(Errors)

#Нет ошибок    
else:    
    print('0')
