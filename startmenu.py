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
import thread, signal, sys, os, gc
import netifaces as ni
import RPi.GPIO as GPIO

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
ledStatus = 1

CursorPosition = 0
CurrentPage = 0
CurrentMenuItem = 0
ssaverTime = 0
ssaverTimeout = 600

# default button states to True (not pressed)
buttons = {'btnUp': True, 'btnDown': True, 'btnBack': True, 'btnSelect': True}

# create lcd object
lcd = Adafruit_CharLCD()

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
        
	GPIO.output(ledStatus, False)
        sleep(MICRO_DELAY)
        
	sys.exit(0)

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
def printMenu(menu):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	
	MenuItems = len(menu)
	
	CursorPosition = 0
	CurrentPage = 0
	CurrentMenuItem = 0
	
	lcd.clear()
	
	lcdPrint(0, CursorPosition, PROMPT)
	lcdPrint(2, 0, menu[CurrentMenuItem])
	
	if ((CurrentMenuItem + 1) < MenuItems):
		lcdPrint(2, 1, menu[CurrentMenuItem + 1])

# determine how many pages any given menu is
def PageCount(MenuItems):
	pages = 1
	
	if (MenuItems > 2):
		pages = (MenuItems / 2)
		
		if (MenuItems % 2 != 0):
			pages += 1
	
	return pages

# move PROMPT to the next menu item or page
def CursorNext(menu):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	global ssaverTime
	
	ssaverTime = 0
	
	MenuItems = len(menu)
	
	if (CursorPosition == 0):
		if ((CurrentMenuItem + 1) < MenuItems):
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
			
			lcdPrint(0, CursorPosition, PROMPT)
			lcdPrint(2, 0, menu[CurrentMenuItem])
			
			if ((CurrentMenuItem + 1) < MenuItems):
				lcdPrint(2, 1, menu[CurrentMenuItem + 1])
				
	sleep(SHORT_DELAY)

# move PROMPT to rpevious menu item or page
def CursorPrevious(menu):
	global CursorPosition
	global CurrentPage
	global CurrentMenuItem
	global ssaverTime
	
	ssaverTime = 0
	
	MenuItems = len(menu)
	
	if (CursorPosition == 1):
		if (CurrentMenuItem > 0):
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
			
			lcdPrint(2, 0, menu[CurrentMenuItem - 1])
			lcdPrint(2, 1, menu[CurrentMenuItem])
			
			lcdPrint(0, 1, PROMPT)
	
	sleep(SHORT_DELAY)

# display information and cycle through pages
def infoMenu():
	global ssaverTime
	
	ssaverTime = 0
	
	menuPosition = 0
	buttonClick = 0
	menuItems = 5
	
	line0 = ''
	line1 = ''
	
	networkinfo = ni.ifaddresses('eth0')
	
	while 1:
		if (buttonClick == 1):
			buttonClick = 0
	
		if (menuPosition == 0):
			line0 = 'IP Address'
			line1 = networkinfo[2][0]['addr']
			
		if (menuPosition == 1):
			gateway = runShell("route -n | grep 'UG[ \t]' | awk '{print $2}'")
			
			line0 = 'Gateway'
			line1 = gateway
			
		if (menuPosition == 2):
			dns_server = runShell("grep nameserver /etc/resolv.conf|head -n1|awk '{print $2}'")
			line0 = 'DNS'
			line1 = dns_server
			
		if (menuPosition == 3):
			line0 = 'Subnet Mask'
			line1 = networkinfo[2][0]['netmask']
			
		if (menuPosition == 4):
			total_mem = runShell("grep MemTotal /proc/meminfo|awk '{print $2}'")
			free_mem = runShell("grep MemFree /proc/meminfo|awk '{print $2}'")
			
			line0 = 'Free Memory'
			line1 = free_mem + '/' + total_mem + 'KB' 
		
		lcdPrint(0, 0, line0, True)
		lcdPrint(0, 1, line1)
		
		while (buttonClick == 0):
			readButtons()
			
			if (buttons['btnDown'] == False):
				ssaverTime = 0
				
				if (menuPosition < (menuItems - 1)):
					menuPosition += 1
					buttonClick = 1
					
			if (buttons['btnUp'] == False):
				ssaverTime = 0
				
				if (menuPosition > 0):
					menuPosition -= 1
					buttonClick = 1
			
			if (buttons['btnBack'] == False):
				ssaverTime = 0
				
				return
				
			# increment idle delay
			ssaverTime += MICRO_DELAY
		
			# if weve been idle for 10 minutes, start screen saver
			if (ssaverTime > ssaverTimeout):
				ssaverTime = 0
				screenSaver()
				
			sleep(MICRO_DELAY)

