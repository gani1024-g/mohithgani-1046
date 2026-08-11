"""
Multimodal Login + Profile Management
--------------------------------------
Flask app with:
1. Username/password registration and login
2. Face registration and face login using face-api.js in the browser
3. Voice-to-text profile entry using the browser Web Speech API
4. Profile picture capture using the webcam
5. Microphone access for speech recognition
6. JSON persistence so accounts survive Flask restarts

Install:
    pip install flask werkzeug

Run:
    python sign_in_page.py

Open:
    http://127.0.0.1:5000

IMPORTANT:
- Camera/microphone work on localhost or HTTPS.
- Face models are loaded by the browser from the face-api.js model CDN.
- For production, use HTTPS, a real database, CSRF protection, rate limiting,
  encrypted biometric storage, and a proper identity/authentication service.
"""

import json
import math
import os
import re
from pathlib import Path

from flask import (
    Flask, jsonify, redirect, render_template_string,
    request, send_from_directory, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "change-this-secret-key")

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "users.json"
UPLOAD_FOLDER = BASE_DIR / "profile_photos"
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_PHOTO_BYTES = 2 * 1024 * 1024
FACE_THRESHOLD = 0.52  # lower = stricter. Tune after testing your camera.

PROFILE_FIELDS = [
    "full_name",
    "contact_phone",
    "email_address",
    "dob",
    "physical_address",
    "accessibility_mode",
]

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_POLICY = "Use at least 8 characters, including an uppercase letter and a special character."


def load_users():
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(users):
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)
    tmp.replace(DATA_FILE)


USERS = load_users()


def clean_username(username):
    return re.sub(r"[^A-Za-z0-9_.-]", "", username.strip())


def find_user_by_identifier(identifier):
    value = str(identifier or "").strip()
    if not value:
        return None

    if EMAIL_PATTERN.fullmatch(value):
        normalized_email = value.lower()
        for username, user in USERS.items():
            if str(user.get("email", "")).strip().lower() == normalized_email:
                return username, user

    cleaned = clean_username(value)
    if cleaned:
        user = USERS.get(cleaned)
        if user:
            return cleaned, user

    return None


def photo_filename(username):
    safe = secure_filename(username) or "user"
    return f"{safe}.jpg"


def photo_url(username):
    path = UPLOAD_FOLDER / photo_filename(username)
    return url_for("get_photo", username=username) if path.exists() else None


def require_login():
    return bool(session.get("authenticated") and session.get("username"))


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must contain at least one special character."
    return True, ""


def face_distance(a, b):
    if not isinstance(a, list) or not isinstance(b, list):
        return 999.0
    if len(a) != len(b) or not a:
        return 999.0
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


# ---------------------------------------------------------------------------
# LOGIN PAGE
# ---------------------------------------------------------------------------

