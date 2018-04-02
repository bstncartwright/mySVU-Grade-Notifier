import pickle
import getpass

print("Welcome to mySVU_scraper login!")

try:
    old_data = pickle.load( open("users.p", "rb") )
except:
    old_data = []

id = input("Student ID: ")
password = getpass.getpass("mySVU Password: ")
email = input("Email: ")

old_data.append({'id':id, 'password':password, 'email':email})

pickle.dump(old_data, open("users.p", "wb") )

print("Successfully added. Thanks!")