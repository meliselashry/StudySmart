from flask import Flask, request, jsonify, render_template
import base64
import mimetypes
from openai import OpenAI

app = Flask(__name__)
client = OpenAI()  # make sure your OPENAI_API_KEY is set in env

def encode_image_to_data_url(file_bytes: bytes, filename: str) -> str:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "image/jpeg"

    encoded = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = request.files["image"]

    if image.filename == "":
        return jsonify({"error": "No file selected"}), 400

    file_bytes = image.read()
    image_data_url = encode_image_to_data_url(file_bytes, image.filename)

    prompt = "Turn this classroom image into clean study notes."

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }
        ],
    )

    return jsonify({"result": response.output_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=False)