LOGIN_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Secure Sign In</title>
<style>
:root{
  --primary:#2563eb; --primary2:#1d4ed8; --bg:#eef4ff;
  --card:#fff; --text:#172033; --muted:#64748b; --border:#dbe3ef;
  --danger:#dc2626; --success:#15803d;
}
*{box-sizing:border-box}
body{
  margin:0; min-height:100vh; display:flex; align-items:center;
  justify-content:center; padding:24px; font-family:Inter,system-ui,Arial,sans-serif;
  background:linear-gradient(135deg,#dbeafe,#f8fafc);
  color:var(--text);
}
.card{
  width:min(100%,460px); background:var(--card); padding:32px;
  border-radius:22px; box-shadow:0 20px 60px rgba(15,23,42,.15);
}
h1{text-align:center;margin:0 0 8px}
.sub{text-align:center;color:var(--muted);margin:0 0 24px}
.tabs{display:flex;gap:8px;margin-bottom:20px}
.tab{
  flex:1;padding:11px;border:1px solid var(--border);background:#f8fafc;
  border-radius:10px;cursor:pointer;font-weight:700
}
.tab.active{background:var(--primary);color:white;border-color:var(--primary)}
.panel{display:none}.panel.active{display:block}
.field{margin-bottom:15px}
label{display:block;font-weight:700;font-size:.9rem;margin-bottom:7px}
input{
  width:100%;padding:12px;border:1px solid var(--border);border-radius:10px;
  font-size:1rem;outline:none
}
input:focus{border-color:var(--primary);box-shadow:0 0 0 3px #dbeafe}
button{
  border:0;border-radius:10px;padding:12px;width:100%;font-weight:800;
  cursor:pointer;font-size:1rem
}
.primary{background:var(--primary);color:#fff}
.primary:hover{background:var(--primary2)}
.secondary{background:#e2e8f0;color:#172033}
.face{
  margin-top:10px;background:#0f172a;color:white
}
.status{min-height:24px;text-align:center;font-size:.9rem;margin:12px 0}
.error{color:var(--danger)} .success{color:var(--success)}
.camera{
  display:none; margin:12px auto; width:320px; max-width:100%;
  background:#000;border-radius:14px;overflow:hidden;position:relative
}
video{display:block;width:100%;aspect-ratio:4/3;object-fit:cover}
.note{font-size:.78rem;color:var(--muted);line-height:1.45;margin-top:18px}
.hidden{display:none!important}
</style>
</head>
<body>
<div class="card">
  <h1>Welcome to Likhitech </h1>
  <p class="sub">Sign in with your account or your face.</p>

  <div class="tabs">
    <button class="tab active" id="loginTab" type="button">Sign In</button>
    <button class="tab" id="registerTab" type="button">Create Account</button>
  </div>

  <div id="status" class="status"></div>

  <section id="loginPanel" class="panel active">
    <form id="loginForm">
      <div class="field">
        <label>Username or Email</label>
        <input id="loginUsername" autocomplete="username" placeholder="Enter your username or email address">
      </div>
      <div class="field">
        <label>Password</label>
        <input id="loginPassword" type="password" autocomplete="current-password" placeholder="Enter your password" required>
      </div>
      <div class="field" style="margin-top:-4px">
        <button class="secondary" id="loginMicBtn" type="button" style="width:auto; padding:10px 14px; display:flex; align-items:center; justify-content:center; gap:8px;"> Voice Input</button>
        <div id="loginVoiceStatus" class="note" style="margin-top:8px"></div>
        <div class="note" style="font-size:.78rem;color:#64748b;margin-top:8px">
          Try voice commands: "username &lt;name&gt;", "password &lt;secret&gt;", "submit", "clear field", "select password", "select username", "focus email"
        </div>
      </div>
      <button class="primary" type="submit">Sign In</button>
    </form>

    <button class="secondary" id="forgotPasswordToggle" type="button" style="margin-top:10px">Forgot Password?</button>

    <form id="forgotPasswordForm" class="hidden" style="margin-top:12px">
      <div class="field">
        <label>Username or Email</label>
        <input id="resetIdentifier" autocomplete="username" placeholder="Enter your username or email address" required>
      </div>
      <div class="field">
        <label>New Password</label>
        <input id="resetPassword" type="password" autocomplete="new-password" placeholder="Enter your new password" required minlength="8">
      </div>
      <div class="field">
        <label>Confirm New Password</label>
        <input id="resetConfirm" type="password" autocomplete="new-password" placeholder="Confirm your new password" required minlength="8">
      </div>
      <div class="field" style="font-size:.85rem;color:#64748b;line-height:1.45">
        <div><b>Password policy:</b> {PASSWORD_POLICY}</div>
      </div>
      <button class="primary" type="submit">Reset Password</button>
    </form>

    <button class="face" id="faceLoginBtn" type="button">Sign In With Face</button>
    <div class="camera" id="loginCamera">
      <video id="loginVideo" autoplay muted playsinline></video>
    </div>
  </section>

  <section id="registerPanel" class="panel">
    <form id="registerForm">
      <div class="field">
        <label>Username</label>
        <input id="registerUsername" autocomplete="username" placeholder="Enter your username" required minlength="3">
      </div>
      <div class="field">
        <label>Email</label>
        <input id="registerEmail" type="email" autocomplete="email" placeholder="Enter your email address" required>
      </div>
      <div class="field">
        <label>Password</label>
        <input id="registerPassword" type="password" autocomplete="new-password" required minlength="8" placeholder="Create a strong password">
      </div>
      <div class="field" style="font-size:.85rem;color:#64748b;line-height:1.45">
        <div><b>Password policy:</b> {PASSWORD_POLICY}</div>
        <ul style="margin:8px 0 0 16px;padding:0;list-style:disc;">
          <li id="passwordRuleLength" data-text="At least 8 characters">○ At least 8 characters</li>
          <li id="passwordRuleUppercase" data-text="At least one uppercase letter">○ At least one uppercase letter</li>
          <li id="passwordRuleSpecial" data-text="At least one special character">○ At least one special character</li>
          <li id="passwordRuleMatch" data-text="Passwords match">○ Passwords match</li>
        </ul>
      </div>
      <div class="field">
        <label>Confirm Password</label>
        <input id="registerConfirm" type="password" autocomplete="new-password" required minlength="8" placeholder="Confirm your password">
      </div>

      <button class="primary" type="submit">Create Account</button>
    </form>
  </section>

  <p class="note">
    Face login requires camera permission. The browser creates a face descriptor
    during registration and sends that numeric descriptor to the Flask server.
    Camera and microphone access normally works on <b>localhost</b> or an
    <b>HTTPS</b> deployment.
  </p>
</div>

<script src="https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js"></script>
<script>
const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";
const statusEl = document.getElementById("status");

function status(message, type="") {
  statusEl.textContent = message;
  statusEl.className = "status " + type;
}

function switchTab(tab) {
  const login = tab === "login";
  document.getElementById("loginTab").classList.toggle("active", login);
  document.getElementById("registerTab").classList.toggle("active", !login);
  document.getElementById("loginPanel").classList.toggle("active", login);
  document.getElementById("registerPanel").classList.toggle("active", !login);
  status("");
}
document.getElementById("loginTab").onclick = () => switchTab("login");
document.getElementById("registerTab").onclick = () => switchTab("register");

const registerPasswordEl = document.getElementById("registerPassword");
const registerConfirmEl = document.getElementById("registerConfirm");
const passwordRuleLength = document.getElementById("passwordRuleLength");
const passwordRuleUppercase = document.getElementById("passwordRuleUppercase");
const passwordRuleSpecial = document.getElementById("passwordRuleSpecial");
const passwordRuleMatch = document.getElementById("passwordRuleMatch");
const registerSubmitButton = document.querySelector("#registerForm button[type='submit']");

function setPasswordRule(element, ok) {
  if (!element) return;
  element.textContent = (ok ? "✓ " : "○ ") + element.dataset.text;
  element.style.color = ok ? "#15803d" : "#64748b";
}

function validateRegisterPasswords() {
  const password = registerPasswordEl.value;
  const confirm = registerConfirmEl.value;
  const isLengthOk = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const passwordsMatch = password !== "" && password === confirm;

  setPasswordRule(passwordRuleLength, isLengthOk);
  setPasswordRule(passwordRuleUppercase, hasUppercase);
  setPasswordRule(passwordRuleSpecial, hasSpecial);
  setPasswordRule(passwordRuleMatch, passwordsMatch);

  if (registerSubmitButton) {
    registerSubmitButton.disabled = !(isLengthOk && hasUppercase && hasSpecial && passwordsMatch);
  }

  return isLengthOk && hasUppercase && hasSpecial && passwordsMatch;
}

if (registerPasswordEl) {
  registerPasswordEl.addEventListener("input", validateRegisterPasswords);
}
if (registerConfirmEl) {
  registerConfirmEl.addEventListener("input", validateRegisterPasswords);
}

validateRegisterPasswords();

let modelsLoaded = false;
let loginStream = null;
let loginVoiceRecognition = null;
let loginVoiceListening = false;

function initLoginVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micBtn = document.getElementById("loginMicBtn");
  const voiceStatus = document.getElementById("loginVoiceStatus");
  if (!SpeechRecognition || !micBtn || !voiceStatus) return;

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 5;
  recognition.lang = "en-IN";

  const SpeechGrammarList = window.SpeechGrammarList || window.webkitSpeechGrammarList;
  if (SpeechGrammarList) {
    const grammar = new SpeechGrammarList();
    grammar.addFromString(
      '#JSGF V1.0; grammar commands; public <command> = username | user name | email | password | pass | submit | sign in | login | log in | clear field | focus password | select password | select username | select email | enter username | enter password ;',
      1
    );
    recognition.grammars = grammar;
  }

  recognition.onstart = () => {
    loginVoiceListening = true;
    micBtn.textContent = "🎙️ Listening...";
    voiceStatus.textContent = "Speak clearly near the microphone.";
  };

  recognition.onend = () => {
    loginVoiceListening = false;
    micBtn.textContent = "🎙️ Voice Input";
    if (!voiceStatus.textContent.includes("typed") && !voiceStatus.textContent.includes("recognized")) {
      voiceStatus.textContent = "Voice input stopped.";
    }
  };

  recognition.onnomatch = () => {
    voiceStatus.textContent = "Could not recognize that speech. Try again.";
  };

  recognition.onerror = (event) => {
    loginVoiceListening = false;
    micBtn.textContent = "🎙️ Voice Input";
    voiceStatus.textContent = "Microphone error: " + event.error;
  };

  function processLoginVoiceCommand(text) {
    const cleaned = text.trim();
    const normalized = cleaned.toLowerCase();
    const loginInput = document.getElementById("loginUsername");
    const passwordInput = document.getElementById("loginPassword");
    const activeElement = document.activeElement && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
      ? document.activeElement
      : loginInput;

    const usernameMatch = normalized.match(/^(?:username|user name|email|login)\s+(.+)$/);
    if (usernameMatch) {
      loginInput.value = usernameMatch[1].trim();
      loginInput.focus();
      loginInput.setSelectionRange(loginInput.value.length, loginInput.value.length);
      voiceStatus.textContent = "Filled username/email from voice.";
      return;
    }

    const passwordMatch = normalized.match(/^(?:password|pass)\s+(.+)$/);
    if (passwordMatch) {
      passwordInput.value = passwordMatch[1].trim();
      passwordInput.focus();
      passwordInput.setSelectionRange(passwordInput.value.length, passwordInput.value.length);
      voiceStatus.textContent = "Filled password from voice.";
      return;
    }

    if (["submit", "sign in", "sign in now", "login", "log in"].includes(normalized)) {
      document.getElementById("loginForm").requestSubmit();
      return;
    }

    if (normalized === "clear field") {
      activeElement.value = "";
      voiceStatus.textContent = "Current field cleared.";
      return;
    }

    const passwordFocusCommands = [
      "focus password",
      "password field",
      "select password",
      "go to password",
      "enter password",
      "password"
    ];

    if (passwordFocusCommands.includes(normalized) || normalized.startsWith("focus password")) {
      passwordInput.focus();
      voiceStatus.textContent = "Focused password field.";
      return;
    }

    const usernameFocusCommands = [
      "focus username",
      "username field",
      "select username",
      "go to username",
      "enter username",
      "focus email",
      "email field",
      "select email",
      "go to email",
      "enter email",
      "username",
      "email"
    ];

    if (usernameFocusCommands.includes(normalized) || normalized.startsWith("focus username") || normalized.startsWith("select username") || normalized.startsWith("go to username") || normalized.startsWith("enter username") || normalized.startsWith("select email") || normalized.startsWith("go to email") || normalized.startsWith("enter email")) {
      loginInput.focus();
      voiceStatus.textContent = "Focused username/email field.";
      return;
    }

    activeElement.value = cleaned;
    activeElement.focus();
    activeElement.setSelectionRange(activeElement.value.length, activeElement.value.length);
    voiceStatus.textContent = "Voice typed into the active field.";
  }

  recognition.onresult = (event) => {
    let finalText = "";
    let interimText = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const best = result[0] && result[0].transcript ? result[0].transcript.trim() : "";
      if (result.isFinal) {
        finalText += best ? best + " " : "";
      } else {
        interimText += best ? best + " " : "";
      }
    }

    if (interimText) {
      voiceStatus.textContent = "Listening: " + interimText.trim();
    }

    if (finalText.trim()) {
      processLoginVoiceCommand(finalText.trim());
    }
  };

  micBtn.onclick = () => {
    if (loginVoiceListening) {
      recognition.stop();
      return;
    }
    try {
      recognition.start();
    } catch (err) {
      voiceStatus.textContent = "Could not start microphone access: " + err.message;
    }
  };

  loginVoiceRecognition = recognition;
}

initLoginVoiceInput();

async function loadFaceModels() {
  if (modelsLoaded) return;
  status("Loading face recognition models...");
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
    faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
    faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL)
  ]);
  modelsLoaded = true;
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function computeEyeAspectRatio(landmarks, eyeIndices) {
  const points = eyeIndices.map(index => landmarks.positions[index]);
  const vertical1 = distance(points[1], points[5]);
  const vertical2 = distance(points[2], points[4]);
  const horizontal = distance(points[0], points[3]);
  return (vertical1 + vertical2) / (2 * (horizontal || 1));
}

