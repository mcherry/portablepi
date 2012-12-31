#!/usr/bin/python
#
# Raspberry Pi menu system
# Written by Mike Cherry <mcherry@inditech.org>
#
# Designed to work with a raspberry pi that has a 16x2 character lcd and 4 push buttons
# connected to various GPIO pins

from Adafruit_CharLCD import Adafruit_CharLCD
from subprocess import * 
from time import sleep, strftime
from datetime import datetime
import thread, signal, sys, os, gc, statvfs
import netifaces as ni
import nmap
import RPi.GPIO as GPIO

GPIO.setwarnings(False)

LONG_DELAY = 1.75
MEDIUM_DELAY = .5
SHORT_DELAY = .25
MICRO_DELAY = .10

PROMPT = '>'

# GPIO pins for different functions
btnUp = 14
btnDown = 15
btnBack = 8
btnSelect = 18
ledBacklight = 7
ledStatus1 = 1
lesStatus2 = 11

CursorPosition = 0
CurrentPage = 0
CurrentMenuItem = 0
ssaverTime = 0
ssaverTimeout = 600

# default button states to True (not pressed)
buttons = {'btnUp': True, 'btnDown': True, 'btnBack': True, 'btnSelect': True}

# create lcd object
lcd = Adafruit_CharLCD()

# convert an IP address string into an array of octets
def IPToArray(ip):
	newip = ip.split('.')
	
	return [int(newip[0]), int(newip[1]), int(newip[2]), int(newip[3])]
	
# convert an array of octets into a string ip address
def ArrayToIP(iparray):
	return str(iparray[0]) + '.' + str(iparray[1]) + '.' + str(iparray[2]) + '.' + str(iparray[3])

# start a background thread to blink LED 'delay' number of times
def ledBlink(ledpin, number, delay=SHORT_DELAY):
	thread.start_new_thread(ledBlinkThread, (ledpin, number, delay))

# blink led
def ledBlinkThread(ledpin, number, delay=SHORT_DELAY):
	GPIO.output(ledpin, GPIO.LOW)
	
	for num in range(0,number):
		GPIO.output(ledpin, GPIO.HIGH)
		
		sleep(delay)
		GPIO.output(ledpin, GPIO.LOW)
		sleep(delay)
		
	GPIO.output(ledpin, GPIO.LOW)

# handle SIGINT
def signal_handler(signal, frame):
	lcd.clear()
        lcd.noDisplay()
        
	GPIO.output(ledBacklight, True)
        sleep(MICRO_DELAY)
        
	GPIO.output(ledStatus1, False)
        sleep(MICRO_DELAY)
        
        GPIO.output(lesStatus2, GPIO.LOW)
        sleep(MICRO_DELAY)
        
	sys.exit(0)
	
def free_bytes(path): 
	stats = os.statvfs(path) 
	return stats[statvfs.F_BSIZE] * stats[statvfs.F_BFREE] 

def avail_bytes(path): 
	stats = os.statvfs(path) 
	return stats[statvfs.F_BSIZE] * stats[statvfs.F_BAVAIL]

# present a method to input an IP address
# if isNetmask == False then you cant select 255 for any given octet
def ipInput(ip, label, isNetmask=False):
	octetPos = 0
	netMaskMax = 254
	octetMin = 0
	
	iparray = IPToArray(ip)
	
	if (isNetmask == True):
		netMaskMax = 255
		
	lcdPrint(0, 0, label, True)
	lcdPrint(0, 1, str(iparray[0]).zfill(3) + '.' +  str(iparray[1]).zfill(3) + '.' +  str(iparray[2]).zfill(3) + '.' +  str(iparray[3]).zfill(3))
	
	lcd.setCursor(2, 1)
	lcd.cursor()
	lcd.blink()
	
	sleep(MICRO_DELAY)
	
	while 1:
		readButtons()
		
		if (buttons['btnUp'] == False):
			if (iparray[octetPos] < netMaskMax):
				iparray[octetPos] += 1
			else:
				if (octetPos == 0):
					iparray[octetPos] = 1
				else:
					iparray[octetPos] = 0
			
			lcdPrint((octetPos+2*(octetPos+1)+octetPos)-2, 1, str(iparray[octetPos]).zfill(3))
			
			sleep(MICRO_DELAY)
			
		if (buttons['btnDown'] == False):
			if (octetPos == 0):
				octetMin = 1
			else:
				octetMin = 0
				
			if (iparray[octetPos] > octetMin):
				iparray[octetPos] -= 1
			else:
				iparray[octetPos] = netMaskMax
			
			lcdPrint((octetPos+2*(octetPos+1)+octetPos)-2, 1, str(iparray[octetPos]).zfill(3))
			
			sleep(MICRO_DELAY)
			
		if (buttons['btnSelect'] == False):
			if (octetPos == 3):
				lcd.noBlink()
				lcd.noCursor()
				
				return ArrayToIP(iparray)
				
			if (octetPos < 4):
				if (octetPos != 3):
					octetPos += 1
					
				lcd.setCursor(octetPos+2*(octetPos+1)+octetPos, 1)
				sleep(SHORT_DELAY)
				
		if (buttons['btnBack'] == False):
			if (octetPos == 0):
				iparray[0] = 0
				
				lcd.noBlink()
				lcd.noCursor()
				
				return 0
			
			octetPos -= 1
			
			lcd.setCursor(octetPos+2*(octetPos+1)+octetPos, 1)
			
			sleep(SHORT_DELAY)

