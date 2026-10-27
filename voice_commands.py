# SPDX-License-Identifier: GPL-3.0-only
"""Strict Italian/English grammar; no eval, model or hardware access."""
import re

def parse_command(text):
 if not isinstance(text,str) or len(text)>240:raise ValueError('Comando vocale non valido.')
 text=text.strip().lower().rstrip('.!?').replace('−','-')
 text=re.sub(r'\b(meno|minus)\s+', '-', text)
 text=re.sub(r'\b(più|piu|plus)\s+', '+', text)
 words={'uno':'1','una':'1','due':'2','tre':'3','quattro':'4','cinque':'5','sei':'6','one':'1','two':'2','three':'3','four':'4','five':'5','six':'6'}
 for word,value in words.items():text=re.sub(r'\b'+word+r'\b',value,text)
 pose=re.fullmatch(r'(?:avvia\s+(?:la\s+)?posa|start\s+pose)\s+(\d{1,4})',text)
 if pose and int(pose[1])>=1:return dict(op='pose_start',index=int(pose[1])-1)
 if not re.match(r'^(muovi|move)\s+',text):raise ValueError('Usa: muovi J2 di 45 gradi; muovi J1 a 45 e J2 a 30; avvia posa 1.')
 text=re.sub(r'^(muovi|move)\s+','',text)
 parts=re.split(r'\s+(?:e|and)\s+|\s*;\s*|,\s*(?=(?:il\s+)?(?:j|giunto|joint))',text)
 targets=[];axes=set()
 for part in parts:
  match=re.fullmatch(r'(?:il\s+)?(?:j\s*|giunto\s*|joint\s*)([1-6])\s+(di|by|a|to)\s*([+-]?\s*\d{1,3}(?:[.,]\d{1,2})?)\s*(?:gradi|degrees)?',part.strip())
  if not match:raise ValueError('Comando ambiguo: specifica giunto, a/di e angolo per ogni movimento.')
  axis=int(match[1])-1;value=float(match[3].replace(' ','').replace(',','.'))
  if abs(value)>360 or axis in axes:raise ValueError('Angolo fuori intervallo o giunto ripetuto.')
  axes.add(axis);targets.append(dict(axis=axis,value=value,relative=match[2] in ('di','by')))
 return dict(op='joint_targets',targets=targets)

def confirmation(text):
 text=re.sub(r'[^\w\s]','',str(text).lower()).strip()
 text=' '.join(text.split())
 if text in ('sì confermo','si confermo','confermo','yes confirm','yes i confirm','i confirm'):return True
 if text in ('annulla','no','cancel','no cancel'):return False
 return None
