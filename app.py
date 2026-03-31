from flask import Flask, request, jsonify, render_template
from openai import OpenAI
from playwright.sync_api import sync_playwright
import nest_asyncio
import base64
import mimetypes
import os
import re
from dotenv import load_dotenv

# --- INITIAL SETUP ---
load_dotenv()
app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Quizlet setup for Render (using /tmp for temporary storage)
USER_DATA_DIR = "/tmp/quizlet_user_data"
nest_asyncio.apply()

# --- HELPER: IMAGE TRANSLATOR ---
def encode_image_to_data_url(file_bytes: bytes, filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "image/jpeg"
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

# --- AI BRAIN METHODS ---

def make_summary_from_image(image_data_urls: list) -> str:
    """Creates detailed study notes from images."""
    prompt = "Turn these classroom images into clean study notes."
    content = [{"type": "text", "text": prompt}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}]
    )
    return response.choices[0].message.content

def make_vocab_data_combined(image_data_urls: list):
    """
    Fetches BOTH vocab and title in one AI call.
    This is much faster and prevents 'Connection Failed' timeouts on Render.
    """
    prompt = """Analyze these images and provide:
    1. A short, specific title (e.g., 'Parts of the Human Cell').
    2. Important vocabulary terms and definitions.
    
    Format your response EXACTLY like this:
    TITLE: [Insert Title Here]
    VOCAB:
    term1<TAB>definition1
    term2<TAB>definition2
    """
    content = [{"type": "text", "text": prompt}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}]
    )
    
    full_text = response.choices[0].message.content
    
    # Split the Title and the Vocab list from the AI's single response
    try:
        title = full_text.split("TITLE:")[1].split("VOCAB:")[0].strip()
        vocab = full_text.split("VOCAB:")[1].strip()
        return vocab, title
    except Exception:
        # Fallback if AI messes up the format
        return full_text, "Class Vocabulary"

# --- BROWSER ROBOT ---
def send_vocab_to_quizlet(vocab_text: str, smart_title: str):
    pw = sync_playwright().start()
    try:
        # Headless must be True for Render servers
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto("https://quizlet.com/create-set")
        
        # Note: If Quizlet asks for a login, a headless browser on a server 
        # may get stuck. This is a best-effort automation.
        page.wait_for_selector("input[name='title']", timeout=10000)
        page.fill("input[name='title']", smart_title)
        
        page.click("text='Import'")
        page.fill("textarea[aria-label='Import']", vocab_text)
        page.click("button:has-text('Import')")
        
        browser.close()
    except Exception as e:
        print(f"Quizlet Robot Error: {e}")
    finally:
        pw.stop()

# --- WEBSITE ROUTES ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    images = request.files.getlist("image")
    if not images or images[0].filename == "":
        return jsonify({"error": "No images selected"}), 400
    
    mode = request.form.get("mode", "summary")
    image_data_urls = []
    for img in images:
        image_data_urls.append(encode_image_to_data_url(img.read(), img.filename))

    try:
        if mode == "vocab_list":
            # Running the combined function to save time and prevent timeouts
            vocab, title = make_vocab_data_combined(image_data_urls)
            return jsonify({"vocab": vocab, "title": title})
        else:
            result = make_summary_from_image(image_data_urls)
            return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/run_quizlet", methods=["POST"])
def run_quizlet():
    data = request.json
    try:
        send_vocab_to_quizlet(data.get("vocab"), data.get("title"))
        return jsonify({"message": "Automation Complete! Check your Quizlet."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Ensure port is pulled from environment for Render compatibility
    port = int(os.environ.get("PORT", 5011))
    app.run(host='0.0.0.0', port=port)