def portScanner():
	addr = 0
	portCount = 0
	
	ip = ipInput("192.168.187.84", "IP Address")
	if (ip == 0):
		return
	else:
		print IPToArray(ip)

# wrapper to move lcd PROMPT and print a string
def lcdPrint(column, row, message, clear=False):
	if ( clear == True ):
		lcd.clear()
		
	lcd.setCursor(column, row)
	lcd.message(message)

# run a shell command and return output
def runShell(cmd):
        p = Popen(cmd, shell=True, stdout=PIPE)
        output = p.communicate()[0]
        
        return output.rstrip()
        
def checkScreenSaver(menuName):
	global ssaverTime
	
	# increment idle delay
	ssaverTime += MICRO_DELAY
		
	# if weve been idle for 10 minutes, start screen saver
	if (ssaverTime > ssaverTimeout):
		ssaverTime = 0
		screenSaver()
		printMenu(menuName)

# clear lcd and turn off ledBacklight then wait for input to "wake up"
def screenSaver():
	global ssaverTime
	
	lcd.clear()
	lcd.noDisplay()
	GPIO.output(ledBacklight, True)
	
	collected = gc.collect()
	
	while 1:
		readButtons()
		
		if ((buttons['btnUp'] == False) or (buttons['btnDown'] == False) or (buttons['btnBack'] == False) or (buttons['btnSelect'] == False)):
			lcd.display()
			GPIO.output(ledBacklight, False)
			
			ssaverTime = 0
			return
		
		sleep(MICRO_DELAY)

# read button states. False is pressed, True is not pressed
def readButtons():
	buttons['btnUp'] = GPIO.input(btnUp)
	buttons['btnDown'] = GPIO.input(btnDown)
	buttons['btnBack'] = GPIO.input(btnBack)
	buttons['btnSelect'] = GPIO.input(btnSelect)

# print an array of menu items
def printMenu(menu, noPrompt=False):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	
	MenuItems = len(menu)
	
	CursorPosition = 0
	CurrentPage = 0
	CurrentMenuItem = 0
	
	itemOffset = 2
	if (noPrompt == True):
		itemOffset = 0
	
	lcd.clear()
	
	if (noPrompt == False):
		lcdPrint(0, CursorPosition, PROMPT)
		
	lcdPrint(itemOffset, 0, menu[CurrentMenuItem])
	
	if ((CurrentMenuItem + 1) < MenuItems):
		lcdPrint(itemOffset, 1, menu[CurrentMenuItem + 1])
		
	sleep(MICRO_DELAY)

# determine how many pages any given menu is
def PageCount(MenuItems):
	pages = 1
	
	if (MenuItems > 2):
		pages = (MenuItems / 2)
		
		if (MenuItems % 2 != 0):
			pages += 1
	
	return pages

# move PROMPT to the next menu item or page
def CursorNext(menu, noPrompt=False, noDelay=False):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	global ssaverTime
	
	ssaverTime = 0
	
	itemOffset = 2
	if (noPrompt == True):
		itemOffset = 0
	
	MenuItems = len(menu)
	
	if (CursorPosition == 0):
		if ((CurrentMenuItem + 1) < MenuItems):
			if (noPrompt == False):
				lcdPrint(0, 0, " ")
				lcdPrint(0, 1, PROMPT)
			
			CursorPosition += 1
			CurrentMenuItem += 1
	else:
		if (CurrentPage < (PageCount(MenuItems) - 1)):
			lcd.clear()
			
			CurrentPage += 1
			CurrentMenuItem += 1
			
			CursorPosition = 0
			
			if (noPrompt == False):
				lcdPrint(0, CursorPosition, PROMPT)
			
			lcdPrint(itemOffset, 0, menu[CurrentMenuItem])
			
			if ((CurrentMenuItem + 1) < MenuItems):
				lcdPrint(itemOffset, 1, menu[CurrentMenuItem + 1])
	
	if (noDelay == False):
		sleep(SHORT_DELAY)

