import requests
import time
import json
import os
from random import randint

try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
except ModuleNotFoundError:
    input("There is no necessary library. Complete the command line command: PIP Install Pytelegrambotapi")
    exit() # Exit if telebot is not found, as the bot cannot function without it

# --- Configuration ---
# Your bot and API tokens
url = "https://leakosintapi.com/"
bot_token = os.getenv("BOT_TOKEN")
api_token = os.getenv("API_TOKEN")
lang = "en"
limit = 300

# Admin User ID (Your Telegram User ID for admin panel access) - PLEASE VERIFY THIS IS YOUR CORRECT NUMERIC ID
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Username for the "Buy Credits" button (can be a different bot or user)
ADMIN_BOT_USERNAME_FOR_CREDITS = os.getenv("ADMIN_BOT_USERNAME_FOR_CREDITS", "") # Set this to the exact username without the '@'

# Group Configuration for mandatory join
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "") # The username of your group (e.g., my_awesome_group)
# IMPORTANT: Replace GROUP_ID with the actual numerical ID of your Telegram group.
# To get the group ID: Add your bot to the group, make it an admin,
# then forward any message from the group to @userinfobot or @getidsbot.
# You need the numerical ID (e.g., -1001234567890).
GROUP_ID = int(os.getenv("GROUP_ID", "0")) # <<<--- YOUR ACTUAL GROUP CHAT ID HAS BEEN ADDED HERE!

INITIAL_FREE_CREDITS = 4  # Number of free credits for new users
REFERRALS_FOR_CREDIT = 5  # Number of referrals needed for 1 credit reward

# --- JSON File Paths for Persistent Data ---
# We will store user data, blacklisted users, and additional admin IDs in JSON files.
# It's good practice to keep them in a dedicated directory.
DATA_DIR = "bot_data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
BLACKLIST_FILE = os.path.join(DATA_DIR, "blacklist.json")
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json") # New file for additional admins

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# --- Global Data Stores (in-memory) ---
# These dictionaries/lists will hold your data in memory and will be loaded from/saved to JSON files.
users_data = {}
blacklisted_users = {}
additional_admins = [] # New list to store additional admin user IDs
cash_reports = {} # Still for temporary reports (not persistent across bot restarts)

# --- JSON File Helper Functions ---
def load_data(file_path):
    """Loads data from a JSON file."""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Error decoding JSON from {file_path}. Returning empty.")
                # Return appropriate empty type based on expected content
                return {} if "users" in file_path or "blacklist" in file_path else []
    # Return appropriate empty type if file doesn't exist
    return {} if "users" in file_path or "blacklist" in file_path else []


