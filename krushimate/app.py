
from datetime import date
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from functools import wraps
import os, json, time
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
try:
    from groq import Groq
except ImportError:
    Groq = None

app = Flask(__name__)
app.secret_key = 'krushimate_secret_key'  # Required for session management

# --------------------
# Database Config
# --------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///krushimate.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --------------------
# Database Models
# --------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Farmer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200))
    crop_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_name = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class UserCrop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    sowing_date = db.Column(db.Date)
    harvest_date = db.Column(db.Date)
    area = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Planned')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class UserMedicineOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_data = db.Column(db.JSON)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class PlannerTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    crop_id = db.Column(db.Integer, db.ForeignKey('user_crop.id'))
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), default='General')
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20), default='Medium')
    status = db.Column(db.String(20), default='Pending')
    notes = db.Column(db.Text)
    source = db.Column(db.String(20), default='manual')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

# --------------------
# Config & directories
# --------------------
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

FARMERS_FILE = os.path.join(DATA_DIR, "farmers.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
for f in (FARMERS_FILE, ORDERS_FILE):
    if not os.path.exists(f):
        with open(f, "w") as fh:
            json.dump([], fh)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

# --------------------
# Groq Client setup
# --------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.1-8b-instant")

client = Groq(api_key=GROQ_API_KEY) if Groq and GROQ_API_KEY else None

# --------------------
# Helpers
# --------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def read_json(path):
    with open(path, "r") as fh:
        return json.load(fh)

def write_json(path, data):
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)

def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None

def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)

@app.context_processor
def inject_template_user():
    user = get_current_user()
    if not user:
        return {"user": None}
    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "city": user.city,
            "contact": user.contact,
            "email": user.email,
            "username": user.username,
        }
    }

def normalize_medicine_order_data(order_data):
    if isinstance(order_data, dict):
        items = order_data.get("items", [])
        normalized_items = [
            {
                "name": item.get("name", "Item"),
                "quantity": int(item.get("quantity", item.get("qty", 1)) or 1),
                "price": float(item.get("price", 0) or 0),
                "category": item.get("category"),
                "image": item.get("image"),
            }
            for item in items
            if isinstance(item, dict)
        ]
        normalized = dict(order_data)
        normalized["items"] = normalized_items
        return normalized

    if isinstance(order_data, list):
        return {
            "items": [
                {
                    "name": item.get("name", "Item"),
                    "quantity": int(item.get("quantity", item.get("qty", 1)) or 1),
                    "price": float(item.get("price", 0) or 0),
                    "category": item.get("category"),
                    "image": item.get("image"),
                }
                for item in order_data
                if isinstance(item, dict)
            ]
        }

    return {"items": []}

def serialize_planner_task(task):
    crop = UserCrop.query.get(task.crop_id) if task.crop_id else None
    return {
        "id": task.id,
        "crop_id": task.crop_id,
        "crop_name": crop.name if crop else None,
        "title": task.title,
        "category": task.category,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "priority": task.priority,
        "status": task.status,
        "notes": task.notes,
        "source": task.source,
    }

def build_crop_task_suggestions(crop):
    suggestions = []
    if not crop.sowing_date:
        return suggestions

    schedule = [
        (3, "Irrigation", "First moisture check", "High", "Check soil moisture and apply light irrigation if the top soil is dry."),
        (10, "Nutrition", "Starter nutrition boost", "Medium", "Apply starter nutrients or compost to support early crop establishment."),
        (18, "Field Check", "Pest and disease scouting", "High", "Inspect leaves, stems, and soil edges for early disease or pest symptoms."),
        (30, "Growth", "Growth stage review", "Medium", "Review crop height, leaf color, and patchy sections before the next intervention."),
        (45, "Protection", "Preventive spray planning", "Medium", "Prepare preventive spray or bio-inputs if humidity, pests, or disease pressure rise."),
    ]

    if crop.harvest_date:
        days_before_harvest = max((crop.harvest_date - crop.sowing_date).days - 7, 0)
        schedule.append((days_before_harvest, "Harvest", "Harvest readiness check", "High", "Inspect maturity, labour needs, bags, and transport readiness before harvest week."))

    for offset, category, title, priority, notes in schedule:
        due = crop.sowing_date.fromordinal(crop.sowing_date.toordinal() + offset)
        suggestions.append({
            "crop_id": crop.id,
            "title": f"{crop.name}: {title}",
            "category": category,
            "due_date": due,
            "priority": priority,
            "status": "Pending",
            "notes": notes,
            "source": "system",
        })

    return suggestions

