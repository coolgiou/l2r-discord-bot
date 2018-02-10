import discord
import asyncio
from discord.ext import commands
import platform
import os
import settings
from gsheets import get_calendar_desc, gsheets
import pandas as pd
import threading
import traceback
import difflib
import datetime

client = commands.Bot(command_prefix='!')

#------------------------------------------------------------------------------
#General
#------------------------------------------------------------------------------
@client.event
async def on_ready():
  if not settings.silent_mode:
    print('Logged in as '+client.user.name+' (ID:'+client.user.id+') | Connected to '+str(len(client.servers))+' servers | Connected to '+str(len(set(client.get_all_members())))+' users')
    print('--------')
    print('Current Discord.py Version: {} | Current Python Version: {}'.format(discord.__version__, platform.python_version()))
    print('--------')
    print('Use this link to invite {}:'.format(client.user.name))
    print('https://discordapp.com/oauth2/authorize?client_id={}&scope=bot&permissions=536345663'.format(client.user.id))
  return await client.change_presence(game=discord.Game(name='with your mom.')) 
@client.event
async def on_message(message):
  if message.author!=client.user:
    await client.process_commands(message)
@client.event
async def on_error(event, *args, **kwargs):
  print(traceback.format_exc())
#------------------------------------------------------------------------------
#Non-cog functionality
#------------------------------------------------------------------------------
#@client.event
#async def on_message(message):
#  if message.author!=client.user:
#    await client.process_commands(message)
#    if message.channel.is_private and message.author.id in settings.admin_list:
#      await client.send_message(discord.utils.get(discord.utils.get(client.servers, name=settings.server_name).channels, name = settings.pm_channel_name),message.content)
    
@client.command(pass_context=True,brief='Helps to find mutual open cores for party')
async def test(ctx):
  await client.send_message(ctx.message.channel, '*usual* **__Markdown__**') 

#------------------------------------------------------------------------------
#Cogs
#------------------------------------------------------------------------------
class Cores():
  def __init__(self, client):
    self.client = client
  @commands.command(pass_context=True,brief='Marks cores as closed')
  async def cores_close(self, ctx):
    name = ctx.message.author.display_name
    monster_name = ctx.message.content[13:]
    await self.client.send_message(ctx.message.channel, ctx.message.author.mention + gsheets().post_core_closed(name, monster_name)) 
  @commands.command(pass_context=True,brief='Helps to find mutual open cores for party')
  async def cores(self, ctx):
    def find_between(s, first, last):
      try:
        start = s.index(first) + len(first)
        end = s.index(last, start)
        return s[start:end]
      except ValueError:
          return ""
    names = find_between(ctx.message.content, '[', ']').split(',')
    names = [x.strip() for x in names]
    if len(ctx.message.content.split('],',1))>1:
      context = ctx.message.content.split('],',1)[1].strip()
    else:
      context = ''
    message = gsheets().get_mutually_open_cores(names, context)
    if type(message)==str:
      await self.client.send_message(ctx.message.channel, ctx.message.author.mention + message)
    else:
      message.set_author(name=client.user.name, icon_url=client.user.default_avatar_url)
      await self.client.send_message(ctx.message.channel, embed = message)