def save_data(data, file_path):
    """Saves data to a JSON file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Initial Data Loading ---
# Load existing data when the bot starts
users_data = load_data(USERS_FILE)
blacklisted_users = load_data(BLACKLIST_FILE)
additional_admins = load_data(ADMINS_FILE) # Load additional admin IDs
print(f"Loaded {len(users_data)} users, {len(blacklisted_users)} blacklisted users, and {len(additional_admins)} additional admins from JSON files.")

# --- Data Management Functions (using JSON files) ---
def get_user_data(user_id):
    """Fetches user data from in-memory dictionary."""
    return users_data.get(str(user_id))

def set_user_data(user_id, data):
    """Sets or updates user data in in-memory dictionary and saves to file."""
    users_data[str(user_id)] = data
    save_data(users_data, USERS_FILE)

def is_user_blacklisted(user_id):
    """Checks if a user is blacklisted from in-memory dictionary."""
    return str(user_id) in blacklisted_users

def blacklist_user(user_id):
    """Blacklists a user by adding to in-memory dictionary and saving to file."""
    blacklisted_users[str(user_id)] = True # Store a simple indicator
    save_data(blacklisted_users, BLACKLIST_FILE)

def unblacklist_user(user_id):
    """Unblacklists a user by removing from in-memory dictionary and saving to file."""
    if str(user_id) in blacklisted_users:
        del blacklisted_users[str(user_id)]
        save_data(blacklisted_users, BLACKLIST_FILE)

def add_admin(user_id):
    """Adds a user to the additional_admins list and saves."""
    if user_id not in additional_admins:
        additional_admins.append(user_id)
        save_data(additional_admins, ADMINS_FILE)
        return True
    return False

def remove_admin(user_id):
    """Removes a user from the additional_admins list and saves."""
    if user_id in additional_admins:
        additional_admins.remove(user_id)
        save_data(additional_admins, ADMINS_FILE)
        return True
    return False

def is_admin_user(user_id):
    """Checks if a user is the primary admin or an added admin."""
    return user_id == ADMIN_USER_ID or user_id in additional_admins

# --- Bot Initialization ---
bot = telebot.TeleBot(bot_token)

# Determine the bot's actual username for referral links
try:
    BOT_USERNAME = bot.get_me().username
except telebot.apihelper.ApiTelegramException as e:
    print(f"Error getting bot username: {e}. Please ensure your bot token is correct and bot is enabled.")
    BOT_USERNAME = "your_bot_username_placeholder" # Fallback in case of error

# --- Core Bot Logic Functions ---
def check_group_membership(user_id, chat_id, bot_instance):
    """Checks if a user is a member of the specified Telegram group."""
    if not chat_id: # If GROUP_ID is not configured
        return True # Assume user can access if group check is not set up

    try:
        chat_member = bot_instance.get_chat_member(chat_id, user_id)
        # Status can be 'creator', 'administrator', 'member', 'restricted', 'left', 'kicked'
        # We allow 'creator', 'administrator', 'member', 'restricted' (if restricted can still receive messages)
        if chat_member.status in ['creator', 'administrator', 'member', 'restricted']:
            return True
        else:
            return False
    except telebot.apihelper.ApiTelegramException as e:
        # Common errors: 'User not found' (user left or blocked bot), 'Bad Request: chat not found' (GROUP_ID is wrong)
        print(f"Error checking group membership for user {user_id} in chat {chat_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in group membership check: {e}")
        return False

def generate_report(query, query_id):
    """Function to generate reports from the API."""
    global url, api_token, limit, lang
    data = {"token": api_token, "request": query.split("\n")[0], "limit": limit, "lang": lang}
    try:
        response = requests.post(url, json=data).json()
        if "Error code" in response:
            print("Error:" + response["Error code"])
            return None

        # Check for "No results found" explicitly
        if "List" in response and "No results found" in response["List"]:
            return ["No results found"] # Indicate no results

        report_content = []
        for database_name in response["List"].keys():
            text = [f"<b>{database_name}</b>", ""]
            text.append(response["List"][database_name]["InfoLeak"] + "\n")
            if database_name != "No results found": # This condition is now redundant due to the check above
                for report_data in response["List"][database_name]["Data"]:
                    for column_name in report_data.keys():
                        text.append(f"<b>{column_name}</b>:  {report_data[column_name]}")
                    text.append("")
            text = "\n".join(text)

            # Strip <b> tags here before storing, as they won't be rendered in <pre><code> anyway.
            # This prevents them from appearing as literal <b>/</b> in the output.
            text = text.replace("<b>", "").replace("</b>", "")

            if len(text) > 3500:
                text = text[:3500] + "\n\n...Some data did not fit this message"
            report_content.append(text)

        # Store report content temporarily (still in-memory for quick access)
        # This will be cleared on bot restart. For persistent reports, use Firestore.
        global cash_reports
        cash_reports[str(query_id)] = report_content
        return report_content
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in generate_report: {e}")
        return None

def create_inline_keyboard(query_id, page_id, count_page):
    """Function for creating an inline keyboard for pagination."""
    markup = InlineKeyboardMarkup()
    if page_id < 0:
        page_id = count_page - 1
    elif page_id >= count_page:
        page_id = 0

    if count_page == 1:
        return markup
    markup.row_width = 3
    markup.add(InlineKeyboardButton(text="<<", callback_data=f"/page {query_id} {page_id - 1}"),
               InlineKeyboardButton(text=f"{page_id + 1}/{count_page}", callback_data="page_list_noop"),
               InlineKeyboardButton(text=">>", callback_data=f"/page {query_id} {page_id + 1}"))
    return markup

def create_main_menu_keyboard(is_admin_check=False):
    """Function to create the main menu with dynamic buttons."""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    # Row 1
    markup.add(KeyboardButton("Check My Credits"), KeyboardButton("Buy Credit"))
    # Row 2
    markup.add(KeyboardButton("Referral System"), KeyboardButton("Contact Admin"))
    # Row 3 (Main Menu - to reset the keyboard and go back to the welcome message)
    markup.add(KeyboardButton("Main Menu"))
    if is_admin_check:
        markup.add(KeyboardButton("Admin Panel")) # Add admin button for admins
    return markup


# --- New Function: Inline keyboard for welcome message to trigger pricing ---
def create_welcome_inline_keyboard():
    """Creates the inline keyboard for the welcome message, with a button to show pricing."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="💰 Buy Access / Credits", callback_data="show_pricing"))
    return markup

# --- New Function: Inline keyboard for pricing message to contact admin ---
def create_pricing_message_keyboard():
    """Creates the inline keyboard for the pricing message, with a CONTACT ADMIN button."""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="CONTACT ADMIN", url=f"https://t.me/{ADMIN_BOT_USERNAME_FOR_CREDITS}"))
    return markup

