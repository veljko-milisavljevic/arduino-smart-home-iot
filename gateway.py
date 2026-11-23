import os
import sys
import urllib.request
import requests
import serial
import time
from threading import Thread
from matplotlib import pyplot as plt
import numpy as np
import datetime
import smtplib
import imaplib
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; plain environment variables work too

def require_env(name):
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable {name}. Copy .env.example to .env and fill it in.")
    return value

PORT = os.environ.get('SERIAL_PORT', 'COM5')
BAUD_RATE = 9600
CHANNEL_ID = require_env('THINGSPEAK_CHANNEL_ID')
API_KEY_WRITE = require_env('THINGSPEAK_WRITE_KEY')
API_KEY_READ = require_env('THINGSPEAK_READ_KEY')
ALERT_EMAIL = require_env('ALERT_EMAIL')
ALERT_EMAIL_APP_PASSWORD = require_env('ALERT_EMAIL_APP_PASSWORD')

BASE_URL = 'https://api.thingspeak.com'
WRITE_URL = f'{BASE_URL}/update?api_key={API_KEY_WRITE}'

def receive(serialCom):
    while True:
        try:
            if serialCom.in_waiting > 0:
                receivedMessage = serialCom.readline().decode('ascii').strip()
                processData(receivedMessage)
        except Exception as e:
            print(f"Serial error: {e}")
        time.sleep(1)

def processData(data):
    dataList = data.split()
    if len(dataList) >= 4:
        processedData = {
            "temp": dataList[0],
            "osv": dataList[1],
            "vrata": dataList[2],
            "pokreti": dataList[3]
        }
        sendTS(processedData)
        
        if int(dataList[3]) > 0:
            sendQuickAlert("ALARM: Detektovan pokret!", "Sistem je detektovao kretanje u objektu.")

def sendTS(data):
    url = f"{WRITE_URL}&field1={data['temp']}&field2={data['osv']}&field3={data['vrata']}&field4={data['pokreti']}"
    urllib.request.urlopen(url)

def checkMail(email_conn, serialCom):
    email_conn.select('inbox')
    while True:
        commands = {
            'UPALI VENTILACIJU': 'V_ON', 'UGASI VENTILACIJU': 'V_OFF',
            'UPALI SVETLO': 'L_ON', 'UGASI SVETLO': 'L_OFF',
            'UPALI PIR': 'PIR_ON', 'UGASI MOD POKRETA': 'PIR_OFF',
            'OTVORI GARAZU': 'G_ON', 'ZATVORI GARAZU': 'G_OFF',
            'IZVESTAJ': 'REPORT'
        }

        for subject, serial_cmd in commands.items():
            retcode, response = email_conn.search(None, f'(SUBJECT "{subject}" UNSEEN)')
            if response[0]:
                print(serial_cmd)
                if serial_cmd == 'REPORT':
                    sendReport()
                else:
                    serialCom.write(serial_cmd.encode('ascii'))
                
                for id in response[0].split():
                    email_conn.store(id, '+FLAGS', '\\Seen')
        time.sleep(10)

def sendReport():
    read_url = f"{BASE_URL}/channels/{CHANNEL_ID}/feeds.json?api_key={API_KEY_READ}&days=1"
    data = requests.get(read_url).json()
    feeds = data.get("feeds", [])

    temp_vals = [float(f['field1']) for f in feeds if f.get('field1')]
    osv_vals = [float(f['field2']) for f in feeds if f.get('field2')]
    
    garage_total = sum(1 for f in feeds if f.get('field3') == '1')
    motion_total = sum(1 for f in feeds if f.get('field4') == '1')

    plt.figure(figsize=(8, 4))
    plt.plot(temp_vals, color='red', label='Temp (C)')
    plt.title(f"Dnevna Temperatura - {datetime.date.today()}")
    plt.ylabel("Celsijus")
    plt.grid(True)
    temp_file = "temp_plot.png"
    plt.savefig(temp_file)
    plt.close()

    plt.figure(figsize=(8, 4))
    plt.plot(osv_vals, color='orange', label='Svetlo (%)')
    plt.title(f"Dnevna Osvetljenost - {datetime.date.today()}")
    plt.ylabel("Procenat")
    plt.grid(True)
    light_file = "light_plot.png"
    plt.savefig(light_file)
    plt.close()

    message = MIMEMultipart()
    message['Subject'] = 'Dnevni Izvestaj sa Senzora'

    htmlText = f"""
    <html>
        <body>
            <h1>Dnevni Izvestaj - {datetime.date.today()}</h1>
            <p><b>Temperatura:</b> Min {np.min(temp_vals):.2f}, Max {np.max(temp_vals):.2f}, Avg {np.mean(temp_vals):.2f}</p>
            <p><b>Osvetljenje:</b> Min {np.min(osv_vals):.2f}, Max {np.max(osv_vals):.2f}, Avg {np.mean(osv_vals):.2f}</p>
            <hr>
            <p><b>Ukupno otvaranja garaze:</b> {garage_total}</p>
            <p><b>Ukupno detektovanih pokreta:</b> {motion_total}</p>
        </body>
    </html>
    """
    message.attach(MIMEText(htmlText, 'html'))

    for filename in [temp_file, light_file]:
        with open(filename, 'rb') as f:
            img = MIMEImage(f.read())
            img.add_header('Content-ID', f'<{filename}>')
            message.attach(img)

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(ALERT_EMAIL, ALERT_EMAIL_APP_PASSWORD)
    server.sendmail(ALERT_EMAIL, ALERT_EMAIL, message.as_string())
    server.quit()
    print("Izvestaj uspesno poslat sa graficima.")

def sendQuickAlert(subject, body, is_html=False):
    message = MIMEMultipart()
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html' if is_html else 'plain'))
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(ALERT_EMAIL, ALERT_EMAIL_APP_PASSWORD)
    server.sendmail(ALERT_EMAIL, ALERT_EMAIL, message.as_string())
    server.quit()

try:
    email = imaplib.IMAP4_SSL('imap.gmail.com')
    email.login(ALERT_EMAIL, ALERT_EMAIL_APP_PASSWORD)

    serialCommunication = serial.Serial(PORT, BAUD_RATE)

    Thread(target=checkMail, args=(email, serialCommunication,), daemon=True).start()
    Thread(target=receive, args=(serialCommunication,), daemon=True).start()

    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Program terminated.")