from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from openai import OpenAI
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatbot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
from models import db
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Import models after db initialization
from models import User, Conversation, Message

# Register auth blueprint
from auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/auth')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# HuggingFace / OpenAI Router Client
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HUGGINGFACE_API_KEY"),
)

# ===================== SYSTEM PROMPT =====================
SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "You are Dr. HealthBot, a seasoned physician with over 20 years of experience in internal medicine and emergency care. Respond as a compassionate yet authoritative doctor would to a patient in a clinic.\n\n"
        "STRICT RULES:\n"
        "- Be empathetic and reassuring, but clinically precise\n"
        "- Use medical terminology appropriately (e.g., 'dyspnea' instead of 'shortness of breath')\n"
        "- Start responses with 'As your physician...' or 'Based on your symptoms...'\n"
        "- End with a personal note like 'Take care, Dr. HealthBot'\n"
        "- Bullet points only, no paragraphs\n"
        "- Ask max ONE follow-up question if needed\n\n"
        "FOLLOW-UP QUESTIONS BASED ON SYMPTOMS (ASK ONE AT A TIME):\n"
        "- If fever mentioned but no temperature asked yet: Output exactly: FOLLOW-UP: What is your current temperature? <98°F, 98-100°F, 100-102°F, 102-104°F, >104°F>\n"
        "- If cold/flu mentioned but no symptoms asked yet: Output exactly: FOLLOW-UP: What are your main symptoms? <Runny nose, Sore throat, Body aches, Fatigue, Sneezing, All of the above>\n"
        "- If cough mentioned but no type asked yet: Output exactly: FOLLOW-UP: What type of cough? <Dry, Productive (with mucus), Wheezing, Whooping, Chronic>\n"
        "- If headache mentioned but no description asked yet: Output exactly: FOLLOW-UP: Describe your headache: <Throbbing, Constant, Sharp, Dull, Migraine-like>\n"
        "- If stomach pain mentioned but no location asked yet: Output exactly: FOLLOW-UP: Where is the pain located? <Upper abdomen, Lower abdomen, All over, Right side, Left side>\n"
        "- If chest pain mentioned but no description asked yet: Output exactly: FOLLOW-UP: Describe the chest pain: <Sharp, Dull, Burning, Crushing, Intermittent>\n"
        "- PRIORITY: Ask about most serious symptom first (chest pain > fever > cough > headache > stomach pain > cold)\n"
        "- CRITICAL: When asking a follow-up question, OUTPUT ONLY THE FOLLOW-UP LINE AS A SEPARATE LINE AT THE END OF YOUR RESPONSE. Do not include it in any section. The follow-up line must be exactly: FOLLOW-UP: [question]? <option1, option2, option3>\n"
        "- EXAMPLE: If asking about cold symptoms, your entire response should end with this line: FOLLOW-UP: What are your main symptoms? <Runny nose, Sore throat, Body aches, Fatigue, Sneezing, All of the above>\n\n"
        "MANDATORY FORMAT:\n"
        "• Severity Assessment:\n"
        "• Differential Diagnosis:\n"
        "• Immediate Management:\n"
        "• Pharmacotherapy (India):\n"
        "• Preventive Measures:\n"
        "• Red Flags - Seek Urgent Care If:\n\n"
        "Use concise, professional language. Stand out by being thorough yet concise, like a real doctor's consultation."
    )
}

chat_history = [SYSTEM_PROMPT]
follow_up_state = {}

# ===================== EMERGENCY CHECK =====================
def analyze_symptoms(text):
    emergency_keywords = [
        "chest pain", "difficulty breathing", "unconscious",
        "severe bleeding", "stroke", "heart attack",
        "poisoning", "suicidal", "severe burn"
    ]

    text = text.lower()
    for word in emergency_keywords:
        if word in text:
            return True
    return False


