import os, random, sys
import pygame
from pygame.locals import *
import tracemalloc

# ----------------  OPCUA SERVER STUFF ----------------------------

import asyncio
from asyncua import Client, ua
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
import threading

SERVER_URL = "opc.tcp://100.90.187.71:4840/myopcua/server"
# SERVER_URL = "opc.tcp://100.100.12.80:4840/myopcua/server"
#
# CLIENT_CERT = "pki/own/certs/client_cert.der"
# CLIENT_KEY = "pki/own/private/client_key.pem"
# # SERVER_CERT = "pki/trusted/certs/server_cert.der"


# ----------------  END --------------- ----------------------------

# GLOBALS
img_dir = os.path.join(os.path.dirname(__file__), "Resources", "images")
WATER_MAX = 4095
FOOD_MAX = 65000
LIGHT_MAX = 100

# check for raspbi OS
if not sys.platform == 'win32':
    from gpiozero import Button
    os_type = 'raspbi'
    KEYDOWN = pygame.KEYDOWN
    A_BUTTON = pygame.K_a
    B_BUTTON = pygame.K_b
    C_BUTTON = pygame.K_c

    btn_a = Button(17)
    btn_b = Button(18)
    btn_c = Button(23)

    # queue keypress when GPIO buttons are pressed
    def press_a():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a))

    def press_b():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))

    def press_c():
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))

    btn_a.when_pressed = press_a
    btn_b.when_pressed = press_b
    btn_c.when_pressed = press_c

# if windows:
else:
    os_type = 'win32'
    KEYDOWN = pygame.KEYDOWN
    A_BUTTON = pygame.K_a # navigate
    B_BUTTON = pygame.K_b # select
    C_BUTTON = pygame.K_c # back

def load_image(name, colorkey=None, scale=1):
    fullname = os.path.join(img_dir, name)
    image = pygame.image.load(fullname)

    size = image.get_size()
    size = (size[0] * scale, size[1] * scale)
    image = pygame.transform.scale(image, size)

    if image.get_masks()[3]:
        image = image.convert_alpha()
    else:
        image = image.convert()
        if colorkey is not None:
            if colorkey == -1:
                colorkey = image.get_at((0, 0))
            image.set_colorkey(colorkey, pygame.RLEACCEL)

    return image, image.get_rect()

def get_font(size_ratio, screen_height):
    return pygame.font.Font(None, max(8, int(screen_height * size_ratio)))

def get_status(tama):
    lowest = min(tama.thirst, tama.vitality, tama.mood)
    if lowest < 25:
        return "Critical!"
    elif lowest < 50:
        return "Needs care"
    else:
        return "Doing well"

