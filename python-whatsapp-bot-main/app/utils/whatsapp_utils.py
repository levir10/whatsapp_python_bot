import logging
from flask import current_app, jsonify
import json
import requests
import re
import pandas as pd
import random
from datetime import datetime, timedelta
import threading


# Constants
EXCEL_FILE_PATH = '/Users/orlevi/Desktop/OrLevisProjects/whatsapp_python_bot/python-whatsapp-bot-main/python-whatsapp-bot-main/data/schedule_test.xlsx'
day_map = {
    'ראשון': 'Sunday',
    'שני': 'Monday',
    'שלישי': 'Tuesday',
    'רביעי': 'Wednesday',
    'חמישי': 'Thursday',
    'שישי': 'Friday'
}

#choices for the first list message of the user - what do you need in general?
choices = [
    {'id': 'set_reminder', 'title': 'יצירת תזכורת'},  # 
    {'id': 'check_schedule', 'title': 'בדיקת לו״ז'},  # 
    {'id': 'get_contact', 'title': 'מספרי קבלנים'},  # 
    {'id': 'get_tidi', 'title': 'פתיחות מלאכה'},  # 
    {'id': 'grade_contractor', 'title': 'דירוג קבלן'}  # 
]

#Choose contractorfor the get_contact list message type
contractor_choices = [
    {'id': 'cement_contractor_num', 'title': 'קבלן בטון'},  #
    {'id': 'plaster_contractor_num', 'title': 'קבלן גבס'},  #
    {'id': 'cranes_contractor_num', 'title': 'מנופאי'},  # 
    {'id': 'driller_contractor_num', 'title': 'קודח'},  # 
    {'id': 'plumbing_contractor_num', 'title': 'אינסטלטור'},  #
    {'id': 'elec_contractor_num', 'title': 'חשמלאי'},  # 
    {'id': 'hvac_contractor_num', 'title': 'קבלן מיזוג'} #  
]

#Choose day of the week for the schedule list message
day_choices = [
    {'id': 'Sunday_day_choice', 'title': 'יום ראשון'},  #
    {'id': 'Monday_day_choice', 'title': 'יום שני'},  #
    {'id': 'Tuesday_day_choice', 'title': 'יום שלישי'},  # 
    {'id': 'Wednesday_day_choice', 'title': 'יום רביעי'},  # 
    {'id': 'Thursday_day_choice', 'title': 'יום חמישי'},  #
    {'id': 'Friday_day_choice', 'title': 'יום שישי'}# 

]
#Choose progect number 
project_choices = [
    {'id': 'Rotchild_project_choice', 'title': 'מלון רוטשילד'},  #
    {'id': 'Agam3_project_choice', 'title': 'אגם 3'},  #
    {'id': 'raul16_project_choice', 'title': 'ראול 16'}, # 
    {'id': 'beyond_project_choice', 'title': 'beyond'} ,# 
    {'id': 'mavoEtrog_project_choice', 'title': 'מבוא אתרוג'} ,# 
    {'id': 'ahisamah_project_choice', 'title': 'אחיסמך'} ,# 
    {'id': 'ako_project_choice', 'title': 'קמפוס עכו'} ,# 
]
#Choose a topic for tidi work opening
tidi_choices = [
    {'id': 'plasterBlock_tidi', 'title': 'בלוק גבס'},  #
    {'id': 'wetRoomsSeal_tidi', 'title': 'איטום חדרים רטובים'},  #
    {'id': 'slariWallsDrill_tidi', 'title': 'קידוח בקירות סלארי'}, # 
    {'id': 'podsPlacement_tidi', 'title': 'הנחת פודים'}, # 
    {'id': 'innerFlooringCeramics_tidi', 'title': 'ריצוף פנים - קרמיקה'}, # 
    {'id': 'chillers_tidi', 'title': 'קירור מים קרים - צ׳ילרים'}, # 
    {'id': 'baranowichWallCladding_tidi', 'title': 'חיפוי קירות -שיטת ברנוביץ׳'} # 
]

