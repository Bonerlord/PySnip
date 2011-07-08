from commands import add, admin
from pyspades.server import block_action, set_color
from pyspades.common import make_color
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from pyspades.constants import *

@admin
def platform(connection, *args):
    if connection.building_button:
        return "You're in button mode! Type /button to exit it."
    if connection.building_platform or connection.editing_platform:
        return connection.end_platform()
    else:
        return connection.start_platform(*args)

@admin
def button(connection, value = None, type = None, speed = None):
    if connection.building_platform or connection.editing_platform:
        return "You're in platform mode! Type /platform to exit it."
    if connection.building_button:
        return connection.cancel_button()
    else:
        return connection.start_button(value, type, speed)

add(platform)
add(button)

def apply_script(protocol, connection, config):
    class Button:
        callbacks = None
        
        def __init__(self):
            self.callbacks = []
        
        def add_action(self, platform, callback, *args):
            self.callbacks.append((platform, callback, args))
        
        def action(self, user):
            for platform, callback, args in self.callbacks:
                if callback(user, *args) == False:
                    return
    
    class Platform:
        protocol = None
        cycle_call = None
        busy = False
        disabled = False
        frozen = False
        mode = None
        
        def __init__(self, protocol, min_x, min_y, max_x, max_y, start_z):
            self.protocol = protocol
            self.x = min_x
            self.y = min_y
            self.x2 = max_x
            self.y2 = max_y
            self.z = start_z
            self.start_z = start_z
            self.cycle_call = LoopingCall(self.cycle)
        
        def collides(self, x, y, z):
            return (x >= self.x and x < self.x2 and y >= self.y and y < self.y2
                and z <= self.start_z and z >= self.z)
        
        def destroy(self, connection, start_z = None):
            start_z = start_z or self.z
            block_action.value = DESTROY_BLOCK
            block_action.player_id = connection.player_id
            for x in xrange(self.x, self.x2):
                block_action.x = x
                for y in xrange(self.y, self.y2):
                    block_action.y = y
                    for z in xrange(start_z, self.start_z + 1):
                        block_action.z = z
                        self.protocol.send_contained(block_action, save = True)
                        self.protocol.map.remove_point(x, y, self.z)
        
        def start(self, user, target_z, mode, speed, force = False):
            if not force:
                if self.disabled:
                    user.send_chat('This platform is currently disabled.')
                    return False
                elif self.busy:
                    return
            self.disabled = False
            self.user = user
            self.mode = mode
            self.last_z = self.z
            self.target_z = target_z
            self.speed = speed
            if self.z == self.target_z:
                return
            self.busy = True
            self.cycle_call.start(self.speed, now = False)
        
        def cycle(self):
            if self.frozen:
                return
            if self.z == self.target_z:
                self.busy = False
                self.cycle_call.stop()
                if self.mode == 'elevator':
                    self.busy = True
                    self.mode = 'once'
                    self.target_z = self.last_z
                    reactor.callLater(3.0, self.cycle_call.start, self.speed)
                return
            elif self.z > self.target_z:
                self.z -= 1
                set_color.value = make_color(255, 0, 0)
                set_color.player_id = self.user.player_id
                self.protocol.send_contained(set_color, save = True)
                block_action.value = BUILD_BLOCK
            elif self.z < self.target_z:
                block_action.value = DESTROY_BLOCK
            block_action.z = self.z
            block_action.player_id = self.user.player_id
            for x in xrange(self.x, self.x2):
                block_action.x = x
                for y in xrange(self.y, self.y2):
                    block_action.y = y
                    self.protocol.send_contained(block_action, save = True)
                    if block_action.value == BUILD_BLOCK:
                        self.protocol.map.set_point(x, y, self.z, (255, 0, 0, 255),
                            user = False)
                    else:
                        self.protocol.map.remove_point(x, y, self.z)
            if self.z < self.target_z:
                self.z += 1
    
    class PlatformConnection(connection):
        building_platform = False
        building_button = False
        editing_platform = False
        editing_mode = None
        editing_args = None
        button_platform = None
        platform_blocks = None
        
        def on_block_build(self, x, y, z):
            if self.building_platform:
                self.platform_blocks.add((x, y, z))
            if self.building_button:
                self.place_button(x, y, z)
            connection.on_block_build(self, x, y, z)
        
        def on_block_destroy(self, x, y, z, mode):
            platform = self.protocol.check_platform(x, y, z)
            if mode == DESTROY_BLOCK:
                if self.building_button and self.button_platform is None:
                    if platform is None:
                        self.send_chat('That is not a platform! Aborting '
                            'button placement.')
                        self.building_button = False
                    elif platform.start_z - self.button_height < 1:
                        self.send_chat("Sorry, but you'll have to pick a lower"
                            "height value.")
                        self.building_button = False
                    else:
                        self.button_platform = platform
                        self.send_chat('Platform selected! Now place a block '
                            'for the button.')
                    return False
                elif (self.building_button and self.protocol.buttons and
                    (x, y, z) in self.protocol.buttons):
                    p = self.button_platform
                    b = self.protocol.buttons[(x, y, z)]
                    b.add_action(p, p.start, p.start_z - self.button_height,
                        self.button_type, self.button_speed)
                    self.building_button = False
                    self.send_chat('Added action to button.')
                    return False
                if self.editing_platform:
                    if platform is None:
                        self.send_chat('That is not a platform! Aborting '
                            'platform edit.')
                    elif self.editing_mode == 'height':
                        target_z = platform.start_z - self.editing_args[0]
                        if target_z < 1:
                            self.send_chat("Sorry, but you'll have to pick a "
                                "lower height value.")
                        platform.start(self, target_z, 'once', 0.25,
                            force = True)
                    elif self.editing_mode == 'freeze':
                        platform.frozen = not platform.frozen
                        self.send_chat('Platform ' + ['unfrozen!', 'frozen!']
                            [platform.frozen])
                    elif self.editing_mode == 'disable':
                        platform.disabled = not platform.disabled
                        self.send_chat('Platform ' + ['enabled!', 'disabled!']
                            [platform.disabled])
                    elif self.editing_mode == 'destroy':
                        platform.destroy(self)
                        self.protocol.platforms.remove(platform)
                        if self.protocol.buttons:
                            for b in self.protocol.buttons:
                                new_callbacks = []
                                for c in b.callbacks:
                                    if c[0] != platform:
                                        new_callbacks.append(c)
                                c.callbacks = new_callbacks
                    elif self.editing_mode == 'vanish':
                        platform.destroy(self, platform.start_z)
                    self.editing_platform = False
                    return False
                if self.protocol.buttons:
                    if (x, y, z) in self.protocol.buttons:
                        self.protocol.buttons[(x, y, z)].action(self)
                        return False
            if platform:
                return False
            return connection.on_block_destroy(self, x, y, z, mode)
        
        def on_block_removed(self, x, y, z):
            pos = (x, y, z)
            if self.building_platform:
                self.platform_blocks.discard(pos)
            if self.protocol.buttons and pos in self.protocol.buttons:
                del self.protocol.buttons[pos]
            connection.on_block_removed(self, x, y, z)
        
        def start_platform(self, *args):
            if len(args) > 0:
                self.editing_mode = args[0]
                modes = ['height', 'freeze', 'disable', 'destroy', 'vanish']
                if self.editing_mode not in modes:
                    return ('Valid platform editing modes: ' + ', '.join(modes))
                if self.editing_mode == 'height':
                    try:
                        self.editing_args = [int(args[1])]
                        if self.editing_args[0] < 0:
                            raise ValueError()
                    except (IndexError, ValueError):
                        return 'Usage: /platform height <height>'
                self.editing_platform = True
                return 'Select the platform to modify.'
            self.building_platform = True
            self.platform_blocks = set()
            return ('Platform construction started. Build a rectangle of the '
                'desired size.')
        
        def end_platform(self):
            if self.editing_platform:
                self.editing_platform = False
                return 'Platform editing cancelled.'
            self.building_platform = False
            if len(self.platform_blocks):
                min_x, min_y, max_x, max_y = None, None, None, None
                start_z = None
                bad = None
                for x, y, z in self.platform_blocks:
                    if start_z is None:
                        start_z = z
                    elif start_z != z:
                        bad = ('Bad platform. All blocks must be on a '
                            'single height.')
                        break
                    min_x = x if min_x is None else min(min_x, x)
                    min_y = y if min_y is None else min(min_y, y)
                    max_x = x if max_x is None else max(max_x, x)
                    max_y = y if max_y is None else max(max_y, y)
                max_x += 1
                max_y += 1
                for x in xrange(min_x, max_x):
                    if bad:
                        break
                    for y in xrange(min_y, max_y):
                        if (x, y, start_z) not in self.platform_blocks:
                            bad = 'Bad platform. Incomplete or uneven floor.'
                            break
                if bad:
                    block_action.value = DESTROY_BLOCK
                    block_action.player_id = self.player_id
                    for x, y, z in self.platform_blocks:
                        block_action.x = x
                        block_action.y = y
                        block_action.z = z
                        self.protocol.send_contained(block_action)
                    return bad
                p = Platform(self.protocol,
                    min_x, min_y, max_x, max_y, start_z)
                if self.protocol.platforms is None:
                    self.protocol.platforms = []
                self.protocol.platforms.append(p)
                return 'Platform construction completed.'
            else:
                return 'Platform construction cancelled.'
        
        def start_button(self, height, type, speed):
            if height is None:
                return 'Usage: /button <height> [elevator|once] [speed]'
            self.button_height = int(height)
            if self.button_height < 0:
                return ('Height is relative to the initial platform and must '
                    'be positive!')
            if type is None:
                type = 'elevator'
            type = type.lower()
            types = ['once', 'elevator']
            if type not in types:
                return ('Allowed platform types: ' + ', '.join(types))
            self.button_type = type
            if speed:
                self.button_speed = float(speed)
            else:
                self.button_speed = {'once' : 0.25, 'elevator' : 0.75}[type]
            if self.protocol.platforms is None:
                return ('There are no platforms created yet! Use /platform to '
                    'build one')
            self.building_button = True
            self.button_platform = None
            return 'Select the platform by digging it with the pickaxe.'
        
        def cancel_button(self):
            self.building_button = False
            return 'Button placement cancelled.'
        
        def place_button(self, x, y, z):
            self.building_button = False
            p = self.button_platform
            if p is None:
                self.send_chat('Bad button. No platform selected.')
                return
            b = Button()
            b.add_action(p, p.start, p.start_z - self.button_height,
                self.button_type, self.button_speed)
            if self.protocol.buttons is None:
                self.protocol.buttons = {}
            self.protocol.buttons[(x, y, z)] = b
            self.send_chat('Button succesfully created!')
    
    class PlatformProtocol(protocol):
        platforms = None
        buttons = None
        
        def check_platform(self, x, y, z):
            if self.platforms is None:
                return None
            for plat in self.platforms:
                if plat.collides(x, y, z):
                    return plat
            return None
        
        def is_indestructable(self, x, y, z):
            if self.platforms:
                if self.check_platform(x, y, z):
                    return True
            if self.buttons:
                if (x, y, z) in self.buttons:
                    return True
            return protocol.is_indestructable(self, x, y, z)
    
    return PlatformProtocol, PlatformConnection