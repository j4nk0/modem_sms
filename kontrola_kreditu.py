#!/usr/bin/python3
# -*- coding: UTF-8 -*-

# Ján Gajdica 17. 9. 2016

import serial
from time import sleep
import threading as thd
import subprocess as sub
import tkinter as tkold
import tkinter.ttk as tk

def fail ():
    window.buttonsDisable()
    window.display ('Modem nereaguje! Opakujte neskôr, prosím.')

def stopNetworking ():
    """Stops network manager from using and blocking
    the serial port of the modem. May raise sub.CalledProcessError."""
    # modems port '/dev/ttyUSB0' stays in use - causes double access!!!
    #sub.run (['nmcli', 'connection', 'down', '4ka'],    \
    # Disable Broadband instead:
    sub.run (['nmcli', 'radio', 'wwan', 'off'], \
        stderr = sub.DEVNULL,                   \
        stdout = sub.DEVNULL,                   \
         check = True)

def startNetworking ():
    """Starts the network manager connection through
    the modem - serial port must not be in use when calling this.
    May raise sub.CalledProcessError."""
    sub.run (['nmcli', 'radio', 'wwan', 'on'],  \
        stderr = sub.DEVNULL,                   \
        stdout = sub.DEVNULL,                   \
         check = True)
    attempts = 10   # takes cca 5 attempts to succeed
    while True:
        try:
            sub.run (['nmcli', 'connection', 'up', '4ka'],  \
                stderr = sub.DEVNULL,                       \
                stdout = sub.DEVNULL,                       \
                 check = True)
            return
        except sub.CalledProcessError:
            attempts -= 1
            if attempts == 0: raise
            sleep (0.5) # Waiting for network manager - nmcli

def todaysDate ():
    """Returns Datetime object or raises ValueError.
    date is called to give values in format which
    is consistent with modem in text mode."""
    attempts = 3
    while True:
        try:
            stdout = ''
            proc = sub.Popen (['date', '+%y/%m/%d,%H:%M:%S+'],  \
                universal_newlines = True,                      \
                             stdin = sub.DEVNULL,               \
                            stderr = sub.DEVNULL,               \
                            stdout = sub.PIPE)
            stdout, _ = proc.communicate()
            return Datetime (stdout.strip())
        except ValueError:
            attempts -= 1
            if attempts == 0: raise
            continue

class Initializer (thd.Thread):
    """Stops network connection through serial port,
    freeing it for communication with modem.
    Sets up modem for SMS send/receive in text mode.
    Doesn't turn the networking back on."""

    def __init__ (self, window, modem):
        super().__init__()
        self.window = window
        self.modem = modem

    def run (self):
        self.window.buttonsDisable()
        self.window.display ('Ruší sa sieťové pripojenie...')
        try:
            stopNetworking()
            self.modem.getPort()
            self.window.display ('Pripájanie do mobilnej siete...')
            assert self.modem.initCellular()
            self.window.display ('Inicializácia dokončená.\nMôžete poslať SMS.')
            self.window.spotrebaPress() # Default action
        except:
            #sub.CalledProcessError:
            #serial.serialutil.SerialException:
            #AssertionError:
            fail()

class SMShandler (thd.Thread):
    """Constructs modem instance, sends SMS (plain ASCII from SMStext)
    to given number (sendTo), waits for response - from the number - 
    and displays it through given window. 
    Expects modems port to be acquired and free to use."""

    def __init__ (self, window, modem, sendTo, SMStext):
        super().__init__()
        self.to = int (sendTo)
        self.text = str (SMStext)
        self.window = window
        self.modem = modem

    def run (self):
        try:
            self.window.buttonsDisable()
            self.window.display ('Konfigurácia modemu...')
            assert self.modem.initSMS()
            self.window.display ('Posiela sa SMS...')
            maxAttempts = 5
            for attempt in range (1, maxAttempts + 1):
                if self.modem.sendSMS (self.to, self.text): break
                if attempt == maxAttempts: raise AssertionError
            self.window.display ('SMS odoslaná, čaká sa na odpoveď...')
            maxAttempts = 400   # Receiving SMS response:
            for attempt in range (1, maxAttempts + 1):
                if attempt == maxAttempts:
                    raise AssertionError
                if self.modem.cntSMS() == 1: break
                sleep (0.25)   # Waiting for sms

            message = modem.readSMS()[0]    # The one and only message
            if int (message[0]) != int (self.to):   # number of the message sender
                # message is not the expected response from adressate
                raise AssertionError
            try:
                if message[1] != todaysDate(): raise AssertionError
            except ValueError:
                pass    # todaysDate cannot be determined so kip the check

            self.window.display (message[2])    # Display the actual message text
            self.window.buttonsEnable()
        except AssertionError:
            fail()