class BotState:
    day = None
    project_number = None
    contractor_num=None
    tidi=None
    setting_reminder = False
    reminder_content = None
    reminder_date = None
    reminder_time = None
    reminder_phone_number = None
    setting_reminder_content = False
    

class Reminder:
    def __init__(self, content, reminder_datetime, phone_number):
        self.content = content
        self.reminder_datetime = reminder_datetime
        self.phone_number = phone_number

reminders = []

day_responses = [
    "לגבי איזה יום תרצה לדעת את",  # "What day would you like to know about?"
    "אנא ציין את היום עבור לוח הזמנים.",  # "Please specify the day for the schedule."
    "איזה יום השבוע מעניין אותך?"  # "Which day of the week are you interested in?"
]

project_number_responses = [
    "מה מספר הפרויקט שלך?",  # "What is your project number?"
    "תן לי רגע את מספר הפרויקט שלך",  # "Please provide the project number."
    "על איזה פרויקט אנחנו מדברים? תרשום לי רגע את המספר שלו.."  # "What is your project number?"
]

greetings_response = [
    "מה קורה חברים? איך אפשר לעזור..",
    "שדר אלי אחי, מה אתה צריך?",
    "כן אני איתכם, מה צריך?"
]
def generate_date_options():
    today = datetime.today()
    date_options = []
    for i in range(10):
        date = today + timedelta(days=i)
        date_str = date.strftime("%d/%m/%Y")
        date_options.append({"id": f"date_{date_str}", "title": date_str})
    return date_options

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")

def get_text_message_input(recipient, text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
    )

def fetch_schedule(project_number, day):
    try:
        logging.info(f"Loading Excel file from {EXCEL_FILE_PATH}")
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=str(project_number))
        logging.info(f"Excel sheet '{project_number}' loaded successfully")
        logging.info(f"Columns in sheet: {df.columns.tolist()}")

        if day not in df.columns:
            logging.error(f"Day '{day}' not found in the sheet '{project_number}'")
            return None

        schedule = df[['Hours', day]].dropna().to_dict('records')
        logging.info(f"Schedule fetched for day '{day}': {schedule}")
        return schedule
    except Exception as e:
        logging.error(f"Error fetching schedule: {e}")
        return None
    
def fetch_contractor(contractor):
    try:
        logging.info(f"Loading Excel file from {EXCEL_FILE_PATH}")
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name="contractors")
        logging.info(f"Excel sheet contractors loaded successfully")
        logging.info(f"Columns in sheet: {df.columns.tolist()}")

        if contractor not in df.columns:
            logging.error(f"contractor '{contractor}' not found in the sheet ")
            return None

        contractor_numbers = df[['numbers', contractor]].dropna().to_dict('records')
        logging.info(f"Schedule fetched for day '{contractor}': {contractor_numbers}")
        return contractor_numbers
    except Exception as e:
        logging.error(f"Error fetching schedule: {e}")
        return None
    
#fetch links to tidi
def fetch_tidi_link(tidi_topic):
    try:
        logging.info(f"Loading Excel file from {EXCEL_FILE_PATH}")
        # Load the Excel file
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name="KnowledgeBase")
        logging.info("Excel sheet 'KnowledgeBase' loaded successfully")
        logging.info(f"Columns in sheet: {df.columns.tolist()}")

        # Check if the tidi_topic is in the 'tidi_link_name' column
        if tidi_topic not in df['tidi_link_name'].values:
            logging.error(f"tidi_link_name '{tidi_topic}' not found in the sheet.")
            return None
        
        # Locate the row with the specified tidi_topic
        link_row = df[df['tidi_link_name'] == tidi_topic]
        
        if link_row.empty:
            logging.error(f"No link found for tidi_link_name '{tidi_topic}'.")
            return None

        # Fetch the link from the 'resource' column
        tidi_link = link_row['resource'].values[0]
        logging.info(f"Link found for '{tidi_topic}': {tidi_link}")
        
        return tidi_link

    except Exception as e:
        logging.error(f"Error fetching TIDI link: {e}")
        return None