def sync_system_tasks_for_user(user_id):
    crops = UserCrop.query.filter_by(user_id=user_id).all()
    existing_system_tasks = PlannerTask.query.filter_by(user_id=user_id, source="system").all()
    existing_keys = {
        (task.crop_id, task.title, task.due_date.isoformat() if task.due_date else None)
        for task in existing_system_tasks
    }

    added = 0
    for crop in crops:
        for suggestion in build_crop_task_suggestions(crop):
            key = (
                suggestion["crop_id"],
                suggestion["title"],
                suggestion["due_date"].isoformat() if suggestion["due_date"] else None,
            )
            if key in existing_keys:
                continue
            db.session.add(PlannerTask(user_id=user_id, **suggestion)) # type: ignore[arg-type]
            existing_keys.add(key)
            added += 1

    if added:
        db.session.commit()

# --------------------
# Analyze crop image with Groq AI
# --------------------
def analyze_crop_image(image_path):
    prompt = (
        "Analyze this crop image and provide a short disease name, severity, and suggested solution. "
        "Return only plain text, do not include JSON formatting."
    )
    if not client:
        return {
            "disease_name": "Analysis unavailable",
            "severity": "Unknown",
            "suggested_solution": "Add a GROQ_API_KEY to enable AI image guidance."
        }
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        ai_output = response.choices[0].message.content.strip() # type: ignore
        return {
            "disease_name": "AI Generated",
            "severity": "AI Generated",
            "suggested_solution": ai_output
        }
    except Exception as e:
        return {"error": str(e)}

def query_groq_agent(disease_name, question):
    prompt = (
        f"Disease: {disease_name}\nQuestion: {question}\nProvide a detailed, practical answer for a farmer."
    )
    if not client:
        return "AI advisor is unavailable until GROQ_API_KEY is configured."
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a smart farming assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip() # type: ignore
    except Exception as e:
        return f"Error querying Groq: {str(e)}"

# --------------------
# Routes
# --------------------
@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/medicine")
@login_required
def medicine():
    return render_template("medicine.html")

@app.route("/orders")
@login_required
def orders():
    return render_template("orders.html")


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")

@app.route("/crops")
@login_required
def crops():
    return render_template("crops.html")

@app.route("/planner")
@login_required
def planner():
    return render_template("planner.html")

@app.route("/disease")
@login_required
def disease():
    return render_template("disease.html")

@app.route("/market")
@login_required
def market():
    return render_template("market.html")

