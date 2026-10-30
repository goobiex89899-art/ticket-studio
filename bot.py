
import os
import json
import re
import html
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = "data/tickets.db"
TRANSCRIPT_DIR = Path("transcripts")

TRANSCRIPT_DIR.mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------- DATABASE ----------------

def connect_db():
    return sqlite3.connect(DB_PATH)


def setup_database():
    with connect_db() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            owner_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            claimed_by INTEGER,
            created_at TEXT NOT NULL
        )
        """)

        db.execute("""
        CREATE TABLE IF NOT EXISTS panels (
            message_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            config TEXT NOT NULL
        )
        """)


# ---------------- HELPERS ----------------

def clean_name(name):
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return name.strip("-")[:35] or "ticket"


def get_ticket(channel_id):
    with connect_db() as db:
        return db.execute(
            "SELECT owner_id, category, claimed_by FROM tickets WHERE channel_id=?",
            (channel_id,)
        ).fetchone()


# ---------------- TICKET FORM ----------------

class TicketModal(discord.ui.Modal):

    def __init__(self, category, config):
        super().__init__(title=category["label"][:45])

        self.category = category
        self.config = config
        self.fields = []

        questions = category.get("form", [])

        if not questions:
            questions = [{
                "label": "Describe your issue",
                "style": "paragraph",
                "required": True
            }]

        for question in questions[:5]:

            field = discord.ui.TextInput(
                label=question.get("label", "Details")[:45],
                style=(
                    discord.TextStyle.paragraph
                    if question.get("style") == "paragraph"
                    else discord.TextStyle.short
                ),
                required=question.get("required", True),
                max_length=1000
            )

            self.add_item(field)
            self.fields.append(field)

    async def on_submit(self, interaction):

        guild = interaction.guild

        if guild is None:
            return await interaction.response.send_message(
                "Use this inside a server.",
                ephemeral=True
            )

        with connect_db() as db:
            existing = db.execute(
                "SELECT channel_id FROM tickets WHERE guild_id=? AND owner_id=?",
                (guild.id, interaction.user.id)
            ).fetchone()

        if existing:
            channel = guild.get_channel(existing[0])

            if channel:
                return await interaction.response.send_message(
                    f"You already have a ticket: {channel.mention}",
                    ephemeral=True
                )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        bot_member = guild.me

        if bot_member:
            overwrites[bot_member] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True
            )

        staff_role_id = self.category.get("staff_role_id")

        if staff_role_id:
            role = guild.get_role(int(staff_role_id))

            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await guild.create_text_channel(
            name=f"ticket-{clean_name(interaction.user.name)}",
            overwrites=overwrites,
            topic=f"Ticket owner: {interaction.user.id}"
        )

        answers = []

        for field in self.fields:
            answers.append(
                f"**{discord.utils.escape_markdown(field.label)}**\n"
                f"{discord.utils.escape_mentions(field.value)}"
            )

        with connect_db() as db:
            db.execute("""
                INSERT INTO tickets
                (channel_id, guild_id, owner_id, category, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                channel.id,
                guild.id,
                interaction.user.id,
                self.category["label"],
                datetime.now(timezone.utc).isoformat()
            ))

        await channel.send(
            f"{interaction.user.mention}\n"
            f"## {self.category['label']}\n"
            f"Welcome! Staff will assist you shortly.\n\n"
            + "\n\n".join(answers),
            view=TicketControls()
        )

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


# ---------------- DROPDOWN ----------------

class TicketDropdown(discord.ui.Select):

    def __init__(self, config):

        self.config = config

        options = []

        for category in config["categories"][:25]:

            options.append(
                discord.SelectOption(
                    label=category["label"][:100],
                    value=category["value"][:100],
                    description=category.get("description", "")[:100] or None,
                    emoji=category.get("emoji") or None
                )
            )

        super().__init__(
            placeholder=config.get(
                "placeholder",
                "Select a ticket category..."
            ),
            options=options,
            custom_id="ticket_studio:category"
        )

    async def callback(self, interaction):

        category = next(
            (
                item for item in self.config["categories"]
                if item["value"] == self.values[0]
            ),
            None
        )

        if category is None:
            return await interaction.response.send_message(
                "This category no longer exists.",
                ephemeral=True
            )

        await interaction.response.send_modal(
            TicketModal(category, self.config)
        )


# ---------------- COMPONENTS V2 PANEL ----------------

class TicketPanel(discord.ui.LayoutView):

    def __init__(self, config):

        super().__init__(timeout=None)

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                f"# {config.get('title', 'Support Center')}\n"
                f"{config.get('description', 'Select a category below.')}"
            ),
            discord.ui.Separator(),
            discord.ui.ActionRow(
                TicketDropdown(config)
            ),
            accent_colour=discord.Colour.from_str(
                config.get("accent", "#6d5dfc")
            )
        )

        self.add_item(container)