class Datetime (object):
    """represents year, month, day, hour, minute and second of the day"""

    def __init__ (self, _string):
        """parses string in format specific
        to modem response in text mode.
        All values are strings."""
        date, time = _string.split (',')
        self.year, self.month, self.day = date.split ('/')
        time, _ = time.split ('+')
        self.hour, self.minute, self.second = time.split (':')

    def __str__ (self):
        return self.day + '.' + self.month + '.' + self.year + ' - '  \
            + self.hour + ':' + self.minute + ':' + self.second

    def __repr__ (self):
        return "'Datetime=" + self.__str__() + "'"

    def __eq__ (self, other):
        """True, only if dates match - exact time is irrelevant!"""
        return   self.year == other.year    \
            and self.month == other.month   \
            and   self.day == other.day

    def __ne__ (self, other):
        return not self.__eq__(other)

class Modem (object):
    """Represents USB mobile broadband modem"""

    def __init__ (self):
        """Initialization without acquiring port,
        getPort needs to be called before any other function!
        This is so that placeholder empty modem can be __initialised__
        without throwing exceptions and actual port acquiring needs to
        happen only once. This should awoid multiple access on port."""
        pass

    def getPort (self):
        """opens USB port:
        use write_timeout or writeTimeout depending on version of pyserial"""
        self.port = serial.Serial (port = '/dev/ttyUSB0',   \
                               baudrate = 9600,             \
                                timeout = 0.2,              \
                           writeTimeout = 0.2)
 
    def chat (self, command):
        """sends bytearray containing command to modem,
        returns response as list of bytearrays.
        Never raises any exception."""
        self.port.write (command)
        self.port.flush()
        res = b''
        while True:
            try:
                line = self.port.read (100)
                if line == b'': break
                res += line
            except: pass
        li = res.split (b'\r\n')[1:]
        try:
            while True: li.remove (b'')
        except ValueError:
            pass
        return li

    def isOK (self):
        """Checks that modem is properly connected to PC,
        receiving commands and capable of respondig.
        Returns bool."""
        return self.chat (b'AT\r') == [b'OK']

    def initCellular (self):
        """Initialise modem on cellular network.
        Useful after the end of data connection."""
        attempts = 0
        maxAttempts = 100
        li = [self.isOK, self.isPINok, self.radioON, self.isRegistered]
        for func in li:
            while not func():
                sleep (0.1)
                attempts += 1
                if attempts == maxAttempts: return False
        return True

    def initSMS (self):
        """Sets important modem settings in order to send SMS.
        Useful after the end of data connection."""
        attempts = 0
        maxAttempts = 100
        li = [self.isOK, self.setModeText, self.setEncodingIRA,   \
            self.setStorageSM, self.deleteSMS]
        for func in li:
            while not func():
                sleep (0.1)
                attempts += 1
                if attempts == maxAttempts: return False
        attempts = 0  # 100 attempts remaining:
        while True:
            cnt = self.cntSMS()
            if cnt >= 0: break
            attempts += 1
            if attempts == maxAttempts: return False
            sleep (0.1)
        if cnt > 0: return False
        return True

    def isPINok (self):
        """Checks that sim is unlocked (isn't waiting for pin)"""
        return self.chat (b'AT+CPIN?\r') == [b'+CPIN: READY', b'OK']
        
    def radioON (self):
        """Switches on the transmitter - solves NO CARRIER error"""
        return self.chat (b'AT+CFUN=1\r') == [b'OK']

    def isRegistered (self):
        """Checks that modem is registered in home network
        and network selection is automatic."""
        return self.chat (b'AT+CREG?\r') == [b'+CREG: 0,1', b'OK']

    def isModeText (self):
        """Checks that modem is in text mode (as opposed to PDU mode)."""
        return self.chat (b'AT+CMGF?\r') == [b'+CMGF: 1', b'OK']

    def setModeText (self):
        """Switches (from PDU) to text mode. If mode is already text, 
        switching occurs anyway."""
        return self.chat (b'AT+CMGF=1\r') == [b'OK']

    def setEncodingIRA (self):
        """Sets SMS encoding scheme to IRA - just works.
        The setting has tendency to change by itself wich causes
        ERROR 302 on working with sms."""
        return modem.chat (b'AT+CSCS="IRA"\r') == [b'OK']

    def setStorageSM (self):
        """Sets SMS storage to SIM card - just works.
        The setting has tendency to change by itself wich causes
        ERROR 302 on working with sms."""
        try:
            return modem.chat (b'AT+CPMS="SM"\r')[1] == b'OK'
        except IndexError:
            pass
        return False

    def deleteSMS (self):
        """Deletes all SMS messages stored on modem."""
        return  self.chat (b'AT+CMGD=0,4\r') == [b'OK']

    def cntSMS (self):
        """Returns int - number of sms messages currently in storage.
        If requst doesn't succeed, returns -1."""
        response = modem.chat (b'AT+CPMS?\r')
        try:
            if response[1] != b'OK': return -1
            return int (str (response[0]).split (',')[1])
        except IndexError:
            return -1
        
    def sendSMS (self, to, message):
        """Sends sms in text mode. to - number to send SMS to.
        message - text of the message - ASCII only due to text mode."""
        response = self.chat (  \
            b'AT+CMGS="'        \
            + bytearray (str (to), 'ASCII') + b'"\r')
        try:
            if response[0] != b'> ': return False   # prompt for sms input
        except IndexError: return False
        response = self.chat (                  \
            bytearray (str (message), 'ASCII')  \
            + b'\r\x1A')
        for part, i in zip (response, range (99)):
            if part == b'OK':
                if response[i - 1][:6] == b'+CMGS:':
                    return True
        return False
        
    def readSMS (self):
        """Returns text of sms messages stored on modem
        as list of tuples representing messages with metadata.
        Each message has the foolowing structure:
        tuple (str (number_of_sender), datetime (own), str (text))."""
        messages = list()
        n = 1   #line nr
        for line in self.chat (b'AT+CMGL="ALL"\r'):
            # every odd line holds metadata
            if line == b'OK': break
            line = str (line)
            if n % 2 == 1:
                line = line.split ('"')
                senderNr = line [3]
                datetime = Datetime (line[5])
                messages.append ([senderNr, datetime]) 
            else:
                messages[-1].append (line[2:-1])
                messages[-1] = tuple (messages[-1])
            n += 1
        return messages