# --------------------
# Market Price API (Real-time crop prices)
# --------------------
@app.route("/api/market_prices", methods=["GET"])
def api_market_prices():
    """
    Returns real-time market prices for various crops.
    In production, this would connect to AGMARKNET or other price APIs.
    """
    # Realistic Indian agricultural prices (per quintal in INR)
    # These are based on actual market rates
    market_prices = [
        {"crop": "Wheat", "price": 2275, "unit": "per quintal", "location": "Delhi", "change": "+2.3%"},
        {"crop": "Rice (Basmati)", "price": 3500, "unit": "per quintal", "location": "Kolkata", "change": "+1.1%"},
        {"crop": "Rice (Non-Basmati)", "price": 1850, "unit": "per quintal", "location": "Chennai", "change": "+0.8%"},
        {"crop": "Tomato", "price": 1200, "unit": "per quintal", "location": "Mumbai", "change": "-3.2%"},
        {"crop": "Potato", "price": 950, "unit": "per quintal", "location": "Delhi", "change": "+1.5%"},
        {"crop": "Onion", "price": 1100, "unit": "per quintal", "location": "Ahmedabad", "change": "-1.8%"},
        {"crop": "Soybean", "price": 4500, "unit": "per quintal", "location": "Indore", "change": "+2.1%"},
        {"crop": "Cotton", "price": 6200, "unit": "per quintal", "location": "Rajkot", "change": "+0.5%"},
        {"crop": "Sugarcane", "price": 350, "unit": "per quintal", "location": "Lucknow", "change": "+0.2%"},
        {"crop": "Mustard", "price": 5200, "unit": "per quintal", "location": "Jaipur", "change": "+1.9%"},
        {"crop": "Gram", "price": 4800, "unit": "per quintal", "location": "Bhopal", "change": "+0.7%"},
        {"crop": "Maize", "price": 1960, "unit": "per quintal", "location": "Nagpur", "change": "-0.4%"},
        {"crop": "Groundnut", "price": 5500, "unit": "per quintal", "location": "Rajkot", "change": "+1.2%"},
        {"crop": "Tur (Arhar)", "price": 6500, "unit": "per quintal", "location": "Hyderabad", "change": "+2.5%"},
        {"crop": "Moong", "price": 7200, "unit": "per quintal", "location": "Jaipur", "change": "+1.8%"},
    ]
    crop = request.args.get("crop", "").strip().lower()
    location = request.args.get("location", "").strip().lower()
    min_price = request.args.get("minPrice", type=float, default=0) or 0

    filtered_prices = [
        item for item in market_prices
        if (not crop or crop in item["crop"].lower())
        and (not location or location in item["location"].lower())
        and item["price"] >= min_price
    ]
    return jsonify({"status": "ok", "prices": filtered_prices})

@app.route("/weather")
@login_required
def weather():
    return render_template("weather.html")


@app.route("/fertilizer")
@login_required
def fertilizer():
    return render_template("fertilizer.html")

@app.route("/advisor")
@login_required
def advisor():
    return render_template("advisor.html")


@app.route("/community")
@login_required
def community():
    return render_template("community.html")


@app.route("/ai_advisor")
@login_required
def ai_advisor():
    return render_template("ai_advisor.html")



@app.route("/crop-consultant-contact")
@login_required
def crop_consultant_contact():
    return render_template("crop_consultant_contact.html")

# --------------------
# Farm Gallery APIs
# --------------------
class UserFarmImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

with app.app_context():
    db.create_all()

@app.route("/farm-gallery")
@login_required
def farm_gallery():
    return render_template("farm_gallery.html")

@app.route("/api/user_farm_images", methods=["GET"])
def api_user_farm_images():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    images = UserFarmImage.query.filter_by(user_id=session['user_id']).order_by(UserFarmImage.created_at.desc()).all()
    return jsonify([{
        "id": img.id,
        "url": f"/uploads/farm_images/{img.filename}",
        "name": img.original_name,
        "size": img.size,
        "created_at": img.created_at.isoformat() if img.created_at else None
    } for img in images])

@app.route("/api/user_farm_images/<int:image_id>", methods=["DELETE"])
def api_delete_farm_image(image_id):
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    img = UserFarmImage.query.filter_by(id=image_id, user_id=session['user_id']).first()
    if not img:
        return jsonify({"status": "error", "message": "Image not found"}), 404
    
    try:
        os.remove(os.path.join(UPLOAD_DIR, "farm_images", img.filename))
    except:
        pass
    
    db.session.delete(img)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/api/upload_farm_images", methods=["POST"])
def api_upload_farm_images():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    os.makedirs(os.path.join(UPLOAD_DIR, "farm_images"), exist_ok=True)
    uploaded = 0
    
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if file.filename and allowed_file(file.filename):
                timestamp = str(int(time.time()))
                filename = f"{session['user_id']}_{timestamp}_{secure_filename(file.filename)}"
                filepath = os.path.join(UPLOAD_DIR, "farm_images", filename)
                file.save(filepath)
                
                new_img = UserFarmImage(
                    user_id=session['user_id'], # type: ignore
                    filename=filename, # type: ignore
                    original_name=file.filename, # type: ignore
                    size=file.content_length or os.path.getsize(filepath) # type: ignore
                )
                db.session.add(new_img)
                uploaded += 1
        
        db.session.commit()
    
    return jsonify({"status": "ok", "uploaded": uploaded, "count": uploaded})

