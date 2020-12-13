# importing image object from PIL
import io
import math 
from PIL import Image, ImageDraw, ImageFont

avatar_size = 128
diam = 20
x = 1*diam + avatar_size
w, h = 600, avatar_size + diam
y = h-diam*1.25
length = w - x - diam*1.25
d = 5

g_a_s = int(y-diam/2-diam) # guild avatar size


background = "#23272A"
grey = "#484B4E"
grey_text = "#808486"
cian = "#62D3F5"


def create_ebar(draw, x, y, length, diam, color):
    bar = [(x, y+diam/2), (x+length, y-diam/2)]
    draw.rectangle(bar, fill=color)
    draw.ellipse([bar[0][0]-diam/2, bar[0][1]-diam,
                  bar[0][0]+diam/2, bar[0][1]], fill=color)
    draw.ellipse([bar[1][0]-diam/2, bar[1][1],
                  bar[1][0]+diam/2, bar[1][1]+diam], fill=color)

def place_avatar(image, avatar, x, y, diam, avatar_size = avatar_size, circle=True):
    if not avatar:
        return
    avatar.seek(0)

    bck_image = Image.new('RGBA', (avatar_size, avatar_size))
    bck_draw = ImageDraw.Draw(bck_image)
    bck_draw.rectangle((0, 0, avatar_size, avatar_size), fill = background)
    
    img = Image.open(avatar)
    img = img.resize((avatar_size, avatar_size), Image.ANTIALIAS)
    try:
        # workaround for transparency
        img = Image.alpha_composite(bck_image, img)
    except:
        ...
    
    mask_image = Image.new('L', (avatar_size, avatar_size))
    mask_draw = ImageDraw.Draw(mask_image)
    if circle:
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill = 255)
    else:
        d = diam/2
        x0 = d
        y0 = d
        x1 = avatar_size - x0
        y1 = avatar_size - y0
        mask_draw.ellipse((x0-d, y0-d, x0+d, y0+d), fill = 255)
        mask_draw.ellipse((x1-d, y0-d, x1+d, y0+d), fill = 255)
        mask_draw.ellipse((x0-d, y1-d, x0+d, y1+d), fill = 255)
        mask_draw.ellipse((x1-d, y1-d, x1+d, y1+d), fill = 255)
        mask_draw.rectangle((x0-d, y0, x1+d, y1), fill = 255)
        mask_draw.rectangle((x0, y0-d, x1, y1+d), fill = 255)

    image.paste(img, (x, y), mask_image)

def create_rank_card(user_avatar,
                     guild_avatar,
                     user_name,
                     user_discriminator,
                     user_points,
                     max_points,
                     rank,
                     members):
    # creating new Image object 
    img = Image.new("RGB", (w, h)) 

    # create rectangle background 
    draw = ImageDraw.Draw(img) 
    draw.rectangle([(0, 0), (w, h)], fill =background)

   
    # create progress bar background
    create_ebar(draw, x, y, length, diam+4, "black")
    create_ebar(draw, x, y, length, diam, grey)

    # create progress bar
    create_ebar(draw, x, y, length*user_points/max_points, diam, cian)

    # add avatars

    place_avatar(img, user_avatar, diam//2, diam//2, diam,
                 avatar_size = avatar_size)
    place_avatar(img, guild_avatar, int(w-diam/2-g_a_s), diam//2, diam,
                 avatar_size = g_a_s, circle=False)


    ## add text
    # add discriminator
    draw = ImageDraw.Draw(img) 
    font = ImageFont.truetype('Roboto-Medium.ttf', 20)
    text = '#' + str(user_discriminator)
    tdw, tdh = draw.textsize(text, font=font)
    draw.text((avatar_size+diam, int(g_a_s + diam/2-tdh)), text,
              fill = grey_text, font = font)

    # add points
    draw = ImageDraw.Draw(img) 
    font = ImageFont.truetype('Roboto-Italic.ttf', 20)
    text = f'points: {user_points} / {max_points}'
    tpw, tph = draw.textsize(text, font=font)
    draw.text((int(w-diam-g_a_s-tpw), int(g_a_s + diam/2-tdh)), text,
              fill = grey_text, font = font)

    # add rank
    draw = ImageDraw.Draw(img) 
    font = ImageFont.truetype('Roboto-Medium.ttf', 20)
    text = " / " + str(members)
    trw, trh = draw.textsize(text, font=font)
    draw.text((int(w-diam-g_a_s-trw), int(g_a_s + diam/2-tph-trh-d)), text,
              fill = "white", font = font)

    
    draw = ImageDraw.Draw(img) 
    font = ImageFont.truetype('Roboto-Medium.ttf', 40, encoding="utf-8")
    text = " #" + str(rank)
    trrw, trrh = draw.textsize(text, font=font)
    draw.text((int(w-diam-g_a_s-trw-trrw), int(g_a_s + diam/2-tph-trrh-d)), text,
              fill = "white", font = font)

    # add user
    text = str(user_name)

    size_w = int(w-diam*2-g_a_s-trw-trrw - (avatar_size))
    draw = ImageDraw.Draw(img)
    f_size = 40
    
    while f_size > 21:
        font = ImageFont.truetype('Roboto-Medium.ttf', f_size, encoding="utf-8")
        tuw, tuh = draw.textsize(text, font=font)
        if tuw <= size_w:
            break
        f_size -= 1

    if tuw > size_w:
        text += '...'
        
    while tuw > size_w:
        text=text[:-4]
        text += '...'
        tuw, tuh = draw.textsize(text, font=font)
        
    draw.text((avatar_size+diam, int(g_a_s + diam/2-tdh-tuh-d)), text,
              fill = "white", font = font)

    # save PNG in buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

