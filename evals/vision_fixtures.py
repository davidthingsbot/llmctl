"""Versioned synthetic vision fixtures. Answers are never embedded in requests."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def build_suite(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    tasks=[]
    def canvas(title, size=(900,700)):
        im=Image.new('RGB',size,'white'); d=ImageDraw.Draw(im)
        d.text((25,18),title,font=ImageFont.truetype(FONT,28),fill='black')
        return im,d
    def text(d,xy,s,size=24,fill='black'):
        d.text(xy,str(s),font=ImageFont.truetype(FONT,size),fill=fill)
    def save(im,ident,difficulty,question,expected):
        p=directory/(ident+'.png'); im.save(p)
        tasks.append(dict(id=ident,difficulty=difficulty,image=str(p.resolve()),question=question,expected=expected))
    def arrow(d,a,b):
        import math
        d.line((a,b),fill='black',width=3)
        angle=math.atan2(b[1]-a[1],b[0]-a[0])
        pts=[b]+[(b[0]-13*math.cos(angle+s),b[1]-13*math.sin(angle+s)) for s in (-0.45,0.45)]
        d.polygon(pts,fill='black')

    im,d=canvas('ACCESS CARD', (640,400)); text(d,(120,150),'R7K2',80)
    save(im,'easy_ocr','easy','Read the access code. Return JSON with string key code.',{'code':'R7K2'})

    im,d=canvas('OBJECTS', (800,400))
    d.rectangle((50,140,180,270),fill='blue'); d.polygon([(335,120),(260,270),(410,270)],fill='green'); d.ellipse((570,140,700,270),fill='red')
    save(im,'easy_spatial','easy','Name the colors of the leftmost and rightmost objects. Return JSON with lowercase string keys leftmost and rightmost.',{'leftmost':'blue','rightmost':'red'})

    im,d=canvas('COUNT THE SYMBOLS')
    circles=[(80,120),(270,150),(520,110),(130,400),(400,450),(700,400)]
    for x,y in circles: d.ellipse((x,y,x+70,y+70),fill='orange')
    for x,y in [(690,130),(320,320),(590,510)]: d.rectangle((x,y,x+70,y+70),fill='orange')
    for x,y in [(60,560),(740,570),(470,270)]: d.ellipse((x,y,x+70,y+70),fill='blue')
    save(im,'easy_count','easy','Count only the orange circles. Return JSON with integer key count.',{'count':len(circles)})

    im,d=canvas('UNITS SOLD')
    values=[30,70,50,20]; labels=['A','B','C','D']
    for val in range(0,81,10):
        y=570-val*5; d.line((110,y,820,y),fill='#cccccc',width=1); text(d,(45,y-12),val,22)
    for i,(label,val) in enumerate(zip(labels,values)):
        x=165+i*165; d.rectangle((x,570-val*5,x+80,570),fill='#326db3'); text(d,(x+30,590),label)
    save(im,'medium_chart','medium','Read the chart. Return JSON: highest (category string), highest_value (integer), gap (highest minus lowest, integer).',{'highest':labels[values.index(max(values))],'highest_value':max(values),'gap':max(values)-min(values)})

    im,d=canvas('STOCK CHECK')
    rows=[('P01','Washers',17,20,'C2'),('P02','Bolts',42,30,'A1'),('P03','Clips',8,12,'B4'),('P04','Nuts',25,25,'C3'),('P05','Pins',4,10,'A2'),('P06','Rivets',60,40,'D1')]
    xs=[35,170,390,530,710]
    for x,h in zip(xs,['ID','Item','Stock','Minimum','Bin']): text(d,(x,100),h)
    for i,row in enumerate(rows):
        y=160+i*70; d.line((25,y-12,870,y-12),fill='#999999')
        for x,value in zip(xs,row): text(d,(x,y),value)
    save(im,'medium_table','medium','Return JSON: restock_ids (IDs with Stock strictly below Minimum, in displayed order), washers_bin (string), bolts_stock (integer).',{'restock_ids':[r[0] for r in rows if r[2]<r[3]],'washers_bin':rows[0][4],'bolts_stock':rows[1][2]})

    im,d=canvas('FAN CONTROLLER')
    text(d,(280,85),'INPUT: temperature = 28',24)
    d.polygon([(450,170),(620,260),(450,350),(280,260)],outline='black',width=3)
    text(d,(330,240),'Temperature > 25?',22)
    arrow(d,(280,260),(150,450)); text(d,(185,315),'NO',24)
    arrow(d,(620,260),(750,450)); text(d,(685,315),'YES',24)
    d.rectangle((50,450,280,535),outline='black',width=3); text(d,(75,475),'FAN LOW',28)
    d.rectangle((620,450,855,535),outline='black',width=3); text(d,(645,475),'FAN HIGH',28)
    save(im,'medium_flow','medium','Follow the displayed input through the diagram. Return JSON with destination equal to the exact output-box text.',{'destination':'FAN HIGH'})

    im,d=canvas('QUALITY RELEASE LEDGER',(1000,1080))
    headers=['Batch','Units','Rejected','Status']; xs=[40,245,460,690]
    for x,h in zip(xs,headers): text(d,(x,90),h,25)
    ledger=[]
    for i in range(18):
        row=(f'L{i+1:02}',40+i*3,i%5,'HOLD' if i%4==0 else 'RELEASE'); ledger.append(row)
        y=150+i*47
        if i%2==0: d.rectangle((25,y-5,970,y+37),fill='#eeeeee')
        for x,value in zip(xs,row): text(d,(x,y),value,22)
    save(im,'hard_ledger','hard','Using only RELEASE rows, sum Units minus Rejected. Also identify all batches (including HOLD) tied for most rejected units, in displayed order, and read Units for L14. Return JSON: released_net_units (integer), most_rejected_batches (list of strings), l14_units (integer).',{'released_net_units':sum(r[1]-r[2] for r in ledger if r[3]=='RELEASE'),'most_rejected_batches':[r[0] for r in ledger if r[2]==max(x[2] for x in ledger)],'l14_units':ledger[13][1]})

    im,d=canvas('PATCH-PANEL CONNECTIONS',(1000,780))
    text(d,(25,65),'Crossings are NOT junctions. Follow through the named middle terminals.',21)
    ys=[180,340,500,660]; mids=['W','X','Y','Z']; first=[2,0,3,1]; second=[3,1,0,2]
    for i in range(4):
        d.line((100,ys[i],475,ys[first[i]]),fill='black',width=3)
        d.line((525,ys[i],900,ys[second[i]]),fill='black',width=3)
    for i in range(4):
        for x,label in [(100,'ABCD'[i]),(500,mids[i]),(900,str(i+1))]:
            d.ellipse((x-25,ys[i]-25,x+25,ys[i]+25),fill='white',outline='black',width=3)
            text(d,(x-10,ys[i]-17),label,24)
    save(im,'hard_connections','hard','Trace each left input through its middle terminal to the numbered right output. Crossings are not junctions. Return JSON with integer keys A, B, C, D (key names are strings; values are integers).',{k:second[first[i]]+1 for i,k in enumerate('ABCD')})

    im,d=canvas('ONE-MACHINE JOB SCHEDULE',(1100,650))
    events=[('BUILD',0,45),('SYNC',30,60),('EVAL',75,120),('BACKUP',150,180)]
    startx=200; scale=4
    for minute in range(0,211,15):
        x=startx+minute*scale; d.line((x,140,x,550),fill='#dddddd')
        if minute%30==0: text(d,(x-20,105),f'{9+minute//60:02}:{minute%60:02}',18)
    for i,(name,start,end) in enumerate(events):
        y=190+i*85; text(d,(30,y),name,23); d.rectangle((startx+start*scale,y-5,startx+end*scale,y+45),fill='#487baa')
    text(d,(25,575),'Bars show occupied intervals; touching endpoints do not overlap.',22)
    overlaps=[[a[0],b[0]] for i,a in enumerate(events) for b in events[i+1:] if max(a[1],b[1])<min(a[2],b[2])]
    candidate=next(m for m in range(0,241,15) if all(m+45<=a or m>=b for _,a,b in events))
    save(im,'hard_schedule','hard','Which two jobs overlap? Give their names in row order. What is the earliest start time at or after 09:00 for a new uninterrupted 45-minute job, using 15-minute start increments? Return JSON: overlapping_jobs (two strings), earliest_start (HH:MM).',{'overlapping_jobs':overlaps[0],'earliest_start':f'{9+candidate//60:02}:{candidate%60:02}'})

    sheet=Image.new('RGB',(1200,1050),'#dddddd'); sd=ImageDraw.Draw(sheet)
    for i,t in enumerate(tasks):
        tile=Image.open(t['image']); tile.thumbnail((390,310)); x=(i%3)*400; y=(i//3)*350
        sheet.paste(tile,(x,y+30)); text(sd,(x+5,y+5),t['id'],18)
    sheet.save(directory/'contact-sheet.png')
    (directory/'manifest.json').write_text(json.dumps({'version':'synthetic-vision-v1','tasks':tasks},indent=2))
    return tasks
