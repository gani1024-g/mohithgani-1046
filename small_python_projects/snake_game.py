"""
Snake Game
----------
Classic Snake built with Pygame.

Controls:
    Arrow keys / WASD - move
    P                 - pause / unpause
    R                 - restart after game over
    Esc / close window - quit

Requirements:
    pip install pygame

Run:
    python snake_game.py
"""

import random
import sys
import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CELL_SIZE = 20
GRID_WIDTH = 30
GRID_HEIGHT = 22
SCREEN_WIDTH = CELL_SIZE * GRID_WIDTH
SCREEN_HEIGHT = CELL_SIZE * GRID_HEIGHT + 60  # extra space for score bar

BASE_FPS = 6
FPS_INCREMENT_EVERY = 5   # speed up every N food eaten
MAX_FPS = 14

# Colors
BLACK = (30, 15, 20)
DARK_GRAY = (30, 30, 38)
WHITE = (240, 240, 240)
GREEN = (60, 200, 90)
DARK_GREEN = (35, 140, 60)
RED = (220, 70, 70)
YELLOW = (240, 200, 60)
GRAY = (120, 120, 130)

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


class Snake:
    def __init__(self):
        self.reset()

    def reset(self):
        start_x = GRID_WIDTH // 2
        start_y = GRID_HEIGHT // 2
        self.body = [(start_x, start_y), (start_x - 1, start_y), (start_x - 2, start_y)]
        self.direction = RIGHT
        self.pending_direction = RIGHT
        self.grow_pending = 0

    def set_direction(self, new_dir):
        # Prevent reversing directly into itself
        opposite = (-self.direction[0], -self.direction[1])
        if new_dir != opposite:
            self.pending_direction = new_dir

    def move(self):
        self.direction = self.pending_direction
        head_x, head_y = self.body[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)
        self.body.insert(0, new_head)
        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.body.pop()

    def grow(self, amount=1):
        self.grow_pending += amount

    def head(self):
        return self.body[0]

    def collides_with_self(self):
        return self.head() in self.body[1:]

    def collides_with_wall(self):
        x, y = self.head()
        return x < 0 or x >= GRID_WIDTH or y < 0 or y >= GRID_HEIGHT


def random_empty_cell(occupied):
    while True:
        cell = (random.randint(0, GRID_WIDTH - 1), random.randint(0, GRID_HEIGHT - 1))
        if cell not in occupied:
            return cell


def draw_grid(surface):
    for x in range(0, SCREEN_WIDTH, CELL_SIZE):
        pygame.draw.line(surface, DARK_GRAY, (x, 60), (x, SCREEN_HEIGHT))
    for y in range(60, SCREEN_HEIGHT, CELL_SIZE):
        pygame.draw.line(surface, DARK_GRAY, (0, y), (SCREEN_WIDTH, y))


def draw_cell(surface, pos, color, inset=2):
    x, y = pos
    rect = pygame.Rect(
        x * CELL_SIZE + inset,
        60 + y * CELL_SIZE + inset,
        CELL_SIZE - inset * 2,
        CELL_SIZE - inset * 2,
    )
    pygame.draw.rect(surface, color, rect, border_radius=4)


def draw_snake(surface, snake):
    for i, segment in enumerate(snake.body):
        color = GREEN if i == 0 else DARK_GREEN
        draw_cell(surface, segment, color)


def draw_score_bar(surface, font, score, high_score, paused):
    pygame.draw.rect(surface, DARK_GRAY, (0, 0, SCREEN_WIDTH, 60))
    score_text = font.render(f"Score: {score}", True, WHITE)
    high_text = font.render(f"Best: {high_score}", True, YELLOW)
    surface.blit(score_text, (16, 18))
    surface.blit(high_text, (SCREEN_WIDTH - high_text.get_width() - 16, 18))
    if paused:
        pause_text = font.render("PAUSED", True, GRAY)
        surface.blit(pause_text, (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, 18))


def draw_center_message(surface, big_font, small_font, lines):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))

    total_height = big_font.get_height() + len(lines[1:]) * (small_font.get_height() + 6)
    y = SCREEN_HEIGHT // 2 - total_height // 2

    title_surf = big_font.render(lines[0], True, WHITE)
    surface.blit(title_surf, (SCREEN_WIDTH // 2 - title_surf.get_width() // 2, y))
    y += big_font.get_height() + 10

    for line in lines[1:]:
        line_surf = small_font.render(line, True, GRAY)
        surface.blit(line_surf, (SCREEN_WIDTH // 2 - line_surf.get_width() // 2, y))
        y += small_font.get_height() + 6


def main():
    pygame.init()
    pygame.display.set_caption("Snake")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 24)
    big_font = pygame.font.SysFont("consolas", 48, bold=True)
    small_font = pygame.font.SysFont("consolas", 22)

    snake = Snake()
    food = random_empty_cell(snake.body)
    score = 0
    high_score = 0
    eaten_count = 0
    fps = BASE_FPS
    paused = False
    game_over = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    pygame.quit()
                    sys.exit()

                elif event.key in (pygame.K_UP, pygame.K_w) and not game_over:
                    snake.set_direction(UP)
                elif event.key in (pygame.K_DOWN, pygame.K_s) and not game_over:
                    snake.set_direction(DOWN)
                elif event.key in (pygame.K_LEFT, pygame.K_a) and not game_over:
                    snake.set_direction(LEFT)
                elif event.key in (pygame.K_RIGHT, pygame.K_d) and not game_over:
                    snake.set_direction(RIGHT)

                elif event.key == pygame.K_p and not game_over:
                    paused = not paused

                elif event.key == pygame.K_r and game_over:
                    snake.reset()
                    food = random_empty_cell(snake.body)
                    score = 0
                    eaten_count = 0
                    fps = BASE_FPS
                    game_over = False
                    paused = False

        if not paused and not game_over:
            snake.move()

            if snake.collides_with_wall() or snake.collides_with_self():
                game_over = True
                high_score = max(high_score, score)

            elif snake.head() == food:
                snake.grow(1)
                score += 1
                eaten_count += 1
                food = random_empty_cell(snake.body)
                if eaten_count % FPS_INCREMENT_EVERY == 0:
                    fps = min(MAX_FPS, fps + 1)

        # ---- draw ----
        screen.fill(BLACK)
        draw_grid(screen)
        draw_cell(screen, food, RED)
        draw_snake(screen, snake)
        draw_score_bar(screen, font, score, max(high_score, score), paused)

        if game_over:
            draw_center_message(
                screen,
                big_font,
                small_font,
                ["Game Over", f"Final score: {score}", "Press R to restart"],
            )
        elif paused:
            draw_center_message(screen, big_font, small_font, ["Paused", "Press P to resume"])

        pygame.display.flip()
        clock.tick(fps)


if __name__ == "__main__":
    main()
