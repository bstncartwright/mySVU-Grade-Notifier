# ubuntu headless, sms enabled

# mySVU grade notifier
# Author: Boston Cartwright

from bs4 import BeautifulSoup
import urllib.request
import time
from datetime import datetime
import http.cookiejar
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from apscheduler.schedulers.blocking import BlockingScheduler
import smtplib
from pyvirtualdisplay import Display
import signal
import atexit
import os
import pickle

# due to being ran on a headless ubuntu server, need display for Selenium to use for browsing
display = Display(visible=0, size=(800, 600))
display.start()

# scheduler to manage 15 minute intervals
scheduler = BlockingScheduler()

BASE_URL = "https://my.svu.edu"

# if using login.py getUsers() methods, ignore this call, just use the call for an empty array
# if not using login.py with pickle to get users, set this array with dictionaries inside to manager users to have grades checked
# users = [
#    {'id':'012345', 'password':'password123', 'email':'this@example.com'}
#    ]
# create empty users array
users = []

# boolean to use SMS lengths for sending updates
sms = True

email_username = ""
email_password = "" 

old_data = []

# starts the loop, asking for email and password emails will be sent from (must be gmail)
def start_scrape():
    email_username = input("Gmail: ")
    email_password = input("Password: ")
    scheduler.start()

# main loop, occuring every hour
@scheduler.scheduled_job('interval', minutes=60, id="scrape_loop")
def mysvu_scrape_loop():
    print(str(datetime.now()) + " -- Starting Loop")

    try:
        users = get_users()
        for user in users:
            mysvu_scrape(user['id'], user['password'])
    except:
        print("ERROR GETTING USERS --  TERMINATING")
        quit()
    
    print(str(datetime.now()) + " -- loop finished")

# loads users from file users.p, those being inserted by running login.py
def get_users():
    return pickle.load(open("users.p", "rb"))

# main scrapping method
def mysvu_scrape(id, pas):
    print(str(datetime.now()) + " -- Getting Grades for id " + id + ".")

    # starts browser
    browser = webdriver.Firefox()
    browser.get("https://my.svu.edu/ics/")

    # wait for webpage to load
    time.sleep(3)

    # enter credentials
    username = browser.find_element_by_id("userName")
    password = browser.find_element_by_id("password")
    username.send_keys(id)
    password.send_keys(pas)

    # wait to ensure credentials are entered
    time.sleep(1)

    # login
    loginButton = browser.find_element_by_id("btnLogin")
    loginButton.click()

    # parse using BeautifulSoup and lxml
    soup = BeautifulSoup(browser.page_source, 'lxml')

    # fetch class list (appears as list of URL's of course sites)
    classes = get_classes(soup)

    courses = []

    if classes != 0:
        print(str(datetime.now()) + " -- Recieved Course List -- getting grades...")
        for i in classes:
            # fetch grades for individual class, add to course list to then be checked
            grade = get_grades(id, i, browser)
            courses.append(grade)
            time.sleep(1) # being nice to site, not overrunning

    # clear browser and cookies
    browser.quit()

    # get old grades (to be compared to)
    oldData = search_dictionaries('id', id, old_data)

    if not oldData:
        old_data.append({'id':id,'data':courses})
    else:
        # compare grades from old grades
        compare_grades(id, oldData[0]['data'], courses)
        time.sleep(1)
        oldData[0]['data'] = courses

    print(str(datetime.now()) + " -- finished with " + id)
    #print(courses)

# comparing grades method, takes the student id, the old grades, and the new grades
def compare_grades(id, oldData, data):
    print(str(datetime.now()) + " -- Comparing grades...")

    # super complicated part; good luck understanding!
    # view line 231 (part of getGrades() method) for format of grades object/array
    
    for course_index, course in enumerate(data): # gets course
        course_name = course['course_name']
        course_final = course['final']
        course_categories = course['categories']

        for category_index, category in enumerate(course_categories): # gets array of categories
            category_name = category['category_name']
            category_grade = category['category_grade']
            category_assignments = category['assignments']

            for assignments_index, assignment in enumerate(category_assignments): # gets array of assignments
                assignment_name = assignment['assignment_name']
                assignment_grade = assignment['assignment_grade']

                # attempts to get old assignment's grade to compare new grade to
                try:
                    old_assignment_name = oldData[course_index]['categories'][category_index]['assignments'][assignments_index]['assignment_name']
                    old_assignment_grade = oldData[course_index]['categories'][category_index]['assignments'][assignments_index]['assignment_grade']

                    # check for same assignment name
                    if assignment_name == old_assignment_name:
                        # same assignment -- good! let's check the grades
                        if assignment_grade != old_assignment_grade:
                            # different grade, update!
                            send_grade_update(id, course_name, course_final, category_name, category_grade, assignment_name, assignment_grade)

                    # different assignment name, can happen because the grades were reformatted, or an update on the name, anything
                    else:
                        print("Must be a new grade! (or reformat of everything)")
                        send_grade_update(id, course_name,  course_final, category_name, category_grade, assignment_name, assignment_grade)

                # entirely new assignment in system, probably a new grade
                except (IndexError, ValueError):
                    print("Index Error, probably an update!")
                    send_grade_update(id, course_name, course_final, category_name, category_grade, assignment_name, assignment_grade)