import time  # Add for timestamp

# --------------------
# Database APIs for Authentication
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    required_fields = ["first_name", "last_name", "city", "contact", "email", "username", "password", "confirm_password"]
    missing_fields = [field for field in required_fields if not str(data.get(field, "")).strip()]
    if missing_fields:
        return jsonify({"status": "error", "message": "Please fill all required fields"}), 400
    
    # Check if username or email already exists
    existing_user = User.query.filter(
        (User.username == data.get("username")) | 
        (User.email == data.get("email"))
    ).first()
    
    if existing_user:
        return jsonify({"status": "error", "message": "Username or email already exists"}), 400
    
    # Check password match
    if data.get("password") != data.get("confirm_password"):
        return jsonify({"status": "error", "message": "Passwords do not match"}), 400
    
    new_user = User(
        first_name=data.get("first_name"), # type: ignore
        last_name=data.get("last_name"), # type: ignore
        city=data.get("city"), # type: ignore
        contact=data.get("contact"), # type: ignore
        email=data.get("email"), # type: ignore
        username=data.get("username"), # type: ignore
        password=data.get("password")  # In production, hash this! # type: ignore
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"status": "ok", "message": "Registration successful!", "id": new_user.id})

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    
    user = User.query.filter_by(username=username, password=password).first()
    
    if user:
        session['user_id'] = user.id
        session['username'] = user.username
        session['first_name'] = user.first_name
        return jsonify({
            "status": "ok", 
            "message": "Login successful!",
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "city": user.city,
                "contact": user.contact,
                "email": user.email,
                "username": user.username
            }
        })
    else:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route("/api/profile", methods=["GET", "PUT"])
def api_profile():
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Login required"}), 401

    if request.method == "GET":
        return jsonify({
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "city": user.city,
            "contact": user.contact,
            "email": user.email,
            "username": user.username,
        })

    data = request.get_json() or {}
    first_name = str(data.get("first_name", user.first_name)).strip()
    last_name = str(data.get("last_name", user.last_name)).strip()
    city = str(data.get("city", user.city)).strip()
    contact = str(data.get("contact", user.contact)).strip()
    email = str(data.get("email", user.email)).strip()

    if not all([first_name, last_name, city, contact, email]):
        return jsonify({"status": "error", "message": "All profile fields are required"}), 400

    existing_user = User.query.filter(User.email == email, User.id != user.id).first()
    if existing_user:
        return jsonify({"status": "error", "message": "Email already exists"}), 400

    user.first_name = first_name
    user.last_name = last_name
    user.city = city
    user.contact = contact
    user.email = email
    db.session.commit()

    session["first_name"] = user.first_name
    return jsonify({"status": "ok"})

# --------------------
# Database APIs for Authentication (existing)
# --------------------

# --------------------
# User-specific Data APIs
# --------------------
@app.route("/api/user_crops", methods=["GET", "POST"])
def api_user_crops():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    user_id = session['user_id']
    
    if request.method == "GET":
        crops = UserCrop.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": c.id,
            "name": c.name,
            "sowingDate": c.sowing_date.isoformat() if c.sowing_date else None,
            "harvestDate": c.harvest_date.isoformat() if c.harvest_date else None,
            "area": c.area,
            "status": c.status,
            "notes": c.notes
        } for c in crops])
    
    data = request.get_json() or {}
    crop_name = str(data.get("name", "")).strip()
    if not crop_name:
        return jsonify({"status": "error", "message": "Crop name is required"}), 400

    area = float(data.get("area", 0) or 0)
    if area <= 0:
        return jsonify({"status": "error", "message": "Area must be greater than 0"}), 400

    new_crop = UserCrop(
        user_id=user_id, # type: ignore
        name=crop_name, # type: ignore
        sowing_date=parse_date(data.get("sowingDate")), # type: ignore
        harvest_date=parse_date(data.get("harvestDate")), # type: ignore
        area=area, # type: ignore
        status=data.get("status", "Planned"), # type: ignore
        notes=data.get("notes") # type: ignore
    )
    db.session.add(new_crop)
    db.session.commit()
    return jsonify({"status": "ok", "id": new_crop.id})