# ===================== FOLLOW-UP STATE MANAGEMENT =====================
def update_follow_up_state(user_message):
    """Update the follow-up state based on user's response to follow-up questions."""
    global follow_up_state
    message_lower = user_message.lower()

    # Temperature follow-up
    if any(temp in message_lower for temp in ['°f', 'fahrenheit', 'celsius', 'temperature']):
        follow_up_state['temperature_asked'] = True

    # Cold symptoms follow-up
    if any(symptom in message_lower for symptom in ['runny nose', 'sore throat', 'body aches', 'fatigue', 'sneezing']):
        follow_up_state['cold_symptoms_asked'] = True

    # Cough type follow-up
    if any(cough in message_lower for cough in ['dry', 'productive', 'wheezing', 'whooping', 'chronic']):
        follow_up_state['cough_type_asked'] = True

    # Headache description follow-up
    if any(desc in message_lower for desc in ['throbbing', 'constant', 'sharp', 'dull', 'migraine']):
        follow_up_state['headache_desc_asked'] = True

    # Stomach pain location follow-up
    if any(loc in message_lower for loc in ['upper abdomen', 'lower abdomen', 'right side', 'left side']):
        follow_up_state['stomach_pain_loc_asked'] = True

    # Chest pain description follow-up
    if any(desc in message_lower for desc in ['sharp', 'dull', 'burning', 'crushing', 'intermittent']):
        follow_up_state['chest_pain_desc_asked'] = True

def create_dynamic_system_prompt(base_prompt):
    """Create a dynamic system prompt based on follow-up state and base prompt."""
    follow_up_instructions = "FOLLOW-UP QUESTIONS BASED ON SYMPTOMS (ASK ONE AT A TIME):\n"

    # Only include follow-up questions that haven't been asked yet
    if not follow_up_state.get('temperature_asked', False):
        follow_up_instructions += "- If fever mentioned: Output exactly: FOLLOW-UP: What is your current temperature? <98°F, 98-100°F, 100-102°F, 102-104°F, >104°F>\n"

    if not follow_up_state.get('cold_symptoms_asked', False):
        follow_up_instructions += "- If cold/flu mentioned: Output exactly: FOLLOW-UP: What are your main symptoms? <Runny nose, Sore throat, Body aches, Fatigue, Sneezing, All of the above>\n"

    if not follow_up_state.get('cough_type_asked', False):
        follow_up_instructions += "- If cough mentioned: Output exactly: FOLLOW-UP: What type of cough? <Dry, Productive (with mucus), Wheezing, Whooping, Chronic>\n"

    if not follow_up_state.get('headache_desc_asked', False):
        follow_up_instructions += "- If headache mentioned: Output exactly: FOLLOW-UP: Describe your headache: <Throbbing, Constant, Sharp, Dull, Migraine-like>\n"

    if not follow_up_state.get('stomach_pain_loc_asked', False):
        follow_up_instructions += "- If stomach pain mentioned: Output exactly: FOLLOW-UP: Where is the pain located? <Upper abdomen, Lower abdomen, All over, Right side, Left side>\n"

    if not follow_up_state.get('chest_pain_desc_asked', False):
        follow_up_instructions += "- If chest pain mentioned: Output exactly: FOLLOW-UP: Describe the chest pain: <Sharp, Dull, Burning, Crushing, Intermittent>\n"

    follow_up_instructions += "- PRIORITY: Ask about most serious symptom first (chest pain > fever > cough > headache > stomach pain > cold)\n"
    follow_up_instructions += "- IMPORTANT: Only output FOLLOW-UP if you decide to ask a follow-up question. Do not include it in regular responses.\n\n"

    final_prompt = base_prompt + "\n\n" + follow_up_instructions + (
        "MANDATORY FORMAT:\n"
        "• Severity Assessment:\n"
        "• Differential Diagnosis:\n"
        "• Immediate Management:\n"
        "• Pharmacotherapy (India):\n"
        "• Preventive Measures:\n"
        "• Red Flags - Seek Urgent Care If:\n\n"
        "Use concise, professional language. Stand out by being thorough yet concise, like a real doctor's consultation."
    )

    return {"role": "system", "content": final_prompt}

