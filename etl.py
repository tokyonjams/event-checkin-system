import gspread 
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd 
from dotenv import load_dotenv
import os
load_dotenv()

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
json_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

creds = ServiceAccountCredentials.from_json_keyfile_name(json_file, scope)
client = gspread.authorize(creds)

sheet_title = os.getenv("SHEET_NAME")
sheet = client.open(sheet_title).worksheet("Form_Responses")

# Get all values and manually create DataFrame to handle duplicate headers
all_values = sheet.get_all_values()
headers = all_values[0]
data_rows = all_values[1:]

# Create DataFrame with first occurrence of each header
# If duplicate headers exist, only the first one will be used
unique_headers = []
header_counts = {}
for h in headers:
    if h in header_counts:
        header_counts[h] += 1
        unique_headers.append(f"{h}_{header_counts[h]}")
    else:
        header_counts[h] = 1
        unique_headers.append(h)

df = pd.DataFrame(data_rows, columns=unique_headers)

# Use the original first header for rename_map
df.columns = headers[:len(df.columns)]

print("Column names:", df.columns.tolist())
rename_map = { 
    'タイムスタンプ': 'Timestamp', 
    'お名前(フルネーム) / Your full name': 'Name',
    'ローマ字でフルネームをご記載ください。(上に書かれたものと違う場合）\nPlease enter your full name (if it is different from the one above).': 'Full Name',
    'Email address': 'email',
    '大学はどこですか？/ Which university do you go to? ': 'Uni',
    '学部・コース / faculty and courses': 'faculty',
    '何年生ですか？ / What year are you in? ': 'Year',
    '食物アレルギーなど、食事に関する特別な配慮事項はございますか？\nDo you have any food allergies or special dietary requirements?': 'dietary_requirement',
    '本イベントでは、事前に共有いただいたアレルギー情報や配慮事項を基に最善の配慮を行いますが、全てのリスクを完全に保証することは致しかねます。飲食物等の最終判断はご自身の責任とし、万が一アレルギー等の問題が発生した場合でも、主催者の重大な過失がある場合を除き、責任を問わないことに同意します。\nWhile we will make every reasonable effort to accommodate allergies or special dietary requirements based on the information you provide in advance, we cannot fully guarantee the elimination of all risks. You are responsible for your own final judgement regarding food and drinks, and you agree that the organisers will not be held liable for any issues related to allergies unless caused by gross negligence.': 'allergy_waiver_consent',
    '本イベントでは活動記録・広報のため写真撮影を行い、一部の写真がその目的のためにSNSに投稿されることがあります。\nそれに同意しますか？\nDuring the event, photos may be taken for documentation and promotional purposes, and some of them may be posted on our social media.\nDo you agree to this?': 'photo_consent',
    'payment_status': 'payment_status',
    'リマインド状況': 'reminder_status',
    '今後どのような会が開催されれば参加したいか教えてください。 / Could you tell us what kind of events you would be interested in attending in the future?': 'future_events',
    '列 12': 'column_12',
    'イベントに参加しようと思った理由はなんですか？\nWhat makes you want to participate in this event?': 'participation_reason'
}

df_clean = df.rename(columns=rename_map)

binary_map = {
    'いいえ / No': 0,
    '同意する/ Agreed': 1
}

df_clean['dietary_requirement'] = df_clean['dietary_requirement'].map(lambda x: 0 if x == 'いいえ / No' else x)


df_clean['allergy_waiver_consent'] = df_clean['allergy_waiver_consent'].map(binary_map)
df_clean['photo_consent'] = df_clean['photo_consent'].map(binary_map)

print("--- スプレッドシートから取得したデータ ---")
print(df_clean.head())


from sqlalchemy import create_engine, text 

host = os.getenv(DB_HOST)
password = os.getenv(DB_PASSWORD)
user = os.getenv(DB_USER)
port = os.getenv(DB_PORT)
database = os.getenv(DB_NAME)

engine = create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}")

df_clean.to_sql("bbq_staging", engine, if_exists="replace", index=False)

def update_db_from_staging(engine): 
    with engine.begin() as conn: 
        conn.execute(text(
            """
            INSERT IGNORE INTO university (university_name)
            SELECT DISTINCT
                b.`Uni`
            FROM bbq_staging b
            WHERE b.`Uni` is NOT NULL;
            """
        ))

        conn.execute(text("""
            INSERT INTO people (name, email, created_at)
            SELECT DISTINCT
                b.`Name`,
                b.`email`,
                b.`Timestamp`
            FROM bbq_staging b
            LEFT JOIN people p ON p.email = b.`email`
            WHERE p.email IS NULL;"""))
        
        conn.execute(text(""" 
            INSERT IGNORE INTO faculty (faculty_name, university_id)
            SELECT DISTINCT
                b.`faculty`,
                u.university_id 
            FROM bbq_staging b
            JOIN university u ON u.university_name = b.`Uni`
            WHERE b.`faculty` is NOT NULL;
        """))

        conn.execute(text("""
            INSERT IGNORE INTO event_registration
            (event_id, person_id, faculty_id, year_of_study,
             dietary_requirement, photo_consent,
             allergy_waiver_agreed, 
             registered_at, payment_status)

            SELECT
                5,
                p.person_id,
                f.faculty_id,
                b.`Year`,
                b.`dietary_requirement`,
                b.`photo_consent`,
                b.`allergy_waiver_consent`,
                STR_TO_DATE(b.`Timestamp`, '%Y/%m/%d %H:%i:%s'),
                CASE WHEN b.`payment_status` = 'TRUE' THEN 1 ELSE 0 END
            FROM bbq_staging b
            JOIN people p ON p.email = b.`email`
            JOIN university u ON u.university_name = b.`Uni`
            JOIN faculty f ON f.university_id = u.university_id
                 AND f.faculty_name = b.`faculty`

            ON DUPLICATE KEY UPDATE
                dietary_requirement = VALUES(dietary_requirement),
                photo_consent = VALUES(photo_consent),
                allergy_waiver_agreed = VALUES(allergy_waiver_agreed),
                payment_status = VALUES(payment_status);""")) 
        conn.execute(text("""
            UPDATE event_registration er
            JOIN people p ON er.person_id = p.person_id
            JOIN bbq_staging b ON p.email = b.email
            SET er.payment_status = CASE WHEN b.payment_status = 'TRUE' THEN 1 ELSE 0 END
            WHERE er.event_id = 5;
        """))


update_db_from_staging(engine)

print("Database updated successfully!")



