import datetime
import numpy as np
import pandas as pd
from PIL import Image
import cv2
import settings
from pytz import timezone
import pytz

def get_gsheet_client():
  import gspread
  from oauth2client.service_account import ServiceAccountCredentials
  scope = ['https://spreadsheets.google.com/feeds']
  creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
  return gspread.authorize(creds)

#------------------------------------------------------------------------------
#Get calendar description
#------------------------------------------------------------------------------
def get_calendar_desc(condition = ''):
  day_num = datetime.datetime.now(tz=timezone(settings.timezone)).day
  if condition.find('tomorrow')>0:
    day_num = day_num+1
  else:
    try:
      day_num = int(condition)
    except ValueError:
      pass

  records = get_gsheet_client().open_by_url(settings.clansheet_url).worksheet('4. CALENDAR').get_all_values()
  result = []
  for i in range(len(records)):
    for j in range(len(records[i])):
      if records[i][j].strip() == str(day_num):
        result.append('Calendar for '+ records[i][j].strip() +' '+ records[0][1] + ':')
        for row in records[i+1][j].split('   '):
          text = row.strip()
          if text != '':
            result.append(text)
        result.append('Current time: ' + datetime.datetime.now(tz=timezone(settings.timezone)).strftime("%H:%M:%S"))
  return result
#------------------------------------------------------------------------------
#Get names from image
#------------------------------------------------------------------------------
async def get_names_from_image_bytes(image_bytes):
  return get_names_from_image(get_image_from_bytes(image_bytes))

def get_image_from_bytes(image_bytes):
  from io import BytesIO
  image = Image.open(BytesIO(image_bytes))
  return cv2.cvtColor(np.asarray(image), cv2.COLOR_BGR2RGB)

def dichotomy(low,up,power):
  for i in range(0, power+1):
    for j in range(1,2**i,2):
      yield (j/2**i)*(up-low)+low

def get_names_from_image(image):
  import pytesseract
  from math import hypot

  template = cv2.imread("clan_emblem.png")
  pytesseract.pytesseract.tesseract_cmd = 'E:\\My Projects\\Python\\la2r-discord-bot\\Tesseract-OCR\\tesseract.exe'
  if image.shape[1]>1920:
    image = cv2.resize(image, (0,0), fx=1920/image.shape[1], fy=1920/image.shape[1])

  max_match = 0
  points = []
  for scale in np.logspace(1, -1, 20, base=2)[::-1]:
    resized = cv2.resize(template, (0,0), fx=scale, fy=scale)
    matchTemplate = cv2.matchTemplate(resized,image,cv2.TM_CCOEFF_NORMED)
    match = max([max(sublist) for sublist in matchTemplate])
    if max_match > match:
      continue
    else:
      points = []
      max_match_scale = scale
      max_match = match
      loc = np.where(matchTemplate>= max_match*0.8)
      for pt in zip(*loc[::-1]):
        for pt2 in points[:]:
          if hypot(pt[0]-pt2[0], pt[1]-pt2[1])<15:
            break
        else:
          points.append(pt)
  result = []
  unrecognized = []
  my_gsheets = gsheets()
  for pt in points:
    im = image[int((pt[1]+25*max_match_scale)):int((pt[1]+60*max_match_scale)), int((pt[0]+60*max_match_scale)):int((pt[0]+230*max_match_scale))]
    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    im = cv2.resize(im, (0,0), fx=4, fy=4)
#    cv2.imshow('image',im)
#    cv2.waitKey(0)
#    cv2.destroyAllWindows()
    guess = pytesseract.image_to_string(Image.fromarray(im))
    name = None
    if guess != '':
      name = my_gsheets.get_correct_name(guess)
    if name == None:
      for i in dichotomy(200,60,6):
        im2 = cv2.threshold(im, i, 255, cv2.THRESH_BINARY)[1]
#        cv2.imshow('image',im2)
#        cv2.waitKey(0)
#        cv2.destroyAllWindows()
        guess2 = pytesseract.image_to_string(Image.fromarray(im2))
        if guess2 !='':
           name = my_gsheets.get_correct_name(guess2)
           if name != None:
              break
    if name!= None:
      result.append(name)
    else:
      unrecognized.append(guess)
  return result,unrecognized