def generate_response(response, user_id):
    if BotState.setting_reminder:
        if BotState.reminder_content is None:
            BotState.reminder_content = response
            return "מתי תרצה לקבל את התזכורת? (פורמט: YYYY-MM-DD HH:MM)"  # "When would you like to receive the reminder? (Format: YYYY-MM-DD HH:MM)"
        elif BotState.reminder_date is None:
            try:
                BotState.reminder_date = datetime.strptime(response, '%Y-%m-%d %H:%M')
                return "מה מספר הטלפון שברצונך לשלוח אליו את התזכורת?"  # "What is the phone number you want to send the reminder to?"
            except ValueError:
                return "פורמט התאריך והשעה שגוי. אנא נסה שוב."  # "The date and time format is incorrect. Please try again."
        elif BotState.reminder_phone_number is None:
            BotState.reminder_phone_number = response
            reminder = Reminder(BotState.reminder_content, BotState.reminder_date, BotState.reminder_phone_number)
            reminders.append(reminder)
            schedule_reminder(current_app._get_current_object(), reminder)
            reset_reminder_state()
            return "התזכורת שלך הוגדרה בהצלחה!"  # "Your reminder has been successfully set!"
    else:
        if re.search(r'תזכורת', response):
            BotState.setting_reminder = True
            return "מה התוכן של התזכורת?"  # "What is the content of the reminder?"

        # Check for greetings
        if re.search(r'(הי|שלום|אהלן|מה קורה|מה אומר)', response):
            # Send the list message using the new function
            body_text = "היי, בחרו את אחת מהאפשרויות הבאות:"
            data = get_list_message_input(user_id, body_text, choices)
            send_message(current_app._get_current_object(), data)
            return None  # Return None because we've sent the interactive message

        # Handle other bot states and responses as before
        # if re.search(r'(מלאכה|בלוק)', response):
        #     return random.choice(greetings_response)
        # if re.search(r'(טלפון|מספר|פלאפון|טלפונים)', response) and re.search(r'(בטון|קודח|משאב|גבסֿ|עפר|קידוח|מנוף|מנופים|מנופאי)', response):
        #     if re.search(r'(בטון|משאב)', response):
        #         BotState.contractor="cement"
        #     elif re.search(r'(קודח|קידוח)', response):
        #         BotState.contractor="drill"
        #     elif re.search(r'(גבס)', response):
        #         BotState.contractor="plaster"
        #     elif re.search(r'(מנוף|מנופים|מנופאי)', response):
        #         BotState.contractor="crane"
        #     contractor_numbers = fetch_contractor(BotState.contractor)
        #     if contractor_numbers:
        #         result = '\n'.join([f"{item['numbers']}: {item[BotState.contractor]}" for item in contractor_numbers])
        #     return result
        # elif BotState.day:
        #     for hebrew_day, english_day in day_map.items():
        #         if re.search(hebrew_day, response):
        #             BotState.day = english_day
        #             return random.choice(project_number_responses)
        # else:
        #     project_number = re.search(r'\d+', response)
        #     if project_number:
        #         BotState.project_number = project_number.group()
        #         schedule = fetch_schedule(BotState.project_number, BotState.day)
        #         if schedule:
        #             result = '\n'.join([f"{item['Hours']}: {item[BotState.day]}" for item in schedule])
        #         else:
        #             result = "לא נמצא לוח זמנים עבור מספר הפרויקט והיום המבוקש."  # "Schedule not found for the given project number and day."

        #         BotState.day = None
        #         BotState.project_number = None

        #         return result
        #     else:
        #         return "מספר פרויקט לא תקין. אנא נסה שוב."  # "Invalid project number. Please try again."