def create_activity_card(players, dMaxPoints):
    if (not players) or (not dMaxPoints):
        return
    avatar_size = 64
    step = 68
    dy = 1
    dx = 1
    w = 800
    h = step * len(players)
    min_trans = 20
    fontM = ImageFont.truetype('Roboto-Medium.ttf', 28, encoding="utf-8")
    
    # creating new Image object 
    img = Image.new("RGBA", (w, h)) 

    # create rectangle background
    draw = ImageDraw.Draw(img) 
    draw.rectangle([(0, 0), (w, h)], fill=background)

    # transparent image for rectangles
    rect = Image.new("RGBA", (w, h))
    drw = ImageDraw.Draw(rect)

    # find max values
    max_w = max(draw.textsize(' ' + str(p.get('iRank'))+'.', font=fontM)[0] for p in players)
    rest_w = w - max_w - step
    act_w = rest_w // (len(dMaxPoints) + 1)
    real_w = act_w * (len(dMaxPoints) + 1) + max_w + step

    
    # add table
    for i, p in enumerate(players):
        # add nr
        nr = ' ' + str(p.get('iRank'))+'.'
        t_w, t_h = draw.textsize(nr, font=fontM)
        draw.text((max_w-t_w, (step-t_h)//2 + step*i), nr,
                  fill = "white", font = fontM)

        # add avatar
        place_avatar(img, p.get('avatar'), max_w + (step-avatar_size)//2,
                     (step-avatar_size)//2 + i * step, diam,
                     avatar_size = avatar_size, circle=True)

        # add bars
        for j, (ch, points) in enumerate(p.get('aSubmissions')):
            big_coord = [(max_w+step+j*act_w, step*i),
                         (max_w+step+(j+1)*act_w, step*(i+1))]
            coord = [(max_w+step+j*act_w+dx, step*i+dy),
                     (max_w+step+(j+1)*act_w-dx, step*(i+1)-dy)]
            drw.rectangle(big_coord, fill=grey)
            drw.rectangle(coord, fill=background)
            transp = hex(int(min_trans + points / (dMaxPoints.get(ch) or points or 1) * (255 - min_trans)))[2:]
            if points:
                drw.rectangle(coord, fill=cian+transp)
                
    img = Image.alpha_composite(img, rect)
    img = img.crop((0, 0, real_w+1, h+1))
    
    # save PNG in buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def create_top_card(the_top):
    if not the_top:
        return
    step = 72
    diam = 20
    avatar_size = 64
    bar = 500
    
    w, h = 700, 700

    fontB = ImageFont.truetype('Roboto-Medium.ttf', 36, encoding="utf-8")
    fontM = ImageFont.truetype('Roboto-Medium.ttf', 28, encoding="utf-8")
    fontS = ImageFont.truetype('Roboto-Medium.ttf', 24, encoding="utf-8")
    # creating new Image object 
    img = Image.new("RGB", (w, h)) 

    # create rectangle background 
    draw = ImageDraw.Draw(img) 

    max_w = max(draw.textsize(' ' + str(p.get('iRank'))+'.', font=fontB)[0] for p in the_top)
    max_wp = max(draw.textsize(str(p.get('iPoints')), font=fontS)[0] for p in the_top)

    max_p = max(int(p.get('iPoints')) for p in the_top)

    w = max_w + step + diam + bar + diam + max_wp + diam//2
    user_w = w - max_w - step - diam
    h = step * len(the_top)
    
    # creating new Image object 
    img = Image.new("RGB", (w, h)) 

    # create rectangle background 
    draw = ImageDraw.Draw(img) 
    draw.rectangle([(0, 0), (w, h)], fill=background)

    # add table
    for i, p in enumerate(the_top):
        # add nr
        nr = ' ' + str(p.get('iRank'))+'.'
        t_w, t_h = draw.textsize(nr, font=fontB)
        draw.text((max_w-t_w, (step-t_h)//2 + step*i), nr,
                  fill = "white", font = fontB)

        # add avatar
        place_avatar(img, p.get('avatar'), max_w + (step-avatar_size)//2,
                     (step-avatar_size)//2 + i * step, diam,
                     avatar_size = avatar_size, circle=True)

        # add bar
        create_ebar (draw, max_w + step + diam, step * i + step * 3 / 4,
                     bar * int(p.get('iPoints')) / max_p, diam, cian)

        # add score
        t_w, t_h = draw.textsize(str(p.get('iPoints')), font=fontS)     
        draw.text((max_w + step + diam + bar * int(p.get('iPoints')) / max_p + diam,
                   int(step * i + step*3/4 - t_h/2)),
                   str(p.get('iPoints')), fill = grey_text, font = fontS)

        # add username & discriminator
        disc = ' #' + str(p.get('iDiscriminator'))
        name = str(p.get('sName'))
        d_w, d_h = draw.textsize(disc, font=fontS)
        u_w, u_h = draw.textsize(name, font=fontM)
        while u_w > user_w - d_w:
            name = name[:-4] + '...'
            u_w, u_h = draw.textsize(name, font=fontM)
        draw.text((max_w + step + diam, step*i + (step/2 - u_h)//2), name, fill="white", font=fontM)
        draw.text((max_w + step + diam + u_w, step*i + (step/2 + u_h)//2-d_h), disc, fill=grey_text, font=fontS)
        
    
    # save PNG in buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer
    