class Tama(pygame.sprite.Sprite):
    def __init__(self, sw, sh):
        pygame.sprite.Sprite.__init__(self)

        self.sw = sw
        self.sh = sh
        self.scale = sw / 160

        self.rect = pygame.Rect(0, 0, 0, 0)
        self.rect.midleft = (int(sw * 0.06), sh // 2 - 20)

        # stats
        self.thirst = 100
        self.vitality = 100
        self.mood = 100
        self.age = 0

        self.name = "Sprout"
        self.plant_type = "Fern"

        # --- state system ---
        self.state = "normal"          # normal / wilt
        self.flash_state = None        # e.g. "tama_joy"
        self.flash_until = 0

        self.current_sprite = None
        self._apply_sprite("tama")

    # ---------------------------
    # OPCUA DATA
    # ---------------------------
    def opc_update(self, water, nutrients, light, age):
        pass
        # self.thirst = ((2000-water) / WATER_MAX) * 100
        # self.vitality = max(0, nutrients / FOOD_MAX * 100)
        # self.mood = max(0, light / LIGHT_MAX * 100)
        # self.age = int(age)

    # ---------------------------
    #  CHANGE STATE
    # ---------------------------
    def status_update(self):
        if self.thirst < 25 and self.vitality < 25 and self.mood < 25:
            self.state = "wilt"
        elif min(self.thirst, self.vitality, self.mood) < 50:
            self.state = "wilt"
        else:
            self.state = "normal"

    def flash_sprite(self, img):
        self.flash_state = img
        self.flash_until = pygame.time.get_ticks() + 1000

    # ---------------------------
    # CENTRAL RESOLUTION
    # ---------------------------
    def resolve_sprite(self):
        now = pygame.time.get_ticks()

        # FLASH 1ST
        if self.flash_state:
            if now < self.flash_until:
                return self.flash_state
            else:
                self.flash_state = None

        # STATUS 2ND
        if self.state == "wilt":
            return "tama_wilt"

        return "tama"

    # ---------------------------
    # APPLY SPRITE IMG
    # ---------------------------
    def _apply_sprite(self, name):
        self.image, self.rect = load_image(name + ".png", None, .13 * self.scale)
        self.rect.midleft = (int(self.sw * 0.06), self.sh // 2 - 20)
        self.current_sprite = name

    # ---------------------------
    # FRAME UPDATE
    # ---------------------------
    def update(self):
        sprite_name = self.resolve_sprite()

        if sprite_name != self.current_sprite:
            self._apply_sprite(sprite_name)

class MenuScreen:
    def __init__(self, sw, sh):
        self.sw = sw
        self.sh = sh
        self.width = sw
        self.height = sh
        self.x = -sw
        self.target_x = -sw
        self.open = False
        self.speed = int(sw * 0.0625)
        self.icon = None
        self.font = None
        self.selected = 0

        panel_width = sw - int(sw * 0.453)
        self.surface = pygame.Surface((panel_width, sh), pygame.SRCALPHA)
        self._panel_width = panel_width

    def toggle(self):
        self.open = not self.open
        self.target_x = 0 if self.open else -self.width

    def handle_key(self, key):
        if not self.open:
            return None
        items_count = 3
        if key == A_BUTTON:
            self.toggle()
        elif key == B_BUTTON:
            self.selected = (self.selected + 1) % items_count
        elif key == C_BUTTON:
            return self.selected
        return None

    def update(self):
        if self.x < self.target_x:
            self.x = min(self.x + self.speed, self.target_x)
        elif self.x > self.target_x:
            self.x = max(self.x - self.speed, self.target_x)

    def draw(self, screen):
        if self.font is None:
            self.font = get_font(0.125, self.sh)
        if self.icon is None:
            icon_dim = int(self.font.size("A")[1] * 2)
            self.icon, _ = load_image("sprite.png", None, 1)
            self.icon = pygame.transform.scale(self.icon, (icon_dim, icon_dim))

        if self.x >= -self.width:
            self.surface.fill((50, 50, 50, 255))

            items = ["Water", "Garden", "Journal"]
            icon_size = self.icon.get_width()
            text_height = self.font.size("A")[1]
            item_height = max(icon_size, text_height)
            item_gap = int(self.sh * 0.067)
            padding_left = int(self._panel_width * 0.125)

            total_height = len(items) * item_height + (len(items) - 1) * item_gap
            start_y = (self.surface.get_height() - total_height) // 2

            for i, item in enumerate(items):
                y = start_y + i * (item_height + item_gap)
                is_selected = i == self.selected
                icon_y = y + (item_height - icon_size) // 2

                if is_selected:
                    self.surface.blit(self.icon, (padding_left, icon_y))
                else:
                    dimmed = self.icon.copy()
                    dimmed.fill((150, 150, 150, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    self.surface.blit(dimmed, (padding_left, icon_y))

                color = (255, 255, 255) if is_selected else (100, 100, 100)
                text = self.font.render(item, True, color)
                text_y = y + (item_height - text_height) // 2
                self.surface.blit(text, (padding_left + icon_size + int(self.sw * 0.03), text_y))

            screen.blit(self.surface, (self.x, 0))

class CareScreen:
    def __init__(self, sw, sh):
        self.sw = sw
        self.sh = sh
        self.width = sw
        self.height = sh
        self.x = sw
        self.target_x = sw
        self.open = False
        self.speed = int(sw * 0.0625)
        self.font = None
        self.surface = pygame.Surface((sw, sh))

    def show(self):
        self.open = True
        self.target_x = 0

    def hide(self):
        self.open = False
        self.target_x = self.width

    def handle_key(self, key, tama, app=None):
        if key == C_BUTTON:
            self.hide()

    def update(self):
        if self.x < self.target_x:
            self.x = min(self.x + self.speed, self.target_x)
        elif self.x > self.target_x:
            self.x = max(self.x - self.speed, self.target_x)

    def draw_content(self, surface, tama):
        pass

    def draw(self, screen, tama):
        if self.font is None:
            self.font = get_font(0.125, self.sh)
        if self.x < self.width:
            self.surface.fill((30, 30, 30))
            self.draw_content(self.surface, tama)
            screen.blit(self.surface, (self.x, 0))

class WaterScreen(CareScreen):
    def __init__(self, sw, sh):
        super().__init__(sw, sh)

    def draw_content(self, surface, tama):
        w, h = surface.get_size()
        bar_w = int(w * 0.625)
        bar_h = int(h * 0.083)
        margin_x = int(w * 0.0625)
        margin_y = int(h * 0.083)
        hint_pad = int(h * 0.167)

        title = self.font.render("Water", True, (100, 200, 255))
        surface.blit(title, (margin_x, margin_y))

        x = (w - bar_w) // 2
        y = h // 2 - bar_h // 2
        pygame.draw.rect(surface, (60, 60, 60), (x, y, bar_w, bar_h))
        pygame.draw.rect(surface, (100, 200, 255), (x, y, int(bar_w * tama.thirst / 100), bar_h))

        label = self.font.render(f"Water level: {int(tama.thirst)}%", True, (255, 255, 255))
        surface.blit(label, (x, y - int(h * 0.125)))

        hint = self.font.render("Press C to water", True, (150, 150, 150))
        surface.blit(hint, ((w - hint.get_width()) // 2, h - hint_pad))

    def handle_key(self, key, tama, app=None):
        super().handle_key(key, tama)
        if key == C_BUTTON:
            threading.Thread(
                target=app._run_opc_write,
                daemon=True,
                args=("Water", True, ua.VariantType.Boolean)
            ).start()

            print("SUCCESS: WATER")

            tama.flash_sprite("tama_joy")

class GardenScreen(CareScreen):
    def __init__(self, sw, sh):
        super().__init__(sw, sh)

    def draw_content(self, surface, tama):
        w, h = surface.get_size()
        bar_w = int(w * 0.625)
        bar_h = int(h * 0.083)
        margin_x = int(w * 0.0625)
        margin_y = int(h * 0.083)
        hint_pad = int(h * 0.167)

        title = self.font.render("Garden", True, (100, 255, 150))
        surface.blit(title, (margin_x, margin_y))

        x = (w - bar_w) // 2
        y = h // 2 - bar_h // 2
        pygame.draw.rect(surface, (60, 60, 60), (x, y, bar_w, bar_h))
        pygame.draw.rect(surface, (100, 255, 150), (x, y, int(bar_w * tama.vitality / 100), bar_h))

        label = self.font.render(f"Nutrients: {int(tama.vitality)}%", True, (255, 255, 255))
        surface.blit(label, (x, y - int(h * 0.125)))

        hint = self.font.render("Fertilize(y)", True, (150, 150, 150))
        surface.blit(hint, ((w - hint.get_width()) // 2, h - hint_pad))

    def handle_key(self, key, tama, app=None):
        super().handle_key(key, tama)
        if key == C_BUTTON:
            threading.Thread(
                target=app._run_opc_write,
                daemon=True,
                args=("Food", True, ua.VariantType.Boolean)
            ).start()

class JournalScreen(CareScreen):
    def __init__(self, sw, sh):
        super().__init__(sw, sh)
        self.entries = []

    def draw_content(self, surface, tama):
        w, h = surface.get_size()
        margin_x = int(w * 0.0625)
        margin_y = int(h * 0.083)
        entry_gap = int(h * 0.146)
        hint_pad = int(h * 0.167)

        title = self.font.render("Journal", True, (255, 200, 80))
        surface.blit(title, (margin_x, margin_y))

        if not self.entries:
            msg = self.font.render("No entries yet.", True, (150, 150, 150))
            surface.blit(msg, (margin_x, margin_y + int(h * 0.125)))
        else:
            for i, entry in enumerate(self.entries[-4:]):
                text = self.font.render(entry, True, (220, 220, 220))
                surface.blit(text, (margin_x, margin_y + int(h * 0.125) + i * entry_gap))

        hint = self.font.render("Press Y to log entry", True, (150, 150, 150))
        surface.blit(hint, ((w - hint.get_width()) // 2, h - hint_pad))

    def handle_key(self, key, tama, app=None):
        super().handle_key(key, tama)
        if key == C_BUTTON:
            from datetime import date
            self.entries.append(f"Day log: W{int(tama.thirst)} V{int(tama.vitality)} M{int(tama.mood)}")
            threading.Thread(
                target=app._run_opc_write,
                daemon=True,
                args=("Light", True, ua.VariantType.Boolean)
            ).start()

class App:
    def __init__(self):
        self._running = True
        self.screen = None
        self.size = self.width, self.height = 800, 480
        self.bg = None
        self.bg_rect = None
        self.tama = None
        self.allsprites = None
        self.menu = None
        self.care_screens = None
        self.active_care = None

    async def get_opc_data_all(self):
        try:
            client = Client(url=SERVER_URL, timeout=10)
            async with client:
                nodes = {
                    "Moisture": client.get_node("ns=2;s=Moisture"),
                    "LightIntensity": client.get_node("ns=2;s=LightIntensity"),
                    "Nitrogen": client.get_node("ns=2;s=Nitrogen"),
                    "Phosphorus": client.get_node("ns=2;s=Phosphorus"),
                    "Potassium": client.get_node("ns=2;s=Potassium"),
                    "New_Plant": client.get_node("ns=2;s=New_Plant"),
                    "Plant_Name": client.get_node("ns=2;s=Plant_Name")
                }
                results = {}
                for name, node in nodes.items():
                    try:
                        results[name] = await node.read_value()
                    except Exception as e:
                        print(f"FAILED node: {name}, NodeId: {node.nodeid}, Error: {e}")
                        results[name] = None
                return results
        except Exception as e:
            import traceback
            print(f"OPC read error: {type(e).__name__}: {e}")
            traceback.print_exc()
            return None

    def _run_opc_read_all(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self.get_opc_data_all())
            if results is not None:
                pygame.event.post(pygame.event.Event(
                    self.OPC_RESULT, {"values": results}
                ))
        except Exception as e:
            print(f"Thread OPC error: {type(e).__name__}: {e}")
        finally:
            loop.close()

    async def write_opc_data(self, node_name, value, variant_type=ua.VariantType.Boolean):
        try:
            client = Client(url=SERVER_URL, timeout=10)
            async with client:
                node = client.get_node(f"ns=2;s={node_name}")
                await node.write_value(ua.Variant(value, variant_type))
                print(f"SUCCESS: {node_name}, {value}")
                return True
        except Exception as e:
            import traceback
            print(f"OPC write error ({node_name}): {type(e).__name__}: {e}")
            traceback.print_exc()
            return False

    def _run_opc_write(self, node_name, value, variant_type=ua.VariantType.Boolean):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.write_opc_data(node_name, value, variant_type))
        except Exception as e:
            print(f"Thread OPC write error: {type(e).__name__}: {e}")
        finally:
            loop.close()

    def on_init(self):
        pygame.init()
        # SCREEN INIT
        if os_type == "raspbi":
            self.screen = pygame.display.set_mode(self.size, pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.size)

        self._running = True
        self.clock = pygame.time.Clock()

        # Background
        self.bg = pygame.image.load(os.path.join(img_dir, "bg.png")).convert()
        bg_w, bg_h = self.bg.get_size()
        scale = 1.7 * min(self.width / bg_w, self.height / bg_h)
        self.bg = pygame.transform.scale(self.bg, (int(bg_w * scale), int(bg_h * scale)))
        self.bg_rect = self.bg.get_rect(center=(self.width // 2, self.height // 2 - 50))

        # OPC timer
        self.OPC_UPDATE = pygame.USEREVENT + 1
        pygame.time.set_timer(self.OPC_UPDATE, 5000)

        self.OPC_RESULT = pygame.USEREVENT + 2

        # set OPC variables
        water = WATER_MAX
        light = LIGHT_MAX
        food = FOOD_MAX

        # Game objects
        self.tama = Tama(self.width, self.height)
        self.allsprites = pygame.sprite.RenderPlain(self.tama)

        self.menu = MenuScreen(self.width, self.height)
        self.care_screens = [
            WaterScreen(self.width, self.height),
            GardenScreen(self.width, self.height),
            JournalScreen(self.width, self.height),
        ]

    def on_event(self, event):
        if event.type == pygame.QUIT:
            self._running = False

        if event.type == KEYDOWN:
            # ESCAPE always quits
            if event.key == pygame.K_ESCAPE:
                self.on_cleanup()
                sys.exit()

            # care screen is open — send keys to it only
            elif self.active_care and self.active_care.open:
                self.active_care.handle_key(event.key, self.tama, self)  # pass app
                if not self.active_care.open:
                    self.active_care = None

            # menu is open — send keys to it only
            elif self.menu.open:
                selected = self.menu.handle_key(event.key)
                if selected is not None:
                    self.active_care = self.care_screens[selected]
                    self.active_care.show()
                    self.menu.toggle()

            # nothing open — A opens menu
            elif event.key == A_BUTTON:
                self.menu.toggle()

        if event.type == self.OPC_UPDATE:
            threading.Thread(target=self._run_opc_read_all, daemon=True).start()

        # self ya
        if event.type == self.OPC_RESULT:
            v = event.values
            if "Moisture" in v:
                self.tama.thirst = max(0, min(((1650 - v["Moisture"]) / WATER_MAX) * 100, 100))
            if "LightIntensity" in v:
                self.tama.mood = min((v["LightIntensity"] / LIGHT_MAX) * 100, 100)
            if "Nitrogen" in v:
                self.tama.vitality = min(((v["Nitrogen"]+v['Phosphorus']+v['Potassium']) / FOOD_MAX) * 100, 100)
            self.tama.status_update()
            if "New_Plant" in v:
                if v['New_Plant']:
                    self.tama.plant_type = v['Plant_Name']
                    threading.Thread(
                        target=self._run_opc_write,
                        daemon=True,
                        args=("New_Plant", False, ua.VariantType.Boolean)
                    ).start()
            print("OPC result keys:", event.values.keys())
            print("OPC values:", event.values)

    def on_loop(self):
        self.allsprites.update()
        self.menu.update()
        if self.active_care:
            self.active_care.update()

    def on_render(self):
        self.screen.fill((255, 255, 255))
        self.screen.blit(self.bg, self.bg_rect)

        self.allsprites.draw(self.screen)
        self._draw_above()
        self._draw_needs()
        self._draw_below()
        self.menu.draw(self.screen)
        if self.active_care:
            self.active_care.draw(self.screen, self.tama)

        pygame.display.flip()

    def _draw_needs(self):
        font = get_font(0.125, self.height)
        bar_width  = int(self.width * 0.31)
        bar_height = int(self.height * 0.083)
        padding    = int(self.height * 0.125)
        margin_x   = int(self.width * 0.0625)
        start_y    = int(self.height * 0.229)
        icon_dim   = int(self.height * 0.067)

        icon, _ = load_image("sprite.png", None, 1)
        icon = pygame.transform.scale(icon, (icon_dim, icon_dim))

        x = self.screen.get_width() - bar_width - margin_x

        needs = [
            ("Thirst",   self.tama.thirst,   (100, 200, 100)),
            ("Vitality", self.tama.vitality, (100, 150, 255)),
            ("Mood",     self.tama.mood,     (255, 200,  80)),
        ]

        for i, (label, value, color) in enumerate(needs):
            y = start_y + i * (bar_height + padding)
            pygame.draw.rect(self.screen, (60, 60, 60), (x, y, bar_width, bar_height))
            pygame.draw.rect(self.screen, color, (x, y, int(bar_width * value / 100), bar_height))

            text = font.render(label, True, (0, 0, 0))
            label_y = y + bar_height + 2
            self.screen.blit(icon, (x, label_y))
            remaining_x = x + icon_dim + int(self.width * 0.0125)
            remaining_width = bar_width - icon_dim - int(self.width * 0.0125)
            text_x = remaining_x + (remaining_width - text.get_width()) // 2
            self.screen.blit(text, (text_x, label_y))

    def _draw_above(self):
        font = get_font(0.125, self.height)
        margin_x = int(self.width * 0.0625)
        margin_y = int(self.height * 0.042)

        day_text = font.render(f"Day {self.tama.age}", True, (0, 0, 0))
        self.screen.blit(day_text, (margin_x, margin_y))

        status_text = font.render(get_status(self.tama), True, (0, 0, 0))
        status_x = self.screen.get_width() - status_text.get_width() - margin_x
        self.screen.blit(status_text, (status_x, margin_y))

    def _draw_below(self):
        font = get_font(0.125, self.height)
        icon_dim = int(self.width * 0.0625)
        gap      = int(self.width * 0.0625)
        margin_b = int(self.height * 0.042)

        icon, _ = load_image("sprite.png", None, 1)
        icon = pygame.transform.scale(icon, (icon_dim, icon_dim))

        items = [self.tama.name, self.tama.plant_type]
        rendered = [font.render(label, True, (0, 0, 0)) for label in items]
        item_widths = [icon_dim + int(self.width * 0.0125) + t.get_width() for t in rendered]
        total_width = sum(item_widths) + gap

        y = self.screen.get_height() - icon_dim - margin_b
        start_x = (self.screen.get_width() - total_width) // 2

        for i, (text, item_width) in enumerate(zip(rendered, item_widths)):
            x = start_x + sum(item_widths[:i]) + i * gap
            self.screen.blit(icon, (x, y))
            self.screen.blit(text, (x + icon_dim + int(self.width * 0.0125), y))

    def on_cleanup(self):
        pygame.quit()

    def on_execute(self):
        if self.on_init() == False:
            self._running = False

        while self._running:
            for event in pygame.event.get():
                self.on_event(event)
            self.on_loop()
            self.on_render()
            self.clock.tick(60)

        self.on_cleanup()

if __name__ == "__main__":
    theApp = App()
    theApp.on_execute()