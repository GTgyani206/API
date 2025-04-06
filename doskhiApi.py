from flask import Flask, request, jsonify, send_file
import google.generativeai as genai
import openai
import os
from pathlib import Path
from dotenv import load_dotenv
from flask_cors import CORS  # Import CORS

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)  # Use environment variable

# Initialize OpenAI client (only if OPENAI_API_KEY is available)
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Warning: OpenAI client initialization failed: {e}")

# Storage Path
BASE_AUDIO_PATH = Path("audioFiles/topics")

# Predefined Themes
THEMES = {
    "CourageAndConsent": "Stories about empowerment, making informed choices, and understanding consent.",
    "HealthAndHygiene": "Educational stories about physical health, cleanliness, and menstrual awareness.",
    "KnowYourRights": "Informative stories about legal rights, gender equality, and self-advocacy.",
    "MindMatters": "Narratives that focus on mental health, emotional intelligence, and resilience.",
    "SafetyAndBoundaries": "Stories about personal safety, setting boundaries, and recognizing red flags.",
}

@app.route('/generate-podcast', methods=['POST'])
def generate_podcast():
    try:
        data = request.json
        topic = data.get('topic', '').strip()
        custom_topic = data.get('custom_topic', '').strip()
        language = data.get('language', 'Hindi')
        voice = data.get('voice', 'coral')
        temperature = float(data.get('temperature', 0.7))

        # Validate topic input
        if not topic and not custom_topic:
            return jsonify({"status": "error", "message": "Please provide a topic or custom topic"}), 400

        # Determine the storage path
        if topic in THEMES:
            audio_folder = BASE_AUDIO_PATH / topic
            category_description = THEMES[topic]
        else:
            # Categorize the custom topic under an existing theme
            audio_folder = BASE_AUDIO_PATH / "CustomTopics" / custom_topic.replace(" ", "_")

        # Ensure the folder exists
        audio_folder.mkdir(parents=True, exist_ok=True)

        # Generate the script
        prompt = f"""
        You are a creative storyteller and animation director. Create a detailed, engaging narrative in {language} about {topic or custom_topic}. {THEMES.get(topic, 'This is a custom topic. Create an informative and engaging story.')}

        Imagine you're telling this story to a young audience. Use natural, conversational language. Include descriptive details, relatable situations, and a clear story arc with a beginning, middle, and end.

        For each sentence or short phrase, provide a corresponding pose directive for the animated character. Use the following poses:
        - Normal: Neutral stance, hands down.
        - Cross: Hands closed.
        - Greet: Single hand wave.
        - Think: Chin touch, one eye slightly closed.
        - Spread: Elbow-out hand opening.
        - Point: Single hand point, palm open.

        Output ONLY the narrative and pose directives in the format:
        <sentence or short phrase>
        [POSE: <pose_name>]

        Ensure the poses naturally complement the story's emotions and actions, and that the transitions are smooth and suitable for audio synchronization.
        """
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(
            [{"role": "user", "parts": [prompt]}],
            generation_config=genai.types.GenerationConfig(temperature=temperature)
        )

        podcast_script = response.text

        # Define file path
        filename = f"{(topic or custom_topic).replace(' ', '_')}.mp3"
        speech_file_path = audio_folder / filename

        # Generate the speech using OpenAI (if available)
        audio_url = None
        if openai_client:
            try:
                tts_response = openai_client.audio.speech.create(
                    model="gpt-4o-mini-tts",
                    voice=voice,
                    input=podcast_script,
                )
                tts_response.stream_to_file(speech_file_path)
                audio_url = f"/stream-audio/{topic}/{filename}" if topic else f"/stream-audio/CustomTopics/{custom_topic}/{filename}" #changed route name.
            except Exception as e:
                print(f"Warning: OpenAI TTS failed: {e}")

        return jsonify({
            "status": "success",
            "script": podcast_script,
            "audio_url": audio_url,
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream-audio/<category>/<filename>', methods=['GET']) #changed route name.
def download_audio(category, filename):
    file_path = BASE_AUDIO_PATH / category / filename
    if file_path.exists():
        return send_file(file_path, mimetype="audio/mpeg", as_attachment=False) #as_attachment = False
    return jsonify({"status": "error", "message": "File not found"}), 404

@app.route('/themes', methods=['GET'])
def get_themes():
    return jsonify({"themes": list(THEMES.keys())})

@app.route('/test', methods=['GET'])
def test_endpoint():
    return jsonify({
        "status": "success",
        "message": "API is working",
        "gemini_key_set": bool(GEMINI_API_KEY),
        "openai_key_set": bool(OPENAI_API_KEY)
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)