class Window (tk.Frame):
    """The one and only gui window"""

    def __init__(self, master = None):
        super().__init__(master)
        master.title ("Kontrola kreditu")
        master.minsize (230, 140)
        master.maxsize (230, 140)
        # Enable resizing:
        master.grid_rowconfigure (0, weight = 1)
        master.grid_columnconfigure (0, weight = 1)
        # Enable changing label text:
        self.text = tkold.StringVar()
        self.initWidgets()
        self.startContentManager()

    def initWidgets (self):
        """Text 'Label' and two buttons"""
        self.textLabel = tk.Label (self)
        self.textLabel['textvariable'] = self.text
        self.textLabel['anchor'] = 'nw'

        self.spotreba = tk.Button (self)
        self.spotreba['text'] = 'SPOTREBA'
        self.spotreba['command'] = self.spotrebaPress

        self.giga = tk.Button (self)
        self.giga['text'] = 'GIGA'
        self.giga['command'] = self.gigaPress
        self.giga['width'] = 8  # len (self.spotreba['text])

    def startContentManager (self):
        """Using grid only, actually draw the gui."""
        self.grid (sticky = 'NSWE')
        self.textLabel.grid (
                   row = 0,     \
                column = 0,     \
            columnspan = 5,     \
                sticky = "NWSE",\
                  padx = 20,    \
                  pady = 10)
        self.spotreba.grid (
               row = 1,     \
            column = 1,     \
            sticky = "SW",  \
              pady = 5)
        self.giga.grid (
               row = 1,     \
            column = 3,     \
            sticky = "SE",  \
              pady = 5)
        self.grid_rowconfigure    (0, weight = 1)
        self.grid_columnconfigure (0, weight = 1)
        self.grid_columnconfigure (2, weight = 2)
        self.grid_columnconfigure (4, weight = 1)

    def buttonsDisable (self):
        self.spotreba.configure (state = tkold.DISABLED)
        self.    giga.configure (state = tkold.DISABLED)

    def buttonsEnable (self):
        self.spotreba.configure (state = tkold.NORMAL)
        self.    giga.configure (state = tkold.NORMAL)

    def display (self, text):
        """Stringvar non-stop watched by tkinter"""
        maxTextLen = 32
        if len (text) < maxTextLen:
            self.text.set (text)
            return
        words = text.split ()
        lines = ['']
        n = 0
        for word in words:
            newline = lines[n] + ' ' + word
            if len (newline) < maxTextLen:
                lines[n] = newline
            else:
                n += 1
                lines.append (word)
        self.text.set ('\n'.join (lines))

    def spotrebaPress (self):
        """What to do when button spotreba is pressed in gui"""
        SMShandler (self, modem, 950, 'SPOTREBA').start()

    def gigaPress (self):
        """What to do when button giga is pressed in gui"""
        SMShandler (self, modem, 950, 'GIGA').start()

kTinkerRoot = tkold.Tk()
kTinkerRoot.style = tk.Style()
kTinkerRoot.style.theme_use ('clam')    # Looks the best
window = Window (master = kTinkerRoot)
modem = Modem ()
Initializer (window, modem).start()
window.mainloop()
startNetworking()   # switch it back on