#function that handles the user buttons presses ( choices )
def handle_button_choice(button_id, user_id):
    if button_id == 'set_reminder':
        # Generate and send the date options
        date_options = generate_date_options()
        body_text = "בחרו את התאריך לתזכורת:"
        data = get_list_message_input(user_id, body_text, date_options)
        send_message(current_app._get_current_object(), data)
        return None  # return none because we've sent the message

    elif re.search(r'^date_', button_id):
        # Extract the selected date
        selected_date = button_id.split('_')[1]
        BotState.reminder_date = selected_date

        # Prompt the user to enter the time
        return "הכנס את השעה בפורמט hh:mm (לדוגמה: 10:10)."

    elif re.search(r'^time_', button_id):
        # Extract the entered time
        selected_time = button_id.split('_')[1]
        
        try:
            # Validate and format the time
            time_obj = datetime.strptime(selected_time, "%H:%M")
            BotState.reminder_time = time_obj.strftime("%H:%M")

            # Now ask for the phone number
            return "בבקשה ציין את מספר הטלפון שאליו תרצה לשלוח הודעה"  # "Please specify the phone number to send the reminder."

        except ValueError:
            return "פורמט הזמן אינו תקין. נסה שוב בפורמט hh:mm."  # "Invalid time format. Please try again in the format hh:mm."

    elif BotState.reminder_date and BotState.reminder_time and not BotState.reminder_phone_number:
        # Process the phone number input
        phone_number = button_id.strip()
        
        if phone_number.startswith('0'):
            phone_number = '+972' + phone_number[1:]

        BotState.reminder_phone_number = phone_number
        
        # Now ask for the reminder content
        BotState.setting_reminder_content = True
        return "מה התוכן של התזכורת?"  # "What is the content of the reminder?"

    elif BotState.setting_reminder_content:
        reminder_content = button_id  # Using button_id to hold the text content temporarily

        # Create a reminder object
        reminder_datetime = datetime.strptime(f"{BotState.reminder_date} {BotState.reminder_time}", "%d/%m/%Y %H:%M")
        reminder = Reminder(
            phone_number=BotState.reminder_phone_number,
            content=reminder_content,
            reminder_datetime=reminder_datetime
        )

        # Schedule the reminder
        schedule_reminder(current_app._get_current_object(), reminder)
        
        # Reset BotState for reminders
        reset_reminder_state()
        # Follow-up with "Can I help with something else?" buttons
        body_text = "התזכורת הוגדרה בהצלחה! האם אני יכול לעזור במשהו נוסף?"  # "Can I help with something else?"
        button_data = get_yes_no_buttons_message(user_id, body_text)
        send_message(current_app._get_current_object(), button_data)
        return None  # "Reminder set successfully!"

#get the schedule for this week
    elif button_id == 'check_schedule':
        body_text="אנא ציין את היום עבור לוח הזמנים."
        data = get_list_message_input(user_id, body_text, day_choices)
        send_message(current_app._get_current_object(), data)
        return None  # return none becouse weve sent the message
    