# sends grade update
def send_grade_update(id, course_name, course_final, category_name, category_grade, assignment_name, assignment_grade):
    print("AN UPDATE!")
    # open smtp server with gmail
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    # login
    server.login(email_username, email_password)
    # get email to send to
    email = search_dictionaries('id', id, users)[0]['email']

    # formulate message
    stri = "Updated mySVU Grade! %s now has a final grade of %s. The updated assignment was %s, with a new grade of %s, in the category of %s." %(course_name, course_final, assignment_name, assignment_grade, category_name)
    
    # check if sending to SMS (which has limit of 160 characters)
    if sms:
        if len(stri) > 160:
            # split to two emails for SMS
            str1 = stri[0:160]
            str2 = stri[160:]
            server.sendmail('', email, str1)
            server.sendmail('', email, str2)
        else:
            server.sendmail('', email, stri)
    else:
        # sends email
        server.sendmail('', email, stri)

    # closes server
    server.close()


# gets list of classes from BeautifulSoup object
def get_classes(soup):
    courses = soup.find("dl", {"id":"myCourses"})
    if courses is None:
        # failed login
        print("FAILED LOGIN -- TERMINATING")
        return 0

    # adds the base url to the url for the gradebook
    course_list = [BASE_URL + li.a["href"] for li in courses.findAll("li")]
    return course_list

# gets grades from browser
def get_grades(id, course, browser):
    # loads course gradebook page
    browser.get(course + "Gradebook.jnz?portlet=Gradebook")
    # create soup
    soup = BeautifulSoup(browser.page_source, 'lxml')
    
    # get course name
    course_name_html = soup.find("div", {"id":"pg0_V_GradesheetIntro"})
    course_name = str(course_name_html).replace('<div ','').replace('id="pg0_V_GradesheetIntro"','').replace('class="introText"','').replace('><strong>Your grade sheet</strong> for ','').replace('</div>','').strip()
    
    # get current course grade
    final = soup.find("div", {"id":"pg0_V_FinalGradeText"})
    final_grade = str(final).replace('<div class="finalGradeValue" id="pg0_V_FinalGradeText"><span class="gradeLetter">','').replace('</span>','').replace('</div>','')
    
    # create dictionary for grades
    # course grades dictionary/array format (example class, CSC 101, with one category and two assignments):
    # dict 
    # {
    #   'course_name':'CSC 101',
    #   'final':'99/100 (99%)', 
    #   'categoires': 
    #   [
    #         dict
    #         {
    #             'category_name':'Quizes'
    #             'category_grade':'19/20 (95%)'
    #             'assignments':
    #              [
    #                 dict 
    #                 {
    #                     `assignment_name':'Variables Quiz'
    #                     `assignemnt_grade`:'10/10 (100%)`
    #                 }
    #                 dict 
    #                 {
    #                     `assignment_name':'Data Types Quiz'
    #                     `assignemnt_grade`:'9/10 (90%)`
    #                 }
    #               ]
    #         }
    #   ]
    # }
    data = {"course_name":course_name, "final":final_grade, 'categories':[]}

    categories = soup.findAll("table", {"class":"gradeList"})
    for category in categories:
        # get category name
        category_name = category.find("div", {"class":"groupName"})
        # special case for when class doesn't have any categories
        if category_name is not None:
            category_name = category_name.string

        # get category grade
        category_grade = category.find("div", {"class":"groupGrade"})
        # case for if there is no grade
        if category_grade is None:
            category_grade = category.find("div", {"class":"noGrade"})

        # converts grade into a string
        if category_grade is not None:
            category_grade = category_grade.string

        # gets categories
        table = category.find("table", {"class":"gradeItemGrid tabularData"})
        tbody = table.find("tbody")
        category_data = {"category_name":category_name, "category_grade":category_grade, 'assignments':[]}
        category_grades = category_data['assignments']
        # gets assignments
        for tr in tbody.findAll("tr"):
            assignment = tr.find("td", {"class":"gradeNameColumn"}).a.string
            grade = tr.find("td", {"class":"gradeColumn"}).span.string
            category_grades.append({"assignment_name":assignment, "assignment_grade":grade})

        data['categories'].append(category_data)
    
    return data

# search_dictionaries function for searching a list of dictionaries for a specified value
def search_dictionaries(key, value, list_of_dictionaries):
    return [element for element in list_of_dictionaries if element[key] == value]


# special thanks to StackOverflow for this
# enables a way to ensure the project is still running, with a pid to lookup on system
PID_FILE_PATH = "mysvu_scrape.pid"
stop = False

def create_pid_file():
    # this creates a file called program.pid
    with open(PID_FILE_PATH, "w") as fhandler:
        # and stores the PID in it
        fhandler.write(str(os.getpid()))

def sigint_handler(signum, frame):
    print("Cleanly exiting")
    global stop

    # this will break the main loop
    stop = True

def exit_handler():
    # delete PID file
    os.unlink(PID_FILE_PATH)

def main():
    create_pid_file()

    # this makes exit_handler to be called automatically when the program exists
    atexit.register(exit_handler)

    # this makes sigint_handler to be called when a signal SIGTERM 
    # is sent to the process, e.g with command: kill -SIGTERM $PID
    signal.signal(signal.SIGTERM, sigint_handler)

    start_scrape()

    while not stop:
        # main loop
        pass

if __name__ == "__main__":
    main()