# ===================== PARSE RESPONSE =====================
def parse_response(text):
    sections = {}
    lines = text.split('\n')
    current_section = None
    follow_up_question = None
    follow_up_options = []

    for line in lines:
        line = line.strip()
        if line.startswith('FOLLOW-UP:'):
            # Extract follow-up question and options
            follow_up_content = line[11:].strip()  # Remove "FOLLOW-UP: "
            if '<' in follow_up_content and '>' in follow_up_content:
                question_part = follow_up_content.split('<')[0].strip()
                options_part = follow_up_content.split('<')[1].split('>')[0]
                options = [opt.strip() for opt in options_part.split(',')]

                follow_up_question = question_part
                follow_up_options = options
        elif line.startswith('•'):
            # Extract section title
            section_title = line[1:].split(':')[0].strip()
            content = line.split(':', 1)[1].strip() if ':' in line else ''
            sections[section_title] = content
            current_section = section_title
        elif current_section and line:
            # Check if this line contains a follow-up question with options
            if '<' in line and '>' in line and ('?' in line or 'temperature' in line.lower() or 'symptoms' in line.lower() or 'cough' in line.lower() or 'headache' in line.lower() or 'pain' in line.lower()):
                # Extract question and options
                question_part = line.split('<')[0].strip()
                options_part = line.split('<')[1].split('>')[0]
                options = [opt.strip() for opt in options_part.split(',')]

                follow_up_question = question_part
                follow_up_options = options
            else:
                # Append to current section if it's continuation
                sections[current_section] += ' ' + line

    # Fallback: If no sections were parsed (e.g., no bullet points), create a default section
    if not sections:
        # Try to split into sections based on common keywords
        section_keywords = [
            "Severity Assessment", "Differential Diagnosis", "Immediate Management",
            "Pharmacotherapy", "Preventive Measures", "Red Flags"
        ]
        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            for keyword in section_keywords:
                if keyword.lower() in line.lower():
                    current_section = keyword
                    sections[current_section] = ""
                    break
            else:
                if current_section:
                    sections[current_section] += line + " "
                else:
                    # If no keyword found, accumulate in a default section
                    if "Response" not in sections:
                        sections["Response"] = ""
                    sections["Response"] += line + " "

        # If still no sections, put entire text in one section
        if not sections:
            sections["Response"] = text.strip()

    if follow_up_question:
        sections["follow_up"] = {
            "question": follow_up_question,
            "options": follow_up_options
        }

    return sections


# ===================== ROUTES =====================
@app.route("/")
@login_required
def index():
    try:
        return render_template("index.html")
    except Exception as e:
        print(f"Error in index: {e}")
        return "Internal Server Error", 500