async function getFaceDescriptor(video) {
  const result = await faceapi
    .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions({
      inputSize: 320,
      scoreThreshold: 0.5
    }))
    .withFaceLandmarks()
    .withFaceDescriptor();

  if (!result) throw new Error("No face detected. Look directly at the camera.");
  return Array.from(result.descriptor);
}

async function waitForBlink(video, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  let closedFrames = 0;
  let openFrames = 0;
  let sawClosed = false;

  while (Date.now() < deadline) {
    const result = await faceapi
      .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions({
        inputSize: 320,
        scoreThreshold: 0.5
      }))
      .withFaceLandmarks();

    if (!result) {
      closedFrames = 0;
      openFrames = 0;
      sawClosed = false;
      status("Face not detected. Keep your face in the frame.");
      await new Promise(resolve => setTimeout(resolve, 150));
      continue;
    }

    const landmarks = result.landmarks;
    const leftEar = computeEyeAspectRatio(landmarks, [36, 37, 38, 39, 40, 41]);
    const rightEar = computeEyeAspectRatio(landmarks, [42, 43, 44, 45, 46, 47]);
    const avgEar = (leftEar + rightEar) / 2;

    if (avgEar < 0.28) {
      closedFrames += 1;
      openFrames = 0;
      if (closedFrames >= 4) {
        sawClosed = true;
        status("Eyes closed. Open them to finish the blink.");
      }
    } else if (sawClosed) {
      openFrames += 1;
      if (openFrames >= 3) {
        return;
      }
    } else {
      closedFrames = 0;
      openFrames = 0;
    }

    await new Promise(resolve => setTimeout(resolve, 150));
  }

  throw new Error("No blink detected. Blink once to confirm face login.");
}

