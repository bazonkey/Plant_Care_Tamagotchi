from gpiozero import Button

button = Button(17)
count = 0
while count < 100:
    if button.is_pressed:
        print("Button is pressed")
    else:
        print("Button is not pressed")
        count += 1
