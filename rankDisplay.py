# importing image object from PIL
import io
import math 
from PIL import Image, ImageDraw, ImageFont

avatar_size = 128
diam = 34
x = 2.5*diam + avatar_size
w, h = 900, avatar_size + 2*diam
y = h-diam*1.25
length = w - x - diam*1.25


background = "#23272A"
grey = "#484B4E"
cian = "#62D3F5"



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

    def create_ebar(draw, x, y, length, diam, color):
        bar = [(x, y+diam/2), (x+length, y-diam/2)]
        draw.rectangle(bar, fill=color)
        draw.ellipse([bar[0][0]-diam/2, bar[0][1]-diam,
                      bar[0][0]+diam/2, bar[0][1]], fill=color)
        draw.ellipse([bar[1][0]-diam/2, bar[1][1],
                      bar[1][0]+diam/2, bar[1][1]+diam], fill=color)
        
    def create_earc(draw, x, y, length, diam):
        bar = [(x+length, y+diam/2), (x+length+diam/2, y-diam/2)]
        draw.arc(bar, 180, 0, 'black')

    def place_avatar(image, avatar, x, y, diam, avatar_size = avatar_size, circle=True):
        if not avatar:
            return
        avatar.seek(0)

        bck_image = Image.new('RGBA', (avatar_size, avatar_size))
        bck_draw = ImageDraw.Draw(bck_image)
        bck_draw.rectangle((0, 0, avatar_size, avatar_size), fill = background)
        
        img = Image.open(avatar)
        img = img.resize((avatar_size, avatar_size))
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

        
    # create progress bar background
    create_ebar(draw, x, y, length, diam+4, "black")
    create_ebar(draw, x, y, length, diam, grey)

    # create progress bar
    create_ebar(draw, x, y, length*user_points/max_points, diam, cian)

    # add avatars

    place_avatar(img, user_avatar, diam//2, diam//2, diam,
                 avatar_size = avatar_size + diam)
    place_avatar(img, guild_avatar, int(w-diam*1.5-avatar_size/2), diam//2, diam//2,
                 avatar_size = avatar_size//2+diam, circle=False)




    # save PNG in buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer
    


### get a font
##fnt = ImageFont.truetype("arial.ttf", 40)
### get a drawing context
##d = ImageDraw.Draw(base)
##
### draw text, half opacity
##d.text((10,10), "Hello", font=fnt, fill=(255,255,255,128))
### draw text, full opacity
##d.text((10,60), "World", font=fnt, fill=(255,255,255,255))
##
##out = Image.alpha_composite(base, d)

#img.show() 
