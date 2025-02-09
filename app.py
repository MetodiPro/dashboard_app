from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
import os
from datetime import datetime
import plotly.graph_objs as go

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Cambia con una chiave più sicura
UPLOAD_FOLDER = 'data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Credenziali fisse per l'autenticazione
USERNAME = "admin@agcommunicationgrou.com"
PASSWORD = "Agcomm11"

# Lista delle sedi interne
INTERNAL_SITES = [
    "CASALNUOVO", "CASALNUOVO BETA", "CASORIA", "CASORIA 2", "CASORIA BETA",
    "MELITO", "MELITO BETA", "NAPOLI 1", "NAPOLI 1 BETA", "Recupero KO Post",
    "SAN MARCELLINO", "SMART CASORIA"
]

# Mappatura delle sedi accorpate
SITE_GROUPS = {
    "J.WOLF - CASALNUOVO": ["CASALNUOVO", "CASALNUOVO BETA"],
    "J.WOLF - CASORIA 1": ["CASORIA", "CASORIA BETA"],
    "J.WOLF - CASORIA 2 Mono Turno": ["CASORIA 2"],
    "J.WOLF - CASORIA SMART Mono Turno": ["SMART CASORIA"],
    "J.WOLF - MELITO": ["MELITO", "MELITO BETA"],
    "J.WOLF - NAPOLI": ["NAPOLI 1", "NAPOLI 1 BETA"],
    "J.WOLF - SAN MARCELLINO": ["SAN MARCELLINO"],
    "J.WOLF - SEDE Centrale BO": ["Recupero KO Post"]
}

# Obiettivi di produzione per il mese corrente
PRODUCTION_TARGETS = {
    "J.WOLF - CASALNUOVO": 190,
    "J.WOLF - CASORIA 1": 150,
    "J.WOLF - CASORIA 2 Mono Turno": 70,
    "J.WOLF - CASORIA SMART Mono Turno": 70,
    "J.WOLF - MELITO": 260,
    "J.WOLF - NAPOLI": 130,
    "J.WOLF - SAN MARCELLINO": 70,
    "J.WOLF - SEDE Centrale BO": 0
}

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('upload'))
        else:
            return render_template('login.html', error="Credenziali errate")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('upload.html', error="Nessun file selezionato")
        file = request.files['file']
        if file.filename == '':
            return render_template('upload.html', error="Nessun file selezionato")
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'contracts.xlsx')
            file.save(filepath)
            return redirect(url_for('produzione'))
    
    return render_template('upload.html')

@app.route('/produzione')
def produzione():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'contracts.xlsx')
    if not os.path.exists(filepath):
        return render_template('produzione.html', error="Nessun file caricato")
    
    # Carica il file Excel e filtra i dati
    df = pd.read_excel(filepath, engine='openpyxl')
    df['Data Inserimento'] = pd.to_datetime(df['Data Inserimento'], format='%d/%m/%Y', errors='coerce')
    today = datetime.today().date()
    current_month = today.month
    current_year = today.year
    days_elapsed = today.day
    working_days = 22

    # Funzione per calcolare i dati aggregati per le sedi raggruppate
    def compute_grouped_summary():
        summary = []
        daily_data = {}
        for group_name, sites in SITE_GROUPS.items():
            subset = df[df['Sede'].isin(sites)]
            inserted_today = len(subset[subset['Data Inserimento'].dt.date == today])
            closed_today = len(subset[(subset['Data Inserimento'].dt.date == today) & (subset['Stato'].isin(["CHIUSO", "IN LAVORAZIONE"]))])
            inserted_month = len(subset[(subset['Data Inserimento'].dt.month == current_month) & (subset['Data Inserimento'].dt.year == current_year)])
            closed_month = len(subset[(subset['Data Inserimento'].dt.month == current_month) & (subset['Data Inserimento'].dt.year == current_year) & (subset['Stato'].isin(["CHIUSO", "IN LAVORAZIONE"]))])
            target = PRODUCTION_TARGETS.get(group_name, 0)
            paf = round((closed_month / days_elapsed) * working_days) if days_elapsed > 0 else 0
            achievement_percent = round((paf / target) * 100) if target > 0 else 0
            
            summary.append({
                "Sede": group_name,
                "Inseriti Oggi": inserted_today,
                "Chiusi Oggi": closed_today,
                "Inseriti Mese": inserted_month,
                "Chiusi Mese": closed_month,
                "Obiettivo Assegnato": target,
                "PAF": paf,
                "% OBB.": achievement_percent
            })

            # Per il grafico giornaliero
            for day in subset['Data Inserimento'].dt.date.unique():
                if day not in daily_data:
                    daily_data[day] = {"Inseriti Mese": 0, "Chiusi Mese": 0}
                day_subset = subset[subset['Data Inserimento'].dt.date == day]
                daily_data[day]["Inseriti Mese"] += len(day_subset)
                daily_data[day]["Chiusi Mese"] += len(day_subset[day_subset['Stato'].isin(["CHIUSO", "IN LAVORAZIONE"])])

        # Calcola la riga totale
        total_inserted_today = sum(row["Inseriti Oggi"] for row in summary)
        total_closed_today = sum(row["Chiusi Oggi"] for row in summary)
        total_inserted_month = sum(row["Inseriti Mese"] for row in summary)
        total_closed_month = sum(row["Chiusi Mese"] for row in summary)
        total_target = sum(PRODUCTION_TARGETS.values())
        total_paf = round((total_closed_month / days_elapsed) * working_days) if days_elapsed > 0 else 0
        total_achievement = round((total_paf / total_target) * 100) if total_target > 0 else 0
        
        summary.append({
            "Sede": "TOTALE",
            "Inseriti Oggi": total_inserted_today,
            "Chiusi Oggi": total_closed_today,
            "Inseriti Mese": total_inserted_month,
            "Chiusi Mese": total_closed_month,
            "Obiettivo Assegnato": total_target,
            "PAF": total_paf,
            "% OBB.": total_achievement,
            "highlight": True  # Evidenzia la riga totale
        })
        
        return summary, daily_data

    production_summary, daily_data = compute_grouped_summary()

    # Creazione del grafico
    dates = sorted(daily_data.keys())
    inserted_data = [daily_data[date]["Inseriti Mese"] for date in dates]
    closed_data = [daily_data[date]["Chiusi Mese"] for date in dates]

    graph = go.Figure()
    graph.add_trace(go.Scatter(x=dates, y=inserted_data, mode='lines+markers', name='Inseriti Mese'))
    graph.add_trace(go.Scatter(x=dates, y=closed_data, mode='lines+markers', name='Chiusi Mese'))

    graph.update_layout(title="Andamento Giornaliero Produzione",
                        xaxis_title="Data",
                        yaxis_title="Numero di Contratti",
                        template="plotly_white")

    graph_json = graph.to_json()

    return render_template('produzione.html', production_summary=production_summary, graph_json=graph_json)

if __name__ == '__main__':
    app.run(debug=True)