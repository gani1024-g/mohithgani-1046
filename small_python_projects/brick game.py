"""
Breakout
--------
Classic Breakout / Brick Breaker built with Pygame.

Controls:
    Left/Right arrows or A/D - move paddle
    Space                    - launch ball / restart after game over or win
    P                        - pause / unpause
    Esc / close window       - quit

Requirements:
    pip install pygame

Run:
    python breakout.py
"""

import sys
import random
import pygame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 700
SCREEN_HEIGHT = 600
TOP_MARGIN = 60  # score bar height

PADDLE_WIDTH = 100
PADDLE_HEIGHT = 14
PADDLE_SPEED = 8
PADDLE_Y_OFFSET = 30  # distance from bottom of screen

BALL_RADIUS = 8
BALL_BASE_SPEED = 5.5
BALL_MAX_SPEED = 9.5
BALL_SPEEDUP_PER_HIT = 0.05

BRICK_ROWS = 6
BRICK_COLS = 10
BRICK_PADDING = 6
BRICK_TOP_OFFSET = TOP_MARGIN + 40
BRICK_HEIGHT = 22
BRICK_SIDE_MARGIN = 20

LIVES_START = 3

# Colors
BLACK = (15, 15, 20)
DARK_GRAY = (30, 30, 38)
WHITE = (240, 240, 240)
GRAY = (120, 120, 130)
YELLOW = (240, 200, 60)
PADDLE_COLOR = (90, 170, 240)
BALL_COLOR = (240, 240, 240)

ROW_COLORS = [
    (220, 70, 70),
    (240, 140, 60),
    (240, 200, 60),
    (100, 200, 100),
    (90, 170, 240),
    (160, 110, 220),
]

BRICK_WIDTH = (SCREEN_WIDTH - 2 * BRICK_SIDE_MARGIN - (BRICK_COLS - 1) * BRICK_PADDING) / BRICK_COLS


class Paddle:
    def __init__(self):
        self.reset()

    def reset(self):
        self.rect = pygame.Rect(0, 0, PADDLE_WIDTH, PADDLE_HEIGHT)
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - PADDLE_Y_OFFSET

    def move(self, dx):
        self.rect.x += dx
        self.rect.x = max(0, min(SCREEN_WIDTH - self.rect.width, self.rect.x))


class Ball:
    def __init__(self, paddle):
        self.paddle = paddle
        self.reset()

    def reset(self):
        self.attached = True
        self.speed = BALL_BASE_SPEED
        self.vx = 0.0
        self.vy = 0.0
        self._snap_to_paddle()

    def _snap_to_paddle(self):
        self.x = self.paddle.rect.centerx
        self.y = self.paddle.rect.top - BALL_RADIUS - 1

    def launch(self):
        if self.attached:
            self.attached = False
            angle_choices = [-0.6, -0.4, -0.2, 0.2, 0.4, 0.6]
            self.vx = self.speed * random.choice(angle_choices)
            self.vy = -abs((self.speed ** 2 - self.vx ** 2) ** 0.5)

    def update(self, paddle, bricks):
        if self.attached:
            self._snap_to_paddle()
            return "none"

        self.x += self.vx
        self.y += self.vy

        # Wall collisions
        if self.x - BALL_RADIUS <= 0:
            self.x = BALL_RADIUS
            self.vx *= -1
        elif self.x + BALL_RADIUS >= SCREEN_WIDTH:
            self.x = SCREEN_WIDTH - BALL_RADIUS
            self.vx *= -1

        if self.y - BALL_RADIUS <= TOP_MARGIN:
            self.y = TOP_MARGIN + BALL_RADIUS
            self.vy *= -1

        ball_rect = self.get_rect()

        # Paddle collision
        if self.vy > 0 and ball_rect.colliderect(paddle.rect):
            self.y = paddle.rect.top - BALL_RADIUS
            # Bounce angle depends on where it hit the paddle
            offset = (self.x - paddle.rect.centerx) / (paddle.rect.width / 2)
            offset = max(-1, min(1, offset))
            max_angle = 0.8
            self.vx = self.speed * offset * max_angle
            self.vy = -abs((self.speed ** 2 - self.vx ** 2) ** 0.5)

        # Brick collisions (check closest brick only, one per frame)
        for brick in bricks:
            if brick.alive and ball_rect.colliderect(brick.rect):
                self._resolve_brick_collision(brick.rect)
                brick.alive = False
                self.speed = min(BALL_MAX_SPEED, self.speed + BALL_SPEEDUP_PER_HIT)
                self._rescale_velocity()
                break

        # Fell below paddle
        if self.y - BALL_RADIUS > SCREEN_HEIGHT:
            return "lost"

        return "none"

    def _resolve_brick_collision(self, brick_rect):
        # Determine bounce direction based on overlap side
        ball_rect = self.get_rect()
        overlap_left = ball_rect.right - brick_rect.left
        overlap_right = brick_rect.right - ball_rect.left
        overlap_top = ball_rect.bottom - brick_rect.top
        overlap_bottom = brick_rect.bottom - ball_rect.top

        min_overlap = min(overlap_left, overlap_right, overlap_top, overlap_bottom)
        if min_overlap in (overlap_left, overlap_right):
            self.vx *= -1
        else:
            self.vy *= -1

    def _rescale_velocity(self):
        mag = (self.vx ** 2 + self.vy ** 2) ** 0.5
        if mag == 0:
            return
        scale = self.speed / mag
        self.vx *= scale
        self.vy *= scale

    def get_rect(self):
        return pygame.Rect(self.x - BALL_RADIUS, self.y - BALL_RADIUS, BALL_RADIUS * 2, BALL_RADIUS * 2)

    def draw(self, surface):
        pygame.draw.circle(surface, BALL_COLOR, (int(self.x), int(self.y)), BALL_RADIUS)


