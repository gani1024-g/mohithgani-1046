import cv2
import mediapipe as mp
import numpy as np
import math
import time
import random


_mp_solutions = getattr(mp, "solutions")
mp_hands = getattr(_mp_solutions, "hands")
mp_drawing = getattr(_mp_solutions, "drawing_utils")


def is_palm_open(hand_landmarks, hands_module):
    wrist = hand_landmarks.landmark[hands_module.HandLandmark.WRIST]
    extended = 0
    tips = [8, 12, 16, 20]
    mcps = [5, 9, 13, 17]

    for tip, mcp in zip(tips, mcps):
        d_tip_wrist = math.hypot(
            hand_landmarks.landmark[tip].x - wrist.x,
            hand_landmarks.landmark[tip].y - wrist.y,
        )
        d_mcp_wrist = math.hypot(
            hand_landmarks.landmark[mcp].x - wrist.x,
            hand_landmarks.landmark[mcp].y - wrist.y,
        )
        if d_tip_wrist > d_mcp_wrist * 1.3:
            extended += 1

    thumb_tip = hand_landmarks.landmark[4]
    thumb_ip = hand_landmarks.landmark[3]
    if (
        abs(thumb_tip.x - thumb_ip.x) > 0.02
        or abs(thumb_tip.y - thumb_ip.y) > 0.02
    ):
        extended += 1

    return extended >= 4


def is_fist(hand_landmarks, hands_module):
    wrist = hand_landmarks.landmark[hands_module.HandLandmark.WRIST]
    curled = 0
    tips = [8, 12, 16, 20]
    mcps = [5, 9, 13, 17]

    for tip, mcp in zip(tips, mcps):
        d_tip_wrist = math.hypot(
            hand_landmarks.landmark[tip].x - wrist.x,
            hand_landmarks.landmark[tip].y - wrist.y,
        )
        d_mcp_wrist = math.hypot(
            hand_landmarks.landmark[mcp].x - wrist.x,
            hand_landmarks.landmark[mcp].y - wrist.y,
        )
        if d_tip_wrist < d_mcp_wrist * 1.1:
            curled += 1

    return curled >= 3


def get_palm_center(hand_landmarks, w, h):
    wrist = hand_landmarks.landmark[0]
    middle_mcp = hand_landmarks.landmark[9]
    cx = int((wrist.x + middle_mcp.x) / 2 * w)
    cy = int((wrist.y + middle_mcp.y) / 2 * h)
    return cx, cy


def get_palm_size(hand_landmarks, w, h):
    wrist = hand_landmarks.landmark[0]
    middle_mcp = hand_landmarks.landmark[9]
    dist = math.sqrt(
        (wrist.x - middle_mcp.x) ** 2 * w**2
        + (wrist.y - middle_mcp.y) ** 2 * h**2
    )
    return dist


def check_circle_gesture(points, min_perimeter=300, close_threshold=60):
    if len(points) < 20:
        return False, None, 0

    end_pt = points[-1]

    path_dist = 0
    for i in range(len(points) - 2, -1, -1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        path_dist += math.hypot(dx, dy)

        if path_dist > min_perimeter:
            dist_to_old = math.hypot(
                end_pt[0] - points[i][0],
                end_pt[1] - points[i][1],
            )
            if dist_to_old < close_threshold:
                loop_points = points[i:]
                cx = sum(p[0] for p in loop_points) / len(loop_points)
                cy = sum(p[1] for p in loop_points) / len(loop_points)
                radii = [
                    math.hypot(p[0] - cx, p[1] - cy)
                    for p in loop_points
                ]
                avg_radius = sum(radii) / len(radii)
                return True, (int(cx), int(cy)), avg_radius

    return False, None, 0


class Spark:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2) + 1.0
        self.life = random.uniform(0.3, 0.6)
        self.max_life = self.life
        self.size = random.randint(2, 4)

    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        self.life -= dt
        return self.life > 0

    def draw(self, frame):
        alpha = max(0.0, self.life / self.max_life)
        color = (
            int(30 * alpha),
            int(140 * alpha + 80 * (1 - alpha)),
            int(255 * alpha),
        )
        cv2.circle(frame, (int(self.x), int(self.y)), self.size, color, -1)