class Administration():
  def __init__(self, client):
    self.client = client
    self.clearing_channels = []
  async def on_member_join(self,member):
    role = discord.utils.get(member.server.roles, name=settings.newcomer_role_name)
    await self.client.add_roles(member, role)
  @commands.command(pass_context=True,brief='Admin only: Clears last n messagaes in chat.')
  async def clear_chat(self, ctx):
    if ctx.message.author.id in settings.admin_list and not ctx.message.channel.is_private:
      if ctx.message.channel in self.clearing_channels:
        await self.client.send_message(ctx.message.channel, ctx.message.author.mention + ' already deleting messages in that channel, relax.')
      else:
        self.clearing_channels.append(ctx.message.channel)
        try:
          number = int(ctx.message.content[12:].strip())
        except:
          number = 1000000
        counter = 0
        old_msg = False
        while number-counter>0:
          mgs = []
          async for x in self.client.logs_from(ctx.message.channel, limit = min(number-counter,100), before = ctx.message):
            if (ctx.message.timestamp - x.timestamp).days >= 14:
              old_msg = True
              break
            else:
              mgs.append(x)
          if len(mgs) == 0:
            break
          elif len(mgs) == 1:
            await self.client.delete_message(mgs[0])
            counter += 1
            break
          else:
            await self.client.delete_messages(mgs)
            counter += len(mgs)
        if old_msg:
          await self.client.send_message(ctx.message.channel, ctx.message.author.mention + ' It will take pretty long to delete all mesages, i will start...')
          async for x in self.client.logs_from(ctx.message.channel, limit = number-counter, before = ctx.message):
            await self.client.delete_message(x)
            counter+=1
        self.clearing_channels.remove(ctx.message.channel)
        await self.client.send_message(ctx.message.channel, ctx.message.author.mention + ' deleted '+str(counter)+ ' messages.')  

class Calendar():
  def __init__(self,client):
    self.client = client
    self.SubThreadObj = self.SubThread()
    self.SubThreadObj.start()
    self.client.loop.create_task(self.run())
  @commands.command(pass_context=True, brief='Use to find out the calendar. Optional parameters: "tomorrow" or needed date.')
  async def calendar(self,ctx):
    if ctx.message.author!=client.user:
      condition = ctx.message.content[9:]
      calendar_list = get_calendar_desc(condition)
      if len(calendar_list)==0:
        await self.client.send_message(ctx.message.channel, "Nothing is in calendar.") 
      else:
        await self.client.send_message(ctx.message.channel, '\n'.join(calendar_list))
  async def run(self):
    try:
      msg_text = self.SubThreadObj.getMsg()
      if msg_text != '':
        if not settings.silent_mode:
          print(msg_text)
        await self.client.send_message(discord.utils.get(discord.utils.get(self.client.servers, name=settings.server_name).channels, name = settings.calendar_channel_name), msg_text)
    except:
      print(traceback.format_exc())
    finally:
      await asyncio.sleep(5)
      self.client.loop.create_task(self.run())
  class SubThread(threading.Thread):
    def __init__(self):
      threading.Thread.__init__(self)
      self.msg_text = ''
      self.calendar_list = ''
      self.calendar_date = datetime.datetime.utcnow().date()
    def run(self):
      import time
      while True:
        try:
          calendar_list = get_calendar_desc()
          if self.calendar_list[:-1] != calendar_list[:-1] and len(calendar_list)>0:
            if len(self.calendar_list)>0:
              if self.calendar_date == datetime.datetime.utcnow().date():
                msg_list = list(difflib.Differ().compare(self.calendar_list[:-1], calendar_list[:-1]))
                new_msg_list = []
                for el in msg_list:
                  if el[0]==' ':
                    new_msg_list.append(el[2:])
                  elif el[0]=='+':
                    new_msg_list.append('**__Added: ' + el[1:]+'__**')
                  elif el[0]=='-':
                    new_msg_list.append('Deleted: ~~' + el[1:]+'~~`')
                self.msg_text = '@everyone Calendar for today have been changed:\n' + '\n'.join(new_msg_list) + '\n' + calendar_list[-1]
              else:
                self.msg_text = '@everyone' + '\n'.join(calendar_list)
            self.calendar_list = calendar_list
            self.calendar_date = datetime.datetime.utcnow().date()
        except:
          print(traceback.format_exc())
        finally:
          time.sleep(5) 
    def getMsg(self):
      result = self.msg_text
      self.msg_text = ''
      return result
      
