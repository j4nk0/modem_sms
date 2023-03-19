# Send SMS from usb modem

See sms.py for list of generic modem commands.

Standalone kontrola_kreditu.py program creates UI window with two buttons:
+ SPOTREBA
+ GIGA

Each button sends corresponding text to number 950. Then program awaits response SMS and reads it out.
When the window is closed, the modem is reconfigured to provide internet access.

The button SPOTREBA is used to read out data usage.

The button GIGA is used to purchase 1 GB data package from prepaid card.

This is all operator specific.