def create_admin_panel_inline_keyboard():
    """Function to create the admin panel inline keyboard."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="📊 View All Users", callback_data="admin_view_users"),
        InlineKeyboardButton(text="➕➖ Manage Credits", callback_data="admin_manage_credits"),
        InlineKeyboardButton(text="🚫 Blacklist User", callback_data="admin_blacklist"),
        InlineKeyboardButton(text="✅ Unblacklist User", callback_data="admin_unblacklist"),
        InlineKeyboardButton(text="➕ Add Admin", callback_data="admin_add_admin") # New button
    )
    return markup

# --- Middleware for Access Control ---
def check_user_access(message):
    """Checks if a user is allowed to use the bot based on group membership and blacklist status."""
    user_id = message.from_user.id
    # IMPORTANT: message.chat.id here refers to the private chat with the bot.
    # We need to check against the actual GROUP_ID.

    # 1. Check if blacklisted
    if is_user_blacklisted(user_id):
        bot.send_message(message.chat.id, "🚫 You are blacklisted and cannot use this bot.")
        return False

    # 2. Check group membership (only if GROUP_ID is set and not the placeholder)
    if GROUP_ID and GROUP_ID != -1001234567890:
        # Corrected: Pass GROUP_ID for the group membership check
        if not check_group_membership(user_id, GROUP_ID, bot):
            join_markup = InlineKeyboardMarkup()
            join_markup.add(InlineKeyboardButton(text="🚀 Join Our Group", url=f"https://t.me/{GROUP_USERNAME}"))
            # Add the new "VERIFY" button below "Join Our Group"
            join_markup.add(InlineKeyboardButton(text="✅ VERIFY", callback_data="verify_group_membership"))

            bot.send_message(
                message.chat.id,
                f"🚨 To use this bot, you must join our official Telegram group: @{GROUP_USERNAME}\n"
                "Please join the group and click VERIFY", # Updated text as requested
                reply_markup=join_markup
            )
            return False
        else:
            pass # User is a member, continue processing
    elif GROUP_ID == -1001234567890:
        # Notify admin if GROUP_ID is not configured but group username is set
        if is_admin_user(user_id): # Check if the sender is an_admin
            bot.send_message(message.chat.id, "⚠️ Warning: GROUP_ID is not configured. Group membership check is disabled. Please set the correct GROUP_ID.")

    return True

# --- Message Handlers ---
@bot.message_handler(commands=["start"])
def send_welcome(message):
    """
    Handles the /start command.
    Initializes user data, checks for referrals, and sends welcome message.
    """
    print(f"DEBUG: send_welcome called for user {message.from_user.id} with text: {message.text} from chat type: {message.chat.type}")
    user_id = message.from_user.id

    # If the user is accessing via /start, ensure they meet group criteria
    # This check is crucial for direct /start commands.
    if not check_user_access(message):
        return

    referrer_id = None

    # Check for referral link payload
    if message.text and len(message.text.split()) > 1:
        payload = message.text.split()[1]
        if payload.startswith("ref_"):
            referrer_id = int(payload.split("ref_")[1]) # Convert referrer_id to int for consistent comparison

    user_data = get_user_data(user_id)
    if user_data is None: # New user
        user_data = {
            "credits": INITIAL_FREE_CREDITS,
            "referral_count": 0,
            "referred_by": referrer_id # Store referrer if exists
        }
        set_user_data(user_id, user_data)

        if referrer_id and referrer_id != user_id: # Ensure user doesn't refer themselves
            try:
                referrer_data = get_user_data(referrer_id)
                if referrer_data:
                    referrer_data["referral_count"] = referrer_data.get("referral_count", 0) + 1
                    set_user_data(referrer_id, referrer_data) # Save updated referrer data
                    bot.send_message(referrer_id, f"🎉 One of your referrals ({message.from_user.first_name}) just started the bot! You now have *{referrer_data['referral_count']}* referrals.", parse_mode="Markdown")

                    # Check for credit reward based on REFERRALS_FOR_CREDIT
                    if referrer_data["referral_count"] % REFERRALS_FOR_CREDIT == 0:
                        referrer_data["credits"] = referrer_data.get("credits", 0) + 1
                        set_user_data(referrer_id, referrer_data) # Save updated referrer data
                        bot.send_message(referrer_id, f"💰 Congratulations! You've reached *{REFERRALS_FOR_CREDIT}* referrals and received *1* credit. Your new balance is *{referrer_data['credits']}*.", parse_mode="Markdown")
                else:
                    print(f"Referrer {referrer_id} not found in database (JSON file).")
            except Exception as e:
                print(f"Error handling referrer {referrer_id}: {e}")

    # Ensure admin gets admin menu
    is_admin_check = is_admin_user(user_id) # Use the unified admin check

    # Fetch current user data for the welcome message
    current_user_data = get_user_data(user_id)
    current_credits = current_user_data.get('credits', INITIAL_FREE_CREDITS)
    current_referrals = current_user_data.get('referral_count', 0)

    # First part: In quote and mono format
    intro_text_quoted_mono = (
        f"<blockquote><pre><code>"
        f"👋 Hello, {message.from_user.first_name or 'there'}!\n"
        "🔎 Before you, the best search engine according to open data.\n"
        "Here is a list of what you can look for:\n"
        "┣📧 Email\n"
        "┣📞 Phones\n"
        "┣👤 Names\n"
        "┣👥 Nicknames\n"
        "┣📍 IP\n"
        "┣🔒 Passwords\n"
        "┣🌐 Domains\n"
        "┣🏢 Company\n"
        "┣🚗 Autonomer\n"
        "┣📇 VIN\n"
        "┣💸 Inn\n"
        "┣🪪 Snils\n"
        "┣✈ Telegram id\n"
        "┣📘 VK ID\n"
        "┣📖 Facebook ID\n"
        "┗🛂 Passports\n"
        "And many other data\n\n"
        "⚠️ Especially sensitive information (bank cards and passwords that can still be relevant) is partially hidden. The use of a bot with any evil intent is strictly prohibited.\n"
        "🔞 The data of people under the age of 18 are also hidden.\n\n"
        "💎 For the full use of the bot, it is necessary to have a subscription.\n\n"
        "🆓 That you could try all the functionality of the bot, we give you full access for 1 week just like that!"
        f"</code></pre></blockquote>"
    )

    # Second part: Bold and attractive, including search examples
    stats_referral_and_search_text = (
        f"**📊 YOUR CREDIT** 💰 = `{current_credits}`\n\n"
        f"**👥 TOTAL REFERRALS** 📈 = `{current_referrals}`\n\n"
        f"**🔗 YOUR REFERRAL LINK** 👇 = `https://t.me/{BOT_USERNAME}?start=ref_{user_id}`\n\n"
        "**(_NB: 5 REFERRALS = 1 CREDIT_)**\n\n"
        "**START SEARCH🔍**\n"
        "**EG-**\n"
        "**- +91XXXXXXXX**\n"
        "**- example@gmail.com**\n"
        "**- Name1234**"
    )

    # Send the first part
    bot.send_message(
        message.chat.id,
        intro_text_quoted_mono,
        parse_mode="html" # Use html parse mode for blockquote/pre/code
    )

    # Send the second part with bold formatting and search examples
    bot.send_message(
        message.chat.id,
        stats_referral_and_search_text,
        parse_mode="Markdown" # Use Markdown for bolding
    )

    # Send the main menu keyboard
    bot.send_message(
        message.chat.id,
        "What would you like to do next?",
        reply_markup=create_main_menu_keyboard(is_admin_check)
    )
    # Send the inline keyboard for buying credits as a separate message
    bot.send_message(
        message.chat.id,
        "Ready to get more access?", # Generic message to prompt the inline button click
        reply_markup=create_welcome_inline_keyboard()
    )


@bot.message_handler(commands=["credits"])
@bot.message_handler(func=lambda message: message.text == "Check My Credits")
def check_credits(message):
    """Handles the 'Check My Credits' menu button or /credits command."""
    if not check_user_access(message):
        return

    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    credits = user_data.get("credits", 0) if user_data else 0
    referrals = user_data.get("referral_count", 0) if user_data else 0

    bot.send_message(
        message.chat.id,
        f"You currently have *{credits}* credits left. 💡\n"
        f"You have *{referrals}* successful referrals.",
        parse_mode="Markdown",
        reply_markup=create_pricing_message_keyboard() # Offer to buy credits directly here
    )

@bot.message_handler(commands=["admin"])
@bot.message_handler(func=lambda message: message.text == "Admin Panel")
def admin_panel(message):
    """Displays the admin panel for the admin user."""
    user_id = message.from_user.id
    if not is_admin_user(user_id): # Use unified admin check
        bot.send_message(message.chat.id, "You are not authorized to access the admin panel.")
        return

    bot.send_message(
        message.chat.id,
        "Welcome to the Admin Panel! Please select an option:",
        reply_markup=create_admin_panel_inline_keyboard()
    )

# --- New Handlers for New Keyboard Buttons ---
@bot.message_handler(func=lambda message: message.text == "Buy Credit")
def handle_buy_credit(message):
    """Handles the 'Buy Credit' button."""
    if not check_user_access(message):
        return

    pricing_text = (
        "💰 *Access Pricing:*\n\n"
        "**1 WEEK ACCESS** = `300₹` / `150 🌟`\n"
        "**1 MONTH ACCESS** = `600₹` / `300🌟`\n"
        "**3 MONTH ACCESS** = `1000₹` / `500🌟`\n"
        "**LIFETIME ACCESS (API)** = `3000₹`\n\n"
        "Contact Admin for purchase:"
    )
    bot.send_message(
        message.chat.id,
        pricing_text,
        parse_mode="Markdown",
        reply_markup=create_pricing_message_keyboard() # Re-use the pricing keyboard with contact admin button
    )

@bot.message_handler(func=lambda message: message.text == "Contact Admin")
def handle_contact_admin(message):
    """Handles the 'Contact Admin' button."""
    if not check_user_access(message):
        return

    contact_text = (
        "Need help or have a question?\n"
        f"Please contact our admin directly via Telegram: @{ADMIN_BOT_USERNAME_FOR_CREDITS}\n\n"
        "We'll get back to you as soon as possible!"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(text="Go to Admin Chat", url=f"https://t.me/{ADMIN_BOT_USERNAME_FOR_CREDITS}"))
    bot.send_message(
        message.chat.id,
        contact_text,
        parse_mode="HTML", # Changed from "Markdown" to "HTML"
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "Referral System")
def handle_referral_system(message):
    """Handles the 'Referral System' button."""
    if not check_user_access(message):
        return

    user_id = message.from_user.id
    user_data = get_user_data(user_id)
    current_referrals = user_data.get('referral_count', 0)

    referral_text = (
        "**🤝 Referral System**\n\n"
        "Invite your friends and earn credits!\n"
        f"**🔗 YOUR REFERRAL LINK** 👇 = `https://t.me/{BOT_USERNAME}?start=ref_{user_id}`\n\n"
        f"**👥 TOTAL REFERRALS** 📈 = `{current_referrals}`\n\n"
        f"**(_NB: Every {REFERRALS_FOR_CREDIT} REFERRALS = 1 CREDIT_)**\n\n"
        "Share your link and when a new user starts the bot using it, "
        f"your referral count will increase. Once you hit {REFERRALS_FOR_CREDIT} referrals, "
        "you'll automatically receive 1 credit!"
    )
    bot.send_message(
        message.chat.id,
        referral_text,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: message.text == "Main Menu")
def handle_main_menu(message):
    """Handles the 'Main Menu' button, essentially restarting the welcome message."""
    send_welcome(message)

@bot.message_handler(func=lambda message: message.content_type == "text" and message.text.startswith("/set_credits"))
def admin_set_credits(message):
    """Admin command to set a user's credits."""
    user_id = message.from_user.id
    if not is_admin_user(user_id): # Use unified admin check
        bot.send_message(message.chat.id, "You are not authorized to use this command.")
        return

    try:
        parts = message.text.split()
        if len(parts) == 3:
            target_user_id = int(parts[1])
            amount = int(parts[2])

            target_user_data = get_user_data(target_user_id)
            if target_user_data:
                target_user_data["credits"] = amount
                set_user_data(target_user_id, target_user_data) # Save to JSON
                bot.send_message(message.chat.id, f"Credits for user {target_user_id} set to {amount}.")
                # Notify the target user if possible
                try:
                    bot.send_message(target_user_id, f"Your credits have been updated to {amount} by the admin.")
                except telebot.apihelper.ApiTelegramException:
                    pass # User might have blocked the bot
            else:
                bot.send_message(message.chat.id, f"User {target_user_id} not found in database.")
        else:
            bot.send_message(message.chat.id, "Usage: `/set_credits <user_id> <amount>`")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid user ID or amount. Usage: `/set_credits <user_id> <amount>`")
    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")