async function startCamera(video, box) {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { width: 640, height: 480, facingMode: "user" },
    audio: false
  });
  video.srcObject = stream;
  box.style.display = "block";
  await new Promise(resolve => video.onloadedmetadata = resolve);
  await video.play();
  return stream;
}

async function stopStream(stream) {
  if (stream) stream.getTracks().forEach(t => t.stop());
}

document.getElementById("registerForm").addEventListener("submit", async e => {
  e.preventDefault();

  const username = document.getElementById("registerUsername").value.trim();
  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;
  const confirm = document.getElementById("registerConfirm").value;

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    status("Please enter a valid email address.", "error");
    return;
  }

  if (password !== confirm) {
    status("Passwords do not match.", "error");
    return;
  }

  try {
    await loadFaceModels();

    status("Account details accepted. Opening camera...");
    const hiddenVideo = document.createElement("video");
    hiddenVideo.autoplay = true;
    hiddenVideo.muted = true;
    hiddenVideo.playsInline = true;
    hiddenVideo.style.position = "fixed";
    hiddenVideo.style.left = "-9999px";
    document.body.appendChild(hiddenVideo);

    const stream = await startCamera(hiddenVideo, {style:{display:"none"}});
    status("Camera ready. Keep your face visible...");
    await new Promise(r => setTimeout(r, 1200));
    const descriptor = await getFaceDescriptor(hiddenVideo);
    await stopStream(stream);
    hiddenVideo.remove();

    const response = await fetch("/api/register", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({username, email, password, face_descriptor:descriptor})
    });
    const data = await response.json();

    if (!response.ok) throw new Error(data.message || "Registration failed.");
    status("Account created. Redirecting...", "success");
    window.location.href = "/profile";
  } catch (err) {
    status(err.message || String(err), "error");
  }
});

