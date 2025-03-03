import discord
from discord.ext import commands, tasks
import requests
import json
import os
from dotenv import load_dotenv
from discord.ui import Button, View

# Charger le token depuis .env
load_dotenv()
TOKEN = os.getenv('TOKEN')

# Configuration du bot avec le préfixe "!"
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Charger les alertes depuis le fichier JSON
def load_alerts():
    try:
        with open('alerts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Sauvegarder les alertes dans le fichier JSON
def save_alerts(alerts):
    with open('alerts.json', 'w') as f:
        json.dump(alerts, f, indent=4)

# Fonction pour récupérer le prix depuis l'API Binance
def get_crypto_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
    response = requests.get(url)
    data = response.json()
    return float(data['price'])

# Ajouter une alerte
@bot.command()
async def set_alert(ctx, symbol: str, threshold: float, action: str):
    alerts = load_alerts()
    symbol = symbol.upper()
    if symbol not in alerts:
        alerts[symbol] = []

    alerts[symbol].append({
        "user_id": ctx.author.id,
        "threshold": threshold,
        "action": action
    })
    save_alerts(alerts)
    await ctx.send(f"✅ Alerte enregistrée pour {symbol} à {threshold} USD pour {ctx.author.mention}!")

# Commande pour afficher les alertes avec un bouton de suppression pour chaque alerte
@bot.command()
async def show_alerts(ctx):
    alerts = load_alerts()
    user_alerts = []

    for symbol, alert_list in alerts.items():
        for alert in alert_list:
            if alert['user_id'] == ctx.author.id:
                user_alerts.append(f"{symbol}: {alert['threshold']} USD - Action: {alert['action']}")

    if user_alerts:
        view = View()

        # Ajouter un bouton de suppression pour chaque alerte
        for alert in user_alerts:
            symbol, threshold, action = alert.split(": ")
            threshold = float(threshold.split(" ")[0])

            # Fonction callback pour supprimer une alerte
            async def remove_alert_callback(interaction, symbol=symbol, threshold=threshold, action=action):
                alerts = load_alerts()
                for symbol, alert_list in alerts.items():
                    alerts[symbol] = [alert for alert in alert_list if not (alert['user_id'] == ctx.author.id and alert['threshold'] == threshold and alert['action'] == action)]
                save_alerts(alerts)
                await interaction.response.send_message(f"✅ L'alerte {symbol} à {threshold} USD ({action}) a été supprimée.")

            # Créer un bouton pour chaque alerte
            button = Button(label=f"Supprimer {alert}", style=discord.ButtonStyle.red)
            button.callback = remove_alert_callback
            view.add_item(button)

        # Ajouter le bouton "Ne rien supprimer"
        async def cancel_callback(interaction):
            # Désactiver tous les autres boutons après avoir cliqué sur "Ne rien supprimer"
            for item in view.children:
                item.disabled = True  # Désactive tous les boutons
            await interaction.response.send_message("❌ Aucune alerte supprimée.", ephemeral=True)
            await interaction.message.edit(view=view)  # Mettre à jour le message avec les boutons désactivés

        cancel_button = Button(label="Ne rien supprimer", style=discord.ButtonStyle.green)
        cancel_button.callback = cancel_callback
        view.add_item(cancel_button)

        # Afficher les boutons
        await ctx.send(f"🔔 Vos alertes actives :\n" + "\n".join(user_alerts), view=view)
    else:
        await ctx.send("❌ Vous n'avez pas d'alertes actives.")

# Vérifier les alertes toutes les 15 minutes
@tasks.loop(minutes=0.1)
async def check_alerts():
    alerts = load_alerts()
    for symbol, alert_list in alerts.items():
        try:
            price = get_crypto_price(symbol)
            for alert in alert_list:
                user = await bot.fetch_user(alert["user_id"])
                if (alert["action"] == "sell" and price >= alert["threshold"]) or \
                   (alert["action"] == "buy" and price <= alert["threshold"]):
                    # Mentionner l'utilisateur dans le message
                    await user.send(f"🚨 {user.mention} - Prix actuel du {symbol}: {price} USD \n Action à réaliser: {'Vente' if alert['action'] == 'sell' else 'Achat'}")
                    # Supprimer l'alerte après envoi
                    alert_list.remove(alert)
            # Mettre à jour les alertes
            alerts[symbol] = alert_list
        except Exception as e:
            print(f"Erreur lors de la vérification des alertes pour {symbol}: {e}")
    save_alerts(alerts)

# Commande pour tester le bot
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Démarrer la vérification des alertes
@bot.event
async def on_ready():
    print(f'✅ Connecté en tant que {bot.user}!')
    check_alerts.start()

bot.run(TOKEN)


