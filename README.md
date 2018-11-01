# mySVU Grade Notifier
A web scraper that periodically scraped mySVU for your grades and notified you if there were changes.

This was created as there was no way to be notified if a grade was updated on the learning management system SVU was using during my early years there.

It accomplishes by following this workflow:
1. Creates a virtual browser and logs into mySVU for you.
2. Navigates to all of your classes and their grades, saving them locally.
3. Repeats steps 1 and 2 every fifteen minutes and looks for changes from last locally saved grades.
4. When a change is found, sends an email to the given email (can be done for freethrough sms with [sms emailing](https://20somethingfinance.com/how-to-send-text-messages-sms-via-email-for-free/), but could easily integrate Twilio if desired).

This process goes on until the program is stopped. 

Current uploaded version is tested to work on Ubuntu, though with minimal changes could work on any system running Python 3.6 or later.
