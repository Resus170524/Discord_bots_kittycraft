
import discord
from discord.ext import commands
from discord.ui import Button, View

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Définition des crafts
crafts = {
    "etoffe": {"name": "📜 Étoffe lunaire", "question": "Combien de couturiers souhaites-tu mettre à disposition de la guilde ?"},
    "peau": {"name": "🐾 Peau robuste traitée", "question": "Combien de travailleurs du cuir souhaites-tu mettre à disposition de la guilde ?"},
    "arcanite": {"name": "⚒️ Barre d’arcanite", "question": "Combien d’alchimistes souhaites-tu mettre à disposition de la guilde ?"}
}

# File d’attente + état des crafteurs
queues = {c: [] for c in crafts}
crafteurs = {c: {} for c in crafts}  
# {craft: {crafter_id: {"slots": 2, "current": [joueur1, joueur2]}}}

# Messages principaux (un par craft)
main_messages = {}


# Générer un embed par craft
def generate_embed(craft: str):
    embed = discord.Embed(title=f"🛠️ {crafts[craft]['name']}", color=0x2ecc71)

    # File d’attente
    if queues[craft]:
        attente = "\n".join([f"{i+1}. {m.mention}" for i, m in enumerate(queues[craft])])
    else:
        attente = "— Vide —"

    # Crafteurs
    if crafteurs[craft]:
        crafter_list = []
        for cid, data in crafteurs[craft].items():
            user_str = f"<@{cid}> ({data['slots']} CD)"
            if data["current"]:
                clients = ", ".join([m.mention for m in data["current"]])
                user_str += f" → {clients}"
            else:
                user_str += " → ⚡ Libre"
            crafter_list.append(user_str)
        crafter_text = "\n".join(crafter_list)
    else:
        crafter_text = "Aucun"

    embed.add_field(name="⏳ File d’attente", value=attente, inline=True)
    embed.add_field(name="🧑‍🏭 Crafteurs", value=crafter_text, inline=True)

    return embed


# Attribution automatique selon slots dispo
async def assign_players(craft: str):
    while queues[craft]:
        assigned = False
        for cid, data in crafteurs[craft].items():
            if len(data["current"]) < data["slots"]:  # encore de la place
                joueur = queues[craft].pop(0)
                data["current"].append(joueur)
                member = await bot.fetch_user(cid)
                await joueur.send(f"🎉 C’est ton tour pour **{crafts[craft]['name']}** avec {member.mention} !")
                assigned = True
                break
        if not assigned:
            break
    await update_message(craft)


# Vue pour choisir combien de slots le crafteur met à dispo
class SlotChoiceView(View):
    def __init__(self, craft: str, user: discord.User):
        super().__init__(timeout=30)
        self.craft = craft
        self.user = user

    async def assign_slots(self, interaction: discord.Interaction, slots: int):
        if self.user.id in crafteurs[self.craft]:
            await interaction.response.send_message("❌ Tu es déjà enregistré comme crafteur.", ephemeral=True)
            return

        crafteurs[self.craft][self.user.id] = {"slots": slots, "current": []}
        await assign_players(self.craft)
        await interaction.response.send_message(f"✅ Tu es maintenant crafteur pour **{crafts[self.craft]['name']}** avec **{slots} CD**.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="1 CD", style=discord.ButtonStyle.green)
    async def one_cd(self, interaction: discord.Interaction, button: Button):
        await self.assign_slots(interaction, 1)

    @discord.ui.button(label="2 CD", style=discord.ButtonStyle.green)
    async def two_cd(self, interaction: discord.Interaction, button: Button):
        await self.assign_slots(interaction, 2)

    @discord.ui.button(label="3 CD", style=discord.ButtonStyle.green)
    async def three_cd(self, interaction: discord.Interaction, button: Button):
        await self.assign_slots(interaction, 3)


# Vue principale par craft
class CraftView(View):
    def __init__(self, craft: str):
        super().__init__(timeout=None)
        self.craft = craft

    @discord.ui.button(label="➕ Rejoindre la file", style=discord.ButtonStyle.blurple)
    async def join_queue(self, interaction: discord.Interaction, button: Button):
        if interaction.user in queues[self.craft]:
            await interaction.response.send_message("⏳ Tu es déjà dans la file.", ephemeral=True)
            return
        queues[self.craft].append(interaction.user)
        await assign_players(self.craft)
        await interaction.response.send_message(f"✅ Tu as rejoint la file pour **{crafts[self.craft]['name']}**", ephemeral=True)

    @discord.ui.button(label="❌ Quitter la file", style=discord.ButtonStyle.gray)
    async def leave_queue(self, interaction: discord.Interaction, button: Button):
        if interaction.user not in queues[self.craft]:
            await interaction.response.send_message("❌ Tu n’es pas dans la file.", ephemeral=True)
            return
        queues[self.craft].remove(interaction.user)
        await update_message(self.craft)
        await interaction.response.send_message(f"🚪 Tu as quitté la file d’attente pour **{crafts[self.craft]['name']}**", ephemeral=True)

    @discord.ui.button(label="✅ Je suis crafteur", style=discord.ButtonStyle.green)
    async def add_crafter(self, interaction: discord.Interaction, button: Button):
        view = SlotChoiceView(self.craft, interaction.user)
        await interaction.response.send_message(crafts[self.craft]["question"], view=view, ephemeral=True)

    @discord.ui.button(label="🚪 Quitter crafteur", style=discord.ButtonStyle.danger)
    async def remove_crafter(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in crafteurs[self.craft]:
            await interaction.response.send_message("❌ Tu n’es pas crafteur ici.", ephemeral=True)
            return

        # remettre les joueurs en cours en tête de file
        data = crafteurs[self.craft].pop(interaction.user.id)
        for joueur in reversed(data["current"]):
            queues[self.craft].insert(0, joueur)

        await assign_players(self.craft)
        await interaction.response.send_message(f"🚪 Tu n’es plus crafteur pour **{crafts[self.craft]['name']}**", ephemeral=True)

    @discord.ui.button(label="🏁 Craft terminé", style=discord.ButtonStyle.red)
    async def craft_done(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id not in crafteurs[self.craft]:
            await interaction.response.send_message("❌ Tu n’es pas crafteur ici.", ephemeral=True)
            return

        data = crafteurs[self.craft][interaction.user.id]
        if not data["current"]:
            await interaction.response.send_message("❌ Tu n’as aucun joueur en cours.", ephemeral=True)
            return

        # Libérer le premier joueur de sa liste
        fini = data["current"].pop(0)
        await fini.send(f"✅ Ton craft avec {interaction.user.mention} est terminé !")

        # Assigner un nouveau joueur s'il y a de la place
        await assign_players(self.craft)
        await interaction.response.send_message(f"🏁 Tu as terminé avec {fini.mention}.", ephemeral=True)


# Mise à jour du tableau
async def update_message(craft: str):
    if craft in main_messages and main_messages[craft]:
        await main_messages[craft].edit(embed=generate_embed(craft), view=CraftView(craft))


# Commande admin pour démarrer les 3 tableaux
@bot.command()
async def start(ctx):
    for craft in crafts:
        embed = generate_embed(craft)
        view = CraftView(craft)
        msg = await ctx.send(embed=embed, view=view)
        main_messages[craft] = msg

bot.run("MTQxMDkzNTk0MTMxNjQ3NzAxMQ.GvsODr.qoZUEYK4iIEHnsRYdL6sROvbBCBjQj9AWhPcMw")