class Particle:
    def __init__(self, cx, cy, radius):
        angle = random.uniform(0, 2 * math.pi)
        r = random.uniform(radius * 0.9, radius * 1.1)
        self.x = cx + r * math.cos(angle)
        self.y = cy + r * math.sin(angle)
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(-1.5, 1.5)
        self.life = random.uniform(0.3, 1.0)
        self.max_life = self.life
        self.size = random.randint(1, 3)

    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        self.life -= dt
        return self.life > 0

    def draw(self, frame):
        alpha = max(0.0, self.life / self.max_life)
        b = int(30 * alpha)
        g = int(140 * alpha + 80 * (1 - alpha))
        r = int(255 * alpha)
        color = (b, g, r)
        cv2.circle(frame, (int(self.x), int(self.y)), self.size, color, -1)


def draw_rune_segments(
    frame,
    cx,
    cy,
    radius,
    angle_offset,
    num_segments,
    thickness,
    color,
    alpha=1.0,
):
    seg_angle = (2 * math.pi) / num_segments
    arc_len = seg_angle * 0.4

    for i in range(num_segments):
        start_angle = angle_offset + i * seg_angle
        end_angle = start_angle + arc_len
        pts = []
        steps = 10

        for s in range(steps + 1):
            a = start_angle + (end_angle - start_angle) * s / steps
            x = int(cx + radius * math.cos(a))
            y = int(cy + radius * math.sin(a))
            pts.append((x, y))

        col = tuple(int(c * alpha) for c in color)
        for j in range(len(pts) - 1):
            cv2.line(
                frame,
                pts[j],
                pts[j + 1],
                col,
                thickness,
                cv2.LINE_AA,
            )


def draw_geometric_symbols(
    frame,
    cx,
    cy,
    radius,
    angle_offset,
    num_symbols,
    color,
    alpha=1.0,
):
    for i in range(num_symbols):
        angle = angle_offset + i * (2 * math.pi / num_symbols)
        sx = cx + radius * math.cos(angle)
        sy = cy + radius * math.sin(angle)
        size = max(3, int(radius * 0.06))
        col = tuple(int(c * alpha) for c in color)

        if i % 3 == 0:
            pts = np.array(
                [
                    [int(sx), int(sy - size)],
                    [int(sx - size * 0.866), int(sy + size * 0.5)],
                    [int(sx + size * 0.866), int(sy + size * 0.5)],
                ],
                np.int32,
            )
            cv2.polylines(frame, [pts], True, col, 1, cv2.LINE_AA)

        elif i % 3 == 1:
            pts = np.array(
                [
                    [int(sx), int(sy - size)],
                    [int(sx + size), int(sy)],
                    [int(sx), int(sy + size)],
                    [int(sx - size), int(sy)],
                ],
                np.int32,
            )
            cv2.polylines(frame, [pts], True, col, 1, cv2.LINE_AA)

        else:
            cv2.circle(
                frame,
                (int(sx), int(sy)),
                size,
                col,
                1,
                cv2.LINE_AA,
            )