#get contractor phone numbers
    elif button_id == 'get_contact':
        body_text="בבקשה בחרו עבור איזה סוג קבלן תרצו לקבל מספרי טלפון-"
        data = get_list_message_input(user_id, body_text, contractor_choices)
        send_message(current_app._get_current_object(), data)
        return None  # return none becouse weve sent the message
    
    elif re.search(r'(_contractor_num)', button_id):
        BotState.contractor_num=button_id.split('_')[0]
        contractor_numbers = fetch_contractor( BotState.contractor_num)
        if contractor_numbers:
            result = '\n'.join([f"{item['numbers']}: {item[BotState.contractor_num]}" for item in contractor_numbers])
        else:
            result = "מצטער, לא קיימים נתונים לגבי קבלן זה."  # 

        BotState.contractor_num=None
        # Send the final response
        data = get_text_message_input(user_id, result)
        send_message(current_app._get_current_object(), data)
        
        # Follow-up with "Can I help with something else?" buttons
        body_text = "האם אני יכול לעזור במשהו נוסף?"  # "Can I help with something else?"
        button_data = get_yes_no_buttons_message(user_id, body_text)
        send_message(current_app._get_current_object(), button_data)
        return None  # return none becouse weve sent the message
    
    elif re.search(r'(_day_choice)', button_id):
        BotState.day=button_id.split('_')[0]
        body_text="בבקשה בחרו את הפרויקט שלכם"
        data = get_list_message_input(user_id, body_text, project_choices)
        send_message(current_app._get_current_object(), data)
        return None  # return none becouse weve sent the message
   
    elif re.search(r'(_project_choice)', button_id):
        BotState.project_number=button_id.split('_')[0]
        schedule = fetch_schedule(BotState.project_number, BotState.day)
        if schedule:
            result = '\n'.join([f"{item['Hours']}: {item[BotState.day]}" for item in schedule])
            
        else:
            result = "לא נמצא לוח זמנים עבור מספר הפרויקט והיום המבוקש."  # "Schedule not found for the given project number and day."

        BotState.day = None
        BotState.project_number = None
           # Send the final response
        data = get_text_message_input(user_id, result)
        send_message(current_app._get_current_object(), data)
        
        # Follow-up with "Can I help with something else?" buttons
        body_text = "האם אני יכול לעזור במשהו נוסף?"  # "Can I help with something else?"
        button_data = get_yes_no_buttons_message(user_id, body_text)
        send_message(current_app._get_current_object(), button_data)


        return None  # "return output from schedule in excel sheet
    #####################################
    #get tidi links
    elif button_id == 'get_tidi':
        body_text="בבקשה בחרו ערך עבורו תרצו לקבל פתיחת מלאכה"
        data = get_list_message_input(user_id, body_text, tidi_choices)
        send_message(current_app._get_current_object(), data)
        return None  # return none becouse weve sent the message
    
    elif re.search(r'(_tidi)', button_id):
        BotState.tidi=button_id.split('_')[0]
        tidi_link = fetch_tidi_link( BotState.tidi)
        if tidi_link:
            result = tidi_link
        else:
            result = "מצטער, לא מצאתי קישור תקין לבקשה שלך."  # 

        BotState.tidi=None
        # Send the final response
        data = get_text_message_input(user_id, result)
        send_message(current_app._get_current_object(), data)
        
        # Follow-up with "Can I help with something else?" buttons
        body_text = "האם אני יכול לעזור במשהו נוסף?"  # "Can I help with something else?"
        button_data = get_yes_no_buttons_message(user_id, body_text)
        send_message(current_app._get_current_object(), button_data)
        return None  # return none becouse weve sent the message
    #####################################

    
    else:
        return "בחירה לא ידועה. אנא נסה שוב."  # "Unknown choice. Please try again."  
   
def schedule_reminder(app, reminder):
    now = datetime.now()
    delay = (reminder.reminder_datetime - now).total_seconds()
    threading.Timer(delay, send_reminder, args=[app, reminder]).start()

def send_reminder(app, reminder):
    data = get_text_message_input(reminder.phone_number, reminder.content)
    send_message(app, data)

def reset_reminder_state():
    BotState.setting_reminder = False
    BotState.reminder_content = None
    BotState.reminder_date = None
    BotState.reminder_time = None
    BotState.reminder_phone_number = None


import json
import logging
import requests

#open list message for user's choices
def get_list_message_input(recipient, body_text, list_items):
    list_payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": ""},  # "Menu Selection"
            "body": {"text": body_text},
            "action": {
                "button": "בחרו אפשרות אחת",  # "Choose an option"
                "sections": [
                    {
                        "title": "אפשרויות",  # "Options"
                        "rows": [
                            {"id": item['id'], "title": item['title'][:20], "description": item.get('description', '')[:72]} for item in list_items
                        ]
                    }
                ]
            }
        }
    }
    return json.dumps(list_payload)