# ---------------- TICKET CONTROLS ----------------

class TicketControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_studio:claim"
    )
    async def claim(self, interaction, button):

        ticket = get_ticket(interaction.channel_id)

        if not ticket:
            return await interaction.response.send_message(
                "This is not a ticket.",
                ephemeral=True
            )

        if ticket[2]:
            return await interaction.response.send_message(
                f"Already claimed by <@{ticket[2]}>.",
                ephemeral=True
            )

        with connect_db() as db:
            db.execute(
                "UPDATE tickets SET claimed_by=? WHERE channel_id=?",
                (interaction.user.id, interaction.channel_id)
            )

        await interaction.response.send_message(
            f"Ticket claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_studio:close"
    )
    async def close(self, interaction, button):

        ticket = get_ticket(interaction.channel_id)

        if not ticket:
            return await interaction.response.send_message(
                "This is not a ticket.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "Are you sure you want to close this ticket?",
            view=CloseConfirmation(),
            ephemeral=True
        )


class CloseConfirmation(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm close",
        style=discord.ButtonStyle.danger
    )
    async def confirm(self, interaction, button):

        channel = interaction.channel

        ticket = get_ticket(channel.id)

        if not ticket:
            return await interaction.response.send_message(
                "Ticket not found.",
                ephemeral=True
            )

        owner_id, category, claimed_by = ticket

        messages = [
            message async for message in
            channel.history(limit=500, oldest_first=True)
        ]

        transcript = [
            "<!DOCTYPE html><html><head><meta charset='UTF-8'>",
            "<title>Ticket Transcript</title></head><body>",
            f"<h1>{html.escape(category)}</h1>"
        ]

        for message in messages:

            content = html.escape(message.content or "[Attachment/embed]")

            transcript.append(
                f"<p><b>{html.escape(str(message.author))}</b>"
                f"<br>{content}</p>"
            )

        transcript.append("</body></html>")

        filename = TRANSCRIPT_DIR / f"ticket-{channel.id}.html"

        filename.write_text(
            "\n".join(transcript),
            encoding="utf-8"
        )

        with connect_db() as db:
            db.execute(
                "DELETE FROM tickets WHERE channel_id=?",
                (channel.id,)
            )

        await interaction.response.send_message(
            "Ticket closed. Transcript saved on the bot host."
        )

        await channel.delete(
            reason=f"Ticket closed by {interaction.user}"
        )


# ---------------- PUBLISH PANEL COMMAND ----------------

@bot.tree.command(
    name="publish-panel",
    description="Publish a Ticket Studio panel."
)
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(
    channel="Channel where the panel will be published",
    config_file="JSON file exported from Ticket Studio"
)
async def publish_panel(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    config_file: discord.Attachment
):

    if not config_file.filename.endswith(".json"):
        return await interaction.response.send_message(
            "Upload a JSON panel configuration.",
            ephemeral=True
        )

    if config_file.size > 100_000:
        return await interaction.response.send_message(
            "Configuration file is too large.",
            ephemeral=True
        )

    try:
        config = json.loads(
            (await config_file.read()).decode("utf-8")
        )

        if not 1 <= len(config["categories"]) <= 25:
            raise ValueError("Use 1–25 categories.")

        for category in config["categories"]:
            if not category.get("label") or not category.get("value"):
                raise ValueError("Every category needs a label and value.")

            if len(category.get("form", [])) > 5:
                raise ValueError("Maximum 5 form questions per category.")

    except Exception as error:
        return await interaction.response.send_message(
            f"Invalid configuration: {error}",
            ephemeral=True
        )

    message = await channel.send(
        view=TicketPanel(config)
    )

    with connect_db() as db:
        db.execute("""
            INSERT OR REPLACE INTO panels
            (message_id, channel_id, guild_id, config)
            VALUES (?, ?, ?, ?)
        """, (
            message.id,
            channel.id,
            interaction.guild_id,
            json.dumps(config)
        ))

    await interaction.response.send_message(
        f"Panel published in {channel.mention}!",
        ephemeral=True
    )


# ---------------- STARTUP ----------------

@bot.event
async def on_ready():

    setup_database()

    bot.add_view(TicketControls())

    # Restore published panels after restart.
    with connect_db() as db:
        panels = db.execute(
            "SELECT config FROM panels"
        ).fetchall()

    for (config_json,) in panels:
        try:
            bot.add_view(
                TicketPanel(json.loads(config_json))
            )
        except Exception as error:
            print("Panel restoration failed:", error)

    if not getattr(bot, "commands_synced", False):
        await bot.tree.sync()
        bot.commands_synced = True

    print(f"Logged in as {bot.user}")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

bot.run(TOKEN)