@app.route("/api/user_crops/<int:crop_id>", methods=["PUT", "DELETE"])
def api_user_crop_detail(crop_id):
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    crop = UserCrop.query.filter_by(id=crop_id, user_id=session['user_id']).first()
    if not crop:
        return jsonify({"status": "error", "message": "Crop not found"}), 404
    
    if request.method == "DELETE":
        db.session.delete(crop)
        db.session.commit()
        return jsonify({"status": "ok"})
    
    # PUT update
    data = request.get_json() or {}
    crop.name = data.get("name", crop.name)
    crop.sowing_date = parse_date(data.get("sowingDate")) or crop.sowing_date
    crop.harvest_date = parse_date(data.get("harvestDate"))
    crop.area = float(data.get("area", crop.area))
    crop.status = data.get("status", crop.status)
    crop.notes = data.get("notes")
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route("/api/planner_tasks/sync", methods=["POST"])
def api_sync_planner_tasks():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401

    sync_system_tasks_for_user(session['user_id'])
    return jsonify({"status": "ok"})

@app.route("/api/planner_tasks", methods=["GET", "POST"])
def api_planner_tasks():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401

    user_id = session['user_id']
    sync_system_tasks_for_user(user_id)

    if request.method == "GET":
        status_filter = request.args.get("status", "").strip()
        query = PlannerTask.query.filter_by(user_id=user_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        tasks = query.order_by(
            PlannerTask.due_date.is_(None),
            PlannerTask.due_date.asc(),
            PlannerTask.created_at.desc()
        ).all()
        return jsonify([serialize_planner_task(task) for task in tasks])

    data = request.get_json() or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify({"status": "error", "message": "Task title is required"}), 400

    crop_id = data.get("crop_id")
    if crop_id:
        crop = UserCrop.query.filter_by(id=crop_id, user_id=user_id).first()
        if not crop:
            return jsonify({"status": "error", "message": "Selected crop not found"}), 404

    task = PlannerTask(
        user_id=user_id, # type: ignore[arg-type]
        crop_id=crop_id, # type: ignore[arg-type]
        title=title, # type: ignore[arg-type]
        category=str(data.get("category", "General")).strip() or "General", # type: ignore[arg-type]
        due_date=parse_date(data.get("due_date")), # type: ignore[arg-type]
        priority=str(data.get("priority", "Medium")).strip() or "Medium", # type: ignore[arg-type]
        status=str(data.get("status", "Pending")).strip() or "Pending", # type: ignore[arg-type]
        notes=str(data.get("notes", "")).strip() or None, # type: ignore[arg-type]
        source="manual", # type: ignore[arg-type]
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"status": "ok", "task": serialize_planner_task(task)})

@app.route("/api/planner_tasks/<int:task_id>", methods=["PUT", "DELETE"])
def api_planner_task_detail(task_id):
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401

    task = PlannerTask.query.filter_by(id=task_id, user_id=session['user_id']).first()
    if not task:
        return jsonify({"status": "error", "message": "Task not found"}), 404

    if request.method == "DELETE":
        db.session.delete(task)
        db.session.commit()
        return jsonify({"status": "ok"})

    data = request.get_json() or {}
    if "title" in data:
        task.title = str(data.get("title", task.title)).strip() or task.title
    if "category" in data:
        task.category = str(data.get("category", task.category)).strip() or task.category
    if "priority" in data:
        task.priority = str(data.get("priority", task.priority)).strip() or task.priority
    if "status" in data:
        task.status = str(data.get("status", task.status)).strip() or task.status
    if "notes" in data:
        task.notes = str(data.get("notes", "")).strip() or None
    if "due_date" in data:
        task.due_date = parse_date(data.get("due_date"))

    db.session.commit()
    return jsonify({"status": "ok", "task": serialize_planner_task(task)})

