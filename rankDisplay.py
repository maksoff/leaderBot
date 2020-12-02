# importing image object from PIL
import io
import math 
from PIL import Image, ImageDraw, ImageFont

w, h = 900, 300

background = "#23272A"
grey = "#484B4E"
cian = "#62D3F5"
diam = 34

avatar_size = 128

x = diam*2
y = h-diam*1.5
length = w - 2*x

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

    buffer = io.BytesIO()
        
    # create progress bar background
    create_ebar(draw, x, y, length, diam+4, "black")
    create_ebar(draw, x, y, length, diam, grey)

    # create progress bar
    create_ebar(draw, x, y, length*user_points/max_points, diam, cian)

    # save PNG in buffer
    img.save(buffer, format='PNG')    

    # move to beginning of buffer so `send()` it will read from beginning
    buffer.seek(0)

    return buffer
    

    avatar_asset = ctx.author.avatar_url_as(format='png', size=AVATAR_SIZE)

    # read JPG from server to buffer (file-like object)

#    buffer_avatar = io.BytesIO()
#    await avatar_asset.save(buffer_avatar)
#    buffer_avatar.seek(0)

    # read JPG from buffer to Image
    avatar_image = Image.open(user_avatar)

    # resize it
    avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE)) #

    circle_image = Image.new('L', (AVATAR_SIZE, AVATAR_SIZE))
    circle_draw = ImageDraw.Draw(circle_image)
    circle_draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
    #avatar_image.putalpha(circle_image)
    #avatar_image.show()

    image.paste(avatar_image, (rect_x0, rect_y0), circle_image)

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
