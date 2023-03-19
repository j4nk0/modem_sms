#!/usr/bin/python3

from time import sleep
import serial

class Datetime (object):
    """represents year, month, day, hour, minute and second of the day"""

    def __init__(self, _string):
        """parses string in format specific
        to modem response in text mode.
        All values are strings."""
        self.string = _string
        date, time = _string.split (',')
        self.year, self.month, self.day = date.split ('/')
        time, _ = time.split ('+')
        self.hour, self.minute, self.second = time.split (':')

    def __str__(self):
        return self.day + '.' + self.month + '.' + self.year + ' - '  \
            + self.hour + ':' + self.minute + ':' + self.second

    def __repr__(self):
        return "'Datetime=" + self.__str__() + "'"

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
                               baudrate = 9600,           \
                                timeout = 0.2,              \
                           writeTimeout = 0.2)#,              \
                                 #rtscts = True)
                                #xonxoff = True)
 
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
        #self.port.flush()
        li = res.split (b'\r\n')[1:]
        try:
            while True: li.remove (b'')
        except ValueError:
            pass
        return li

    #print (modem.chat (b'AT+CMEE?\r')) # Error reporting way
    #print (modem.chat (b'AT+CSCA?\r')) # SMS center number
    #print (modem.chat (b'AT+CSQ\r'))    # signal strength

    #to check, that modem supports both PDU and text mode:
    #assert modem.chat (b'AT+CMGF=?\r') == [b'+CMGF: (0,1)', b'OK']

    # display some network mode configuration:
    #print (modem.chat (b'AT^SYSCFG?\r'))

    # current network info
    #print (modem.chat (b'AT+COPS?\r'))

    def isOK (self):
        """Checks that modem is properly connected to PC,
        receiving commands and capable of respondig.
        Returns bool."""
        return self.chat (b'AT\r') == [b'OK']

    def initCellular (self):
        """Initialise modem on cellular network.
        Useful after the end of data connection."""
        attempts = 0
        maxAttempts = 300
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
        maxAttempts = 300
        li = [self.isOK, self.setModeText, self.setEncodingIRA,   \
            self.setStorageSM, self.deleteSMS]
        for func in li:
            while not func():
                sleep (0.1)
                attempts += 1
                if attempts == maxAttempts: return False
        attempts = 200  # 100 attempts remaining:
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
        print (response)
        if response[0] != b'> ': return False   # prompt for sms input
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

modem = Modem()
modem.getPort()
print (modem.readSMS())
#print (modem.initCellular())
#print (modem.initSMS())
#print (modem.isOK())
#print (modem.isRegistered())
#print (modem.setModeText())
#print (modem.isModeText())
#print (modem.chat (b'AT+CSCS?\r'))
#print (modem.chat (b'AT+CPMS?\r'))
#print (modem.chat (b'AT+CSCS="IRA"\r'))
#print (modem.chat (b'AT+CPMS="SM"\r'))
#print (modem.chat (b'AT+CSCS?\r'))
#print (modem.chat (b'AT+CPMS?\r'))
#print (modem.chat (b'AT+COPS?\r'))
#print (modem.chat (b'AT+CSMP?\r'))  # sms settings
#print (modem.chat (b'AT+CSMP=1,,0,0\r'))
#print (modem.chat (b'AT+CSMP?\r'))
#print (modem.chat (b'AT+CSMS?\r'))  # sms settings
#print (modem.radioON())

#print (modem.isOK())
#print (modem.radioOFF())
#print (modem.isPINok())
#print (modem.setModeText())
#print ('send SMS:')
#print (modem.sendSMS(950, 'spotreba'))

#print (modem.readSMS())
#print (modem.deleteSMS())
#print (modem.chat (b'AT+COPS?\r'))
#print (modem.chat (b'AT+CREG?\r'))
#print (modem.chat (b'AT+CGACT?\r'))    # attachement status
#print (modem.chat (b'AT+CGDCONT?\r'))   # access points
#print (modem.chat (b'AT+CGATT=1\r'))
#print (modem.chat (b'AT+CGATT=1\r'))

#print (modem.chat (b'AT+CGATT?\r'))
#print (modem.chat (b'AT+CSCS?\r'))  # sms settings
#print (modem.chat (b'AT+CSMP?\r'))  # sms settings
#print (modem.chat (b'AT+CSMS?\r'))  # sms settings
#print (modem.chat (b'AT+CPMS?\r'))  # sms storage

# THE HOLY HANDGRANADE:
#print (modem.chat (b'AT+CSCS="IRA"\r'))
#print (modem.chat (b'AT+CPMS="SM"\r'))  # sms storage

#print (modem.chat (b'AT+CSCS?\r'))
#print (modem.chat (b'AT+CSQ\r')) # signal quality
#print (modem.chat (b'AT+CFUN=?\r'))  # all modes
#print (modem.chat (b'AT+CFUN?\r'))   # current mode
#print (modem.chat (b'AT+CSMP?\r'))   # sms settings
#print (modem.chat (b'AT+CPMS?\r'))   # sms storage
#print (modem.cntSMS())
#print (modem.readSMS())

#print (modem.readSMS())
#print (modem.sendSMS(950, 'spotreba'))
#print (modem.readSMS())
#print (modem.deleteSMS())

#print (modem.chat (b'AT+CSMP=1,,0,0\r'))  # sms settings
#print (modem.chat (b'AT+CSCS?\r'))  # sms settings
#print (modem.chat (b'AT+CSCS="GSM"\r'))  # sms settings
#print (modem.chat (b'AT+CSCS?\r'))  # sms settings

##print (modem.chat (b'AT+CGDCONT=?'))
#print (modem.chat (b'AT^SYSCFG?\r'))   #???
#print (modem.chat (b'AT+CREG=1\r'))    # registration message enable
#print (modem.chat (b'AT+CREG?\r'))
#print (modem.chat (b'AT+CFUN=1\r'))

#print (modem.chat (b'AT+CSMP?\r'))   # sms settings
#print (modem.chat (b'AT+COPS?\r'))   # current operator name
#print (modem.chat (b'AT+COPS=?\r'))  # all  available networks

#print (modem.chat (b'AT+CSQ\r')) # signal quality
#print (modem.chat (b'AT+CSMP?\r'))   # sms settings
#print (modem.chat (b'AT+COPS?\r'))   # current operator name

#print (modem.chat (b'AT+CREG=2\r'))  #first enable creg
#print (modem.chat (b'AT+CIMI=?\r'))  # is connected to network?
#print (modem.chat (b'AT+COPS=0,0,0\r'))
#print (modem.chat (b'AT+COPS=?\r'))  #list available networks

#print (modem.chat (b'AT+CGACT?\r'))   # attachement status
#print (modem.chat (b'AT+CGACT=?\r'))  # list operators
#print (modem.chat (b'AT+CGATT=0\r'))  # dettach
#print (modem.chat (b'AT+CGATT=1\r'))  # attach