#yes and no buttons for end of conversation:
def get_yes_no_buttons_message(recipient, body_text):
    return json.dumps(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "yes", "title": "כן"}},
                        {"type": "reply", "reply": {"id": "no", "title": "לא"}},
                    ]
                }
            }
        }
    )



def send_message(app, data):
    with app.app_context():
        headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {app.config['ACCESS_TOKEN']}",
        }

        url = f"https://graph.facebook.com/{app.config['VERSION']}/{app.config['PHONE_NUMBER_ID']}/messages"

        logging.info(f"Sending request to URL: {url}")
        logging.info(f"Request headers: {headers}")
        logging.info(f"Request data: {data}")

        try:
            response = requests.post(url, data=data, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.Timeout:
            logging.error("Timeout occurred while sending message")
            return jsonify({"status": "error", "message": "Request timed out"}), 408
        except requests.RequestException as e:
            logging.error(f"Request failed due to: {e}")
            logging.error(f"Response content: {e.response.content}")
            return jsonify({"status": "error", "message": "Failed to send message"}), 500
        else:
            log_http_response(response)
            return response

def log_http_response(response):
    logging.info(f"Status: {response.status_code}")
    logging.info(f"Content-type: {response.headers.get('content-type')}")
    logging.info(f"Body: {response.text}")


def process_text_for_whatsapp(text):
    pattern = r"\【.*?\】"
    text = re.sub(pattern, "", text).strip()
    pattern = r"\*\*(.*?)\*\*"
    replacement = r"*\1*"
    whatsapp_style_text = re.sub(pattern, replacement, text)
    return whatsapp_style_text

def process_whatsapp_message(body):
    wa_id = body["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    name = body["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"]["name"]
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    
    if message["type"] == "interactive":
        if message["interactive"]["type"] == "button_reply":
            button_id = message["interactive"]["button_reply"]["id"]
            
            if button_id == 'yes':
                # Send the list message with choices
                body_text = "היי, בחרו את אחת מהאפשרויות הבאות:"
                data = get_list_message_input(wa_id, body_text, choices)
                send_message(current_app._get_current_object(), data)
                return None  # Message has been sent, no further action needed
            
            elif button_id == 'no':
                # End the conversation with a message
                final_message = "אוקי,אני כאן אם תרצו עזרה עם משהו נוסף.\n זכרו! אתם עושים עבודה מצוינת🫶."
                data = get_text_message_input(wa_id, final_message)
                send_message(current_app._get_current_object(), data)
                return None  # Message has been sent, no further action needed

            # Handle other button replies including reminders
            response = handle_button_choice(button_id, wa_id)
            
        elif message["interactive"]["type"] == "list_reply":
            list_id = message["interactive"]["list_reply"]["id"]
            response = handle_button_choice(list_id, wa_id)  # Reusing button choice handler for simplicity
    
    else:  # If it's plain text
        message_body = message["text"]["body"]
        
        # Handle the different stages of setting a reminder
        if BotState.reminder_date and BotState.reminder_time and not BotState.reminder_phone_number:
            # Use the message as the phone number input
            response = handle_button_choice(message_body.strip(), wa_id)  # Strip whitespace from phone number
        elif BotState.reminder_date and not BotState.reminder_time:
            # Use the message as the time input
            response = handle_button_choice(f"time_{message_body.strip()}", wa_id)  # Format as time input
        elif BotState.setting_reminder_content:
            # Use the message as the reminder content
            response = handle_button_choice(message_body, wa_id)
        else:
            # General response handling
            response = generate_response(message_body, wa_id)
    
    # Send the response if it's generated
    if response:
        data = get_text_message_input(current_app.config["RECIPIENT_WAID"], response)
        send_message(current_app._get_current_object(), data)


def is_valid_whatsapp_message(body):
    return (
        body.get("object")
        and body.get("entry")
        and body["entry"][0].get("changes")
        and body["entry"][0]["changes"][0].get("value")
        and body["entry"][0]["changes"][0]["value"].get("messages")
        and body["entry"][0]["changes"][0]["value"]["messages"][0]
    )

