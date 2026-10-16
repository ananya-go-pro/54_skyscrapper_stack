import random
import pygame
from game.block import Block


class Debris:
    """A sliced-off piece of a block that tumbles and falls away."""
    GRAVITY = 0.55
    MAX_FALL_SPEED = 18.0

    def __init__(self, x, y, width, height, color, side):
        # x, y = top-left of the piece; stored as a center point for rotation
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.cx = x + width / 2
        self.cy = y + height / 2
        self.color = color

        # Drift away from the tower (side: -1 = left overhang, +1 = right overhang)
        self.vx = side * random.uniform(0.6, 1.8)
        self.vy = random.uniform(-1.5, 0.0)

        # Tip outward: a right-side piece rotates clockwise, a left-side piece counter-clockwise
        self.angle = 0.0
        self.spin = -side * random.uniform(1.5, 4.5)

        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        rect = self.surface.get_rect()
        pygame.draw.rect(self.surface, color, rect, border_radius=4)
        pygame.draw.rect(self.surface, (245, 245, 250), rect,
                         width=max(1, min(2, self.width // 2, self.height // 2)), border_radius=4)

    def update(self):
        self.vy = min(self.MAX_FALL_SPEED, self.vy + self.GRAVITY)
        self.cx += self.vx
        self.cy += self.vy
        self.angle += self.spin

    def y_shift(self, amount):
        self.cy += amount

    def is_offscreen(self, screen_height):
        # Generous margin so a rotated piece is fully gone before it is removed
        return self.cy - max(self.width, self.height) > screen_height

    def render(self, surface):
        rotated = pygame.transform.rotate(self.surface, self.angle)
        surface.blit(rotated, rotated.get_rect(center=(int(self.cx), int(self.cy))))


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.block_height = 28
        self.base_width = 180

        # Perfect placement tuning
        self.perfect_tolerance = 6      # max pixel offset that still counts as perfect
        self.perfect_bonus = 2          # bonus points per perfect (multiplied by streak)
        self.perfect_bonus_cap = 10     # cap on bonus from a single drop
        self.width_restore = 10         # pixels regained per perfect after the first in a streak

        # Atmospheric sky: (tower height, color) keyframes, blended smoothly in between
        self.sky_keyframes = [
            (0,  (24, 27, 36)),    # ground level (original background)
            (6,  (38, 70, 120)),   # pre-dawn
            (14, (60, 125, 195)),  # daytime sky
            (22, (170, 95, 115)),  # sunset
            (30, (80, 55, 120)),   # dusk
            (38, (30, 25, 70)),    # night
            (50, (6, 6, 20)),      # space
        ]
        self.sky_lookahead = 8     # the top of the screen shows the sky this many blocks higher
        self.stars = [(random.randint(0, width), random.randint(0, height), random.choice([1, 1, 2]))
                      for _ in range(60)]

        self.font_title = pygame.font.SysFont(None, 38)
        self.font_hud = pygame.font.SysFont(None, 28)
        self.font_big = pygame.font.SysFont(None, 46)

        self.reset()

    def get_color(self, index):
        palette = [
            (230, 75, 75),   # Crimson
            (240, 140, 45),  # Orange
            (245, 210, 50),  # Gold
            (60, 195, 110),  # Green
            (50, 150, 240),  # Blue
            (165, 80, 225),  # Purple
        ]
        return palette[index % len(palette)]

    def reset(self):
        self.score = 0
        self.game_over = False
        self.perfect_streak = 0
        self.perfect_timer = 0
        self.perfect_text_bonus = 0
        self.debris = []
        self.sky_height = 0.0   # smoothed tower height that drives the background

        base_x = (self.width - self.base_width) // 2
        base_y = self.height - 60
        base_block = Block(base_x, base_y, self.base_width, self.block_height, self.get_color(0), speed=0)
        self.stack = [base_block]

        self.spawn_active_block()

    def get_sky_color(self, h):
        """Interpolate the sky color for a given (fractional) tower height."""
        keys = self.sky_keyframes
        if h <= keys[0][0]:
            return keys[0][1]
        for (h0, c0), (h1, c1) in zip(keys, keys[1:]):
            if h <= h1:
                t = (h - h0) / (h1 - h0)
                return tuple(int(a + (b - a) * t) for a, b in zip(c0, c1))
        return keys[-1][1]

    def draw_background(self, screen):
        top = self.get_sky_color(self.sky_height + self.sky_lookahead)
        bottom = self.get_sky_color(self.sky_height)

        # Build a thin vertical gradient strip and stretch it across the screen
        steps = 64
        strip = pygame.Surface((1, steps))
        for i in range(steps):
            t = i / (steps - 1)
            strip.set_at((0, i), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        screen.blit(pygame.transform.smoothscale(strip, (self.width, self.height)), (0, 0))

        # Stars fade in as the tower reaches space
        star_alpha = max(0.0, min(1.0, (self.sky_height - 34) / 14))
        if star_alpha > 0:
            level = int(255 * star_alpha)
            for x, y, r in self.stars:
                pygame.draw.circle(screen, (level, level, level), (x, y), r)

    def spawn_active_block(self):
        top_block = self.stack[-1]
        next_y = top_block.y - self.block_height - 4
        speed = min(10.0, 4.5 + (len(self.stack) * 0.35))
        color = self.get_color(len(self.stack))

        start_x = 25 if random.choice([True, False]) else self.width - 25 - top_block.width
        self.active_block = Block(start_x, next_y, top_block.width, self.block_height, color, speed=speed)

    def spawn_debris(self, act, left, right):
        """Create falling pieces for any part of the active block hanging outside the overlap."""
        # Overhang on the left
        left_w = left - act.x
        if left_w >= 1:
            self.debris.append(Debris(act.x, act.y, left_w, self.block_height, act.color, side=-1))
        # Overhang on the right
        act_right = act.x + act.width
        right_w = act_right - right
        if right_w >= 1:
            self.debris.append(Debris(right, act.y, right_w, self.block_height, act.color, side=1))

    def drop_block(self):
        if self.game_over:
            return

        top_block = self.stack[-1]
        act = self.active_block

        left = max(act.x, top_block.x)
        right = min(act.x + act.width, top_block.x + top_block.width)
        overlap = right - left
        
        is_successful_drop = overlap > 0
        
        if is_successful_drop:
            is_perfect = abs(act.x - top_block.x) <= self.perfect_tolerance

            if is_perfect:
                # Snap flush with the tower below: no trimming
                self.perfect_streak += 1
                new_width = top_block.width
                new_x = top_block.x

                # From the 2nd consecutive perfect on, regain some lost width
                if self.perfect_streak >= 2 and new_width < self.base_width:
                    restored = min(self.width_restore, self.base_width - new_width)
                    new_width += restored
                    new_x -= restored / 2
                    # Keep the block inside the same bounds the blocks oscillate in
                    new_x = max(20.0, min(new_x, self.width - 20 - new_width))

                bonus = min(self.perfect_bonus * self.perfect_streak, self.perfect_bonus_cap)
                self.score += 1 + bonus
                self.perfect_timer = 60
                self.perfect_text_bonus = bonus
                new_block = Block(new_x, act.y, new_width, self.block_height, act.color, speed=0)
            else:
                self.perfect_streak = 0
                self.spawn_debris(act, left, right)
                trimmed_width = max(10.0, overlap)
                new_block = Block(left, act.y, trimmed_width, self.block_height, act.color, speed=0)
                self.score += 1

            self.stack.append(new_block)

            if new_block.y < 180:
                shift_amount = self.block_height + 4
                for b in self.stack:
                    b.y += shift_amount
                for d in self.debris:
                    d.y_shift(shift_amount)

            self.spawn_active_block()
        else:
            self.game_over = True

    def handle_event(self, event):
        if self.game_over:
            if (event.type == pygame.KEYDOWN and event.key in (pygame.K_r, pygame.K_SPACE)) or \
               (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self.reset()
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.drop_block()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.drop_block()

    def update(self):
        if not self.game_over:
            self.active_block.update(self.width)
            if self.perfect_timer > 0:
                self.perfect_timer -= 1

        target_height = len(self.stack) - 1
        self.sky_height += (target_height - self.sky_height) * 0.04

        for d in self.debris:
            d.update()
        self.debris = [d for d in self.debris if not d.is_offscreen(self.height)]

    def render(self, screen):
        self.draw_background(screen)

        title_surf = self.font_title.render("Skyscraper Stack", True, (245, 245, 245))
        screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 16))

        score_surf = self.font_hud.render(f"Height: {self.score}", True, (255, 220, 80))
        screen.blit(score_surf, (self.width // 2 - score_surf.get_width() // 2, 54))

        for b in self.stack:
            b.render(screen)

        for d in self.debris:
            d.render(screen)

        if not self.game_over:
            self.active_block.render(screen)

        if self.perfect_timer > 0 and not self.game_over:
            alpha = min(255, self.perfect_timer * 8)
            text = "PERFECT!"
            if self.perfect_streak > 1:
                text += f"  x{self.perfect_streak}"
            perfect_surf = self.font_big.render(text, True, (120, 255, 170))
            perfect_surf.set_alpha(alpha)
            screen.blit(perfect_surf, (self.width // 2 - perfect_surf.get_width() // 2, 88))

            bonus_surf = self.font_hud.render(f"+{self.perfect_text_bonus} bonus", True, (255, 220, 80))
            bonus_surf.set_alpha(alpha)
            screen.blit(bonus_surf, (self.width // 2 - bonus_surf.get_width() // 2, 122))

        if self.game_over:
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 195))
            screen.blit(overlay, (0, 0))

            over_surf = self.font_big.render("TOWER COLLAPSED!", True, (240, 75, 75))
            screen.blit(over_surf, (self.width // 2 - over_surf.get_width() // 2, self.height // 2 - 40))

            final_surf = self.font_hud.render(f"Final Height: {self.score}", True, (255, 255, 255))
            screen.blit(final_surf, (self.width // 2 - final_surf.get_width() // 2, self.height // 2 + 10))

            restart_surf = self.font_hud.render("Press [Space] or [R] to Play Again", True, (200, 200, 200))
            screen.blit(restart_surf, (self.width // 2 - restart_surf.get_width() // 2, self.height // 2 + 50))