# display system menu
def systemMenu():
	global ssaverTime
	
	ssaverTime = 0
	SystemMenu = ['Restart', 'Reboot', 'Shutdown']
	
	printMenu(SystemMenu)
	
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
				lcdPrint(0, 0, 'Restarting...')
				
				sys.exit(0)
			
			if (CurrentMenuItem == 1):
				lcd.clear()
				lcdPrint(0, 0, 'Rebooting...')
				
				nothing = runShell("reboot")
			
			if (CurrentMenuItem == 2):
				lcd.clear()
				lcdPrint(0, 0, 'Shutting down...')
				
				nothing = runShell("shutdown -h now")
		
		# increment idle delay
		ssaverTime += MICRO_DELAY
		
		# if weve been idle for 10 minutes, start screen saver
		if (ssaverTime > ssaverTimeout):
			ssaverTime = 0
			screenSaver()
			printMenu(SystemMenu)
			
		sleep(MICRO_DELAY)

# display main menu and respond to a selection
def mainMenu():
	global ssaverTime
	
	ledBlink(ledStatus, 5)
	
	ssaverTime = 0
	MainMenu = ['Information', 'Diagnostics', 'Host Discovery', 'Port Scanner', 'System', 'About']
	
	printMenu(MainMenu)

	while 1:
		readButtons()

		# up button
		if ( buttons['btnUp'] == False ):
			CursorPrevious(MainMenu)
	
		# down button
		if ( buttons['btnDown'] == False ):
			CursorNext(MainMenu)

		# back button (unused in main menu)
		# if ( buttons['btnBack'] == False ):
		#	lcd.clear()
		#	lcd.message('Button 3')
		#	sleep(LONG_DELAY)
		#	printMenu(MainMenu)
	
		# select button
		if ( buttons['btnSelect'] == False ):
			lcd.clear()
			
			if (CurrentMenuItem == 0):
				infoMenu()
			
				sleep(SHORT_DELAY)
				printMenu(MainMenu)
				
			elif (CurrentMenuItem == 4):
				systemMenu()
				
				sleep(SHORT_DELAY)
				printMenu(MainMenu)
				
			else:
				printMenu(MainMenu)

		# increment idle delay
		ssaverTime += MICRO_DELAY
		
		# if weve been idle for 10 minutes, start screen saver
		if (ssaverTime > ssaverTimeout):
			ssaverTime = 0
			screenSaver()
			printMenu(MainMenu)
		
		sleep(MICRO_DELAY)

# setup inputs and signals
def setup():
	signal.signal(signal.SIGINT, signal_handler)
	
	#GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(btnUp, GPIO.IN)
	GPIO.setup(btnDown, GPIO.IN)
	GPIO.setup(btnBack, GPIO.IN)
	GPIO.setup(btnSelect, GPIO.IN)
	GPIO.setup(ledBacklight, GPIO.OUT)
	GPIO.setup(ledStatus, GPIO.OUT)
	
	GPIO.output(ledBacklight, False)
	GPIO.output(ledStatus, GPIO.LOW)
	
	lcd.begin(16,2)

# get this party started
setup()
mainMenu()
