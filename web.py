from flask import Flask, jsonify, request, send_from_directory
import random
import string
import time
from threading import Lock
import os

app = Flask(__name__, static_folder="dist", static_url_path="")

# Słownik do przechowywania kodów weryfikacyjnych
verification_data = {}
lock = Lock()
EXPIRATION_TIME = 5 * 60  # 5 minut

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@app.route("/api/code")
def get_code():
    verification_id = request.args.get("id")
    if not verification_id:
        return jsonify({"error": "Missing id"}), 400

    with lock:
        now = time.time()
        # Czy istnieje już kod?
        if verification_id in verification_data:
            code, timestamp = verification_data[verification_id]
            # Jeżeli nie wygasł
            if now - timestamp < EXPIRATION_TIME:
                return jsonify({"code": code})
        
        # Wygeneruj nowy kod
        code = generate_code()
        verification_data[verification_id] = (code, now)
        return jsonify({"code": code})

@app.route("/")
def root():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
