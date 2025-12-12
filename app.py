import streamlit as st
from datetime import datetime
import numpy as np
import pandas as pd
import hashlib
import sqlite3
from PIL import Image
from auth import require_auth,login_signup_ui  # LOGIN SYSTEM
import plotly
import plotly.express
import gdown
import os
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array, load_img
import tensorflow as tf
from utils import  save_listing, load_user_listings
from io import BytesIO
from utils import init_db
import base64
import pydeck as pdk
from utils import (
    create_chatroom, send_message,
    get_chatroom_messages, search_messages,DB_PATH,
    list_user_chats
)
# =======================================================
# PAGE CONFIG + CSS
# =======================================================
st.set_page_config(
    page_title="SmartCycle - AI Circular Marketplace",
    page_icon="♻️",
    layout="wide"
)

st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    padding: 20px;
    border-radius: 12px;
    color: white;
    margin: 10px 0;
}
.defect-badge {
    display: inline-block;
    background: #fee2e2;
    color: #991b1b;
    padding: 4px 12px;
    border-radius: 20px;
    margin: 4px;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)

# =======================================================
# SESSION STATE INITIALIZATION
# =======================================================
def init_session():
    defaults = {
        "item_list": [],
        "nearby_shops": [],
        "selected_item": None,
        "user": None,
        "page": "Dashboard"
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()
init_db()

MODEL_PATH = "item_analyzer_model.h5"
GDRIVE_ID = "1zGqHM8xOEmNDj3EAuxxxruubNjL_Ksri"
MODEL_URL = f"https://drive.google.com/uc?id={GDRIVE_ID}"

@st.cache_resource
def load_cnn_model():
    # Download once if not present
    if not os.path.exists(MODEL_PATH):
        st.info("Downloading AI model…")
        gdown.download(MODEL_URL, MODEL_PATH, quiet=False)
    # Load model from local file
    model = load_model(MODEL_PATH)
    return model

cnn_model = load_cnn_model()
# =======================================================
# SIMULATED AI CORE
# =======================================================
class ItemAnalyzer:
    CATEGORIES = ['Camera', 'Chair', 'CoffeeMaker', 'Laptop', 'Shoe', 'Sofa']
    DEFECTS = ['Scratch', 'Dent', 'Discoloration', 'Minor Crack', 'Wear & Tear', 'Screen Issues']

    @staticmethod
    def analyze_image(uploaded_file_or_pil):
        # If already a PIL Image, use it; else open
        if isinstance(uploaded_file_or_pil, Image.Image):
            img = uploaded_file_or_pil
        else:
            img = Image.open(uploaded_file_or_pil).convert('RGB')

        # Resize and normalize
        img = img.resize((128, 128))
        img_array = np.array(img) / 255.0
        img_array = np.expand_dims(img_array, axis=0)

        # Predict class
        pred_probs = cnn_model.predict(img_array, verbose=0)
        pred_class_idx = np.argmax(pred_probs, axis=1)[0]
        model_name = ItemAnalyzer.CATEGORIES[pred_class_idx]
        CATEGORY_MAP = {
        "Camera": "Electronics",
        "Laptop": "Electronics",
        "CoffeeMaker": "Appliances",
        "Chair": "Furniture",
        "Sofa": "Furniture",
        "Shoe": "Clothing"
    }
        category = CATEGORY_MAP.get(model_name, "Other")
        # Simulate defects & condition
        condition_score = float(np.random.uniform(0.7, 0.99))
        defects = list(np.random.choice(ItemAnalyzer.DEFECTS, size=np.random.randint(0, 3), replace=False))

        return {
            "category": category,
            "model": model_name,
            "condition_score": condition_score,
            "defects": defects,
            "confidence": float(np.max(pred_probs))
        }





class PricingEngine:
    @staticmethod
    def suggest_price(score, category, defects_count):
        base = {"Electronics": 500, "Appliances": 150, "Furniture": 200, "Clothing": 50}.get(category, 100)
        price = base * score * 1.1
        price *= (1 - defects_count * 0.05)

        return {
            "suggested_price": float(price),
            "min_price": float(price * 0.7),
            "max_price": float(price * 1.3),
            "quick_sale_price": float(price * 0.85)
        }

class LCACalculator:
    IMPACT = {
        'Electronics': {'co2': 50, 'water': 200, 'energy': 150},
        'Appliances': {'co2': 30, 'water': 100, 'energy': 80},
        'Furniture': {'co2': 20, 'water': 50, 'energy': 30},
        'Clothing': {'co2': 5, 'water': 30, 'energy': 10},
    }

    @staticmethod
    def calculate(category, score):
        imp = LCACalculator.IMPACT.get(category, {'co2': 10, 'water': 50, 'energy': 20})
        return {
            "co2_saved": imp['co2'] * score,
            "water_saved": imp['water'] * score,
            "energy_saved": imp['energy'] * score,
            "summary": f"Reusing saves ~{imp['co2'] * score:.0f}kg CO₂, {imp['water'] * score:.0f}L water, {imp['energy'] * score:.0f} kWh!"
        }

class RecommendationEngine:
    @staticmethod
    def get_shops(lat, lon):
        seed = int((lat * 1000 + lon * 1000)) % (2**32)
        np.random.seed(seed)

        shops = []
        for i in range(np.random.randint(3, 7)):
            shops.append({
                "id": i,
                "name": f"Repair Shop #{i+1}",
                "distance": float(np.random.uniform(0.5, 5)),
                "rating": float(np.random.uniform(4.0, 5.0)),
                "reviews": np.random.randint(20, 200),
                "eta_days": np.random.randint(1, 5),
                "repair_cost_estimate": float(np.random.uniform(30, 150)),
                "services": list(np.random.choice(
                    ["Screen Fix", "Battery Replace", "Hardware Repair", "Water Damage"],
                    size=np.random.randint(1, 3),
                    replace=False
                ))
            })
        return sorted(shops, key=lambda x: x["distance"])

# =======================================================
# PAGES
# =======================================================
def back_button():
    if st.button("⬅️ Back to Dashboard"):
        st.session_state.page = "Dashboard"
        st.rerun()

def settings_page():
    back_button()
    st.markdown("## ⚙️ Settings & Profile")
    tab1, tab2, tab3 = st.tabs(["👤 Profile", "🛠️ Preferences", "🔒 Privacy"])
    user = st.session_state.user

    # Profile
    with tab1:
        st.markdown("### Update Profile")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", value=user["name"])
            email = st.text_input("Email", value=user["email"], disabled=True)
        with col2:
            location = st.text_input("Location", value=user.get("location", ""))
            user_type = st.selectbox("Account Type", ["Buyer", "Seller", "Repair Shop"], index=1)
        if st.button("💾 Save Changes", type="primary"):
            user["name"] = full_name
            user["location"] = location
            user["type"] = user_type
            st.success("Profile updated successfully!")

    # Preferences
    with tab2:
        st.markdown("### App Preferences")
        st.checkbox("Receive Email Notifications", value=True)
        st.checkbox("Show Profile in Public Directory", value=True)
        st.checkbox("Allow My Data for ML Optimization", value=False)

    # Privacy
    with tab3:
        st.markdown("### Privacy Settings")
        st.info("SmartCycle automatically removes EXIF, GPS, and sensitive metadata from all uploads.")
        st.checkbox("Opt-In to Sustainability Research Dataset", value=False)

# ====================== Upload Item Page ======================
from io import BytesIO
from PIL import Image

def upload_item_page():
    st.markdown("""
### 📘 How to Use This Page

1. **Upload clear photos** of your item using the uploader below.  
2. Our AI will automatically:
   - Detect the **item type** (model)
   - Assign the correct **category** (Electronics, Appliances, Furniture, Clothing)
   - Estimate the **condition score**
   - Suggest a **fair price**  
3. You don't need to choose a category — it is **auto-detected** using AI.
4. After analysis, click **Save Listing** to publish your item.
5. Your listing will appear in: 
   - 🌐 **Community Feed** which buyers can view and contact you 
6. Even if you log out, your uploaded items **will not be deleted**.

Upload the best possible photo for highest accuracy!
""")

    if st.session_state.user is None:
        st.error("You need to log in to upload an item."); st.session_state.page="Dashboard"; st.stop()
    back_button()
    st.markdown("## 📸 Upload & Analyze Item")
    uploaded_files = st.file_uploader("Upload item photos", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
    if uploaded_files:
        uploaded_image=uploaded_files[0]
        st.success(f"{len(uploaded_files)} image(s) uploaded")
        img=Image.open(uploaded_image).convert("RGB")
        st.image(img,width=400)
        analysis=ItemAnalyzer.analyze_image(img)
        prices=PricingEngine.suggest_price(analysis["condition_score"],analysis["category"],len(analysis["defects"]))
        lca=LCACalculator.calculate(analysis["category"],analysis["condition_score"])
        st.metric("Category",analysis["category"])
        st.metric("Model",analysis["model"])
        st.metric("Condition",f"{analysis['condition_score']*100:.0f}%")
        st.metric("Confidence",f"{analysis['confidence']*100:.0f}%")
        description=st.text_area("Describe this item")
        if st.button("Create Listing"):
            buf=BytesIO(); img.save(buf,format="PNG"); img_b64=base64.b64encode(buf.getvalue()).decode('utf-8')
            item_data={"analysis":analysis,"prices":prices,"lca":lca,"description":description,"image":img_b64,"status":"active","timestamp":datetime.now().isoformat(),"user":st.session_state.user["email"]}
            save_listing(st.session_state.user["email"],item_data)
            st.session_state.item_list=load_user_listings(st.session_state.user["email"])
            st.success("Listing created successfully!"); st.balloons(); 


# ====================== Dashboard ======================
def dashboard_page():
    
    st.markdown("## 📊 Dashboard Overview")
    user = st.session_state.user
    user.setdefault("created_at", datetime.now())
    user.setdefault("items_count", 0)
    user.setdefault("co2_saved", 0)
    my_items = [i for i in st.session_state.item_list if i.get("user") == user.get("email")]

    # ================= Quick Navigation =================
    st.markdown("### 🔹 Quick Navigation")
    nav_cols = st.columns(6)
    pages = [
        ("📦 Upload Item", "Upload Item"),
        
        ("🔧 Repair Shops", "Repair Shops"),
        ("⚙️ Settings", "Settings"),
        ("💬 Messages", "Messages"),
        ("🌐 Feed", "Feed")  # New feed page
    ]
    for col, (title, page_name) in zip(nav_cols, pages):
        if col.button(title):
            st.session_state.page = page_name
            st.rerun()

    st.divider()

    # ================= Metrics Row =================
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Items Listed", user.get('items_count', 0))
    with col2: st.metric("CO₂ Saved", f"{user.get('co2_saved', 0):.0f} kg", delta="🌍")
    with col3: st.metric("Green Score", f"{min(user.get('items_count',0)*10,100)}/100")
    with col4: st.metric("Member Since", user["created_at"].strftime("%b %Y"))

    st.divider()

    # ================= Tabs =================
    tab1, tab2, tab3, tab4 = st.tabs(["📦 My Listings", "🌍 Impact Report", "📈 Performance", "💰 Earnings"])

    # ===== My Listings =====
    with tab1:
        st.markdown("### Your Active Listings")
        if my_items:
            for item in my_items:
                img_data = item["image"]
                if isinstance(img_data, str):
                    img_bytes = base64.b64decode(img_data)
                    st.image(img_bytes, width=300)
                else:
                    st.image(img_data, width=300)

                st.markdown(f"**Model:** {item['analysis']['model']} | **Category:** {item['analysis']['category']}")
                st.markdown(f"**Condition:** {item['analysis']['condition_score']*100:.0f}% | **Price:** ${item['prices']['suggested_price']:.0f}")
                st.markdown(f"**Description:** {item.get('description','No description')}")
                st.divider()
        else:
            st.info("You haven't listed any items yet.")

    # ===== Impact Report =====
    with tab2:
        st.markdown("### Environmental Impact Summary")
        if my_items:
            impact_df = pd.DataFrame([{
                "Item": i['analysis']['model'],
                "CO₂ (kg)": i['lca']['co2_saved'],
                "Water (L)": i['lca']['water_saved'],
                "Energy (kWh)": i['lca']['energy_saved'],
            } for i in my_items])
            fig = plotly.express.bar(
                impact_df,
                x="Item",
                y=["CO₂ (kg)", "Water (L)", "Energy (kWh)"],
                title="Environmental Savings by Item",
                barmode="group"
            )
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("Total Environmental Savings")
            st.markdown(f"""
            - **CO₂ Saved:** {impact_df['CO₂ (kg)'].sum():.0f} kg  
            - **Water Saved:** {impact_df['Water (L)'].sum():.0f} L  
            - **Energy Saved:** {impact_df['Energy (kWh)'].sum():.0f} kWh  
            """)
        else:
            st.info("Impact data will appear once you upload items 🌱")
  
# ====================== Marketplace Page ======================
def marketplace_page():
    back_button()
    """Browse and search marketplace"""
    st.markdown("## 🛒 Marketplace")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        category_filter = st.selectbox("Category", ["All", "Electronics", "Appliances", "Furniture", "Clothing"])
    with col2:
        price_range = st.slider("Price Range", 0, 1000, (0, 1000))
    with col3:
        condition_min = st.slider("Min Condition", 0.0, 1.0, 0.5, step=0.1)
    with col4:
        sort_by = st.selectbox("Sort By", ["Newest", "Price: Low to High", "Price: High to Low", "Eco Impact"])
    
    # Ensure items is a list
    filtered_items = list(st.session_state.get('items', []))
    
    if category_filter != "All":
        filtered_items = [i for i in filtered_items if i['analysis']['category'] == category_filter]
    
    filtered_items = [i for i in filtered_items 
                     if price_range[0] <= i['prices']['suggested_price'] <= price_range[1]]
    
    filtered_items = [i for i in filtered_items 
                     if i['analysis']['condition_score'] >= condition_min]
    
    # Sorting logic...

    # Sort
    if sort_by == "Price: Low to High":
        filtered_items.sort(key=lambda x: x['prices']['suggested_price'])
    elif sort_by == "Price: High to Low":
        filtered_items.sort(key=lambda x: x['prices']['suggested_price'], reverse=True)
    elif sort_by == "Eco Impact":
        filtered_items.sort(key=lambda x: x['lca']['co2_saved'], reverse=True)
    
    if not filtered_items:
        st.info("📭 No items found. Try adjusting filters.")
        return
    
    st.markdown(f"### Found {len(filtered_items)} item(s)")
    
    # Display items in a grid
    cols = st.columns(3)
    for idx, item in enumerate(filtered_items):
        with cols[idx % 3]:
            st.markdown(
                f"<div style='border:1px solid #e5e7eb; padding:10px; border-radius:12px; margin:5px;'>",
                unsafe_allow_html=True
            )
            # Use uploaded image if exists, else placeholder
            if 'image' in item:
                st.image(item['image'], width=150)
            else:
                st.image(f"https://via.placeholder.com/150?text={item['analysis']['model']}")
            
            st.markdown(f"**{item['analysis']['model']}**")
            st.caption(f"Category: {item['analysis']['category']}")
            st.caption(f"Condition: {item['analysis']['condition_score']*100:.0f}%")
            st.metric("Price", f"${item['prices']['suggested_price']:.0f}")
            st.caption(f"CO₂ Saved: {item['lca']['co2_saved']:.0f}kg")
            
            if st.button("View Details", key=f"item_{item['id']}"):
                st.session_state.selected_item = item
                st.experimental_rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)

# ====================== Repair Shops Page ======================
CITY_COORDS = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Hyderabad": (17.3850, 78.4867),
}
def repair_shops_page():
    back_button()
    st.markdown("## 🔧 Find Repair Shops")
    
    # --- Filters / Search ---
    col1, col2, col3 = st.columns(3)
    
    with col1:
        service_filter = st.selectbox(
            "Filter by Service",
            ["All", "Screen Fix", "Battery Replace", "Hardware Repair", "Water Damage"]
        )
        
    with col2:
        sort_by = st.selectbox(
            "Sort By",
            ["Distance", "Rating", "Repair Cost"]
        )
        
    with col3:
        search_text = st.text_input("Search Shop Name")
    
    # --- Load Shops (simulated / DB) ---
    if st.button("🔍 Search Shops", type="primary"):
        st.session_state.nearby_shops = RecommendationEngine.get_shops(0, 0)  # lat/lon ignored here

    # --- Display Shops ---
    if 'nearby_shops' in st.session_state:
        shops = st.session_state.nearby_shops
        
        # --- Apply Filters ---
        if service_filter != "All":
            shops = [s for s in shops if service_filter in s['services']]
        
        if search_text.strip():
            shops = [s for s in shops if search_text.lower() in s['name'].lower()]
        
        # --- Sorting ---
        if sort_by == "Rating":
            shops.sort(key=lambda x: x['rating'], reverse=True)
        elif sort_by == "Repair Cost":
            shops.sort(key=lambda x: x['repair_cost_estimate'])
        elif sort_by == "Distance":
            shops.sort(key=lambda x: x['distance'])  # simulated
        
        st.markdown(f"### Found {len(shops)} Repair Shops")
        
        # --- Display Shop Cards ---
        for shop in shops:
            # Simulated coordinates for map link
            shop_lat = 19.07 + np.random.uniform(-0.05, 0.05)
            shop_lng = 72.87 + np.random.uniform(-0.05, 0.05)
            maps_url = f"https://www.google.com/maps/search/?api=1&query={shop_lat},{shop_lng}"
            
            st.markdown(
                f"<div style='border:1px solid #e5e7eb; padding:16px; border-radius:12px; margin:8px; background:white'>",
                unsafe_allow_html=True
            )
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"#### {shop['name']}")
                st.caption(f"Services: {', '.join(shop['services'])}")
                st.markdown(f"[📍 View on Google Maps]({maps_url})", unsafe_allow_html=True)
            
            with col2:
                st.metric("Distance", f"{shop['distance']:.1f} km")
                st.metric("Repair Cost", f"${shop['repair_cost_estimate']:.0f}")
            
            with col3:
                st.markdown(f"⭐ {shop['rating']:.1f} ({shop['reviews']} reviews)")
                st.markdown(f"**Ready in:** {shop['eta_days']} days")
            
            if st.button(f"💬 Contact {shop['name']}", key=f"shop_{shop['id']}"):
                st.session_state.selected_shop = shop
                st.experimental_rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)