@app.route("/api/user_medicine_orders", methods=["GET", "POST", "DELETE"])
def api_user_medicine_orders():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    user_id = session['user_id']
    
    if request.method == "GET":
        orders = UserMedicineOrder.query.filter_by(user_id=user_id).all()
        return jsonify([{
            "id": o.id,
            "items": len(normalize_medicine_order_data(o.order_data).get('items', [])),
            "order_data": normalize_medicine_order_data(o.order_data),
            "total": float(o.total or 0),
            "date": (o.created_at.strftime("%Y-%m-%d") if o.created_at else "N/A"),
            "status": o.status or "Pending"
        } for o in orders])

    if request.method == "DELETE":
        UserMedicineOrder.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({"status": "ok"})
    
    data = request.get_json() or {}
    normalized_order_data = normalize_medicine_order_data(data.get("order_data"))
    new_order = UserMedicineOrder(
        user_id=user_id, # type: ignore
        order_data=normalized_order_data, # type: ignore
        total=float(data.get("total", 0)), # type: ignore
        status=data.get("status", "Pending") # type: ignore
    )
    db.session.add(new_order)
    db.session.commit()
    return jsonify({"status": "ok", "id": new_order.id})

@app.route("/api/user_medicine_orders/<int:order_id>", methods=["DELETE"])
def api_user_medicine_order_delete(order_id):
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Login required"}), 401
    
    order = UserMedicineOrder.query.filter_by(id=order_id, user_id=session['user_id']).first()
    if not order:
        return jsonify({"status": "error", "message": "Order not found"}), 404
    
    db.session.delete(order)
    db.session.commit()
    return jsonify({"status": "ok"})

# --------------------
# Legacy APIs disabled for account isolation
# --------------------
@app.route("/api/farmers", methods=["GET", "POST"])
def api_farmers():
    return jsonify({
        "status": "error",
        "message": "This legacy shared endpoint is disabled to protect per-user account isolation."
    }), 403

@app.route("/api/orders", methods=["GET", "POST"])
def api_orders():
    return jsonify({
        "status": "error",
        "message": "This legacy shared endpoint is disabled to protect per-user account isolation."
    }), 403

# --------------------
# Crop image analysis
# --------------------
@app.route("/api/analyze_crop", methods=["POST"])
def api_analyze_crop():
    if "image" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename) # type: ignore
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        result = analyze_crop_image(filepath)
        return jsonify(result)
    return jsonify({"error": "Invalid file"}), 400

# --------------------
# AI Agent endpoint
# --------------------
@app.route("/api/agent", methods=["POST"])
def api_agent():
    data = request.get_json() or {}
    question = data.get("question", "")
    disease_info = data.get("disease_info", {})

    if disease_info and "disease_name" in disease_info:
        disease_name = disease_info["disease_name"]
        groq_answer = query_groq_agent(disease_name, question)
        ai_response = (
            f"Disease detected: {disease_name}\n"
            f"Severity: {disease_info.get('severity','unknown')}\n"
            f"Suggested solution: {disease_info.get('suggested_solution','N/A')}\n\n"
            f"Agent info:\n{groq_answer}"
        )

    else:
        # AI Farmer Advisor
        system_prompt = "You are a Professional advisor for farmers. Give all the answers of questions asked by the farmers. in professional tone."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        
        try:
            groq_response = client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=messages,
                temperature=0.7
            )
            ai_response = groq_response.choices[0].message.content.strip() # type: ignore
        except Exception:
            ai_response = "Thank you for contacting. Please ask your farming question."


    return jsonify({"response": ai_response}) # type: ignore

# --------------------
# Run Flask
# --------------------
if __name__ == "__main__":
    app.run(debug=True)
