"""Temporary local Windows-username convenience mapping, NOT authentication security.
Off by default. Does not touch Firebase or passwords. Must be configured by an already signed-in user.
"""
import getpass,time,os,math
KEY='trial_windows_autologin_v1'
def windows_user():
 if os.name=='nt':
  import ctypes
  from ctypes import wintypes
  size=wintypes.DWORD(256);buf=ctypes.create_unicode_buffer(size.value)
  if not ctypes.windll.advapi32.GetUserNameW(buf,ctypes.byref(size)):raise OSError('Windows username could not be read')
  return buf.value.strip().casefold()
 return getpass.getuser().strip().casefold()
def status(settings,users,now=None):
 now=time.time()if now is None else now;c=settings.get(KEY)or{}
 if not isinstance(c,dict):c={}
 user=c.get('program_user','')
 try:expiry=float(c.get('expires_at',0))
 except(TypeError,ValueError):expiry=0
 valid=c.get('enabled')is True and c.get('windows_user')==windows_user()and user in users and user!='ADMIN'and math.isfinite(expiry)and now<expiry
 return {'enabled':bool(valid),'program_user':user if valid else None,'windows_user':windows_user(),'expires_at':expiry,'trial_only':True,'convenience_not_security':True}
def enable(settings,user,users,minutes=60,now=None):
 if user not in users or user=='ADMIN':raise ValueError('Sign in as a non-ADMIN trial user first. ADMIN is never automatically selected.')
 if type(minutes)is not int or not 5<=minutes<=60:raise ValueError('Trial expiry must be 5 to 60 minutes')
 now=time.time()if now is None else now;settings[KEY]={'enabled':True,'windows_user':windows_user(),'program_user':user,'expires_at':now+minutes*60};return status(settings,users,now)
def disable(settings):settings.pop(KEY,None)
