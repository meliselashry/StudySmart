
# --- THE TOOLBOX (IMPORTS) ---
# These are external "plugin" packages that give this script special powers.
from flask import Flask, request, jsonify, render_template  
# Flask is the skeleton that lets us build a website people can actually visit.
from openai import OpenAI  
# This is the direct phone line to the AI "brain" (GPT-4) that reads your images.
from playwright.sync_api import sync_playwright  
# This is a "robot" that can open a real Chrome browser and click buttons for you.
import nest_asyncio  
# This is a technical fix that allows the "robot" and the "website" to run at the same time.
import base64  
# This translates a picture file into a long string of text so the AI can "see" it.
import mimetypes  
# This helps the computer figure out if a file is a JPEG, a PNG, or something else.
import os  
# This lets the script talk to your computer's folders to save your Quizlet login.
import re  
# This is a "smart search" tool used to find buttons on a page even if the text changes slightly.

# --- INITIAL SETUP ---
# We are initializing the "Brain" and the "Website" here.
app = Flask(__name__)  
# We name our website "app" so we can give it instructions later.
client = OpenAI()  
# We wake up the OpenAI connection so it's ready to process images.

# These two lines tell the robot where to store your Quizlet login data so you stay logged in.
QUIZLET_STORAGE_STATE = "quizlet_state.json"
USER_DATA_DIR = os.path.join(os.getcwd(), "quizlet_user_data")

# --- THE IMAGE TRANSLATOR ---
def encode_image_to_data_url(file_bytes: bytes, filename: str) -> str:
    """
    Computers don't see images; they see binary code (1s and 0s). 
    This function turns those 1s and 0s into a format the AI can understand.
    """
    mime_type, _ = mimetypes.guess_type(filename)
    # This line checks the file name to see if it's a photo or a screenshot.
    if mime_type is None:
        mime_type = "image/jpeg"
    # If the computer is confused, we just tell it "it's probably a JPEG photo."
    encoded = base64.b64encode(file_bytes).decode("utf-8")
    # This is the actual "translation" step from image to text-string.
    return f"data:{mime_type};base64,{encoded}"
    # We send back the final "translated" version to be used by the AI.

# --- THE AI BRAIN METHODS ---
def make_summary_from_image(image_data_urls: list) -> str:
    """
    This tells the AI: 'Look at these whiteboard photos and write a study guide.'
    """
    prompt = "Turn these classroom images into clean study notes."
    # This is the specific instruction we give to the AI.
    content = [{"type": "input_text", "text": prompt}]
    # We start a 'list' of things to show the AI, beginning with our instruction.
    for url in image_data_urls:
        content.append({"type": "input_image", "image_url": url})
    # We loop through every photo you uploaded and "show" them to the AI one by one.
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": content}],
    )
    # We wait for the AI to finish thinking and then grab its written response.
    return response.output_text

def make_vocab_title(image_data_urls: list) -> str:
    """
    This tells the AI: 'Based on these photos, what should we name this Quizlet set?'
    """
    prompt = """
Create a title for a list of vocab words you would make of the images provided. The title should 
summarize and represent a list of vocab words that the student should study based on the images and the 
topic/ lesson covered. Example: "parts of a heart". NO OTHER WORDS! 
"""
    # We tell the AI to be very brief so it doesn't add extra chatty text.
    content = [{"type": "input_text", "text": prompt}]
    # Again, we prepare the message for the AI.
    for url in image_data_urls:
        content.append({"type": "input_image", "image_url": url})
    # We show the images to the AI again so it knows what the topic is.
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": content}],
    )
    # We ask the AI to generate the title.
    return response.output_text.strip()
    # '.strip()' removes any accidental spaces at the beginning or end.

def make_vocab_from_image(image_data_urls: list) -> str:
    """
    This is the "Flashcard Maker." It finds keywords and defines them.
    """
    prompt = """
Look at these classroom images and extract important vocabulary terms and definitions.

Return ONLY plain text in this exact format:
term<TAB>definition
definition should not be longer than a few words.
One pair per line.
No numbering. No bullet points. No extra commentary.
"""
    # We tell the AI to use a 'Tab' because that's how Quizlet separates words from definitions.
    content = [{"type": "input_text", "text": prompt}]
    # We prepare the "package" of instructions and images.
    for url in image_data_urls:
        content.append({"type": "input_image", "image_url": url})
    # We feed the images into the AI's "eyes."
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[{"role": "user", "content": content}],
    )
    # We receive the final list of words and definitions.
    return response.output_text.strip()

# This makes sure the browser automation doesn't crash the website while it runs.
nest_asyncio.apply()