class Brick:
    def __init__(self, x, y, width, height, color, points):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.points = points
        self.alive = True

    def draw(self, surface):
        if self.alive:
            pygame.draw.rect(surface, self.color, self.rect, border_radius=3)


def build_bricks():
    bricks = []
    for row in range(BRICK_ROWS):
        color = ROW_COLORS[row % len(ROW_COLORS)]
        points = (BRICK_ROWS - row) * 10
        for col in range(BRICK_COLS):
            x = BRICK_SIDE_MARGIN + col * (BRICK_WIDTH + BRICK_PADDING)
            y = BRICK_TOP_OFFSET + row * (BRICK_HEIGHT + BRICK_PADDING)
            bricks.append(Brick(x, y, BRICK_WIDTH, BRICK_HEIGHT, color, points))
    return bricks


def draw_score_bar(surface, font, score, lives, high_score, paused):
    pygame.draw.rect(surface, DARK_GRAY, (0, 0, SCREEN_WIDTH, TOP_MARGIN))
    score_text = font.render(f"Score: {score}", True, WHITE)
    lives_text = font.render(f"Lives: {lives}", True, YELLOW)
    high_text = font.render(f"Best: {high_score}", True, GRAY)
    surface.blit(score_text, (16, 18))
    surface.blit(lives_text, (SCREEN_WIDTH // 2 - lives_text.get_width() // 2, 18))
    surface.blit(high_text, (SCREEN_WIDTH - high_text.get_width() - 16, 18))
    if paused:
        pause_text = font.render("PAUSED", True, GRAY)
        surface.blit(pause_text, (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, TOP_MARGIN + 10))


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
    pygame.display.set_caption("Breakout")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 22)
    big_font = pygame.font.SysFont("consolas", 46, bold=True)
    small_font = pygame.font.SysFont("consolas", 20)

    paddle = Paddle()
    ball = Ball(paddle)
    bricks = build_bricks()

    score = 0
    high_score = 0
    lives = LIVES_START
    paused = False
    game_over = False
    won = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                elif event.key == pygame.K_p and not (game_over or won):
                    paused = not paused

                elif event.key == pygame.K_SPACE:
                    if game_over or won:
                        paddle.reset()
                        ball = Ball(paddle)
                        bricks = build_bricks()
                        score = 0
                        lives = LIVES_START
                        game_over = False
                        won = False
                        paused = False
                    else:
                        ball.launch()

        keys = pygame.key.get_pressed()
        if not paused and not game_over and not won:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                paddle.move(-PADDLE_SPEED)
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                paddle.move(PADDLE_SPEED)

            result = ball.update(paddle, bricks)

            if result == "lost":
                lives -= 1
                if lives <= 0:
                    game_over = True
                    high_score = max(high_score, score)
                else:
                    ball.reset()

            for brick in bricks:
                if not brick.alive and brick.points:
                    score += brick.points
                    brick.points = 0  # count each brick once

            if all(not b.alive for b in bricks):
                won = True
                high_score = max(high_score, score)

        # ---- draw ----
        screen.fill(BLACK)
        for brick in bricks:
            brick.draw(screen)
        pygame.draw.rect(screen, PADDLE_COLOR, paddle.rect, border_radius=4)
        ball.draw(screen)
        draw_score_bar(screen, font, score, lives, max(high_score, score), paused)

        if game_over:
            draw_center_message(
                screen, big_font, small_font,
                ["Game Over", f"Final score: {score}", "Press Space to restart"],
            )
        elif won:
            draw_center_message(
                screen, big_font, small_font,
                ["You Win!", f"Final score: {score}", "Press Space to play again"],
            )
        elif paused:
            draw_center_message(screen, big_font, small_font, ["Paused", "Press P to resume"])
        elif ball.attached:
            hint = small_font.render("Press Space to launch", True, GRAY)
            screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 60))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()