def chat_page():
    import sqlite3
    from datetime import datetime

    back_button()

    # ------------------ PAGE HEADER + FEATURES ------------------
    st.markdown("""
    <div style="
        padding:20px; 
        background:transparent; 
        border-radius:12px; 
        margin-bottom:20px;
        border-left: 4px solid #2f80ed;
    ">
        <h2 style="margin-bottom:8px; color:#2f80ed;">💬 SmartCycle Messaging Center</h2>
        <p style="margin:0; font-size:15px; color:#ffff;">
            Manage all your conversations professionally. Connect with buyers, sellers, repair experts, or support.
        </p>
        <div style="
            padding:15px; 
            background:transparent; 
            border-radius:10px; 
            margin-top:12px; 
            border:1px solid #2f80ed;
            font-size:14px;
            line-height:1.5;
        ">
            <strong>How to use this page:</strong>
            <ul style="margin:5px 0 0 15px; padding:0;">
                <li>1️⃣ Select or search a chatroom from the left panel.</li>
                <li>2️⃣ View messages and reply in real-time in the right panel.</li>
                <li>3️⃣ Create new chatrooms or start a private chat by email.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ------------------ LOAD CHATROOMS ------------------
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM chatrooms ORDER BY id DESC")
    chatrooms = c.fetchall()
    conn.close()

    # Create default chatroom if none
    if len(chatrooms) == 0:
        default_id = create_chatroom("General Support")
        chatrooms = [(default_id, "General Support")]

    col1, col2 = st.columns([1, 2])

    # ================= LEFT PANEL =================
    with col1:
        st.markdown("### 🔍 Search Messages")
        msg_query = st.text_input("", placeholder="Search by email, message, or chatroom...")

        if msg_query.strip():
            results = search_messages(msg_query)
            st.markdown("### 🔎 Results")
            if len(results) == 0:
                st.info("No matching messages found.")
            for r in results:
                st.markdown(f"""
                <div style="
                    padding:12px; 
                    background:#eef3fb; 
                    border-radius:10px; 
                    margin-bottom:12px;
                    border:1px solid #d6ddea;
                    font-size:14px;
                ">
                    <strong>{r['sender']}</strong> in <em>{r['chatroom_name']}</em>:<br>
                    {r['message']}
                </div>
                """, unsafe_allow_html=True)
            st.stop()

        st.markdown("### 💬 Chatrooms")
        chatroom_names = {cid: name for cid, name in chatrooms}
        selected_chat_name = st.radio(
            "",
            [name for (_, name) in chatrooms],
            label_visibility="collapsed"
        )
        selected_chat_id = [cid for cid, name in chatrooms if name == selected_chat_name][0]

        # ---------------- Create Chatroom ----------------
        st.markdown("#### ➕ Create Chatroom")
        new_room = st.text_input("", placeholder="Ex: Laptop Repair Help")
        if st.button("Create"):
            if new_room.strip():
                create_chatroom(new_room.strip())
                st.success("Chatroom created!")
                st.rerun()

        # ---------------- Private Chat ----------------
        st.markdown("#### 🔐 Private Message")
        pm_email = st.text_input("User Email", placeholder="Enter email to chat privately...")
        if st.button("Start Private Chat"):
            if pm_email.strip():
                private_id = create_private_chatroom_if_not_exists(
                    st.session_state.user["email"], pm_email
                )
                st.success("Private chat ready!")
                st.session_state["force_chat_id"] = private_id
                st.rerun()

    # ================= RIGHT PANEL =================
    with col2:
        if "force_chat_id" in st.session_state:
            selected_chat_id = st.session_state["force_chat_id"]
            st.session_state.pop("force_chat_id", None)

        st.markdown(f"### 💬 Chat: **{selected_chat_name}**")

        messages = get_chatroom_messages(selected_chat_id)

        chat_container = st.container()

        with chat_container:
            for msg in messages:
                sender = msg["sender"]
                txt = msg["message"]
                t = msg["time"]

                if sender == st.session_state.user["email"]:
                    st.chat_message("user").write(f"{txt}\n\n*{t}*")
                else:
                    st.chat_message("assistant").write(f"**{sender}:** {txt}\n\n*{t}*")

        msg_input = st.chat_input("Type your message...")
        if msg_input:
            send_message(selected_chat_id, st.session_state.user["email"], msg_input)
            st.rerun()

def feed_page():
    back_button()
    st.markdown("## 🌐 Community Feed")
    st.caption("View all items uploaded by users across SmartCycle.")

    # ------------------------- Load all items from DB -------------------------
    all_users_items = []
    # Assuming you have a list of all registered users in DB
    import sqlite3, json
    from utils import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email FROM users")
    users = c.fetchall()

    for (email,) in users:
        c.execute("SELECT data_json FROM items WHERE user_email=? ORDER BY id DESC", (email,))
        rows = c.fetchall()
        for row in rows:
            item = json.loads(row[0])
            item["user"] = email  # Add email as seller
            all_users_items.append(item)
    conn.close()

    if not all_users_items:
        st.info("No items available in the feed yet. Upload something to get started!")
        return

    # ------------------------- Filters -------------------------
    st.markdown("### 🔍 Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        category_filter = st.selectbox(
            "Category",
            ["All"] + sorted({item["analysis"]["category"] for item in all_users_items})
        )

    with col2:
        sort_by = st.selectbox(
            "Sort By",
            ["Newest", "Price: Low to High", "Price: High to Low", "Condition"]
        )

    with col3:
        search = st.text_input("Search Model")

    # ------------------------- Apply Filters -------------------------
    filtered = all_users_items

    if category_filter != "All":
        filtered = [i for i in filtered if i["analysis"]["category"] == category_filter]

    if search.strip():
        filtered = [i for i in filtered if search.lower() in i["analysis"]["model"].lower()]

    # Sort
    if sort_by == "Newest":
        filtered = sorted(filtered, key=lambda x: x.get("timestamp",""), reverse=True)
    elif sort_by == "Price: Low to High":
        filtered = sorted(filtered, key=lambda x: x['prices']['suggested_price'])
    elif sort_by == "Price: High to Low":
        filtered = sorted(filtered, key=lambda x: x['prices']['suggested_price'], reverse=True)
    elif sort_by == "Condition":
        filtered = sorted(filtered, key=lambda x: x['analysis']['condition_score'], reverse=True)

    st.divider()

    # ------------------------- Display Feed -------------------------
    st.markdown("### 📦 All Listings")
    cols = st.columns(3)

    import base64
    from io import BytesIO

    for idx, item in enumerate(filtered):
        with cols[idx % 3]:
            st.markdown("""
                <div style="
                    background: #f7f9fa;
                    border-radius: 12px;
                    padding: 12px;
                    margin-bottom: 15px;
                    border: 1px solid #e5e7eb;
                ">
            """, unsafe_allow_html=True)

            # ----- Image decoding -----
            if "image" in item and item["image"]:
                try:
                    img_bytes = base64.b64decode(item["image"])
                    st.image(img_bytes, width=300)
                except Exception as e:
                    st.image("https://via.placeholder.com/300?text=No+Image")
            else:
                st.image("https://via.placeholder.com/300?text=No+Image")

            # ----- Item Info -----
            st.markdown(f"**{item['analysis']['model']}**")
            st.caption(f"Category: {item['analysis']['category']}")
            st.caption(f"Condition: {item['analysis']['condition_score']*100:.0f}%")
            st.metric("Price", f"${item['prices']['suggested_price']:.0f}")
            st.caption(f"Seller: {item['user']}")

            # ----- Contact Seller -----
            if st.button("Contact Seller", key=f"contact_{idx}"):
                st.session_state.selected_item = item
                st.session_state.page = "Messages"
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# ====================== Main ======================
def main():
    require_auth()
    if st.session_state.user is None:
        return

    st.sidebar.markdown(f"### 👤 {st.session_state.user['name']}")
    nav = st.sidebar.radio(
        "Navigation",
        ["Dashboard", "Upload Item", "Repair Shops","Messages",   # <-- add this
    "Feed","Settings"],
        index=["Dashboard", "Upload Item", "Repair Shops","Messages",   # <-- add this
    "Feed","Settings"].index(st.session_state.page)
    )

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.page = "Dashboard"
        st.stop()

    st.session_state.page = nav

    if nav == "Dashboard": dashboard_page()
    elif nav == "Upload Item": upload_item_page()

    elif nav == "Repair Shops": repair_shops_page()
    elif nav == "Settings": settings_page()
    elif nav == "Messages": 
        chat_page()
    elif nav == "Feed": feed_page()    
if __name__ == "__main__":
    main()