@bot.message_handler(func=lambda message: message.content_type == "text" and message.text.startswith("/blacklist"))
def admin_blacklist_cmd(message):
    """Admin command to blacklist a user."""
    user_id = message.from_user.id
    if not is_admin_user(user_id): # Use unified admin check
        bot.send_message(message.chat.id, "You are not authorized to use this command.")
        return

    try:
        parts = message.text.split()
        if len(parts) == 2:
            target_user_id = int(parts[1])
            blacklist_user(target_user_id) # Save to JSON
            bot.send_message(message.chat.id, f"User {target_user_id} has been blacklisted.")
            try:
                bot.send_message(target_user_id, "You have been blacklisted and can no longer use this bot.")
            except telebot.apihelper.ApiTelegramException:
                pass
        else:
            bot.send_message(message.chat.id, "Usage: `/blacklist <user_id>`")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid user ID. Usage: `/blacklist <user_id>`")
    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")

@bot.message_handler(func=lambda message: message.content_type == "text" and message.text.startswith("/unblacklist"))
def admin_unblacklist_cmd(message):
    """Admin command to unblacklist a user."""
    user_id = message.from_user.id
    if not is_admin_user(user_id): # Use unified admin check
        bot.send_message(message.chat.id, "You are not authorized to use this command.")
        return

    try:
        parts = message.text.split()
        if len(parts) == 2:
            target_user_id = int(parts[1])
            unblacklist_user(target_user_id) # Save to JSON
            bot.send_message(message.chat.id, f"User {target_user_id} has been unblacklisted.")
            try:
                bot.send_message(target_user_id, "You have been unblacklisted and can now use this bot.")
            except telebot.apihelper.ApiTelegramException:
                pass
        else:
            bot.send_message(message.chat.id, "Usage: `/unblacklist <user_id>`")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid user ID. Usage: `/unblacklist <user_id>`")
    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")