# --- THE BROWSER ROBOT METHOD ---
def send_vocab_to_quizlet(vocab_text: str, smart_title: str):
    """
    This function opens a real browser and moves your AI notes into Quizlet.
    """
    pw = sync_playwright().start()
    # We start up the "Robot Engine."
    try:
        context = pw.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        # We open a Chrome window that you can see (headless=False means 'not hidden').
        page = context.pages[0]
        # We grab the first tab in that window.
        page.goto("https://quizlet.com/create-set")
        # We tell the robot to drive the browser to the Quizlet creation page.

        if "login" in page.url.lower():
            print("Action Required: Please log in in the browser.")
        # If the robot sees the word "login" in the URL, it pauses for you.
            
        while "login" in page.url:
            page.wait_for_timeout(2000) 
        # The robot waits and checks every 2 seconds to see if you've finished logging in.

        title_input = page.get_by_label("Title").first 
        # The robot looks for the box labeled "Title."
        if not title_input.is_visible():
            title_input = page.locator("input[name='title'], #title-input").first
        # If it can't find it easily, it tries searching for the code-name of the box.

        title_input.wait_for(state="visible")
        # The robot waits until the box actually appears on the screen.
        title_input.click()
        # The robot clicks the box so it can start typing.
        page.keyboard.press("Control+A")
        # It highlights any old text in the box.
        page.keyboard.press("Backspace")
        # It deletes the old text to make room for the new title.
        title_input.type(smart_title, delay=70)
        # It types the title. 'delay=70' makes it type slowly like a human would.
        
        import_selector = "text='Import'"
        # It looks for the button that says "Import."
        page.wait_for_selector(import_selector, timeout=10000)
        # It waits up to 10 seconds for that button to show up.
        page.click(import_selector)
        # It clicks the "Import" button.
        
        textarea = page.locator("div[role='dialog'] textarea, textarea[aria-label='Import']").first
        # It looks for the big empty box where you paste your words.
        textarea.wait_for(state="visible", timeout=10000)
        # It waits for that box to be ready.
        textarea.click()
        # It clicks inside the box.
        textarea.type(vocab_text, delay=10)
        # It "pastes" (types) all your words and definitions into the box.
        
        page.get_by_role("button", name=re.compile(r"^import$", re.I)).last.click()
        # It clicks the final 'Import' button to confirm everything.
        input("Review your flashcards in the browser, then press ENTER in this terminal to close...")
        # It stops here so you can look at the results before the browser closes.
        
    except Exception as e:
        print(f"An error occurred: {e}")
    # If anything breaks, the computer prints out exactly what went wrong.
    finally:
        context.close()
        # We shut down the browser window.
        pw.stop()
        # We turn off the "Robot Engine."

# --- THE WEBSITE PAGES (ROUTES) ---
@app.route("/")
def home():
    """This is the main page you see when you first open the website."""
    return render_template("index.html")
    # It sends the 'index.html' file to your browser.
    
@app.route("/analyze", methods=["POST"])
def analyze():
    """This happens when you click 'Upload' or 'Analyze' on the website."""
    images = request.files.getlist("image")
    # It gathers all the images you picked.
    if not images or images[0].filename == "":
        return jsonify({"error": "No images selected"}), 400
    # If you didn't pick any images, it tells you there's an error.
    
    mode = request.form.get("mode", "summary")
    # It checks if you clicked "Summary" or "Vocab List."
    image_data_urls = []
    # It creates an empty list to store the "translated" images.
    for img in images:
        file_bytes = img.read()
        # It reads the raw data of each image.
        data_url = encode_image_to_data_url(file_bytes, img.filename)
        # It calls our translator function from earlier.
        image_data_urls.append(data_url)
        # It adds the translated image to our list.

    try:
        if mode == "vocab_list":
            # If you chose "Vocab," it runs the two vocab-related AI steps.
            vocab_text = make_vocab_from_image(image_data_urls)
            smart_title = make_vocab_title(image_data_urls)
            return jsonify({"vocab": vocab_text, "title": smart_title})
            # It sends the words and the title back to your screen.
        elif mode == "summary":
            # If you chose "Summary," it runs the note-taking AI step.
            result = make_summary_from_image(image_data_urls)
            return jsonify({"result": result})
            # It sends the notes back to your screen.
        else:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        # If the AI crashes, it tells the website to show the error message.

@app.route("/run_quizlet", methods=["POST"])
def run_quizlet():
    """This happens when you click the 'Send to Quizlet' button."""
    data = request.json
    # It gathers the words and title currently showing on your screen.
    try:
        vocab = data.get("vocab")
        title = data.get("title")
        send_vocab_to_quizlet(vocab, title)
        # It starts the "Robot" using that data.
        return jsonify({"message": "Automation Complete"})
        # It tells the website that the robot is finished.
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- STARTING THE PROGRAM ---
if __name__ == "__main__":
    # This part actually runs the script.
    port = int(os.environ.get("PORT", 5011))
    # It picks a 'door' (port) to run the website through—usually 5011.
    app.run(host='0.0.0.0', port=port)
    # This launches the server so you can go to 'localhost:5011' in your browser.