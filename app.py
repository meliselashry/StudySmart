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
    Fetches title and vocab with a robust parser.
    """
    # Updated prompt to ensure actual Tab characters are used
    prompt = """
        You are a strict data formatter. Extract vocabulary from the text.
        RULES:
        1. Format: Term [TAB] Definition
        2. Do NOT use the words "Definition:" or "Term:" or "Meaning:".
        3. Use ONLY a single Tab character between the term and the definition.
        4. One pair per line.

        GOOD EXAMPLE:
        Photosynthesis	The process by which plants make food using sunlight.
        Mitochondria	The powerhouse of the cell.

        BAD EXAMPLE (DO NOT DO THIS):
        Term: Photosynthesis - Definition: The process by which...

        TEXT TO PROCESS:
        """
    content = [{"type": "text", "text": prompt}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}]
    )
    
    full_text = response.choices[0].message.content.strip()
    print(f"--- AI RAW RESPONSE ---\n{full_text}\n-----------------------")

    title = "Class Vocabulary"
    vocab = ""

    if "TITLE:" in full_text:
        try:
            title_match = full_text.split("TITLE:")[1].split("VOCAB:")[0].strip()
            if title_match:
                title = title_match
        except:
            pass
    
    if "VOCAB:" in full_text:
        vocab = full_text.split("VOCAB:")[1].strip()
    else:
        vocab = full_text

    vocab = vocab.replace("```text", "").replace("```", "").strip()
    return vocab, title

# --- BROWSER ROBOT ---
def send_vocab_to_quizlet(vocab_text: str, smart_title: str):
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        # FIXED URL: Removed markdown formatting
        page.goto("https://quizlet.com/create-set")
        
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
            vocab, title = make_vocab_data_combined(image_data_urls)
            
            if not vocab or len(vocab) < 3:
                return jsonify({"error": "The AI couldn't find vocabulary. Try a clearer photo."}), 500
                
            return jsonify({"vocab": vocab, "title": title})
        else:
            result = make_summary_from_image(image_data_urls)
            return jsonify({"result": result})
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
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
    port = int(os.environ.get("PORT", 5011))
    app.run(host='0.0.0.0', port=port)