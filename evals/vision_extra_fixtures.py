"""Ten deterministic, uncalibrated visual-reasoning candidates (Pillow only).

All problem inputs and conventions are rendered into each individual image.
This module builds assets only: it never queries a model or starts a service.
"""
import argparse
import heapq
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
RENDER_AUDIT = []
MECHANICAL = dict(width=120, height=70, a_left=18, a_bottom=16, b_right=37, b_top=21)
MECHANICAL_SCALE = 5
GEOMETRY = dict(outline=[(0,0),(12,0),(12,5),(8,5),(8,9),(0,9)], holes=[(2,2,2,2),(5,5,2,3)], cm_per_cell=2)
ROADS = [('A','B',4,False),('B','C',6,False),('C','D',2,False),
         ('E','F',2,False),('F','G',1,True),('G','H',3,False),
         ('I','J',3,False),('J','K',2,True),('K','L',2,False),
         ('A','E',3,False),('B','F',4,False),('C','G',2,False),('D','H',7,False),
         ('E','I',6,False),('F','J',2,False),('G','K',5,False),('H','L',3,False)]
STACKS = {
    'North': [('ready',17),('quarantine',12),('allocated',18),('rejected',8)],
    'East': [('rejected',10),('allocated',12),('quarantine',8),('ready',23)],
    'South': [('quarantine',14),('ready',19),('rejected',7),('allocated',15)],
    'West': [('allocated',26),('rejected',6),('ready',16),('quarantine',9)],
}
CELLS = {
    'A1':'Item','B1':'Qty','C1':'Rate','D1':'Gross','E1':'Net',
    'A2':'Gear','B2':3,'C2':12,'D2':'=B2*C2','E2':'=D2-$B$6',
    'A3':'Plate','B3':5,'C3':9,'D3':'=B3*C3','E3':'=D3-$B$6',
    'A4':'Pin','B4':2,'C4':17,'D4':'=B4*C4','E4':'=D4-$B$6',
    'A5':'Totals','B5':'=SUM(B2:B4)','C5':'=IF(E5>90,B5,0)', 'D5':'=SUM(D2:D4)','E5':'=SUM(E2:E4)',
    'A6':'Fee','B6':4,'C6':'=E5-C3*B2','D6':'','E6':'',
}
NETWORK = [('A','B',False),('B','C',True),('C','D',False),
           ('E','F',False),('F','G',False),('G','H',True),
           ('A','E',False),('F','B',False),('C','G',False),('H','D',False)]
WAVES = {'CLK':[(0,0),(2,1),(4,0),(6,1),(8,0),(10,1),(12,0),(14,1),(16,0),(18,1),(20,0),(22,1),(24,0)],
         'RESET':[(0,1),(3,0),(14,1),(15,0)],
         'ENABLE':[(0,1),(7,0),(13,1),(19,0)],
         'D':[(0,0),(4,1),(10,0),(16,1),(22,0)]}
REAR_CODES = [('W','Q','T','P'),('U','R','S','V')]
DOCUMENT = [('R1','Alpha','Travel',120,'APPROVED'),('R2','Alpha','Meals',40,'APPROVED'),
            ('R3','Beta','Equipment',90,'APPROVED'),('R4','Gamma','Travel',80,'HOLD'),
            ('R5','Delta','Meals',60,'APPROVED'),('R6','Beta','Travel',50,'APPROVED'),
            ('R7','Gamma','Equipment',110,'APPROVED')]
TRACKING = [[(1,2),(2,3),(3,2),(4,4),(5,3)],
            [(2,2),(2,4),(3,3),(3,4),(4,3)],
            [(2,3),(1,4),(4,3),(2,4),(5,3)],
            [(3,3),(2,4),(4,4),(2,3),(5,2)]]


