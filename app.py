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
    Fetches title and vocab with a robust parser to prevent empty tables.
    """
    prompt = """Analyze these images and extract vocabulary.
    
    Format your response EXACTLY like this:
    TITLE: [Insert Title Here]
    VOCAB:
    term<TAB>definition
    
    Do not include any other text, greetings, or markdown formatting (like ```).
    """
    content = [{"type": "text", "text": prompt}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}]
    )
    
    full_text = response.choices[0].message.content.strip()
    
    # DEBUG: This will show up in your Render logs so you can see if the AI is behaving
    print(f"--- AI RAW RESPONSE ---\n{full_text}\n-----------------------")

    title = "Class Vocabulary"
    vocab = ""

    # 1. Robust Title Extraction
    if "TITLE:" in full_text:
        try:
            # Get everything between TITLE: and VOCAB:
            title_match = full_text.split("TITLE:")[1].split("VOCAB:")[0].strip()
            if title_match:
                title = title_match
        except:
            pass
    
    # 2. Robust Vocab Extraction
    if "VOCAB:" in full_text:
        vocab = full_text.split("VOCAB:")[1].strip()
    else:
        # Safety net: If AI forgets 'VOCAB:', assume the whole response is the list
        vocab = full_text

    # Clean up any leftover markdown code blocks if the AI ignored instructions
    vocab = vocab.replace("```text", "").replace("```", "").strip()

    return vocab, title

# --- BROWSER ROBOT ---
def send_vocab_to_quizlet(vocab_text: str, smart_title: str):
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto("[https://quizlet.com/create-set](https://quizlet.com/create-set)")
        
        # Wait up to 10 seconds for the page to load
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
            
            # Final Safety: If it's still empty, tell the user why
            if not vocab or len(vocab) < 3:
                return jsonify({"error": "The AI couldn't find vocabulary in these images. Please ensure the text is clear."}), 500
                
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