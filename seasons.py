"""Recurring Cindy Lú themes, using calendar dates in continental Chile."""
import datetime as dt
from zoneinfo import ZoneInfo

ZONE='America/Santiago'
LEAD_DAYS=10

def events(year):
    may_first=dt.date(year,5,1)
    mother=may_first+dt.timedelta(days=(6-may_first.weekday())%7+7)
    return [
        ('birthday','Cumpleaños de Cindy y Florencia',dt.date(year,2,8),'Celebramos a Cindy y Florencia'),
        ('mother','Día de la Madre',mother,'Con cariño, para mamá'),
        ('halloween','Halloween',dt.date(year,10,31),'Un toque de magia dorada'),
        ('christmas','Navidad',dt.date(year,12,25),'Pequeños detalles, mucha ilusión'),
    ]

def season_for(day=None):
    day=day or dt.datetime.now(ZoneInfo(ZONE)).date()
    calendar=[]
    for year in (day.year,day.year+1):
        for key,label,event,greeting in events(year):
            if event>=day:calendar.append((event,key,label,greeting))
    event,key,label,greeting=min(calendar)
    remaining=(event-day).days
    active=remaining<=LEAD_DAYS
    countdown=('Hoy · '+label) if remaining==0 else str(remaining)+(' día para ' if remaining==1 else ' días para ')+label
    upcoming=[]
    for k,l,d,_ in events(day.year):
        if d<day:d=next(e[2] for e in events(day.year+1) if e[0]==k)
        upcoming.append({'key':k,'label':l,'date':d.isoformat(),'starts':(d-dt.timedelta(days=LEAD_DAYS)).isoformat()})
    return {'key':key if active else 'base','event_key':key,'label':label,'greeting':greeting,
            'date':day.isoformat(),'event_date':event.isoformat(),'starts':(event-dt.timedelta(days=LEAD_DAYS)).isoformat(),
            'days':remaining,'countdown':countdown,'active':active,'year':event.year,
            'variant':event.year%4,'seed':event.year*31+sum(map(ord,key)),'timezone':ZONE,
            'calendar':sorted(upcoming,key=lambda e:e['date'])}