def text(draw, xy, value, size=24, fill='#172334', anchor=None):
    value = str(value)
    font = ImageFont.truetype(FONT, size)
    bbox = draw.textbbox(xy, value, font=font, anchor=anchor)
    canvas = draw._image.size
    if size < 18 or min(bbox[:2]) < 0 or bbox[2] > canvas[0] or bbox[3] > canvas[1]:
        raise ValueError(f'Text outside readable bounds: {value!r}, {bbox}, {canvas}')
    RENDER_AUDIT.append(dict(font_size=size, bbox=bbox, canvas=canvas))
    draw.text(xy, value, font=font, fill=fill, anchor=anchor)


def canvas(title, subtitle, size=(1400,1100)):
    im = Image.new('RGB', size, 'white')
    d = ImageDraw.Draw(im)
    d.rectangle((0,0,size[0],76), fill='#e9eff6')
    text(d,(32,20),title,32)
    text(d,(32,95),subtitle,23)
    return im,d


def lines(d, xy, strings, size=24, step=38):
    for i,s in enumerate(strings): text(d,(xy[0],xy[1]+i*step),s,size)


def arrow(d, a, b, fill='#26384e', width=4, both=False):
    d.line((a,b), fill=fill, width=width)
    for start,end in [(a,b)] + ([(b,a)] if both else []):
        angle = math.atan2(end[1]-start[1],end[0]-start[0])
        d.polygon([end]+[(end[0]-15*math.cos(angle+s),end[1]-15*math.sin(angle+s)) for s in (-.4,.4)], fill=fill)


def cross(d, p):
    x,y = p
    d.ellipse((x-21,y-21,x+21,y+21),fill='white')
    d.line((x-14,y-14,x+14,y+14),fill='#b32330',width=6)
    d.line((x-14,y+14,x+14,y-14),fill='#b32330',width=6)


def mechanical_point(u,v):
    angle = math.radians(25)
    return (390+MECHANICAL_SCALE*(u*math.cos(angle)-v*math.sin(angle)),
            815-MECHANICAL_SCALE*(u*math.sin(angle)+v*math.cos(angle)))