# move PROMPT to rpevious menu item or page
def CursorPrevious(menu, noPrompt=False, noDelay=False):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	global ssaverTime
	
	ssaverTime = 0
	
	itemOffset = 2
	if (noPrompt == True):
		itemOffset = 0
	
	MenuItems = len(menu)
	
	if (CursorPosition == 1):
		if (CurrentMenuItem > 0):
			if (noPrompt == False):
				lcdPrint(0, 1, " ")
				lcdPrint(0, 0, PROMPT)
			
			
			CursorPosition -= 1
			CurrentMenuItem -= 1
	else:
		if (CurrentPage > 0):
			lcd.clear()
			
			CurrentPage -= 1
			CurrentMenuItem -= 1
			
			CursorPosition = 1
			
			lcdPrint(itemOffset, 0, menu[CurrentMenuItem - 1])
			lcdPrint(itemOffset, 1, menu[CurrentMenuItem])
			
			if (noPrompt == False):
				lcdPrint(0, 1, PROMPT)
	
	if (noDelay == False):
		sleep(SHORT_DELAY)

# display information and cycle through pages
def infoMenu():
	global ssaverTime
	
	ssaverTime = 0
	
	gateway = runShell("route -n | grep 'UG[ \t]' | awk '{print $2}'")
	dns_server = runShell("grep nameserver /etc/resolv.conf|head -n1|awk '{print $2}'")
	total_mem = int(runShell("grep MemTotal /proc/meminfo|awk '{print $2}'")) / 1024
	free_mem = int(runShell("grep MemFree /proc/meminfo|awk '{print $2}'")) / 1024
	
	InfoMenu = []
	
	for nic in ni.interfaces():
		if (nic != "lo"):
			item = ni.ifaddresses(nic).get(2, 0)
			
			if (item != 0):
				InfoMenu.append(nic)
				InfoMenu.append(item[0]['addr'])
			
				InfoMenu.append('Subnet Mask')
				InfoMenu.append(item[0]['netmask'])
	
	InfoMenu.append('Gateway')
	InfoMenu.append(gateway)
	
	InfoMenu.append('DNS')
	InfoMenu.append(dns_server)
	
	InfoMenu.append('Free Memory')
	InfoMenu.append(str(free_mem)+'/'+str(total_mem)+' MB')
	
	InfoMenu.append('Free Space on /')
	InfoMenu.append(str(format(avail_bytes('/') / 1024, ',d'))+' MB')
	
	printMenu(InfoMenu, True)
	
	sleep(MICRO_DELAY)
	
	while 1:
		readButtons()

		# up button
		if ( buttons['btnUp'] == False ):
			CursorPrevious(InfoMenu, True, True)
			CursorPrevious(InfoMenu, True)
			
	
		# down button
		if ( buttons['btnDown'] == False ):
			CursorNext(InfoMenu, True, True)
			CursorNext(InfoMenu, True)
		
		# back button (unused in main menu)
		if ( buttons['btnBack'] == False ):
			return
			
		checkScreenSaver(InfoMenu)
		sleep(MICRO_DELAY)
			