# --- Admin Add Admin Handler ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_admin")
def admin_add_admin_callback(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_admin_user(user_id):
        bot.answer_callback_query(call.id, "You are not authorized to use this option.")
        return

    bot.send_message(call.message.chat.id, "Please send the User ID of the person you want to add as an admin.")
    bot.answer_callback_query(call.id)
    # Register the next step to process the user ID
    bot.register_next_step_handler(call.message, process_add_admin_step)

def process_add_admin_step(message):
    user_id = message.from_user.id
    if not is_admin_user(user_id): # Re-check admin status
        bot.send_message(message.chat.id, "You are not authorized to perform this action.")
        return

    try:
        new_admin_id = int(message.text.strip())
        if new_admin_id == ADMIN_USER_ID or new_admin_id in additional_admins:
            bot.send_message(message.chat.id, f"User `{new_admin_id}` is already an admin.", parse_mode="Markdown")
        elif add_admin(new_admin_id):
            bot.send_message(message.chat.id, f"User `{new_admin_id}` has been added as an admin.", parse_mode="Markdown")
            try:
                bot.send_message(new_admin_id, "🎉 You have been granted admin access to the bot!")
            except telebot.apihelper.ApiTelegramException:
                pass # User might have blocked the bot
        else:
            bot.send_message(message.chat.id, "Failed to add admin. Please try again.")
    except ValueError:
        bot.send_message(message.chat.id, "Invalid User ID. Please send a valid numeric User ID.")
    except Exception as e:
        bot.send_message(message.chat.id, f"An error occurred: {e}")

# --- Handle chat_member_updated for automatic bot start after group join ---
@bot.chat_member_handler()
def chat_member_updates(message: telebot.types.ChatMemberUpdated):
    user_id = message.from_user.id
    old_status = message.old_chat_member.status
    new_status = message.new_chat_member.status
    chat_id = message.chat.id # This is the chat ID where the member status changed (i.e., the group's chat ID)

    # Debug print to see if the handler is triggered at all
    print(f"DEBUG: chat_member_updates triggered for user {user_id} in chat {chat_id}. Old status: {old_status}, New status: {new_status}")
    print(f"DEBUG: Configured GROUP_ID: {GROUP_ID}")

    # Check if the event is for *your* configured group
    if chat_id == GROUP_ID:
        # Check if the user was NOT a member ('left', 'kicked') and now IS a member ('member', 'administrator', 'creator', 'restricted')
        # This covers cases where a user joins for the first time or rejoins after leaving/being kicked.
        if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator', 'restricted']:
            print(f"DEBUG: User {user_id} ({message.new_chat_member.user.first_name}) explicitly joined/rejoined group {GROUP_ID}. Simulating /start.")
            # Added a small delay to potentially allow Telegram's state to propagate
            time.sleep(0.5)
            try:
                # Re-check the chat member status after a small delay
                updated_chat_member = bot.get_chat_member(GROUP_ID, user_id)
                if updated_chat_member.status in ['member', 'administrator', 'creator', 'restricted']:
                    dummy_message = telebot.types.Message.de_json({
                        "message_id": int(time.time()),
                        "from": message.new_chat_member.user.to_dict(),
                        "chat": { # Corrected: Use a dictionary for chat properties
                            "id": message.new_chat_member.user.id,
                            "type": "private", # Assuming this is always a private chat with the bot
                            "first_name": message.new_chat_member.user.first_name,
                            "last_name": message.new_chat_member.user.last_name,
                            "username": message.new_chat_member.user.username
                        },
                        "date": int(time.time()),
                        "text": "/start"
                    })
                    send_welcome(dummy_message)
                    print(f"DEBUG: send_welcome successfully called for user {user_id} after verified group join.")
                else:
                    print(f"DEBUG: User {user_id} was not confirmed as a member after delay. Status: {updated_chat_member.status}")
            except Exception as e:
                print(f"ERROR: Failed to re-check chat member status or send welcome message: {e}")
        elif old_status not in ['member', 'administrator', 'creator', 'restricted'] and \
             new_status in ['member', 'administrator', 'creator', 'restricted']:
            # This handles the initial join where old_status might not be 'left'/'kicked' (e.g., brand new user)
            print(f"DEBUG: User {user_id} ({message.new_chat_member.user.first_name}) transitioned to member status in group {GROUP_ID}. Simulating /start.")
            time.sleep(0.5)
            try:
                updated_chat_member = bot.get_chat_member(GROUP_ID, user_id)
                if updated_chat_member.status in ['member', 'administrator', 'creator', 'restricted']:
                    dummy_message = telebot.types.Message.de_json({
                        "message_id": int(time.time()),
                        "from": message.new_chat_member.user.to_dict(),
                        "chat": { # Corrected: Use a dictionary for chat properties
                            "id": message.new_chat_member.user.id,
                            "type": "private", # Assuming this is always a private chat with the bot
                            "first_name": message.new_chat_member.user.first_name,
                            "last_name": message.new_chat_member.user.last_name,
                            "username": message.new_chat_member.user.username
                        },
                        "date": int(time.time()),
                        "text": "/start"
                    })
                    send_welcome(dummy_message)
                    print(f"DEBUG: send_welcome successfully called for user {user_id} after verified initial join.")
                else:
                    print(f"DEBUG: User {user_id} was not confirmed as a member after delay on initial join. Status: {updated_chat_member.status}")
            except Exception as e:
                print(f"ERROR: Failed to re-check chat member status or send welcome message on initial join: {e}")
        else:
            print(f"DEBUG: chat_member_updates for user {user_id} in GROUP_ID {GROUP_ID} was not a valid join event (old: {old_status}, new: {new_status}).")
    else:
        print(f"DEBUG: chat_member_updates for a different chat_id {chat_id} (not configured GROUP_ID {GROUP_ID}).")


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """
    Handles all incoming messages.
    Performs access checks and processes search queries.
    """
    if not check_user_access(message):
        return

    user_id = message.from_user.id
    is_admin_check = is_admin_user(user_id) # Use unified admin check

    if message.content_type == "text":
        # Handle new keyboard buttons first
        if message.text == "Check My Credits":
            check_credits(message)
            return
        elif message.text == "Buy Credit":
            handle_buy_credit(message)
            return
        elif message.text == "Contact Admin":
            handle_contact_admin(message)
            return
        elif message.text == "Referral System":
            handle_referral_system(message)
            return
        elif message.text == "Main Menu":
            handle_main_menu(message)
            return
        elif is_admin_check and message.text == "Admin Panel":
            admin_panel(message)
            return
        elif message.text.startswith("/set_credits") or \
             message.text.startswith("/blacklist") or \
             message.text.startswith("/unblacklist"):
            # These are handled by their specific handlers, this prevents credit deduction
            pass
        else:
            # Process as a search query
            user_data = get_user_data(user_id)
            credits = user_data.get("credits", 0) if user_data else 0

            if credits <= 0:
                bot.send_message(
                    message.chat.id,
                    "🚫 You have no credits left. Please buy more to continue searching.",
                    reply_markup=create_pricing_message_keyboard() # Offer to buy credits when none left
                )
                return

            user_data["credits"] -= 1 # Deduct credit
            set_user_data(user_id, user_data) # Save updated credits to JSON

            bot.send_message(
                message.chat.id,
                f"Searching for '{message.text.splitlines()[0]}'...\n"
                f"Credits remaining: *{user_data['credits']}*",
                parse_mode="Markdown"
            )

            query_id = randint(0, 9999999)
            report = generate_report(message.text, query_id)

            # --- Handle "No results found" and refund credit ---
            if report is None:
                bot.reply_to(message, "The bot is unable to process your request at the moment. Please try again later.")
                # Add back the deducted credit for API errors
                user_data["credits"] += 1
                set_user_data(user_id, user_data)
                bot.send_message(message.chat.id, f"Your credit has been refunded due to a processing error. Current credits: *{user_data['credits']}*", parse_mode="Markdown")

                markup_after_result = InlineKeyboardMarkup()
                markup_after_result.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu"))
                bot.send_message(message.chat.id, "Please try another query or select an option:",
                                 reply_markup=markup_after_result)
                return
            elif report == ["No results found"]:
                bot.reply_to(message, "😔 No results found for your query.")
                # Refund credit if no results are found
                user_data["credits"] += 1
                set_user_data(user_id, user_data)
                bot.send_message(message.chat.id, f"Your credit has been refunded as no results were found. Current credits: *{user_data['credits']}*", parse_mode="Markdown")

                markup_after_result = InlineKeyboardMarkup()
                markup_after_result.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu"))
                bot.send_message(message.chat.id, "Please try another query or select an option:",
                                 reply_markup=markup_after_result)
                return

            # Continue with normal report display if results are found
            escaped_report_content = (
                report[0].replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
            )

            formatted_report_with_attribution = (
                f"<blockquote><pre><code>{escaped_report_content}</code></pre></blockquote>\n"
                "GENERATED BY @EAGLEHELP_ROBOT"
            )
            pagination_markup = create_inline_keyboard(query_id, 0, len(report))

            combined_markup = InlineKeyboardMarkup(row_width=3)
            if pagination_markup.keyboard:
                for row in pagination_markup.keyboard:
                    combined_markup.add(*row)

            combined_markup.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu"))

            try:
                bot.send_message(message.chat.id, formatted_report_with_attribution, parse_mode="html", reply_markup=combined_markup)
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Error sending HTML formatted message: {e}. Falling back to plain text within blockquote/pre.")
                escaped_plain_report_content = (
                    report[0].replace("&", "&amp;")
                                     .replace("<", "&lt;")
                                     .replace(">", "&gt;")
                )
                formatted_plain_report_with_attribution = (
                    f"<blockquote><pre><code>{escaped_plain_report_content}</code></pre></blockquote>\n"
                    "GENERATED BY @EAGLEHELP_ROBOT"
                )
                bot.send_message(message.chat.id, formatted_plain_report_with_attribution, parse_mode="html", reply_markup=combined_markup)
    else:
        bot.send_message(message.chat.id, "Please send a text query to search.", reply_markup=create_main_menu_keyboard(is_admin_check))

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    """Handles callback queries from inline buttons (pagination, pricing, and admin panel)."""
    user_id = call.from_user.id
    is_admin_check = is_admin_user(user_id) # Get admin status for menu

    if call.data == "show_pricing":
        # Handle the "Show Pricing" callback
        pricing_text = (
            "💰 *Access Pricing:*\n\n"
            "**1 WEEK ACCESS** = `300₹` / `150 🌟`\n"
            "**1 MONTH ACCESS** = `600₹` / `300🌟`\n"
            "**3 MONTH ACCESS** = `1000₹` / `500🌟`\n"
            "**LIFETIME ACCESS (API)** = `3000₹`\n\n"
            "Contact Admin for purchase:"
        )
        markup = create_pricing_message_keyboard()
        markup.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu")) # Add back button here
        bot.send_message(
            call.message.chat.id,
            pricing_text,
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id) # Acknowledge the callback

    elif call.data == "verify_group_membership":
        # Simulate a /start command when the "Verify" button is pressed
        user_id = call.from_user.id
        # Explicitly construct the chat dictionary from call.message.chat attributes
        # to avoid any potential issues with .to_dict() not being found or working unexpectedly.
        chat_data = {
            "id": call.message.chat.id,
            "type": call.message.chat.type,
            "first_name": call.message.chat.first_name,
            "last_name": call.message.chat.last_name,
            "username": call.message.chat.username
        }
        dummy_message = telebot.types.Message.de_json({
            "message_id": int(time.time()),
            "from": call.from_user.to_dict(),
            "chat": chat_data, # Use the explicitly constructed dictionary
            "date": int(time.time()),
            "text": "/start"
        })
        # Delete the previous message with the "Join Group" and "Verify" buttons
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except telebot.apihelper.ApiTelegramException as e:
            print(f"Could not delete message: {e}") # Log if deletion fails

        send_welcome(dummy_message)
        bot.answer_callback_query(call.id, text="Checking membership...") # Acknowledge callback

    elif call.data.startswith("/page "):
        query_id, page_id = call.data.split(" ")[1:]
        if query_id not in cash_reports:
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="The results of this request have expired or were deleted.")
            # Add "Back to Main Menu" button after expiration
            markup_after_result = InlineKeyboardMarkup()
            markup_after_result.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu"))
            bot.send_message(call.message.chat.id, "Please try another query or select an option:",
                             reply_markup=markup_after_result) # Use inline button here
        else:
            report = cash_reports[query_id]
            current_page_id = int(page_id)
            if current_page_id < 0:
                current_page_id = len(report) - 1
            elif current_page_id >= len(report):
                current_page_id = 0

            # Combine formatted report with attribution
            # The report content from generate_report now has <b> tags stripped.
            # So, only HTML escape the general special characters that would break <pre><code>
            escaped_report_content = (
                report[current_page_id].replace("&", "&amp;")
                                       .replace("<", "&lt;")
                                       .replace(">", "&gt;")
            )
            formatted_report_with_attribution = (
                f"<blockquote><pre><code>{escaped_report_content}</code></pre></blockquote>\n"
                "GENERATED BY @EAGLEHELP_ROBOT"
            )
            pagination_markup = create_inline_keyboard(query_id, current_page_id, len(report))

            # Create a combined markup for results and back button
            combined_markup = InlineKeyboardMarkup(row_width=3)
            if pagination_markup.keyboard: # Add pagination buttons if they exist
                for row in pagination_markup.keyboard:
                    combined_markup.add(*row)

            # Add the "Back to Main Menu" button
            combined_markup.add(InlineKeyboardButton(text="⬅️ Back to Main Menu", callback_data="back_to_main_menu"))

            try:
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=formatted_report_with_attribution, parse_mode="html", reply_markup=combined_markup)
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Error editing HTML formatted message: {e}. Falling back to plain text within blockquote/pre.")
                escaped_plain_report_content = (
                    report[current_page_id].replace("&", "&amp;")
                                     .replace("<", "&lt;")
                                     .replace(">", "&gt;")
                )
                formatted_plain_report_with_attribution = (
                    f"<blockquote><pre><code>{escaped_plain_report_content}</code></pre></blockquote>\n"
                    "GENERATED BY @EAGLEHELP_ROBOT"
                )
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=formatted_plain_report_with_attribution, parse_mode="html", reply_markup=combined_markup)

            bot.answer_callback_query(call.id) # Acknowledge the callback

    elif call.data == "page_list_noop":
        bot.answer_callback_query(call.id, text="This is the current page.")

    elif call.data == "back_to_main_menu":
        user_id = call.from_user.id
        is_admin_check = is_admin_user(user_id)
        current_user_data = get_user_data(user_id)
        current_credits = current_user_data.get('credits', INITIAL_FREE_CREDITS)
        current_referrals = current_user_data.get('referral_count', 0)

        # Content for returning to main menu
        main_menu_return_text = (
            f"Welcome back to the main menu!\n\n"
            f"**📊 YOUR CREDIT** 💰 = `{current_credits}`\n\n"
            f"**👥 TOTAL REFERRALS** 📈 = `{current_referrals}`\n\n"
            f"**🔗 YOUR REFERRAL LINK** 👇 = `https://t.me/{BOT_USERNAME}?start=ref_{user_id}`\n\n"
            "**(_NB: 5 REFERRALS = 1 CREDIT_)**\n\n"
            "**START SEARCH🔍**\n"
            "**EG-**\n"
            "**- +91XXXXXXXX**\n"
            "**- example@gmail.com**\n"
            "**- Name1234**"
        )

        bot.send_message(
            call.message.chat.id,
            main_menu_return_text,
            parse_mode="Markdown"
        )
        bot.send_message(
            call.message.chat.id,
            "What would you like to do?", # Prompt for the reply keyboard
            reply_markup=create_main_menu_keyboard(is_admin_check)
        )
        bot.answer_callback_query(call.id) # Acknowledge the callback

    # --- Admin Panel Callbacks ---
    elif call.data.startswith("admin_"):
        if not is_admin_user(user_id): # Unified admin check
            bot.answer_callback_query(call.id, "You are not authorized to use this option.")
            return

        action = call.data.split("admin_")[1]

        if action == "view_users":
            # Iterate through the in-memory users_data dictionary
            user_list_text = "📊 *All Users:*\n\n"
            users_found = False
            for user_id_str, user_data in users_data.items():
                users_found = True
                credits = user_data.get("credits", 0)
                referrals = user_data.get("referral_count", 0)
                is_blacklisted_status = "🚫" if is_user_blacklisted(user_id_str) else ""

                user_name = "Unknown User"
                try:
                    chat_info = bot.get_chat(int(user_id_str))
                    if chat_info.username:
                        user_name = f"@{chat_info.username}"
                    elif chat_info.first_name and chat_info.last_name:
                        user_name = f"{chat_info.first_name} {chat_info.last_name}"
                    elif chat_info.first_name:
                        user_name = chat_info.first_name
                except telebot.apihelper.ApiTelegramException as e:
                    # This can happen if the bot can't access chat info (e.g., user blocked the bot)
                    print(f"Could not fetch chat info for user {user_id_str}: {e}")
                    user_name = "Cannot retrieve name"


                user_list_text += f"👤 *Name/Username*: {user_name}\n" \
                                  f"   *ID*: `{user_id_str}`\n" \
                                  f"   *Credits*: {credits}\n" \
                                  f"   *Referrals*: {referrals} {is_blacklisted_status}\n\n"

            if not users_found:
                user_list_text += "No users found in the database."

            if len(user_list_text) > 4000: # Telegram message limit
                bot.send_message(call.message.chat.id, user_list_text[:4000], parse_mode="Markdown")
                bot.send_message(call.message.chat.id, "... (truncated) For full list, check the 'bot_data/users.json' file directly.")
            else:
                bot.send_message(call.message.chat.id, user_list_text, parse_mode="Markdown")
            bot.answer_callback_query(call.id, "Users list generated.")

        elif action == "manage_credits":
            bot.send_message(call.message.chat.id, "To set credits, send: `/set_credits <user_id> <amount>`\n"
                                                  "Example: `/set_credits 123456789 10`", parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif action == "blacklist":
            bot.send_message(call.message.chat.id, "To blacklist a user, send: `/blacklist <user_id>`\n"
                                                  "Example: `/blacklist 987654321`", parse_mode="Markdown")
            bot.answer_callback_query(call.id)

        elif action == "unblacklist":
            bot.send_message(call.message.chat.id, "To unblacklist a user, send: `/unblacklist <user_id>`\n"
                                                  "Example: `/unblacklist 987654321`", parse_mode="Markdown")
            bot.answer_callback_query(call.id)

    else:
        bot.answer_callback_query(call.id, "Unknown action.")


# --- Bot Polling ---
print("Bot polling started...")
while True:
    try:
        # Use none_stop=True to keep polling even if updates are not coming in.
        # Use interval=0 for immediate processing of updates.
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Bot polling error: {e}")
        # Implement exponential backoff for retries
        time.sleep(5) # Wait before retrying to prevent rapid error loops