def map_point(node):
    n = ord(node)-ord('A')
    return (190+(n%4)*320,290+(n//4)*280)


def shortest_route():
    queue = [(0,('A',),False)]
    while queue:
        cost,path,visited_f = heapq.heappop(queue)
        if path[-1] == 'L' and visited_f: return list(path),cost
        for a,b,w,blocked in ROADS:
            if blocked: continue
            n = b if path[-1] == a else a if path[-1] == b else None
            if n is not None and n not in path:
                heapq.heappush(queue,(cost+w,path+(n,),visited_f or n == 'F'))
    raise ValueError('No route')


def build_suite(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    RENDER_AUDIT.clear()
    tasks = []
    def save(im,ident,question,expected):
        path = directory/(ident+'.png')
        im.save(path)
        tasks.append(dict(id=ident,difficulty='hard',image=str(path),question=question,expected=expected))

    m = MECHANICAL
    im,d = canvas('01 / ROTATED MACHINED PLATE','All dimensions are in mm, measured along the local u and v axes.')
    point = mechanical_point
    d.polygon([point(0,0),point(m['width'],0),point(m['width'],m['height']),point(0,m['height'])],fill='#e6edf3',outline='#172334',width=4)
    a = (m['a_left'],m['a_bottom']); b = (m['width']-m['b_right'],m['height']-m['b_top'])
    for name,(u,v) in [('A',a),('B',b)]:
        x,y=point(u,v)
        d.ellipse((x-18,y-18,x+18,y+18),fill='white',outline='#172334',width=3)
        d.line((x-25,y,x+25,y),fill='#172334',width=2)
        d.line((x,y-25,x,y+25),fill='#172334',width=2)
        text(d,(x+25,y-12),name,28)
    def dim(p,q,label,offset=(0,0)):
        pp,qq=point(*p),point(*q)
        arrow(d,pp,qq,width=2,both=True)
        x=(pp[0]+qq[0])/2+offset[0];y=(pp[1]+qq[1])/2+offset[1]
        box=d.textbbox((x,y),str(label),font=ImageFont.truetype(FONT,24),anchor='mm')
        d.rectangle((box[0]-6,box[1]-4,box[2]+6,box[3]+4),fill='white')
        text(d,(x,y),label,24,anchor='mm')
    def extension(p,q): d.line((point(*p),point(*q)),fill='#728096',width=2)
    for u in (0,m['width']): extension((u,0),(u,-25))
    dim((0,-22),(m['width'],-22),m['width'])
    for v in (0,m['height']): extension((0,v),(-24,v))
    dim((-21,0),(-21,m['height']),m['height'])
    extension((a[0],a[1]),(a[0],-11)); dim((0,-9),(a[0],-9),m['a_left'])
    extension(a,(-9,a[1])); dim((-8,0),(-8,a[1]),m['a_bottom'],(-18,0))
    extension(b,(b[0],m['height']+13)); extension((m['width'],m['height']),(m['width'],m['height']+13))
    dim((b[0],m['height']+10),(m['width'],m['height']+10),m['b_right'])
    extension(b,(m['width']+15,b[1])); extension((m['width'],m['height']),(m['width']+15,m['height']))
    dim((m['width']+12,b[1]),(m['width']+12,m['height']),m['b_top'])
    arrow(d,point(126,0),point(147,0)); text(d,point(150,0),'+u',26)
    arrow(d,point(0,77),point(0,96)); text(d,point(0,102),'+v',26)
    lines(d,(32,980),['Find the positive u and v center offsets from A to B.',
                         'Also find the squared straight-line center distance. Hole radii are irrelevant.'],23)
    du,dv=b[0]-a[0],b[1]-a[1]
    save(im,'extra01_rotated_dimensions','Solve the pictured dimension problem. Return JSON with integer fields du_mm, dv_mm, distance_squared_mm2.',dict(du_mm=du,dv_mm=dv,distance_squared_mm2=du*du+dv*dv))

    im,d=canvas('02 / CUT PLATE ON A SQUARE GRID','Each grid square is 2 cm by 2 cm. Heavy lines are physical boundaries.')
    origin=(250,830); step=65
    def gp(p):return (origin[0]+p[0]*step,origin[1]-p[1]*step)
    d.polygon([gp(p) for p in GEOMETRY['outline']],fill='#a9d8d4')
    for x in range(13):d.line((gp((x,0)),gp((x,9))),fill='#b8c3cd',width=1)
    for y in range(10):d.line((gp((0,y)),gp((12,y))),fill='#b8c3cd',width=1)
    d.line([gp(p) for p in GEOMETRY['outline']+[GEOMETRY['outline'][0]]],fill='#172334',width=4)
    for x,y,w,h in GEOMETRY['holes']:
        d.rectangle((gp((x,y+h)),gp((x+w,y))),fill='white',outline='#172334',width=4)
        text(d,gp((x+w/2,y+h/2)),'VOID',20,anchor='mm')
    for x in range(13):text(d,(gp((x,0))[0],858),x,20,anchor='mm')
    for y in range(10):text(d,(222,gp((0,y))[1]),y,20,anchor='mm')
    text(d,(1090,855),'grid x',22);text(d,(130,230),'grid y',22)
    lines(d,(32,925),['The white interior rectangles are through-holes; the upper-right notch is exterior.',
                         'Find material area and total boundary length, including all hole edges.',
                         'Grid numbers count squares, not centimeters. Count enclosed holes too.'],24)
    poly=GEOMETRY['outline']
    outer_area=abs(sum(x*v-u*y for (x,y),(u,v) in zip(poly,poly[1:]+poly[:1])))//2
    outer_length=sum(abs(x-u)+abs(y-v) for (x,y),(u,v) in zip(poly,poly[1:]+poly[:1]))
    holes=GEOMETRY['holes']; scale=GEOMETRY['cm_per_cell']
    save(im,'extra02_scaled_plate_holes','Solve the pictured plate problem. Return JSON with integer fields area_cm2, all_boundary_cm, hole_count.',
         dict(area_cm2=(outer_area-sum(w*h for _,_,w,h in holes))*scale**2,all_boundary_cm=(outer_length+sum(2*(w+h) for _,_,w,h in holes))*scale,hole_count=len(holes)))

    im,d=canvas('03 / ROAD CLOSURES AND A REQUIRED STOP','Find the minimum-cost route from A to L that visits F. Do not repeat a node.')
    text(d,(32,140),'Roads are two-way. Numbers are costs. A red X closes the entire road.',23)
    for a,b,cost,blocked in ROADS:
        p,q=map_point(a),map_point(b);d.line((p,q),fill='#a2adbb' if blocked else '#24384e',width=6)
        mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
        if blocked: cross(d,(mx,my))
        pos=(mx,my-35) if p[1]==q[1] else (mx+38,my)
        d.rectangle((pos[0]-18,pos[1]-17,pos[0]+18,pos[1]+17),fill='white')
        text(d,pos,cost,25,anchor='mm')
    for node in 'ABCDEFGHIJKL':
        x,y=map_point(node);d.ellipse((x-32,y-32,x+32,y+32),fill='#fff0be' if node in 'AFL' else 'white',outline='#172334',width=3)
        text(d,(x,y),node,28,anchor='mm')
    text(d,(32,1000),'Return every visited node in travel order, including A and L, and the sum of road costs.',23)
    route,cost=shortest_route()
    save(im,'extra03_closed_road_route','Solve the pictured route problem. Return JSON with route (list of node strings in travel order) and cost (integer).',dict(route=route,cost=cost))

    im,d=canvas('04 / INVENTORY STACKS WITH A SHARED LEGEND','Segment labels give exact item counts. Stack order varies by site.')
    colors={'allocated':'#9fbbe2','ready':'#9ed6be','quarantine':'#f5d193','rejected':'#c7b6da'}
    patterns={'allocated':'/','ready':'o','quarantine':'|','rejected':'x'}
    def segment(box,kind,value=None):
        x0,y0,x1,y1=box;d.rectangle(box,fill=colors[kind],outline='#24384e',width=2)
        # The large repeated symbols provide a redundant legend cue.
        text(d,(x0+15,(y0+y1)/2),patterns[kind],20,anchor='lm')
        if value is not None:text(d,((x0+x1)/2,(y0+y1)/2),value,26,anchor='mm')
    for i,kind in enumerate(colors):
        x=40+i*340;segment((x,175,x+66,227),kind);text(d,(x+78,186),kind,23)
    for i,(site,segs) in enumerate(STACKS.items()):
        x=165+310*i;y=810
        for kind,value in segs:
            height=value*8;segment((x,y-height,x+170,y),kind,value);y-=height
        text(d,(x+85,845),site,28,anchor='mm')
    lines(d,(32,915),['Usable items = allocated + ready. Exclude quarantine and rejected from usable.',
                         'Find the site with most usable items, usable items across all sites,',
                         'and quarantined items across all sites. Use the exact site spelling.'],24)
    usable={site:sum(v for k,v in segs if k in ('allocated','ready')) for site,segs in STACKS.items()}
    save(im,'extra04_permuted_stack_legend','Solve the pictured inventory problem. Return JSON with highest_usable (string), total_usable (integer), quarantine_total (integer).',dict(highest_usable=max(usable,key=usable.get),total_usable=sum(usable.values()),quarantine_total=sum(v for segs in STACKS.values() for k,v in segs if k=='quarantine')))

    im,d=canvas('05 / SPREADSHEET FORMULA VIEW','Evaluate D4, E5 and C6 using the pictured cell contents.')
    left,top,cw,rh=100,250,250,87
    for c,col in enumerate('ABCDE'):text(d,(left+c*cw+cw/2,top-37),col,28,anchor='mm')
    for row in range(1,7):
        text(d,(60,top+(row-.5)*rh),row,28,anchor='mm')
        for c,col in enumerate('ABCDE'):
            box=(left+c*cw,top+(row-1)*rh,left+(c+1)*cw,top+row*rh)
            d.rectangle(box,fill='#e8eff6' if row==1 else '#fff4d3' if col+str(row) in ('D4','E5','C6') else 'white',outline='#718197',width=2)
            text(d,(box[0]+10,box[1]+30),CELLS[col+str(row)],20)
    lines(d,(32,860),['Rules: evaluate formulas recursively; * multiplies; + and - add and subtract.',
                         'A reference uses its column letter and row number. $ fixes a reference when copied.',
                         'SUM(X:Y) includes both endpoints. IF(test,a,b) chooses a if true, otherwise b.',
                         'Use the formulas exactly as displayed; no formulas are being copied.'],23)
    gross=[CELLS[f'B{r}']*CELLS[f'C{r}'] for r in (2,3,4)]
    net=sum(v-CELLS['B6'] for v in gross)
    save(im,'extra05_formula_cell_binding','Evaluate the requested pictured cells. Return JSON with integer fields D4, E5, C6.',{'D4':gross[2],'E5':net,'C6':net-CELLS['C3']*CELLS['B2']})

    im,d=canvas('06 / DIRECTED NETWORK AFTER LINK FAILURES','Start at A. Follow arrowheads only. Red X links have failed and cannot be used.')
    pos={n:(190+(i%4)*320,350+(i//4)*370) for i,n in enumerate('ABCDEFGH')}
    for a,b,failed in NETWORK:
        p,q=pos[a],pos[b];length=math.dist(p,q);vx=(q[0]-p[0])/length;vy=(q[1]-p[1])/length
        arrow(d,(p[0]+37*vx,p[1]+37*vy),(q[0]-37*vx,q[1]-37*vy),fill='#b32330' if failed else '#24384e',width=5)
        if failed:cross(d,((p[0]+q[0])/2,(p[1]+q[1])/2))
    for node,(x,y) in pos.items():
        d.ellipse((x-36,y-36,x+36,y+36),fill='#fff0be' if node=='A' else '#e8eff6',outline='#172334',width=3)
        text(d,(x,y),node,28,anchor='mm')
    lines(d,(32,885),['List all reachable nodes except A, sorted alphabetically.',
                         'Also find the fewest working directed links needed to reach G.',
                         'Only the eight circular nodes are junctions; there are no hidden links.'],24)
    distance={'A':0};front=['A']
    while front:
        n=front.pop(0)
        for a,b,failed in NETWORK:
            if a==n and not failed and b not in distance:distance[b]=distance[a]+1;front.append(b)
    save(im,'extra06_failed_directed_links','Solve the pictured network problem. Return JSON with reachable (alphabetically sorted list of strings) and min_edges_to_G (integer).',dict(reachable=sorted(set(distance)-{'A'}),min_edges_to_G=distance['G']))

    im,d=canvas('07 / SYNCHRONOUS REGISTER TIMING','Sample only at the marked rising CLK edges. Time unit: ns.',(1500,1200))
    lines(d,(32,145),['Initial Q = 1. At each rising edge: RESET=1 sets Q=0; otherwise ENABLE=1 sets Q=D;',
                         'otherwise Q holds. RESET is synchronous and has priority over ENABLE.',
                         'At coincident transitions, use signal levels just AFTER the transition at that time.'],23)
    x0=205;scale=49
    for t in range(25):
        x=x0+t*scale;d.line((x,335,x,930),fill='#dce2e9',width=1)
        text(d,(x,310),t,18,anchor='mm')
    for t in (2,6,10,14,18,22):
        x=x0+t*scale;d.line((x,330,x,938),fill='#bb5555',width=2)
        d.polygon([(x-8,328),(x+8,328),(x,341)],fill='#bb5555')
    for i,(name,events) in enumerate(WAVES.items()):
        low=445+i*145; high=low-70
        text(d,(28,high+20),name,24)
        text(d,(172,high),'1',18,anchor='mm');text(d,(172,low),'0',18,anchor='mm')
        pts=[]
        for j,(t,value) in enumerate(events):
            x=x0+t*scale;y=low-70*value
            if j:pts.append((x,low-70*events[j-1][1]))
            pts.append((x,y))
        pts.append((x0+24*scale,low-70*events[-1][1]))
        d.line(pts,fill='#173e69',width=4)
    lines(d,(32,1000),['Read Q just after each marked edge from left to right as one six-character bit string.',
                          'Count Q transitions from 0 to 1 at those edges. Include the initial Q in transition checks.',
                          'Intervals are left-inclusive and right-exclusive; vertical transitions occur at exact grid times.'],23)
    def level(name,t):return next(v for start,v in reversed(WAVES[name]) if start<=t)
    q=1;bits='';rises=0
    for t in [t for t,v in WAVES['CLK'] if v==1]:
        prev=q
        if level('RESET',t):q=0
        elif level('ENABLE',t):q=level('D',t)
        rises+=int(prev==0 and q==1);bits+=str(q)
    save(im,'extra07_clock_edge_binding','Solve the pictured register timing problem. Return JSON with q_after_edges (bit string), q_rises (integer), final_q (integer).',dict(q_after_edges=bits,q_rises=rises,final_q=q))

    im,d=canvas('08 / CONNECTOR FRONT AND REAR VIEWS','Both views show the SAME connector with its key at the top. No vertical flip.')
    text(d,(32,145),'Rear view is viewed from the wire-entry side, opposite the front mating face.',23)
    for side,left in [('FRONT / mating face',80),('REAR / wire-entry face',780)]:
        text(d,(left+250,245),side,26,anchor='mm')
        d.rounded_rectangle((left,310,left+540,655),radius=24,fill='#edf1f6',outline='#172334',width=4)
        d.rectangle((left+215,282,left+325,318),fill='#f3cd76',outline='#172334',width=3)
        text(d,(left+270,297),'KEY',19,anchor='mm')
        for r in range(2):
            for c in range(4):
                x=left+78+c*128;y=410+r*150
                d.ellipse((x-35,y-35,x+35,y+35),fill='white',outline='#172334',width=3)
                label=4*r+c+1 if left==80 else REAR_CODES[r][c]
                text(d,(x,y),label,29,anchor='mm')
    lines(d,(50,720),['Front pin assignments:', 'TX = pin 2       RX = pin 7       GND = pin 5'],27,45)
    lines(d,(50,850),['Rear letters are unique wire codes, not pin numbers.',
                         'Match each signal to its rear wire code; also identify the front pin number',
                         'at the top-left position of the rear view. Preserve uppercase wire letters.'],24)
    wire=lambda pin:REAR_CODES[(pin-1)//4][3-(pin-1)%4]
    save(im,'extra08_connector_view_reflection','Solve the pictured connector mapping. Return JSON with TX_wire, RX_wire, GND_wire (strings) and rear_top_left_pin (integer).',dict(TX_wire=wire(2),RX_wire=wire(7),GND_wire=wire(5),rear_top_left_pin=4))

    im,d=canvas('09 / REIMBURSEMENT MEMO WITH EXCLUSIONS','Apply the numbered footnotes before totaling reimbursements. All amounts are USD.',(1400,1200))
    xs=[45,180,405,720,920];headers=['Row','Project','Category / note','Claim','Status']
    for x,h in zip(xs,headers):text(d,(x,190),h,25)
    note={'Travel':1,'Meals':2,'Equipment':3}
    for i,(ident,project,kind,amount,status) in enumerate(DOCUMENT):
        y=255+i*68
        d.rectangle((32,y-8,1368,y+47),fill='#eef2f7' if i%2==0 else 'white')
        for x,value in zip(xs,[ident,project,f'{kind} [{note[kind]}]',amount,status]):text(d,(x,y),value,25)
    lines(d,(40,780),['General rule: only APPROVED rows can qualify. HOLD rows receive nothing.',
                         '[1] Travel: reimburse 75% of the claim, except Beta travel is excluded.',
                         '[2] Meals: reimburse the smaller of the claim and $30; Delta meals are excluded.',
                         '[3] Equipment: reimburse 50% of the claim for Gamma only; all other projects excluded.',
                         'An eligible row passes the general rule and its category rule.',
                         'Return eligible row IDs in displayed order, total reimbursement, and excluded row count.'],23,51)
    eligible=[];total=0
    rates={'Travel':lambda amount:amount*75//100,'Meals':lambda amount:min(amount,30),'Equipment':lambda amount:amount//2}
    for ident,project,kind,amount,status in DOCUMENT:
        qualifies=status=='APPROVED' and {'Travel':project!='Beta','Meals':project!='Delta','Equipment':project=='Gamma'}[kind]
        if qualifies:eligible.append(ident);total+=rates[kind](amount)
    save(im,'extra09_footnote_exclusions','Apply the pictured memo. Return JSON with eligible_rows (list of row-ID strings in displayed order), reimbursement_usd (integer), excluded_count (integer).',dict(eligible_rows=eligible,reimbursement_usd=total,excluded_count=len(DOCUMENT)-len(eligible)))

    im,d=canvas('10 / IDENTICAL TOKENS ACROSS FOUR FRAMES','Each token moves EXACTLY one cell up, down, left or right between consecutive frames.',(1400,1400))
    lines(d,(32,138),['No diagonal moves, stays, new tokens or lost tokens. One token per cell at each frame.',
                         'Labels appear only in frame 1. Infer identities from all five tokens together.'],23)
    for frame_index,frame in enumerate(TRACKING):
        left=180+(frame_index%2)*680;top=315+(frame_index//2)*495;step=74
        text(d,(left+185,top-83),f'FRAME {frame_index+1}',28,anchor='mm')
        for c in range(5):text(d,(left+(c+.5)*step,top-27),'ABCDE'[c],23,anchor='mm')
        for r in range(5):text(d,(left-27,top+(r+.5)*step),r+1,23,anchor='mm')
        for i in range(6):
            d.line((left+i*step,top,left+i*step,top+5*step),fill='#7c8a9c',width=2)
            d.line((left,top+i*step,left+5*step,top+i*step),fill='#7c8a9c',width=2)
        for j,(col,row) in enumerate(frame):
            x=left+(col-.5)*step;y=top+(row-.5)*step
            d.ellipse((x-25,y-25,x+25,y+25),fill='#d5c3ed',outline='#38204c',width=3)
            if frame_index==0:text(d,(x,y),'PQRST'[j],23,anchor='mm')
    lines(d,(32,1250),['In frame 4, find the cells containing P, R and T, and identify the token at cell B3.',
                          'Cell format: uppercase column letter followed by row digit (for example, A1).'],24)
    cell=lambda p:'ABCDE'[p[0]-1]+str(p[1])
    final=TRACKING[-1]
    save(im,'extra10_sequential_token_tracking','Solve the pictured tracking problem. Return JSON with string fields P_cell, R_cell, T_cell, token_at_B3.',dict(P_cell=cell(final[0]),R_cell=cell(final[2]),T_cell=cell(final[4]),token_at_B3='PQRST'[final.index((2,3))]))

    # The contact sheet is an overview; source task images retain full-size text.
    sheet=Image.new('RGB',(1600,1400),'#dce2e9');sd=ImageDraw.Draw(sheet)
    for i,task in enumerate(tasks):
        x=(i%5)*320;y=(i//5)*700
        text(sd,(x+12,y+18),task['id'].split('_')[0],24)
        title=task['id'].split('_',1)[1].replace('_',' ')
        words=title.split(); current=''; wrapped=[]
        for word in words:
            if len(current+' '+word)>23:wrapped.append(current);current=word
            else:current=(current+' '+word).strip()
        wrapped.append(current)
        lines(sd,(x+12,y+57),wrapped,18,26)
        with Image.open(task['image']) as tile:
            tile.thumbnail((306,535),Image.Resampling.LANCZOS)
            sheet.paste(tile,(x+(320-tile.width)//2,y+140))
    sheet.save(directory/'contact-sheet.png')
    (directory/'manifest.json').write_text(json.dumps({'version':'synthetic-vision-candidates-extra10-v1','tasks':tasks},indent=2)+'\n')
    return tasks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'fixtures'/'vision-candidates-extra10')
    args=parser.parse_args()
    tasks=build_suite(args.output)
    print(f'Built {len(tasks)} candidate tasks in {args.output.resolve()}')