def draw_magic_circle(frame, cx, cy, radius, t, intensity=1.0):
    orange = (30, 140, 255)
    gold = (50, 180, 255)
    bright_gold = (80, 210, 255)
    white_gold = (150, 230, 255)

    alpha = min(1.0, max(0.0, float(intensity)))

    glow_overlay = frame.copy()
    for g in range(3):
        r = int(radius * (1.15 + g * 0.08))
        col = tuple(
            int(c * alpha * (0.3 - g * 0.08))
            for c in orange
        )
        cv2.circle(
            glow_overlay,
            (cx, cy),
            r,
            col,
            2,
            cv2.LINE_AA,
        )

    cv2.addWeighted(
        glow_overlay,
        0.5,
        frame,
        0.5,
        0,
        frame,
    )

    cv2.circle(
        frame,
        (cx, cy),
        int(radius),
        tuple(int(c * alpha) for c in bright_gold),
        3,
        cv2.LINE_AA,
    )
    cv2.circle(
        frame,
        (cx, cy),
        int(radius),
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )

    draw_rune_segments(
        frame,
        cx,
        cy,
        radius * 0.95,
        t * 0.8,
        36,
        2,
        gold,
        alpha * 0.9,
    )
    draw_rune_segments(
        frame,
        cx,
        cy,
        radius * 0.90,
        -t * 0.6,
        24,
        3,
        orange,
        alpha * 0.7,
    )

    pts_oct = []
    for i in range(8):
        angle = t * 0.5 + i * (math.pi / 4)
        x = int(cx + radius * 0.82 * math.cos(angle))
        y = int(cy + radius * 0.82 * math.sin(angle))
        pts_oct.append([x, y])

    cv2.polylines(
        frame,
        [np.array(pts_oct, np.int32)],
        True,
        tuple(int(c * alpha) for c in bright_gold),
        2,
        cv2.LINE_AA,
    )

    for i in range(12):
        angle = -t * 0.4 + i * (math.pi / 6)
        r_outer = radius * 0.82
        r_inner = radius * 0.65
        x1 = int(cx + r_outer * math.cos(angle))
        y1 = int(cy + r_outer * math.sin(angle))
        x2 = int(cx + r_inner * math.cos(angle))
        y2 = int(cy + r_inner * math.sin(angle))

        cv2.line(
            frame,
            (x1, y1),
            (x2, y2),
            tuple(int(c * alpha * 0.8) for c in gold),
            2,
            cv2.LINE_AA,
        )
        cv2.circle(
            frame,
            (x2, y2),
            4,
            tuple(int(c * alpha) for c in white_gold),
            -1,
            cv2.LINE_AA,
        )

    cv2.circle(
        frame,
        (cx, cy),
        int(radius * 0.65),
        tuple(int(c * alpha) for c in orange),
        2,
        cv2.LINE_AA,
    )

    for offset in [0, math.pi / 4]:
        pts_sq = []
        for i in range(4):
            angle = t * 1.5 + offset + i * (math.pi / 2)
            x = int(cx + radius * 0.50 * math.cos(angle))
            y = int(cy + radius * 0.50 * math.sin(angle))
            pts_sq.append([x, y])

        cv2.polylines(
            frame,
            [np.array(pts_sq, np.int32)],
            True,
            tuple(int(c * alpha) for c in bright_gold),
            2,
            cv2.LINE_AA,
        )

    draw_geometric_symbols(
        frame,
        cx,
        cy,
        radius * 0.35,
        -t * 2.0,
        6,
        white_gold,
        alpha,
    )

    pulse = 0.5 + 0.5 * math.sin(t * 8)

    cv2.circle(
        frame,
        (cx, cy),
        int(radius * 0.15),
        tuple(int(c * alpha * 0.5) for c in gold),
        -1,
        cv2.LINE_AA,
    )
    cv2.circle(
        frame,
        (cx, cy),
        int(radius * 0.05 + 5 * pulse),
        tuple(int(c * alpha) for c in white_gold),
        -1,
        cv2.LINE_AA,
    )


