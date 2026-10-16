import random
import pygame
from game.block import Block


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

        base_x = (self.width - self.base_width) // 2
        base_y = self.height - 60
        base_block = Block(base_x, base_y, self.base_width, self.block_height, self.get_color(0), speed=0)
        self.stack = [base_block]

        self.spawn_active_block()

    def spawn_active_block(self):
        top_block = self.stack[-1]
        next_y = top_block.y - self.block_height - 4
        speed = min(10.0, 4.5 + (len(self.stack) * 0.35))
        color = self.get_color(len(self.stack))

        start_x = 25 if random.choice([True, False]) else self.width - 25 - top_block.width
        self.active_block = Block(start_x, next_y, top_block.width, self.block_height, color, speed=speed)

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
                trimmed_width = max(10.0, overlap)
                new_block = Block(left, act.y, trimmed_width, self.block_height, act.color, speed=0)
                self.score += 1

            self.stack.append(new_block)

            if new_block.y < 180:
                shift_amount = self.block_height + 4
                for b in self.stack:
                    b.y += shift_amount

            self.spawn_active_block()
        else:
            self.game_over = True

    def handle_event(self, event):
        if self.game_over:
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_r) or \
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

    def render(self, screen):
        screen.fill((24, 27, 36))

        title_surf = self.font_title.render("Skyscraper Stack", True, (245, 245, 245))
        screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 16))

        score_surf = self.font_hud.render(f"Height: {self.score}", True, (255, 220, 80))
        screen.blit(score_surf, (self.width // 2 - score_surf.get_width() // 2, 54))

        for b in self.stack:
            b.render(screen)

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