@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    conversation_id = request.json.get("conversation_id")

    if not user_message:
        return jsonify({"response": "Please describe your symptoms."}), 400

    # Check for follow-up triggers before updating state
    follow_up_data = None
    user_lower = user_message.lower()

    # Priority order: chest pain > fever > cough > headache > stomach pain > cold
    if "chest pain" in user_lower and not follow_up_state.get('chest_pain_desc_asked', False):
        follow_up_data = {
            "question": "Describe the chest pain:",
            "options": ["Sharp", "Dull", "Burning", "Crushing", "Intermittent"]
        }
        follow_up_state['chest_pain_desc_asked'] = True
    elif "fever" in user_lower and not follow_up_state.get('temperature_asked', False):
        follow_up_data = {
            "question": "What is your current temperature?",
            "options": ["98°F", "98-100°F", "100-102°F", "102-104°F", ">104°F"]
        }
        follow_up_state['temperature_asked'] = True
    elif "cough" in user_lower and not follow_up_state.get('cough_type_asked', False):
        follow_up_data = {
            "question": "What type of cough?",
            "options": ["Dry", "Productive (with mucus)", "Wheezing", "Whooping", "Chronic"]
        }
        follow_up_state['cough_type_asked'] = True
    elif "headache" in user_lower and not follow_up_state.get('headache_desc_asked', False):
        follow_up_data = {
            "question": "Describe your headache:",
            "options": ["Throbbing", "Constant", "Sharp", "Dull", "Migraine-like"]
        }
        follow_up_state['headache_desc_asked'] = True
    elif ("stomach pain" in user_lower or "abdominal pain" in user_lower) and not follow_up_state.get('stomach_pain_loc_asked', False):
        follow_up_data = {
            "question": "Where is the pain located?",
            "options": ["Upper abdomen", "Lower abdomen", "All over", "Right side", "Left side"]
        }
        follow_up_state['stomach_pain_loc_asked'] = True
    elif ("cold" in user_lower or "flu" in user_lower) and not follow_up_state.get('cold_symptoms_asked', False):
        follow_up_data = {
            "question": "What are your main symptoms?",
            "options": ["Runny nose", "Sore throat", "Body aches", "Fatigue", "Sneezing", "All of the above"]
        }
        follow_up_state['cold_symptoms_asked'] = True

    # Update follow-up state based on user's response
    update_follow_up_state(user_message)

    # Emergency detection
    if analyze_symptoms(user_message):
        return jsonify({
            "response": (
                "⚠️ EMERGENCY ⚠️\n\n"
                "Possible life-threatening condition.\n"
                "Go to nearest emergency room NOW or call local emergency number."
            )
        })

    # Determine base prompt: use custom prompt if user is authenticated and has one, else default
    if current_user.is_authenticated and current_user.custom_prompt:
        base_prompt = current_user.custom_prompt
    else:
        base_prompt = SYSTEM_PROMPT["content"]

    # Create dynamic system prompt based on follow-up state
    dynamic_system_prompt = create_dynamic_system_prompt(base_prompt)

    # Use dynamic system prompt for this conversation
    current_messages = [dynamic_system_prompt] + chat_history[1:] + [{"role": "user", "content": user_message}]

    try:
        response = client.chat.completions.create(
            model=os.getenv("MODEL", "Qwen/Qwen2.5-VL-7B-Instruct:hyperbolic"),
            messages=current_messages,
            temperature=float(os.getenv("TEMPERATURE", "0.25")),
            max_tokens=int(os.getenv("MAX_TOKENS", "300"))
        )

        assistant_reply = response.choices[0].message.content.strip()

        # Force short output
        assistant_reply = assistant_reply[:900]

        # Debug: print the raw response
        print(f"Raw AI response: {repr(assistant_reply)}")

        # Parse the response into sections
        sections = parse_response(assistant_reply)

        # Add follow-up if triggered
        if follow_up_data:
            sections["follow_up"] = follow_up_data

        # Append disclaimer
        sections["disclaimer"] = "*Disclaimer: AI guidance only. Consult a qualified doctor.*"

        # Update chat history with the dynamic prompt response
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": assistant_reply})

        # Create conversation if not provided and user is authenticated
        if not conversation_id and current_user.is_authenticated:
            conversation = Conversation(user_id=current_user.id, title=user_message[:50] + ('...' if len(user_message) > 50 else ''))
            db.session.add(conversation)
            db.session.commit()
            conversation_id = conversation.id

        # Save to database if conversation_id is provided and user is authenticated
        if conversation_id and current_user.is_authenticated:
            conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first()
            if conversation:
                # Check if this is the first user message in the conversation
                existing_user_messages = Message.query.filter_by(conversation_id=conversation_id, role='user').count()
                if existing_user_messages == 0:
                    # Update conversation title to the first user message
                    conversation.title = user_message[:50] + ('...' if len(user_message) > 50 else '')

                # Save user message
                user_msg = Message(conversation_id=conversation_id, role='user', content=user_message)
                db.session.add(user_msg)

                # Save bot response
                bot_msg = Message(conversation_id=conversation_id, role='assistant', content=json.dumps(sections))
                db.session.add(bot_msg)

                db.session.commit()

        response_data = {"response": sections}
        if conversation_id:
            response_data["conversation_id"] = conversation_id
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in /chat: {str(e)}")  # Add logging for debugging
        return jsonify({
            "response": "System error. Please try again later."
        }), 500


