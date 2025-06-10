import requests
from flask import Flask, jsonify, request, render_template
import mysql.connector
from flask import Flask, render_template, request, url_for, redirect, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user
import os
import io
from sqlalchemy_utils import get_class_by_table
import copy
from sqlalchemy.orm.session import make_transient
from flask import session
from flask import Flask, render_template, request, url_for, redirect, send_file
import json

app = Flask(__name__,
            static_url_path='',
            static_folder='html',
            template_folder='html')

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SECRET_KEY"] = "supersecret"

# Initialisation de la base de données et du login manager
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

# Définition du modèle User
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    preferedcity = db.Column(db.String(250), nullable=True)
    lastitinerary = db.Column(db.String(250), nullable=True)

# Création des tables dans la base de données
with app.app_context():
    db.create_all()

API_KEY = "05bd76f2bb03d89952c9044af9ef400d259423a4"
BASE_URL = "https://api.jcdecaux.com/vls/v3/stations"

@app.route('/ville')
def accueil():
    username = request.args.get("username")
    if username:
        user = User.query.filter_by(username=username).first()
        if user and user.lastitinerary:
            try:
                itinerary = json.loads(user.lastitinerary)
                ville = itinerary.get("ville")
                if ville:
                    return redirect(f"/ville.html?ville={ville}")
            except Exception as e:
                print("Erreur dans l’itinéraire favori :", e)
                # On continue normalement vers la page d’accueil

    return render_template('ville.html', ville="Nantes")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# Route pour inscription depuis le formulaire HTML
@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return "Nom d'utilisateur et mot de passe requis", 400

    existing_user = User.query.filter_by(username=username).first()

    if existing_user:
        # L'utilisateur existe déjà → on vérifie le mot de passe
        if existing_user.password == password:
            # Connexion réussie
            return redirect(f"/ville?username={username}")
        else:
            return "Mot de passe incorrect pour cet utilisateur.", 401

    # L'utilisateur n'existe pas → on l'inscrit
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()
    return redirect(f"/ville?username={username}")

# indispensable sinon la base ne peut pas être utilisée en consultation
@login_manager.user_loader
def loader_user(user_id):
    return db.session.get(User, user_id) #User.query.get(user_id)

# un exemple de fonction qui demande tous les utilisateurs
def load_all_users():
    return db.session.query(User).all()

@app.route("/admin/")
def admin():
    user = User(username="rene"+os.urandom(12).hex(),password="coty", preferedcity = "test", lastitinerary="test")
    db.session.add(user)
    db.session.commit()
    users = load_all_users()
    return render_template("admin.html", userlist=users)

@app.route('/stations/<ville>', methods=['GET'])
def get_stations(ville):
    url = f"{BASE_URL}?contract={ville}&apiKey={API_KEY}"
    response = requests.get(url)

    print("Statut HTTP:", response.status_code)  # Affiche le code HTTP
    print("Réponse brute:", response.text)  # Affiche la réponse brute

    if response.status_code != 200:
        return jsonify({"error": "Impossible de récupérer les données"}), 500

    stations_data = response.json()
    print("Données reçues:", stations_data)  # Affiche les données JSON reçues

    stations = [
        {
            "longitude": station["position"]["longitude"],
            "latitude": station["position"]["latitude"],
            "nom": station["name"],
            "vélos_disponibles": station["totalStands"]["availabilities"]["bikes"]
        }
        for station in stations_data
        if station["status"] == "OPEN" and station["totalStands"]["availabilities"]["bikes"] > 0
    ]

    return jsonify(stations)


@app.route('/villes_disponibles', methods=['GET'])
def get_villes_disponibles():
    url = f"{BASE_URL}/contracts?apiKey={API_KEY}"
    response = requests.get(url)

    print("Statut HTTP:", response.status_code)  # Affiche le code HTTP
    print("Réponse brute:", response.text)  # Affiche la réponse brute

    if response.status_code != 200:
        return jsonify({"error": "Impossible de récupérer les données"}), 500

    villes_data = response.json()
    print("Données reçues:", villes_data)  # Affiche les données JSON reçues

    villes = [ville["name"] for ville in villes_data]

    return jsonify(villes)

@app.route('/')
def index():
    return redirect('/ville')

@app.route('/get_favorite_url')
def get_favorite_url():
    username = request.args.get("username")
    user = User.query.filter_by(username=username).first()
    if user and user.lastitinerary:
        try:
            itinerary = json.loads(user.lastitinerary)
            ville = itinerary.get("ville")
            if ville:
                return jsonify({ "url": f"/ville.html?ville={ville}" })
        except Exception as e:
            print("Erreur parsing JSON:", e)
    return jsonify({ "url": None })


@app.route('/save_itinerary', methods=['POST'])
def save_itinerary_route():
    data = request.get_json()
    username = data.get('username')
    itinerary = data.get('itinerary')

    user = User.query.filter_by(username=username).first()
    if user:
        user.lastitinerary = json.dumps(itinerary)  # stocké sous forme de JSON
        db.session.commit()
        return "Trajet sauvegardé"
    return "Utilisateur non trouvé", 404

@app.route('/get_itinerary_json')
def get_itinerary_json():
    username = request.args.get('username')
    user = User.query.filter_by(username=username).first()
    if user and user.lastitinerary:
        return jsonify(json.loads(user.lastitinerary))
    return jsonify({})


# Lancement du serveur
if __name__ == "__main__":
    app.run(debug=True, port=80, host='0.0.0.0', use_reloader=False)