class Attendance():
  def __init__(self,client):
    self.client = client
    self.started = False
    self.lock = asyncio.Lock()
  @commands.command(pass_context=True,brief='Admin only: Starts attendance monitoring.')
  async def start(self,ctx):
    if (ctx.message.author.id in settings.admin_list or ctx.message.author.id in settings.attendance_master_list) and ctx.message.channel.name == settings.attendance_channel_name:  
      await client.send_message(ctx.message.channel, 'Attendance monitoring activated.')
      self.started = True
  @commands.command(pass_context=True,brief='Admin only: Stops attendance monitoring.')
  async def stop(self,ctx):
    if (ctx.message.author.id in settings.admin_list or ctx.message.author.id in settings.attendance_master_list) and ctx.message.channel.name == settings.attendance_channel_name:  
      await client.send_message(ctx.message.channel, 'Attendance monitoring stoped.')
      self.started = False
  @commands.command(pass_context=True,brief='Use to post attendance if you are without party.')
  async def solo(self,ctx):
    if ctx.message.channel.name == settings.attendance_channel_name:
      if self.started:
        if ctx.message.content == '!solo':
          name = ctx.message.author.display_name
        else:
          name = ctx.message.content[6:].strip()
        correct_name = gsheets().get_correct_name(name)
        if correct_name != None:
          gsheets().post_attendance([correct_name])
          text = ctx.message.author.mention + 'Posted: ' + str(correct_name)
        else:
          text = ctx.message.author.mention + 'Unrecognized name: '+ str(name)
        await client.send_message(ctx.message.channel, text)
      else:
        await client.send_message(ctx.message.channel, ctx.message.author.mention + 'Attandance monitoring is stopped.')
  async def on_message(self,message):
    if message.channel.name == settings.attendance_channel_name:
      for attach in message.attachments:
        filename, file_extension = os.path.splitext(attach['filename'])
        if file_extension in ('.jpg','.png','jpeg','.bmp'):
          if self.started:
            if self.lock.locked():
              await client.send_message(message.channel, message.author.mention + 'Processing is queued, it will take some time to finish.')
            await self.lock.acquire()
            try:
              recognized, unregonized = await gsheets().get_names_from_image_url(self.client.loop, attach['url'])
            finally:
              self.lock.release()
            gsheets().post_attendance(recognized)
            text = message.author.mention + 'Posted: ' + str(recognized)
            if len(unregonized)>0:
              text += ', Unrecognized: '+ str(unregonized)
            await client.send_message(message.channel, text)
          else:
            await client.send_message(message.channel, message.author.mention + 'Attandance monitoring is stopped.')

class Notifications():
  def __init__(self,client):
    self.client = client
    self.prev_df = pd.DataFrame()
    self.SubThreadObj = self.SubThread()
    self.SubThreadObj.start()
    self.client.loop.create_task(self.run())
  async def run(self):
    try:
      msg_text = self.SubThreadObj.getMsg()
      if msg_text != '':
        if not settings.silent_mode:
          print(msg_text)
        await self.client.send_message(discord.utils.get(discord.utils.get(self.client.servers, name=settings.server_name).channels, name = settings.calendar_channel_name),'@everyone\n' + msg_text)
    except:
      print(traceback.format_exc())
    finally:
      await asyncio.sleep(5)
      self.client.loop.create_task(self.run())
  class SubThread(threading.Thread):
    def __init__(self):
      threading.Thread.__init__(self)
      self.msg_text = ''
      self.prev_df = pd.DataFrame()
    def run(self):
      import time
      while True:
        try:
          msg_text, self.prev_df = gsheets().get_notifications(self.prev_df)
          self.msg_text += msg_text
        except:
          print(traceback.format_exc())
        finally:
          time.sleep(5) 
    def getMsg(self):
      result = self.msg_text
      self.msg_text = ''
      return result
 
client.add_cog(Administration(client))
client.add_cog(Cores(client))
client.add_cog(Calendar(client))
client.add_cog(Attendance(client))
client.add_cog(Notifications(client))
client.run(settings.token)