class gsheets:
  def __init__(self):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scope = ['https://spreadsheets.google.com/feeds']
    creds = ServiceAccountCredentials.from_json_keyfile_name('client_secret.json', scope)
    self.client = gspread.authorize(creds)
    self.members = []
  def load_members(self):
    if len(self.members)==0:
      self.members = list(filter(None, self.client.open_by_url(settings.clansheet_url).worksheet('7. ATTENDANCE').col_values(2)[4:]))
  def get_correct_name(self,name):
    from difflib import SequenceMatcher
    self.load_members()
    max_similarity_ratio = 0
    new_name = ''
    for member in self.members:
      similarity_ratio = SequenceMatcher(None, name, member).ratio()
      if max_similarity_ratio < similarity_ratio:
        max_similarity_ratio = similarity_ratio
        new_name = member
    if max_similarity_ratio>0.6:
      return new_name
    else:
      return None
  def post_attendance(self,names):
    sheet = self.client.open_by_url(settings.clansheet_url).worksheet('7. ATTENDANCE')
    members = sheet.col_values(2)[4:]
    dates = sheet.row_values(3)[4:]
    weekday = datetime.datetime.now(tz=timezone(settings.timezone)).weekday()
    cur_date_column = dates.index(datetime.datetime.now(tz=timezone(settings.timezone)).date().strftime("%d/%m"))+5
    for name in names:
      for i in range(len(members)):
        if members[i] == name:
          if weekday in [0,4]:
            sheet.update_cell(i+5,cur_date_column,2)
          else:
            sheet.update_cell(i+5,cur_date_column,1)
          break
  def post_core_closed(self, player_name, monster_name):
    if monster_name == '':
      return 'Please provide monster name, f.e.: "!cores_close Black Fang".'
    if player_name == '':
      return 'Empty player name.'
    temp = self.get_correct_name(player_name)
    if temp == None:
      return 'Unrecognized name "' + player_name + '".'
    else:
      player_name = temp
    sheet = self.client.open_by_url(settings.clansheet_url).worksheet('6. CORES')
    player_names = sheet.row_values(1)[5:]
    monster_names = sheet.col_values(1)[1:]
    if not player_name in player_names:
      return 'Player name "' + player_name + '" not found.'
    if not monster_name in monster_names:
      return 'Monster name "' + monster_name + '" not found.'
    sheet.update_cell(monster_names.index(monster_name)+2,player_names.index(player_name)+6,'☑')
    return monster_name + "'s core was marked as closed for " + player_name
  def get_mutually_open_cores(self, names, condition = ''):
    if len(names)==0:
      return 'No names in list.'
    sheet = self.client.open_by_url(settings.clansheet_url).worksheet('6. CORES')
    field_names = sheet.get_all_values()[0]
    fields = ['Monster','City','Map', 'CP/core', 'Boss']
    recognized_names = []
    unrecognized_names = []
    for name in names:
      if name in field_names:
        recognized_names.append(name)
        fields.append(name)
      else:
        unrecognized_names.append(name)
    if len(unrecognized_names)>0:
      return 'Unrecognized: ' + str(unrecognized_names)
    df = pd.DataFrame(sheet.get_all_records())[fields]
    df = df[df['City']!='']
    df = df[df['Boss']!='TRUE']


    if condition == '':
      description='Mutual open cores for ' + ', '.join(names) + ' are:'
    else:
      if not df[df['City']==condition].empty:
        df = df[df['City']==condition]
        description = 'Mutual open cores in **' + condition + '** for ' + ', '.join(names) + ' are:'
      elif not df[df['Map']==condition].empty:
        df = df[df['Map']==condition]
        description = 'Mutual open cores in **' + condition + '** for ' + ', '.join(names) + ' are:'
      else:
        return 'Unrecognized context "' + condition + '".'

    for name in recognized_names:
      df = df[df[name]=='☐']
    if df.empty:
      return 'No mutual cores under context.'
    else:
      df = df.sort_values('CP/core', ascending=False)
#      embed=discord.Embed(title="Cores", description=description, color=0x004000)
      text = 'CP/core  Monster      Map\n'
      for index, row in df.iterrows():
        text += "{:6.2f}".format(row['CP/core'])+'   '+row['Monster']+' '*max(13-len(row['Monster']),1)+row['Map']+'\n'
#      embed.add_field(name='CP/core Monster Map', value=text, inline=True)
      return description + '\n```\n' + text + '\n```'
  def get_notifications(self, prev_df):
    def get_date(row):
      return datetime.datetime.combine(datetime.datetime.now(tz=timezone(settings.timezone)).date() - datetime.timedelta(days=datetime.datetime.now(tz=timezone(settings.timezone)).date().weekday()-row['weekday_num']+1),row['time'].time())
    def seconds_to_timedelta(i):
      return datetime.timedelta(seconds=i)
    def is_date_passed(in_date):
      return pytz.timezone(settings.timezone).localize(in_date)<datetime.datetime.now(tz=timezone(settings.timezone))
    timetable_df = pd.DataFrame(self.client.open_by_url(settings.clansheet_url).worksheet('bot_events').get_all_records())
    periods_df = pd.DataFrame(self.client.open_by_url(settings.clansheet_url).worksheet('bot_notifications').get_all_records())
    df = pd.merge(timetable_df,periods_df, how='inner', on='event_name')
    df['time']=pd.to_datetime(df['time'])
    df['datetime'] = df.apply(get_date, axis=1)
    for index, row in df.iterrows():
      if row['repeated_in_hours']!='':
        for new_datetime in [row['datetime'] + datetime.timedelta(hours=x) for x in range(int(row['repeated_in_hours']), 24*7, int(row['repeated_in_hours']))]:
          new_row = row
          new_row['datetime']=new_datetime
          df = df.append(new_row, ignore_index=True)
    df['period_passed'] = (df['datetime']-df['seconds_before'].apply(seconds_to_timedelta)).apply(is_date_passed)
    msg_text = ''
    if not prev_df.empty:
      msg_df = df[df['period_passed']==True].merge(prev_df[prev_df['period_passed']==False], on = ['datetime','event_name','seconds_before'], how='left', indicator= True)
      msg_df = msg_df[msg_df['_merge']=='both']
      for index, row in msg_df.iterrows():
        msg_text += row['text'] + '\n'
    prev_df = df[['event_name','datetime','seconds_before','period_passed']]
    return msg_text, prev_df
  async def get_names_from_image_url(self,loop, url):
    import aiohttp
    async with aiohttp.ClientSession(loop=loop) as cs:
      async with cs.get(url) as r:
        image_bytes = await r.read()
    return get_names_from_image(get_image_from_bytes(image_bytes))

#for i in range(1,11):
#  print(get_names_from_image(cv2.imread(str(i)+".png")))


#print(gsheets().post_core_closed('TaMaT', 'Sandstorm'))
#gsheets().get_mutually_open_cores(['TaMaT'],'Giran')