def main():
    # Camera
    cap = cv2.VideoCapture(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        # Fall back to the default camera if camera index 1 is unavailable.
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        raise RuntimeError(
            "Could not open a camera. Check your camera index and permissions."
        )

    # Portal state
    portal_active = False
    portal_center = (0, 0)
    portal_radius = 0.0
    portal_intensity_val = 0.0

    drawing_points = []
    spark_particles = []
    portal_particles = []

    start_time = time.time()
    last_time = start_time

    print("╔════════════════════════════════════════════════╗")
    print("║        Doctor Strange Portal Effect 🌀         ║")
    print("╠════════════════════════════════════════════════╣")
    print("║  1. Open Palm -> Small Magical Hand Runes      ║")
    print("║  2. Left Fist + Right Hand Circles -> PORTAL   ║")
    print("║  Press 'q' / ESC to Quit                       ║")
    print("╚════════════════════════════════════════════════╝")

    # Create the MediaPipe Hands object once.
    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("Warning: could not read a camera frame.")
                break

            now = time.time()
            dt = max(0.0, now - last_time)
            last_time = now
            t = now - start_time

            image = cv2.flip(image, 1)
            h, w = image.shape[:2]

            # MediaPipe expects RGB frames.
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)

            dark_bg = np.full(
                (h, w, 3),
                (5, 3, 1),
                dtype=np.uint8,
            )
            blend = cv2.addWeighted(
                image,
                0.55,
                dark_bg,
                0.45,
                0,
            )

            left_fist_present = False
            right_hand_landmarks = None

            # Detect hands and classify gestures.
            if (
                results.multi_hand_landmarks
                and len(results.multi_handedness)
                == len(results.multi_hand_landmarks)
            ):
                for idx, hand_landmarks in enumerate(
                    results.multi_hand_landmarks
                ):
                    label = (
                        results.multi_handedness[idx]
                        .classification[0]
                        .label
                    )

                    # MediaPipe labels are mirrored relative to the
                    # user's physical left/right hand in this setup.
                    is_left_hand = label == "Right"
                    is_right_hand = label == "Left"

                    palm_open = is_palm_open(
                        hand_landmarks,
                        mp_hands,
                    )
                    fist = is_fist(
                        hand_landmarks,
                        mp_hands,
                    )

                    cx, cy = get_palm_center(
                        hand_landmarks,
                        w,
                        h,
                    )
                    palm_size = get_palm_size(
                        hand_landmarks,
                        w,
                        h,
                    )

                    if is_left_hand:
                        if fist:
                            left_fist_present = True
                        elif (
                            palm_open
                            and not portal_active
                            and len(drawing_points) == 0
                        ):
                            draw_magic_circle(
                                blend,
                                cx,
                                cy,
                                palm_size * 1.5,
                                t,
                                0.8,
                            )

                    if is_right_hand:
                        right_hand_landmarks = hand_landmarks
                        if (
                            palm_open
                            and not portal_active
                            and len(drawing_points) == 0
                        ):
                            draw_magic_circle(
                                blend,
                                cx,
                                cy,
                                palm_size * 1.5,
                                t,
                                0.8,
                            )

            # Draw a circle with the right index finger while the
            # left hand is in a fist.
            if left_fist_present:
                if not portal_active:
                    if right_hand_landmarks is not None:
                        index_tip = right_hand_landmarks.landmark[
                            mp_hands.HandLandmark.INDEX_FINGER_TIP
                        ]
                        ix = int(index_tip.x * w)
                        iy = int(index_tip.y * h)
                        drawing_points.append((ix, iy))

                        for _ in range(4):
                            spark_particles.append(
                                Spark(ix, iy)
                            )

                        if len(drawing_points) > 100:
                            drawing_points.pop(0)

                        (
                            is_circle,
                            center,
                            avg_radius,
                        ) = check_circle_gesture(
                            drawing_points,
                            min_perimeter=250,
                            close_threshold=50,
                        )

                        if is_circle and center is not None:
                            portal_active = True
                            portal_center = center
                            portal_radius = max(
                                avg_radius,
                                120,
                            ) * 1.2
                            portal_intensity_val = max(
                                portal_intensity_val,
                                0.05,
                            )
                            drawing_points = []
                else:
                    portal_intensity_val = min(
                        1.0,
                        portal_intensity_val + dt * 2.0,
                    )
                    drawing_points = []
            else:
                portal_intensity_val = max(
                    0.0,
                    portal_intensity_val - dt * 2.0,
                )
                if portal_intensity_val <= 0:
                    portal_active = False
                drawing_points = []

            # Draw the live finger path.
            if len(drawing_points) > 1:
                for i in range(1, len(drawing_points)):
                    cv2.line(
                        blend,
                        drawing_points[i - 1],
                        drawing_points[i],
                        (50, 180, 255),
                        2,
                        cv2.LINE_AA,
                    )

            # Draw the active portal.
            if portal_active or portal_intensity_val > 0.05:
                draw_magic_circle(
                    blend,
                    int(portal_center[0]),
                    int(portal_center[1]),
                    portal_radius,
                    t,
                    portal_intensity_val,
                )

                if random.random() < 0.8 * portal_intensity_val:
                    for _ in range(2):
                        portal_particles.append(
                            Particle(
                                portal_center[0],
                                portal_center[1],
                                portal_radius,
                            )
                        )

            # Update sparks.
            alive_sparks = []
            for particle in spark_particles:
                if particle.update(dt):
                    particle.draw(blend)
                    alive_sparks.append(particle)
            spark_particles = alive_sparks

            # Update portal particles.
            alive_portal = []
            for particle in portal_particles:
                if particle.update(dt):
                    particle.draw(blend)
                    alive_portal.append(particle)
            portal_particles = alive_portal

            # Keep particle lists bounded.
            if len(spark_particles) > 300:
                spark_particles = spark_particles[-200:]
            if len(portal_particles) > 400:
                portal_particles = portal_particles[-300:]

            cv2.imshow("Doctor Strange Portal", blend)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