def networkMenu():
	global ssaverTime
	global networkAnimation
	
	ssaverTime = 0
	NetworkMenu = ['Start Wired', 'Stop Wired', 'Start Wireless', 'Stop Wireless']
	
	printMenu(NetworkMenu)
	sleep(MICRO_DELAY)
	
	while 1:
		readButtons()

		# up button
		if ( buttons['btnUp'] == False ):
			CursorPrevious(NetworkMenu)
	
		# down button
		if ( buttons['btnDown'] == False ):
			CursorNext(NetworkMenu)
		
		# back button (unused in main menu)
		if ( buttons['btnBack'] == False ):
			return
			
		# select button
		if ( buttons['btnSelect'] == False ):
			lcd.clear()
			
			if (CurrentMenuItem == 0):
				lcdPrint(0, 0, 'Starting')
				lcdPrint(0, 1, 'wired network')
				
				nothing = runShell('ifconfig eth0 up')
				nothing = runShell('dhclient eth0')
				
			if (CurrentMenuItem == 1):
				lcdPrint(0, 0, 'Stopping')
				lcdPrint(0, 1, 'wired network')
				
				nothing = runShell('ifconfig eth0 down')
				nothing = runShell('ifconfig eth0 0.0.0.0')
			
			if (CurrentMenuItem == 2):
				lcdPrint(0, 0, 'Starting')
				lcdPrint(0, 1, 'wireless network')
				
				nothing = runShell('modprobe r8712u')
				nothing = runShell('/usr/local/bin/startwifi.sh')
			
			if (CurrentMenuItem == 3):
				lcdPrint(0, 0, 'Stopping')
				lcdPrint(0, 1, 'wireless network')
				
				nothing = runShell('ifconfig wlan0 down')
				nothing = runShell('ifconfig wlan0 0.0.0.0')
				nothing = runShell('rmmod r8712u')
			
			sleep(SHORT_DELAY)
			return
				
		checkScreenSaver(NetworkMenu)
			
		sleep(MICRO_DELAY)
	

# display system menu
def systemMenu():
	global ssaverTime
	
	ssaverTime = 0
	SystemMenu = ['Reload', 'Reboot', 'Shutdown']
	
	printMenu(SystemMenu)
	sleep(MICRO_DELAY)
	
	while 1:
		readButtons()

		# up button
		if ( buttons['btnUp'] == False ):
			CursorPrevious(SystemMenu)
	
		# down button
		if ( buttons['btnDown'] == False ):
			CursorNext(SystemMenu)
		
		# back button (unused in main menu)
		if ( buttons['btnBack'] == False ):
			return
			
		# select button
		if ( buttons['btnSelect'] == False ):
			lcd.clear()
			
			if (CurrentMenuItem == 0):
				lcd.clear()
				lcdPrint(0, 0, 'Reloading')
				lcdPrint(0, 1, 'menu...')
				
				sys.exit(0)
			
			if (CurrentMenuItem == 1):
				lcd.clear()
				lcdPrint(0, 0, 'Rebooting...')
				
				nothing = runShell("reboot")
			
			if (CurrentMenuItem == 2):
				lcd.clear()
				lcdPrint(0, 0, 'Shutting down...')
				
				nothing = runShell("shutdown -h now")
		
		checkScreenSaver(SystemMenu)
			
		sleep(MICRO_DELAY)
		
# display main menu and respond to a selection
def mainMenu():
	global ssaverTime
	
	ledBlink(ledStatus1, 5)
	
	ssaverTime = 0
	MainMenu = ['Information', 'Diagnostics', 'Tools', 'Network', 'System', 'About']
	
	printMenu(MainMenu)
	sleep(MICRO_DELAY)

	while 1:
		readButtons()

		# up button
		if ( buttons['btnUp'] == False ):
			CursorPrevious(MainMenu)
	
		# down button
		if ( buttons['btnDown'] == False ):
			CursorNext(MainMenu)

		# select button
		if ( buttons['btnSelect'] == False ):
			lcd.clear()
			
			if (CurrentMenuItem == 0):
				infoMenu()
			
				sleep(SHORT_DELAY)
				printMenu(MainMenu)
				
			elif (CurrentMenuItem == 3):
				networkMenu()
				
				sleep(MICRO_DELAY)
				printMenu(MainMenu)
				
			elif (CurrentMenuItem == 4):
				systemMenu()
				
				sleep(SHORT_DELAY)
				printMenu(MainMenu)
				
			else:
				printMenu(MainMenu)

		checkScreenSaver(MainMenu)
		
		sleep(MICRO_DELAY)

# setup inputs and signals
def setup():
	signal.signal(signal.SIGINT, signal_handler)
	
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(btnUp, GPIO.IN)
	GPIO.setup(btnDown, GPIO.IN)
	GPIO.setup(btnBack, GPIO.IN)
	GPIO.setup(btnSelect, GPIO.IN)
	GPIO.setup(ledBacklight, GPIO.OUT)
	GPIO.setup(ledStatus1, GPIO.OUT)
	GPIO.setup(lesStatus2, GPIO.OUT)
	
	GPIO.output(ledBacklight, False)
	GPIO.output(ledStatus1, GPIO.LOW)
	GPIO.output(lesStatus2, GPIO.LOW)
	
	lcd.begin(16,2)

# get this party started
setup()
mainMenu()