document.getElementById("loginForm").addEventListener("submit", async e => {
  e.preventDefault();

  try {
    const identifier = document.getElementById("loginUsername").value.trim();
    const response = await fetch("/api/login", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        identifier,
        username:identifier,
        password:document.getElementById("loginPassword").value
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Login failed.");
    window.location.href = "/profile";
  } catch (err) {
    status(err.message || String(err), "error");
  }
});

document.getElementById("forgotPasswordToggle").addEventListener("click", () => {
  const form = document.getElementById("forgotPasswordForm");
  form.classList.toggle("hidden");
  if (!form.classList.contains("hidden")) {
    document.getElementById("resetIdentifier").focus();
  }
});

document.getElementById("forgotPasswordForm").addEventListener("submit", async e => {
  e.preventDefault();

  const identifier = document.getElementById("resetIdentifier").value.trim();
  const password = document.getElementById("resetPassword").value;
  const confirm = document.getElementById("resetConfirm").value;

  if (password !== confirm) {
    status("Passwords do not match.", "error");
    return;
  }

  try {
    const response = await fetch("/api/reset-password", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({identifier, password})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Password reset failed.");
    status("Password updated successfully. You can now sign in.", "success");
    document.getElementById("forgotPasswordForm").classList.add("hidden");
    document.getElementById("loginUsername").value = identifier;
    document.getElementById("loginPassword").value = "";
    document.getElementById("resetIdentifier").value = "";
    document.getElementById("resetPassword").value = "";
    document.getElementById("resetConfirm").value = "";
  } catch (err) {
    status(err.message || String(err), "error");
  }
});

document.getElementById("faceLoginBtn").addEventListener("click", async () => {
  const username = document.getElementById("loginUsername").value.trim();

  try {
    await loadFaceModels();

    const box = document.getElementById("loginCamera");
    const video = document.getElementById("loginVideo");
    loginStream = await startCamera(video, box);

    status("Look at the camera and blink once...");
    await waitForBlink(video);
    status("Blink detected. Verifying face...");

    const descriptor = await getFaceDescriptor(video);

    const response = await fetch("/api/face-login", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({identifier:username, username, face_descriptor:descriptor})
    });
    const data = await response.json();

    await stopStream(loginStream);
    loginStream = null;
    box.style.display = "none";

    if (!response.ok) throw new Error(data.message || "Face login failed.");

    status("Face matched. Redirecting...", "success");
    window.location.href = "/profile";
  } catch (err) {
    await stopStream(loginStream);
    loginStream = null;
    document.getElementById("loginCamera").style.display = "none";
    status(err.message || String(err), "error");
  }
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PROFILE PAGE
# ---------------------------------------------------------------------------

PROFILE_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profile</title>
<style>
:root{
  --primary:#2563eb;--bg:#f1f5f9;--card:#fff;--text:#172033;
  --muted:#64748b;--border:#dbe3ef;--danger:#dc2626
}
*{box-sizing:border-box}
body{
  margin:0;background:var(--bg);color:var(--text);font-family:system-ui,Arial;
  padding:25px
}
.container{
  max-width:760px;margin:auto;background:var(--card);padding:30px;
  border-radius:20px;box-shadow:0 15px 45px rgba(15,23,42,.1)
}
.header{display:flex;justify-content:space-between;align-items:center;gap:12px}
.logout{background:#fee2e2;color:#b91c1c;border:0;border-radius:10px;padding:10px 15px;font-weight:800}
.section{margin-top:24px;padding-top:20px;border-top:1px solid var(--border)}
h1{margin:0}.muted{color:var(--muted)}
.field{margin:15px 0}
label{display:block;font-weight:700;margin-bottom:7px}
input,textarea,select{
  width:100%;padding:12px;border:1px solid var(--border);border-radius:10px;
  font:inherit;background:white
}
textarea{resize:vertical}
button{
  border:0;border-radius:10px;padding:11px 16px;font-weight:800;cursor:pointer
}
.primary{background:var(--primary);color:white}
.secondary{background:#e2e8f0;color:#172033}
.danger{background:#fee2e2;color:#b91c1c}
.camera-wrap{max-width:480px;margin:auto}
.camera-box{background:#000;border-radius:15px;overflow:hidden}
video,canvas{width:100%;display:block}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
.controls button{flex:1}
.preview{
  width:110px;height:110px;border-radius:50%;object-fit:cover;
  border:4px solid #e2e8f0;margin:12px auto;display:block
}
.voice{
  display:flex;gap:12px;align-items:center;background:#eff6ff;padding:14px;
  border-radius:14px
}
.mic{
  width:52px;height:52px;border-radius:50%;background:#fff;
  border:2px solid #94a3b8;font-size:1.25rem
}
.mic.listening{background:#ef4444;color:white;border-color:#ef4444}
.voiceText{flex:1;color:#475569}
.status{min-height:22px;margin:10px 0;font-weight:600}
.success{color:#15803d}.error{color:#dc2626}
.guide{background:#f8fafc;padding:14px;border-radius:12px;color:#475569;font-size:.9rem}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>My Profile</h1>
      <div class="muted">Signed in as <b>{{ username }}</b></div>
    </div>
    <button class="logout" id="logout">Logout</button>
  </div>

  <div class="section">
    <h2> Profile Picture</h2>
    {% if photo_url %}
      <img class="preview" id="currentPhoto" src="{{ photo_url }}" alt="Profile picture">
    {% else %}
      <img class="preview" id="currentPhoto" style="display:none" alt="Profile picture">
    {% endif %}

    <div class="camera-wrap">
      <div class="camera-box">
        <video id="camera" autoplay muted playsinline></video>
        <canvas id="canvas" class="hidden"></canvas>
      </div>
      <div class="controls">
        <button class="primary" id="takePhoto" type="button">Take Photo</button>
        <button class="secondary" id="retake" type="button" disabled>Retake</button>
        <button class="primary" id="upload" type="button" disabled>Save Photo</button>
      </div>
      <div id="cameraStatus" class="status"></div>
    </div>
  </div>

  <div class="section">
    <h2>Voice-to-Text</h2>
    <div class="voice">
      <button class="mic" id="mic" type="button"> 🎙️</button>
      <div class="voiceText" id="voiceText">Click the microphone and speak to dictate text.
      </div>
    </div>
    <div id="voiceStatus" class="status"></div>
  </div>

  <div class="section">
    <h2>Profile Information</h2>

    <form id="profileForm">
      <div class="field">
        <label>Full Name</label>
        <input id="full_name" name="full_name" value="{{ profile.full_name or '' }}" required>
      </div>

      <div class="field">
        <label>Contact Phone</label>
        <input id="contact_phone" name="contact_phone" value="{{ profile.contact_phone or '' }}" required>
      </div>

      <div class="field">
        <label>Email Address</label>
        <input id="email_address" name="email_address" type="email"
               value="{{ profile.email_address or '' }}" required>
      </div>

      <div class="field">
        <label>Date of Birth</label>
        <input id="dob" name="dob" type="date" value="{{ profile.dob or '' }}" required>
      </div>

      <div class="field">
        <label>Physical Address</label>
        <textarea id="physical_address" name="physical_address" rows="3" required>{{ profile.physical_address or '' }}</textarea>
      </div>

      <div class="field">
        <label>Accessibility Mode</label>
        <select id="accessibility_mode" name="accessibility_mode">
          <option value="default" {% if profile.accessibility_mode == "default" %}selected{% endif %}>Default</option>
          <option value="high-contrast" {% if profile.accessibility_mode == "high-contrast" %}selected{% endif %}>High Contrast</option>
          <option value="large-text" {% if profile.accessibility_mode == "large-text" %}selected{% endif %}>Large Text</option>
        </select>
      </div>

      <button class="primary" type="submit">Save Profile</button>
      <div id="profileStatus" class="status"></div>
    </form>
  </div>

  <div class="section guide">
    <b>Voice commands:</b>
    <ul>
      <li>"Select full name"</li>
      <li>"Select phone"</li>
      <li>"Select email"</li>
      <li>"Select date of birth"</li>
      <li>"Select address"</li>
      <li>"Clear field"</li>
      <li>"Delete last word"</li>
      <li>"Next field"</li>
      <li>"Submit profile"</li>
      <li>"Logout"</li>
    </ul>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);

function setStatus(id, text, ok=false) {
  $(id).textContent = text;
  $(id).className = "status " + (ok ? "success" : "error");
}

/* ---------------- PROFILE SAVE ---------------- */
$("profileForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const response = await fetch("/submit-profile", {
      method:"POST",
      body:new FormData(e.target)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Could not save profile.");
    setStatus("profileStatus", "Profile saved successfully.", true);
  } catch (err) {
    setStatus("profileStatus", err.message || String(err));
  }
});

/* ---------------- LOGOUT ---------------- */
$("logout").onclick = () => {
  stopCamera();
  window.location.href = "/logout";
};

/* ---------------- CAMERA PROFILE PHOTO ---------------- */
let stream = null;
let imageBlob = null;

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video:{width:640,height:480,facingMode:"user"},
      audio:false
    });
    $("camera").srcObject = stream;
    $("takePhoto").disabled = false;
    setStatus("cameraStatus", "Camera is ready. Position your face in the frame.", true);
  } catch (err) {
    setStatus("cameraStatus", "Camera permission failed: " + err.message);
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach(track => track.stop());
    stream = null;
  }
}

$("takePhoto").onclick = async () => {
  if (!stream) {
    try {
      await startCamera();
      setStatus("cameraStatus", "Camera is ready. Click Take Photo again to capture.", true);
      return;
    } catch (err) {
      setStatus("cameraStatus", "Camera permission failed: " + err.message);
      return;
    }
  }

  const video = $("camera");
  const canvas = $("canvas");

  if (!video.videoWidth) return;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video,0,0,canvas.width,canvas.height);

  canvas.toBlob(blob => {
    imageBlob = blob;
    stopCamera();
    $("retake").disabled = false;
    $("upload").disabled = false;
    $("takePhoto").disabled = true;
    setStatus("cameraStatus", "Photo captured. Camera stopped.", true);
  }, "image/jpeg", .88);
};

$("retake").onclick = () => {
  imageBlob = null;
  $("upload").disabled = true;
  $("takePhoto").disabled = !stream;
  $("canvas").getContext("2d").clearRect(0,0,$("canvas").width,$("canvas").height);
  setStatus("cameraStatus", "Ready for another photo.", true);
};

$("upload").onclick = async () => {
  if (!imageBlob) return;

  if (imageBlob.size > 2 * 1024 * 1024) {
    setStatus("cameraStatus", "Photo is larger than 2MB. Retake it with better lighting.");
    return;
  }

  const fd = new FormData();
  fd.append("photo", imageBlob, "profile.jpg");

  try {
    const response = await fetch("/api/upload-photo", {
      method:"POST", body:fd
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Upload failed.");

    $("currentPhoto").src = data.url + "?t=" + Date.now();
    $("currentPhoto").style.display = "block";
    stopCamera();
    setStatus("cameraStatus", "Profile picture saved.", true);
  } catch (err) {
    setStatus("cameraStatus", err.message || String(err));
  }
};

/* ---------------- VOICE TO TEXT ---------------- */
const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition = null;
let listening = false;

if (!SpeechRecognition) {
  setStatus("voiceStatus",
    "Speech recognition is not supported by this browser. Try Chrome or Edge.");
  $("mic").disabled = true;
} else {
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-IN";

  $("mic").onclick = () => {
    if (listening) recognition.stop();
    else {
      try { recognition.start(); }
      catch (e) {}
    }
  };

  recognition.onstart = () => {
    listening = true;
    $("mic").classList.add("listening");
    $("voiceText").textContent = "Listening...";
    setStatus("voiceStatus", "Speak now.", true);
  };

  recognition.onend = () => {
    listening = false;
    $("mic").classList.remove("listening");
    if ($("voiceStatus").textContent === "Speak now.")
      setStatus("voiceStatus", "Microphone stopped.", true);
  };

  recognition.onerror = event => {
    listening = false;
    $("mic").classList.remove("listening");
    setStatus("voiceStatus", "Voice error: " + event.error);
  };

  recognition.onresult = event => {
    let finalText = "";
    let interimText = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += text;
      else interimText += text;
    }

    $("voiceText").textContent = interimText || finalText;

    if (finalText.trim()) {
      processVoiceCommand(finalText.trim().toLowerCase());
    }
  };
}

const fieldMap = {
  "full name":"full_name",
  "name":"full_name",
  "phone":"contact_phone",
  "contact phone":"contact_phone",
  "email":"email_address",
  "email address":"email_address",
  "date of birth":"dob",
  "dob":"dob",
  "address":"physical_address",
  "physical address":"physical_address",
  "accessibility mode":"accessibility_mode"
};

function currentField() {
  const el = document.activeElement;
  return el && ["INPUT","TEXTAREA","SELECT"].includes(el.tagName) ? el : null;
}

function saveCurrentField() {
  const f = currentField();
  if (f) localStorage.setItem("profile_" + f.name, f.value);
}

function processVoiceCommand(command) {
  const cleaned = command.replace(/[.!?]+$/,"").trim();

  if (cleaned === "logout" || cleaned === "log out") {
    $("logout").click();
    return;
  }

  if (cleaned === "submit profile" || cleaned === "save profile") {
    $("profileForm").requestSubmit();
    return;
  }

  if (cleaned === "clear field") {
    const f = currentField();
    if (f) {
      f.value = "";
      saveCurrentField();
      f.dispatchEvent(new Event("input",{bubbles:true}));
    }
    return;
  }

  if (cleaned === "delete last word") {
    const f = currentField();
    if (f && "value" in f) {
      f.value = f.value.trim().split(/\s+/).slice(0,-1).join(" ");
      saveCurrentField();
      f.dispatchEvent(new Event("input",{bubbles:true}));
    }
    return;
  }

  if (cleaned === "next field") {
    const fields = Array.from($("profileForm").querySelectorAll("input,textarea,select"));
    const current = currentField();
    const index = fields.indexOf(current);
    fields[(index + 1) % fields.length].focus();
    return;
  }

  let selectMatch = cleaned.match(/^select (.+)$/);
  if (selectMatch) {
    const name = selectMatch[1];
    if (fieldMap[name]) {
      $(fieldMap[name]).focus();
      return;
    }
  }

  const fieldPhraseMap = [
    { pattern: /^my name is(?:\s+(.+))?$/i, fieldId: "full_name" },
    { pattern: /^my full name is(?:\s+(.+))?$/i, fieldId: "full_name" },
    { pattern: /^my (?:contact|phone|mobile|cell) number is(?:\s+(.+))?$/i, fieldId: "contact_phone" },
    { pattern: /^my (?:contact|phone|mobile|cell) is(?:\s+(.+))?$/i, fieldId: "contact_phone" },
    { pattern: /^my telephone number is(?:\s+(.+))?$/i, fieldId: "contact_phone" },
    { pattern: /^my email is(?:\s+(.+))?$/i, fieldId: "email_address" },
    { pattern: /^my email address is(?:\s+(.+))?$/i, fieldId: "email_address" },
    { pattern: /^my email id is(?:\s+(.+))?$/i, fieldId: "email_address" },
    { pattern: /^my address is(?:\s+(.+))?$/i, fieldId: "physical_address" },
    { pattern: /^my physical address is(?:\s+(.+))?$/i, fieldId: "physical_address" },
    { pattern: /^my residential address is(?:\s+(.+))?$/i, fieldId: "physical_address" },
    { pattern: /^my date of birth is(?:\s+(.+))?$/i, fieldId: "dob" },
    { pattern: /^my dob is(?:\s+(.+))?$/i, fieldId: "dob" },
    { pattern: /^my birth date is(?:\s+(.+))?$/i, fieldId: "dob" }
  ];

  for (const entry of fieldPhraseMap) {
    const match = cleaned.match(entry.pattern);
    if (match) {
      const field = $(entry.fieldId);
      field.focus();
      if (match[1]) {
        const rawName = match[1].trim();
        field.value = rawName
          .split(/\s+/)
          .filter(Boolean)
          .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
          .join(' ');
      }
      if (field.tagName === "INPUT" && field.type === "date") {
        const digits = field.value.replace(/\D/g, "");
        if (digits.length === 8) {
          field.value = digits.slice(0,4) + "-" + digits.slice(4,6) + "-" + digits.slice(6,8);
        }
      }
      field.setSelectionRange(field.value.length, field.value.length);
      saveCurrentField();
      field.dispatchEvent(new Event("input", {bubbles:true}));
      return;
    }
  }

  const f = currentField();
  if (!f) return;

  if (f.tagName === "SELECT") {
    for (const option of f.options) {
      if (option.text.toLowerCase().includes(cleaned)) {
        f.value = option.value;
        saveCurrentField();
        return;
      }
    }
  } else if (f.type === "date") {
    // Say dates in a simple format such as "20 05 2000".
    const digits = cleaned.replace(/\D/g,"");
    if (digits.length === 8) {
      const day = digits.slice(0,2);
      const month = digits.slice(2,4);
      const year = digits.slice(4,8);
      f.value = `${year}-${month}-${day}`;
      saveCurrentField();
    }
  } else {
    f.value = (f.value ? f.value + " " : "") + cleaned;
    saveCurrentField();
  }
}

/* Restore locally saved values after refresh. */
document.querySelectorAll("#profileForm input,#profileForm textarea,#profileForm select")
.forEach(el => {
  const saved = localStorage.getItem("profile_" + el.name);
  if (saved !== null && !el.value) el.value = saved;
  el.addEventListener("input", saveCurrentField);
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("profile_page" if require_login() else "login_page"))


@app.route("/login")
def login_page():
    if require_login():
        return redirect(url_for("profile_page"))
    return render_template_string(LOGIN_HTML)


@app.route("/api/register", methods=["POST"])
def register_api():
    data = request.get_json(silent=True) or {}

    username = clean_username(str(data.get("username", "")))
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    descriptor = data.get("face_descriptor")

    if len(username) < 3:
        return jsonify(message="Username must contain at least 3 valid characters."), 400

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify(message=message), 400

    if not EMAIL_PATTERN.fullmatch(email):
        return jsonify(message="Please provide a valid email address."), 400

    if username in USERS:
        return jsonify(message="Username already exists. Please sign in instead."), 409

    existing_email = next(
        (user.get("email") for user in USERS.values() if user.get("email") == email),
        None,
    )
    if existing_email:
        return jsonify(message="An account with this email already exists."), 409

    if not isinstance(descriptor, list) or len(descriptor) != 128:
        return jsonify(message="A valid face descriptor was not received."), 400

    if any(not isinstance(x, (int, float)) for x in descriptor):
        return jsonify(message="Invalid face descriptor."), 400

    USERS[username] = {
        "password_hash": generate_password_hash(password),
        "email": email,
        "face_descriptor": [float(x) for x in descriptor],
        "profile": {"email_address": email}
    }
    save_users(USERS)

    session.clear()
    session["authenticated"] = True
    session["username"] = username

    return jsonify(status="success", message="Account created.")


@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier") or data.get("username") or data.get("email") or ""
    password = str(data.get("password", ""))

    resolved = find_user_by_identifier(identifier)
    if not resolved:
        return jsonify(message="Account not found. Please register first."), 404

    username, user = resolved
    if not check_password_hash(user.get("password_hash", ""), password):
        return jsonify(message="Incorrect username or password."), 401

    session.clear()
    session["authenticated"] = True
    session["username"] = username

    return jsonify(status="success")


@app.route("/api/reset-password", methods=["POST"])
def reset_password_api():
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier") or data.get("username") or data.get("email") or ""
    password = str(data.get("password", ""))

    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify(message=message), 400

    resolved = find_user_by_identifier(identifier)
    if not resolved:
        return jsonify(message="No account found for that username or email."), 404

    username, user = resolved
    user["password_hash"] = generate_password_hash(password)
    save_users(USERS)

    return jsonify(status="success", message="Password updated successfully.")


@app.route("/api/face-login", methods=["POST"])
def face_login():
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier") or data.get("username") or data.get("email") or ""
    descriptor = data.get("face_descriptor")

    if not isinstance(descriptor, list) or len(descriptor) != 128:
        return jsonify(message="A valid face descriptor was not received."), 400

    if any(not isinstance(x, (int, float)) for x in descriptor):
        return jsonify(message="Invalid face descriptor."), 400

    candidates = []
    if identifier:
        resolved = find_user_by_identifier(identifier)
        if resolved:
            candidates.append(resolved)
        else:
            return jsonify(message="Account not found."), 404
    else:
        candidates = [(name, user) for name, user in USERS.items() if isinstance(user.get("face_descriptor"), list)]

    if not candidates:
        return jsonify(message="Account not found."), 404

    matched_user = None
    best_distance = None

    for candidate_username, user in candidates:
        saved_descriptor = user.get("face_descriptor")
        if not isinstance(saved_descriptor, list):
            continue

        distance = face_distance(descriptor, saved_descriptor)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            matched_user = (candidate_username, distance)

    if not matched_user:
        return jsonify(message="No face is registered for this account."), 400

    if best_distance > FACE_THRESHOLD:
        return jsonify(
            message="Face did not match. Try again with better lighting and face the camera."
        ), 401

    session.clear()
    session["authenticated"] = True
    session["username"] = matched_user[0]

    return jsonify(status="success", distance=round(best_distance, 4), username=matched_user[0])


@app.route("/profile")
def profile_page():
    if not require_login():
        return redirect(url_for("login_page"))

    username = session["username"]
    user = USERS.get(username, {})
    return render_template_string(
        PROFILE_HTML,
        username=username,
        profile=user.get("profile", {}),
        photo_url=photo_url(username)
    )
@app.route("/api/check-blink", methods=["POST"])
def api_check_blink():
    """
    FR-4 / Face Enrollment blink check.

    The browser sends one camera frame at a time.
    The server stores the eye state in the user's Flask session.

    A blink is detected when the sequence is:

        OPEN -> CLOSED -> OPEN
    """

    photo = request.files.get("photo")

    if not photo:
        return jsonify({
            "status": "error",
            "message": "No face photo provided."
        }), 400

    try:
        frame = decode_photo_frame(photo)

        ear = get_eye_aspect_ratio(frame)

        if ear is None:
            return jsonify({
                "status": "success",
                "blink_detected": False,
                "eye_state": "unknown"
            })

        eyes_closed = ear < BLINK_EAR_THRESHOLD

        # Get the previous state from the current browser session.
        previous_state = session.get("blink_eye_state", "unknown")

        blink_detected = False

        # ------------------------------------------------------------
        # OPEN -> CLOSED
        # ------------------------------------------------------------
        if previous_state == "open" and eyes_closed:
            session["blink_eye_state"] = "closed"

        # ------------------------------------------------------------
        # CLOSED -> OPEN
        # This completes the blink.
        # ------------------------------------------------------------
        elif previous_state == "closed" and not eyes_closed:
            blink_detected = True

            # Reset so another blink can be detected if necessary.
            session["blink_eye_state"] = "open"

        # ------------------------------------------------------------
        # First frame / already open
        # ------------------------------------------------------------
        elif not eyes_closed:
            session["blink_eye_state"] = "open"

        # ------------------------------------------------------------
        # Still closed
        # ------------------------------------------------------------
        elif eyes_closed:
            session["blink_eye_state"] = "closed"

        session.modified = True

        return jsonify({
            "status": "success",
            "blink_detected": blink_detected,
            "eye_state": "closed" if eyes_closed else "open",
            "ear": round(float(ear), 3)
        })

    except ValueError as exc:
        return jsonify({
            "status": "error",
            "message": str(exc)
        }), 400

    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": f"Unable to detect blink: {exc}"
        }), 400

@app.route("/submit-profile", methods=["POST"])
def submit_profile():
    if not require_login():
        return jsonify(status="error", message="Unauthorized"), 401

    username = session["username"]
    profile = {
        field: request.form.get(field, "").strip()
        for field in PROFILE_FIELDS
    }

    USERS[username]["profile"] = profile
    save_users(USERS)

    return jsonify(
        status="success",
        message="Profile saved successfully.",
        data=profile
    )


@app.route("/api/upload-photo", methods=["POST"])
def upload_photo():
    if not require_login():
        return jsonify(status="error", message="Unauthorized"), 401

    photo = request.files.get("photo")
    if not photo:
        return jsonify(status="error", message="No photo received."), 400

    data = photo.read()
    if len(data) > MAX_PHOTO_BYTES:
        return jsonify(status="error", message="Photo exceeds the 2MB limit."), 413

    # Browser sends JPEG. Validate basic JPEG signature.
    if not data.startswith(b"\xff\xd8"):
        return jsonify(status="error", message="Please upload a JPEG camera image."), 400

    path = UPLOAD_FOLDER / photo_filename(session["username"])
    path.write_bytes(data)

    return jsonify(status="success", url=photo_url(session["username"]))


@app.route("/photo/<username>")
def get_photo(username):
    if not require_login() or username != session.get("username"):
        return redirect(url_for("login_page"))

    return send_from_directory(
        UPLOAD_FOLDER,
        photo_filename(username)
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