@app.route("/reset", methods=["POST"])
def reset_chat():
    global chat_history, follow_up_state
    chat_history = [SYSTEM_PROMPT]
    follow_up_state = {}
    return jsonify({"message": "Chat reset successful"})


@app.route("/history", methods=["GET"])
@login_required
def history():
    return jsonify({"history": chat_history[1:]})


@app.route("/conversations", methods=["GET"])
@login_required
def get_conversations():
    try:
        print(f"get_conversations called for user: {current_user.id}")
        # Return all conversations for the user
        conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.created_at.desc()).all()
        print(f"Found {len(conversations)} conversations")
        for conv in conversations:
            print(f"Conversation: {conv.id} - {conv.title}")
        return jsonify({
            "conversations": [
                {
                    "id": conv.id,
                    "title": conv.title,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat()
                } for conv in conversations
            ]
        })
    except Exception as e:
        print(f"Error in get_conversations: {e}")
        return jsonify({"error": "Failed to load conversations"}), 500


@app.route("/conversation/<int:conv_id>", methods=["GET"])
@login_required
def get_conversation(conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    messages = Message.query.filter_by(conversation_id=conv_id).order_by(Message.created_at).all()
    return jsonify({
        "conversation": {
            "id": conversation.id,
            "title": conversation.title,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                } for msg in messages
            ]
        }
    })


@app.route("/conversation", methods=["POST"])
@login_required
def create_conversation():
    data = request.json
    title = data.get("title", "New Conversation")

    conversation = Conversation(user_id=current_user.id, title=title)
    db.session.add(conversation)
    db.session.commit()

    return jsonify({"conversation_id": conversation.id})

@app.route("/message", methods=["POST"])
@login_required
def save_message():
    data = request.json
    conversation_id = data.get("conversation_id")
    content = data.get("content")
    role = data.get("role")

    if not conversation_id or not content or not role:
        return jsonify({"error": "Missing required fields"}), 400

    conversation = Conversation.query.filter_by(id=conversation_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    message = Message(conversation_id=conversation_id, role=role, content=content)
    db.session.add(message)
    db.session.commit()

    # Check if this is the first user message in the conversation
    if role == 'user':
        existing_user_messages = Message.query.filter_by(conversation_id=conversation_id, role='user').count()
        if existing_user_messages == 1:  # This is the first user message
            # Update conversation title to the first user message (truncated)
            conversation.title = content[:50] + ('...' if len(content) > 50 else '')
            db.session.commit()

    return jsonify({"message_id": message.id})


@app.route("/settings", methods=["GET"])
@login_required
def settings():
    return render_template("settings.html", system_prompt=SYSTEM_PROMPT["content"])


@app.route("/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.json
    custom_prompt = data.get("custom_prompt", "")

    current_user.custom_prompt = custom_prompt
    db.session.commit()

    return jsonify({"message": "Settings updated successfully"})


@app.route("/conversation/<int:conv_id>", methods=["DELETE"])
@login_required
def delete_conversation(conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    # Delete all messages in the conversation
    Message.query.filter_by(conversation_id=conv_id).delete()

    # Delete the conversation
    db.session.delete(conversation)
    db.session.commit()

    return jsonify({"message": "Conversation deleted successfully"})


@app.route("/conversations", methods=["DELETE"])
@login_required
def delete_all_conversations():
    # Delete all messages for the user
    Message.query.filter(Message.conversation_id.in_(
        db.session.query(Conversation.id).filter_by(user_id=current_user.id)
    )).delete(synchronize_session=False)

    # Delete all conversations for the user
    Conversation.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    return jsonify({"message": "All conversations deleted successfully"})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="127.0.0.1", port=5000)
